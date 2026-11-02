"""Synthetic launcher tool handoffs; no game assets or shader compilation."""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

from launcher_native import sfo


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher',type=Path,required=True)
    parser.add_argument('--probe',type=Path,required=True)
    args=parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='Tourline tools ') as folder:
        root=Path(folder);install=root/'Install';home=root/'Home';data=root/'Data';disc=root/'Disc/PS3_GAME'
        for path in (install/'runtime',install/'preparation',install/'assets',home,data/'input',disc/'USRDIR'):
            path.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(args.launcher,install/'tourline-prologue.exe')
        for path in (install/'runtime/gt5p.exe',install/'preparation/GT5P-Prepare.exe'):
            shutil.copyfile(args.probe,path)
        (data/'input/EMAIN.ELF').write_bytes(b'synthetic ELF')
        for name in ('GT.VOL','TV.DAT'):(disc/'USRDIR'/name).write_bytes(b'synthetic volume')
        (disc/'PARAM.SFO').write_bytes(sfo())
        (data/'setup.ini').write_text('[game]\ndirectory='+str(disc)+'\n',encoding='utf-16')
        (home/'storage.ini').write_text('[game]\ndirectory='+str(data)+'\n',encoding='utf-16')
        digest=hashlib.sha256(args.probe.read_bytes()).hexdigest()
        (install/'release.ini').write_text('[release]\nschema=1\ntarget=BCUS98158\nversion=03.00\n'
            'elf_sha256='+hashlib.sha256((data/'input/EMAIN.ELF').read_bytes()).hexdigest()+
            '\ngame_sha256='+digest+'\nprepare_sha256='+digest+'\n')
        env={k:v for k,v in os.environ.items() if not k.startswith(('GT5P_','RSX_','PS3_'))}
        env.update(GT5P_LAUNCHER_HOME=str(home),GT5P_STORAGE_PICKER='0',GT5P_PREPARE_UI='0',PS3_VERBOSE='0')
        for mode in ('collect','verify','prepare'):
            for cancel in ('0','1'):
                output=data/'tool-result.txt'
                if output.exists():output.unlink()  # Synthetic metadata only.
                variant=dict(env,GT5P_PROBE_PIPELINE_ACTION=mode)
                if cancel=='1':variant['GT5P_PROBE_TOOL_CANCEL']='1'
                result=subprocess.run([install/'tourline-prologue.exe'],env=variant,timeout=20)
                assert result.returncode==0
                text=output.read_text(encoding='utf-8-sig')
                if mode=='prepare':assert 'mode=prepare' in text and 'lease=held' in text
                else:
                    assert '--'+('collect-contribution' if mode=='collect' else 'verify-contribution') in text
                    assert 'leases=released' in text
        for extra in ({'GT5P_PIPELINE_TOOLS':'0'},{'GT5P_LAUNCHER_RESTART':'0'},{'RSX_PSO_PROVENANCE':'active-collection'}):
            output=data/'tool-result.txt';output.unlink()
            result=subprocess.run([install/'tourline-prologue.exe'],env=dict(env,GT5P_PROBE_PIPELINE_ACTION='collect',**extra),timeout=20)
            assert result.returncode==0 and not output.exists()
            # Leave a synthetic marker for the next iteration's reset.
            output.write_text('not launched')
        print('Collect/verify/preparation handoff, correct leases, cancellation, rollback and active-collection exclusion passed')


if __name__=='__main__':main()
