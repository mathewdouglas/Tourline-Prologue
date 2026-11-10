"""Production launcher overlay against owned synthetic game/helper processes, under run_locked.py."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
import zlib
from launcher_native import sfo


class Windows:
    def __init__(self):
        self.ui=u=C.WinDLL('user32');self.k=k=C.WinDLL('kernel32');self.g=g=C.WinDLL('gdi32')
        self.callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
        for name,result,arguments in (
            ('GetForegroundWindow',W.HWND,[]),('GetWindow',W.HWND,[W.HWND,W.UINT]),
            ('GetWindowThreadProcessId',W.DWORD,[W.HWND,C.POINTER(W.DWORD)]),
            ('GetClassNameW',C.c_int,[W.HWND,W.LPWSTR,C.c_int]),('GetWindowTextW',C.c_int,[W.HWND,W.LPWSTR,C.c_int]),
            ('IsWindowVisible',W.BOOL,[W.HWND]),('ShowWindow',W.BOOL,[W.HWND,C.c_int]),
            ('SetForegroundWindow',W.BOOL,[W.HWND]),('AttachThreadInput',W.BOOL,[W.DWORD,W.DWORD,W.BOOL]),
            ('BringWindowToTop',W.BOOL,[W.HWND]),('PeekMessageW',W.BOOL,[C.POINTER(W.MSG),W.HWND,W.UINT,W.UINT,W.UINT]),
            ('GetWindowRect',W.BOOL,[W.HWND,C.POINTER(W.RECT)]),('GetWindowDC',W.HDC,[W.HWND]),
            ('ReleaseDC',C.c_int,[W.HWND,W.HDC]),('PrintWindow',W.BOOL,[W.HWND,W.HDC,W.UINT]),
            ('SendMessageW',W.LPARAM,[W.HWND,W.UINT,W.WPARAM,W.LPARAM])):
            fn=getattr(u,name);fn.restype=result;fn.argtypes=arguments
        u.EnumWindows.argtypes=[self.callback,W.LPARAM]
        k.OpenEventW.argtypes=[W.DWORD,W.BOOL,W.LPCWSTR];k.OpenEventW.restype=W.HANDLE
        k.SetEvent.argtypes=k.ResetEvent.argtypes=k.CloseHandle.argtypes=[W.HANDLE]
        k.GetCurrentThreadId.restype=W.DWORD
        for name,result,args in [('CreateCompatibleDC',W.HDC,[W.HDC]),
            ('CreateCompatibleBitmap',W.HBITMAP,[W.HDC,C.c_int,C.c_int]),('SelectObject',W.HANDLE,[W.HDC,W.HANDLE]),
            ('DeleteObject',W.BOOL,[W.HANDLE]),('DeleteDC',W.BOOL,[W.HDC])]:
            fn=getattr(g,name);fn.restype=result;fn.argtypes=args

    def find(self,pid,cls,visible=True):
        found=[]
        @self.callback
        def visit(hwnd,_):
            actual=W.DWORD();self.ui.GetWindowThreadProcessId(hwnd,C.byref(actual))
            name=C.create_unicode_buffer(128);self.ui.GetClassNameW(hwnd,name,128)
            if actual.value==pid and name.value==cls and (not visible or self.ui.IsWindowVisible(hwnd)):found.append(hwnd)
            return True
        self.ui.EnumWindows(visit,0)
        return found[0] if found else None

    def text(self,hwnd):
        text=C.create_unicode_buffer(512);self.ui.GetWindowTextW(hwnd,text,512);return text.value

    def activate(self,hwnd):
        message=W.MSG();self.ui.PeekMessageW(C.byref(message),None,0,0,0)
        for _ in range(8):
            foreground=self.ui.GetWindowThreadProcessId(self.ui.GetForegroundWindow(),None)
            current=self.k.GetCurrentThreadId();attached=foreground!=current and self.ui.AttachThreadInput(current,foreground,True)
            try:
                self.ui.ShowWindow(hwnd,9);self.ui.BringWindowToTop(hwnd);self.ui.SetForegroundWindow(hwnd)
            finally:
                if attached:self.ui.AttachThreadInput(current,foreground,False)
            if self.ui.GetForegroundWindow()==hwnd:return
            time.sleep(.2)
        raise AssertionError('Could not activate owned fixture window')

    def capture(self,hwnd,path):
        class Header(C.Structure):
            _fields_=[('size',W.DWORD),('width',W.LONG),('height',W.LONG),('planes',W.WORD),('bits',W.WORD),
                ('compression',W.DWORD),('image_size',W.DWORD),('xppm',W.LONG),('yppm',W.LONG),('used',W.DWORD),('important',W.DWORD)]
        self.g.GetDIBits.argtypes=[W.HDC,W.HBITMAP,W.UINT,W.UINT,C.c_void_p,C.POINTER(Header),W.UINT]
        rc=W.RECT();assert self.ui.GetWindowRect(hwnd,C.byref(rc))
        width,height=rc.right-rc.left,rc.bottom-rc.top
        source=self.ui.GetWindowDC(hwnd);dc=self.g.CreateCompatibleDC(source)
        bitmap=self.g.CreateCompatibleBitmap(source,width,height);old=self.g.SelectObject(dc,bitmap)
        try:
            assert self.ui.PrintWindow(hwnd,dc,2)
            self.g.SelectObject(dc,old);header=Header(C.sizeof(Header),width,-height,1,32)
            buffer=C.create_string_buffer(width*height*4)
            assert self.g.GetDIBits(dc,bitmap,0,height,buffer,C.byref(header),0)==height
            raw=buffer.raw;rgb=bytearray(width*height*3)
            rgb[0::3],rgb[1::3],rgb[2::3]=raw[2::4],raw[1::4],raw[0::4]
            def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data))
            rows=b''.join(b'\0'+rgb[y*width*3:(y+1)*width*3] for y in range(height))
            path.write_bytes(b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',width,height,8,2,0,0,0))+
                chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b''))
        finally:
            self.g.SelectObject(dc,old);self.g.DeleteObject(bitmap);self.g.DeleteDC(dc);self.ui.ReleaseDC(hwnd,source)


def until(check,seconds=12):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=check()
        if value:return value
        time.sleep(.05)
    raise AssertionError('Timed out waiting for owned background status')


def read(path):return dict(line.split('=',1) for line in path.read_text(encoding='utf-8-sig').splitlines() if '=' in line)


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('launcher','probe','game','output'):ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();root=args.output.resolve()
    if root.exists():raise ValueError('Use a fresh ignored output')
    root.mkdir(parents=True);win=Windows();original=win.ui.GetForegroundWindow()
    install=root/'I';disc=root/'Disc/PS3_GAME'
    for folder in (install/'runtime',install/'preparation',install/'assets',disc/'USRDIR'):folder.mkdir(parents=True)
    (disc/'PARAM.SFO').write_bytes(sfo())
    for name in ('GT.VOL','TV.DAT'):(disc/'USRDIR'/name).write_bytes(b'synthetic')
    for source,destination in ((args.launcher,install/'tourline-prologue.exe'),(args.game,install/'runtime/gt5p.exe'),
                               (args.probe,install/'preparation/GT5P-Prepare.exe')):shutil.copyfile(source,destination)
    elf=b'\x7fELF synthetic visible fixture'
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    (install/'release.ini').write_text('[release]\nschema=1\ntarget=BCUS98158\nversion=03.00\nport_version=0.2.5\n'+
        'elf_sha256='+hashlib.sha256(elf).hexdigest()+'\ngame_sha256='+sha(args.game)+'\nprepare_sha256='+sha(args.probe)+'\n')
    results=[]
    try:
        for case,extra in [('pause-restart',{}),('complete',{'GT5P_PROBE_BACKGROUND_MS':'3000'}),
            ('complete-during-race',{'GT5P_PROBE_BACKGROUND_MS':'3000','GT5P_PREPARE_BACKGROUND_PAUSE':'0'}),
            ('failure',{'GT5P_PROBE_BACKGROUND_MS':'1200','GT5P_PROBE_BACKGROUND_EXIT':'1'}),
            ('indicator-off',{'GT5P_PREPARE_BACKGROUND_INDICATOR':'0'})]:
            storage=root/case;(storage/'input').mkdir(parents=True)
            (storage/'input/EMAIN.ELF').write_bytes(elf)
            (storage/'setup.ini').write_text('[game]\ndirectory='+str(disc)+'\n',encoding='utf-16')
            (storage/'gt5p_settings.toml').write_text('[video]\nresolution="720p"\naspect="16:9"\nmsaa=2\n')
            (storage/'prepare-offer-0.2.5.done').write_text('answered')
            env={k:v for k,v in os.environ.items() if not k.upper().startswith(('GT5P_','RSX_'))}
            env.update(GT5P_USER_DIR=str(storage),PS3_VERBOSE='0',GT5P_PREPARE_DXC_OFFER='0',GT5P_PREPARE_CLEANUP='0',
                GT5P_PROBE_SELECTED='0',GT5P_PROBE_BACKGROUND_MS='60000')
            env.update(extra)
            owner=subprocess.Popen([install/'tourline-prologue.exe'],env=env)
            event=None
            try:
                info=until(lambda:read(storage/'ui-game.txt') if (storage/'ui-game.txt').exists() else None)
                pid=int(info['pid']);game=until(lambda:win.find(pid,'tourline_ui_fixture'));win.activate(game)
                event=win.k.OpenEventW(0x100002,False,info['event']);assert event
                def overlay():return win.find(owner.pid,'tourline_background_prepare')
                def view(label):return until(lambda:(window:=overlay()) and win.text(window)==label and window)
                def shot(window,name):win.capture(window,storage/(name+'.png'))
                if case=='indicator-off':
                    time.sleep(.6);assert not overlay()
                    win.k.SetEvent(event);time.sleep(.4);a=(storage/'heartbeat.txt').read_bytes();time.sleep(.5)
                    assert (storage/'heartbeat.txt').read_bytes()==a
                    win.k.ResetEvent(event);until(lambda:(storage/'heartbeat.txt').read_bytes()!=a)
                elif case=='pause-restart':
                    active=view('Preparing shaders in background');assert win.ui.GetWindow(active,4)==game,(active,win.ui.GetWindow(active,4),game)
                    assert win.ui.GetForegroundWindow()==game
                    assert win.ui.SendMessageW(active,0x84,0,0)==-1  # HTTRANSPARENT
                    shot(active,'preparing');win.k.SetEvent(event)
                    paused=view('Shader preparation paused during race');shot(paused,'paused')
                    a=(storage/'heartbeat.txt').read_bytes();time.sleep(.5);assert (storage/'heartbeat.txt').read_bytes()==a
                    win.k.ResetEvent(event);view('Preparing shaders in background')
                    (storage/'ui-restart').write_text('restart')
                    until(lambda:int(read(storage/'ui-game.txt')['pid'])!=pid)
                    pid=int(read(storage/'ui-game.txt')['pid']);game=until(lambda:win.find(pid,'tourline_ui_fixture'));win.activate(game)
                    active=until(lambda:(window:=overlay()) and win.text(window)=='Preparing shaders in background' and
                        win.ui.GetWindow(window,4)==game and window)
                elif case in ('complete','complete-during-race'):
                    view('Preparing shaders in background')
                    if case=='complete-during-race':
                        win.k.SetEvent(event)
                        until(lambda:'outcome=finished' in (storage/'background.txt').read_text(encoding='utf-8-sig'))
                        time.sleep(.4);assert not overlay(),'Completion displayed during race'
                        assert 'complete-notice' not in (storage/'logs/prepare-background-status.txt').read_text()
                        win.k.ResetEvent(event)
                    done=view('Shader preparation complete');shot(done,'complete')
                    ready=view('Shaders ready for next launch');shot(ready,'ready')
                    assert win.ui.GetForegroundWindow()==game
                    win.k.SetEvent(event);until(lambda:not overlay());win.k.ResetEvent(event)
                    view('Shaders ready for next launch')
                else:
                    failed=view('Background preparation incomplete');shot(failed,'incomplete')
                    assert 'complete-notice' not in (storage/'logs/prepare-background-status.txt').read_text()
                results.append(case);print(case+': passed',flush=True)
            finally:
                if event:win.k.CloseHandle(event)
                (storage/'ui-stop').write_text('stop')
                try:owner.wait(timeout=12)
                except subprocess.TimeoutExpired:owner.kill();owner.wait(timeout=10)
            assert owner.returncode==0,(case,owner.returncode)
            assert not win.find(owner.pid,'tourline_background_prepare',visible=False),'Overlay survived launcher exit'
    finally:
        if original:win.ui.SetForegroundWindow(original)
    (root/'validation.json').write_text(json.dumps(dict(passed=results,engine_changed=False,
        scope='Native synthetic UI/process contract; real-game integration recorded separately'),indent=2)+'\n')


if __name__=='__main__':main()
