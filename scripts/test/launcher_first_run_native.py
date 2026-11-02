"""First-run choices against owned synthetic children; never starts the game."""
import argparse
import ctypes as C
from ctypes import wintypes as W
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

from launcher_native import sfo


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--launcher', type=Path, required=True)
    ap.add_argument('--probe', type=Path, required=True)
    args = ap.parse_args()
    ui = C.WinDLL('user32')
    callback = C.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    ui.EnumWindows.argtypes = [callback, W.LPARAM]
    ui.EnumChildWindows.argtypes = [W.HWND, callback, W.LPARAM]
    ui.GetClassNameW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    ui.GetDlgCtrlID.argtypes = [W.HWND]
    ui.GetWindowThreadProcessId.argtypes = [W.HWND, C.POINTER(W.DWORD)]
    ui.GetWindowTextW.argtypes = [W.HWND, W.LPWSTR, C.c_int]
    ui.GetDlgItem.argtypes = [W.HWND, C.c_int]
    ui.GetDlgItem.restype = W.HWND
    ui.SetWindowTextW.argtypes = [W.HWND, W.LPCWSTR]
    ui.PostMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    ui.SendMessageW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    with tempfile.TemporaryDirectory(prefix='Tourline first run ') as temp:
        root = Path(temp)
        install, disc = root/'Install', root/'Game/PS3_GAME'
        (install/'runtime').mkdir(parents=True)
        (install/'preparation').mkdir()
        (install/'assets').mkdir()
        (install/'assets/probe.txt').write_text('synthetic distributable art')
        (disc/'USRDIR').mkdir(parents=True)
        (disc/'PARAM.SFO').write_bytes(sfo())
        for name in ('GT.VOL', 'TV.DAT'):
            (disc/'USRDIR'/name).write_bytes(b'synthetic')
        launcher = install/'tourline-prologue.exe'
        shutil.copyfile(args.launcher, launcher)
        for destination in ('runtime/gt5p.exe', 'preparation/GT5P-Prepare.exe'):
            shutil.copyfile(args.probe, install/destination)
        elf = b'\x7fELF synthetic first-run executable'
        probe_hash = hashlib.sha256(args.probe.read_bytes()).hexdigest()
        (install/'release.ini').write_text('[release]\nschema=1\ntarget=BCUS98158\nversion=03.00\n'
            +'elf_sha256='+hashlib.sha256(elf).hexdigest()+'\ngame_sha256='+probe_hash
            +'\nprepare_sha256='+probe_hash+'\n')
        for label, choice in [('prepare',100), ('skip',101), ('close',0),
                              ('cancel-preparation',100), ('cancel-legacy',100),
                              ('helper-unavailable',100), ('offer-disabled',None), ('cancel-setup',None)]:
            data = root/label
            (data/'input').mkdir(parents=True)
            (data/'input/EMAIN.ELF').write_bytes(elf)
            env = dict(os.environ, GT5P_USER_DIR=str(data), PS3_VERBOSE='0',
                       GT5P_PROBE_DELAY_MS='100',
                       GT5P_PROBE_PREPARE_DELAY_MS='30000' if label.startswith('cancel-') else '100')
            env.pop('GT5P_PREPARE_OFFER',None)
            env.pop('GT5P_PREPARE_UI',None)
            if label=='offer-disabled': env['GT5P_PREPARE_OFFER']='0'
            if label=='cancel-legacy': env['GT5P_PREPARE_UI']='0'
            release=install/'release.ini'
            release_text=release.read_text()
            if label=='helper-unavailable':
                release.write_text(release_text.replace('prepare_sha256='+probe_hash,'prepare_sha256='+'0'*64))
            owner = subprocess.Popen([launcher], env=env)
            seen, picked, offered, cancelled = set(), False, False, False
            picker_seen = None
            @callback
            def visit(hwnd, unused):
                nonlocal picked, offered, cancelled, picker_seen
                pid = W.DWORD()
                ui.GetWindowThreadProcessId(hwnd,C.byref(pid))
                if pid.value!=owner.pid: return True
                title = C.create_unicode_buffer(512)
                ui.GetWindowTextW(hwnd,title,len(title))
                seen.add(title.value)
                if title.value=='Select your GT5P dump folder (or its PS3_GAME folder)' and not picked:
                    if picker_seen is None: picker_seen=time.monotonic()
                    if time.monotonic()-picker_seen<.7: return True
                    if label=='cancel-setup': ui.PostMessageW(hwnd,0x10,0,0)
                    else:
                        edits = []
                        @callback
                        def child(control, unused):
                            cls = C.create_unicode_buffer(128)
                            ui.GetClassNameW(control,cls,len(cls))
                            if cls.value=='Edit':
                                edits.append((ui.GetDlgCtrlID(control),control))
                            return True
                        ui.EnumChildWindows(hwnd,child,0)
                        edit = next((h for i,h in edits if i==1152),None)
                        if not edit and edits: edit=edits[0][1]
                        if not edit: return True
                        ui.SetWindowTextW(edit,'')
                        for character in str(disc): ui.SendMessageW(edit,0x102,ord(character),0)
                        ui.PostMessageW(ui.GetDlgItem(hwnd,1),0xF5,0,0)
                    picked = True
                elif title.value=='Tourline Prologue' and not offered:
                    assert picked and (data/'setup.ini').is_file(), 'Offer precedes completed setup'
                    assert not (data/'probe.txt').exists(), 'Child started before offer'
                    if choice: ui.PostMessageW(hwnd,0x400+102,choice,0)
                    else: ui.PostMessageW(hwnd,0x10,0,0)
                    offered = True
                elif title.value=='Tourline Prologue' and offered and label in ('cancel-preparation','cancel-legacy') and not cancelled and (data/'logs/prepare.out').exists():
                    ui.PostMessageW(hwnd,0x400+102,2,0)
                    cancelled = True
                elif title.value=='GT5P setup' and label=='helper-unavailable':
                    ui.PostMessageW(hwnd,0x111,2,0)
                return True
            try:
                deadline = time.monotonic()+25
                while owner.poll() is None and time.monotonic()<deadline:
                    ui.EnumWindows(visit,0)
                    if (data/'logs/setup.err').exists() and label!='helper-unavailable':
                        raise AssertionError((label,(data/'logs/setup.err').read_text()))
                    time.sleep(.03)
                assert owner.poll() is not None, (label,'timed out',seen)
                assert owner.returncode==0,(label,owner.returncode,seen)
                if label=='cancel-setup':
                    assert not offered and not (data/'probe.txt').exists()
                    assert not (data/'setup.ini').exists()
                else:
                    assert offered==(choice is not None),(label,seen)
                    probe = dict(line.split('=',1) for line in (data/'probe.txt').read_text(encoding='utf-8-sig').splitlines())
                    assert probe['argc']=='2' and Path(probe['arg1'])==data/'input/EMAIN.ELF'
                    assert (data/'logs/prepare.out').exists()==(choice==100 and label!='helper-unavailable')
                    if label in ('cancel-preparation','cancel-legacy'): assert cancelled and (data/'prepare.cancel').exists()
                    if label=='helper-unavailable': assert 'helper is missing or does not match' in (data/'logs/setup.err').read_text()
                    # Once configured, ordinary launches do not offer again.
                    done = subprocess.run([launcher],env=dict(env,GT5P_PROBE_DELAY_MS='0'),timeout=10)
                    assert done.returncode==0
                print(label+': passed')
            finally:
                if owner.poll() is None: owner.terminate(); owner.wait(timeout=10)
                release.write_text(release_text)


if __name__=='__main__': main()
