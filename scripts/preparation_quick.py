"""Bounded foreground menu/race preparation; full coverage remains a separate generation."""
import json
import os
from pathlib import Path

from preparation_reuse import regular_read


def enabled(environ=None):
    value=(os.environ if environ is None else environ).get('GT5P_PREPARE_QUICK','1')
    if value not in ('0','1'):raise ValueError('GT5P_PREPARE_QUICK must be unset, 0 or 1')
    return value=='1'


def settings_key(storage):
    from preparation_settings import select
    from interp_pipeline_classes import player_settings
    selection=select(storage)
    shape=player_settings(storage)
    if shape is None:raise ValueError('Cannot read settings for focused preparation')
    return dict(translation=selection['mode'],resolution=selection.get('resolution',720),
                aspect=selection.get('aspect','16:9'),msaa=shape[0],
                high_precision=shape[1],anisotropy=shape[2])


def records(document,plan):
    from pipeline_warmup_plan import validate
    validate(plan)
    if document.get('version')!=3 or plan['version']!=2:
        raise ValueError('Quick preparation requires input templates and an input warmup plan')
    keys=set().union(*map(set,plan['phases'].values()))
    selected=[r for r in document['records'] if r['key'] in keys]
    if len(selected)!=len(keys):raise ValueError('Quick plan contains unknown template inputs')
    return selected


def stage_inputs(document,plan,folder):
    """Deterministic private subset plus an equivalently pinned observed plan."""
    from background_preparation import write_subset
    from pipeline_template import template_digest
    from pipeline_warmup_plan import validate
    folder.mkdir(exist_ok=True)
    subset=write_subset(document,records(document,plan),folder/'template')
    adapted=validate(dict(plan,template_sha256=template_digest(subset)))
    path=folder/'plan.json'
    data=json.dumps(adapted,sort_keys=True,separators=(',',':')).encode()
    if path.exists():
        if regular_read(path,1024**2)!=data:raise ValueError('Quick plan changed; existing work preserved')
    else:
        temporary=path.with_suffix('.tmp')
        with temporary.open('xb') as stream:stream.write(data)
        temporary.replace(path)
    return subset,path,adapted


def scope(output):
    """Small completion metadata, independent of the large native proof report."""
    try:
        value=json.loads(regular_read(Path(output)/'preparation-scope.json',65536))
    except FileNotFoundError:return None  # pre-existing preparations are full
    if (not isinstance(value,dict) or set(value)!={'schema','kind','settings','records'} or
            type(value['schema']) is not int or value['schema']!=1 or value['kind'] not in ('quick','full') or
            not isinstance(value['settings'],dict) or type(value['records']) is not int or value['records']<1):
        raise ValueError('Malformed preparation scope; cache preserved')
    return value


def publish_scope(output,storage,quick,count):
    value=dict(schema=1,kind='quick' if quick else 'full',settings=settings_key(storage),records=count)
    path=Path(output)/'preparation-scope.json'
    if path.exists():regular_read(path,65536)
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value,sort_keys=True)+'\n',encoding='utf-8')
    temporary.replace(path)
    return value
