"""Frozen full-starter preparation with cancel/resume and optional incremental reuse.

Run under the shared test lock. Original game/install files are read-only. The
frozen helper, a private runtime and the repository starter are copied into a
fresh ignored output; the user's real caches and storage are never touched.

  --mode fresh        cancel once native input starts, check the old selection
                      stayed, resume, require every record prepared
  --mode incremental  start with storage pointing at an earlier generation
                      (--previous-cache, a preparation/<24 hex>/shadercache
                      directory prepared by an older renderer) and prepare with
                      reuse enabled
Only counts/timings are written; shader/driver output stays in the ignored
output until the caller removes it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_template as template
from train_pipeline_cache import idle, isolated


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('helper-dir', 'runtime', 'elf', 'game', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--mode', choices=('fresh', 'incremental'), default='fresh')
    ap.add_argument('--previous-cache', type=Path, help='Earlier-generation shadercache directory (incremental mode)')
    ap.add_argument('--translation', default=None, help='GT5P_PREPARE_TRANSLATION override')
    ap.add_argument('--limit', type=int, default=0, help='Use only the first N records (subset install)')
    a = ap.parse_args()
    idle()
    out = isolated(a.output)
    if out.exists():
        raise ValueError('Use a fresh ignored output')
    install = out / 'Install'
    storage = out / 'Storage'
    (storage / 'input').mkdir(parents=True)
    shutil.copytree(a.runtime, install / 'runtime')
    shutil.copytree(a.helper_dir, install / 'preparation')
    shutil.copyfile(a.elf, storage / 'input/EMAIN.ELF')
    original = template.ROOT / 'assets/pipeline-templates/gt5p-disc-v2'
    bundle = install / 'assets/pipeline-templates/gt5p-disc-v2'
    if a.limit:
        document = template.read(original)
        template.bundle(dict(document, records=document['records'][:a.limit]), bundle)
        for name in ('player-map.json', 'volume-map.json'):
            shutil.copyfile(original / name, bundle / name)
    else:
        shutil.copytree(original, bundle)
    pointer = storage / 'prepared-cache.txt'
    preserved = None
    if a.mode == 'incremental':
        if a.previous_cache is None or not re.fullmatch(r'[0-9a-f]{24}', a.previous_cache.parent.name):
            raise ValueError('Incremental mode needs --previous-cache <...>/preparation/<24 hex>/shadercache')
        target = storage / 'preparation' / a.previous_cache.parent.name / 'shadercache'
        target.parent.mkdir(parents=True)
        shutil.copytree(a.previous_cache, target)
        pointer.write_text(target.relative_to(storage).as_posix())
    else:
        source = storage / 'preparation' / ('a' * 24) / 'shadercache'
        source.mkdir(parents=True)
        (source / 'preserved.txt').write_text('Prior cache stays intact')
        pointer.write_text(source.relative_to(storage).as_posix())
        preserved = (source, snapshot(source))
    previous = pointer.read_text()
    command = [str(install / 'preparation/GT5P-Prepare.exe'), '--install', str(install),
               '--storage', str(storage), '--game', str(a.game.resolve())]
    if a.mode == 'fresh':
        command.append('--no-reuse')
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(('GT5P_', 'RSX_'))}
    env.update(PS3_VERBOSE='0', PATH=str(Path(os.environ['SystemRoot']) / 'System32'))
    if a.translation:
        env['GT5P_PREPARE_TRANSLATION'] = a.translation
    cancel = storage / 'prepare.cancel'
    summary = dict(mode=a.mode, records=None)

    def run(name, check=True):
        begin = time.perf_counter()
        with (out / (name + '.log')).open('wb') as log:
            result = subprocess.run(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                    timeout=3000, creationflags=subprocess.CREATE_NO_WINDOW)
        seconds = time.perf_counter() - begin
        if check and result.returncode:
            raise AssertionError((out / (name + '.log')).read_text(errors='replace')[-3000:])
        summary[name + '_seconds'] = round(seconds, 2)
        return result.returncode

    if a.mode == 'fresh':
        begin = time.perf_counter()
        with (out / 'cancel.log').open('wb') as log:
            child = subprocess.Popen(command, env=env, stdout=log, stderr=subprocess.STDOUT,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                deadline = time.monotonic() + 1500
                while child.poll() is None:
                    try:
                        text = (storage / 'prepare-status.txt').read_text()
                    except OSError:
                        text = ''
                    if re.fullmatch(r'Native input \d+/\d+', text) and int(text.split()[2].split('/')[0]) > 0:
                        cancel.write_text('cancel')
                        break
                    if time.monotonic() > deadline:
                        raise AssertionError('Native input stage never started')
                    time.sleep(.05)
                code = child.wait(timeout=120)
                assert code == 2, (out / 'cancel.log').read_text(errors='replace')[-3000:]
            finally:
                if child.poll() is None:
                    child.terminate()
                    child.wait(timeout=15)
        summary['cancel_seconds'] = round(time.perf_counter() - begin, 2)
        generations = [p for p in (storage / 'preparation').iterdir() if p.name != 'a' * 24]
        assert len(generations) == 1
        state = json.loads((generations[0] / 'preparation-state.json').read_text())
        assert state['phase'] == 'interrupted', state
        assert pointer.read_text() == previous and snapshot(preserved[0]) == preserved[1]
        summary['interrupted_shader_files'] = sum(1 for _ in (generations[0] / 'shadercache').glob('*.dxbc'))
        cancel.unlink()
        run('resume')
    else:
        run('prepare')
    generations = [p for p in (storage / 'preparation').iterdir()
                   if (p / 'report.json').exists() and p.name != 'a' * 24
                   and not (a.previous_cache and p.name == a.previous_cache.parent.name)]
    assert len(generations) == 1, generations
    generation = generations[0]
    report = json.loads((generation / 'report.json').read_text())
    total = report['requested']
    assert report['counts'] == {'prepared': total}, report['counts']
    assert pointer.read_text() == (generation / 'shadercache').relative_to(storage).as_posix()
    summary.update(records=total, counts=report['counts'],
                   preparation_seconds=round(report['preparation_seconds'], 2),
                   resume=report['resume'], cache_reuse=report.get('cache_reuse'),
                   vertex=report.get('vertex_preparation', {}).get('seconds'),
                   fragment=report.get('fragment_preparation', {}).get('seconds'),
                   native_handoff=report.get('native_handoff'),
                   inventory={k: (v if isinstance(v, (int, float, str)) else len(v))
                              for k, v in report['inventory'].items()},
                   shader_packs=report.get('shader_packs'),
                   warmup_plan=report.get('warmup_plan'))
    if report.get('native_timings'):
        summary['native_batches'] = [dict(requested=t.get('requested'), created=t.get('created'),
                                          driver_calls=t.get('driver_calls'), cached=t.get('cached_blob_calls'))
                                     for t in report['native_timings']]
    if preserved:
        assert snapshot(preserved[0]) == preserved[1]
        summary['old_selection_preserved'] = True
    (out / 'validation.json').write_text(json.dumps(summary, indent=2, default=str) + '\n')
    print(json.dumps(summary, indent=2, default=str))


if __name__ == '__main__':
    main()
