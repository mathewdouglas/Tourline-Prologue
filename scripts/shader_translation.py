"""Explicit offline translation environments. No resolution guessing.

The production vertex translator latches RSX_ULTRAWIDE on first use and emits
its edge epilogue whenever that latched value is nonzero. Fragment rs_on() is
true only for RSX_ULTRAWIDE==2 or an active RSX_RENDER_HEIGHT, and the WPOS
rewrite runs only for a qualifying b1 program. A mode is therefore one fresh
process with one fixed environment, never a value inferred from a desktop mode.

default: RSX_ULTRAWIDE=0 and no RSX_RENDER_HEIGHT.
ultrawide-native: RSX_ULTRAWIDE=2 and no RSX_RENDER_HEIGHT.
native-scaled: RSX_ULTRAWIDE=0 and RSX_RENDER_HEIGHT=1440.
"""
import os


# Same renderer families offline_env strips, plus PS3_HEADLESS. Matching is
# case-insensitive: Windows getenv treats rsx_ultrawide and RSX_ULTRAWIDE as one.
PREFIXES = ('FP_', 'VP_', 'RSX_', 'GT5P_', 'PAD_', 'PPU_', 'SPU_', 'D3D12_', 'CULL_')
MODES = ('default', 'ultrawide-native', 'native-scaled')
_FIELDS = {
    'default': (('RSX_ULTRAWIDE', '0'),),
    'ultrawide-native': (('RSX_ULTRAWIDE', '2'),),
    'native-scaled': (('RSX_ULTRAWIDE', '0'), ('RSX_RENDER_HEIGHT', '1440')),
}
_TRANSLATION_KEYS = ('RSX_ULTRAWIDE', 'RSX_RENDER_HEIGHT')


def _mode(mode):
    if mode not in _FIELDS:
        raise ValueError('Unsupported shader translation mode')
    return mode


def _dropped(key):
    folded = key.upper()
    return folded == 'PS3_HEADLESS' or folded.startswith(PREFIXES)


def overlay(mode):
    """Fixed bounded dict. Callers apply it after offline_env, not instead of it."""
    return dict(_FIELDS[_mode(mode)])


def apply(env, mode):
    """Install one mode. Drops any previous ultrawide/height key, then sets the fixed fields."""
    spec = overlay(mode)
    for key in [key for key in env if key.upper() in _TRANSLATION_KEYS]:
        del env[key]
    env.update(spec)
    return env


def environment(mode, base=None):
    """Sanitized process environment: non-renderer owner variables plus one explicit mode."""
    source = os.environ if base is None else base
    env = {}
    for key, value in source.items():
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError('Shader translation environment must be text')
        if _dropped(key):
            continue
        env[key] = value
    # Phase 231: the vertex workers compile with this process's compiler (and its DLL), never a default of their own.
    import shader_compiler
    env['RSX_SHADER_COMPILER'] = shader_compiler.mode(source)
    env['GT5P_PREPARE_DXC_LIBRARY'] = str(shader_compiler.library(source).resolve())
    return apply(env, mode)
