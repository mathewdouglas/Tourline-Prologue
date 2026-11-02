"""Owned native window integration: progress, failure and cancel/close cleanup."""
import ctypes as C
from ctypes import wintypes as W
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).parents[1]))
from collection_ui import show


def child(mode, root):
    def operation(progress):
        try:
            progress('vertex', dict(completed=12, total=32))
            progress('vertex')  # Heartbeat must retain the stage count.
            while not (root/'continue').exists():
                progress('vertex')
                time.sleep(.03)
            if mode == 'failed':
                raise ValueError('Synthetic original-asset rejection')
            return dict(verified=31, pending=1, share_file='share-this-template.json')
        finally:
            time.sleep(.25)  # Simulate owned worker/lease cleanup before completion.
            (root/'cleaned').write_text('yes')
    try:
        result = show(operation)
    except KeyboardInterrupt:
        result = dict(cancelled=True)
    except ValueError as error:
        result = dict(error=str(error))
    assert (root/'cleaned').exists()
    (root/'result.json').write_text(json.dumps(result))


def main():
    ui = C.WinDLL('user32', use_last_error=True)
    enum = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    ui.EnumWindows.argtypes = [enum, W.LPARAM]
    ui.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    ui.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    ui.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    ui.GetDlgItem.argtypes = [W.HWND, C.c_int]
    ui.GetDlgItem.restype = W.HWND
    ui.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    def text(hwnd, identity):
        data = C.create_unicode_buffer(4096)
        ui.GetWindowTextW(ui.GetDlgItem(hwnd, identity), data, len(data))
        return data.value
    def until(check):
        deadline = time.monotonic()+12
        while time.monotonic()<deadline:
            result = check()
            if result:
                return result
            time.sleep(.04)
        raise AssertionError('Timed out waiting for owned verification UI')
    with tempfile.TemporaryDirectory(prefix='Tourline collection UI ') as folder:
        for mode in ('complete', 'failed', 'cancel-button', 'cancel-close', 'cancel-escape'):
            root = Path(folder)/mode
            root.mkdir()
            with (root/'child.log').open('w') as log:
                process = subprocess.Popen([sys._base_executable, __file__, '--child', mode, str(root)],
                                           stdout=log, stderr=log)
                windows = []
                @enum
                def find(hwnd, unused):
                    pid = W.DWORD()
                    ui.GetWindowThreadProcessId(hwnd, C.byref(pid))
                    name = C.create_unicode_buffer(128)
                    ui.GetClassNameW(hwnd, name, len(name))
                    if pid.value == process.pid and name.value.startswith('TourlineCollectionVerification'):
                        windows.append(hwnd)
                    return True
                def window():
                    windows.clear()
                    ui.EnumWindows(find, 0)
                    if process.poll() is not None:
                        raise AssertionError((root/'child.log').read_text())
                    assert len(windows)<=1
                    return windows[0] if windows else None
                try:
                    hwnd = until(window)
                    until(lambda: '12 / 32' in text(hwnd, 3))
                    if mode.startswith('cancel'):
                        if mode == 'cancel-escape':ui.PostMessageW(hwnd, 0x100, 0x1b, 0)
                        else:ui.PostMessageW(hwnd, 0x111 if mode == 'cancel-button' else 0x10, 1, 0)
                        until(lambda: 'Verification cancelled' == text(hwnd, 2))
                    else:
                        (root/'continue').touch()
                        expected = 'Verification complete' if mode == 'complete' else 'Verification could not finish'
                        until(lambda: expected == text(hwnd, 2))
                    assert (root/'cleaned').exists(), 'UI reported completion before cleanup'
                    if mode == 'complete':
                        assert 'Verified: 31    Pending: 1' in text(hwnd, 3)
                        assert 'share-this-template.json' in text(hwnd, 3)
                    else:
                        assert 'Resume pipeline verification.cmd' in text(hwnd, 3)
                    ui.PostMessageW(hwnd, 0x10, 0, 0)
                    assert process.wait(timeout=10) == 0
                    log.flush()
                    assert 'Exception ignored' not in (root/'child.log').read_text()
                    result = json.loads((root/'result.json').read_text())
                    if mode.startswith('cancel'):assert result == dict(cancelled=True)
                    elif mode == 'failed':assert 'Synthetic original-asset rejection' in result['error']
                    else:assert result['verified'] == 31
                finally:
                    if process.poll() is None:
                        process.terminate();process.wait(timeout=10)
    print('Native verification UI progress, counts, success, rejection, Cancel/Close and cleanup passed')


if __name__ == '__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--child':child(sys.argv[2], Path(sys.argv[3]))
    else:main()
