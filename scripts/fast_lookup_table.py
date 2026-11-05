"""Write the renderer's fast pipeline lookup table from a completed preparation (Phase 221).

The renderer (RSX_PSO_FAST_LOOKUP, main patch) maps a session-independent draw key to the native pipeline hash
so a first-in-process draw whose pipeline is already resident skips HLSL/DXBC rebuilding. It learns the table
during play; this module writes the same table ahead of play from what preparation already proved: every
prepared record's fragment program, vertex-shader bytecode hash ("vs"), translation state and native pipeline
key, for each translation mode the preparation made. The functions below mirror the backend exactly
(rsx_fp_structural_hash, fplk_key, fplk_epoch); scripts/test/fast_lookup_table.py pins them.

Nothing here changes prepared shaders, native blobs, recipes or the preparation token. A table entry is only a
hint: the renderer uses it when the named pipeline is resident, so a wrong or stale entry falls back to the
full path. GT5P_PREPARE_FAST_LOOKUP=0 skips writing.
"""
import os
from pathlib import Path
import struct

FNV = 1469598103934665603
PRIME = 1099511628211
MASK = (1 << 64) - 1
MAGIC = 0x324B4C5050355447          # "GT5PPLK2"
MAX_ENTRIES = (1 << 16) * 3 // 4     # renderer table capacity (FPLK_N 3/4)
FP_MAX_INLINE_CONSTANTS = 256
MODES = {'default': (0, 0), 'ultrawide-native': (2, 0), 'native-scaled': (0, 1)}
STATE_FIELDS = ('blend', 'nrt', 'rtfmt', 'exp32', 'cmask', 'cull', 'stencil', 'unnorm', 'cube', 'vmask',
                'samplers', 'ghi', 'shd', 'unhi')


def _fnv_bytes(data, h):
    for b in data:
        h = ((h ^ b) * PRIME) & MASK
    return h


def mix(h, v):
    for i in range(8):
        h = ((h ^ ((v >> (i * 8)) & 0xFF)) * PRIME) & MASK
    return h


def _fp_word(data, off):
    be = int.from_bytes(data[off:off + 4], 'big')
    return ((be << 16) | (be >> 16)) & 0xFFFFFFFF


def structural_hash(ucode):
    """rsx_fp_structural_hash(ucode, len, 0): instruction words only, inline constants skipped."""
    h = _fnv_bytes(struct.pack('<I', 0x31535046), 0)
    off = count = constants = 0
    n = len(ucode)
    while off + 16 <= n:
        w0, w1, w2, w3 = (_fp_word(ucode, off + 4 * i) for i in range(4))
        h = _fnv_bytes(ucode[off:off + 16], h)
        count += 1
        off += 16
        if any((w & 3) == 2 for w in (w1, w2, w3)):
            if off + 16 > n or constants >= FP_MAX_INLINE_CONSTANTS:
                return 0
            constants += 1
            off += 16
        if w0 & 1:
            h = _fnv_bytes(struct.pack('<I', count), h)
            return _fnv_bytes(struct.pack('<I', constants), h)
    return 0


def key(code_identity, vs_code, state):
    """fplk_key: fields as the in-memory key stores them (template state = the provenance copy of that key)."""
    s = state
    h = FNV
    h = mix(h, code_identity); h = mix(h, vs_code)
    h = mix(h, (s['blend'] << 32) | s['cmask']); h = mix(h, (s['nrt'] << 32) | s['rtfmt'])
    h = mix(h, (s['exp32'] << 32) | s['cull']); h = mix(h, (s['stencil'] << 32) | s['unnorm'])
    h = mix(h, (s['cube'] << 32) | s['vmask']); h = mix(h, int(s['samplers'], 16))
    h = mix(h, (s['ghi'] << 32) | s['shd']); h = mix(h, s['unhi'])
    return h or 1


def tag(engine, mode, high_precision=True, translation_env=None):
    """fplk_epoch for a game run of this engine in this translation mode (translation_env: RSX_FP_*-style
    variables the game will have set, i.e. shader_source_policy.overlay())."""
    st = os.stat(engine)
    filetime = st.st_mtime_ns // 100 + 116444736000000000
    uw, scaled = MODES[mode]
    h = _fnv_bytes(b'FPLK2', FNV)
    h = mix(h, st.st_size); h = mix(h, filetime)
    h = mix(h, uw); h = mix(h, scaled); h = mix(h, 1 if high_precision else 0)
    total = 0
    for name, value in (translation_env or {}).items():
        name = name.upper()
        if not (name.startswith(('RSX_FP_', 'RSX_VP_', 'FP_', 'VP_')) or name == 'RSX_VFETCH_LOOP'):
            continue
        total = (total + _fnv_bytes(f'{name}={value}'.encode('ascii'), FNV)) & MASK
    return mix(h, total)


def entries(records, fp_identities):
    """records: derived/resolved preparation records (fp sha256, vs, key, state). Returns {lookup key: native}."""
    out = {}
    for r in records:
        ident = fp_identities.get(r['fp']['sha256'])
        if not ident:
            continue
        k = key(int(ident, 16), int(r['vs'], 16), r['state'])
        out[k] = int(r['key'], 16)
    return out


def write(path, tag_value, table):
    path = Path(path)
    rows = list(table.items())[:MAX_ENTRIES]
    data = struct.pack('<QQQ', MAGIC, tag_value, len(rows)) + b''.join(struct.pack('<QQ', k, v) for k, v in rows)
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(data)
    tmp.replace(path)
    return len(rows)


def read(path):
    data = Path(path).read_bytes()
    magic, tag_value, count = struct.unpack_from('<QQQ', data)
    if magic != MAGIC or len(data) != 24 + 16 * count:
        raise ValueError('not a fast lookup table')
    return tag_value, dict(struct.unpack_from('<QQ', data, 24 + 16 * i) for i in range(count))


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_FAST_LOOKUP', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_FAST_LOOKUP must be unset, 0 or 1')
    return value == '1'


def write_for_preparation(output, engine, report, high_precision=True, translation_env=None):
    """Per translation mode in a completed preparation report: write warmup-v1/fp-lookup-v2-<tag>.bin into
    output/shadercache, merging with a table the game already learned there. Returns a small summary."""
    ids = report.get('fp_code_identity') or {}
    summary = {}
    if not enabled() or not ids:
        return dict(status='skipped', reason='disabled' if not enabled() else 'no fragment identities in report')
    warm = Path(output) / 'shadercache' / 'warmup-v1'
    warm.mkdir(parents=True, exist_ok=True)
    sets = {'default': report.get('derived_records') or []}
    extra = report.get('additional_translation')
    if isinstance(extra, dict) and extra.get('translation') in MODES and extra.get('resolved_records'):
        sets[extra['translation']] = extra['resolved_records']
    for mode, records in sets.items():
        if not records:
            continue
        t = tag(engine, mode, high_precision, translation_env)
        path = warm / f'fp-lookup-v2-{t:016x}.bin'
        table = entries(records, ids)
        if path.is_file():
            try:
                old_tag, learned = read(path)
                if old_tag == t:
                    learned.update(table)
                    table = learned
            except (OSError, ValueError, struct.error):
                pass
        summary[mode] = dict(tag=f'{t:016x}', entries=write(path, t, table), records=len(records))
    return dict(status='complete', modes=summary)
