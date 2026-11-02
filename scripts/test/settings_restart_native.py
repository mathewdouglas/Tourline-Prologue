"""Exercise real settings restarts in a private install, using owned handles only.

Requires the game to be closed. Reads original game files; never copies GT.VOL.
Output must be a new ignored directory. Run no other tests concurrently.
"""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import zipfile

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from train_pipeline_cache import idle, isolated


class ProcessEntry(C.Structure):
    _fields_ = [('size',W.DWORD),('usage',W.DWORD),('pid',W.DWORD),
                ('heap',C.c_size_t),('module',W.DWORD),('threads',W.DWORD),
                ('parent',W.DWORD),('priority',W.LONG),('flags',W.DWORD),
                ('exe',W.WCHAR*260)]


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('zip','launcher','engine','elf','game','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args()
    idle()
    out=isolated(a.output)
    if out.exists(): raise ValueError('Fresh output required')
    install,storage=out/'Install',out/'Storage'
    install.mkdir(parents=True);(storage/'input').mkdir(parents=True)
    with zipfile.ZipFile(a.zip) as archive:
        for name in archive.namelist():
            if not name.startswith('preparation/'): archive.extract(name,install)
    shutil.copyfile(a.launcher,install/'tourline-prologue.exe')
    shutil.copyfile(a.engine,install/'runtime/gt5p.exe')
    shutil.copyfile(a.elf,storage/'input/EMAIN.ELF')
    manifest=install/'release.ini'
    text=manifest.read_text()
    engine_hash=hashlib.sha256(a.engine.read_bytes()).hexdigest()
    text='\n'.join('game_sha256='+engine_hash if line.startswith('game_sha256=') else line for line in text.splitlines())+'\n'
    manifest.write_text(text)
    (storage/'setup.ini').write_text('[game]\ndirectory='+str(a.game.resolve())+'\n',encoding='utf-16')
    settings=storage/'gt5p_settings.toml'
    settings.write_text('[video]\nresolution = "720p"\naspect = "16:9"\nmsaa = 2\nshader_precompile = false\npipeline_async = true\n')
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('RSX_','GT5P_','PS3_'))}
    env.update(GT5P_USER_DIR=str(storage),PS3_VERBOSE='0',GT5P_SETTINGS_UI='1',
               GT5P_SETTINGS_UI_LEGACY='1',GT5P_SETTINGS_PAUSE='0')
    u,k=C.WinDLL('user32'),C.WinDLL('kernel32',use_last_error=True)
    cb=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    u.EnumWindows.argtypes=[cb,W.LPARAM]
    u.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    u.GetClassNameW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    u.IsWindowVisible.argtypes=[W.HWND]
    u.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
    k.CreateToolhelp32Snapshot.argtypes=[W.DWORD,W.DWORD];k.CreateToolhelp32Snapshot.restype=W.HANDLE
    k.Process32FirstW.argtypes=[W.HANDLE,C.POINTER(ProcessEntry)]
    k.Process32NextW.argtypes=[W.HANDLE,C.POINTER(ProcessEntry)]
    k.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];k.OpenProcess.restype=W.HANDLE
    k.CloseHandle.argtypes=[W.HANDLE]
    k.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD]
    k.GetExitCodeProcess.argtypes=[W.HANDLE,C.POINTER(W.DWORD)]
    owner=subprocess.Popen([install/'tourline-prologue.exe'],env=env)
    handles,history=[],[]
    def children():
        snap=k.CreateToolhelp32Snapshot(2,0)
        assert snap and snap!=C.c_void_p(-1).value
        entry=ProcessEntry();entry.size=C.sizeof(entry);pids=set()
        try:
            more=k.Process32FirstW(snap,C.byref(entry))
            while more:
                if entry.parent==owner.pid and entry.exe.lower()=='gt5p.exe': pids.add(entry.pid)
                more=k.Process32NextW(snap,C.byref(entry))
        finally: k.CloseHandle(snap)
        return pids
    def window(previous=None):
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            assert owner.poll() is None,('Launcher exited',owner.returncode)
            found=[];pids=children()
            @cb
            def visit(hwnd,unused):
                pid=W.DWORD();u.GetWindowThreadProcessId(hwnd,C.byref(pid))
                if pid.value in pids and pid.value!=previous:
                    cls=C.create_unicode_buffer(128);u.GetClassNameW(hwnd,cls,len(cls))
                    if cls.value=='gt5p_settings' and u.IsWindowVisible(hwnd):found.append((hwnd,pid.value))
                return True
            u.EnumWindows(visit,0)
            if found:
                hwnd,pid=found[0]
                handle=k.OpenProcess(0x100000|0x1000,False,pid)
                assert handle
                handles.append(handle);history.append(pid)
                time.sleep(.5)
                return hwnd,pid,handle
            time.sleep(.1)
        raise AssertionError('No replacement settings window')
    def key(hwnd,value):
        assert u.PostMessageW(hwnd,0x100,value,0)
        time.sleep(.15)
    try:
        hwnd,pid,handle=window()
        for stage,row,expected in [('resolution-1080',0,'resolution = "1080p"'),
                                   ('aspect-ultrawide',1,'aspect = "21:9"'),
                                   ('aspect-standard',1,'aspect = "16:9"')]:
            # Page opens with its first item selected. Right changes that item.
            for _ in range(row):key(hwnd,0x28)
            key(hwnd,0x27)
            assert expected in settings.read_text(),(stage,settings.read_text())
            # Up from the first item -> section header -> first button (Restart).
            for _ in range(row+2):key(hwnd,0x26)
            key(hwnd,0x0D)
            assert k.WaitForSingleObject(handle,15000)==0,'Old game did not exit'
            code=W.DWORD();assert k.GetExitCodeProcess(handle,C.byref(code))
            assert code.value==0x47543552,hex(code.value)
            hwnd,new_pid,handle=window(pid)
            assert new_pid!=pid
            time.sleep(1)
            for name in ('play.out','play.err'):
                shutil.copyfile(storage/'logs'/name,out/(stage+'-'+name))
            boot=(out/(stage+'-play.out')).read_text(errors='replace')
            assert 'resolution=1080p' in boot,(stage,'Replacement did not reload saved resolution')
            assert ('ultrawide: 21:9 aspect' in boot)==(stage=='aspect-ultrawide'),(stage,'Stale aspect mode')
            pid=new_pid
            print(stage+': old game exited; replacement settings window ready',flush=True)
        (out/'validation.json').write_text(json.dumps(dict(restarts=3,launcher_pid=owner.pid,game_pids=history,
            settings=settings.read_text(),limitations='Boot/settings-window check; no race, frame-time or screenshot rendering claim.'),indent=2)+'\n')
    finally:
        if owner.poll() is None:owner.terminate();owner.wait(timeout=10)
        for handle in handles:
            try: assert k.WaitForSingleObject(handle,10000)==0,'Owned game survived launcher shutdown'
            finally:k.CloseHandle(handle)


if __name__=='__main__':main()
