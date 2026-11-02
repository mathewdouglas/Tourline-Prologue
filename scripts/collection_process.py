"""Hidden offline children in an atomic, private kill-on-close Windows job."""
import ctypes
import os
from pathlib import Path
import subprocess
import time
from types import SimpleNamespace

from preparation_reuse import regular_read
from shader_vertex_batch import (ctypes_kernel, _extended_limits, _startup,
    _create_process, _environment_text, JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE,
    JOB_OBJECT_EXTENDED_LIMIT)


def run_owned(command, cwd, env, log, poll=None, timeout=180):
    kernel = ctypes_kernel()
    kernel.GetExitCodeProcess.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_ulong)]
    job = kernel.CreateJobObjectW(None, None)
    process = _startup(ctypes)[1]()
    if not job:
        raise ValueError('Could not own collection verification process')
    try:
        limits = _extended_limits(ctypes)
        limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not kernel.SetInformationJobObject(job, JOB_OBJECT_EXTENDED_LIMIT, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ValueError('Could not protect collection verification process')
        # Job handle stays non-inheritable. Only explicit standard handles inherit.
        with Path(log).open('wb') as stream, open(os.devnull, 'rb') as null:
            import msvcrt
            output = msvcrt.get_osfhandle(stream.fileno())
            input_handle = msvcrt.get_osfhandle(null.fileno())
            for handle in (output, input_handle):
                if not kernel.SetHandleInformation(handle, 1, 1):
                    raise ValueError('Cannot configure private verification handles')
            try:
                command_line = ctypes.create_unicode_buffer(subprocess.list2cmdline([str(p) for p in command]))
                environment = ctypes.create_unicode_buffer(_environment_text(env))
                ok, error = _create_process(SimpleNamespace(kernel=kernel, job=job), _startup(ctypes)[0],
                    process, command_line, environment, Path(cwd), input_handle, output, output, True)
                if not ok:
                    raise ValueError(f'Cannot own verification child (Windows error {error})')
            finally:
                for handle in (output, input_handle):
                    kernel.SetHandleInformation(handle, 1, 0)
            if kernel.ResumeThread(process.hThread) == 0xffffffff:
                raise ValueError('Cannot resume owned verification child')
            started = time.monotonic()
            while kernel.WaitForSingleObject(process.hProcess, 100) == 258:
                if poll:
                    poll()
                if time.monotonic() - started > timeout:
                    raise TimeoutError('Collection verification child timed out; completed cache retained')
                if os.fstat(stream.fileno()).st_size > 32*1024**2:
                    raise ValueError('Collection verification log budget exceeded')
            code = ctypes.c_ulong()
            if not kernel.GetExitCodeProcess(process.hProcess, ctypes.byref(code)) or code.value:
                raise ValueError('Collection verification process failed; see '+str(log))
    finally:
        # Closing our job kills only our child and descendants, including on owner death.
        kernel.CloseHandle(job)
        if process.hProcess:
            kernel.WaitForSingleObject(process.hProcess, 15000)
            kernel.CloseHandle(process.hProcess)
        if process.hThread:
            kernel.CloseHandle(process.hThread)
    text = regular_read(Path(log), 32*1024**2).decode('utf-8', errors='replace')
    if 'guest entry was not executed' not in text or '[GT5P] Executing' in text:
        raise ValueError('Collection verification offline execution guard was not confirmed')
    return text
