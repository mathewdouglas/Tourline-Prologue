"""Bounded offline compiler concurrency; never affects normal gameplay."""
import os


def compiler_workers(environ=None):
    # Leave room for the owner and OS on small CPUs; never grow past four.
    default = '4' if (os.cpu_count() or 1) >= 8 else '2'
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_COMPILER_WORKERS', default)
    if value not in ('2', '3', '4'):
        raise ValueError('GT5P_PREPARE_COMPILER_WORKERS must be unset, 2, 3, or 4')
    return int(value)
