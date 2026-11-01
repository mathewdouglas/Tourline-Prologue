"""Frozen opt-in vertex workers: cancellation, verified resume and zero-worker reuse.

Uses a local release ZIP and original assets; no guest entry or game-data copy.
All tests run sequentially in fresh ignored storage. No shadercache is removed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_template import read, bundle
from train_pipeline_cache import isolated, idle


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('zip', 'helper-dir', 'template', 'elf', 'assets', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    a = ap.parse_args()
    idle()
    out = isolated(a.output)
    if out.exists():
        raise ValueError('Use a fresh ignored output')
    install, storage = out/'Install with spaces', out/'Storage'
    install.mkdir(parents=True)
    with zipfile.ZipFile(a.zip) as archive:
        for name in archive.namelist():
            if not name.startswith(('preparation/', 'assets/pipeline-templates/')):
                archive.extract(name, install)
    shutil.copytree(a.helper_dir, install/'preparation')
    document = read(a.template)
    target = install/'assets/pipeline-templates/gt5p-disc-v2'
    bundle(document, target)
    original = Path(__file__).resolve().parents[2]/'assets/pipeline-templates/gt5p-disc-v2'
    shutil.copyfile(original/'player-map.json', target/'player-map.json')
    (storage/'input').mkdir(parents=True)
    shutil.copyfile(a.elf, storage/'input/EMAIN.ELF')
    source = storage/'preparation'/('a'*24)/'shadercache'
    source.mkdir(parents=True)
    marker = source/'preserved.txt'
    marker.write_text('Prior selection and cache must survive cancellation.')
    previous = source.relative_to(storage).as_posix()
    pointer = storage/'prepared-cache.txt'
    pointer.write_text(previous)
    command = [str((install/'preparation/GT5P-Prepare.exe').resolve()), '--install', str(install.resolve()),
        '--storage', str(storage.resolve()), '--assets', str(a.assets.resolve())]
    env = dict(os.environ, PS3_VERBOSE='0', GT5P_PREPARE_VERTEX_BATCH='1',
               PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    started = time.perf_counter()
    with (out/'cancel.log').open('wb') as log:
        child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.monotonic()+90
            while child.poll() is None:
                generations = [p for p in source.parent.parent.iterdir() if p != source.parent]
                text = (storage/'prepare-status.txt').read_text() if (storage/'prepare-status.txt').exists() else ''
                if text.startswith('Vertex') and generations and list((generations[0]/'shadercache').glob('*.dxbc')):
                    (storage/'prepare.cancel').write_text('cancel')
                    break
                if time.monotonic() > deadline:
                    raise AssertionError('Vertex batch did not make progress')
                time.sleep(.02)
            assert child.wait(timeout=20) == 2, (out/'cancel.log').read_text(errors='replace')
        finally:
            if child.poll() is None:
                child.terminate()
                child.wait(timeout=10)
    state = generations[0]/'preparation-state.json'
    assert json.loads(state.read_text())['phase'] == 'interrupted'
    assert pointer.read_text() == previous and marker.read_text().startswith('Prior selection')
    kept = len(list((state.parent/'shadercache').glob('*.dxbc')))
    assert kept > 0
    (storage/'prepare.cancel').unlink()  # Only this test's request marker; no cache removal.
    with (out/'resume.log').open('wb') as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW, check=True, timeout=900)
    first = json.loads((state.parent/'report.json').read_text())
    assert first['counts'] == {'prepared': len(document['records'])}
    assert first['resume']['vertex_programs_reused'] >= kept
    assert first['vertex_preparation']['launches'] <= 2
    assert first['vertex_preparation']['ownership'] == 'private-job'
    assert 0 < first['vertex_preparation']['worker_job_peak_commit_bytes'] <= 1024**3
    selected = pointer.read_text()
    assert selected == (state.parent/'shadercache').relative_to(storage).as_posix()
    with (out/'cached.log').open('wb') as log:
        subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW, check=True, timeout=900)
    cached = json.loads((state.parent/'report.json').read_text())
    assert cached['counts'] == first['counts']
    assert cached['vertex_preparation']['launches'] == 0
    assert cached['resume']['vertex_programs_compiled'] == 0
    assert cached['fragment_preparation']['processes'] == 0
    assert pointer.read_text() == selected and marker.read_text().startswith('Prior selection')
    serial_env = env.copy()
    serial_env.pop('GT5P_PREPARE_VERTEX_BATCH')
    with (out/'serial-rollback.log').open('wb') as log:
        subprocess.run(command, env=serial_env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW, check=True, timeout=900)
    rollback = json.loads((state.parent/'report.json').read_text())
    assert rollback['counts'] == first['counts'] and rollback['vertex_preparation']['mode'] == 'serial'
    assert rollback['resume']['vertex_programs_compiled'] == 0 and pointer.read_text() == selected
    # An invalid player switch must not disturb the successful selected generation.
    with (out/'invalid.log').open('wb') as log:
        rejected = subprocess.run(command, env=dict(env, GT5P_PREPARE_VERTEX_BATCH='invalid'),
            stdout=log, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW, timeout=30)
    assert rejected.returncode != 0 and pointer.read_text() == selected
    result = dict(counts=first['counts'], kept_vertices=kept, resumed=first['vertex_preparation'],
        cached=cached['vertex_preparation'], cancellation_preserved_selection=True,
        invalid_mode_preserved_selection=True, source_preserved=True, clean_path=True,
        serial_default_rollback_passed=True,
        seconds=time.perf_counter()-started,
        limitation='Small original-asset proof, warm OS/driver caches; no gameplay/stutter measurement.')
    (out/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
