"""Budgeted default template + enumeration preparation for attribution routes.

Invoke every resume through run_locked.py. Original packed assets are read-only.
Cancellation happens at owned checkpoint boundaries, retaining verified work.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--budget',type=int,default=120)
    a=ap.parse_args()
    listing=subprocess.check_output(['tasklist','/FI','IMAGENAME eq gt5p.exe'])
    print(listing.decode(errors='replace'),flush=True)
    if b'gt5p.exe' in listing.lower():raise ValueError('Another game is running')
    from pipeline_template import prepare
    from preparation_enumeration import load, sample_share
    home=ROOT/'scratch/hitch';output=home/'preparation';game=home/'prepare-game'
    game.mkdir(exist_ok=True)
    ref=Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare')
    original=Path(r'C:\Users\GGPC\Dev\Recomps\GT5P/input')
    (game/'input').mkdir()
    shutil.copyfile(original/'EMAIN.ELF',game/'input/EMAIN.ELF')
    os.environ['GT5P_PREPARE_HASH_LIBRARY']=str(ref/'cache_hash.dll')
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY']=str(ref/'volume_reader.dll')
    template=ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    enumeration=load(ROOT/'assets/shader-enumeration/gt5p-disc-v1',template)
    attempt=len(list(home.glob('prepare-*.json')))
    log=home/f'prepare-{attempt:03d}.log'
    begin=time.monotonic();last=[0]
    def progress(phase,counts):
        if time.monotonic()-last[0]>5:
            print(phase,counts,flush=True);last[0]=time.monotonic()
            with log.open('a') as stream:stream.write(json.dumps(dict(seconds=time.monotonic()-begin,phase=phase,counts=counts))+'\n')
        if a.budget and time.monotonic()-begin>a.budget:
            raise KeyboardInterrupt('Attribution preparation checkpoint budget')
    code=1
    try:
        report=prepare(template,None,original/'EMAIN.ELF',home/'build/install/runtime/gt5p.exe',ref/'decoder.dll',game,output,
            asset_map=template/'player-map.json',volume=original/'pkg/USRDIR/GT.VOL',volume_map=template/'volume-map.json',
            resume=output.exists(),progress=progress,warmup_plan=ROOT/'config/pipeline-warmup/gt5p-disc-v2.json',
            shader_packs=True,enumeration=enumeration,enumeration_sample_share=sample_share())
        assert report['counts']=={'prepared':12669}
        assert report['enumeration']['prepared']+report['enumeration']['failed']==report['enumeration']['requested']
        code=0
        (home/'prepared-summary.json').write_text(json.dumps({k:report[k] for k in ('counts','enumeration','preparation_seconds')},indent=2))
    except KeyboardInterrupt:
        code=2
    finally:
        if game.resolve().is_relative_to((ROOT/'scratch').resolve()):shutil.rmtree(game)
        (home/f'prepare-{attempt:03d}.json').write_text(json.dumps(dict(code=code,seconds=time.monotonic()-begin,private_game_removed=not game.exists()),indent=2))
    print(json.dumps(dict(code=code,seconds=time.monotonic()-begin)),flush=True)
    return code


if __name__=='__main__':sys.exit(main())
