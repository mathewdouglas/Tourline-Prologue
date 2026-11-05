"""Shader-interpreter pipeline classes derived from the verified starter's numeric state (Phase 220).

An interpreter pipeline pairs the generic fragment interpreter with the generic
vertex interpreter, so its identity is native output state only: input layout
(GPU fetch or the attribute mask), target count/format, blend, write mask,
cull, stencil/depth, and whether the target is multisampled. No program bytes,
shader keys, material state or game data are read or written here.

`base_classes` reduces starter records to the settings-independent class rows
the private engine embeds (`rsx_interp_classes`). `map_settings` is the mirror
of the engine's `interp_class_map` (patches/ps3recomp-shader-interp.patch):
every multisampled target uses the configured RSX_MSAA sample count, 8-bit
guest colour targets are R16G16B16A16_UNORM only with RSX_HIGH_PRECISION, and
the fragment interpreter uses its per-sample variant when RSX_SSAA is on and
the target is multisampled. Each class yields one pipeline per fragment input
variant (common/full). The shader translation modes (ultrawide-native,
native-scaled) change specialized shader text only and do not enter these
pipelines.
"""
import hashlib
import json
from pathlib import Path

MAX_CLASSES = 512                   # engine INTERP_PREP_MAX (1024) / two fragment input variants
FORMATS = {28: 'R8G8B8A8_UNORM', 11: 'R16G16B16A16_UNORM', 10: 'R16G16B16A16_FLOAT',
           2: 'R32G32B32A32_FLOAT', 41: 'R32_FLOAT'}
FIELDS = ('gpu', 'vmask', 'nrt', 'fmt', 'blend', 'cmask', 'cull', 'stencil', 'cube')
U32 = 0xFFFFFFFF


def _u32(value, name):
    if type(value) is not int or not 0 <= value <= U32:
        raise ValueError(f'interpreter class field {name} is not a 32-bit unsigned integer')
    return value


def base_classes(records):
    """Sorted, de-duplicated settings-independent class rows. Raises on malformed or excessive input."""
    if not isinstance(records, list) or not records:
        raise ValueError('no starter records')
    classes = set()
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('state'), dict):
            raise ValueError('malformed starter record')
        state, gpu = record['state'], record.get('vp_gpu')
        if gpu not in (0, 1) or type(gpu) is not int:
            raise ValueError('starter vp_gpu must be 0 or 1')
        vmask = _u32(state.get('vmask'), 'vmask')
        nrt, fmt = _u32(state.get('nrt'), 'nrt'), _u32(state.get('rtfmt'), 'rtfmt')
        cube = _u32(state.get('cube'), 'cube')
        if vmask > 0xFFFF or not 1 <= nrt <= 4 or fmt not in FORMATS:
            raise ValueError('starter class outside the interpreter bounds')
        samples = (cube >> 16) & 0xF
        if samples not in (0, 2, 4, 8):
            raise ValueError('starter sample count outside 1/2/4/8')
        classes.add((gpu, 0 if gpu else vmask, nrt, fmt,
                     *(_u32(state.get(k), k) for k in ('blend', 'cmask', 'cull', 'stencil')),
                     cube & 0xF0000))
        if len(classes) > MAX_CLASSES:
            raise ValueError(f'more than {MAX_CLASSES} interpreter classes')
    return sorted(classes)


def map_settings(classes, msaa=2, high_precision=True, sample_rate=True):
    """Distinct pipeline keys the engine prepares for these settings, in engine queue order."""
    if msaa not in (1, 2, 4, 8):
        raise ValueError('msaa must be 1, 2, 4 or 8')
    if type(high_precision) is not bool or type(sample_rate) is not bool:
        raise ValueError('high_precision/sample_rate must be booleans')
    seen, keys = set(), []
    for row in classes:
        if len(row) != len(FIELDS):
            raise ValueError('malformed class row')
        gpu, vmask, nrt, fmt, blend, cmask, cull, stencil, cube = row
        if gpu not in (0, 1) or not 1 <= nrt <= 4 or fmt not in FORMATS or cube & ~0xF0000 or vmask > 0xFFFF:
            raise ValueError('class row outside the interpreter bounds')
        raw = (cube >> 16) & 0xF
        samples = msaa if raw > 1 and msaa > 1 else 1
        fmt = 28 if fmt == 11 and not high_precision else fmt
        layout = 0 if gpu else (vmask or 0xFFFF)
        for full in (0, 1):
            key = (gpu, layout, nrt, fmt, blend, cmask, cull, stencil, samples, full,
                   int(sample_rate and samples > 1))
            if key not in seen:
                seen.add(key)
                keys.append(key)
    return keys


def load_template(folder):
    """Records of a metadata-only template folder (part-*.json shards)."""
    folder = Path(folder)
    if folder.is_symlink() or not folder.is_dir():
        raise ValueError('template folder missing or redirected')
    records = []
    for part in sorted(folder.glob('part-*.json')):
        if part.is_symlink() or part.stat().st_size > 64 * 1024 * 1024:
            raise ValueError('template shard redirected or too large')
        records += json.loads(part.read_text(encoding='utf-8'))['records']
    return records


def digest(classes):
    return hashlib.sha256(json.dumps(classes, separators=(',', ':')).encode('ascii')).hexdigest()


def render_c(classes):
    """The embedded table (private build output; numeric state only)."""
    lines = ['static const struct { u32 gpu, vmask, nrt, fmt, blend, cmask, cull, stencil, cube; } rsx_interp_classes[] = {']
    lines += ['    {' + ','.join(f'{v}u' for v in row) + '},' for row in classes]
    lines.append('};')
    return lines


def player_settings(storage):
    """(msaa, high_precision, anisotropy) as the game would read them from the launcher settings, or None.

    Conservative: an unreadable/invalid file returns None and the caller skips the stage (the game's startup
    step still prepares for the actual settings). A missing file is the launcher's first-run preset (2x).
    """
    import tomllib
    path = Path(storage) / 'gt5p_settings.toml'
    try:
        if path.is_symlink() or path.stat().st_size > 64 * 1024:
            return None
        document = tomllib.loads(path.read_text(encoding='utf-8-sig'))
    except FileNotFoundError:
        return 2, True, 16
    except (OSError, UnicodeError, tomllib.TOMLDecodeError):
        return None
    video, game = document.get('video', {}), document.get('game', {})
    if not isinstance(video, dict) or not isinstance(game, dict):
        return None
    msaa, hp, aniso = video.get('msaa', 4), game.get('smooth_colour', True), game.get('anisotropy', 16)
    if type(msaa) is not int or type(hp) is not bool or type(aniso) is not int:
        return None
    # Same normalisation as gt5p_settings.cpp / rsx_msaa_samples().
    msaa = msaa if msaa in (2, 4, 8) else (1 if msaa <= 1 else 4)
    if aniso not in (1, 4, 8, 16):
        aniso = 16
    return msaa, hp, aniso


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--template', type=Path, default=Path(__file__).resolve().parents[1] / 'assets/pipeline-templates/gt5p-disc-v2')
    ap.add_argument('--msaa', type=int, default=2)
    ap.add_argument('--no-high-precision', action='store_true')
    ap.add_argument('--no-sample-rate', action='store_true')
    a = ap.parse_args()
    rows = base_classes(load_template(a.template))
    keys = map_settings(rows, a.msaa, not a.no_high_precision, not a.no_sample_rate)
    print(json.dumps(dict(classes=len(rows), pipelines=len(keys), classes_sha256=digest(rows))))
