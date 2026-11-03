"""Automatically visit supported routes and prepare their learned pipelines.

This pragmatic developer workflow uses real draw state, not independent state
reconstruction. It cannot discover scenes it never visits. All writes are in a
private ignored output; the fixture must already be a copied local game dump.

The default visit is still High Speed Ring then Daytona. --course-slots selects
numeric Course Select ordinals instead, so additional tracks do not need a name
map. --provenance is off unless requested; it records into <output>/provenance
and exports a portable template with pipeline_template.py.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time

from shader_coverage import ROOT, bounded_read, fnv64
from shader_reconstruct import offline_env, run_offline

DEFAULT_TRACKS = ('HighSpeedRing', 'Daytona')
MEASURED_COURSE_SLOTS = {'HighSpeedRing': 0, 'Daytona': 1, 'FujiSpeedwayF': 2}
TRACKS = tuple(MEASURED_COURSE_SLOTS)
# Distinct piece/course_logo_S assets in the read-only volume listing: 10.
# Slots are cursor ordinals. Slots 0..2 are measured; the listing assigns no names.
COURSE_SLOT_MAX = 9
# Runtime clamps RSX_PSO_PROVENANCE_LIMIT to 1..16384 (rsx_pso_provenance.h).
PROVENANCE_LIMIT = 16384


def resolve_routes(tracks, course_slots):
    """Return ordered visit descriptors. Default tracks stay name-tagged."""
    if course_slots is None:
        names = list(DEFAULT_TRACKS if tracks is None else tracks)
        if any(name not in MEASURED_COURSE_SLOTS for name in names):
            raise ValueError('Unknown measured route')
        return [dict(slot=MEASURED_COURSE_SLOTS[name], label=name, tag_kind='track',
                     identity='measured') for name in names]
    if tracks is not None:
        raise ValueError('Pass tracks or course slots, not both')
    if not course_slots or len(set(course_slots)) != len(course_slots):
        raise ValueError('Course slots must be a non-empty list of unique ordinals')
    routes = []
    for slot in course_slots:
        if type(slot) is not int or isinstance(slot, bool) or not 0 <= slot <= COURSE_SLOT_MAX:
            raise ValueError(f'Course slot {slot} is outside the experimental range 0..{COURSE_SLOT_MAX}')
        label = next((name for name, measured in MEASURED_COURSE_SLOTS.items() if measured == slot), f'slot{slot}')
        routes.append(dict(slot=slot, label=label, tag_kind='slot',
                           identity='measured' if slot in MEASURED_COURSE_SLOTS.values() else 'experimental-unverified'))
    return routes


def provenance_directory(output):
    """Owned recorder directory. The runtime requires the parent to exist and rejects a path of 448 characters or more."""
    path = (output / 'provenance').resolve()
    if output.resolve() not in path.parents:
        raise ValueError('Provenance path escapes this run')
    if len(str(path)) >= 448:
        raise ValueError('Provenance path exceeds the runtime directory limit (447 characters)')
    return path


def template_destination(output):
    primary = output / 'session-template.json'
    if not primary.exists():
        return primary
    for number in range(2, 100):
        candidate = output / f'session-template-{number}.json'
        if not candidate.exists():
            return candidate
    raise ValueError('Too many session templates already exist; nothing was overwritten')


def provenance_capture_state(logs, tags):
    """Require the recorder's own enabled line. Return whether it reported an incomplete capture."""
    missing, incomplete = [], False
    for tag in tags:
        err = logs / f'{tag}.err'
        text = err.read_text(errors='replace') if err.exists() else ''
        if '[pso-provenance] enabled:' not in text:
            missing.append(tag)
        if 'capture incomplete' in text:
            incomplete = True
    if missing:
        raise ValueError('Provenance recorder did not start for: ' + ', '.join(missing))
    return incomplete


def export_session(engine, decoder, elf, trace, cache, destination):
    if destination.exists():
        raise ValueError('Template output exists; nothing was overwritten: ' + str(destination))
    if not any(trace.glob('links_*.jsonl')):
        raise ValueError('Provenance directory has no link log; nothing was exported')
    cmd = [sys.executable, str(ROOT / 'scripts/pipeline_template.py'), 'export',
           '--trace', str(trace), '--cache', str(cache), '--engine', str(engine),
           '--decoder', str(decoder), '--elf', str(elf), '--output', str(destination)]
    done = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, errors='replace', timeout=600)
    stdout, stderr = done.stdout or '', done.stderr or ''
    if done.returncode:
        raise ValueError('Template export failed: ' + (stderr or stdout)[-2000:])
    match = re.search(r'(\d+) template records:', stdout)
    records = int(match.group(1)) if match else 0
    if records <= 0:
        raise ValueError('Template export produced no portable records: ' + stdout[-1000:])
    return dict(records=records, exporter_log=stdout[-4000:])


def save_report(path, report):
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n')
    temporary.replace(path)


def idle():
    if b'gt5p.exe' in subprocess.run(['tasklist', '/FI', 'IMAGENAME eq gt5p.exe', '/NH'], capture_output=True).stdout.lower():
        raise ValueError('Another gt5p.exe is running; nothing was stopped')


def isolated(path):
    path = path.resolve()
    if ROOT not in path.parents or subprocess.run(
            ['git', 'check-ignore', '-q', str(path / 'report.json')], cwd=ROOT).returncode:
        raise ValueError('Use a private gitignored path inside this audit checkout')
    return path


def writable_tree(path, output):
    """Reject redirected resume paths before starting any child or cache write."""
    if output not in path.resolve().parents:
        raise ValueError('Writable path escapes this run: ' + str(path))
    for current, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            item = Path(current) / name
            if item.is_symlink() or item.is_junction():
                raise ValueError('Writable run directories must not contain links: ' + str(item))


def bounded_cache_read(path, maximum):
    """Avoid maximum-sized speculative buffers for small, immutable cache files.

    Stat the opened handle, then request one sentinel byte past that size. A
    short read, growth or size change rejects instead of accepting a prefix.
    The caller still validates the complete envelope/checksum independently.
    """
    with path.open('rb') as stream:
        size = os.fstat(stream.fileno()).st_size
        if size > maximum:
            raise ValueError('oversized input')
        data = stream.read(size + 1)
        if len(data) != size or os.fstat(stream.fileno()).st_size != size:
            raise ValueError('Cache file changed during read')
    return data


def recipe_metadata(path, reader=None):
    data = (reader or bounded_read)(path, 16384)
    if (len(data) != 2760 or struct.unpack_from('<QII', data) != (0x31574d5241503547, 1, 2760) or
            struct.unpack_from('<Q', data, 2752)[0] != fnv64(data[:-8])):
        raise ValueError('Invalid pinned Windows x64 recipe envelope/checksum')
    key, vs, ps, vlen, plen = struct.unpack_from('<QQQII', data, 16)
    if not key or path.name != f'pso_{key:016x}.recipe':
        raise ValueError('Recipe filename/key mismatch')
    dependencies = ((vs, vlen), (ps, plen))
    for code, length in dependencies:
        if not 0 < length <= 4 * 1024 * 1024:
            raise ValueError('Invalid bytecode length')
    return f'{key:016x}', dependencies


def validate_code(directory, code, length, reader=None):
    payload = (reader or bounded_read)(directory / f'code_{code:016x}.dxbc', 4 * 1024 * 1024)
    if len(payload) != length or not payload.startswith(b'DXBC') or fnv64(payload) != code:
        raise ValueError('Missing or mismatched recipe bytecode')


def validate_recipe(path, codes=None):
    key, dependencies = recipe_metadata(path)
    for code, length in dependencies:
        if codes is not None and (code, length) in codes:
            continue
        validate_code(path.parent, code, length)
        if codes is not None:
            codes.add((code, length))
    return key


def verification_batch(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_VERIFY_BATCH', '32')
    if value not in ('1', '32'):
        raise ValueError('GT5P_PREPARE_VERIFY_BATCH must be unset, 1, or 32')
    return int(value)


def inventory(cache, validate_blobs=False, progress=None):
    if verification_batch() == 32:
        return inventory_batched(cache, validate_blobs, progress)
    return inventory_legacy(cache, validate_blobs, progress)


def inventory_batched(cache, validate_blobs=False, progress=None):
    """Four bounded readers; unique code validation, metadata-only batch results.

    No bytecode is retained between reads. A batch holds at most 32 metadata
    results; each reader still opens only one payload at a time. All publication
    and progress/cancellation callbacks remain on the owner, after joined reads.
    """
    from preparation_io import read_pool
    paths = sorted((cache/'warmup-v1').glob('*.recipe'))
    def reads(function, items):
        chunks = (items[i:i+32] for i in range(0, len(items), 32))
        def chunk(values):
            return [function(value) for value in values]
        with read_pool(chunk, chunks) as results:
            for values in results:
                yield from values
    def metadata(path):
        try:
            key, dependencies = recipe_metadata(path, bounded_cache_read)
            return path.name, key, dependencies, None
        except (ValueError, OSError) as exc:
            return path.name, None, (), str(exc)
    # Explicit close joins pending readers if a callback cancels the owner.
    from contextlib import closing
    records = []
    with closing(reads(metadata, paths)) as results:
        for number, record in enumerate(results, 1):
            records.append(record)
            if progress:progress('verifying-cache',dict(completed=number,total=len(paths),detail='recipe headers'))
    dependencies = sorted({entry for _,key,deps,error in records if key for entry in deps})
    errors = {}
    def code(entry):
        try:
            validate_code(cache/'warmup-v1', *entry, reader=bounded_cache_read)
            return entry, None
        except (ValueError, OSError) as exc:
            return entry, str(exc)
    with closing(reads(code, dependencies)) as results:
        for number, (entry,error) in enumerate(results, 1):
            if error is not None:errors[entry] = error
            if progress:progress('verifying-cache',dict(completed=number,total=len(dependencies),detail='shared bytecode'))
    keys, rejected = [], []
    for name, key, deps, error in records:
        if error is None:error = next((errors[entry] for entry in deps if entry in errors), None)
        if error is None:keys.append(key)
        else:rejected.append(dict(file=name,reason=error))
    blobs = []
    if validate_blobs:
        with closing(reads(lambda key: valid_blob(cache, key, bounded_cache_read), keys)) as results:
            for number, key in enumerate(results, 1):
                if key is not None:blobs.append(key)
                if progress:progress('verifying-cache',dict(completed=number,total=len(keys),detail='driver blobs'))
    return dict(recipes=keys,valid_driver_blobs=blobs,rejected=rejected)


def valid_blob(cache, key, reader=None):
    try:
        data = (reader or bounded_read)(cache / f'pso_{key}.bin', 32 * 1024 * 1024)
        if len(data) > 24:
            magic, size, checksum = struct.unpack_from('<QQQ', data)
            if magic == 0x31534f5035505447 and size == len(data) - 24 and fnv64(data[24:]) == checksum:
                return key
    except (ValueError, OSError):
        pass
    return None


def inventory_legacy(cache, validate_blobs=False, progress=None):
    from preparation_io import read_pool
    keys, rejected, codes = [], [], set()
    paths=sorted((cache/'warmup-v1').glob('*.recipe'))
    def recipe(path):
        try:
            return validate_recipe(path,codes),None
        except (ValueError, OSError) as exc:
            return None,dict(file=path.name,reason=str(exc))
    with read_pool(recipe,paths) as results:
        for number,(key,error) in enumerate(results,1):
            if error is None:keys.append(key)
            else:rejected.append(error)
            if progress:progress('verifying-cache',dict(completed=number,total=len(paths),detail='recipes'))
    blobs = []
    if validate_blobs:
        with read_pool(lambda key: valid_blob(cache,key),keys) as results:
            for number,key in enumerate(results,1):
                if key is not None:blobs.append(key)
                if progress:progress('verifying-cache',dict(completed=number,total=len(keys),detail='driver blobs'))
    return dict(recipes=keys, valid_driver_blobs=blobs, rejected=rejected)


def route_result(logs, tag):
    out = (logs / f'{tag}.out').read_text(errors='replace')
    window = json.loads((logs / f'{tag}.window.json').read_text(encoding='utf-8-sig'))
    milestones = dict(re.findall(r'\[milestone\] (\w+) at (\d+) ms', out))
    if 'QuickArcadeRoot' not in milestones or window['sample_end_ms'] <= window['sample_start_ms']:
        raise ValueError('Route did not confirm a grid and completed sampling window')
    rows = (logs / f'{tag}.frames.csv').read_text().splitlines()
    times = [float(row.split(',')[0]) for row in rows if len(row.split(',')) == 3]
    presented = [t for t in times if window['sample_start_ms'] <= t <= window['sample_end_ms']]
    if len(presented) < 10 or any(b <= a for a, b in zip(presented, presented[1:])):
        raise ValueError('Route did not confirm ongoing frame presentation')
    return dict(milestones=milestones, presented_samples=len(presented), window=window,
                limitation='Grid/presentation checks do not prove every scene rendered correctly or all variants were encountered.')


def prepare(engine, game, cache, log):
    before = inventory(cache)
    if before['rejected'] or not before['recipes']:
        raise ValueError('Cannot prepare an empty or damaged learned recipe set')
    if len(before['recipes']) > 8192:
        raise ValueError('Recipe set exceeds this runtime offline cap (8192); no partial-success claim')
    env = offline_env(game, cache)
    env.update(RSX_SHADER_WARMUP_BACKGROUND='0', RSX_PSO_RECIPE_KEEP_DAYS='0',
               RSX_SHADER_WARMUP_SCAN='1', RSX_PSO_RECIPES='1')
    text = run_offline(engine, game, env, log, timeout=1200)
    match = re.search(r'\[shader-warmup\] finished: loaded=(\d+) rejected=(\d+) elapsed_ms=(\d+)', text)
    if not match or int(match[1]) != len(before['recipes']) or int(match[2]):
        raise ValueError('Native preparation did not accept every learned recipe; inspect ' + str(log))
    after = inventory(cache, validate_blobs=True)
    if after['rejected'] or set(after['recipes']) != set(before['recipes']) or set(after['valid_driver_blobs']) != set(after['recipes']):
        raise ValueError('Native preparation did not preserve recipes and persist every driver blob')
    return dict(loaded=int(match[1]), rejected=int(match[2]), elapsed_ms=int(match[3]),
                persisted_driver_blobs=len(after['valid_driver_blobs']), guest_entry_executed=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('fixture', 'engine', 'output'):
        ap.add_argument('--' + name, required=True, type=Path)
    ap.add_argument('--tracks', nargs='+', choices=TRACKS,
                    help='Measured routes. Default is HighSpeedRing then Daytona. Mutually exclusive with --course-slots.')
    ap.add_argument('--course-slots', nargs='+', type=int,
                    help='Course Select ordinals 0..9. 0..2 are measured HighSpeedRing, Daytona and FujiSpeedwayF. '
                         '3..9 are experimental and unnamed. Omit --tracks.')
    ap.add_argument('--provenance', action='store_true',
                    help='Record RSX_PSO_PROVENANCE under this output and export a portable template. Off by default.')
    ap.add_argument('--decoder', type=Path,
                    help='Production decoder.dll. Required with --provenance so the session template can be exported.')
    ap.add_argument('--seconds', type=int, default=90, help='Sampling seconds after the grid (30..900)')
    ap.add_argument('--passes', type=int, default=1, help='Visits per route (1..4); more visits can catch late async draws')
    ap.add_argument('--resolution', choices=('720p', '1080p'), default='1080p')
    ap.add_argument('--msaa', choices=('1', '2'), default='2')
    ap.add_argument('--resume', action='store_true', help='Continue this output with matching engine/settings/fixture')
    ap.add_argument('--prepare-only', action='store_true', help='With --resume, rebuild every learned pipeline without driving')
    args = ap.parse_args()
    if not 30 <= args.seconds <= 900 or not 1 <= args.passes <= 4:
        ap.error('Use --seconds 30..900 and --passes 1..4')
    if args.prepare_only and not args.resume:
        ap.error('--prepare-only requires --resume')
    if args.provenance and args.decoder is None:
        ap.error('--provenance requires --decoder so the session can export a portable template')
    try:
        routes = resolve_routes(args.tracks, args.course_slots)
    except ValueError as exc:
        ap.error(str(exc))
    fixture, output, engine = isolated(args.fixture), isolated(args.output), args.engine.resolve()
    if fixture == output or fixture in output.parents or output in fixture.parents:
        ap.error('Output must be separate from the copied fixture')
    if len(str(output)) > 130:
        ap.error('Use an output path of at most 130 characters for native cache paths')
    isolated(engine.parent)
    for name in ('input/EMAIN.ELF', 'input/pkg/PARAM.SFO', 'gamedata', 'assets'):
        if not (fixture / name).exists():
            ap.error('Incomplete copied fixture: ' + name)
    # Reject junctions/symlinks in the supplied fixture: all game writes must
    # resolve within the copied audit fixture, including writable game data.
    for current, dirs, files in os.walk(fixture, followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            if path.is_symlink() or path.is_junction():
                ap.error('The supplied fixture must contain copies, not links: ' + str(path))
    idle()
    decoder = None
    if args.provenance:
        decoder = args.decoder.resolve()
        isolated(decoder.parent)
        if not decoder.is_file():
            ap.error('Decoder is missing')
    # Default config stays the historical track list. Slot and provenance keys
    # are added only for those explicit modes, so an older resume still matches.
    config = dict(engine_sha256=hashlib.sha256(engine.read_bytes()).hexdigest(),
                  fixture=str(fixture), elf_sha256=hashlib.sha256((fixture / 'input/EMAIN.ELF').read_bytes()).hexdigest(),
                  tracks=[route['label'] for route in routes], seconds=args.seconds, passes=args.passes,
                  resolution=args.resolution, msaa=args.msaa)
    if args.course_slots is not None:
        config['course_slots'] = [route['slot'] for route in routes]
    if args.provenance:
        config['provenance'] = dict(limit=PROVENANCE_LIMIT,
                                    decoder_sha256=hashlib.sha256(decoder.read_bytes()).hexdigest())
    report_path = output / 'report.json'
    if args.resume:
        report = json.loads(report_path.read_text())
        if report['config'] != config:
            ap.error('Resume engine/fixture/route/settings differ from the saved run')
    else:
        if output.exists():
            ap.error('Use a new output or --resume; no files were removed')
        output.mkdir(parents=True)
        limitations = ['Only the supported routes/current car and selected settings are visited.',
                       'No whole-game coverage or stutter-reduction guarantee.',
                       'Driver blobs are local to this hardware/driver; retain recipes and code.',
                       'Preparation finishes before play; do not bulk scan this cache during a benchmark.']
        if args.course_slots is not None:
            limitations.append('Course slots 0..2 are measured HighSpeedRing, Daytona and FujiSpeedwayF. '
                               'Slots 3..9 are an experimental ordinal bound from 10 distinct course_logo_S assets and have no names.')
        if args.provenance:
            limitations.append('Provenance recording is diagnostic I/O under this output. '
                               'The exported template contains recorded links only.')
        report = dict(schema=1, config=config, routes=[], status='initializing',
                      origin='Automatically learned real draw state and local bytecode, not independent asset reconstruction.',
                      limitations=limitations)
        save_report(report_path, report)
        game = output / 'game'
        game.mkdir()
        shutil.copytree(fixture / 'gamedata', game / 'gamedata')
        shutil.copytree(fixture / 'assets', game / 'assets')
        (game / 'input').mkdir()
        shutil.copy2(fixture / 'input/EMAIN.ELF', game / 'input/EMAIN.ELF')
        link_env = dict(os.environ, GT5P_TRAIN_LINK=str(game / 'input/pkg'), GT5P_TRAIN_TARGET=str(fixture / 'input/pkg'))
        subprocess.run(['powershell', '-NoProfile', '-Command',
                        'New-Item -ItemType Junction -Path $env:GT5P_TRAIN_LINK -Target $env:GT5P_TRAIN_TARGET | Out-Null'],
                       env=link_env, check=True)
    game, cache, logs = output / 'game', output / 'shadercache', output / 'logs'
    for path in (game / 'gamedata', game / 'assets', cache, logs):
        writable_tree(path, output)
    if (game / 'input/pkg').resolve() != (fixture / 'input/pkg').resolve():
        ap.error('Run disc junction no longer points to the copied fixture')
    cache.mkdir(exist_ok=True)
    logs.mkdir(exist_ok=True)
    prov = None
    if args.provenance:
        prov = provenance_directory(output)
        if prov.exists() and (prov.is_symlink() or prov.is_junction()):
            ap.error('Provenance directory must be a real directory inside this run')
        prov.mkdir(exist_ok=True)

    def save():
        save_report(report_path, report)

    try:
        if prov is not None:
            report['provenance_directory'] = str(prov)
            save()
        if not args.prepare_only:
            for number in range(1, args.passes + 1):
                for visit in routes:
                    tag = f"{number}-{visit['label']}" if visit['tag_kind'] == 'track' else f"{number}-slot{visit['slot']}"
                    if any(r['tag'] == tag and r['status'] == 'visited' for r in report['routes']):
                        continue
                    idle()
                    before = set(inventory(cache)['recipes'])
                    report['status'] = 'visiting ' + tag
                    save()
                    env = {k: v for k, v in os.environ.items() if not k.startswith(
                        ('GT5P_', 'RSX_', 'PS3_', 'PAD_', 'FP_', 'VP_', 'SPU_', 'PPU_', 'D3D12_', 'CULL_'))}
                    env.update(PS3_VERBOSE='0', GT5P_GAME_DIR='input/pkg/', PS3_VFS_ROOT=str(game),
                               PS3_GAMEDATA_ROOT=str(game / 'gamedata'), RSX_SHADER_CACHE=str(cache),
                               RSX_SHADER_WARMUP='1', RSX_SHADER_WARMUP_SCAN='0', RSX_SHADER_WARMUP_BACKGROUND='1',
                               RSX_PSO_ASYNC='1', RSX_SHADER_ASYNC='1', RSX_PSO_RECIPES='1',
                               RSX_PSO_RECIPE_KEEP_DAYS='0', RSX_RACE_PREWARM='1',
                               RSX_RACE_PREWARM_WAIT_MS='0', RSX_PSO_PROVENANCE='0' if prov is None else str(prov),
                               PAD_HOLD_MERGE='0', RSX_PRESENT_SYNC='1')
                    if prov is not None:
                        env['RSX_PSO_PROVENANCE_LIMIT'] = str(PROVENANCE_LIMIT)
                    cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(ROOT / 'scripts/test/race.ps1')]
                    if visit['tag_kind'] == 'slot':
                        cmd.extend(['-CourseSlot', str(visit['slot'])])
                    if visit['identity'] == 'measured':
                        cmd.extend(['-Track', visit['label']])
                    cmd.extend(['-Tag', tag, '-Seconds', str(args.seconds), '-SampleDelay', '0',
                                '-FrameTest', '-RaceShots', '30', '-Engine', str(engine), '-GameRoot', str(game),
                                '-OutputDirectory', str(logs), 'GT5P_RESOLUTION=' + args.resolution, 'RSX_MSAA=' + args.msaa])
                    if prov is not None:
                        cmd.extend(['RSX_PSO_PROVENANCE=' + str(prov), 'RSX_PSO_PROVENANCE_LIMIT=' + str(PROVENANCE_LIMIT)])
                    print('Automatically visiting', tag, flush=True)
                    with (logs / (tag + '.runner.log')).open('wb') as stream:
                        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
                        try:
                            if proc.wait(timeout=args.seconds + 480):
                                raise ValueError('Route failed; inspect ' + str(logs / (tag + '.runner.log')))
                        finally:
                            if proc.poll() is None:
                                # This exact child tree belongs to this invocation.
                                subprocess.run(['taskkill', '/PID', str(proc.pid), '/T', '/F'], capture_output=True)
                                proc.wait(timeout=15)
                    result = route_result(logs, tag)
                    after = inventory(cache)
                    if after['rejected']:
                        raise ValueError('Learned recipe dependencies are damaged; inspect the cache')
                    route = dict(tag=tag, status='visited', course_slot=visit['slot'],
                                 course_identity=visit['identity'],
                                 new_recipes=len(set(after['recipes']) - before),
                                 total_recipes=len(after['recipes']), **result)
                    report['routes'].append(route)
                    save()
                    print(f"{tag}: {route['new_recipes']} new / {route['total_recipes']} learned recipes", flush=True)
        export_error = None
        if args.provenance:
            try:
                visited = [item['tag'] for item in report['routes'] if item.get('status') == 'visited']
                if not visited:
                    raise ValueError('No visited route is available to export')
                incomplete = provenance_capture_state(logs, visited)
                destination = template_destination(output)
                exported = export_session(engine, decoder, fixture / 'input/EMAIN.ELF', prov, cache, destination)
                report['provenance_export'] = dict(trace=str(prov), template=str(destination), limit=PROVENANCE_LIMIT,
                                                   incomplete=incomplete, **exported)
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                export_error = exc
                report['provenance_export_error'] = str(exc)
            save()
        report['status'] = 'preparing'
        save()
        print('Preparing every learned native pipeline before play', flush=True)
        started = time.monotonic()
        report['preparation'] = prepare(engine, game, cache, output / 'prepare.log')
        report['preparation']['wall_seconds'] = time.monotonic() - started
        if export_error is not None:
            raise export_error
        if args.provenance and report.get('provenance_export', {}).get('incomplete'):
            raise ValueError('RSX_PSO_PROVENANCE reported an incomplete capture. The partial template and prepared cache were kept.')
        report['status'] = 'complete'
        report.pop('error', None)
        save()
        print('Completed:', report_path, flush=True)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        report.update(status='failed', error=str(exc))
        save()
        raise


if __name__ == '__main__':
    main()
