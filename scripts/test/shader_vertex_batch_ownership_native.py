"""Kill a compiler owner inside a surviving outer job; only its workers must exit."""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shader_vertex_batch as batch
from train_pipeline_cache import isolated, idle


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--decoder', type=Path, required=True)
    ap.add_argument('--worker-exe', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--child', action='store_true', help=argparse.SUPPRESS)
    ap.add_argument('--workers', type=int, choices=(2,3,4), default=2)
    a = ap.parse_args()
    out = isolated(a.output)
    if out.exists():
        raise ValueError('Use a fresh ignored output')
    out.mkdir(parents=True)
    if a.child:
        batch.worker_command = lambda decoder: [str(a.worker_exe.resolve()), batch.SENTINEL, str(Path(decoder).resolve())]
        pool, workers = batch.open_workers(a.workers, a.decoder.resolve(), out)
        try:
            (out/'workers.json').write_text(json.dumps([w.pid for w in workers]))
            time.sleep(30)
        finally:
            pool.retire(workers)
        return
    idle()
    outer = batch._WinPool()
    kernel = outer.kernel
    kernel.OpenProcess.argtypes = [C.c_ulong, C.c_int, C.c_ulong]
    kernel.OpenProcess.restype = C.c_void_p
    child_out = out/'nested owner'
    command = [sys.executable, str(Path(__file__).resolve()), '--child', '--decoder', str(a.decoder.resolve()),
        '--worker-exe', str(a.worker_exe.resolve()), '--output', str(child_out.resolve()), '--workers',str(a.workers)]
    owner = None
    observed = []
    try:
        owner = batch._create_worker(outer, 0, subprocess.list2cmdline(command), out,
                                     batch.shader_translation.environment('default'))
        deadline = time.monotonic()+15
        while not (child_out/'workers.json').exists():
            assert owner.alive() and time.monotonic() < deadline
            time.sleep(.05)
        pids = json.loads((child_out/'workers.json').read_text())
        assert len(pids) == a.workers
        for pid in pids:
            handle = kernel.OpenProcess(0x00100000, False, pid)
            assert handle
            observed.append(handle)
        owner.retire()  # Outer job deliberately remains open.
        for handle in observed:
            assert kernel.WaitForSingleObject(handle, 10000) == 0, 'Nested frozen worker outlived its owner'
        result = dict(frozen_workers=a.workers, nested_private_job=True, owner_exit_retired_workers=True,
            outer_job_remained_open=True, no_game_started=True)
        (out/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
        print(json.dumps(result))
    finally:
        for handle in observed:
            kernel.CloseHandle(handle)
        outer.retire([owner] if owner else [])


if __name__ == '__main__':
    main()
