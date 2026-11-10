"""Focused scope, deterministic subset/pins and completion/readiness checks; synthetic plus shipped metadata."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
import preparation_quick as q
import pipeline_template as t
from pipeline_warmup_plan import load,read
import player_prepare as p


def main():
    assert q.enabled({}) and not q.enabled({'GT5P_PREPARE_QUICK':'0'})
    for value in ('','2','yes'):
        try:q.enabled({'GT5P_PREPARE_QUICK':value})
        except ValueError:pass
        else:raise AssertionError(value)
    bundle=ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    document=t.read(bundle);plan=load(ROOT/'config/pipeline-warmup/gt5p-disc-v2.json',bundle)
    rows=q.records(document,plan)
    assert {r['key'] for r in rows}==set(plan['phases']['menu'])|set(plan['phases']['race'])
    assert 0<len(rows)<len(document['records'])
    foreign=dict(plan,phases=dict(menu=['f'*64],race=[]))
    try:q.records(document,foreign)
    except ValueError:pass
    else:raise AssertionError('Unknown member accepted')
    with tempfile.TemporaryDirectory(prefix='tourline-quick-') as temp:
        storage=Path(temp);out=storage/'inputs'
        subset,path,adapted=q.stage_inputs(document,plan,out)
        assert t.read(subset)['records']==rows
        assert read(path)==adapted and adapted['template_sha256']==t.template_digest(subset)
        before={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
        assert q.stage_inputs(document,plan,out)==(subset,path,adapted)
        assert before=={p.name:p.read_bytes() for p in out.iterdir() if p.is_file()}
        (storage/'gt5p_settings.toml').write_text('[video]\nresolution="1080p"\naspect="21:9"\nmsaa=8\n')
        key=q.settings_key(storage);assert key['msaa']==8 and key['translation']=='ultrawide-native'
        folder=storage/'preparation'/('a'*24);folder.mkdir(parents=True)
        (storage/'prepared-cache.txt').write_text('preparation/'+'a'*24+'/shadercache')
        (storage/'prepared-identity.txt').write_text('same\n')
        (folder/'preparation-state.json').write_text(json.dumps(dict(phase='complete')))
        with patch.object(p,'release_identity',return_value='same'):
            # Older full preparations continue to count as ready.
            assert p.selected_is_current(storage,storage,full=True)
            q.publish_scope(folder,storage,True,len(rows))
            assert p.selected_is_current(storage,storage) and not p.selected_is_current(storage,storage,full=True)
            (storage/'gt5p_settings.toml').write_text('[video]\nresolution="1080p"\naspect="21:9"\nmsaa=2\n')
            assert not p.selected_is_current(storage,storage)
            q.publish_scope(folder,storage,False,len(document['records']))
            assert p.selected_is_current(storage,storage,full=True)
            (folder/'preparation-scope.json').write_text('{}')
            assert not p.selected_is_current(storage,storage)
    print(f'Quick subset {len(rows)}/{len(document["records"])}; deterministic pin, unknown input rejection, settings identity, quick/full readiness and legacy reuse passed')


if __name__=='__main__':main()
