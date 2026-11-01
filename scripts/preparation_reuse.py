"""Read-only, bounded cache hints for a different preparation generation.

Only shader bytes named and verified by the new template are reusable. Driver
blobs are hints: the ordinary native constructor must still validate every PSO.
No recipes, membership indices, packs or source checkpoint state are imported.
"""
import os
from pathlib import Path
import stat
import struct
import time

from shader_coverage import bounded_read, fnv64

MAX_SHADERS = 128 * 1024**2
MAX_BLOBS = 256 * 1024**2
MAX_SECONDS = 60


def expected_shaders(document):
    expected = {}
    for record in document['records']:
        for source, code, index in (('vp_source', 'vs', 4), ('fp_source', 'ps', 8)):
            words = record['native']['words']
            value = (record[code], words[index] | (words[index + 1] << 32))
            if record[source] in expected and expected[record[source]] != value:
                raise ValueError('Template source/bytecode mapping conflicts')
            expected[record[source]] = value
    return expected


def shader_matches(data, code_id, length):
    return data.startswith(b'DXBC') and len(data) == length and f'{fnv64(data):016x}' == code_id


def cache_root(path):
    path = Path(os.path.abspath(path))
    for item in (path, *path.parents):
        if item.is_symlink() or getattr(item.lstat(), 'st_file_attributes', 0) & 0x400:
            raise ValueError('Reuse cache must not be redirected')
    if not path.is_dir():
        raise ValueError('Reuse cache directory is missing')
    return path


def regular_read(path, limit):
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink > 1 or
            getattr(info, 'st_file_attributes', 0) & 0x400):
        raise ValueError('Reuse input must be a regular unlinked file')
    return bounded_read(path, limit)


def driver_blob_valid(data):
    if len(data) <= 24:
        return False
    magic, size, checksum = struct.unpack_from('<QQQ', data)
    return (magic == 0x31534f5035505447 and size == len(data) - 24 and
            fnv64(data[24:]) == checksum)


def seed_cache(document, source, destination, progress=None):
    source, destination = cache_root(source), cache_root(destination)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Reuse source and destination caches must be separate')
    started = time.monotonic()
    report = dict(source=str(source), shaders_copied=0, shader_bytes=0,
                  driver_blobs_copied=0, driver_blob_bytes=0, rejected_shaders=0,
                  rejected_driver_blobs=0, missing_shaders=0, missing_driver_blobs=0,
                  budget_skipped=0, already_present=0, seconds=0)
    shaders = expected_shaders(document)
    requests = [(key + '.dxbc', 'shader', value) for key, value in sorted(shaders.items())]
    requests += [(f'pso_{key}.bin', 'driver_blob', None)
                 for key in sorted({r['key'] for r in document['records']})]
    for number, (name, kind, expected) in enumerate(requests):
        if progress:
            progress('reusing-cache', dict(completed=number, total=len(requests)))
        if time.monotonic() - started > MAX_SECONDS:
            report['budget_skipped'] += len(requests) - number
            break
        target = destination / name
        if target.exists():
            report['already_present'] += 1
            continue
        try:
            data = regular_read(source / name, (4 if kind == 'shader' else 32) * 1024**2)
        except FileNotFoundError:
            report['missing_' + ('shaders' if kind == 'shader' else 'driver_blobs')] += 1
            continue
        except (OSError, ValueError):
            report['rejected_' + ('shaders' if kind == 'shader' else 'driver_blobs')] += 1
            continue
        valid = shader_matches(data, *expected) if expected else driver_blob_valid(data)
        if not valid:
            report['rejected_' + ('shaders' if kind == 'shader' else 'driver_blobs')] += 1
            continue
        byte_field = kind + '_bytes'
        if report[byte_field] + len(data) > (MAX_SHADERS if expected else MAX_BLOBS):
            report['budget_skipped'] += 1
            continue
        # The destination is protected by the caller's preparation lock. Keep
        # complete files across cancellation; never write into the source cache.
        pending = target.with_suffix(target.suffix + '.reuse.tmp')
        pending.write_bytes(data)
        pending.replace(target)
        report['shaders_copied' if expected else 'driver_blobs_copied'] += 1
        report[byte_field] += len(data)
    report['seconds'] = time.monotonic() - started
    return report
