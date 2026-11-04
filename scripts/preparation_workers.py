"""Bounded offline compiler concurrency; never affects normal gameplay."""
import os

MAX_COMPILER_WORKERS = 12
AUTO_CAP = 10
# One vertex worker is a separate process (512 MiB commit cap; measured peak 59 MiB, so
# 256 MiB is a wide allowance). The default never asks for more workers than the RAM that is
# available (after a fixed 1 GiB reserve for the owner and the OS) can hold at that allowance.
MEMORY_PER_WORKER = 256 * 1024**2
MEMORY_RESERVE = 1024**3
_AUTO = [None]


def _available_memory():
    """Available physical bytes, or None when unknown (then only the CPU rule applies)."""
    if os.name != 'nt':
        return None
    try:
        import ctypes

        class Status(ctypes.Structure):
            _fields_ = [('length', ctypes.c_ulong), ('load', ctypes.c_ulong), ('total', ctypes.c_ulonglong),
                        ('available', ctypes.c_ulonglong), ('total_page', ctypes.c_ulonglong),
                        ('available_page', ctypes.c_ulonglong), ('total_virtual', ctypes.c_ulonglong),
                        ('available_virtual', ctypes.c_ulonglong), ('available_extended', ctypes.c_ulonglong)]
        status = Status(); status.length = ctypes.sizeof(status)
        if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            return None
        return int(status.available)
    except Exception:
        return None


def legacy_default(cpus=None):
    """Phases 209-213: four workers on CPUs with at least eight logical processors, otherwise two."""
    cpus = (os.cpu_count() or 1) if cpus is None else cpus
    return 4 if cpus >= 8 else 2


def auto_default(cpus=None, available=None):
    """Logical processors minus two (owner and the engine's submitting thread), 2..AUTO_CAP,
    reduced when available RAM could not hold that many separate vertex worker processes."""
    cpus = (os.cpu_count() or 1) if cpus is None else cpus
    count = max(2, min(AUTO_CAP, cpus - 2))
    memory = _available_memory() if available is None else available
    if memory is not None:
        count = min(count, max(2, (memory - MEMORY_RESERVE) // MEMORY_PER_WORKER))
    return int(count)


def compiler_workers(environ=None):
    """GT5P_PREPARE_COMPILER_WORKERS: unset/auto (CPU and RAM based), legacy (the 4-or-2 rule of
    Phases 209-213), or an explicit count 2..12."""
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_COMPILER_WORKERS', 'auto')
    if value == 'auto':
        # Resolved once per process: free RAM moves, and the fragment threads, vertex processes and
        # report of one preparation should agree. Explicit environ mappings (tests) are not cached.
        if environ is not None:
            return auto_default()
        if _AUTO[0] is None:
            _AUTO[0] = auto_default()
        return _AUTO[0]
    if value == 'legacy':
        return legacy_default()
    if not isinstance(value, str) or not value.isascii() or not value.isdigit() or not 2 <= int(value) <= MAX_COMPILER_WORKERS or str(int(value)) != value:
        raise ValueError('GT5P_PREPARE_COMPILER_WORKERS must be unset, auto, legacy, or 2..%d' % MAX_COMPILER_WORKERS)
    return int(value)
