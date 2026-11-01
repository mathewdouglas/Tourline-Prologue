"""Prepare a growing real template, compare fresh/reuse and revalidate all PSOs."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pipeline_template as tool
from train_pipeline_cache import idle,isolated


def snapshot(root):
    return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('template','elf','engine','decoder','game-root','assets','asset-map','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    args=ap.parse_args();idle();base=isolated(args.output)
    if base.exists():ap.error('Choose a new ignored output')
    base.mkdir()
    document=tool.read(args.template)
    assert len(document['records'])>=64
    paths={}
    for count in (32,64):
        path=base/f'template-{count}.json'
        path.write_text(json.dumps(dict(document,records=document['records'][:count])))
        paths[count]=path
    common=[None,*[getattr(args,k).resolve() for k in ('elf','engine','decoder','game_root')]]
    options=dict(assets=args.assets.resolve(),asset_map=args.asset_map.resolve())
    reports=[]
    for tag,count,source in (('base',32,None),('expanded',64,'base'),
                             ('fresh-control',64,None),('all-reused',64,'expanded')):
        out=base/tag
        reuse=base/source/'shadercache' if source else None
        before=snapshot(base/source) if source else None
        if tag=='all-reused':
            with patch('pipeline_template.NativeCompiler',side_effect=AssertionError('Vertex recompiled')):
                report=tool.prepare(paths[count],*common,out,reuse_cache=reuse,**options)
        else:report=tool.prepare(paths[count],*common,out,reuse_cache=reuse,**options)
        assert report['counts']=={'prepared':count}
        if source:assert snapshot(base/source)==before,'Reuse changed its source generation'
        native=(out/'native.log').read_text(errors='replace')
        match=re.search(r'requests=(\d+) created=(\d+) driver_calls=(\d+) cached_blob_calls=(\d+)',native)
        assert match and list(map(int,match.groups()[:3]))==[count]*3
        cached=int(match[4])
        assert cached==({'expanded':32,'all-reused':64}.get(tag,0))
        if tag=='all-reused':
            assert report['resume']['vertex_programs_compiled']==0
            assert report['fragment_preparation']['processes']==0
            assert report['resume']['fragment_jobs_reused']==count
        reports.append(dict(case=tag,records=count,seconds=report['preparation_seconds'],
            cache_reuse=report['cache_reuse'],shaders=report['resume'],
            fragment_preparation=report['fragment_preparation'],native_counts=list(map(int,match.groups()))))
    result=dict(growing_template=True,source_generations_unchanged=True,
                all_native_keys_verified=True,zero_shader_compiles_on_complete_reuse=True,cases=reports)
    (base/'validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Growing-template/fresh parity, exact PSOs, driver hints and read-only source preservation passed')


if __name__=='__main__':main()
