"""Locked native strict-reference, source-gate absence and corrupt-resume proof."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipeline_template as template
from pipeline_template_inputs import convert
from train_pipeline_cache import isolated, idle


def snapshot(folder):
    return {str(p.relative_to(folder)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in folder.rglob('*') if p.is_file()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('fixture','reference-template','engine','decoder','volume','volume-library','hash-library','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args()
    for name in vars(a):setattr(a,name,getattr(a,name).resolve())
    idle();out=isolated(a.output)
    if out.exists():raise ValueError('Use a fresh ignored output')
    out.mkdir()
    storage=a.fixture/'Storage'
    pointer=storage/'prepared-cache.txt';selected=pointer.read_bytes()
    source=storage/pointer.read_text();previous=snapshot(source.parent)
    bundle=a.fixture/'Install/assets/pipeline-templates/gt5p-disc-v2'
    document=template.read(bundle)
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY']=str(a.volume_library)
    os.environ['GT5P_PREPARE_HASH_LIBRARY']=str(a.hash_library)
    args=(bundle,None,storage/'input/EMAIN.ELF',a.engine,a.decoder,storage)
    options=dict(asset_map=bundle/'player-map.json',volume=a.volume,volume_map=bundle/'volume-map.json',reuse_cache=source)
    # Every source fingerprint access is a failure in this current-input pass.
    with patch.object(template,'renderer_contract',side_effect=AssertionError('Renderer source hard gate used')):
        report=template.prepare(*args,out/'strict-report',reference_report=source.parent/'report.json',**options)
    total=len(document['records'])
    assert report['counts']=={'prepared':total} and report['strict_reference']
    assert report['fragment_preparation']['processes']==0
    assert report['vertex_preparation']['workers']==0
    assert report['native_counts']==[total]*4 and report['runtime_lookup_counts']==[total]*4
    old=template.read(a.reference_template,legacy=True)
    wanted={r['key'] for r in document['records']}
    old=dict(old,records=[r for r in old['records'] if convert(dict(old,records=[r]))['records'][0]['key'] in wanted])
    old['records'][0]['ps']='f'*16 if old['records'][0]['ps']!='f'*16 else 'e'*16
    bad=out/'bad-reference.json';bad.write_text(json.dumps(old))
    try:template.prepare(*args,out/'reference-rejected',reference_template=bad,**options)
    except ValueError as exc:assert 'Maintainer reference output regression' in str(exc),str(exc)
    else:raise AssertionError('Incorrect reference output accepted')
    assert not (out/'reference-rejected/report.json').exists()
    assert json.loads((out/'reference-rejected/preparation-state.json').read_text())['phase']=='failed'
    cache=out/'strict-report/shadercache'
    shader=next(cache.glob('*.dxbc'));data=bytearray(shader.read_bytes());data[-1]^=1;shader.write_bytes(data)
    with patch.object(template,'run_offline',side_effect=AssertionError('Native started for corrupt shader')):
        try:template.prepare(*args,out/'strict-report',resume=True,reference_report=source.parent/'report.json',**options)
        except ValueError as exc:assert 'resume verification' in str(exc),str(exc)
        else:raise AssertionError('Corrupted derived shader resumed')
    assert shader.read_bytes()==data
    assert pointer.read_bytes()==selected and snapshot(source.parent)==previous
    result=dict(records=total,strict_report=True,incorrect_reference_rejected=True,
        corrupted_resume_rejected=True,source_fingerprint_never_read=True,source_and_selection_preserved=True,
        zero_shader_workers=True,native_counts=report['native_counts'],runtime_lookup_counts=report['runtime_lookup_counts'])
    (out/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
