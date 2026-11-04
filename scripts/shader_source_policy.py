"""Rollback switches for the renderer's cheaper-to-compile shader text (Phase 215).

The renderer emits the cheaper text by default. Offline preparation strips every inherited RSX_* variable so a
cache always matches the default game; these two helper switches are the only way to prepare for a game run
with a rollback setting, and they must then be set for that game run as well (a cache prepared with one text
does not serve the other, because the text is the cache key):

  GT5P_PREPARE_VFETCH_LOOP   unset = renderer default; 0, 1 or 2 -> RSX_VFETCH_LOOP (0 = original unrolled
                             GPU vertex fetch)
  GT5P_PREPARE_FP_REG_SIZE   unset or 1 = renderer default; 0 -> RSX_FP_REG_SIZE=0 (48-entry fragment
                             register files)
  GT5P_PREPARE_FP_GAMMA_LAZY unset or 1 = renderer default; 0 -> RSX_FP_GAMMA_LAZY=0 (the sRGB helper
                             functions are added to every program that has a gamma bit, called or not)
"""
import os


def _setting(environ, name, allowed):
    value = (os.environ if environ is None else environ).get(name)
    if value is None:
        return ''
    if value not in allowed:
        raise ValueError(f'{name} must be unset or one of: {", ".join(allowed)}')
    return value


def vfetch_loop(environ=None):
    """'' (renderer default) or '0'/'1'/'2' for RSX_VFETCH_LOOP."""
    return _setting(environ, 'GT5P_PREPARE_VFETCH_LOOP', ('0', '1', '2'))


def fp_reg_size(environ=None):
    """'' (renderer default) or '0' for RSX_FP_REG_SIZE."""
    value = _setting(environ, 'GT5P_PREPARE_FP_REG_SIZE', ('0', '1'))
    return '0' if value == '0' else ''


def fp_gamma_lazy(environ=None):
    """'' (renderer default) or '0' for RSX_FP_GAMMA_LAZY."""
    value = _setting(environ, 'GT5P_PREPARE_FP_GAMMA_LAZY', ('0', '1'))
    return '0' if value == '0' else ''


def overlay(environ=None):
    """RSX_* variables to add to an offline environment; empty for the renderer defaults."""
    fields = {}
    loop = vfetch_loop(environ)
    if loop:
        fields['RSX_VFETCH_LOOP'] = loop
    if fp_reg_size(environ) == '0':
        fields['RSX_FP_REG_SIZE'] = '0'
    if fp_gamma_lazy(environ) == '0':
        fields['RSX_FP_GAMMA_LAZY'] = '0'
    return fields


def marker(environ=None):
    """Identity text for the generation token; empty for the renderer defaults (token unchanged)."""
    fields = overlay(environ)
    return ''.join(f'{key}={fields[key]};' for key in sorted(fields))
