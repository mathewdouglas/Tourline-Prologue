"""Exercise the production preparation UI with a stand-in wait, never the game.

Build preparation_ui_native.cpp first. Runs windows sequentially and only sends
messages to its own child. Screenshots contain synthetic test status.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
from pathlib import Path
import subprocess
import struct
import tempfile
import time
import zlib


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--probe', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    ui, gdi = C.WinDLL('user32'), C.WinDLL('gdi32')
    callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    ui.EnumWindows.argtypes = [callback, W.LPARAM]
    ui.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    ui.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    ui.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    ui.GetDlgItem.argtypes = [W.HWND, C.c_int]
    ui.GetDlgItem.restype = W.HWND
    ui.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    ui.SendMessageW.restype = W.LPARAM
    ui.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    ui.GetWindowRect.argtypes = [W.HWND, C.POINTER(W.RECT)]
    ui.GetWindowDC.argtypes = [W.HWND]
    ui.GetWindowDC.restype = W.HDC
    ui.ReleaseDC.argtypes = [W.HWND, W.HDC]
    ui.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]
    gdi.CreateCompatibleDC.argtypes = [W.HDC]
    gdi.CreateCompatibleDC.restype = W.HDC
    gdi.CreateCompatibleBitmap.argtypes = [W.HDC, C.c_int, C.c_int]
    gdi.CreateCompatibleBitmap.restype = W.HBITMAP
    gdi.SelectObject.argtypes = [W.HDC, W.HANDLE]
    gdi.SelectObject.restype = W.HANDLE
    gdi.DeleteObject.argtypes = [W.HANDLE]
    gdi.DeleteDC.argtypes = [W.HDC]

    class BitmapHeader(C.Structure):
        _fields_ = [('size', W.DWORD), ('width', W.LONG), ('height', W.LONG),
                    ('planes', W.WORD), ('bits', W.WORD), ('compression', W.DWORD),
                    ('image_size', W.DWORD), ('xppm', W.LONG), ('yppm', W.LONG),
                    ('used', W.DWORD), ('important', W.DWORD)]

    gdi.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, C.c_void_p,
                              C.POINTER(BitmapHeader), W.UINT]

    def rect(hwnd):
        value = W.RECT()
        assert ui.GetWindowRect(hwnd, C.byref(value))
        return value

    def text(hwnd):
        value = C.create_unicode_buffer(32769)
        ui.GetWindowTextW(hwnd, value, len(value))
        return value.value

    def until(check):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            time.sleep(.04)
        raise AssertionError('Timed out waiting for owned preparation UI')

    def screenshot(hwnd, path):
        r = rect(hwnd)
        width, height = r.right - r.left, r.bottom - r.top
        source = ui.GetWindowDC(hwnd)
        dc = gdi.CreateCompatibleDC(source)
        bitmap = gdi.CreateCompatibleBitmap(source, width, height)
        old = gdi.SelectObject(dc, bitmap)
        try:
            assert ui.PrintWindow(hwnd, dc, 2), 'PrintWindow failed'
            gdi.SelectObject(dc, old)
            header = BitmapHeader(C.sizeof(BitmapHeader), width, -height, 1, 32)
            data = C.create_string_buffer(width * height * 4)
            assert gdi.GetDIBits(dc, bitmap, 0, height, data, C.byref(header), 0) == height
            raw = data.raw
            rgb = bytearray(width * height * 3)
            rgb[0::3], rgb[1::3], rgb[2::3] = raw[2::4], raw[1::4], raw[0::4]
            def chunk(kind, content):
                return (struct.pack('>I', len(content)) + kind + content
                        + struct.pack('>I', zlib.crc32(kind + content)))
            rows = b''.join(b'\0' + rgb[y * width * 3:(y + 1) * width * 3]
                            for y in range(height))
            path.write_bytes(b'\x89PNG\r\n\x1a\n'
                + chunk(b'IHDR', struct.pack('>2I5B', width, height, 8, 2, 0, 0, 0))
                + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
        finally:
            gdi.SelectObject(dc, old)
            gdi.DeleteObject(bitmap)
            gdi.DeleteDC(dc)
            ui.ReleaseDC(hwnd, source)

    with tempfile.TemporaryDirectory(prefix='Tourline preparation UI ') as temp:
        root = Path(temp)
        subprocess.run([args.probe, '--selftest', root/'parser'], check=True, timeout=20)
        for mode in ('button', 'close', 'escape', 'enter', 'space', 'legacy-message', 'cancel-write-failure'):
            folder = root/mode
            folder.mkdir()
            status = folder/'status.txt'
            status.write_text('Vertex 180/2892', encoding='utf-8')
            if mode == 'cancel-write-failure':
                (folder/'cancel').mkdir()
            child = subprocess.Popen([args.probe, '--window', folder])
            windows = []

            @callback
            def find(hwnd, unused):
                pid = W.DWORD()
                ui.GetWindowThreadProcessId(hwnd, C.byref(pid))
                klass = C.create_unicode_buffer(128)
                ui.GetClassNameW(hwnd, klass, len(klass))
                if pid.value == child.pid and klass.value == 'TourlinePrepareProgress':
                    windows.append(hwnd)
                return True

            try:
                def owned_window():
                    windows.clear()
                    ui.EnumWindows(find, 0)
                    return windows[0] if windows else None
                hwnd = until(owned_window)
                control = lambda ident: ui.GetDlgItem(hwnd, ident)
                until(lambda: text(control(102)) == 'Vertex')
                assert text(control(106)) == '180 / 2,892 for this step'
                assert ui.SendMessageW(control(120), 0x408, 0, 0) == 180  # PBM_GETPOS
                if mode == 'button':
                    time.sleep(.25)
                    screenshot(hwnd, args.output/'vertex.png')
                    status.write_text('Checking game archive 2147483648/4294967296', encoding='utf-8')
                    until(lambda: text(control(102)) == 'Checking game archive')
                    assert text(control(106)) == '2,147,483,648 / 4,294,967,296 bytes for this step'
                    assert ui.SendMessageW(control(120), 0x408, 0, 0) == 500000
                    screenshot(hwnd, args.output/'archive.png')
                    status.write_text('Fragment', encoding='utf-8')
                    until(lambda: text(control(102)) == 'Fragment')
                    assert text(control(106)) == 'Not counted for this step'
                    screenshot(hwnd, args.output/'fragment.png')
                    status.write_bytes(b'\xff')
                    time.sleep(.3)
                    assert text(control(102)) == 'Fragment', 'bad UTF8 replaced last good status'
                    ui.SendMessageW(hwnd, 0x2e0, (144 << 16) | 144, 0)  # WM_DPICHANGED
                    outer, button = rect(hwnd), rect(control(2))
                    assert outer.left <= button.left < button.right <= outer.right
                    assert outer.top <= button.top < button.bottom <= outer.bottom
                    screenshot(hwnd, args.output/'scaled.png')
                if mode == 'close':
                    ui.PostMessageW(hwnd, 0x10, 0, 0)
                elif mode in ('escape', 'enter', 'space'):
                    key = {'escape': 27, 'enter': 13, 'space': 32}[mode]
                    ui.PostMessageW(control(2), 0x100, key, 0)
                    ui.PostMessageW(control(2), 0x101, key, 0)
                elif mode == 'legacy-message':
                    ui.SendMessageW(hwnd, 0x400 + 102, 2, 0)
                else:
                    ui.SendMessageW(control(2), 0xf5, 0, 0)  # BM_CLICK real button
                if mode == 'cancel-write-failure':
                    until(lambda: 'Could not write' in text(control(104)))
                else:
                    until(lambda: (folder/'cancel').is_file())
                    assert (folder/'cancel').read_text() == 'cancel\n'
                    until(lambda: 'Cancelling preparation' in text(control(104)))
                time.sleep(.3)
                assert child.poll() is None and owned_window(), 'cancel abandoned owned wait'
                (folder/'finish').touch()
                assert child.wait(timeout=8) == 0
                print(mode + ': cancellation waits for owned completion, passed')
            finally:
                (folder/'finish').touch()
                if child.poll() is None:
                    child.wait(timeout=8)
    print('Sequential preparation UI checks passed; screenshots use synthetic status.')


if __name__ == '__main__':
    main()
