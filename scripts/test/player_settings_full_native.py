"""Full packed-game frozen automatic preparation in an empty private cache.

Parent-only sequential check. No game entry, cache deletion or game-data copy.
"""
import argparse
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
from pipeline_template import read


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('zip','helper-dir','elf','game','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--aspect',choices=('16:9','21:9'),default='16:9')
    a=ap.parse_args()
    idle()
    out=isolated(a.output)
    if out.exists():raise ValueError('Fresh ignored output required')
    if shutil.disk_usage(out.parent).free<4*1024**3:raise ValueError('Insufficient reserved disk space')
    install,storage=out/'Install',out/'Storage'
    (install/'runtime').mkdir(parents=True);(storage/'input').mkdir(parents=True)
    with zipfile.ZipFile(a.zip) as archive:
        (install/'runtime/gt5p.exe').write_bytes(archive.read('runtime/gt5p.exe'))
    shutil.copytree(a.helper_dir,install/'preparation')
    source=Path(__file__).resolve().parents[2]/'assets/pipeline-templates/gt5p-disc-v2'
    shutil.copytree(source,install/'assets/pipeline-templates/gt5p-disc-v2')
    document=read(source)
    shutil.copyfile(a.elf,storage/'input/EMAIN.ELF')
    settings=storage/'gt5p_settings.toml'
    settings.write_text('[video]\nresolution="1440p"\naspect="'+a.aspect+'"\nmsaa=2\n[game]\nanisotropy=16\nsmooth_colour=true\n')
    original=settings.read_bytes()
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('GT5P_','RSX_'))}
    env.update(PS3_VERBOSE='0',PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    command=[install/'preparation/GT5P-Prepare.exe','--install',install,'--storage',storage,'--game',a.game.resolve()]
    start=time.perf_counter()
    with (out/'prepare.log').open('wb') as log:
        subprocess.run(command,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,
            timeout=2400,creationflags=subprocess.CREATE_NO_WINDOW)
    cache=storage/(storage/'prepared-cache.txt').read_text()
    report=json.loads((cache.parent/'report.json').read_text())
    total=len(document['records'])
    expected_mode='native-scaled' if a.aspect=='16:9' else 'ultrawide-native'
    assert report['counts']==report['additional_translation']['counts']=={'prepared':total}
    extra=report['additional_translation']
    assert extra['translation']==report['player_settings']['mode']==expected_mode
    assert report['player_settings']['requested']=='auto'
    assert report['player_settings']['settings_sha256']==hashlib.sha256(original).hexdigest()
    assert settings.read_bytes()==original
    assert extra['native_counts'][:2]==[extra['unique_pipelines']]*2
    if expected_mode=='native-scaled':assert extra['vertex_preparation']['launches']==0
    result=dict(default=report['counts'],translation=extra,selection=report['player_settings'],
        wall_seconds=time.perf_counter()-start,lookup=report['lookup'],
        fresh_application_cache=True,settings_preserved=True,
        limitation='Observed numeric template only, one GPU, warm OS/driver caches. No live stutter, screenshot or whole-game coverage proof.')
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='translation'},indent=2))


if __name__=='__main__':main()
