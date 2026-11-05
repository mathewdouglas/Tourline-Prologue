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
    ap.add_argument('--budget',type=int,default=120,help='seconds per locked attempt; 0 = no budget')
    ap.add_argument('--engine',type=Path,help='engine to prepare with (default scratch/hitch/build)')
    ap.add_argument('--translation',choices=('default','ultrawide-native','native-scaled'),default='default')
    ap.add_argument('--name',default='preparation',help='output folder under scratch/hitch')
    a=ap.parse_args()
    listing=subprocess.check_output(['tasklist','/FI','IMAGENAME eq gt5p.exe'])
    print(listing.decode(errors='replace'),flush=True)
    if b'gt5p.exe' in listing.lower():raise ValueError('Another game is running')
    from pipeline_template import prepare
    from preparation_enumeration import load, sample_share
    home=ROOT/'scratch/hitch';output=home/a.name;game=home/('prepare-game-'+a.name)
    game.mkdir(exist_ok=True)
    ref=Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare')
    original=Path(r'C:\Users\GGPC\Dev\Recomps\GT5P/input')
    (game/'input').mkdir()
    shutil.copyfile(original/'EMAIN.ELF',game/'input/EMAIN.ELF')
    os.environ['GT5P_PREPARE_HASH_LIBRARY']=str(ref/'cache_hash.dll')
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY']=str(ref/'volume_reader.dll')
    template=ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    enumeration=load(ROOT/'assets/shader-enumeration/gt5p-disc-v1',template)
    attempt=len(list(home.glob(f'prepare-{a.name}-*.json')))
    log=home/f'prepare-{a.name}-{attempt:03d}.log'
    engine=(a.engine or home/'build/install/runtime/gt5p.exe').resolve()
    plan=ROOT/'config/pipeline-warmup/gt5p-disc-v2.json' if a.translation=='default' else None
    begin=time.monotonic();last=[0]
    def progress(phase,counts):
        if time.monotonic()-last[0]>5:
            print(phase,counts,flush=True);last[0]=time.monotonic()
            with log.open('a') as stream:stream.write(json.dumps(dict(seconds=time.monotonic()-begin,phase=phase,counts=counts))+'\n')
        if a.budget and time.monotonic()-begin>a.budget:
            raise KeyboardInterrupt('Attribution preparation checkpoint budget')
    code=1
    try:
        report=prepare(template,None,original/'EMAIN.ELF',engine,ref/'decoder.dll',game,output,
            asset_map=template/'player-map.json',volume=original/'pkg/USRDIR/GT.VOL',volume_map=template/'volume-map.json',
            resume=output.exists(),progress=progress,warmup_plan=plan,translation=a.translation,
            shader_packs=plan is not None,enumeration=enumeration,enumeration_sample_share=sample_share())
        assert report['counts']=={'prepared':12669}
        assert report['enumeration']['prepared']+report['enumeration']['failed']==report['enumeration']['requested']
        code=0
        import fast_lookup_table
        report['fast_lookup']=fast_lookup_table.write_for_preparation(output,engine,report)
        print('fast lookup:',json.dumps(report['fast_lookup']),flush=True)
        (home/f'prepared-summary-{a.name}.json').write_text(json.dumps({k:report.get(k) for k in ('counts','enumeration','preparation_seconds','fast_lookup')},indent=2))
    except KeyboardInterrupt:
        code=2
    finally:
        if game.resolve().is_relative_to((ROOT/'scratch').resolve()):shutil.rmtree(game)
        (home/f'prepare-{a.name}-{attempt:03d}.json').write_text(json.dumps(dict(code=code,seconds=time.monotonic()-begin,private_game_removed=not game.exists()),indent=2))
    print(json.dumps(dict(code=code,seconds=time.monotonic()-begin)),flush=True)
    return code


if __name__=='__main__':sys.exit(main())
