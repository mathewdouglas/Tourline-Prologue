"""Synthetic checks for the content sweep: plan parsing, press compilation, resume, attribution, saturation.

No game, no GPU and no game data: everything here is generated. Run with the repo Python:
  python scripts/test/content_sweep.py
"""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import zlib

sys.path.insert(0, str(Path(__file__).parents[1]))
import content_sweep as cs

ROOT = Path(__file__).parents[2]


def expect_error(function, *args, fragment=''):
    try:
        function(*args)
    except ValueError as exc:
        assert fragment in str(exc), (fragment, str(exc))
        return
    raise AssertionError('expected ValueError containing ' + repr(fragment))


def small_plan(**over):
    plan = dict(schema=cs.PLAN_SCHEMA, version=cs.PLAN_VERSION,
                dealer=dict(columns=16, rows=2, makers_per_chunk=2, survey_makers_per_chunk=2, max_cars=4, makers=[
                    dict(id='alpha', col=0, row=0, cars=2), dict(id='beta', col=0, row=1, cars=1),
                    dict(id='gamma', col=13, row=0, cars=3, colors=1),
                    dict(id='sa', col=1, row=0, cars=None), dict(id='sb', col=1, row=1, cars=None),
                    dict(id='sc', col=2, row=0, cars=None)]),
                courses=dict(cameras=3, list=[dict(id='ring', slot=0), dict(id='oval', slot=1)]))
    plan.update(over)
    return plan


# ---- shipped plan parses and every chunk fits PAD_HOLD ----------------------------------------
shipped = cs.load_plan(ROOT / 'config/content-sweep/gt5p-prologue.json')
chunks = cs.expand_chunks(shipped)
assert len(chunks) >= 12 and chunks[0]['kind'] == 'dealer' and chunks[-1]['kind'] == 'course'
assert sum(len(c['makers']) for c in chunks if c['kind'] == 'dealer') == 31
for chunk in chunks:
    script = cs.compile_chunk(shipped, chunk)
    assert len(script.presses) <= cs.MAX_PADHOLD_PRESSES, chunk['id']
makers = shipped['dealer']['makers']
assert len(makers) == 31 and len({(m['col'], m['row']) for m in makers}) == 31

# ---- the main-menu route is byte-for-byte the one milestone.ps1 builds ------------------------
golden = ('@TopMenuTemplate+6000-6300:CIRCLE,@TopMenuTemplate+7000-9000:RIGHT,@TopMenuTemplate+9300-9400:LEFT,'
          '@TopMenuTemplate+9650-9750:LEFT,@TopMenuTemplate+10000-10100:LEFT,@TopMenuTemplate+10350-10450:LEFT,'
          '@TopMenuTemplate+11000-11300:CROSS,@TopMenuTemplate+15000-15300!DealerSelectRoot:CIRCLE,'
          '@TopMenuTemplate+16000-18000!DealerSelectRoot:RIGHT,@TopMenuTemplate+18300-18400!DealerSelectRoot:LEFT,'
          '@TopMenuTemplate+18650-18750!DealerSelectRoot:LEFT,@TopMenuTemplate+19000-19100!DealerSelectRoot:LEFT,'
          '@TopMenuTemplate+19350-19450!DealerSelectRoot:LEFT,@TopMenuTemplate+20000-20300!DealerSelectRoot:CROSS')
assert cs.hold_string(cs.to_dealers(6000)) == golden
slot1 = cs.hold_string(cs.to_course(6000, 1))
assert slot1.endswith('@CourseSelectRoot+3000-3100:RIGHT,@CourseSelectRoot+4500-4800:CROSS'), slot1
slot0 = cs.hold_string(cs.to_course(6000, 0))
assert slot0.endswith('@TopMenuTemplate+9100-9400:CROSS,@CourseSelectRoot+4500-4800:CROSS'), slot0

# ---- plan validation ---------------------------------------------------------------------------
plan = cs.load_plan(small_plan())
assert plan['timing']['car_dwell'] == cs.DEFAULT_TIMING['car_dwell'] and plan['settings']['resolution'] == '1080p'
assert plan['dealer']['makers'][2]['colors'] == 1 and plan['dealer']['makers'][0]['colors'] == 0
bad = small_plan(); bad['dealer']['makers'][1]['col'] = 99
expect_error(cs.load_plan, bad, fragment='col')
bad = small_plan(); bad['dealer']['makers'][1]['id'] = 'alpha'
expect_error(cs.load_plan, bad, fragment='unique')
bad = small_plan(); bad['dealer']['makers'][1].update(col=0, row=0)
expect_error(cs.load_plan, bad, fragment='duplicates grid cell')
bad = small_plan(timing=dict(nonsense=1))
expect_error(cs.load_plan, bad, fragment='Unknown timing')
bad = small_plan(timing=dict(car_dwell=-5))
expect_error(cs.load_plan, bad, fragment='car_dwell')
bad = small_plan(settings=dict(resolution='4k'))
expect_error(cs.load_plan, bad, fragment='settings')
bad = small_plan(); bad['courses']['list'][1]['slot'] = 0
expect_error(cs.load_plan, bad, fragment='repeats slot')
bad = small_plan(surprise=1)
expect_error(cs.load_plan, bad, fragment='Unknown plan fields')
expect_error(cs.load_plan, dict(schema='other', version=1), fragment='Not a')
expect_error(cs.load_plan, dict(schema=cs.PLAN_SCHEMA, version=1), fragment='needs a dealer')

# ---- chunk expansion and compilation -----------------------------------------------------------
chunks = cs.expand_chunks(plan)
assert [c['id'] for c in chunks] == ['dealer-alpha+beta', 'dealer-gamma', 'dealer-sa+sb', 'dealer-sc',
                                     'course-ring', 'course-oval'], [c['id'] for c in chunks]
assert [c['id'] for c in cs.expand_chunks(plan, ['gamma'])] == ['dealer-gamma']
assert [c['id'] for c in cs.expand_chunks(plan, ['sb'])] == ['dealer-sa+sb']
assert [c['id'] for c in cs.expand_chunks(plan, ['course'])] == ['course-ring', 'course-oval']
two = cs.compile_chunk(plan, chunks[0])
kinds = [u.kind for u in two.units]
assert kinds == ['boot', 'maker-page', 'car-studio', 'car-studio', 'maker-page', 'car-studio'], kinds
text = two.hold()
assert text.startswith(golden) and text.count(':CROSS') >= 8
times = [p.start for p in two.presses if p.anchor == 'DealerSelectRoot']
assert times == sorted(times), 'dealer presses must be in time order'
# second maker (col 0, row 1) after the first (col 0, row 0): one DOWN, no horizontal move after backing out
assert [p.key for p in two.presses].count('DOWN') == 1 and [p.key for p in two.presses].count('CIRCLE') >= 4
# survey units are scans: max_cars + 1 presses and max_cars + 2 shots, all with a car-name probe
survey = cs.compile_chunk(plan, chunks[2])
assert [u.kind for u in survey.units] == ['boot', 'maker-page', 'showroom-scan', 'maker-page', 'showroom-scan']
scan = survey.units[2]
named = [s for s in scan.shots if s['name'].startswith('scan')]
assert scan.shots[0]['name'] == 'page' and 'crop' not in scan.shots[0]
assert len(named) == plan['dealer']['max_cars'] + 2 and all('name' in s['regions'] for s in named)
assert [p.key for p in survey.presses if p.anchor == 'DealerSelectRoot'].count('RIGHT') >= 2 * (plan['dealer']['max_cars'] + 1)
far = cs.compile_chunk(plan, chunks[1])           # column 13: one RIGHT tap per column, no held sweep
nav = [p for p in far.presses if p.anchor == 'DealerSelectRoot']
assert not any(p.end - p.start >= 1000 for p in nav), 'grid movement stays one tap per cell'
assert sum(1 for p in nav if p.key == 'RIGHT' and p.end - p.start == plan['timing']['tap_len']) >= 13
assert [s['name'] for s in far.units[2].shots] == ['studio', 'color1'], 'colors=1 adds one swatch step'
retries = [p for p in two.presses if p.unless == 'CarColorSelectRoot']
assert len(retries) == 1 and retries[0].key == 'CROSS' and retries[0].start > 0
course = cs.compile_chunk(plan, chunks[5])
assert [u.id for u in course.units] == ['boot', 'prepare', 'grid', 'cam0', 'cam1', 'cam2']
assert [p.key for p in course.presses].count('SELECT') == 0
# greedy grouping stops before the PAD_HOLD capacity: eight survey makers cannot share one process
wide = small_plan()
wide['dealer'].update(survey_makers_per_chunk=8, max_cars=8, makers=[
    dict(id=f's{i}', col=i, row=0, cars=None) for i in range(6)])
groups = [len(c['makers']) for c in cs.expand_chunks(cs.load_plan(wide)) if c['kind'] == 'dealer']
assert sum(groups) == 6 and max(groups) < 6 and all(cs.compile_chunk(cs.load_plan(wide), c) for c in cs.expand_chunks(cs.load_plan(wide)))
too_many = copy.deepcopy(plan)
too_many['dealer']['max_cars'] = 32
too_many['dealer']['makers'] = [dict(id='big', label='Big', col=12, row=1, cars=32, colors=3)]
expect_error(cs.compile_chunk, cs.load_plan(too_many), cs.expand_chunks(cs.load_plan(too_many))[0], fragment='capacity')
# Twelve cars in the last column fit only after the menu retry is dropped.
packed = small_plan()
packed['dealer']['max_cars'] = 12
packed['dealer']['makers'] = [dict(id='end', col=15, row=0, cars=12)]
packed['dealer']['columns'] = 16
packed_plan = cs.load_plan(packed)
packed_script = cs.compile_chunk(packed_plan, cs.expand_chunks(packed_plan)[0])
assert len(packed_script.presses) <= cs.MAX_PADHOLD_PRESSES
assert '!DealerSelectRoot' not in packed_script.hold()
assert sum(1 for u in packed_script.units if u.kind == 'car-studio') == 12
expect_error(cs.hold_string, [cs.Press('A', 0, 10, 'CROSS')] * 65, fragment='capacity')
expect_error(cs.Press, 'A', 10, 5, 'CROSS', fragment='ordered')
expect_error(cs.Press, 'A', 0, 5, 'L1', fragment='Unknown pad key')
expect_error(cs.Press, 'A b', 0, 5, 'CROSS', fragment='milestone')

# ---- resume ----------------------------------------------------------------------------------------
state = dict(schema=cs.STATE_SCHEMA, version=1, chunks={
    'dealer-alpha+beta': dict(status='done', attempts=1),
    'dealer-gamma': dict(status='failed', attempts=1),
    'dealer-sa+sb': dict(status='done', attempts=1),
    'course-ring': dict(status='failed', attempts=2),
    'course-oval': dict(status='running', attempts=1)})
todo = [c['id'] for c in cs.pending_chunks(chunks, state, attempts=2)]
assert todo == ['dealer-gamma', 'dealer-sc', 'course-oval'], todo   # done skipped, exhausted failure skipped, interrupted retried
assert [c['id'] for c in cs.pending_chunks(chunks, state, attempts=3)] == ['dealer-gamma', 'dealer-sc', 'course-ring', 'course-oval']
assert len(cs.pending_chunks(chunks, state, attempts=2, force=True)) == 6
assert [c['id'] for c in cs.pending_chunks(chunks, dict(chunks={}))] == [c['id'] for c in chunks]
with tempfile.TemporaryDirectory() as tmp:
    assert cs.load_state(tmp)['chunks'] == {}
    cs.save_state(tmp, state)
    assert cs.load_state(tmp) == state and not list(Path(tmp).glob('*.tmp'))
    (Path(tmp) / 'state.json').write_text('{"schema": "x"}')
    expect_error(cs.load_state, tmp, fragment='Unrecognised')

# ---- link attribution and saturation -----------------------------------------------------------------
links = [(0.5, 'k0'), (1.0, 'k1'), (3.2, 'k2'), (3.3, 'k0'), (7.0, 'k3'), (9.9, 'k4')]
owned = cs.attribute_links(links, [('boot', 0.9), ('a', 3.0), ('b', None), ('c', 7.0)])
assert owned == {'boot': ['k1'], 'a': ['k2', 'k0'], 'b': [], 'c': ['k3', 'k4'], None: ['k0']}, owned
rows = cs.saturation([('boot', ['k1', 'k5']), ('a', ['k2', 'k1', 'k2']), ('b', []), ('c', ['k3', 'k5'])],
                     starter={'k1', 'k2'}, exportable={'k1', 'k2', 'k3'})
assert [(r['unit'], r['new_in_sweep'], r['exportable'], r['new_vs_starter'], r['cumulative_distinct']) for r in rows] == [
    ('boot', 2, 1, 0, 2), ('a', 1, 1, 0, 3), ('b', 0, 0, 0, 3), ('c', 1, 1, 1, 4)], rows
assert rows[-1]['cumulative_new_vs_starter'] == 1

# ---- carousel end detection -------------------------------------------------------------------------------
def shot(count, cx=500.0, cy=675.0):
    return dict(count=count, cx=cx, cy=cy)
# three cars (shots 0..2 differ), then RIGHT does nothing: the name is unchanged from shot 2 on
assert cs.detect_car_count([shot(300), shot(420, 520), shot(260, 480), shot(260, 480), shot(262, 481), shot(260, 480)])[0] == 3
assert cs.detect_car_count([shot(300), shot(300), shot(300), shot(300)])[0] == 1          # a single car
assert cs.detect_car_count([None, shot(5)])[0] is None                                      # text never found
assert cs.detect_car_count([shot(300), shot(310, 520), shot(330, 480), shot(350, 540)])[0] is None   # never settles

# ---- PNG encoder and fingerprints --------------------------------------------------------------------------
width, height = 6, 4
rgb = bytes(range(width * height * 3))
png = cs.png_bytes(width, height, rgb)
assert png[:8] == b'\x89PNG\r\n\x1a\n'
pos, parts = 8, {}
while pos < len(png):
    length, tag = struct.unpack('>I4s', png[pos:pos + 8])
    body = png[pos + 8:pos + 8 + length]
    assert zlib.crc32(tag + body) & 0xffffffff == struct.unpack('>I', png[pos + 8 + length:pos + 12 + length])[0]
    parts[tag] = body
    pos += 12 + length
assert struct.unpack('>IIBBBBB', parts[b'IHDR']) == (width, height, 8, 2, 0, 0, 0)
raw = zlib.decompress(parts[b'IDAT'])
assert raw == b''.join(b'\x00' + rgb[y * 18:(y + 1) * 18] for y in range(height))
white = bytearray(1920 * 1080 * 3)
for y in range(660, 680):
    for x in range(300, 340):
        o = (y * 1920 + x) * 3
        white[o:o + 3] = b'\xff\xff\xff'
stats = cs.region_text_stats(1920, 1080, white, cs.CAR_NAME_BOX)
assert stats['count'] == 800 and abs(stats['cx'] - 319.5) < 0.01 and abs(stats['cy'] - 669.5) < 0.01
half = cs.region_text_stats(960, 540, bytearray(960 * 540 * 3), cs.CAR_NAME_BOX)      # reference-resolution scaling
assert half['count'] == 0
sig = cs.signature(1920, 1080, white)
assert len(sig) == cs.GRID_W * cs.GRID_H and cs.signature_stats(sig)['dark_fraction'] > 0.9

# ---- the child environment never inherits tuning switches --------------------------------------------------------
import os
os.environ['RSX_ANISO'] = '2'
os.environ['PAD_HOLD'] = 'bogus'
env = cs.game_environment(Path('G'), Path('C'), '@A+0-5:CROSS', Path('P'))
assert 'RSX_ANISO' not in env and env['PAD_HOLD'] == '@A+0-5:CROSS' and env['RSX_SHADER_CACHE'] == 'C'
assert env['RSX_PSO_PROVENANCE'] == 'P' and env['RSX_PSO_PROVENANCE_LIMIT'] == '16384' and env['PS3_VERBOSE'] == '0'
assert env['FS_HIDE'] == 'grim/file/contents' and env['GT5P_NO_SETTINGS'] == '1' and env['RSX_SHADER_WARMUP'] == '0'

print('Plan parsing, chunk compilation, PAD_HOLD capacity, resume, attribution, saturation and detection passed')
