"""Sequential real vertex/pipeline parity and owned-worker checks; no guest entry.

Reads original assets, writes only a fresh ignored output, never removes a cache.
The parent runs this after all other executable tests are idle.
"""
import argparse
import ctypes as C
import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_template as template
import shader_vertex_batch as batch
from shader_reconstruct import NativeCompiler
from train_pipeline_cache import isolated, idle


def handles():
    kernel = batch.ctypes_kernel()
    kernel.OpenProcess.argtypes = [C.c_ulong, C.c_int, C.c_ulong]
    kernel.OpenProcess.restype = C.c_void_p
    return kernel


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('assets', 'elf', 'engine', 'decoder', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--count', type=int, default=32)
    ap.add_argument('--vertex-only', action='store_true', help='Compare every selected variant without repeating pipeline checks')
    ap.add_argument('--owner-probe', action='store_true', help=argparse.SUPPRESS)
    a = ap.parse_args()
    for name in ('assets', 'elf', 'engine', 'decoder'):
        setattr(a, name, getattr(a, name).resolve())
    out = isolated(a.output)
    if a.owner_probe:
        out.mkdir(parents=True)
        pool, workers = batch.open_workers(2, a.decoder.resolve(), out)
        (out/'owned.json').write_text(json.dumps([w.pid for w in workers]))
        try:
            time.sleep(30)
        finally:
            pool.retire(workers)
        return
    idle()
    if out.exists():
        raise ValueError('Use a fresh ignored output; nothing was overwritten')
    out.mkdir(parents=True)
    (out/'input').mkdir()
    shutil.copyfile(a.elf, out/'input/EMAIN.ELF')
    bundle = template.ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    document = template.read(bundle)
    chosen, seen = [], set()
    for record in document['records']:
        identity = (record['vp']['sha256'], record['vp_gpu'])
        if identity not in seen:
            seen.add(identity)
            chosen.append(record)
        if len(chosen) == a.count:
            break
    if not 2 <= len(chosen) == a.count <= 4096:
        raise ValueError('Insufficient unique bounded vertex variants')
    subset = dict(document, records=chosen)
    selected = out/'template.json'
    selected.write_text(json.dumps(subset))
    locations = bundle/'player-map.json'
    vertices, fragments, lookup = template.locate(chosen, None, a.elf, locations, a.assets)
    assert all(r['vp']['sha256'] in vertices and r['fp']['sha256'] in fragments for r in chosen)
    decisions, jobs, _, _ = batch.plan_vertices(chosen, vertices, fragments, {})
    assert len(jobs) == a.count and all(d[0] == 'ready' for d in decisions)
    compiler = NativeCompiler(a.decoder)
    start = time.perf_counter()
    expected = {}
    for job in jobs:
        source, code = compiler.vertex(job['program'], bool(job['gpu']))
        expected[(job['sha256'], job['gpu'])] = batch.accept_result(job,
            batch._echo(job['sha256'], job['gpu'], job['expected_source'], job['expected_code']), source, code)
        if len(expected) % 32 == 0:
            print(f'Serial vertex variants {len(expected)}/{len(jobs)}', flush=True)
    serial_seconds = time.perf_counter() - start
    kernel = handles()
    observed = []
    original_open = batch.open_workers

    def observe(count, decoder, work):
        pool, workers = original_open(count, decoder, work)
        for worker in workers:
            handle = kernel.OpenProcess(0x00100000, False, worker.pid)
            assert handle
            observed.append(handle)
        return pool, workers

    def retired():
        for handle in observed:
            try:
                assert kernel.WaitForSingleObject(handle, 10000) == 0, 'Owned worker survived'
            finally:
                kernel.CloseHandle(handle)
        observed.clear()

    actual, failures, timing = batch.compile_jobs(jobs, a.decoder, out/'direct batch', opener=observe)
    retired()
    assert not failures and actual == expected
    assert timing['launches'] == 2 and timing['ownership'] == 'private-job'
    if a.vertex_only:
        result = dict(variants=a.count, lookup=lookup, serial_vertex_seconds=serial_seconds,
            batch_vertex=timing, direct_bytecode_equal=True,
            limitation='Vertex-only comparison; no pipeline or live stutter measurement in this run.')
        (out/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result, indent=2))
        return
    # A real cancellation after one accepted result preserves that result and joins both workers.
    accepted = []
    def poll():
        if accepted:
            raise KeyboardInterrupt('Native cancellation probe')
    def on_ready(job, source_id, code_id, code):
        accepted.append(source_id)
        template.save_code(out/(source_id+'.dxbc'), code)
    try:
        batch.compile_jobs(jobs, a.decoder, out/'cancel batch', opener=observe, poll=poll, on_ready=on_ready)
    except KeyboardInterrupt:
        pass
    else:
        raise AssertionError('Cancellation did not interrupt the real batch')
    retired()
    assert accepted and all((out/(name+'.dxbc')).is_file() for name in accepted)
    # Force the owner to exit. Only its private-job worker handles are observed.
    command = [sys.executable, str(Path(__file__).resolve()), '--owner-probe']
    for name in ('assets', 'elf', 'engine', 'decoder'):
        command += ['--'+name, str(getattr(a, name).resolve())]
    owner_out = out/'abrupt owner'
    child = subprocess.Popen(command+['--output', str(owner_out.resolve())], creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic()+15
        while not (owner_out/'owned.json').exists():
            assert child.poll() is None and time.monotonic() < deadline
            time.sleep(.05)
        for pid in json.loads((owner_out/'owned.json').read_text()):
            handle = kernel.OpenProcess(0x00100000, False, pid)
            assert handle
            observed.append(handle)
        child.terminate()
        child.wait(timeout=10)
        retired()
    finally:
        if child.poll() is None:
            child.terminate()
            child.wait(timeout=10)
        retired()
    # Full independent empty caches still verify both shaders, exact keys and D3D12 creation.
    reports = {}
    for mode in ('serial', 'batch'):
        report = template.prepare(selected, None, a.elf, a.engine, a.decoder, out, out/mode,
            asset_map=locations, assets=a.assets, vertex_mode=mode)
        assert report['counts'] == {'prepared': a.count}
        reports[mode] = dict(seconds=report['preparation_seconds'], vertex=report['vertex_preparation'])
    serial_files = {p.name:p.read_bytes() for p in (out/'serial/shadercache').glob('*.dxbc')}
    batch_files = {p.name:p.read_bytes() for p in (out/'batch/shadercache').glob('*.dxbc')}
    assert serial_files == batch_files
    resumed = template.prepare(selected, None, a.elf, a.engine, a.decoder, out, out/'batch',
        asset_map=locations, assets=a.assets, vertex_mode='batch', resume=True)
    assert resumed['counts'] == {'prepared': a.count}
    assert resumed['vertex_preparation']['launches'] == 0
    assert resumed['resume']['vertex_programs_compiled'] == 0
    assert resumed['fragment_preparation']['processes'] == 0
    result = dict(records=a.count, lookup=lookup, serial_vertex_seconds=serial_seconds,
        batch_vertex=timing, direct_bytecode_equal=True, owned_cancel_passed=True,
        owner_death_passed=True, pipelines=reports, resume_zero_workers=True,
        limitation='Local first-run preparation only; no live stutter measurement; OS/driver caches warm.')
    (out/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
