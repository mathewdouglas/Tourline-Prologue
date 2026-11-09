"""One sequential file for the race prewarm.

The prewarm used to open a recipe, two bytecode files and a driver blob for
every pipeline. This writes ``warmup-v1/race-pack-v1.bin`` beside the race
index. The renderer reads that one file. ``RSX_RACE_PREWARM_PACK=0`` keeps the
old opens.

Little-endian layout, matching the reader in the main runtime patch:

* 40-byte header: magic ``u64``, version ``u32``, count ``u32``, code_count
  ``u32``, flags ``u32``, index_fnv ``u64``, payload_fnv ``u64``.
* ``count`` records of 32 bytes: hash ``u64``, recipe_off ``u32``, recipe_len
  ``u32``, vs_id ``u32``, ps_id ``u32``, blob_off ``u32``, blob_len ``u32``.
* ``code_count`` records of 16 bytes: hash ``u64``, off ``u32``, len ``u32``.
* Payload. Offsets are from the first payload byte. Each recipe, shader and
  driver blob starts 16-byte aligned; the pad bytes are part of the payload.

``index_fnv`` is the renderer FNV-1a over the little-endian hash list, in index
order. ``payload_fnv`` is the same function over the payload. A stored driver
blob is the raw cached PSO, without its 24-byte file header. A missing recipe
or shader is a zero length, so one bad file does not drop the rest of the index.
"""
import struct
from pathlib import Path

from cache_hash import python_fnv64

MAGIC = 0x314B434150355447  # 'GT5PACK1' little-endian
VERSION = 1
BLOB_MAGIC = 0x31534F5035505447
HEADER = struct.Struct('<QIIIIQQ')
RECIPE = struct.Struct('<QIIIIII')
CODE = struct.Struct('<QII')
NO_CODE = 0xFFFFFFFF


def index_hashes(path):
    hashes = []
    text = Path(path).read_text(encoding='ascii', errors='replace')
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        hashes.append(int(line, 16))
    return hashes


def _fnv_hashes(hashes):
    return python_fnv64(b''.join(struct.pack('<Q', h) for h in hashes))


def _read_blob(cache, hash_):
    path = cache / f'pso_{hash_:016x}.bin'
    try:
        data = path.read_bytes()
    except OSError:
        return b''
    if len(data) < 24:
        return b''
    magic, size, checksum = struct.unpack_from('<QQQ', data, 0)
    blob = data[24:]
    if magic != BLOB_MAGIC or size != len(blob) or python_fnv64(blob) != checksum:
        return b''
    return blob


def build(warmup, index_name='race-v1.txt', dest=None):
    """Write the pack for one index. ``warmup`` is ``shadercache/warmup-v1``.

    Driver blobs are read from the shader cache above that directory. ``dest``
    defaults to a file next to the index. Returns a small report.
    """
    warmup = Path(warmup)
    cache = warmup.parent
    index = warmup / index_name
    hashes = index_hashes(index)
    if dest is None:
        dest = warmup / ('race-pack-v1.bin' if index_name.startswith('race') else 'menu-pack-v1.bin')
    dest = Path(dest)
    codes = {}
    code_bytes = []
    payload = bytearray()
    records = []

    def align():
        pad = (-len(payload)) & 15
        if pad:
            payload.extend(b'\0' * pad)

    def add_code(hash_, raw):
        if hash_ in codes:
            return codes[hash_]
        if python_fnv64(raw) != hash_:
            return NO_CODE
        align()
        codes[hash_] = len(code_bytes)
        code_bytes.append((hash_, len(payload), len(raw)))
        payload.extend(raw)
        return codes[hash_]

    for hash_ in hashes:
        recipe_path = warmup / f'pso_{hash_:016x}.recipe'
        try:
            recipe = recipe_path.read_bytes()
        except OSError:
            recipe = b''
        vs_id = ps_id = NO_CODE
        # Prologue is magic, version, size. Then hash, vs_hash, ps_hash, vs_bytes, ps_bytes.
        if len(recipe) >= 48:
            _pipe, vs_hash, ps_hash, vs_len, ps_len = struct.unpack_from('<QQQII', recipe, 16)
            try:
                vs = (warmup / f'code_{vs_hash:016x}.dxbc').read_bytes()
            except OSError:
                vs = b''
            try:
                ps = (warmup / f'code_{ps_hash:016x}.dxbc').read_bytes()
            except OSError:
                ps = b''
            if len(vs) == vs_len:
                vs_id = add_code(vs_hash, vs)
            if len(ps) == ps_len:
                ps_id = add_code(ps_hash, ps)
        if recipe:
            align()
        recipe_off = len(payload)
        payload.extend(recipe)
        blob = _read_blob(cache, hash_)
        if blob:
            align()
        blob_off = len(payload)
        payload.extend(blob)
        records.append((hash_, recipe_off, len(recipe), vs_id, ps_id, blob_off, len(blob)))

    payload_fnv = python_fnv64(payload)
    header = HEADER.pack(MAGIC, VERSION, len(hashes), len(code_bytes), 0,
                          _fnv_hashes(hashes), payload_fnv)
    body = bytearray(header)
    for rec in records:
        body.extend(RECIPE.pack(*rec))
    for hash_, off, length in code_bytes:
        body.extend(CODE.pack(hash_, off, length))
    body.extend(payload)
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + '.tmp')
    tmp.write_bytes(body)
    tmp.replace(dest)
    return dict(status='written', path=str(dest), recipes=len(hashes), codes=len(code_bytes),
                bytes=len(body), blobs=sum(1 for rec in records if rec[6]))


def parse(path):
    """Return header fields and the payload view. Raises ValueError when the file is not a pack."""
    data = Path(path).read_bytes()
    if len(data) < HEADER.size:
        raise ValueError('pack is shorter than its header')
    magic, version, count, code_count, flags, index_fnv, payload_fnv = HEADER.unpack_from(data, 0)
    if magic != MAGIC or version != VERSION:
        raise ValueError('pack magic or version does not match')
    tables = HEADER.size + count * RECIPE.size + code_count * CODE.size
    if tables > len(data):
        raise ValueError('pack tables run past the file')
    payload = data[tables:]
    if python_fnv64(payload) != payload_fnv:
        raise ValueError('pack payload checksum does not match')
    records = [RECIPE.unpack_from(data, HEADER.size + i * RECIPE.size) for i in range(count)]
    codes = [CODE.unpack_from(data, HEADER.size + count * RECIPE.size + i * CODE.size) for i in range(code_count)]
    listed = _fnv_hashes([rec[0] for rec in records])
    if listed != index_fnv:
        raise ValueError('pack index checksum does not match its records')
    return dict(count=count, code_count=code_count, flags=flags, index_fnv=index_fnv,
                payload_fnv=payload_fnv, records=records, codes=codes, payload=payload, bytes=len(data))
