"""Synthetic ownership, confirmation, cancellation and redirection cleanup checks."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('cleanup_impl',Path(__file__).resolve().parents[1]/'preparation_cleanup.py')
cleanup=importlib.util.module_from_spec(spec);spec.loader.exec_module(cleanup)


def fixture(root):
    storage=root/'storage';storage.mkdir()
    for name,phase in (('a'*24,'complete'),('b'*24,'complete'),('c'*24,'interrupted')):
        folder=storage/'preparation'/name
        (folder/'shadercache').mkdir(parents=True)
        (folder/'shadercache/code.bin').write_bytes(b'synthetic shader cache')
        (folder/'preparation.lock').write_bytes(b'\0')
        (folder/'preparation-state.json').write_text(json.dumps(dict(schema=1,phase=phase)))
    (storage/'prepared-cache.txt').write_text('preparation/'+'a'*24+'/shadercache')
    (storage/'shadercache').mkdir();(storage/'shadercache/keep').write_bytes(b'ordinary')
    (storage/'gamedata').mkdir();(storage/'gamedata/keep').write_bytes(b'save')
    return storage


def snapshot(folder):
    return {p.relative_to(folder).as_posix():p.read_bytes() for p in folder.rglob('*') if p.is_file()}


def main():
    with tempfile.TemporaryDirectory(prefix='Tourline-cleanup-') as temp:
        root=Path(temp)
        def fresh(label):
            case=root/label;case.mkdir();return fixture(case)
        for answer in (False,True):
            storage=fresh(str(answer));before=snapshot(storage)
            old=storage/'preparation'/('b'*24)
            expected=sum(p.stat().st_size for p in old.rglob('*') if p.is_file())
            calls=[]
            def ask(size,count):
                assert (size,count)==(expected,1)
                calls.append(1);return answer
            cleanup.schedule(storage);cleanup.offer(storage,lambda:None,ask)
            assert bool(old.exists()) != answer
            assert calls==[1]
            # No second prompt for a repeated successful preparation of this generation.
            cleanup.schedule(storage);assert not (storage/cleanup.PENDING).exists()
            after=snapshot(storage)
            for name,data in before.items():
                if answer and name.startswith('preparation/'+'b'*24+'/'):continue
                assert after[name]==data,name
        storage=fresh('disabled')
        with patch.dict(os.environ,GT5P_PREPARE_CLEANUP='0'):
            cleanup.schedule(storage);assert not (storage/cleanup.PENDING).exists()
        storage=fresh('not-completed')
        state=storage/'preparation'/('a'*24)/'preparation-state.json'
        state.write_text(json.dumps(dict(schema=1,phase='interrupted')))
        try:cleanup.schedule(storage)
        except ValueError:pass
        else:raise AssertionError('Incomplete preparation scheduled cleanup')
        storage=fresh('changed-selection');cleanup.schedule(storage)
        (storage/'prepared-cache.txt').write_text('preparation/'+'b'*24+'/shadercache')
        before=snapshot(storage)
        cleanup.offer(storage,lambda:None,lambda *_:(_ for _ in ()).throw(AssertionError('stale offer')))
        before.pop(cleanup.PENDING);assert snapshot(storage)==before
        storage=fresh('change-during-dialog');cleanup.schedule(storage)
        def change(*_):
            (storage/'preparation'/('b'*24)/'new-file').write_bytes(b'changed');return True
        try:cleanup.offer(storage,lambda:None,change)
        except ValueError:pass
        else:raise AssertionError('Changed generation deleted')
        assert (storage/'preparation'/('b'*24)/'shadercache/code.bin').exists()
        storage=fresh('game-running');cleanup.schedule(storage);before=snapshot(storage)
        def busy():raise ValueError('Another game running')
        try:cleanup.offer(storage,busy,lambda *_:True)
        except ValueError:pass
        else:raise AssertionError('Game guard ignored')
        assert snapshot(storage)==before
        storage=fresh('hardlink');cleanup.schedule(storage)
        outside=root/'outside.bin';outside.write_bytes(b'never remove')
        os.link(outside,storage/'preparation'/('b'*24)/'linked')
        try:cleanup.offer(storage,lambda:None,lambda *_:True)
        except ValueError:pass
        else:raise AssertionError('Hardlink accepted')
        assert outside.read_bytes()==b'never remove'
        storage=fresh('junction');cleanup.schedule(storage)
        outside_dir=root/'outside';outside_dir.mkdir();(outside_dir/'keep').write_bytes(b'keep')
        link=storage/'preparation'/('b'*24)/'redirect'
        if os.name=='nt':
            subprocess.run(['cmd','/d','/c','mklink','/J',str(link),str(outside_dir)],check=True,capture_output=True)
        else:link.symlink_to(outside_dir,target_is_directory=True)
        try:
            try:cleanup.offer(storage,lambda:None,lambda *_:True)
            except ValueError:pass
            else:raise AssertionError('Redirected tree accepted')
            assert (outside_dir/'keep').read_bytes()==b'keep'
        finally:
            if os.name=='nt':subprocess.run(['cmd','/d','/c','rmdir',str(link)],check=True)
            else:link.unlink()
        storage=fresh('locked');cleanup.schedule(storage)
        with cleanup.generation_lock(storage/'preparation'/('b'*24)):
            cleanup.offer(storage,lambda:None,lambda *_:(_ for _ in ()).throw(AssertionError('locked cache offered')))
        assert (storage/'preparation'/('b'*24)).exists()
    print('Cleanup: keep/remove, exact size, repeat, disabled, incomplete, selection changes, game guard, hardlink, junction and lock passed')


def native_dialogs(helper=None):
    import ctypes as C
    from ctypes import wintypes as W
    ui=C.WinDLL('user32')
    callback=C.WINFUNCTYPE(W.BOOL,W.HWND,W.LPARAM)
    ui.EnumWindows.argtypes=[callback,W.LPARAM];ui.EnumChildWindows.argtypes=[W.HWND,callback,W.LPARAM]
    ui.GetWindowThreadProcessId.argtypes=[W.HWND,C.POINTER(W.DWORD)]
    ui.GetWindowTextW.argtypes=[W.HWND,W.LPWSTR,C.c_int]
    ui.PostMessageW.argtypes=[W.HWND,W.UINT,W.WPARAM,W.LPARAM]
    with tempfile.TemporaryDirectory(prefix='Tourline-cleanup-dialog-') as temp:
        for answer in (6,7):
            root=Path(temp)/str(answer);root.mkdir();storage=fixture(root);cleanup.schedule(storage)
            command=([str(helper),'--offer-cache-cleanup','--install',str(root),
                      '--storage',str(storage),'--game',str(root)] if helper else
                     [sys.executable,str(Path(__file__).resolve()),'--dialog',str(storage)])
            owner=subprocess.Popen(command,env=dict(os.environ,GT5P_PREPARE_CLEANUP='1'))
            seen=[]
            @callback
            def visit(hwnd,unused):
                pid=W.DWORD();ui.GetWindowThreadProcessId(hwnd,C.byref(pid))
                actual=storage/'dialog.pid'
                expected=int(actual.read_text()) if actual.exists() else owner.pid
                if pid.value!=expected:return True
                title=C.create_unicode_buffer(256);ui.GetWindowTextW(hwnd,title,len(title))
                if title.value!='Tourline Prologue - old shader caches':return True
                texts=[]
                @callback
                def child(control,unused):
                    value=C.create_unicode_buffer(4096);ui.GetWindowTextW(control,value,len(value))
                    texts.append(value.value);return True
                ui.EnumChildWindows(hwnd,child,0)
                text='\n'.join(texts)
                assert '0.00 GB' in text and 'Choose No' in text and 'saves and settings will be kept' in text,text
                seen.append(text);ui.PostMessageW(hwnd,0x111,answer,0);return True
            try:
                deadline=time.monotonic()+30
                while owner.poll() is None and time.monotonic()<deadline:
                    ui.EnumWindows(visit,0);time.sleep(.03)
                assert owner.poll()==0,(owner.poll(),seen)
                assert seen,'Native cleanup prompt missing'
                assert (storage/'preparation'/('b'*24)).exists()==(answer==7)
                assert (storage/'preparation'/('a'*24)/'shadercache/code.bin').exists()
            finally:
                if owner.poll() is None:owner.kill();owner.wait()
    print('Native cleanup Yes/No dialogs passed'+(' (frozen helper)' if helper else ''))


if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--dialog':
        storage=Path(sys.argv[2]);(storage/'dialog.pid').write_text(str(os.getpid()))
        cleanup.offer(storage,lambda:None)
    elif len(sys.argv)>1 and sys.argv[1]=='--native':native_dialogs(Path(sys.argv[2]) if len(sys.argv)>2 else None)
    else:main()
