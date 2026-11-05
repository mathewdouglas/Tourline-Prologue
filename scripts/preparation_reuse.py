"""Read-only, bounded cache hints for a different preparation generation.

Only shader bytes named and verified by the new template are reusable. Driver
blobs are hints: the ordinary native constructor must still validate every PSO.
No recipes, membership indices, packs or source checkpoint state are imported.

An opted-in seed_cache call can also return the shader bytes it has just
checked and copied. That object lives only for the locked preparation pass
that holds the destination. It is not a manifest, and destination files that
were already present are never members of it.
"""
import os
from collections.abc import Mapping
from pathlib import Path
import stat
import struct
import time
from preparation_io import read_pool, worker_count

from shader_coverage import bounded_read, fnv64

MAX_SHADERS = 128 * 1024**2
MAX_BLOBS = 256 * 1024**2
MAX_SECONDS = 60


def handoff_enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_REUSE_HANDOFF', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_REUSE_HANDOFF must be unset, 0, or 1')
    return value == '1'


def expected_shaders(document):
    """Local resolved outputs (or legacy expectations), never format-3 inputs.

    Format 3 first derives its output mapping with the current engine/decoder.
    An earlier format-3 generation can supply engine-matched, input-keyed local
    derivations; a format-2 generation supplies driver hints after derivation.
    """
    expected = {}
    for record in document['records']:
        if any(k not in record for k in ('vp_source','fp_source','vs','ps')):
            raise ValueError('Shader reuse requires locally derived outputs, not portable input identities')
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


_HANDOFF_SEAL = object()


class VerifiedShaders(Mapping):
    """Source-key bytes copied by one successful seed_cache call.

    seed_cache is the only constructor. Members are template source ids, not
    filenames. Driver blobs, rejected inputs and files already in the
    destination are absent. Do not serialize this object or reuse it after
    the destination lock is released.
    """

    __slots__ = ('_bytes', '_identity', '_stamps')

    def __init__(self, seal, records):
        if seal is not _HANDOFF_SEAL:
            raise TypeError('Verified shader handoff must come from seed_cache')
        blob = {}
        identity = {}
        stamps = {}
        for key, code_id, data, stamp in records:
            if type(key) is not str or type(code_id) is not str or type(data) is not bytes:
                raise TypeError('Verified shader handoff contains an invalid record')
            if key in blob:
                raise ValueError('Template source/bytecode mapping conflicts')
            blob[key] = data
            identity[key] = (code_id, len(data))
            stamps[key] = stamp
        self._bytes = blob
        self._identity = identity
        self._stamps = stamps

    def __getitem__(self, key):
        return self._bytes[key]

    def __iter__(self):
        return iter(self._bytes)

    def __len__(self):
        return len(self._bytes)

    def same_identity(self, key, code_id, length):
        """True when this entry was published for this exact template identity."""
        return self._identity.get(key) == (code_id, length)

    def unchanged(self, key, path):
        return self._stamps.get(key) == destination_stamp(path, len(self[key]))

    def __repr__(self):
        return f'VerifiedShaders({len(self)} shaders, {sum(len(item) for item in self._bytes.values())} bytes)'


def destination_stamp(path, size):
    """File identity/change stamp for immediate reuse under the output lock."""
    try:
        info = path.lstat()
    except OSError:
        return None
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or
            getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size != size):
        return None
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def destination_holds_copy(path, size):
    return destination_stamp(path, size) is not None


def seed_cache(document, source, destination, progress=None, *, handoff=False):
    """Copy verified shader and driver hints into a separate locked cache.

    The return is the report dict unless handoff is true. Then the return is
    (report, VerifiedShaders). The report schema does not change either way
    and stays JSON-serializable; shader bytes are never one of its fields.

    The handoff contains only shader files this call validated and replaced
    onto a destination name that did not already exist, and only when the
    file still has the written size and a single regular link afterward.
    Publication happens after the call completes. Cancellation, a write
    error, or any other exception publishes nothing: complete destination
    files remain on disk for a later locked pass to hash from scratch.
    Already-present, missing, rejected and budget-skipped shaders are omitted.
    Driver blobs are omitted. Call shaders_for_locked_pass with the same
    document before any later writer replaces those destination names.
    """
    if type(handoff) is not bool:
        raise TypeError('handoff must be a bool')
    collected = {} if handoff else None
    try:
        report = _seed_cache(document, source, destination, progress, collected)
    except BaseException:
        if collected is not None:
            collected.clear()
        raise
    if not handoff:
        return report
    published = [(key, code_id, data, stamp) for key, (code_id, data, stamp) in collected.items()]
    return report, VerifiedShaders(_HANDOFF_SEAL, published)


def _seed_cache(document, source, destination, progress, collected):
    source, destination = cache_root(source), cache_root(destination)
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Reuse source and destination caches must be separate')
    started = time.monotonic()
    report = dict(source=str(source), shaders_copied=0, shader_bytes=0,
                  driver_blobs_copied=0, driver_blob_bytes=0, rejected_shaders=0,
                  rejected_driver_blobs=0, missing_shaders=0, missing_driver_blobs=0,
                  budget_skipped=0, already_present=0, seconds=0)
    shaders = expected_shaders(document)
    requests = [(key, key + '.dxbc', 'shader', value) for key, value in sorted(shaders.items())]
    requests += [(None, f'pso_{key}.bin', 'driver_blob', None)
                 for key in sorted({record['key'] for record in document['records']})]
    report['io_workers']=worker_count()
    def read_request(request):
        storage_key,name,kind,expected=request
        if time.monotonic()-started>MAX_SECONDS:return request,'budget',None
        if (destination/name).exists():return request,'present',None
        try:
            data=regular_read(source/name,(4 if kind=='shader' else 32)*1024**2)
        except FileNotFoundError:return request,'missing',None
        except (OSError,ValueError):return request,'rejected',None
        valid=shader_matches(data,*expected) if expected else driver_blob_valid(data)
        return request,'valid' if valid else 'rejected',data if valid else None
    with read_pool(read_request,requests,report['io_workers']) as results:
        for number, ((storage_key, name, kind, expected), status, data) in enumerate(results):
            if progress:
                progress('reusing-cache', dict(completed=number, total=len(requests)))
            if time.monotonic() - started > MAX_SECONDS:
                report['budget_skipped'] += len(requests) - number
                break
            target = destination / name
            if status=='present':
                report['already_present'] += 1
                continue
            if status=='missing':
                report['missing_' + ('shaders' if kind == 'shader' else 'driver_blobs')] += 1
                continue
            if status=='rejected':
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
            if collected is not None and expected is not None:
                code_id, length = expected
                if storage_key in collected:
                    raise ValueError('Template source/bytecode mapping conflicts')
                if len(data) == length:
                    stamp = destination_stamp(target, length)
                    if stamp is not None:
                        collected[storage_key] = (code_id, data, stamp)
    report['seconds'] = time.monotonic() - started
    return report


def shaders_for_locked_pass(document, destination, verified_shaders):
    """Bytes for the locked pass that just received this handoff.

    Published entries skip a destination read only while they still name the
    same template identity and the destination identity/change stamp is unchanged.
    Every other expected shader that exists, including files seed_cache
    counted as already present, is read and hashed. A shape mismatch, a
    changed template identity, or a sealed entry that no longer matches the
    file falls back to that same disk check instead of using the memory copy.
    Missing files are omitted. The combined size stays within MAX_SHADERS.
    This transient optimization assumes ownership of the destination lock, not
    protection against another process deliberately forging file metadata.
    """
    if type(verified_shaders) is not VerifiedShaders:
        raise TypeError('verified_shaders must be the sealed handoff from seed_cache')
    destination = Path(destination)
    expected = expected_shaders(document)
    outside = [key for key in verified_shaders if key not in expected]
    if outside:
        raise ValueError('Verified shader handoff is outside the template: ' + outside[0])
    found = {}
    total = 0
    for key, (code_id, length) in expected.items():
        path = destination / (key + '.dxbc')
        published = verified_shaders[key] if key in verified_shaders else None
        if (published is not None and
                verified_shaders.same_identity(key, code_id, length) and
                verified_shaders.unchanged(key, path)):
            total += len(published)
            if total > MAX_SHADERS:
                raise ValueError('Resume shader memory budget exceeded')
            found[key] = published
            continue
        if not path.exists():
            continue
        data = regular_read(path, 4 * 1024**2)
        if not shader_matches(data, code_id, length):
            raise ValueError('Cached shader failed resume verification; cache preserved: ' + key)
        total += len(data)
        if total > MAX_SHADERS:
            raise ValueError('Resume shader memory budget exceeded')
        found[key] = data
    return found
