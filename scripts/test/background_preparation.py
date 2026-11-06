"""Phase 225 background preparation: switches, race selection and the merge into a live cache (synthetic; no game).

1. GT5P_PREPARE_BACKGROUND / GT5P_PREPARE_BACKGROUND_WORKERS parsing and the worker default.
2. race_records: the plan's race identities in template order; a plan naming records outside the template is refused.
   On the shipped starter: 2,113 records.
3. merge: shader bytes, driver blobs and code files land; files the game already has are never replaced; only the
   race keys' recipes are copied (after everything they reference); lists, packs, the lookup table and other
   names stay out; the race index gains only missing keys, after the game's own lines; a second merge places
   nothing. Merge records are per live cache. A truncated shader or blob is not placed.
4. Trickle (Phase 226): while the stage runs, complete shaders and driver blobs reach the live cache at most once per
   interval; incomplete files wait for a later pass; game files are never replaced; recipes and the race list wait
   for the final merge. prepare_race trickles during the stage (live files appear before it returns) and records the
   counts; GT5P_PREPARE_BACKGROUND_TRICKLE=0 copies only at the end.
"""
import json
import os
from pathlib import Path
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import background_preparation as b  # noqa: E402
from shader_coverage import fnv64  # noqa: E402


def dxbc(n):
    body = bytes([n]) * (8 + n)
    return b'DXBC' + bytes(16) + struct.pack('<III', 1, 32 + len(body), 0) + body


def blob(n):
    body = bytes([n]) * (16 + n)
    return struct.pack('<QQQ', 0x31534f5035505447, len(body), fnv64(body)) + body


def switches():
    assert b.enabled({}) and b.enabled({'GT5P_PREPARE_BACKGROUND': '1'}) and not b.enabled({'GT5P_PREPARE_BACKGROUND': '0'})
    for bad in ('', 'yes', '2'):
        try:
            b.enabled({'GT5P_PREPARE_BACKGROUND': bad})
            raise AssertionError('accepted ' + bad)
        except ValueError:
            pass
    assert b.workers({}, 12) == 6 and b.workers({}, 4) == 2 and b.workers({}, 1) == 2 and b.workers({}, 64) == 12
    assert b.workers({'GT5P_PREPARE_BACKGROUND_WORKERS': '3'}, 12) == 3
    for bad in ('1', '13', 'x'):
        try:
            b.workers({'GT5P_PREPARE_BACKGROUND_WORKERS': bad}, 12)
            raise AssertionError('accepted ' + bad)
        except ValueError:
            pass
    print('switches: passed')


def selection():
    document = dict(records=[dict(key=k) for k in 'abcde'])
    plan = dict(phases=dict(menu=['a'], race=['d', 'b']))
    assert [r['key'] for r in b.race_records(document, plan)] == ['b', 'd']
    try:
        b.race_records(document, dict(phases=dict(menu=[], race=['z'])))
        raise AssertionError('foreign race key accepted')
    except ValueError:
        pass
    from pipeline_template import read
    from pipeline_warmup_plan import load
    bundle = ROOT / 'assets/pipeline-templates/gt5p-disc-v2'
    records = b.race_records(read(bundle), load(ROOT / 'config/pipeline-warmup/gt5p-disc-v2.json', bundle))
    assert len(records) == 2113, len(records)
    print('race selection: passed (starter: 2,113 race records)')


def merge():
    key = lambda n: f'{n:016x}'  # noqa: E731
    with tempfile.TemporaryDirectory() as d:
        stage, live = Path(d) / 'stage', Path(d) / 'live'
        (stage / 'warmup-v1').mkdir(parents=True)
        (live / 'warmup-v1').mkdir(parents=True)
        for n in (1, 2, 3):
            (stage / (key(n) + '.dxbc')).write_bytes(dxbc(n))
            (stage / ('pso_' + key(n) + '.bin')).write_bytes(blob(n))
            (stage / 'warmup-v1' / ('code_' + key(n) + '.dxbc')).write_bytes(dxbc(n + 10))
            (stage / 'warmup-v1' / ('pso_' + key(n) + '.recipe')).write_bytes(b'recipe' + bytes([n]))
        for name in ('race-v1.txt', 'menu-v1.txt', 'fp-lookup-v2-0123.bin', 'race-shaders-v1.pack', 'notes.txt'):
            (stage / name).write_text('stage')
            (stage / 'warmup-v1' / name).write_text('stage')
        # What the game already wrote: one shader (different bytes must stay), a recipe and its own race list.
        (live / (key(1) + '.dxbc')).write_bytes(b'GAME')
        (live / 'warmup-v1' / ('pso_' + key(2) + '.recipe')).write_bytes(b'game recipe')
        (live / 'warmup-v1' / 'race-v1.txt').write_text(key(9) + '\n' + key(2) + '\n')
        counts = b.merge(stage, live, [key(1), key(2)])
        assert counts == dict(placed=8, present=1, incomplete=0, recipes=1, race_keys=2, race_appended=1), counts
        assert (live / (key(1) + '.dxbc')).read_bytes() == b'GAME'
        assert (live / 'warmup-v1' / ('pso_' + key(2) + '.recipe')).read_bytes() == b'game recipe'
        assert (live / 'warmup-v1' / ('pso_' + key(1) + '.recipe')).read_bytes() == b'recipe\x01'
        assert not (live / 'warmup-v1' / ('pso_' + key(3) + '.recipe')).exists(), 'non-race recipe copied'
        assert (live / 'warmup-v1' / 'race-v1.txt').read_text() == key(9) + '\n' + key(2) + '\n' + key(1) + '\n'
        for name in ('menu-v1.txt', 'fp-lookup-v2-0123.bin', 'race-shaders-v1.pack', 'notes.txt'):
            assert not (live / name).exists() and not (live / 'warmup-v1' / name).exists(), name
        assert not list(live.rglob('*.tmp')), 'temporary files left'
        again = b.merge(stage, live, [key(1), key(2)])
        assert again == dict(placed=0, present=9, incomplete=0, recipes=0, race_keys=2, race_appended=0), again
        (stage / (key(4) + '.dxbc')).write_bytes(dxbc(4)[:-1])
        (stage / ('pso_' + key(4) + '.bin')).write_bytes(blob(4)[:-1] + b'x')
        torn = b.merge(stage, live, [])
        assert torn['incomplete'] == 2 and torn['placed'] == 0, torn
        assert not (live / (key(4) + '.dxbc')).exists() and not (live / ('pso_' + key(4) + '.bin')).exists()
        folder = Path(d) / 'race'
        folder.mkdir()
        (folder / b.MARKER).write_text(json.dumps(dict(live_cache=str(live.resolve()))))
        assert b.merged(folder, live) is not None and b.merged(folder, stage) is None
        try:
            b.merge(stage, live, ['../x'])
            raise AssertionError('malformed key accepted')
        except ValueError:
            pass
    print('merge: passed')


def trickle_pass():
    key = lambda n: f'{n:016x}'  # noqa: E731
    assert b.trickle_enabled({}) and not b.trickle_enabled({'GT5P_PREPARE_BACKGROUND_TRICKLE': '0'})
    try:
        b.trickle_enabled({'GT5P_PREPARE_BACKGROUND_TRICKLE': 'on'})
        raise AssertionError('accepted on')
    except ValueError:
        pass
    with tempfile.TemporaryDirectory() as d:
        stage, live = Path(d) / 'stage', Path(d) / 'live'
        now = [0.0]
        t = b.Trickle(stage, live, interval=5, clock=lambda: now[0])
        t()                                         # stage not created yet: nothing, no error
        (stage / 'warmup-v1').mkdir(parents=True)
        (live / 'warmup-v1').mkdir(parents=True)
        (stage / (key(1) + '.dxbc')).write_bytes(dxbc(1))
        (stage / (key(2) + '.dxbc')).write_bytes(dxbc(2)[:-3])          # still being written
        (stage / ('pso_' + key(1) + '.bin')).write_bytes(blob(1))
        (stage / 'warmup-v1' / ('code_' + key(1) + '.dxbc')).write_bytes(dxbc(5))
        (stage / 'warmup-v1' / ('pso_' + key(1) + '.recipe')).write_bytes(b'recipe')
        (stage / 'warmup-v1' / 'race-v1.txt').write_text(key(1))
        (live / ('pso_' + key(1) + '.bin')).write_bytes(b'GAME')
        now[0] = 10
        t()
        assert t.counts == dict(trickled=2, trickle_passes=1), t.counts
        assert (live / (key(1) + '.dxbc')).read_bytes() == dxbc(1)
        assert (live / 'warmup-v1' / ('code_' + key(1) + '.dxbc')).exists()
        assert (live / ('pso_' + key(1) + '.bin')).read_bytes() == b'GAME'
        assert not (live / (key(2) + '.dxbc')).exists()
        assert not (live / 'warmup-v1' / ('pso_' + key(1) + '.recipe')).exists()
        assert not (live / 'warmup-v1' / 'race-v1.txt').exists()
        (stage / (key(2) + '.dxbc')).write_bytes(dxbc(2))
        now[0] = 12
        t()                                         # inside the interval
        assert not (live / (key(2) + '.dxbc')).exists() and t.counts['trickle_passes'] == 1
        now[0] = 15
        t()
        assert (live / (key(2) + '.dxbc')).read_bytes() == dxbc(2) and t.counts == dict(trickled=3, trickle_passes=2)
        t(force=True)
        assert t.counts == dict(trickled=3, trickle_passes=3)
        assert not list(live.rglob('*.tmp'))
    print('trickle: passed')


def trickle_stage():
    """prepare_race with stand-in stages: files reach the live cache during the stage, and only at the end when off."""
    key = lambda n: f'{n:016x}'  # noqa: E731
    import preparation_template_inputs
    import train_pipeline_cache
    saved = (preparation_template_inputs.successful_inputs, train_pipeline_cache.save_report, b.write_subset,
             os.environ.get('GT5P_PREPARE_BACKGROUND_TRICKLE'))
    preparation_template_inputs.successful_inputs = lambda report: {'a': key(7), 'b': key(8)}
    train_pipeline_cache.save_report = lambda path, report: path.write_text(json.dumps(report))
    b.write_subset = lambda document, records, folder: folder
    try:
        for enabled in ('1', '0'):
            os.environ['GT5P_PREPARE_BACKGROUND_TRICKLE'] = enabled
            with tempfile.TemporaryDirectory() as d:
                live = Path(d) / 'live'
                (live / 'warmup-v1').mkdir(parents=True)
                seen = []
                def prepare_stage(template, output, resume, progress):
                    cache = output / 'shadercache'
                    (cache / 'warmup-v1').mkdir(parents=True)
                    (cache / (key(1) + '.dxbc')).write_bytes(dxbc(1))
                    progress('compiling', {})
                    seen.append((live / (key(1) + '.dxbc')).exists())
                    (cache / ('pso_' + key(7) + '.bin')).write_bytes(blob(7))
                    (cache / 'warmup-v1' / ('pso_' + key(7) + '.recipe')).write_bytes(b'recipe')
                    (cache / 'warmup-v1' / ('code_' + key(3) + '.dxbc')).write_bytes(dxbc(3))
                    return dict(counts={'prepared': 2}, records=[])
                def msaa_stage(output, report, progress):
                    progress('msaa', {})
                    return None
                document = dict(records=[dict(key='a'), dict(key='b')])
                plan = dict(phases=dict(menu=[], race=['a', 'b']))
                record = b.prepare_race(Path(d) / 'race', document, plan, 'default', live, prepare_stage, msaa_stage)
                assert seen == [enabled == '1'], (enabled, seen)
                assert record['status'] == 'merged' and record['recipes'] == 1 and record['race_appended'] == 1, record
                if enabled == '1':
                    assert record['trickled'] == 1 and record['present'] == 1 and record['placed'] == 2, record
                else:
                    assert 'trickled' not in record and record['placed'] == 3, record
                assert (live / 'warmup-v1' / 'race-v1.txt').read_text() == key(7) + '\n'
    finally:
        preparation_template_inputs.successful_inputs, train_pipeline_cache.save_report, b.write_subset, old = saved
        if old is None:
            os.environ.pop('GT5P_PREPARE_BACKGROUND_TRICKLE', None)
        else:
            os.environ['GT5P_PREPARE_BACKGROUND_TRICKLE'] = old
    print('trickle during the stage: passed')


if __name__ == '__main__':
    switches()
    selection()
    merge()
    trickle_pass()
    trickle_stage()
