"""Explicit, default-off aggregate shader preparation profiling."""
import os


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_SHADER_PROFILE', '0')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_SHADER_PROFILE must be unset, 0, or 1')
    return value == '1'
