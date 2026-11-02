"""Build existing runtime shader packs from verified local preparation bytes.

Only source-keyed DXBC dependencies of explicit default phase targets qualify.
The packs contain game-derived bytes and must never be shipped or committed.
Call stage only while holding the preparation lock, or on an idle private copy.
"""
import argparse
import hashlib
import json
from pathlib import Path
import stat
import struct
import time
import uuid

from pipeline_warmup_plan import read as read_plan, validate_preparation
from preparation_reuse import cache_root, expected_shaders, regular_read, shader_matches

MAGIC = b'GT5PSPK1'
VERSION = 1
MAX_BYTES = 64 * 1024**2  # Runtime default, per scope; never silently truncate.
MAX_ENTRIES = 12288       # Runtime's 3/4-full 16384-slot table.
MAX_SHADER = 4 * 1024**2
MAX_SECONDS = 60


def dependencies(plan, document, report):
    validate_preparation(plan, report)
    records = {r['key']: r for r in document['records']}
    if len(records) != len(document['records']):
        raise ValueError('Duplicate template pipeline key')
    expected = expected_shaders(document)  # Reject conflicting source mappings.
    phases = {}
    for phase, keys in plan['phases'].items():
        sources = set()
        for key in keys:
            if key not in records:
                raise ValueError('Phase target is absent from this template')
            sources.update(records[key][s] for s in ('vp_source', 'fp_source'))
        phases[phase] = sorted(sources)
        if (len(sources) > MAX_ENTRIES or
                sum(expected[s][1] for s in sources) > MAX_BYTES):
            raise ValueError('Shader pack exceeds the runtime default budget')
    return phases, expected


def _file_digest(path, limit, poll=None):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size > limit):
        raise ValueError('Existing shader pack must be bounded, regular and unlinked')
    checksum, size = hashlib.sha256(), 0
    with path.open('rb') as stream:
        while True:
            if poll:poll()
            data = stream.read(128 * 1024)
            if not data:
                break
            size += len(data)
            if size > limit:
                raise ValueError('Existing shader pack exceeds its bound')
            checksum.update(data)
    return size, checksum.hexdigest()


def stage(plan, document, report, cache, resume=False, progress=None, destination=None):
    """Preserve learned packs; resume only byte-identical generated packs."""
    started = time.perf_counter()
    cache = cache_root(cache)
    destination = cache_root(destination) if destination is not None else cache
    phases, expected = dependencies(plan, document, report)
    sources = sorted(set().union(*map(set, phases.values())))
    if sum(expected[s][1] for s in sources) > 2 * MAX_BYTES:
        raise ValueError('Combined shader pack budget exceeded')
    blobs = {}
    def poll(detail, completed=0, total=0):
        if time.perf_counter()-started > MAX_SECONDS:
            raise TimeoutError('Shader pack time budget exceeded; completed files preserved')
        if progress:
            counts = dict(detail=detail)
            if total:
                counts.update(completed=completed, total=total)
            progress('packing-shaders', counts)
    # Verify every dependency before creating either pack. Source identifiers
    # are not bytecode hashes: both the bytecode hash and length must match.
    for index, source in enumerate(sources, 1):
        poll('verifying', index, len(sources))
        code_id, length = expected[source]
        data = regular_read(cache/(source+'.dxbc'), MAX_SHADER)
        if not shader_matches(data, code_id, length):
            raise ValueError('Shader pack dependency failed verification: '+source)
        blobs[source] = data
    pending, rows = [], {}
    for phase, sources in phases.items():
        poll('checking '+phase)
        path = destination/(phase+'-shaders-v1.pack')
        checksum = hashlib.sha256()
        size = 0
        def chunks():
            yield MAGIC+struct.pack('<I', len(sources))
            for source in sources:
                data = blobs[source]
                yield struct.pack('<QI', int(source, 16), len(data))
                yield data
        for chunk in chunks():
            checksum.update(chunk)
            size += len(chunk)
        identity = (size, checksum.hexdigest())
        if path.exists() or path.is_symlink():
            if not resume or _file_digest(path, MAX_BYTES+MAX_ENTRIES*12+12, lambda:poll('checking '+phase)) != identity:
                raise ValueError('Refusing to replace an existing learned shader pack')
            written = False
        else:
            pending.append((path, sources))
            written = True
        rows[phase] = dict(shaders=len(sources), shader_bytes=sum(len(blobs[s]) for s in sources),
                           file_bytes=size, sha256=identity[1], written=written)
    # All existing destinations and both payloads pass before publication.
    publish = []
    try:
        for path, sources in pending:
            temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
            publish.append((temporary, path))
            with temporary.open('xb') as stream:
                stream.write(MAGIC+struct.pack('<I', len(sources)))
                for index, source in enumerate(sources, 1):
                    poll(path.stem, index, len(sources))
                    data = blobs[source]
                    stream.write(struct.pack('<QI', int(source, 16), len(data)))
                    stream.write(data)
        poll('publishing')
        for temporary, path in publish:
            temporary.replace(path)
    finally:
        # Only our unique incomplete temporary files; never remove a pack,
        # learned shader, recipe, driver blob or another attempt's artifact.
        for temporary, _ in publish:
            temporary.unlink(missing_ok=True)
    return dict(format=VERSION, phases=rows, unique_shaders=len(blobs),
                verified_shader_bytes=sum(map(len, blobs.values())),
                packs_written=len(pending), seconds=time.perf_counter()-started,
                limitation='Local bytecode lookup packs; not driver pipelines, new coverage, GPU residency or a stutter measurement.')


def main():
    from pipeline_template import read, template_digest
    from pipeline_runtime_coverage import MAX_REPORT
    from pipeline_warmup_plan import bounded
    from preparation_checkpoint import Checkpoint
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('template', 'plan', 'report', 'cache', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--resume', action='store_true')
    args = ap.parse_args()
    template = args.template.resolve()
    plan = read_plan(args.plan)
    if plan['template_sha256'] != template_digest(template):
        raise ValueError('Shader pack template does not match the phase plan')
    document = read(template)
    report = json.loads(bounded(args.report, MAX_REPORT))
    # A standalone operation may only publish to its own fresh output, using
    # read-only source cache files. The normal preparer uses stage under its lock.
    from train_pipeline_cache import isolated
    output = isolated(args.output)
    if output.exists() and not args.resume:
        raise ValueError('Choose a fresh isolated output, or resume its exact contract')
    contract = dict(shader_packs=VERSION, template=plan['template_sha256'],
        plan=hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest(),
        cache=str(cache_root(args.cache)))
    dependencies(plan, document, report)
    with Checkpoint(output, contract, args.resume) as checkpoint:
        cache = output/'shadercache'
        cache.mkdir(exist_ok=True)
        source_cache = cache_root(args.cache)
        if source_cache == cache or source_cache in cache.parents or cache in source_cache.parents:
            raise ValueError('Standalone output must differ from source cache')
        result = stage(plan, document, report, source_cache, args.resume, destination=cache)
        (output/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        checkpoint.stage('complete')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
