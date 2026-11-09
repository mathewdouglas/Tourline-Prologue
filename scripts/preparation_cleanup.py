"""Opt-in removal of older completed preparations, after a new selection succeeds.

Called by the launcher with its storage lease held and no game running. Ordinary
shadercache, saves, incomplete work and the selected generation are never targets.
"""
import ctypes
from contextlib import ExitStack, contextmanager
import json
import os
from pathlib import Path
import re
import shutil

from preparation_checkpoint import generation_entry_budget, preflight_tree
from preparation_reuse import cache_root, regular_read

PENDING = 'prepare-cleanup-pending.txt'


def write_marker(path, text):
    if path.exists() or path.is_symlink():
        regular_read(path, 512)  # never write through redirected or hard-linked markers
    path.write_text(text, encoding='utf-8')


@contextmanager
def generation_lock(folder):
    # Do not race another helper resuming an older completed generation.
    lock = folder/'preparation.lock'
    regular_read(lock, 64)
    with lock.open('r+b') as stream:
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == 'nt':
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def selection(storage):
    value = regular_read(storage/'prepared-cache.txt', 512).decode('utf-8')
    if not re.fullmatch(r'preparation/[0-9a-f]{24}/shadercache', value):
        raise ValueError('Invalid cache selection; nothing removed')
    folder = cache_root(storage/Path(value).parent)
    cache_root(folder/'shadercache')
    state = json.loads(regular_read(folder/'preparation-state.json', 65536))
    if (not isinstance(state, dict) or type(state.get('schema')) is not int or
            state.get('schema') != 1 or state.get('phase') != 'complete'):
        raise ValueError('Selected preparation is incomplete; nothing removed')
    return value, folder


def schedule(storage):
    if os.environ.get('GT5P_PREPARE_CLEANUP') == '0':
        return
    value, folder = selection(storage)
    if not (storage/('prepare-cleanup-'+folder.name+'.done')).exists():
        write_marker(storage/PENDING, value)


def candidates(storage, selected):
    parent = cache_root(storage/'preparation')
    children = list(parent.iterdir())
    if len(children) > 256:
        raise ValueError('Too many preparation generations; nothing removed')
    result = []
    for folder in sorted(children):
        if folder == selected or not re.fullmatch('[0-9a-f]{24}', folder.name):
            continue
        # Refuse redirected or shared files before inspecting any old generation.
        cache_root(folder)
        try:
            state = json.loads(regular_read(folder/'preparation-state.json', 65536))
        except (FileNotFoundError, ValueError):
            continue
        if (not isinstance(state, dict) or type(state.get('schema')) is not int or
                state.get('schema') != 1 or state.get('phase') != 'complete'):
            continue
        with ExitStack() as held:
            try:
                held.enter_context(generation_lock(folder))
            except OSError:
                continue
            preflight_tree(folder, generation_entry_budget())
            size = sum(p.stat().st_size for p in folder.rglob('*') if p.is_file())
        result.append((folder, size))
    return result


def confirm(size, count):
    ui = ctypes.WinDLL('user32', use_last_error=True)
    ui.MessageBoxW.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_uint]
    ui.MessageBoxW.restype = ctypes.c_int
    text = (f'Shader preparation completed successfully.\n\n'
            f'Remove {count} older prepared cache(s) to free approximately {size / 1024**3:.2f} GB?\n\n'
            'Your new prepared cache, saves and settings will be kept. Removing older caches also removes '
            'their learned shaders; switching back to an older renderer or FXC will require preparing again.\n\n'
            'Choose No to keep the older caches.')
    answer = ui.MessageBoxW(None, text, 'Tourline Prologue - old shader caches', 0x4 | 0x20 | 0x100)
    if not answer:
        raise OSError('Could not show cache cleanup offer')
    return answer == 6


def offer(storage, idle, ask=confirm):
    if os.environ.get('GT5P_PREPARE_CLEANUP') == '0':
        return
    idle()
    value, selected = selection(storage)
    if regular_read(storage/PENDING, 512).decode('utf-8') != value:
        (storage/PENDING).unlink()  # a later selection superseded this completion
        return
    marker = storage/('prepare-cleanup-'+selected.name+'.done')
    if marker.exists():
        (storage/PENDING).unlink()
        return
    old = candidates(storage, selected)
    yes = bool(old) and ask(sum(size for _, size in old), len(old))
    if yes:
        idle()
        if selection(storage)[0] != value:
            raise ValueError('Cache selection changed; nothing removed')
        # Revalidate the full target set after the dialog, before deleting anything.
        if candidates(storage, selected) != old:
            raise ValueError('Old caches changed; nothing removed')
        with ExitStack() as locks:
            for folder, _ in old:
                if folder.parent != selected.parent or folder == selected:
                    raise ValueError('Cleanup target escaped preparation storage')
                locks.enter_context(generation_lock(folder))
                preflight_tree(folder, generation_entry_budget())
            for folder, _ in old:
                if selection(storage)[0] != value:
                    raise ValueError('Cache selection changed; cleanup stopped')
                for child in folder.iterdir():
                    if child.name == 'preparation.lock':
                        continue
                    if child.is_dir():shutil.rmtree(child)
                    else:child.unlink()
        for folder, _ in old:
            (folder/'preparation.lock').unlink()
            folder.rmdir()
    write_marker(marker, 'removed\n' if yes else 'kept\n')
    (storage/PENDING).unlink()
