"""Synthetic coverage contract. Does not launch the game or compile shaders."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_runtime_coverage as coverage

ROOT = Path(__file__).resolve().parents[2]
BOOLS = ('material_requested', 'material_applied', 'pass_requested', 'pass_applied',
         'native_requested', 'native_applied', 'prepare_requested', 'prepared',
         'input_requested', 'input_applied')


def key(number):
    return f'{number:016x}'


def native_result(identifier, created=True, actual=None):
    result = {name: False for name in BOOLS}
    result.update(expected=identifier, actual=identifier if actual is None else actual,
                  created=created, hresult='00000000')
    return result


def prepared(identifier):
    return dict(key=identifier, status='prepared', result=native_result(identifier))


def report(rows, blobs=None, translation=None, **extra):
    counts = {}
    for row in rows:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    ready = [row['key'] for row in rows if row['status'] == 'prepared']
    document = dict(schema=1, template_sha256='ab' * 32, engine_sha256='cd' * 32, decoder_sha256='ef' * 32,
                    requested=len(rows), records=rows, counts=counts, preparation_seconds=1.25,
                    inventory=dict(recipes=list(ready), valid_driver_blobs=list(ready if blobs is None else blobs),
                                   rejected=[]))
    if translation is not None:
        document['additional_translation'] = translation
    document.update(extra)
    return document


def translation(pairs, mode='ultrawide-native', native=None, cached=0):
    records = [dict(template_key=left, key=right, vp_source='a' * 16, fp_source='b' * 16) for left, right in pairs]
    unique = len({right for _, right in pairs})
    return dict(translation=mode, counts={'prepared': len(records)}, unique_pipelines=unique, records=records,
                root_signature='c' * 16, seconds=2.0,
                native_counts=[unique, unique, unique, cached] if native is None else native,
                limitation='synthetic')


def use(identifier, outcome=None):
    return f'[pipeline-use] key={identifier}' + (f' outcome={outcome}' if outcome else '')


def summary(count, pending=0, truncated=0):
    return (f'[pipeline-use-summary] format=1 unique={count} recorded={count} '
            f'truncated={truncated} pending_shader_draws={pending}')


def metrics(shader, driver, cached, demand, done, loaded, warm, resident):
    return (f'[pipeline-metrics] shader_compiles={shader} driver_calls={driver} cached_calls={cached} '
            f'demand_queued={demand} demand_done={done} warm_loaded={loaded} warm_hits={warm} resident={resident}')


def assess(text, document):
    return coverage.assess(text, document, dict(sample=True))


def withheld(document, fragment):
    assert document['available'] is False, document['reason']
    assert document['coverage'] is None
    assert document['gpu_residency'] is None and document['stutter'] is None
    assert fragment in document['reason']
    blob = json.dumps(document)
    assert '"ratio"' not in blob and '0%' not in blob and '100%' not in blob
    assert 'GPU residency' in blob and 'pending_shader_draws' in blob


def test_parser_matches_existing_metrics():
    source = (ROOT / 'scripts/test/shader_stutter.py').read_text(encoding='utf-8')
    assert coverage.METRIC_RE.pattern in source
    assert coverage.METRIC_NOTE in source


def test_default_and_translation_are_separate_from_disk_and_residency():
    default_a, default_b = key(1), key(2)
    derived_c, missed, blob_only = key(3), key(4), key(5)
    shader_id = 'a' * 16
    rows = [prepared(default_a), prepared(default_b),
            dict(key=missed, status='unresolved-program'),
            dict(key=key(6), status='incompatible', reason='synthetic'),
            dict(key=key(7), status='key-rejected', result=native_result(key(7), created=False, actual=key(8)))]
    document = report(rows, blobs=[default_a, default_b, blob_only],
                      translation=translation([(default_a, default_a), (default_b, derived_c)], cached=1),
                      player_settings=dict(schema=1, mode='native-scaled', settings_sha256='12' * 32,
                                           resolution=1440, aspect='16:9'))
    text = '\n'.join([
        metrics(1, 1, 0, 1, 0, 0, 50, 0),
        use(default_a, 'warm_hit'), summary(1, pending=1),
        summary(1, pending=1),
        use(derived_c), summary(2, pending=9),
        use(missed, 'demand'), summary(3, pending=9),
        use(blob_only), summary(4, pending=9),
        use(shader_id), summary(5, pending=9),
        metrics(7, 9, 3, 4, 2, 1, 99, 8),
    ]) + '\n'
    result = assess(text, document)
    assert result['available'] is True and result['reason'] is None
    assert result['coverage'] == dict(requested_unique=5, prepared_intersection=2, ratio='2/5', percent=40.0)
    assert result['misses'] == [missed, blob_only, shader_id] and result['miss_count'] == 3
    assert result['successful_preparation_keys'] == 3
    assert result['successful_default_keys'] == 2 and result['successful_translation_keys'] == 2
    assert result['valid_driver_blob_count'] == 3
    assert result['pending_shader_draws'] == 9 and result['denominator_excludes'] == 'pending_shader_draws'
    assert result['outcome_lines'] == dict(warm_hit=1, demand=1, omitted=3)
    assert result['gpu_residency'] is None and result['shader_compilation'] is None
    assert result['runtime_counters']['warm_hits'] == 99 and result['runtime_counters']['shader_compiles'] == 7
    assert result['runtime_counters']['resident'] == 8
    assert result['runtime_counters']['warm_hits'] != result['coverage']['prepared_intersection']
    assert 'do not show that a prepared key avoided a hitch' in result['runtime_counters_note']
    assert result['translation']['mode'] == 'ultrawide-native'
    assert result['translation']['native_batch'] == dict(requests=2, created=2, driver_calls=2, cached_blob_calls=1)
    assert result['player_settings']['mode'] == 'native-scaled' and result['player_settings']['interpreted'] is True
    assert result['summaries'] == 6
    assert result['provenance']['template_sha256'] == 'ab' * 32
    assert 'not the numerator' in result['disk_note']
    joined = '\n'.join(result['limitations'])
    assert 'not GPU residency' in joined and 'excluded from the denominator' in joined
    assert 'offline creation counts' in joined


def test_measured_extremes_keep_residency_unknown():
    identifier = key(1)
    document = report([prepared(identifier)])
    full = assess('\n'.join([use(identifier), summary(1)]) + '\n', document)
    assert full['available'] is True and full['coverage']['ratio'] == '1/1'
    assert full['gpu_residency'] is None and full['miss_count'] == 0
    empty = assess('\n'.join([use(key(2)), summary(1)]) + '\n', document)
    assert empty['available'] is True and empty['coverage']['ratio'] == '0/1'
    assert empty['misses'] == [key(2)]


def test_cumulative_snapshot_and_bad_metrics_do_not_invent_coverage():
    identifier = key(1)
    text = '\n'.join([
        summary(0, pending=1),
        use(identifier), summary(1, pending=2),
        summary(1, pending=6),
        '[pipeline-metrics] shader_compiles=nope',
        metrics(3, 3, 1, 1, 1, 0, 4, 0),
    ]) + '\n'
    result = assess(text, report([prepared(identifier)]))
    assert result['available'] is True and result['coverage']['ratio'] == '1/1'
    assert result['pending_shader_draws'] == 6 and result['summaries'] == 3
    assert result['runtime_counters']['shader_compiles'] == 3
    assert 'did not match the existing parser' in result['runtime_counters_note']
    no_sample = assess(use(identifier) + '\n' + summary(1) + '\n[pipeline-metrics] broken\n', report([prepared(identifier)]))
    assert no_sample['available'] is True and no_sample['runtime_counters'] is None
    assert no_sample['coverage']['ratio'] == '1/1'


def test_unusable_logs_withhold_the_ratio():
    good = report([prepared(key(1))])
    cases = [
        ('noise only\n', 'no pipeline-use-summary'),
        (use(key(1)) + '\n', 'no pipeline-use-summary'),
        ('\n'.join([use(key(1)), summary(1, truncated=1)]) + '\n', 'truncated'),
        ('\n'.join([use(key(1)), use(key(1)), summary(1)]) + '\n', 'duplicate pipeline-use key'),
        ('[pipeline-use] key=' + 'A' * 16 + '\n' + summary(1) + '\n', 'malformed pipeline-use key'),
        ('[pipeline-use] key=abc\n', 'malformed pipeline-use key'),
        (use(key(1), 'resident') + '\n', 'malformed pipeline-use key'),
        ('\n'.join([use(key(1)), summary(1), use(key(2))]) + '\n', 'exceed the final summary'),
        ('\n'.join([use(key(1)), summary(2)]) + '\n', 'does not match records so far'),
        ('\n'.join([use(key(1)), summary(1, truncated=1), use(key(2)), summary(2)]) + '\n', 'not a cumulative snapshot'),
        (summary(0) + '\n', 'no complete native keys'),
        ('[pipeline-use-summary] format=2 unique=1 recorded=1 truncated=0 pending_shader_draws=0\n',
         'malformed pipeline-use-summary'),
        ('[pipeline-use-summary] format=1 unique=2 recorded=1 truncated=0 pending_shader_draws=0\n',
         'unique and recorded disagree'),
        (use(key(1)) + ' [pipeline-use-summary] format=1 unique=1 recorded=1 truncated=0 pending_shader_draws=0\n',
         'malformed pipeline-use line'),
    ]
    for text, fragment in cases:
        withheld(assess(text, good), fragment)


def test_reports_accept_only_successful_rows():
    ready = prepared(key(1))
    base_log = use(key(1)) + '\n' + summary(1) + '\n'
    withheld(assess(base_log, dict(schema='gt5p-pipeline-template', records=[dict(key=key(1))])), 'template membership')
    withheld(assess(base_log, report([], **{'counts': {'template-rejected': 1}, 'template_sha256': None, 'requested': 0})),
             'rejected its template')
    withheld(assess(base_log, report([ready], preparation_seconds=None)), 'incomplete preparation report')
    changed = prepared(key(1))
    changed['result']['actual'] = key(2)
    withheld(assess(base_log, report([changed])), 'failed native key validation')
    withheld(assess(base_log, report([ready], blobs=[key(9)])), 'no validated driver blob')
    fake = dict(key=key(1), status='key-rejected', result=native_result(key(1)))
    withheld(assess(base_log, report([fake])), 'successful native result')
    withheld(assess(base_log, report([ready, prepared(key(1))])), 'duplicate preparation record key')
    withheld(assess(base_log, report([ready], translation=translation([(key(1), key(3))], native=[1, 0, 1, 0]))),
             'native batch')
    missing_native = translation([(key(1), key(3))])
    del missing_native['native_counts']
    withheld(assess(base_log, report([ready], translation=missing_native)), 'unsupported additional_translation')
    withheld(assess(base_log, report([ready], translation=translation([(key(2), key(3))]))),
             'not tied to a successful default')
    withheld(assess(base_log, report([ready], translation=dict(translation='default'))), 'unsupported additional_translation')
    dirty = report([ready])
    dirty['inventory']['rejected'] = [dict(file='pso_x.recipe', reason='bad')]
    withheld(assess(base_log, dirty), 'driver inventory')
    mismatched = report([ready])
    mismatched['counts'] = {'prepared': 2}
    withheld(assess(base_log, mismatched), 'counts do not match')
    withheld(assess(base_log, dict(translation='ultrawide-native', records=[])), 'unsupported preparation report schema')
    # A failed sibling stays out of the numerator while a validated row still counts.
    mixed = report([ready, dict(key=key(4), status='unresolved-program')])
    result = assess('\n'.join([use(key(1)), use(key(4)), summary(2)]) + '\n', mixed)
    assert result['available'] is True and result['coverage']['ratio'] == '1/2'
    assert result['misses'] == [key(4)] and result['successful_preparation_keys'] == 1


def test_bounds_and_duplicate_derived_key():
    old = coverage.MAX_KEYS
    coverage.MAX_KEYS = 1
    try:
        withheld(assess('\n'.join([use(key(1)), use(key(2)), summary(2)]) + '\n', report([prepared(key(1))])),
                 'key count exceeds its bound')
    finally:
        coverage.MAX_KEYS = old
    shared = key(3)
    document = report([prepared(key(1)), prepared(key(2))],
                      translation=translation([(key(1), shared), (key(2), shared)]))
    result = assess('\n'.join([use(shared), summary(1)]) + '\n', document)
    assert result['available'] is True and result['coverage']['ratio'] == '1/1'
    assert result['successful_translation_keys'] == 1 and result['successful_preparation_keys'] == 3


def test_cli_writes_ignored_output_without_touching_inputs():
    base = ROOT / 'scratch' / f'pipeline-runtime-coverage-{os.getpid()}'
    if base.exists():
        raise AssertionError('refusing to reuse an existing coverage directory')
    inputs = base / 'inputs'
    output = base / 'out'
    forbidden = ROOT / 'scripts' / 'pipeline-runtime-coverage-not-ignored'
    if forbidden.exists():
        raise AssertionError('refusing to use an existing forbidden-output fixture')
    try:
        inputs.mkdir(parents=True)
        log_path, report_path = inputs / 'game.err', inputs / 'report.json'
        text = use(key(1)) + '\n' + summary(1, pending=3) + '\n'
        document = report([prepared(key(1))])
        log_path.write_bytes(text.encode())
        report_path.write_bytes((json.dumps(document) + '\n').encode())
        log_path.chmod(stat.S_IREAD)
        report_path.chmod(stat.S_IREAD)
        before = (log_path.stat().st_mtime_ns, report_path.stat().st_mtime_ns, log_path.read_bytes(), report_path.read_bytes())
        assert coverage.main(['--log', str(log_path), '--report', str(report_path), '--output', str(output)]) == 0
        written = json.loads((output / 'coverage.json').read_text(encoding='utf-8'))
        assert written['available'] is True and written['coverage']['ratio'] == '1/1'
        assert written['provenance']['inputs_unchanged'] is True
        assert written['provenance']['log_sha256'] == hashlib.sha256(before[2]).hexdigest()
        assert written['provenance']['report_sha256'] == hashlib.sha256(before[3]).hexdigest()
        assert written['pending_shader_draws'] == 3 and written['gpu_residency'] is None
        assert (log_path.stat().st_mtime_ns, report_path.stat().st_mtime_ns, log_path.read_bytes(), report_path.read_bytes()) == before
        ignored = __import__('subprocess').run(['git', 'check-ignore', '-q', str(output / 'coverage.json')], cwd=ROOT)
        assert ignored.returncode == 0
        try:
            coverage.main(['--log', str(log_path), '--report', str(report_path), '--output', str(forbidden)])
        except SystemExit as exc:
            assert exc.code == 2
        else:
            raise AssertionError('non-ignored output accepted')
        assert not forbidden.exists()
        broken = inputs / 'broken.json'
        broken.write_text('{', encoding='utf-8')
        second = base / 'rejected-out'
        assert coverage.main(['--log', str(log_path), '--report', str(broken), '--output', str(second)]) == 0
        rejected = json.loads((second / 'coverage.json').read_text(encoding='utf-8'))
        withheld(rejected, 'not UTF-8 JSON')
        assert log_path.read_bytes() == before[2]
    finally:
        if forbidden.exists():
            assert forbidden.resolve().is_relative_to(ROOT.resolve()) and not forbidden.is_junction()
            forbidden.chmod(stat.S_IWRITE)
            shutil.rmtree(forbidden)
        if base.exists():
            assert base.resolve().is_relative_to((ROOT/'scratch').resolve()) and not base.is_junction()
            for path in base.rglob('*'):
                path.chmod(stat.S_IWRITE)
            shutil.rmtree(base)


def test_native_counter_and_failure_edges():
    # The producer confirms requested/created keys. Driver work is separate:
    # warm memory hits can avoid a call; a stale driver blob can need a retry.
    for native in ([1, 1, 0, 0], [1, 1, 2, 1]):
        document = report([prepared(key(1))],
                          translation=translation([(key(1), key(2))], native=native))
        result = assess(use(key(2))+'\n'+summary(1), document)
        assert result['available'] and result['coverage']['ratio'] == '1/1'
        assert result['translation']['native_batch']['driver_calls'] == native[2]
    for native in ([1, 0, 0, 0], [1, 1, 0, 1], [1, 1, -1, 0], [1, 1, coverage.MAX_PENDING+1, 0]):
        document = report([prepared(key(1))],
                          translation=translation([(key(1), key(2))], native=native))
        withheld(assess(use(key(2))+'\n'+summary(1), document), 'native batch')
    # Native FNV keys can theoretically be zero; still a valid observed miss.
    result = assess(use('0'*16)+'\n'+summary(1, pending=20_000_000), report([prepared(key(1))]))
    assert result['available'] and result['coverage']['ratio'] == '0/1'
    withheld(assess(use(key(1))+'\n'+summary(1, pending=10)+'\n'+summary(1, pending=9),
                    report([prepared(key(1))])), 'cumulative snapshot')
    for value in (float('nan'), float('inf')):
        withheld(assess(use(key(1))+'\n'+summary(1), report([prepared(key(1))], preparation_seconds=value)), 'incomplete preparation report')
    row = prepared(key(1));row['result']['hresult']='80004005'
    withheld(assess(use(key(1))+'\n'+summary(1), report([row])), 'failed native key validation')


if __name__ == '__main__':
    test_native_counter_and_failure_edges()
    test_parser_matches_existing_metrics()
    test_default_and_translation_are_separate_from_disk_and_residency()
    test_measured_extremes_keep_residency_unknown()
    test_cumulative_snapshot_and_bad_metrics_do_not_invent_coverage()
    test_unusable_logs_withhold_the_ratio()
    test_reports_accept_only_successful_rows()
    test_bounds_and_duplicate_derived_key()
    test_cli_writes_ignored_output_without_touching_inputs()
    print('pipeline runtime coverage contract passed')
