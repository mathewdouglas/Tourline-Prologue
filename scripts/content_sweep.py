"""Maintainer-run, unattended content sweep that observes pipelines per car/track.

Developer tool, default-off, never part of the player package. It drives a
private copy of the game with scripted pad presses (PAD_HOLD), records which
pipelines each sweep unit (a dealership manufacturer page, one car's studio
page, one Arcade camera view...) draws for the first time in that process, and
exports metadata-only templates for comparison with the shipped starter. Shader
bytes, programs and caches stay in an ignored private output; only identifiers
and numeric state reach a template, and nothing here edits assets/.

  python scripts/content_sweep.py setup   --root scratch/content-sweep
  python scripts/content_sweep.py check   --plan config/content-sweep/gt5p-prologue.json
  python scripts/content_sweep.py run     --root R --out O --plan P [--only id,id] [--attempts 2]
  python scripts/content_sweep.py plan-update --out O --plan P --output P2     (fold survey results into the plan)
  python scripts/content_sweep.py report  --out O --baseline assets/pipeline-templates/gt5p-disc-v2 --engine E --decoder D
  python scripts/content_sweep.py probe   --root R --out O --hold "<PAD_HOLD>"   (ad-hoc menu-flow discovery)
  python scripts/content_sweep.py contact --output O/sheet.png --columns 4 "O/chunks/*/attempt-1/*.studio.png"

Every external effect is bounded: one game at a time, a private RSX_SHADER_CACHE,
a private copy of gamedata, per-chunk timeouts and a kill in a finally block.
Run it only through the machine-wide test lock when other agents share the machine.
Sweeps are open loop: PAD_HOLD holds at most 64 presses and cannot see the screen,
so each chunk is verified afterwards from milestones and window shots, failures
are recorded (never silently accepted) and only verified chunks count as done.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time
import zlib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ENGINE = Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\build\gt5p.exe')
DEFAULT_DECODER = Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare\decoder.dll')
DEFAULT_FIXTURE = Path(r'C:\Users\GGPC\Dev\Recomps\GT5P')

# Environment prefixes a child game must not inherit from the caller's shell.
SCRUB_PREFIXES = ('GT5P_', 'RSX_', 'PS3_', 'PAD_', 'FP_', 'VP_', 'SPU_', 'PPU_', 'D3D12_', 'CULL_', 'FS_')
PLAN_SCHEMA = 'gt5p-content-sweep-plan'
PLAN_VERSION = 1
STATE_SCHEMA = 'gt5p-content-sweep-state'
MAX_PADHOLD_PRESSES = 64        # cellPad.c: static ev[64]
PROVENANCE_LIMIT = 16384        # rsx_pso_provenance.h clamp
KEYS = ('UP', 'DOWN', 'LEFT', 'RIGHT', 'CROSS', 'CIRCLE', 'SQUARE', 'TRIANGLE', 'START', 'SELECT')
ID_RE = re.compile(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,47}')
MILESTONE_RE = re.compile(r'\[milestone\] (\w+) at (\d+) ms \(pad clock (-?\d+) ms\)')

# Millisecond timing. Every value is a plan field (plan["timing"]) and was calibrated on a warm
# private shader cache at 1080p; a cold cache slows frames to ~10 FPS and misfires held presses.
DEFAULT_TIMING = dict(
    boot_at=6000,          # first main-menu press, after TopMenuTemplate
    nav_start=3000,        # grid navigation start, after DealerSelectRoot
    nav_tap_gap=450, tap_len=120, nav_settle=1200,
    press_len=400,         # Cross/Circle length
    maker_load=1000,       # Cross -> maker page ready
    maker_dwell=8000,      # Cross while the Showroom button is still up; a later Cross hits the cinematic
    showroom_open=3000,    # Cross on the Showroom button -> carousel cursor on the car
    scan_gap=2800,         # survey: RIGHT -> next settled name shot
    car_step_gap=2200,     # RIGHT -> Cross
    car_dwell=12000,       # studio dwell; the camera orbits on its own (no extra button)
    car_back=8000,         # Circle -> carousel ready
    enter_retry=4000,      # second Cross, skipped once CarColorSelectRoot has been seen
    color_gap=2500,        # per extra colour swatch (off unless the plan sets colors)
    back_circle1=5000, back_circle2=7000,   # carousel -> showcase -> grid
    pit_press=(10000, 25000, 40000),        # PitSceneRoot retries
    driving_press=(4000, 14000, 24000),     # DrivingOptionRoot retries
    grid_start=5000,       # QuickArcadeRoot -> Start
    race_lead=50000,       # start -> first race shot (loading, rolling start, intro camera)
    cam_dwell=20000,       # later race shot; the title changes camera across the start itself
    drain_quiet=4.0, drain_max=90.0,        # seconds: pending recipes / link quiet before stopping
)
TIMING_LIMITS = (0, 600000)

# Reference-resolution (1920x1080) regions for carousel text/arrow probes.
CAROUSEL_CROP = (100, 280, 900, 760)
CAR_NAME_BOX = (200, 640, 800, 710)
# The "Enter" label of the top-right button prompt is on every dealership page (manufacturer page, carousel,
# studio) whether the glyph is a keyboard key or a gamepad button. Dark paint on a dark studio makes
# luminance an unreliable "page reached" test; a black splash or movie has no such label (0 px).
ENTER_LABEL_BOX = (1700, 40, 1830, 95)
ENTER_TEXT_MIN = 60


# --------------------------------------------------------------------------
# PAD_HOLD script building (pure logic; mirrors scripts/test/milestone.ps1)
# --------------------------------------------------------------------------
class Press:
    """One scripted press: held from `start` to `end` ms after `anchor` (or after the first poll)."""
    __slots__ = ('anchor', 'start', 'end', 'key', 'unless')

    def __init__(self, anchor, start, end, key, unless=''):
        if key not in KEYS:
            raise ValueError(f'Unknown pad key {key!r}')
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= 3_600_000:
            raise ValueError(f'Press window {start}-{end} ms is outside 0..3,600,000 ms and ordered')
        for name in (anchor, unless):
            if name and not re.fullmatch(r'[A-Za-z0-9_]{1,47}', name):
                raise ValueError(f'Invalid milestone name {name!r}')
        self.anchor, self.start, self.end, self.key, self.unless = anchor, start, end, key, unless

    def text(self):
        head = f'@{self.anchor}+' if self.anchor else ''
        tail = f'!{self.unless}' if self.unless else ''
        return f'{head}{self.start}-{self.end}{tail}:{self.key}'

    def __repr__(self):
        return self.text()


def hold_string(presses):
    items = list(presses)
    if len(items) > MAX_PADHOLD_PRESSES:
        raise ValueError(f'{len(items)} presses exceed the runtime PAD_HOLD capacity of {MAX_PADHOLD_PRESSES}')
    return ','.join(p.text() for p in items)


def to_dealers(at=6000, retry=True):
    """Main menu -> manufacturer list. Attempt 0 closes the News popup, parks on Save and walks Left four times
    to Dealerships; attempt 1 (9 s later) is skipped once DealerSelectRoot has loaded."""
    presses = []
    for attempt in ((0, 1) if retry else (0,)):
        t = at + 9000 * attempt
        u = 'DealerSelectRoot' if attempt else ''
        presses.append(Press('TopMenuTemplate', t, t + 300, 'CIRCLE', u))
        presses.append(Press('TopMenuTemplate', t + 1000, t + 3000, 'RIGHT', u))
        for k in range(4):
            lo = t + 3300 + 350 * k
            presses.append(Press('TopMenuTemplate', lo, lo + 100, 'LEFT', u))
        presses.append(Press('TopMenuTemplate', t + 5000, t + 5300, 'CROSS', u))
    return presses


def to_course(at=6000, slot=1):
    """Main menu -> Arcade Course Select -> `slot` RIGHT taps -> Cross. Mirrors Get-ToCourse."""
    presses = [Press('TopMenuTemplate', at, at + 300, 'CIRCLE')]
    for k in range(4):
        t = at + 1000 + 350 * k
        presses.append(Press('TopMenuTemplate', t, t + 100, 'RIGHT'))
    presses.append(Press('TopMenuTemplate', at + 3100, at + 3400, 'CROSS'))
    for k in range(slot):
        t = 3000 + 400 * k
        presses.append(Press('CourseSelectRoot', t, t + 100, 'RIGHT'))
    cross = 4500
    if slot >= 1:
        last_end = 3100 + 400 * (slot - 1)
        if last_end + 1000 > 4500:
            cross = last_end + 1400
    presses.append(Press('CourseSelectRoot', cross, cross + 300, 'CROSS'))
    return presses


# --------------------------------------------------------------------------
# Sweep plan (data only, no game data) and chunk compilation (pure logic)
# --------------------------------------------------------------------------
def _int(value, name, low, high):
    if type(value) is not int or isinstance(value, bool) or not low <= value <= high:
        raise ValueError(f'{name} must be an integer in {low}..{high}, not {value!r}')
    return value


def load_plan(path_or_document):
    """Validate and normalise a plan. Raises ValueError with the offending field."""
    doc = path_or_document
    if isinstance(doc, (str, Path)):
        doc = json.loads(Path(doc).read_text(encoding='utf-8'))
    if not isinstance(doc, dict) or doc.get('schema') != PLAN_SCHEMA or doc.get('version') != PLAN_VERSION:
        raise ValueError(f'Not a {PLAN_SCHEMA} version {PLAN_VERSION} document')
    unknown = set(doc) - {'schema', 'version', 'title', 'settings', 'timing', 'dealer', 'courses'}
    if unknown:
        raise ValueError('Unknown plan fields: ' + ', '.join(sorted(unknown)))
    plan = copy.deepcopy(doc)
    settings = dict(resolution='1080p', msaa='2')
    settings.update(plan.get('settings') or {})
    if settings['resolution'] not in ('720p', '1080p') or settings['msaa'] not in ('1', '2'):
        raise ValueError('settings.resolution must be 720p/1080p and settings.msaa 1/2 (collection contexts)')
    plan['settings'] = settings
    timing = dict(DEFAULT_TIMING)
    for key, value in (plan.get('timing') or {}).items():
        if key not in DEFAULT_TIMING:
            raise ValueError(f'Unknown timing field {key!r}')
        default = DEFAULT_TIMING[key]
        if isinstance(default, tuple):
            if not isinstance(value, (list, tuple)) or not value or any(type(v) is not int for v in value):
                raise ValueError(f'timing.{key} must be a non-empty list of integers')
            value = tuple(_int(v, f'timing.{key}', *TIMING_LIMITS) for v in value)
        elif isinstance(default, float):
            if not isinstance(value, (int, float)) or isinstance(value, bool) or not 0 <= value <= 600:
                raise ValueError(f'timing.{key} must be seconds in 0..600')
        else:
            _int(value, f'timing.{key}', *TIMING_LIMITS)
        timing[key] = value
    plan['timing'] = timing
    dealer = plan.get('dealer')
    if dealer is not None:
        d = dict(columns=16, rows=2, makers_per_chunk=1, survey_makers_per_chunk=3, max_cars=8, colors_per_car=0)
        d.update({k: v for k, v in dealer.items() if k != 'makers'})
        _int(d['columns'], 'dealer.columns', 1, 64)
        _int(d['rows'], 'dealer.rows', 1, 8)
        _int(d['makers_per_chunk'], 'dealer.makers_per_chunk', 1, 8)
        _int(d['survey_makers_per_chunk'], 'dealer.survey_makers_per_chunk', 1, 8)
        _int(d['max_cars'], 'dealer.max_cars', 1, 32)
        _int(d['colors_per_car'], 'dealer.colors_per_car', 0, 12)
        makers, seen, cells = [], set(), set()
        for m in dealer.get('makers') or []:
            if not isinstance(m, dict) or set(m) - {'id', 'label', 'col', 'row', 'cars', 'colors'}:
                raise ValueError(f'Invalid maker entry {m!r}')
            if not isinstance(m.get('id'), str) or not ID_RE.fullmatch(m['id']) or m['id'] in seen:
                raise ValueError(f'Maker ids must be unique identifiers: {m.get("id")!r}')
            seen.add(m['id'])
            col = _int(m.get('col'), f"maker {m['id']} col", 0, d['columns'] - 1)
            row = _int(m.get('row'), f"maker {m['id']} row", 0, d['rows'] - 1)
            if (col, row) in cells:
                raise ValueError(f"maker {m['id']} duplicates grid cell {(col, row)}")
            cells.add((col, row))
            cars = m.get('cars')
            if cars is not None:
                _int(cars, f"maker {m['id']} cars", 1, d['max_cars'])
            colors = m.get('colors', d['colors_per_car'])
            _int(colors, f"maker {m['id']} colors", 0, 12)
            makers.append(dict(id=m['id'], label=str(m.get('label', m['id']))[:64], col=col, row=row, cars=cars, colors=colors))
        d['makers'] = makers
        plan['dealer'] = d
    courses = plan.get('courses')
    if courses is not None:
        c = dict(cameras=4)
        c.update({k: v for k, v in courses.items() if k != 'list'})
        _int(c['cameras'], 'courses.cameras', 1, 8)
        items, seen, slots = [], set(), set()
        for item in courses.get('list') or []:
            if not isinstance(item, dict) or set(item) - {'id', 'label', 'slot', 'identity'}:
                raise ValueError(f'Invalid course entry {item!r}')
            if not isinstance(item.get('id'), str) or not ID_RE.fullmatch(item['id']) or item['id'] in seen:
                raise ValueError(f'Course ids must be unique identifiers: {item.get("id")!r}')
            seen.add(item['id'])
            slot = _int(item.get('slot'), f"course {item['id']} slot", 0, 9)
            if slot in slots:
                raise ValueError(f"course {item['id']} repeats slot {slot}")
            slots.add(slot)
            items.append(dict(id=item['id'], label=str(item.get('label', item['id']))[:64], slot=slot,
                              identity=str(item.get('identity', 'measured'))[:32]))
        c['list'] = items
        plan['courses'] = c
    if not plan.get('dealer') and not plan.get('courses'):
        raise ValueError('A plan needs a dealer and/or courses section')
    return plan


class Unit:
    """A sweep unit: where it starts (for attribution), when to take its shots and what must hold."""

    def __init__(self, uid, kind, label, start, shots, expect=None, meta=None):
        self.id, self.kind, self.label = uid, kind, label
        self.start = start                        # (anchor, ms): first press of the unit's navigation
        self.shots = shots                        # list of dict(name, anchor, ms, crop=None, regions=None, scale=2)
        self.expect = expect or {}                # milestone=, mean=(lo, hi) on the last shot
        self.meta = meta or {}

    def to_json(self):
        return dict(id=self.id, kind=self.kind, label=self.label, start=list(self.start), shots=self.shots,
                    expect=self.expect, meta=self.meta)


class Script:
    def __init__(self, chunk_id, presses, units, seconds):
        self.chunk_id, self.presses, self.units, self.seconds = chunk_id, presses, units, seconds

    def hold(self):
        return hold_string(self.presses)


def expand_chunks(plan, only=None):
    """Chunk descriptors in sweep order. Dealer makers are grouped greedily: survey makers (cars unknown) share a
    process up to survey_makers_per_chunk, sweep makers up to makers_per_chunk, and a group stops growing as soon
    as its presses would exceed the PAD_HOLD capacity. Courses follow, one process each."""
    chunks = []
    dealer = plan.get('dealer')
    if dealer:
        group = []

        def limit(maker):
            return dealer['survey_makers_per_chunk'] if maker['cars'] is None else dealer['makers_per_chunk']

        def fits(makers):
            try:
                compile_dealer_chunk(plan, dict(id='fit', kind='dealer', makers=makers)).hold()
            except ValueError:
                return False
            return True

        def flush():
            if group:
                chunks.append(dict(id='dealer-' + '+'.join(m['id'] for m in group), kind='dealer', makers=list(group)))
                group.clear()

        for maker in dealer['makers']:
            same_mode = group and (group[0]['cars'] is None) == (maker['cars'] is None)
            if group and not (same_mode and len(group) < limit(maker) and fits(group + [maker])):
                flush()
            group.append(maker)
        flush()
    courses = plan.get('courses')
    if courses:
        for item in sorted(courses['list'], key=lambda x: x['slot']):
            chunks.append(dict(id='course-' + item['id'], kind='course', course=item))
    if only:
        wanted = set(only)
        chunks = [c for c in chunks if c['id'] in wanted or c['kind'] in wanted or
                  any(m['id'] in wanted for m in c.get('makers', []))]
    return chunks


def compile_dealer_chunk(plan, chunk, retry=True):
    tm, d = plan['timing'], plan['dealer']
    presses = to_dealers(tm['boot_at'], retry=retry)
    units = [Unit('boot', 'boot', 'boot to the main menu', ('', 0), [], dict(milestone='TopMenuTemplate'))]
    A = 'DealerSelectRoot'
    t = tm['nav_start']
    cur = (0, 0)
    makers = chunk['makers']
    for mi, m in enumerate(makers):
        dc, dr = m['col'] - cur[0], m['row'] - cur[1]
        step = 0
        # One tap per cell. The grid clamps at the last column (Concept by GT);
        # a held Right repeats too fast to land on a chosen cell.
        for _ in range(abs(dr)):
            presses.append(Press(A, t + step, t + step + tm['tap_len'], 'DOWN' if dr > 0 else 'UP'))
            step += tm['nav_tap_gap']
        for _ in range(abs(dc)):
            presses.append(Press(A, t + step, t + step + tm['tap_len'], 'RIGHT' if dc > 0 else 'LEFT'))
            step += tm['nav_tap_gap']
        t += step + tm['nav_settle']
        enter = t
        presses.append(Press(A, t, t + tm['press_len'], 'CROSS'))
        t += tm['maker_load'] + tm['maker_dwell']
        shots = [dict(name='maker', anchor=A, ms=t - 400, scale=2, regions=dict(enter=list(ENTER_LABEL_BOX)))]
        units.append(Unit(f"{m['id']}/maker", 'maker-page', f"{m['label']}: manufacturer page", (A, enter), shots,
                          dict(milestone='DealerTopRoot' if mi == 0 else None, mean=(5, 90),
                               text=['enter', ENTER_TEXT_MIN]), dict(maker=m['id'])))
        presses.append(Press(A, t, t + tm['press_len'], 'CROSS'))          # Showroom
        t += tm['showroom_open']
        if m['cars'] is None:                                              # survey: scan the carousel
            start = t
            shots = [dict(name='page', anchor=A, ms=t - 200, scale=2),
                     dict(name='scan00', anchor=A, ms=t - 200, crop=list(CAROUSEL_CROP), regions=dict(name=list(CAR_NAME_BOX)), scale=1)]
            for j in range(1, d['max_cars'] + 2):
                presses.append(Press(A, t, t + tm['tap_len'], 'RIGHT'))
                t += tm['scan_gap']
                shots.append(dict(name=f'scan{j:02d}', anchor=A, ms=t - 200, crop=list(CAROUSEL_CROP), regions=dict(name=list(CAR_NAME_BOX)), scale=1))
            units.append(Unit(f"{m['id']}/scan", 'showroom-scan', f"{m['label']}: showroom scan", (A, start), shots,
                              dict(), dict(maker=m['id'], max_cars=d['max_cars'])))
        else:
            for i in range(m['cars']):
                start = t
                if i:
                    presses.append(Press(A, t, t + tm['tap_len'], 'RIGHT'))
                    t += tm['car_step_gap']
                presses.append(Press(A, t, t + tm['press_len'], 'CROSS'))
                # The first Cross on a cold studio can land while the carousel is still
                # settling. A second one is skipped once that screen has been read.
                # Later cars cannot use the same skip: the milestone fires only once.
                if mi == 0 and i == 0:
                    presses.append(Press(A, t + tm['enter_retry'], t + tm['enter_retry'] + tm['press_len'],
                                         'CROSS', 'CarColorSelectRoot'))
                t += tm['car_dwell']
                shots = [dict(name='studio', anchor=A, ms=t - 500, scale=2, regions=dict(enter=list(ENTER_LABEL_BOX)))]
                for c in range(m['colors']):             # RIGHT on the studio page steps the paint swatch
                    presses.append(Press(A, t, t + tm['tap_len'], 'RIGHT'))
                    t += tm['color_gap']
                    shots.append(dict(name=f'color{c + 1}', anchor=A, ms=t - 300, scale=2))
                presses.append(Press(A, t, t + tm['press_len'], 'CIRCLE'))
                units.append(Unit(f"{m['id']}/car{i}", 'car-studio', f"{m['label']}: car {i + 1} studio page", (A, start), shots,
                                  dict(milestone='CarColorSelectRoot' if (mi == 0 and i == 0) else None, mean=(3, 255),
                                       text=['enter', ENTER_TEXT_MIN]),
                                  dict(maker=m['id'], car=i)))
                t += tm['car_back']
        if mi + 1 < len(makers):                                           # back to the manufacturer grid
            presses.append(Press(A, t, t + tm['press_len'], 'CIRCLE'))
            t += tm['back_circle1']
            presses.append(Press(A, t, t + tm['press_len'], 'CIRCLE'))
            t += tm['back_circle2']
            cur = (m['col'], m['row'])
    seconds = (tm['boot_at'] + 21000) / 1000.0 + t / 1000.0 + 20.0
    return Script(chunk['id'], presses, units, seconds)


def compile_course_chunk(plan, chunk):
    tm, c = plan['timing'], plan['courses']
    slot = chunk['course']['slot']
    presses = to_course(tm['boot_at'], slot)
    for at in tm['pit_press']:
        presses.append(Press('PitSceneRoot', at, at + 300, 'CROSS', 'DrivingOptionRoot'))
    for at in tm['driving_press']:
        presses.append(Press('DrivingOptionRoot', at, at + 300, 'CROSS', 'LoadingRoot'))
    G = 'QuickArcadeRoot'
    presses.append(Press(G, tm['grid_start'], tm['grid_start'] + 300, 'CROSS'))
    units = [Unit('boot', 'boot', 'boot to the main menu', ('', 0), [], dict(milestone='TopMenuTemplate')),
             Unit('prepare', 'course-prepare', f"{chunk['course']['label']}: Race Mode page and loading",
                  ('CourseSelectRoot', 4500), [], dict(milestone='LoadingRoot')),
             Unit('grid', 'course-grid', f"{chunk['course']['label']}: starting grid", (G, 0),
                  [dict(name='grid', anchor=G, ms=tm['grid_start'] - 500, scale=2)], dict(milestone=G))]
    t = tm['grid_start']
    for k in range(c['cameras']):
        start = t
        t += tm['race_lead'] if k == 0 else tm['cam_dwell']
        shots = [dict(name=f'cam{k}', anchor=G, ms=t - 600, scale=2)]
        meta = dict(camera=k)
        units.append(Unit(f'cam{k}', 'course-race', f"{chunk['course']['label']}: race view {k + 1}", (G, start), shots,
                          dict(milestone='RaceRoot' if k == 0 else None, mean=(30, 255)), meta))
        # No SELECT. Existing race scripts never bind a camera button, and a
        # High Speed Ring run changes camera on its own from the rolling-start
        # view to the chase view. A guessed button could open the pause menu.
    seconds = 60.0 + t / 1000.0 + 30.0
    return Script(chunk['id'], presses, units, seconds)


def compile_chunk(plan, chunk):
    if chunk['kind'] != 'dealer':
        script = compile_course_chunk(plan, chunk)
        script.hold()
        return script
    # The menu route retries once. A full showroom that would not fit keeps the
    # first attempt, which already closes the Confirmation popup.
    try:
        script = compile_dealer_chunk(plan, chunk, retry=True)
        script.hold()
        return script
    except ValueError:
        script = compile_dealer_chunk(plan, chunk, retry=False)
        script.hold()
        return script


# --------------------------------------------------------------------------
# State (resume)
# --------------------------------------------------------------------------
def load_state(out):
    path = Path(out) / 'state.json'
    if not path.exists():
        return dict(schema=STATE_SCHEMA, version=1, chunks={})
    state = json.loads(path.read_text())
    if state.get('schema') != STATE_SCHEMA:
        raise ValueError('Unrecognised sweep state; nothing was changed')
    return state


def save_state(out, state):
    path = Path(out) / 'state.json'
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(state, indent=1) + '\n')
    temporary.replace(path)


def pending_chunks(chunks, state, attempts=2, force=False):
    """Chunks still to run: never started, or failed with attempts left. Done chunks are skipped."""
    todo = []
    for chunk in chunks:
        entry = state['chunks'].get(chunk['id'])
        if force or entry is None:
            todo.append(chunk)
        elif entry['status'] != 'done' and entry.get('attempts', 0) < attempts:
            todo.append(chunk)
    return todo


# --------------------------------------------------------------------------
# Attribution and saturation (pure logic)
# --------------------------------------------------------------------------
def attribute_links(links, unit_starts):
    """links: [(t, key)], unit_starts: [(unit_id, start_t)] in order. A link belongs to the last unit started
    before it (links before the first start belong to None). Returns {unit_id: [keys in arrival order]}."""
    out = {uid: [] for uid, _ in unit_starts}
    out[None] = []
    for t, key in sorted(links, key=lambda x: x[0]):
        owner = None
        for uid, start in unit_starts:
            if start is not None and start <= t:
                owner = uid
            elif start is not None and start > t:
                break
        out[owner].append(key)
    return out


def saturation(sequence, starter=frozenset(), exportable=None):
    """sequence: ordered [(unit_label, [keys])] across the whole sweep. Returns rows with the number of pipeline
    keys first seen in this unit (new_in_sweep), how many of those are absent from the starter, and the running
    totals. `exportable` limits the starter comparison to keys that exported to a template record."""
    seen, rows = set(), []
    novel_total = 0
    for label, keys in sequence:
        fresh = [k for k in dict.fromkeys(keys) if k not in seen]
        seen.update(fresh)
        usable = [k for k in fresh if exportable is None or k in exportable]
        novel = [k for k in usable if k not in starter]
        novel_total += len(novel)
        rows.append(dict(unit=label, links=len(set(keys)), new_in_sweep=len(fresh), exportable=len(usable),
                         new_vs_starter=len(novel), cumulative_distinct=len(seen), cumulative_new_vs_starter=novel_total))
    return rows


def detect_car_count(stats):
    """stats: per scan shot dict(count, cx, cy) of the bright car-name text. The carousel stops at the last car,
    so the count is the index at which the name stops changing for two consecutive RIGHT presses.
    Returns (cars or None, note)."""
    def same(a, b):
        if a is None or b is None:
            return False
        return abs(a['count'] - b['count']) <= max(8, 0.03 * max(a['count'], b['count'])) and \
            abs(a['cx'] - b['cx']) <= 3 and abs(a['cy'] - b['cy']) <= 3
    if not stats or stats[0] is None or stats[0]['count'] < 40:
        return None, 'carousel text not found on the first shot'
    for j in range(1, len(stats) - 1):
        if same(stats[j - 1], stats[j]) and same(stats[j], stats[j + 1]):
            return j, 'name unchanged for two presses after car %d' % j
    return None, 'name still changing at the end of the scan; raise dealer.max_cars'


# --------------------------------------------------------------------------
# Windows helpers (imported lazily so pure-logic tests run anywhere)
# --------------------------------------------------------------------------
_WIN = {}


def _win():
    if not _WIN:
        import ctypes
        from ctypes import wintypes
        user32 = ctypes.WinDLL('user32', use_last_error=True)
        gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)
        try:
            user32.SetProcessDPIAware()
        except OSError:
            pass
        user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetDC.argtypes = [wintypes.HWND]
        user32.GetDC.restype = wintypes.HDC
        user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
        user32.PrintWindow.argtypes = [wintypes.HWND, wintypes.HDC, wintypes.UINT]
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
        gdi32.CreateCompatibleDC.restype = wintypes.HDC
        gdi32.CreateCompatibleBitmap.argtypes = [wintypes.HDC, ctypes.c_int, ctypes.c_int]
        gdi32.CreateCompatibleBitmap.restype = wintypes.HBITMAP
        gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
        gdi32.SelectObject.restype = wintypes.HGDIOBJ
        gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
        gdi32.DeleteDC.argtypes = [wintypes.HDC]
        gdi32.GetDIBits.argtypes = [wintypes.HDC, wintypes.HBITMAP, wintypes.UINT, wintypes.UINT, ctypes.c_void_p,
                                    ctypes.c_void_p, wintypes.UINT]
        _WIN.update(ctypes=ctypes, wintypes=wintypes, user32=user32, gdi32=gdi32)
    return _WIN


def find_window(pid):
    """The game's own top-level window (title contains the game name), or 0."""
    w = _win()
    ctypes, wintypes, user32 = w['ctypes'], w['wintypes'], w['user32']
    found = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def visit(hwnd, _):
        owner = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid:
            text = ctypes.create_unicode_buffer(512)
            user32.GetWindowTextW(hwnd, text, 512)
            if 'Gran Turismo' in text.value or 'Project Tourline Prologue' in text.value:
                found.append(hwnd)
                return False
        return True
    user32.EnumWindows(visit, 0)
    return found[0] if found else 0


def window_title(hwnd):
    w = _win()
    text = w['ctypes'].create_unicode_buffer(512)
    w['user32'].GetWindowTextW(hwnd, text, 512)
    return text.value


def png_bytes(width, height, rgb):
    """Minimal PNG encoder (8-bit RGB). `rgb` is width*height*3 bytes, top-down."""
    stride = width * 3
    raw = b''.join(b'\x00' + bytes(rgb[y * stride:(y + 1) * stride]) for y in range(height))

    def chunk(tag, data):
        body = tag + data
        return struct.pack('>I', len(data)) + body + struct.pack('>I', zlib.crc32(body) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) +
            chunk(b'IDAT', zlib.compress(raw, 3)) + chunk(b'IEND', b''))


GRID_W, GRID_H = 32, 18


def signature(width, height, rgb):
    """Coarse 32x18 luminance grid (0..255) used only for cheap change/blank checks."""
    cells = []
    for gy in range(GRID_H):
        y = min(height - 1, (2 * gy + 1) * height // (2 * GRID_H))
        base = y * width * 3
        for gx in range(GRID_W):
            x = min(width - 1, (2 * gx + 1) * width // (2 * GRID_W))
            o = base + x * 3
            cells.append((rgb[o] * 299 + rgb[o + 1] * 587 + rgb[o + 2] * 114) // 1000)
    return cells


def signature_stats(sig, other=None):
    out = dict(mean=sum(sig) / len(sig), dark_fraction=sum(1 for v in sig if v < 12) / len(sig))
    if other is not None and len(other) == len(sig):
        out['change'] = sum(abs(a - b) for a, b in zip(sig, other)) / len(sig)
    return out


def region_text_stats(width, height, rgb, box, threshold=160):
    """Count of near-white pixels in a 1920x1080-reference box, with their centroid (text fingerprint)."""
    x0, y0, x1, y1 = (int(box[0] * width / 1920), int(box[1] * height / 1080),
                      int(box[2] * width / 1920), int(box[3] * height / 1080))
    count = sx = sy = 0
    for y in range(max(0, y0), min(height, y1)):
        row = y * width * 3
        for x in range(max(0, x0), min(width, x1)):
            o = row + x * 3
            if rgb[o] > threshold and rgb[o + 1] > threshold and rgb[o + 2] > threshold:
                count += 1
                sx += x
                sy += y
    return dict(count=count, cx=round(sx / count, 1) if count else 0.0, cy=round(sy / count, 1) if count else 0.0)


def capture(hwnd, path, crop=None, regions=None, scale=2):
    """PrintWindow the client area to a PNG (optionally cropped, 1/scale nearest-neighbour). Returns metadata."""
    w = _win()
    ctypes, wintypes, user32, gdi32 = w['ctypes'], w['wintypes'], w['user32'], w['gdi32']
    rect = wintypes.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rect))
    width, height = max(16, rect.right), max(16, rect.bottom)
    screen = user32.GetDC(None)
    memdc = gdi32.CreateCompatibleDC(screen)
    bitmap = gdi32.CreateCompatibleBitmap(screen, width, height)
    old = gdi32.SelectObject(memdc, bitmap)
    try:
        user32.PrintWindow(hwnd, memdc, 3)

        class BitmapInfoHeader(ctypes.Structure):
            _fields_ = [('biSize', wintypes.DWORD), ('biWidth', wintypes.LONG), ('biHeight', wintypes.LONG),
                        ('biPlanes', wintypes.WORD), ('biBitCount', wintypes.WORD), ('biCompression', wintypes.DWORD),
                        ('biSizeImage', wintypes.DWORD), ('biXPelsPerMeter', wintypes.LONG),
                        ('biYPelsPerMeter', wintypes.LONG), ('biClrUsed', wintypes.DWORD),
                        ('biClrImportant', wintypes.DWORD)]
        header = BitmapInfoHeader(ctypes.sizeof(BitmapInfoHeader), width, -height, 1, 32, 0, 0, 0, 0, 0, 0)
        buffer = (ctypes.c_ubyte * (width * height * 4))()
        gdi32.GetDIBits(memdc, bitmap, 0, height, buffer, ctypes.byref(header), 0)
    finally:
        gdi32.SelectObject(memdc, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memdc)
        user32.ReleaseDC(None, screen)
    data = bytes(buffer)
    rgb = bytearray(width * height * 3)
    rgb[0::3], rgb[1::3], rgb[2::3] = data[2::4], data[1::4], data[0::4]
    info = dict(width=width, height=height, signature=signature(width, height, rgb))
    if regions:
        info['regions'] = {name: region_text_stats(width, height, rgb, box) for name, box in regions.items()}
    out_w, out_h, out = width, height, rgb
    if crop:
        x0, y0, x1, y1 = (int(crop[0] * width / 1920), int(crop[1] * height / 1080),
                          int(crop[2] * width / 1920), int(crop[3] * height / 1080))
        out_w, out_h = x1 - x0, y1 - y0
        out = bytearray()
        for y in range(y0, y1):
            out += rgb[(y * width + x0) * 3:(y * width + x1) * 3]
    if scale and scale > 1:
        out_w, out_h, out = downscale(out_w, out_h, out, scale)
    Path(path).write_bytes(png_bytes(out_w, out_h, out))
    return info


def downscale(width, height, rgb, factor):
    """Nearest-neighbour 1/factor reduction of a top-down RGB buffer. Returns (width, height, rgb)."""
    sw, sh = width // factor, height // factor
    scaled = bytearray()
    for y in range(sh):
        row = rgb[y * factor * width * 3:(y * factor + 1) * width * 3]
        r, g, b = row[0::3 * factor], row[1::3 * factor], row[2::3 * factor]
        line = bytearray(sw * 3)
        line[0::3], line[1::3], line[2::3] = r[:sw], g[:sw], b[:sw]
        scaled += line
    return sw, sh, scaled


PNG_SIGNATURE = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])


def read_png(path):
    """Decode a PNG written by png_bytes (8-bit RGB, filter 0). Returns (width, height, rgb)."""
    data = Path(path).read_bytes()
    if data[:8] != PNG_SIGNATURE:
        raise ValueError(f'{path} is not a PNG')
    pos, idat, header = 8, [], None
    while pos < len(data):
        length, tag = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + length]
        if tag == b'IHDR':
            header = struct.unpack('>IIBBBBB', body)
        elif tag == b'IDAT':
            idat.append(body)
        pos += 12 + length
    if header is None or header[2:] != (8, 2, 0, 0, 0):
        raise ValueError(f'{path} is not an 8-bit RGB PNG written by this tool')
    width, height = header[0], header[1]
    raw = zlib.decompress(b''.join(idat))
    stride = width * 3
    if len(raw) != height * (stride + 1) or any(raw[y * (stride + 1)] for y in range(height)):
        raise ValueError(f'{path} uses PNG filters this reader does not support')
    return width, height, bytearray(b''.join(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)] for y in range(height)))


def contact_sheet(files, columns=3, tile_width=640, gap=4):
    """Tile screenshots (reduced by an integer factor to about tile_width) for visual review.
    Returns (png bytes, [(row, column, file)]). Missing/unreadable files leave a grey tile."""
    tiles, layout = [], []
    for i, file in enumerate(files):
        try:
            width, height, rgb = read_png(file)
        except (OSError, ValueError, zlib.error):
            tiles.append(None)
        else:
            factor = max(1, round(width / tile_width))
            tiles.append(downscale(width, height, rgb, factor))
        layout.append((i // columns, i % columns, str(file)))
    sizes = [(t[0], t[1]) for t in tiles if t]
    cell_w = max([w for w, _ in sizes] or [tile_width])
    cell_h = max([h for _, h in sizes] or [tile_width * 9 // 16])
    rows = (len(files) + columns - 1) // columns
    canvas_w, canvas_h = columns * (cell_w + gap) + gap, rows * (cell_h + gap) + gap
    canvas = bytearray([0x40]) * (canvas_w * canvas_h * 3)
    for i, tile in enumerate(tiles):
        if tile is None:
            continue
        w, h, rgb = tile
        x0, y0 = gap + (i % columns) * (cell_w + gap), gap + (i // columns) * (cell_h + gap)
        for y in range(h):
            dest = ((y0 + y) * canvas_w + x0) * 3
            canvas[dest:dest + w * 3] = rgb[y * w * 3:(y + 1) * w * 3]
    return png_bytes(canvas_w, canvas_h, canvas), layout


# --------------------------------------------------------------------------
# Private run layout
# --------------------------------------------------------------------------
def isolated(path):
    """A path inside this checkout that git ignores (scratch/, out/ ...)."""
    path = Path(path).resolve()
    if ROOT not in path.parents:
        raise ValueError(f'{path} must be inside this checkout ({ROOT})')
    probe = path / 'x'
    if subprocess.run(['git', 'check-ignore', '-q', str(probe)], cwd=ROOT).returncode:
        raise ValueError(f'{path} is not git-ignored; use scratch/')
    return path


def setup_root(root, fixture):
    """Private game root: copied save data and assets, copied ELF, junction to the read-only disc files."""
    root = isolated(root)
    game = root / 'game'
    if (game / 'input/pkg').exists():
        print('game root already prepared:', game)
        return game
    fixture = Path(fixture)
    for name in ('input/EMAIN.ELF', 'input/pkg', 'gamedata', 'assets'):
        if not (fixture / name).exists():
            raise ValueError(f'Fixture is missing {name}')
    game.mkdir(parents=True, exist_ok=True)
    for name in ('gamedata', 'assets'):
        if not (game / name).exists():
            subprocess.run(['robocopy', str(fixture / name), str(game / name), '/E', '/NFL', '/NDL', '/NJH', '/NJS',
                            '/NP', '/R:1', '/W:1'], check=False)   # robocopy exit codes below 8 are success
            if not (game / name).exists():
                raise ValueError('Copy failed: ' + name)
    (game / 'input').mkdir(exist_ok=True)
    import shutil
    shutil.copy2(fixture / 'input/EMAIN.ELF', game / 'input/EMAIN.ELF')
    env = dict(os.environ, SWEEP_LINK=str(game / 'input/pkg'), SWEEP_TARGET=str(fixture / 'input/pkg'))
    subprocess.run(['powershell', '-NoProfile', '-Command',
                    'New-Item -ItemType Junction -Path $env:SWEEP_LINK -Target $env:SWEEP_TARGET | Out-Null'],
                   env=env, check=True)
    print('prepared', game)
    return game


def game_environment(game, cache, hold, provenance=None, extra=None, resolution='1080p', msaa='2'):
    """Sanitised child environment. Matches the settings the starter template was collected under:
    default 16:9 context, anisotropy 16 (the engine default), smooth colour on (default)."""
    env = {k: v for k, v in os.environ.items() if not k.startswith(SCRUB_PREFIXES)}
    env.update(PS3_VERBOSE='0', GT5P_NO_SETTINGS='1', FS_HIDE='grim/file/contents', GT5P_PROFVIEW='0',
               GT5P_ROOT=str(game), GT5P_GAME_DIR='input/pkg/', PS3_VFS_ROOT=str(game),
               PS3_GAMEDATA_ROOT=str(game / 'gamedata'), RSX_SHADER_CACHE=str(cache),
               RSX_SHADER_WARMUP='0', RSX_PSO_ASYNC='1', RSX_SHADER_ASYNC='1', RSX_PSO_RECIPES='1',
               RSX_PSO_RECIPE_KEEP_DAYS='0', RSX_RACE_PREWARM='0', RSX_PRESENT_SYNC='1',
               PAD_HOLD_MERGE='0', GT5P_RESOLUTION=resolution, RSX_MSAA=msaa, PAD_HOLD=hold)
    if provenance is not None:
        env['RSX_PSO_PROVENANCE'] = str(provenance)
        env['RSX_PSO_PROVENANCE_LIMIT'] = str(PROVENANCE_LIMIT)
    env.update(extra or {})
    return env


class Tail:
    """Incremental reader of a file another process is still writing."""

    def __init__(self, path):
        self.path, self.pos, self.partial = Path(path), 0, b''

    def lines(self):
        try:
            with open(self.path, 'rb') as stream:
                stream.seek(self.pos)
                data = stream.read()
        except OSError:
            return []
        self.pos += len(data)
        data = self.partial + data
        *complete, self.partial = data.split(b'\n')
        return [line.decode('utf-8', 'replace').rstrip('\r') for line in complete]


class Session:
    """One game process: stdout milestones, provenance links, recipe settling, window shots."""

    def __init__(self, engine, game, env, out_dir, provenance=None, cache=None, foreground=True):
        self.engine, self.game, self.env = Path(engine), Path(game), env
        self.out = Path(out_dir)
        self.provenance, self.cache = provenance, cache
        self.foreground = foreground
        self.proc = None
        self.hwnd = 0
        self.start = None
        self.milestones = {}          # name -> dict(wall, pad_ms)
        self.pad_t0 = None            # wall time (since launch) of the PAD_HOLD clock zero, tightest bound
        self.links = []               # dict(t, pipeline, fp, vp, request)
        self.link_tail = None
        self.out_tail = None
        self.log = []

    def now(self):
        return time.monotonic() - self.start

    def launch(self):
        self.out.mkdir(parents=True, exist_ok=True)
        self.stdout = open(self.out / 'game.out', 'wb')
        self.stderr = open(self.out / 'game.err', 'wb')
        self.start = time.monotonic()
        self.proc = subprocess.Popen([str(self.engine)], cwd=str(self.game), env=self.env, stdout=self.stdout,
                                     stderr=self.stderr, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.out_tail = Tail(self.out / 'game.out')

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def ensure_window(self, timeout=20.0):
        deadline = time.monotonic() + timeout
        while not self.hwnd and time.monotonic() < deadline and self.alive():
            self.hwnd = find_window(self.proc.pid)
            if not self.hwnd:
                time.sleep(0.1)
        if self.hwnd and self.foreground:
            w = _win()
            w['user32'].ShowWindow(self.hwnd, 5)
            w['user32'].SetForegroundWindow(self.hwnd)
        return self.hwnd

    def poll(self):
        """Read new stdout milestones and new provenance links. Returns the number of new links."""
        wall = self.now()
        for line in self.out_tail.lines():
            m = MILESTONE_RE.search(line)
            if m and m.group(1) not in self.milestones:
                pad_ms = int(m.group(3))
                self.milestones[m.group(1)] = dict(wall=wall, pad_ms=pad_ms)
                if pad_ms >= 0:
                    bound = wall - pad_ms / 1000.0
                    self.pad_t0 = bound if self.pad_t0 is None else min(self.pad_t0, bound)
            elif line.startswith(('[cellPad] PAD_HOLD', '[pso-provenance]')):
                self.log.append((wall, line))
        new = 0
        if self.provenance is not None:
            if self.link_tail is None:
                files = sorted(Path(self.provenance).glob('links_*.jsonl'))
                if files:
                    self.link_tail = Tail(files[-1])
            if self.link_tail is not None:
                for line in self.link_tail.lines():
                    try:
                        row = json.loads(line)
                    except ValueError:
                        continue
                    self.links.append(dict(t=wall, pipeline=row['pipeline'], fp=row['fp_identity'],
                                           vp=row['vp_raw'], request=row['request']))
                    new += 1
        return new

    def pending_recipes(self):
        """Linked pipelines whose native pipeline has not been created (no recipe file yet)."""
        if self.cache is None:
            return []
        directory = Path(self.cache) / 'warmup-v1'
        return sorted({l['pipeline'] for l in self.links if not (directory / f"pso_{l['pipeline']}.recipe").exists()})

    def anchor_wall(self, anchor, ms):
        """Wall time (since launch) of `anchor`+ms, or None until that milestone has been seen."""
        if not anchor:
            return None if self.pad_t0 is None else self.pad_t0 + ms / 1000.0
        seen = self.milestones.get(anchor)
        if seen is None or self.pad_t0 is None or seen['pad_ms'] < 0:
            return None
        return self.pad_t0 + (seen['pad_ms'] + ms) / 1000.0

    def shot(self, name, **options):
        if not self.hwnd:
            self.ensure_window(2.0)
        if not self.hwnd:
            return None
        info = capture(self.hwnd, self.out / name, **options)
        info['file'] = name
        info['title'] = window_title(self.hwnd)
        return info

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            subprocess.run(['taskkill', '/PID', str(self.proc.pid), '/T', '/F'], capture_output=True)
            try:
                self.proc.wait(timeout=15)
            except subprocess.TimeoutExpired:
                pass
        for stream in (getattr(self, 'stdout', None), getattr(self, 'stderr', None)):
            if stream:
                stream.close()


def idle_check():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq gt5p.exe', '/NH'], capture_output=True, text=True).stdout.lower()
    if 'gt5p.exe' in out:
        raise RuntimeError('Another gt5p.exe is running; nothing was stopped (use the test lock)')


# --------------------------------------------------------------------------
# Chunk execution
# --------------------------------------------------------------------------
def execute_chunk(script, plan, args, attempt_dir, game, cache):
    """Run one chunk; return the result document (verification outcome, per-unit shots and link attribution)."""
    attempt_dir = Path(attempt_dir)
    prov = attempt_dir / 'provenance'
    prov.mkdir(parents=True, exist_ok=True)
    env = game_environment(game, cache, script.hold(), prov, resolution=plan['settings']['resolution'],
                           msaa=plan['settings']['msaa'])
    session = Session(args.engine, game, env, attempt_dir, provenance=prov, cache=cache, foreground=not args.no_foreground)
    due = []   # (unit_index, shot)
    for ui, unit in enumerate(script.units):
        for shot in unit.shots:
            due.append((ui, shot))
    taken = {}     # (ui, name) -> shot info
    previous_sig = None
    deadline = script.seconds * 1.5 + 60
    last_link_change = None
    started = time.monotonic()
    error = None
    try:
        session.launch()
        session.ensure_window()
        while session.alive() and session.now() < deadline:
            before = len(session.links)
            session.poll()
            if len(session.links) != before:
                last_link_change = session.now()
            for item in list(due):
                ui, shot = item
                target = session.anchor_wall(shot['anchor'], shot['ms'])
                if target is not None and session.now() >= target:
                    options = {k: shot[k] for k in ('crop', 'regions', 'scale') if shot.get(k) is not None}
                    info = session.shot(f"{script.units[ui].id.replace('/', '_')}.{shot['name']}.png", **options)
                    if info:
                        stats = signature_stats(info['signature'], previous_sig)
                        previous_sig = info['signature']
                        info.update(stats)
                        info['t'] = round(session.now(), 2)
                        info['links'] = len(session.links)
                        info['pending'] = len(session.pending_recipes())
                        info.pop('signature', None)
                        taken[(ui, shot['name'])] = info
                    due.remove(item)
            if not due:
                break
            time.sleep(0.1)
        # drain: let queued pipelines finish creating (recipes present) before the process is killed
        drain_end = session.now() + float(plan['timing']['drain_max'])
        quiet = float(plan['timing']['drain_quiet'])
        while session.alive() and session.now() < drain_end:
            before = len(session.links)
            session.poll()
            if len(session.links) != before:
                last_link_change = session.now()
            if not session.pending_recipes() and (last_link_change is None or session.now() - last_link_change >= quiet):
                break
            time.sleep(0.2)
        session.poll()
    except Exception as exc:          # recorded, never swallowed: the chunk is marked failed below
        error = f'{type(exc).__name__}: {exc}'
    finally:
        alive_at_end = session.alive()
        session.stop()
    return build_result(script, session, taken, due, alive_at_end, error, time.monotonic() - started)


def build_result(script, session, taken, due, alive_at_end, error, elapsed):
    starts = []
    for unit in script.units:
        starts.append((unit.id, session.anchor_wall(*unit.start)))
    link_rows = [(l['t'], l['pipeline']) for l in session.links]
    owned = attribute_links(link_rows, starts)
    units, ok_all = [], True
    for ui, unit in enumerate(script.units):
        checks = []
        start = starts[ui][1]
        shots = [dict(taken[(ui, s['name'])], name=s['name']) for s in unit.shots if (ui, s['name']) in taken]
        want = unit.expect.get('milestone')
        if want:
            checks.append(dict(check=f'milestone {want}', ok=want in session.milestones))
        if start is None:
            checks.append(dict(check='start anchor reached', ok=False))
        if unit.shots:
            checks.append(dict(check='shots taken', ok=len(shots) == len(unit.shots)))
        if unit.kind == 'showroom-scan':
            first = next((s for s in shots if str(s.get('name', '')).startswith('scan')), None)
            count = 0
            if first:
                count = first.get('regions', {}).get('name', {}).get('count', 0)
            checks.append(dict(check=f'carousel name visible ({count} px)', ok=count >= 40))
        mean_range = unit.expect.get('mean')
        if mean_range and shots:
            mean = shots[-1]['mean']
            checks.append(dict(check=f'last-shot mean luminance {mean:.0f} within {mean_range}',
                               ok=mean_range[0] <= mean <= mean_range[1]))
        text = unit.expect.get('text')
        if text and shots:
            region, minimum = text
            count = shots[0].get('regions', {}).get(region, {}).get('count', 0)
            checks.append(dict(check=f'{region} label visible ({count} px, need {minimum})', ok=count >= minimum))
        keys = owned.get(unit.id, [])
        key_set = set(keys)
        arrival = [t for t, k in link_rows if k in key_set] if keys else []
        next_start = next((s2 for _, s2 in starts[ui + 1:] if s2 is not None), None)
        end = next_start if next_start is not None else (arrival and max(arrival)) or 0
        late = sum(1 for t in arrival if t >= end - 2.0) if arrival else 0
        entry = dict(unit.to_json(), start_s=None if start is None else round(start, 2), late_links=late,
                     links=len(keys), keys=keys, shots=shots, checks=checks,
                     first_link_s=round(min(arrival) - start, 2) if arrival and start is not None else None,
                     last_link_s=round(max(arrival) - start, 2) if arrival and start is not None else None,
                     ok=all(c['ok'] for c in checks))
        ok_all = ok_all and entry['ok']
        units.append(entry)
    pending = session.pending_recipes()
    return dict(schema=1, chunk=script.chunk_id, ok=bool(ok_all and not error and not due),
                error=error, process_alive_at_end=alive_at_end, unshot=[s['name'] for _, s in due],
                elapsed_s=round(elapsed, 1), pad_t0=session.pad_t0, milestones=session.milestones,
                links_total=len(session.links), pending_recipes_at_stop=len(pending),
                boot_links=len(owned.get(None, [])), units=units, link_times=[[round(t, 2), k] for t, k in link_rows],
                log=[line for _, line in session.log])


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------
def cmd_setup(args):
    setup_root(args.root, args.fixture)


def cmd_check(args):
    plan = load_plan(args.plan)
    chunks = expand_chunks(plan)
    total = 0.0
    for chunk in chunks:
        script = compile_chunk(plan, chunk)
        total += script.seconds
        units = [u for u in script.units if u.kind != 'boot']
        print(f"{chunk['id']:<34} presses={len(script.presses):>2}/{MAX_PADHOLD_PRESSES} units={len(units):>2} "
              f"~{script.seconds:5.0f}s")
        if args.verbose:
            print('   ', script.hold())
    print(f'{len(chunks)} chunks, about {total / 60:.0f} min of game time (estimate, excludes retries)')


def cmd_run(args):
    plan = load_plan(args.plan)
    root, out = isolated(args.root), isolated(args.out)
    game = root / 'game'
    if not (game / 'input/pkg').exists():
        raise SystemExit('Prepare the private game root first: content_sweep.py setup')
    out.mkdir(parents=True, exist_ok=True)
    cache = isolated(args.cache) if args.cache else (out / 'shadercache')
    cache.mkdir(exist_ok=True)
    state = load_state(out)
    chunks = expand_chunks(plan, args.only.split(',') if args.only else None)
    todo = pending_chunks(chunks, state, args.attempts, args.force)
    print(f'{len(todo)} of {len(chunks)} chunks to run', flush=True)
    budget_end = time.monotonic() + args.max_seconds if args.max_seconds else None
    for chunk in todo:
        script = compile_chunk(plan, chunk)
        if budget_end and time.monotonic() + script.seconds > budget_end:
            print('time budget reached before', chunk['id'])
            break
        idle_check()
        entry = state['chunks'].setdefault(chunk['id'], dict(status='new', attempts=0))
        entry['attempts'] += 1
        attempt_dir = out / 'chunks' / chunk['id'] / f"attempt-{entry['attempts']}"
        if attempt_dir.exists():
            raise SystemExit('Refusing to overwrite ' + str(attempt_dir))
        print(f"== {chunk['id']} attempt {entry['attempts']} (~{script.seconds:.0f}s, {len(script.presses)} presses)", flush=True)
        entry.update(status='running', started=time.strftime('%Y-%m-%dT%H:%M:%S'))
        save_state(out, state)
        result = execute_chunk(script, plan, args, attempt_dir, game, cache)
        (attempt_dir / 'result.json').write_text(json.dumps(result, indent=1))
        entry.update(status='done' if result['ok'] else 'failed', attempt_dir=str(attempt_dir.relative_to(out)),
                     elapsed_s=result['elapsed_s'], links=result['links_total'],
                     failed_units=[u['id'] for u in result['units'] if not u['ok']], error=result['error'])
        save_state(out, state)
        for u in result['units']:
            if u['kind'] == 'boot':
                continue
            flag = 'ok ' if u['ok'] else 'FAIL'
            bad = '; '.join(c['check'] for c in u['checks'] if not c['ok'])
            print(f"   {flag} {u['id']:<28} links={u['links']:>4} last_link=+{u['last_link_s']}s {bad}", flush=True)
        print(f"   boot links={result['boot_links']} total={result['links_total']} pending_at_stop="
              f"{result['pending_recipes_at_stop']} elapsed={result['elapsed_s']}s", flush=True)
    done = sum(1 for e in state['chunks'].values() if e['status'] == 'done')
    print(f'{done} chunks done, state in {out / "state.json"}')


def scan_results(out):
    """survey results -> {maker_id: (cars or None, note)} from every attempt's scan units (latest wins)."""
    found = {}
    for result_path in sorted((Path(out) / 'chunks').glob('*/attempt-*/result.json')):
        result = json.loads(result_path.read_text())
        for unit in result['units']:
            if unit['kind'] != 'showroom-scan':
                continue
            stats = [s.get('regions', {}).get('name') for s in unit['shots']
                     if str(s.get('name', '')).startswith('scan')]
            found[unit['meta']['maker']] = detect_car_count(stats)
    return found


def cmd_plan_update(args):
    plan = json.loads(Path(args.plan).read_text())
    found = scan_results(args.out)
    changed = []
    for maker in plan['dealer']['makers']:
        cars, note = found.get(maker['id'], (None, 'not surveyed'))
        if cars is not None and maker.get('cars') != cars:
            maker['cars'] = cars
            changed.append((maker['id'], cars))
    load_plan(plan)
    Path(args.output).write_text(json.dumps(plan, indent=2) + '\n')
    for maker_id, cars in changed:
        print(f'{maker_id}: {cars} cars')
    unknown = [m for m, (c, n) in found.items() if c is None]
    print(f'{len(changed)} makers updated; unresolved: {unknown}')


def cmd_probe(args):
    root = isolated(args.root)
    out = isolated(args.out)
    game = root / 'game'
    cache = root / 'shadercache'
    cache.mkdir(parents=True, exist_ok=True)
    idle_check()
    hold = args.hold
    if hold.startswith('@dealers'):
        hold = hold_string(to_dealers()) + hold[len('@dealers'):]
    elif hold.startswith('@course:'):
        slot, _, rest = hold[len('@course:'):].partition(' ')
        hold = hold_string(to_course(slot=int(slot))) + rest
    prov = out / 'provenance'
    prov.mkdir(parents=True, exist_ok=True)
    env = game_environment(game, cache, hold, prov, resolution=args.resolution, msaa=args.msaa)
    session = Session(args.engine, game, env, out, provenance=prov, cache=cache, foreground=not args.no_foreground)
    timeline = []
    try:
        session.launch()
        session.ensure_window()
        shot_n = 0
        next_shot = args.shot_start
        seen_ms = set()
        while session.alive() and session.now() < args.seconds:
            session.poll()
            for name, info in list(session.milestones.items()):
                if name not in seen_ms:
                    seen_ms.add(name)
                    print(f"{info['wall']:6.1f}s milestone {name} (pad clock {info['pad_ms']} ms)", flush=True)
            if session.now() >= next_shot:
                shot_n += 1
                info = session.shot(f'p{shot_n:03d}.png', scale=2)
                if info:
                    stats = signature_stats(info['signature'])
                    timeline.append(dict(t=round(session.now(), 1), file=info['file'], links=len(session.links),
                                         pending=len(session.pending_recipes()), mean=round(stats['mean'], 1),
                                         title=info['title'][:100]))
                    print(f"{session.now():6.1f}s shot {info['file']} links={len(session.links)} "
                          f"pending={timeline[-1]['pending']} mean={stats['mean']:.0f} :: {info['title'][:90]}", flush=True)
                next_shot += args.shot_every
            time.sleep(0.1)
        session.poll()
    finally:
        session.stop()
    (out / 'probe.json').write_text(json.dumps(dict(hold=hold, milestones=session.milestones, timeline=timeline,
                                                    links=session.links), indent=1))
    print('links:', len(session.links), 'pending recipes at stop:', len(session.pending_recipes()))


def cmd_contact(args):
    import glob
    files = []
    for pattern in args.files:
        found = sorted(glob.glob(pattern))
        files.extend(found if found else [pattern])
    output = isolated(args.output.parent) / args.output.name
    sheet, layout = contact_sheet(files, args.columns, args.tile_width)
    output.write_bytes(sheet)
    print('wrote', output)
    for row, column, file in layout:
        resolved = Path(file).resolve()
        print(f'  r{row} c{column}  {resolved.relative_to(ROOT) if ROOT in resolved.parents else file}')


# --------------------------------------------------------------------------
# Report: export per-chunk templates, compare with the starter, saturation per unit
# --------------------------------------------------------------------------
def latest_attempt(out, entry):
    return Path(out) / entry['attempt_dir']


def merge_quarantining(documents):
    """Union of same-contract templates; a key with two different records is dropped and reported."""
    records, conflicts = {}, set()
    for document in documents:
        for record in document['records']:
            key = record['key']
            if key in conflicts:
                continue
            if key in records and records[key] != record:
                records.pop(key)
                conflicts.add(key)
            else:
                records[key] = record
    return dict(documents[0], records=list(records.values())), sorted(conflicts)


def cmd_report(args):
    sys.path.insert(0, str(ROOT / 'scripts'))
    import pipeline_template as pt
    import pipeline_template_coverage as cov
    from train_pipeline_cache import save_report
    out = isolated(args.out)
    state = load_state(out)
    plan = load_plan(args.plan)
    cache = out / 'shadercache'
    baseline = pt.read(Path(args.baseline))
    starter = {r['key'] for r in baseline['records']}
    elf = Path(args.elf) if args.elf else (isolated(args.root) / 'game/input/EMAIN.ELF')
    compat = pt.compatibility(Path(args.engine), Path(args.decoder), elf)
    if compat != baseline['compatibility']:
        raise SystemExit('The sweep contract (renderer/ELF/settings) differs from the baseline template; not comparable')
    order = [c['id'] for c in expand_chunks(plan) if c['id'] in state['chunks']]
    sessions, sequence, per_chunk = {}, [], []
    exportable_all, first_boot = set(), True
    for cid in order:
        entry = state['chunks'][cid]
        if 'attempt_dir' not in entry:
            continue
        attempt = latest_attempt(out, entry)
        result = json.loads((attempt / 'result.json').read_text())
        template_path = attempt / 'template.json'
        if template_path.exists():
            document, rejected = pt.read(template_path), json.loads((attempt / 'export-rejected.json').read_text())
        else:
            document, rejected = pt.export(attempt / 'provenance', cache, compat)
            save_report(template_path, document)
            (attempt / 'export-rejected.json').write_text(json.dumps(rejected))
        keys = {r['key'] for r in document['records']}
        exportable_all |= keys
        per_chunk.append(dict(chunk=cid, status=entry['status'], attempts=entry['attempts'], links=result['links_total'],
                              exported=len(keys), rejected=rejected, new_vs_starter=len(keys - starter),
                              elapsed_s=result['elapsed_s'], failed_units=entry.get('failed_units', [])))
        sessions.setdefault(cid.split('-')[0], []).append(document)
        for unit in result['units']:
            if unit['kind'] == 'boot':
                if first_boot:
                    sequence.append(('menu-boot', unit['keys'], unit))
                    first_boot = False
                continue
            sequence.append((f"{cid}:{unit['id']}", unit['keys'], unit))
    rows = saturation([(label, keys) for label, keys, _ in sequence], starter, exportable_all)
    for row, (_, _, unit) in zip(rows, sequence):
        row.update(kind=unit['kind'], verified=unit['ok'], last_link_s=unit['last_link_s'],
                   late_links=unit.get('late_links'))
    grouped, conflicts = {}, {}
    for label, documents in sessions.items():
        grouped[label], conflicts[label] = merge_quarantining(documents)
    coverage = delta = None
    if grouped:
        coverage, delta = cov.analyze(baseline, grouped, quarantine_conflicts=True)
    report = dict(schema='gt5p-content-sweep-report', version=1,
                  policy='Observed metadata only. Candidates still need original-asset lookup, both-stage shader '
                         'reconstruction and exact native preparation before they can enter a starter.',
                  baseline_records=len(starter), chunks=per_chunk, units=rows, coverage=coverage,
                  merge_conflicts={k: v for k, v in conflicts.items() if v})
    save_report(out / 'report.json', report)
    if delta is not None:
        save_report(out / 'delta-candidates.json', delta)
    lines = ['| unit | kind | ok | links | new in sweep | exportable | new vs starter | cumulative new vs starter | last link (s) |',
             '|---|---|---|---|---|---|---|---|---|']
    for row in rows:
        lines.append(f"| {row['unit']} | {row['kind']} | {'yes' if row['verified'] else 'NO'} | {row['links']} | "
                     f"{row['new_in_sweep']} | {row['exportable']} | {row['new_vs_starter']} | "
                     f"{row['cumulative_new_vs_starter']} | {row['last_link_s']} |")
    table = os.linesep.join(lines) + os.linesep
    (out / 'report.md').write_text(table)
    print(table, end='')
    if coverage:
        print(json.dumps(dict(union=coverage['union'], additional_records=coverage['additional_records'],
                              new_with_existing_programs=coverage['additional_pipelines_with_existing_programs'],
                              new_needing_new_programs=coverage['additional_pipelines_needing_new_programs'],
                              conflicts=len(coverage['quarantined_conflicts']) + sum(len(v) for v in conflicts.values())),
                         indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)
    s = sub.add_parser('setup')
    s.add_argument('--root', type=Path, default=ROOT / 'scratch/content-sweep')
    s.add_argument('--fixture', type=Path, default=DEFAULT_FIXTURE)
    c = sub.add_parser('check')
    c.add_argument('--plan', type=Path, required=True)
    c.add_argument('--verbose', action='store_true')
    r = sub.add_parser('run')
    r.add_argument('--root', type=Path, default=ROOT / 'scratch/content-sweep')
    r.add_argument('--out', type=Path, required=True)
    r.add_argument('--plan', type=Path, required=True)
    r.add_argument('--engine', type=Path, default=DEFAULT_ENGINE)
    r.add_argument('--cache', type=Path, help='private RSX_SHADER_CACHE (default: <out>/shadercache)')
    r.add_argument('--only', help='comma list of chunk ids, maker ids or kinds (dealer, course)')
    r.add_argument('--attempts', type=int, default=2, help='retry a failed chunk until it has had this many attempts')
    r.add_argument('--force', action='store_true', help='run done chunks again')
    r.add_argument('--max-seconds', type=float, default=0, help='do not start a chunk that would end after this budget')
    r.add_argument('--no-foreground', action='store_true')
    u = sub.add_parser('plan-update')
    u.add_argument('--out', type=Path, required=True)
    u.add_argument('--plan', type=Path, required=True)
    u.add_argument('--output', type=Path, required=True)
    p = sub.add_parser('probe')
    p.add_argument('--root', type=Path, default=ROOT / 'scratch/content-sweep')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--engine', type=Path, default=DEFAULT_ENGINE)
    p.add_argument('--hold', required=True)
    p.add_argument('--seconds', type=float, default=90.0)
    p.add_argument('--shot-start', type=float, default=20.0)
    p.add_argument('--shot-every', type=float, default=4.0)
    p.add_argument('--resolution', default='1080p')
    p.add_argument('--msaa', default='2')
    p.add_argument('--no-foreground', action='store_true')
    ct = sub.add_parser('contact', help='tile screenshots into one PNG for visual review')
    ct.add_argument('--output', type=Path, required=True)
    ct.add_argument('--columns', type=int, default=3)
    ct.add_argument('--tile-width', type=int, default=640)
    ct.add_argument('files', nargs='+', help='PNG files or glob patterns (kept in the order given)')
    rp = sub.add_parser('report')
    rp.add_argument('--root', type=Path, default=ROOT / 'scratch/content-sweep')
    rp.add_argument('--out', type=Path, required=True)
    rp.add_argument('--baseline', type=Path, default=ROOT / 'assets/pipeline-templates/gt5p-disc-v2')
    rp.add_argument('--engine', type=Path, default=DEFAULT_ENGINE)
    rp.add_argument('--decoder', type=Path, default=DEFAULT_DECODER)
    rp.add_argument('--elf', type=Path)
    rp.add_argument('--plan', type=Path, default=ROOT / 'config/content-sweep/gt5p-prologue.json',
                    help='the plan fixes the sweep order used by the saturation table')
    args = ap.parse_args(argv)
    {'setup': cmd_setup, 'check': cmd_check, 'run': cmd_run, 'plan-update': cmd_plan_update,
     'probe': cmd_probe, 'contact': cmd_contact, 'report': cmd_report}[args.command](args)


if __name__ == '__main__':
    main()
