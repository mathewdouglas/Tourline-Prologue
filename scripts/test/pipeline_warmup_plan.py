"""Synthetic phase-plan contracts. No game, GPU, compiler or real shader cache."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import uuid
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_warmup_plan as warmup
from pipeline_runtime_coverage import RESULT_BOOLS


def key(n):
    return f'{n:016x}'


def preparation():
    rows = []
    for n in (1, 2, 3):
        result = {name:False for name in RESULT_BOOLS}
        result.update(expected=key(n), actual=key(n), created=True, hresult='00000000')
        rows.append(dict(key=key(n), status='prepared', result=result))
    return dict(schema=1, template_sha256='a'*64, engine_sha256='b'*64, decoder_sha256='c'*64,
                requested=3, records=rows, counts={'prepared':3}, preparation_seconds=1,
                inventory=dict(valid_driver_blobs=[key(i) for i in (1, 2, 3)], rejected=[]))


def rejected(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError('Invalid phase plan accepted')


def main():
    root = Path(__file__).resolve().parents[2]
    folder = root/'scratch'/('warmup-plan-test-'+uuid.uuid4().hex)
    folder.mkdir()
    source = folder/'1-prepared'/'shadercache'/'warmup-v1'
    source.mkdir(parents=True)
    report = preparation()
    raw = json.dumps(report).encode()
    (folder/'preparation.json').write_bytes(raw)
    sha = hashlib.sha256(raw).hexdigest()
    session = dict(conditions=warmup.CONDITIONS, startup_policy='indexed', engine_sha256='d'*64,
        trials=[dict(tag='1-prepared', condition='prepared',
        window=dict(grid_observed_ms=1000, sample_end_ms=91000),
        coverage_condition=dict(prepared_cache_selected=True, reference_report_sha256=sha),
        reference_pipeline_coverage=dict(available=True, provenance=dict(report_sha256=sha)))])
    (folder/'session.json').write_text(json.dumps(session), encoding='utf-8')
    (source/'menu-v1.txt').write_text(key(1)+'\n'+key(1)+'\n'+key(99)+'\n')
    (source/'race-v1.txt').write_text(key(1)+'\n'+key(2)+'\n')
    before = {p:p.read_bytes() for p in (folder/'preparation.json', folder/'session.json',
                                        source/'menu-v1.txt', source/'race-v1.txt')}
    plan, audit = warmup.export(folder/'session.json', '1-prepared', folder/'preparation.json')
    assert plan['phases'] == {'menu':[key(1)], 'race':[key(1), key(2)]}
    assert audit['excluded_unprepared_keys'] == {'menu':1, 'race':0}
    assert all(p.read_bytes() == data for p,data in before.items())
    assert 'dxbc' not in json.dumps(plan) and str(folder) not in json.dumps(plan)
    local, _ = warmup.export_local(source.parent, folder/'preparation.json')
    assert local['phases'] == plan['phases']
    assert local['evidence'][0]['source_kind'] == 'local-notifier-indices'
    assert warmup.merge([plan, plan]) == plan
    rejected(lambda:warmup.merge([plan]*(warmup.MAX_EVIDENCE+1)))
    other = copy.deepcopy(plan)
    other['phases']['race'].append(key(3))
    assert warmup.merge([plan, other])['phases']['race'] == [key(1), key(2), key(3)]
    other['template_sha256'] = 'e'*64
    rejected(lambda:warmup.merge([plan, other]))
    for field, value in [('version', 2), ('version', True), ('context', 'ultrawide'),
                         ('template_sha256', 'bad'), ('phases', {'menu':[], 'race':[]}),
                         ('phases', {'menu':[key(1), key(1)], 'race':[]})]:
        bad = copy.deepcopy(plan)
        bad[field] = value
        rejected(lambda:warmup.validate(bad))
    for data in (b'../bad\n', b'0000000000000000\n', b'BAD\n', b'\n', b'a'*(warmup.MAX_INDEX+1)):
        rejected(lambda:warmup.index(data))
    rejected(lambda:warmup.index((key(1)+'\n').encode()*(warmup.MAX_LINES+1)))
    target = folder/'private-warmup'
    target.mkdir()
    # Placeholders test only staging. Production worker owns recipe/code checks.
    for n in (1, 2):
        (target/('pso_'+key(n)+'.recipe')).write_text('synthetic placeholder')
    changed = dict(report, template_sha256='e'*64)
    rejected(lambda:warmup.stage(plan, changed, target))
    bad = copy.deepcopy(plan)
    bad['phases']['race'].append(key(99))
    rejected(lambda:warmup.stage(bad, report, target))
    assert not (target/'menu-v1.txt').exists()
    staged = warmup.stage(plan, report, target)
    assert staged['unique_keys'] == 2
    assert (target/'menu-v1.txt').read_text() == key(1)+'\n'
    rejected(lambda:warmup.stage(plan, report, target))
    assert warmup.stage(plan, report, target, resume=True)['indices_written'] == 0
    partial = folder/'partial-warmup'
    partial.mkdir()
    for n in (1, 2):
        (partial/('pso_'+key(n)+'.recipe')).write_text('synthetic placeholder')
    (partial/'menu-v1.txt').write_bytes((key(1)+'\n').encode('ascii'))
    (partial/'race-v1.txt.interrupted.tmp').write_text('interrupted metadata')
    assert warmup.stage(plan, report, partial, resume=True)['indices_written'] == 1
    assert (partial/'race-v1.txt.interrupted.tmp').read_text() == 'interrupted metadata'
    session['trials'][0]['warmup_plan'] = staged
    (folder/'session.json').write_text(json.dumps(session))
    rejected(lambda:warmup.export(folder/'session.json', '1-prepared', folder/'preparation.json'))
    session['trials'][0].pop('warmup_plan')
    session['trials'][0]['coverage_condition']['reference_report_sha256'] = 'f'*64
    (folder/'session.json').write_text(json.dumps(session))
    rejected(lambda:warmup.export(folder/'session.json', '1-prepared', folder/'preparation.json'))
    # Exercise real checkpoint/publication integration with a mocked native
    # producer. No shader compiler or game process is started by this test.
    import pipeline_template as template
    plan_file = folder/'plan.json'
    plan_file.write_text(json.dumps(plan))
    identity = folder/'identity.txt'
    identity.write_text('synthetic compiler identity')
    fake_document = dict(compatibility={}, records=[dict(key=key(n)) for n in (1, 2, 3)])
    def native_producer(*args):
        out = args[7]
        directory = out/'shadercache/warmup-v1'
        directory.mkdir(parents=True, exist_ok=True)
        for n in (1, 2, 3):
            (directory/('pso_'+key(n)+'.recipe')).write_text('synthetic placeholder')
        return copy.deepcopy(report)
    with patch.object(template, 'idle'), patch.object(template, 'read', return_value=fake_document), \
            patch.object(template, 'compatibility', return_value={}), \
            patch.object(template, 'template_digest', return_value=report['template_sha256']), \
            patch.object(template, 'cached_shaders', return_value={}), \
            patch.object(template, 'prepare_document', side_effect=native_producer) as producer:
        def prepare(out, **kwargs):
            return template.prepare(identity, None, identity, identity, identity, folder, out,
                                    output_validator=lambda p:p, **kwargs)
        enabled = folder/'checkpoint-enabled'
        result = prepare(enabled, warmup_plan=plan_file)
        assert result['warmup_plan']['unique_keys'] == 2
        result = prepare(enabled, warmup_plan=plan_file, resume=True)
        assert result['warmup_plan']['indices_written'] == 0
        state = (enabled/'preparation-state.json').read_bytes()
        changed = copy.deepcopy(plan)
        changed['phases']['menu'].append(key(3))
        plan_file.write_text(json.dumps(changed))
        calls = producer.call_count
        rejected(lambda:prepare(enabled, warmup_plan=plan_file, resume=True))
        assert producer.call_count == calls
        assert (enabled/'preparation-state.json').read_bytes() == state
        disabled = folder/'checkpoint-disabled'
        result = prepare(disabled)
        assert 'warmup_plan' not in result
        assert not (disabled/'shadercache/warmup-v1/menu-v1.txt').exists()
        assert 'warmup_plan' not in json.loads((disabled/'preparation-state.json').read_text())['contract']
        rejected(lambda:prepare(folder/'unsupported', warmup_plan=plan_file, translation='native-scaled'))
        assert not (folder/'unsupported').exists()
    print('Observed export, bounds, compatibility, unprepared-key rejection, merge and learned-index preservation pass:', folder)


if __name__ == '__main__':
    main()
