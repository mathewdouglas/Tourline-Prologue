"""Background preparation while the player plays (Phase 225).

A player who has not prepared gets the preparation helper started by the launcher beside the game, at idle
priority, with fewer compiler workers. It works races first:

1. Race stage: the observed race membership of the bundled warmup plan (2,113 of the starter's 12,669 records,
   557 of 2,824 fragment programs) is prepared on its own, through the same template preparation, translation
   and MSAA re-target stages as a full preparation, into preparation/race-<token>/stage. Every pipeline is
   proven exactly as in a full preparation (shader bytes, native key, driver creation, persistence).
2. Merge: the race stage's files are copied into the cache the running game uses (never replacing a file the
   game already has; each file lands by an atomic rename), recipes last, and the race pipelines are appended
   to that cache's race membership (warmup-v1/race-v1.txt). The renderer reads that list at every race
   loading screen, so the next race prepares them inside the loading gate; draws before then find the shader
   bytes and driver blobs on disk instead of compiling.
3. Full stage: the ordinary full preparation, reusing the race stage's verified shaders and driver blobs. It is
   selected (prepared-cache.txt) only after it completes, as before, so the next launch uses it.

While the race stage runs (Phase 226), its finished shaders and driver blobs are copied into the live cache every
few seconds, each only once complete and well formed (GT5P_PREPARE_BACKGROUND_TRICKLE=0: only at the end). Draws
then find them on disk before the stage completes; recipes and the race list still wait for the proven stage.

GT5P_PREPARE_BACKGROUND=0 (launcher) restores the one-time preparation offer. GT5P_PREPARE_BACKGROUND_WORKERS
sets the compiler workers (2..12; default half the logical processors, at least 2). The launcher pauses the
helper's processes while a race runs (GT5P_RACE_EVENT from the renderer; GT5P_PREPARE_BACKGROUND_PAUSE=0 never
pauses), so it works in the menus.
"""
import json
import os
from pathlib import Path
import re
import struct
import time
import uuid

MARKER = 'merged-v1.json'
MAX_FILE = 64 * 1024**2
MAX_INDEX = 1024 * 1024
PATTERNS = {
    '.': re.compile(r'(?:[0-9a-f]{16}\.dxbc|pso_[0-9a-f]{16}\.bin)'),
    'warmup-v1': re.compile(r'code_[0-9a-f]{16}\.dxbc'),
}
RECIPE = re.compile(r'pso_[0-9a-f]{16}\.recipe')


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_BACKGROUND', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_BACKGROUND must be unset, 0 or 1')
    return value == '1'


def workers(environ=None, cpus=None):
    environ = os.environ if environ is None else environ
    value = environ.get('GT5P_PREPARE_BACKGROUND_WORKERS')
    if value is not None:
        if not value.isdigit() or not 2 <= int(value) <= 12:
            raise ValueError('GT5P_PREPARE_BACKGROUND_WORKERS must be 2..12')
        return int(value)
    cpus = (os.cpu_count() or 2) if cpus is None else cpus
    return max(2, min(12, cpus // 2))


def trickle_enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_BACKGROUND_TRICKLE', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_BACKGROUND_TRICKLE must be unset, 0 or 1')
    return value == '1'


def complete(name, data):
    """A shader container or driver blob that is whole: its own length field matches (and the blob checksum)."""
    if name.endswith('.bin'):
        from preparation_reuse import driver_blob_valid
        return driver_blob_valid(data)
    return len(data) >= 32 and data[:4] == b'DXBC' and struct.unpack_from('<I', data, 24)[0] == len(data)


def lower_priority():
    """Idle CPU priority for this process and, by inheritance, every process it starts. Best effort.
    Not PROCESS_MODE_BACKGROUND_BEGIN: measured, it puts the process back to NORMAL_PRIORITY_CLASS as far as
    child processes see it, so the compiler and offline processes started at normal priority."""
    if os.name != 'nt':
        return
    import ctypes
    kernel = ctypes.windll.kernel32
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetPriorityClass.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.SetPriorityClass(kernel.GetCurrentProcess(), 0x00000040)     # IDLE_PRIORITY_CLASS


def race_records(document, plan):
    """Records of the plan's race phase, in template order."""
    race = set(plan['phases']['race'])
    records = [r for r in document['records'] if r['key'] in race]
    if len(records) != len(race):
        raise ValueError('Warmup plan race membership is not in this template')
    return records


def write_subset(document, records, folder):
    """The race subset as its own template bundle (deterministic; an existing one must match)."""
    from pipeline_template import bundle, read
    subset = dict(document, records=records)
    if folder.exists():
        if read(folder) != subset:
            raise ValueError('Race stage template changed; preparation retained')
        return folder
    temporary = folder.with_name(folder.name + '.' + uuid.uuid4().hex + '.tmp')
    bundle(subset, temporary)
    temporary.replace(folder)
    return folder


def race_keys(report, plan, translation, msaa_mapping, warmup):
    """Native keys the game will draw for the plan's race phase in the player's mode."""
    from preparation_template_inputs import successful_inputs
    inputs = successful_inputs(report)
    keys = [inputs[k] for k in plan['phases']['race'] if k in inputs]
    if translation != 'default':
        extra = report.get('additional_translation') or {}
        moved = {r['template_key']: r['key'] for r in extra.get('records', [])
                 if isinstance(r.get('template_key'), str) and isinstance(r.get('key'), str)}
        keys = [moved[k] for k in keys if k in moved]
    if msaa_mapping:
        keys = [msaa_mapping.get(k, k) for k in keys]
    keys = list(dict.fromkeys(keys))
    return [k for k in keys if (warmup / ('pso_' + k + '.recipe')).is_file()]


def _regular_dir(path):
    path = Path(path)
    for p in (path, *path.parents):
        if p.is_symlink() or p.is_junction():
            raise ValueError('Cache directories must not be redirected')
    return path


def _place(source, target, check=True):
    """Copy one file by an atomic rename that never replaces an existing file. True when placed, False when the
    target exists, None when the source is not (yet) a complete file."""
    if target.exists():
        return False
    data = source.read_bytes()
    if len(data) > MAX_FILE:
        raise ValueError('Prepared file exceeds its bound')
    if check and not complete(source.name, data):
        return None
    temporary = target.with_name('.' + target.name + '.' + uuid.uuid4().hex + '.tmp')
    with temporary.open('xb') as stream:
        stream.write(data)
    try:
        os.rename(temporary, target)     # Windows: fails if the target appeared meanwhile
    except FileExistsError:
        temporary.unlink()
        return False
    return True


def _append(index, keys):
    """Append keys missing from a membership index in one write (the renderer appends lines too)."""
    existing = set()
    if index.exists():
        if index.is_symlink() or index.stat().st_size > MAX_INDEX:
            raise ValueError('Unexpected race membership index')
        existing = set(index.read_text(encoding='ascii', errors='replace').split())
    new = [k for k in keys if k not in existing]
    if new:
        with open(index, 'ab') as stream:
            stream.write(''.join(k + '\n' for k in new).encode('ascii'))
    return len(new)


def merge(stage_cache, live_cache, keys, progress=None):
    """Copy the race stage into the live cache (shaders and driver blobs, then recipes), then append the race
    membership. Never replaces, deletes or rewrites anything the game wrote, except appending index lines."""
    stage_cache = _regular_dir(stage_cache)
    live_cache = _regular_dir(live_cache)
    (live_cache / 'warmup-v1').mkdir(parents=True, exist_ok=True)
    counts = dict(placed=0, present=0, incomplete=0, recipes=0)
    for sub, pattern in PATTERNS.items():
        folder = stage_cache / sub
        for number, source in enumerate(sorted(folder.iterdir())):
            if progress and number % 256 == 0:
                progress('background-merge', {})
            if not pattern.fullmatch(source.name) or not source.is_file() or source.is_symlink():
                continue
            placed = _place(source, live_cache / sub / source.name)
            counts['incomplete' if placed is None else 'placed' if placed else 'present'] += 1
    for key in keys:
        name = 'pso_' + key + '.recipe'
        if not RECIPE.fullmatch(name):
            raise ValueError('Malformed race key')
        if _place(stage_cache / 'warmup-v1' / name, live_cache / 'warmup-v1' / name, check=False):
            counts['recipes'] += 1
    counts['race_keys'] = len(keys)
    counts['race_appended'] = _append(live_cache / 'warmup-v1' / 'race-v1.txt', keys)
    return counts


class Trickle:
    """Phase 226: called often while the race stage runs; at most every `interval` seconds it copies the stage's
    new shaders and driver blobs into the live cache, through the same never-replacing atomic placement. Files
    not yet complete are retried next time. Recipes and race membership are not trickled."""

    def __init__(self, stage_cache, live_cache, interval=5.0, clock=time.monotonic):
        self.stage, self.live = Path(stage_cache), _regular_dir(live_cache)
        self.interval, self.clock, self.last, self.done = interval, clock, None, set()
        self.counts = dict(trickled=0, trickle_passes=0)

    def __call__(self, force=False):
        now = self.clock()
        if not force and self.last is not None and now - self.last < self.interval:
            return
        self.last = now
        if not self.stage.is_dir():
            return
        _regular_dir(self.stage)
        (self.live / 'warmup-v1').mkdir(parents=True, exist_ok=True)
        self.counts['trickle_passes'] += 1
        before = self.counts['trickled']
        for sub, pattern in PATTERNS.items():
            folder = self.stage / sub
            if not folder.is_dir():
                continue
            for entry in os.scandir(folder):
                key = (sub, entry.name)
                if key in self.done or not pattern.fullmatch(entry.name) or not entry.is_file(follow_symlinks=False):
                    continue
                placed = _place(Path(entry.path), self.live / sub / entry.name)
                if placed is None:
                    continue
                self.done.add(key)
                self.counts['trickled'] += placed
        if self.counts['trickled'] != before:
            print(f"Trickled {self.counts['trickled'] - before} files into the live cache "
                  f"({self.counts['trickled']} so far)", flush=True)


def merged(folder, live_cache):
    """The merge record for this live cache, or None."""
    path = Path(folder) / MARKER
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
    return record if isinstance(record, dict) and record.get('live_cache') == str(Path(live_cache).resolve()) else None


def prepare_race(folder, document, plan, translation, live_cache, prepare_stage, msaa_stage, progress=None):
    """Race stage into folder/stage, then merge into live_cache. prepare_stage(template, output, resume, progress)
    runs the template preparation; msaa_stage(output, report, progress) returns the MSAA key mapping or None."""
    from train_pipeline_cache import save_report
    began = time.monotonic()
    folder = Path(folder)
    folder.mkdir(exist_ok=True)
    done = merged(folder, live_cache)
    if done is not None:
        return dict(done, status='already-merged')
    records = race_records(document, plan)
    template = write_subset(document, records, folder / 'template')
    output = folder / 'stage'
    trickle = Trickle(output / 'shadercache', live_cache) if trickle_enabled() else None
    def staged(phase, counts):
        if progress:
            progress(phase, counts)
        if trickle is not None:
            trickle()
    report = prepare_stage(template, output, output.exists(), staged)
    if report['counts'] != {'prepared': len(records)}:
        raise ValueError('Race stage incomplete; normal play remains available')
    mapping = None
    try:
        mapping = msaa_stage(output, report, staged)
    except KeyboardInterrupt:
        raise
    except Exception as exc:  # noqa: BLE001 - optional, as in the full preparation
        report['msaa_map'] = dict(status='failed', reason=str(exc))
    save_report(output / 'report.json', report)
    cache = output / 'shadercache'
    keys = race_keys(report, plan, translation, mapping, cache / 'warmup-v1')
    counts = merge(cache, live_cache, keys, progress)
    if trickle is not None:
        counts.update(trickle.counts)
    record = dict(schema=1, live_cache=str(Path(live_cache).resolve()), translation=translation,
                  records=len(records), seconds=round(time.monotonic() - began, 1), **counts)
    (folder / MARKER).write_text(json.dumps(record, indent=2), encoding='utf-8')
    return dict(record, status='merged')
