"""Bounded pack verification, publication, cancellation and checkpoint tests."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import preparation_shader_pack as pack
import pipeline_warmup_plan as warmup
from pipeline_runtime_coverage import RESULT_BOOLS
from shader_coverage import fnv64


def reject(call, error=ValueError):
    try:
        call()
    except error:
        return
    raise AssertionError('Invalid pack operation accepted')


def decode(data):
    assert data[:8] == pack.MAGIC
    count, = struct.unpack_from('<I', data, 8)
    result, offset = {}, 12
    for _ in range(count):
        key, size = struct.unpack_from('<QI', data, offset)
        offset += 12
        assert key not in result and size > 0
        result[f'{key:016x}'] = data[offset:offset+size]
        offset += size
    assert offset == len(data)
    return result


def check_defaults():
    import pipeline_template as template
    import player_prepare
    plan_path = Path('plan.json')
    parser = argparse.ArgumentParser()
    parser.add_argument('--warmup-plan', type=Path)
    parser.add_argument('--shader-packs', action=argparse.BooleanOptionalAction, default=None)
    chosen = parser.parse_args(['--warmup-plan', 'plan.json'])
    assert template.packs_enabled(chosen.shader_packs, chosen.warmup_plan) is True
    rolled = parser.parse_args(['--warmup-plan', 'plan.json', '--no-shader-packs'])
    assert template.packs_enabled(rolled.shader_packs, rolled.warmup_plan) is False
    plain = parser.parse_args([])
    assert template.packs_enabled(plain.shader_packs, plain.warmup_plan) is False
    assert template.packs_enabled(None, plan_path) is True
    assert template.packs_enabled(False, plan_path) is False
    assert template.packs_enabled(True, None) is True
    reject(lambda: template.packs_enabled('yes', plan_path))
    bundled = player_prepare.shader_pack_plan('default')
    assert bundled.name == 'gt5p-disc-v2.json' and bundled.is_file()
    assert player_prepare.shader_pack_plan('native-scaled') is None
    assert player_prepare.shader_pack_plan('ultrawide-native') is None
    unpacked = player_prepare.preparation_token('meta', 'ee', 'dd', False)
    bundled_document=warmup.read(bundled)
    packed = player_prepare.preparation_token('meta', 'ee', 'dd', True, bundled_document)
    assert unpacked != packed and len(unpacked) == 24
    assert unpacked == hashlib.sha256(b'metaeedd').hexdigest()[:24]
    reject(lambda:player_prepare.preparation_token('meta','ee','dd',True))
    changed=copy.deepcopy(bundled_document)
    changed['phases']['menu'].reverse()
    assert player_prepare.preparation_token('meta','ee','dd',True,changed)!=packed
    assert player_prepare.preparation_token('meta','ee','dd',True,json.loads(json.dumps(bundled_document,indent=4)))==packed
    with patch.object(player_prepare, 'ROOT', Path('missing-root')):
        reject(lambda: player_prepare.shader_pack_plan('default'))


def check_player_generations(folder, document, report, plan, blobs):
    """Actual helper main + checkpoint/staging, with only native work mocked."""
    import player_prepare as player
    import pipeline_template as template
    import pipeline_asset_map
    from types import SimpleNamespace
    storage=folder/'player-storage';storage.mkdir()
    install=folder/'install'
    (install/'runtime').mkdir(parents=True)
    (install/'preparation').mkdir()
    (install/'runtime/gt5p.exe').write_bytes(b'synthetic engine identity')
    (install/'preparation/decoder.dll').write_bytes(b'synthetic decoder identity')
    plan_path=folder/'player-plan.json';plan_path.write_text(json.dumps(plan))
    calls=[];interrupt=[False]
    def producer(*args):
        calls.append(dict(output=args[7],reuse=args[15]))
        if interrupt[0]:
            interrupt[0]=False
            raise KeyboardInterrupt('synthetic native-stage cancellation')
        cache=args[7]/'shadercache'
        (cache/'warmup-v1').mkdir(parents=True,exist_ok=True)
        for key,data in blobs.items():(cache/(key+'.dxbc')).write_bytes(data)
        for row in report['records']:
            (cache/'warmup-v1'/('pso_'+row['key']+'.recipe')).write_bytes(b'fixture: existence only')
        return copy.deepcopy(report)
    argv=['player_prepare.py','--install',str(install),'--storage',str(storage),'--assets',str(folder)]
    with patch.object(sys,'argv',argv), patch.object(player,'shader_pack_plan',return_value=plan_path), \
            patch.object(player,'select_settings',return_value={'mode':'default'}), \
            patch.object(player,'verify_settings'), patch.object(player,'read_map',return_value={}), \
            patch.object(pipeline_asset_map,'read',return_value={}), \
            patch.object(player.subprocess,'run',return_value=SimpleNamespace(stdout='')), \
            patch.object(template,'read',return_value=document), \
            patch.object(template,'compatibility',return_value={}), \
            patch.object(template,'template_digest',return_value=report['template_sha256']), \
            patch.object(template,'prepare_document',side_effect=producer), \
            patch.dict(os.environ,{'GT5P_PREPARE_REUSE':'1','GT5P_PREPARE_REUSE_HANDOFF':'1'}):
        old_idle=template.idle;old_runner=template.run_offline
        import shader_fragment_batch
        old_fragment_runner=shader_fragment_batch.run_offline
        try:
            player.main()
            pointer=storage/'prepared-cache.txt'
            first=pointer.read_text();original=storage/first
            # A runtime save can reorder identical valid entries and add a
            # genuine learned notifier key. Keep every byte it wrote intact.
            path=original/'menu-shaders-v1.pack'
            entries=decode(path.read_bytes())
            path.write_bytes(pack.MAGIC+struct.pack('<I',len(entries))+b''.join(
                struct.pack('<QI',int(k,16),len(data))+data for k,data in reversed(list(entries.items()))))
            index=original/'warmup-v1/menu-v1.txt'
            index.write_bytes(index.read_bytes()+b'0000000000000002\n')
            snapshot={p:p.read_bytes() for p in original.parent.rglob('*') if p.is_file()}
            # Fork cancellation preserves the selected learned cache/pointer.
            interrupt[0]=True
            reject(player.main,KeyboardInterrupt)
            fork=calls[-1]['output']
            assert fork!=original.parent and pointer.read_text()==first
            assert json.loads((fork/'preparation-state.json').read_text())['phase']=='interrupted'
            assert all(p.read_bytes()==data for p,data in snapshot.items())
            player.main()
            assert calls[-1]['output']==fork and calls[-1]['reuse'] is not None
            assert pointer.read_text()==(fork/'shadercache').relative_to(storage).as_posix()
            assert all(p.read_bytes()==data for p,data in snapshot.items())
            player.main()  # Unchanged cache resumes; no unnecessary generation.
            assert calls[-1]['output']==fork
            assert json.loads((fork/'preparation-state.json').read_text())['attempt']==3
            # A plan-only change chooses a new family and reuses verified work.
            changed=copy.deepcopy(plan);changed['phases']['race'].reverse()
            plan_path.write_text(json.dumps(changed))
            player.main()
            assert calls[-1]['output']!=fork and calls[-1]['reuse'] is not None
        finally:
            template.idle=old_idle;template.run_offline=old_runner
            shader_fragment_batch.run_offline=old_fragment_runner
    # A pack-only change also forks; cancellation remains polled while hashing.
    parent=folder/'player-storage/preparation'
    token=original.parent.name
    index.write_bytes(b'0000000000000001\n')
    assert player.preparation_output(parent,token,plan)==fork
    def cancel(phase,counts):raise KeyboardInterrupt('generation selection cancelled')
    reject(lambda:player.preparation_output(parent,token,plan,cancel),KeyboardInterrupt)
    with patch.object(player,'MAX_GENERATIONS',1):
        reject(lambda:player.preparation_output(parent,token,plan))
    # Native completion is an intermediate checkpoint: a hard owner death
    # before pack/index publication must resume, even with no phase files yet.
    partial_parent=folder/'native-completed-before-publication'
    partial=partial_parent/('e'*24)
    (partial/'shadercache').mkdir(parents=True)
    (partial/'preparation-state.json').write_text(json.dumps({'phase':'complete'}))
    (partial/'report.json').write_text(json.dumps(report))
    assert player.preparation_output(partial_parent,'e'*24,plan)==partial


def main():
    check_defaults()
    root = Path(__file__).resolve().parents[2]
    folder = root/'scratch'/('shader-pack-test-'+uuid.uuid4().hex)
    source = folder/'source'
    source.mkdir(parents=True)
    blobs = {f'{i:016x}': b'DXBC'+bytes([i])*60 for i in (10, 11, 12)}
    for key, data in blobs.items():
        (source/(key+'.dxbc')).write_bytes(data)
    records, rows = [], []
    for n, vs, ps in ((1, 10, 11), (2, 10, 12)):
        words = [0]*164
        words[4] = words[8] = 64
        records.append(dict(key=f'{n:016x}', vp_source=f'{vs:016x}', fp_source=f'{ps:016x}',
            vs=f'{fnv64(blobs[f"{vs:016x}"]):016x}', ps=f'{fnv64(blobs[f"{ps:016x}"]):016x}', native=dict(words=words)))
        result = {name:False for name in RESULT_BOOLS}
        result.update(expected=f'{n:016x}', actual=f'{n:016x}', created=True, hresult='00000000')
        rows.append(dict(key=f'{n:016x}', status='prepared', result=result))
    document = dict(records=records, compatibility={})
    report = dict(schema=1, template_sha256='a'*64, engine_sha256='b'*64, decoder_sha256='c'*64,
        requested=2, records=rows, counts={'prepared':2}, preparation_seconds=1,
        inventory=dict(valid_driver_blobs=[r['key'] for r in rows], rejected=[]))
    plan = dict(schema=warmup.SCHEMA, version=1, template_sha256='a'*64,
        context=warmup.CONTEXT, scope=warmup.SCOPE,
        phases=dict(menu=['0000000000000001'], race=[r['key'] for r in rows]),
        evidence=[dict(source_kind='local-notifier-indices', source_sha256='a'*64,
        report_sha256='b'*64, menu_index_sha256='c'*64, race_index_sha256='d'*64)])
    check_player_generations(folder,document,report,plan,blobs)
    target = folder/'target'
    target.mkdir()
    before = {p:p.read_bytes() for p in source.iterdir()}
    result = pack.stage(plan, document, report, source, destination=target)
    assert result['packs_written'] == 2 and result['unique_shaders'] == 3
    menu = target/'menu-shaders-v1.pack'
    race = target/'race-shaders-v1.pack'
    assert decode(menu.read_bytes()) == {k:blobs[k] for k in list(blobs)[:2]}
    assert decode(race.read_bytes()) == blobs
    saved = {p:p.read_bytes() for p in target.iterdir()}
    assert pack.stage(plan, document, report, source, destination=target, resume=True)['packs_written'] == 0
    assert {p:p.read_bytes() for p in target.iterdir()} == saved  # No resume temp growth.
    reject(lambda:pack.stage(plan, document, report, source, destination=target))
    assert all(p.read_bytes() == data for p,data in before.items())
    empty = folder/'empty'
    empty.mkdir()
    shader = source/'000000000000000c.dxbc'
    shader.write_bytes(b'DXBC'+b'x'*60)
    reject(lambda:pack.stage(plan, document, report, source, destination=empty))
    assert not list(empty.iterdir())  # All dependencies checked before either file.
    shader.write_bytes(blobs['000000000000000c'])
    with patch.object(pack, 'MAX_BYTES', 100):
        reject(lambda:pack.stage(plan, document, report, source, destination=empty))
    with patch.object(pack, 'MAX_ENTRIES', 1):
        reject(lambda:pack.stage(plan, document, report, source, destination=empty))
    bad = copy.deepcopy(document)
    bad['records'][1]['vs'] = 'f'*16
    reject(lambda:pack.stage(plan, bad, report, source, destination=empty))
    bad = copy.deepcopy(plan)
    bad['template_sha256'] = 'e'*64
    reject(lambda:pack.stage(bad, document, report, source, destination=empty))
    bad = copy.deepcopy(report)
    bad['records'][1] = dict(key=rows[1]['key'], status='incompatible', reason='synthetic failure')
    bad['counts'] = {'prepared':1, 'incompatible':1}
    reject(lambda:pack.stage(plan, document, bad, source, destination=empty))
    # An existing learned race pack prevents publishing the missing menu pack.
    learned = empty/'race-shaders-v1.pack'
    learned.write_bytes(b'learned bytes')
    reject(lambda:pack.stage(plan, document, report, source, resume=True, destination=empty))
    assert learned.read_bytes() == b'learned bytes' and not (empty/menu.name).exists()
    partial = folder/'partial'
    partial.mkdir()
    (partial/menu.name).write_bytes(menu.read_bytes())
    assert pack.stage(plan, document, report, source, resume=True, destination=partial)['packs_written'] == 1
    cancelled = folder/'cancelled'
    cancelled.mkdir()
    def cancel(phase, counts):
        raise InterruptedError('test cancel')
    reject(lambda:pack.stage(plan, document, report, source, destination=cancelled, progress=cancel), InterruptedError)
    assert not list(cancelled.iterdir())
    def cancel_write(phase, counts):
        if counts['detail'].startswith('race-shaders'):
            raise InterruptedError('cancel during the second pack write')
    reject(lambda:pack.stage(plan, document, report, source, destination=cancelled, progress=cancel_write), InterruptedError)
    assert not list(cancelled.iterdir())  # No partial packs or abandoned temps.
    with patch.object(pack, 'MAX_SECONDS', -1):
        reject(lambda:pack.stage(plan, document, report, source, destination=cancelled), TimeoutError)
    assert not list(cancelled.iterdir())
    # A hard-linked dependency is refused, without modifying either name.
    link = source/'alias.dxbc'
    os.link(shader, link)
    reject(lambda:pack.stage(plan, document, report, source, destination=cancelled))
    link.unlink()
    # Actual checkpoint integration with a synthetic native producer.
    import pipeline_template as template
    plan_file = folder/'plan.json'
    plan_file.write_text(json.dumps(plan))
    identity = folder/'identity'
    identity.write_text('synthetic helper identity')
    def producer(*args):
        directory = args[7]/'shadercache'
        (directory/'warmup-v1').mkdir(parents=True, exist_ok=True)
        for key, data in blobs.items():
            (directory/(key+'.dxbc')).write_bytes(data)
        for row in rows:
            (directory/'warmup-v1'/('pso_'+row['key']+'.recipe')).write_bytes(b'placeholder')
        return copy.deepcopy(report)
    with patch.object(template, 'idle'), patch.object(template, 'read', return_value=document), \
            patch.object(template, 'compatibility', return_value={}), \
            patch.object(template, 'template_digest', return_value='a'*64), \
            patch.object(template, 'cached_shaders', return_value={}), \
            patch.object(template, 'prepare_document', side_effect=producer) as native:
        def prepare(out, **kwargs):
            return template.prepare(identity, None, identity, identity, identity, folder, out,
                output_validator=lambda p:p, **kwargs)
        enabled = folder/'checkpoint'
        assert prepare(enabled, warmup_plan=plan_file, shader_packs=True)['shader_packs']['packs_written'] == 2
        assert prepare(enabled, warmup_plan=plan_file, shader_packs=True, resume=True)['shader_packs']['packs_written'] == 0
        state = (enabled/'preparation-state.json').read_bytes()
        calls = native.call_count
        reject(lambda:prepare(enabled, warmup_plan=plan_file, resume=True))
        assert native.call_count == calls and (enabled/'preparation-state.json').read_bytes() == state
        reject(lambda:prepare(folder/'no-plan', shader_packs=True))
        assert not (folder/'no-plan').exists()
        disabled = folder/'disabled'
        assert 'shader_packs' not in prepare(disabled, warmup_plan=plan_file)
        assert not list((disabled/'shadercache').glob('*.pack'))
    (folder/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Both-stage packs, checksums, budgets, learned-file preservation, cancellation and checkpoint rollback pass:', folder)


if __name__ == '__main__':
    main()
