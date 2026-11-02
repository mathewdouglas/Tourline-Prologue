"""Small native post-play window; all verification stays in an owned worker.

The UI consumes one latest snapshot, never polls checkpoint/cache files. Closing
during work requests cooperative cancellation and waits for owned child cleanup.
No new packages, shader/runtime contracts or gameplay hooks are required.
"""
import ctypes as C
from ctypes import wintypes as W
import threading
import time
import uuid


PHASES = {
    'starting': 'Checking the collection',
    'finding-original-programs': 'Finding programs in your original game files',
    'lookup': 'Reading verified original programs',
    'vertex': 'Verifying vertex shaders',
    'fragment': 'Compiling fragment shaders',
    'native': 'Verifying native pipelines and saved driver data',
    'publishing': 'Saving the verified export',
    'checking-cache': 'Checking saved verification work',
    'verifying-cache': 'Checking persisted shader and driver data',
    'complete': 'Finishing verification',
}


class State:
    def __init__(self):
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.values = dict(phase='starting', counts={}, outcome=None, result=None)
        self.error = None
        self.finished = None

    def progress(self, phase, counts=None):
        if self.cancel.is_set():
            raise KeyboardInterrupt('Verification cancelled; completed work retained for resume')
        with self.lock:
            if phase != self.values['phase'] or counts is not None:
                self.values['counts'] = dict(counts or {})
            self.values['phase'] = phase

    def snapshot(self):
        with self.lock:
            return dict(self.values)

    def run(self, operation):
        try:
            result = operation(self.progress)
        except BaseException as error:
            self.error = error
            print(str(error), flush=True)
            outcome = 'cancelled' if isinstance(error, KeyboardInterrupt) else 'failed'
            with self.lock:
                self.values.update(outcome=outcome, result=str(error))
        else:
            with self.lock:
                self.values.update(outcome='complete', result=result)
        finally:
            self.finished = time.monotonic()


def show(operation):
    """Run operation(progress) and keep the result visible until Close.

    Startup failure propagates before any worker starts; never silently retry a
    verification whose ownership/outcome is unknown.
    """
    ui = C.WinDLL('user32', use_last_error=True)
    kernel = C.WinDLL('kernel32', use_last_error=True)
    gdi = C.WinDLL('gdi32', use_last_error=True)
    proc = C.WINFUNCTYPE(C.c_ssize_t, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    class WindowClass(C.Structure):
        _fields_ = [('style', W.UINT), ('proc', proc), ('cls_extra', C.c_int),
                    ('wnd_extra', C.c_int), ('instance', W.HINSTANCE),
                    ('icon', W.HICON), ('cursor', W.HANDLE), ('background', W.HBRUSH),
                    ('menu', W.LPCWSTR), ('name', W.LPCWSTR)]
    ui.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    ui.DefWindowProcW.restype = C.c_ssize_t
    ui.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD,
        C.c_int, C.c_int, C.c_int, C.c_int, W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
    ui.CreateWindowExW.restype = W.HWND
    ui.RegisterClassW.argtypes = [C.POINTER(WindowClass)]
    ui.UnregisterClassW.argtypes = [W.LPCWSTR, W.HINSTANCE]
    ui.SetWindowTextW.argtypes = [W.HWND, W.LPCWSTR]
    ui.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    ui.SendMessageW.restype = C.c_ssize_t
    ui.EnableWindow.argtypes = [W.HWND, W.BOOL]
    ui.DestroyWindow.argtypes = [W.HWND]
    ui.ShowWindow.argtypes = [W.HWND, C.c_int]
    ui.SetForegroundWindow.argtypes = [W.HWND]
    ui.SetTimer.argtypes = [W.HWND, C.c_size_t, W.UINT, W.LPVOID]
    ui.KillTimer.argtypes = [W.HWND, C.c_size_t]
    ui.GetMessageW.argtypes = [C.POINTER(W.MSG), W.HWND, W.UINT, W.UINT]
    ui.TranslateMessage.argtypes = [C.POINTER(W.MSG)]
    ui.DispatchMessageW.argtypes = [C.POINTER(W.MSG)]
    ui.IsDialogMessageW.argtypes = [W.HWND, C.POINTER(W.MSG)]
    ui.SetFocus.argtypes = [W.HWND]
    kernel.GetModuleHandleW.argtypes = [W.LPCWSTR]
    kernel.GetModuleHandleW.restype = W.HMODULE
    gdi.GetStockObject.argtypes = [C.c_int]
    gdi.GetStockObject.restype = W.HANDLE
    state = State()
    controls = {}
    started = time.monotonic()
    def cancel():
        state.cancel.set()
        ui.SetWindowTextW(controls['button'], 'Cancelling...')
        ui.EnableWindow(controls['button'], False)
    @proc
    def callback(hwnd, message, wp, lp):
        if message == 0x10 or (message == 0x111 and wp & 0xffff in (1, 2)):
            if state.snapshot()['outcome'] is None:
                cancel()
            else:
                ui.DestroyWindow(hwnd)
            return 0
        if message == 0x113:
            snap = state.snapshot()
            elapsed = int((state.finished or time.monotonic()) - started)
            if snap['outcome'] is None:
                title = PHASES.get(snap['phase'], snap['phase'].replace('-', ' ').capitalize())
                counts = snap['counts']
                detail = 'Working; this stage may take a few minutes.'
                if 'completed' in counts and 'total' in counts:
                    detail = f"{counts['completed']:,} / {counts['total']:,} in this stage"
                elif 'requested' in counts:
                    detail = f"{counts['requested']:,} requests in this stage. Working..."
                if state.cancel.is_set():
                    title = 'Cancelling safely'
                    detail = 'Waiting for owned workers to stop. Completed work will be kept.'
            else:
                outcome = snap['outcome']
                title = {'complete': 'Verification complete', 'cancelled': 'Verification cancelled',
                         'failed': 'Verification could not finish'}[outcome]
                if outcome == 'complete':
                    result = snap['result']
                    detail = f"Verified: {result['verified']:,}    Pending: {result['pending']:,}\r\n"
                    detail += ('Share only: ' + result['share_file']) if result.get('share_file') else 'No verified share file was published.'
                else:
                    detail = ('Your collection and completed work are kept.\r\n'
                              'Use Resume pipeline verification.cmd to try again.\r\n'
                              'Details are in the collection console.')
                ui.SetWindowTextW(controls['button'], 'Close')
                ui.EnableWindow(controls['button'], True)
            ui.SetWindowTextW(controls['phase'], title)
            ui.SetWindowTextW(controls['detail'], detail)
            ui.SetWindowTextW(controls['elapsed'], f'Elapsed: {elapsed // 60}:{elapsed % 60:02d}')
            return 0
        if message == 2:
            ui.PostQuitMessage(0)
            return 0
        return ui.DefWindowProcW(hwnd, message, wp, lp)
    instance = kernel.GetModuleHandleW(None)
    name = 'TourlineCollectionVerification' + uuid.uuid4().hex
    cls = WindowClass(0, callback, 0, 0, instance, None, None, W.HBRUSH(6), None, name)
    if not ui.RegisterClassW(C.byref(cls)):
        raise C.WinError(C.get_last_error())
    hwnd = None
    worker = None
    try:
        hwnd = ui.CreateWindowExW(0, name, 'Tourline Prologue - Collection verification',
            0x00ca0000, 0x80000000 - 0x100000000, 0, 580, 270, None, None, instance, None)
        if not hwnd:
            raise C.WinError(C.get_last_error())
        font = gdi.GetStockObject(17)
        for key, label, x, y, width, height, kind, identity in (
            ('phase', 'Checking the collection', 20, 20, 530, 28, 'STATIC', 2),
            ('detail', 'Your collection is saved. Verification uses your original game files.', 20, 60, 530, 66, 'STATIC', 3),
            ('elapsed', 'Elapsed: 0:00', 20, 138, 530, 24, 'STATIC', 4),
            ('note', 'Only verified records can be shared. Pending records remain private.', 20, 171, 530, 22, 'STATIC', 5),
            ('button', 'Cancel', 438, 199, 110, 28, 'BUTTON', 1)):
            control = ui.CreateWindowExW(0, kind, label, 0x50000000 | (0x10000 if kind == 'BUTTON' else 0),
                x, y, width, height, hwnd, W.HMENU(identity), instance, None)
            if not control:
                raise C.WinError(C.get_last_error())
            controls[key] = control
            ui.SendMessageW(control, 0x30, font, 1)
        if not ui.SetTimer(hwnd, 1, 200, None):
            raise C.WinError(C.get_last_error())
        ui.ShowWindow(hwnd, 5)
        ui.SetForegroundWindow(hwnd)
        ui.SetFocus(controls['button'])
        worker = threading.Thread(target=state.run, args=(operation,), name='collection-verification')
        worker.start()
        msg = W.MSG()
        while True:
            received = ui.GetMessageW(C.byref(msg), None, 0, 0)
            if received == -1:
                raise C.WinError(C.get_last_error())
            if received == 0:
                break
            if not ui.IsDialogMessageW(hwnd, C.byref(msg)):
                ui.TranslateMessage(C.byref(msg))
                ui.DispatchMessageW(C.byref(msg))
    finally:
        state.cancel.set()
        if worker is not None:
            worker.join()  # The helper must outlive its children and lease cleanup.
        if hwnd:
            ui.KillTimer(hwnd, 1)
            ui.DestroyWindow(hwnd)
        ui.UnregisterClassW(name, instance)
    if state.error is not None:
        raise state.error
    return state.snapshot()['result']
