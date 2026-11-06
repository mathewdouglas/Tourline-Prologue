"""Phase 225 background preparation: switches, race selection and the merge into a live cache (synthetic; no game).

1. GT5P_PREPARE_BACKGROUND / GT5P_PREPARE_BACKGROUND_WORKERS parsing and the worker default.
2. race_records: the plan's race identities in template order; a plan naming records outside the template is refused.
   On the shipped starter: 2,113 records.
3. merge: shader bytes, driver blobs and code files land; files the game already has are never replaced; only the
   race keys' recipes are copied (after everything they reference); lists, packs, the lookup table and other
   names stay out; the race index gains only missing keys, after the game's own lines; a second merge places
   nothing. Merge records are per live cache.
"""
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import background_preparation as b  # noqa: E402


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
            (stage / (key(n) + '.dxbc')).write_bytes(b'DXBC' + bytes([n]))
            (stage / ('pso_' + key(n) + '.bin')).write_bytes(b'blob' + bytes([n]))
            (stage / 'warmup-v1' / ('code_' + key(n) + '.dxbc')).write_bytes(b'code')
            (stage / 'warmup-v1' / ('pso_' + key(n) + '.recipe')).write_bytes(b'recipe' + bytes([n]))
        for name in ('race-v1.txt', 'menu-v1.txt', 'fp-lookup-v2-0123.bin', 'race-shaders-v1.pack', 'notes.txt'):
            (stage / name).write_text('stage')
            (stage / 'warmup-v1' / name).write_text('stage')
        # What the game already wrote: one shader (different bytes must stay), a recipe and its own race list.
        (live / (key(1) + '.dxbc')).write_bytes(b'GAME')
        (live / 'warmup-v1' / ('pso_' + key(2) + '.recipe')).write_bytes(b'game recipe')
        (live / 'warmup-v1' / 'race-v1.txt').write_text(key(9) + '\n' + key(2) + '\n')
        counts = b.merge(stage, live, [key(1), key(2)])
        assert counts == dict(placed=8, present=1, recipes=1, race_keys=2, race_appended=1), counts
        assert (live / (key(1) + '.dxbc')).read_bytes() == b'GAME'
        assert (live / 'warmup-v1' / ('pso_' + key(2) + '.recipe')).read_bytes() == b'game recipe'
        assert (live / 'warmup-v1' / ('pso_' + key(1) + '.recipe')).read_bytes() == b'recipe\x01'
        assert not (live / 'warmup-v1' / ('pso_' + key(3) + '.recipe')).exists(), 'non-race recipe copied'
        assert (live / 'warmup-v1' / 'race-v1.txt').read_text() == key(9) + '\n' + key(2) + '\n' + key(1) + '\n'
        for name in ('menu-v1.txt', 'fp-lookup-v2-0123.bin', 'race-shaders-v1.pack', 'notes.txt'):
            assert not (live / name).exists() and not (live / 'warmup-v1' / name).exists(), name
        assert not list(live.rglob('*.tmp')), 'temporary files left'
        again = b.merge(stage, live, [key(1), key(2)])
        assert again == dict(placed=0, present=9, recipes=0, race_keys=2, race_appended=0), again
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


if __name__ == '__main__':
    switches()
    selection()
    merge()
