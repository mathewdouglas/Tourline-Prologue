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
    packed = player_prepare.preparation_token('meta', 'ee', 'dd', True)
    assert unpacked != packed and len(unpacked) == 24
    assert unpacked == hashlib.sha256(b'metaeedd').hexdigest()[:24]
    with patch.object(player_prepare, 'ROOT', Path('missing-root')):
        reject(lambda: player_prepare.shader_pack_plan('default'))


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
