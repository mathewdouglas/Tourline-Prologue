"""Compare gameplay native-pipeline requests with a successful preparation report.

Reads one gameplay log and one preparation report.json. Writes an ignored
coverage.json. Does not launch the game, compile shaders, or change inputs.

The ratio counts each distinct complete `[pipeline-use] key=<16 lowercase hex>`
once. The numerator is the intersection with validated successful preparation
rows: default-stage `prepared` results, plus rows in a successful
`additional_translation` block. Template membership alone is not preparation.
The ratio is not GPU residency, shader compilation, driver pipeline creation,
or a stutter measurement.

A missing, truncated, malformed, or inconsistent `[pipeline-use-summary]`
withholds the ratio. `pending_shader_draws` stay out of the denominator.
Optional `outcome=warm_hit|demand` is recorded and never treated as residency
when it is absent.

The runtime diagnostic is a separate default-off switch (`RSX_PSO_COVERAGE=1`).
This tool only reads lines that switch would emit.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import subprocess
import sys

from pipeline_catalogue_limits import MAX_RECORDS

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = 'gt5p-pipeline-runtime-coverage'
VERSION = 1
MAX_LOG = 32 * 1024 * 1024
MAX_REPORT = 128 * 1024 * 1024
MAX_LINE = 4096
MAX_PREPARED_KEYS = 2 * MAX_RECORDS
MAX_KEYS = 16384
MAX_PENDING = (1 << 63) - 1
MAX_TEXT = 2000
HEX16 = re.compile(r'[0-9a-f]{16}')
HEX64 = re.compile(r'[0-9a-f]{64}')
COUNT = r'(?:0|[1-9][0-9]{0,18})'
USE_RE = re.compile(rf'\[pipeline-use\] key=({HEX16.pattern})(?: outcome=(warm_hit|demand))?$')
SUMMARY_RE = re.compile(
    rf'\[pipeline-use-summary\] format=1 unique=({COUNT}) recorded=({COUNT}) '
    rf'truncated=([01]) pending_shader_draws=({COUNT})$')
# Same expression as scripts/test/shader_stutter.py analyze_run. Imported here
# as text so this developer tool does not load the game harness.
METRIC_RE = re.compile(
    r'\[pipeline-metrics\] shader_compiles=(\d+) driver_calls=(\d+) cached_calls=(\d+) '
    r'demand_queued=(\d+) demand_done=(\d+) warm_loaded=(\d+) warm_hits=(\d+) resident=(\d+)')
METRIC_NAMES = ('shader_compiles', 'driver_calls', 'cached_calls', 'demand_queued',
                'demand_done', 'warm_loaded', 'warm_hits', 'resident')
METRIC_NOTE = ('Cumulative counters sampled every five seconds; final partial interval can be omitted. '
               'Driver calls include startup preparation; demand_queued counts live async work. '
               'Warm hits include preload bookkeeping; timestamp marks are not independent draw coverage.')
RESULT_FIELDS = ('expected', 'actual', 'created', 'hresult', 'material_requested', 'material_applied',
                 'pass_requested', 'pass_applied', 'native_requested', 'native_applied',
                 'prepare_requested', 'prepared', 'input_requested', 'input_applied')
RESULT_BOOLS = RESULT_FIELDS[4:]
FAILURES = {'unresolved-program': {'key', 'status'},
            'incompatible': {'key', 'status', 'reason'},
            'key-rejected': {'key', 'status', 'result'}}
TRANSLATION_MODES = {'native-scaled', 'ultrawide-native'}
TRANSLATION_FIELDS = {'template_key', 'key', 'vp_source', 'fp_source'}
CORE_LIMITS = (
    'This is the fraction of distinct complete native pipeline keys in the supplied gameplay log that match a validated successful preparation row.',
    'It is not GPU residency, shader compilation, driver pipeline creation, or a stutter measurement.',
    'pending_shader_draws are shader-incomplete draws and are excluded from the denominator.',
    'A template record is not prepared unless its default-stage row is status prepared, the native result key matches, and the default-stage driver-blob inventory contains that key.',
    'Optional outcome=warm_hit or outcome=demand is not residency when the field is absent.',
    'The ratio applies only to this log and preparation report. It does not prove that the game selected that cache or used the same settings; capture the launch configuration separately.',
    'Only complete guest VP/FP pipeline requests count. Renderer fallback draws without a guest fragment program, other routes/settings and failures before a complete key exists are outside this denominator.',
    'A runtime pipeline-metrics sample, when present, is a separate counter. It does not mean a prepared key avoided a hitch.',
    'A consistent key snapshot does not prove orderly shutdown or completion of the route. Record the sampling and process outcome separately.',
)


class Usage(Exception):
    pass


class Rejected(Exception):
    pass


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _hex16(value, label, allow_zero=False):
    if not isinstance(value, str) or not HEX16.fullmatch(value) or (not allow_zero and int(value, 16) == 0):
        raise Rejected(f'malformed {label}; coverage ratio withheld')
    return value


def _count(text):
    return int(text)


def parse_log(text):
    """Return the final pipeline-use snapshot, or reject an unusable log."""
    if text.startswith('\ufeff'):
        text = text[1:]
    if len(text.encode('utf-8')) > MAX_LOG:
        raise Rejected('gameplay log exceeds its size bound; coverage ratio withheld')
    keys, seen, outcomes, summaries = [], set(), {'warm_hit': 0, 'demand': 0, 'omitted': 0}, []
    for raw in text.splitlines():
        marker = '[pipeline-use]' in raw or '[pipeline-use-summary]' in raw
        if marker and len(raw) > MAX_LINE:
            raise Rejected('oversized pipeline-use line; coverage ratio withheld')
        line = raw.strip()
        has_summary = '[pipeline-use-summary]' in line
        has_use = '[pipeline-use]' in line
        if has_summary and has_use:
            raise Rejected('malformed pipeline-use line; coverage ratio withheld')
        if has_summary:
            match = SUMMARY_RE.fullmatch(line)
            if not match:
                raise Rejected('malformed pipeline-use-summary; coverage ratio withheld')
            unique, recorded = _count(match.group(1)), _count(match.group(2))
            truncated = match.group(3) == '1'
            pending = _count(match.group(4))
            if unique != recorded:
                raise Rejected('pipeline-use summary unique and recorded disagree; coverage ratio withheld')
            if unique != len(keys) or recorded != len(seen):
                raise Rejected('pipeline-use summary does not match records so far; coverage ratio withheld')
            if unique > MAX_KEYS or pending > MAX_PENDING:
                raise Rejected('pipeline-use summary exceeds its count bound; coverage ratio withheld')
            if summaries and (unique < summaries[-1]['unique'] or pending < summaries[-1]['pending']
                              or summaries[-1]['truncated'] and not truncated):
                raise Rejected('pipeline-use summaries are not a cumulative snapshot; coverage ratio withheld')
            summaries.append(dict(unique=unique, recorded=recorded, truncated=truncated, pending=pending))
            continue
        if has_use:
            match = USE_RE.fullmatch(line)
            if not match:
                raise Rejected('malformed pipeline-use key; coverage ratio withheld')
            key = _hex16(match.group(1), 'pipeline-use key', allow_zero=True)
            if key in seen:
                raise Rejected('duplicate pipeline-use key; coverage ratio withheld')
            if len(keys) >= MAX_KEYS:
                raise Rejected('pipeline-use key count exceeds its bound; coverage ratio withheld')
            keys.append(key)
            seen.add(key)
            outcomes[match.group(2) or 'omitted'] += 1
    if not summaries:
        raise Rejected('gameplay log has no pipeline-use-summary; coverage ratio withheld')
    final = summaries[-1]
    if len(keys) != final['recorded'] or len(seen) != final['unique']:
        raise Rejected('pipeline-use records exceed the final summary; coverage ratio withheld')
    if final['truncated']:
        raise Rejected(
            f"pipeline-use summary is truncated (unique={final['unique']} recorded={final['recorded']} "
            f"pending_shader_draws={final['pending']}); coverage ratio withheld")
    if final['unique'] == 0:
        raise Rejected('pipeline-use summary recorded no complete native keys; coverage ratio withheld')
    counters, counter_note = runtime_counters(text)
    return dict(keys=keys, outcomes=outcomes, summaries=len(summaries),
                pending_shader_draws=final['pending'], runtime_counters=counters,
                runtime_counters_note=counter_note)


def runtime_counters(text):
    """Last matching five-second sample. Never a preparation-coverage input."""
    matches = METRIC_RE.findall(text)
    marker = '[pipeline-metrics]' in text
    if not matches:
        note = METRIC_NOTE + ' No matching pipeline-metrics sample was present, so shader, driver, warm-hit and resident counts are unknown.'
        if marker:
            note += ' A pipeline-metrics marker did not match the existing parser and was not guessed.'
        return None, note
    values = []
    for item in matches[-1]:
        if len(item) > 19:
            return None, METRIC_NOTE + ' The last pipeline-metrics sample exceeded its count bound and was ignored.'
        number = int(item)
        if number > MAX_PENDING:
            return None, METRIC_NOTE + ' The last pipeline-metrics sample exceeded its count bound and was ignored.'
        values.append(number)
    note = METRIC_NOTE + ' These counters are not the preparation ratio and do not show that a prepared key avoided a hitch.'
    if text.count('[pipeline-metrics]') != len(matches):
        note += ' A pipeline-metrics marker did not match the existing parser; only the last matching sample is shown.'
    return dict(zip(METRIC_NAMES, values)), note


def _result_ok(result, key):
    if not isinstance(result, dict) or set(result) != set(RESULT_FIELDS):
        return False
    if any(type(result[name]) is not bool for name in RESULT_BOOLS) or type(result['created']) is not bool:
        return False
    if not isinstance(result['hresult'], str) or not re.fullmatch(r'[0-9a-f]{8}', result['hresult']):
        return False
    return (int(result['hresult'], 16) < 0x80000000 and result['created'] is True and result['expected'] == key and result['actual'] == key
            and isinstance(result['expected'], str) and isinstance(result['actual'], str))


def _failure_row(row):
    status = row.get('status')
    if status not in FAILURES or set(row) != FAILURES[status]:
        raise Rejected('unsupported preparation record; coverage ratio withheld')
    _hex16(row.get('key'), 'preparation record key')
    if status == 'incompatible':
        if not isinstance(row['reason'], str) or len(row['reason']) > MAX_TEXT:
            raise Rejected('malformed incompatible preparation record; coverage ratio withheld')
    elif status == 'key-rejected' and _result_ok(row['result'], row['key']):
        raise Rejected('key-rejected row carries a successful native result; coverage ratio withheld')
    elif status == 'key-rejected' and not isinstance(row['result'], dict):
        raise Rejected('malformed key-rejected preparation record; coverage ratio withheld')


def _translation(block, default_keys):
    if not isinstance(block, dict):
        raise Rejected('additional_translation is not an object; coverage ratio withheld')
    required = {'translation', 'counts', 'unique_pipelines', 'records', 'root_signature', 'seconds', 'native_counts'}
    if not required <= set(block) or not isinstance(block['translation'],str) or block['translation'] not in TRANSLATION_MODES:
        raise Rejected('unsupported additional_translation; coverage ratio withheld')
    records = block['records']
    if not isinstance(records, list) or not records or len(records) > MAX_RECORDS:
        raise Rejected('additional_translation records are missing or over its bound; coverage ratio withheld')
    if block['counts'] != {'prepared': len(records)}:
        raise Rejected('additional_translation counts do not match its rows; coverage ratio withheld')
    if type(block['unique_pipelines']) is not int or type(block['seconds']) not in (int, float) or isinstance(block['seconds'], bool):
        raise Rejected('malformed additional_translation counts; coverage ratio withheld')
    if not math.isfinite(block['seconds']) or block['seconds'] < 0:
        raise Rejected('malformed additional_translation counts; coverage ratio withheld')
    _hex16(block['root_signature'], 'translation root signature')
    native = block['native_counts']
    derived, template_keys = [], []
    for row in records:
        if not isinstance(row, dict) or set(row) != TRANSLATION_FIELDS:
            raise Rejected('unsupported additional_translation row; coverage ratio withheld')
        template_keys.append(_hex16(row['template_key'], 'translation template key'))
        derived.append(_hex16(row['key'], 'translation native key'))
        _hex16(row['vp_source'], 'translation vertex source')
        _hex16(row['fp_source'], 'translation fragment source')
    if len(set(template_keys)) != len(template_keys):
        raise Rejected('duplicate translation template key; coverage ratio withheld')
    if not set(template_keys) <= default_keys:
        raise Rejected('translation row is not tied to a successful default preparation key; coverage ratio withheld')
    unique = len(set(derived))
    confirmed = (isinstance(native, list) and len(native) == 4
                 and all(type(item) is int and 0 <= item <= MAX_PENDING for item in native)
                 and native[0] == native[1] == unique and native[3] <= native[2])
    if block['unique_pipelines'] != unique or not confirmed:
        raise Rejected('additional_translation native batch does not confirm every derived key; coverage ratio withheld')
    return dict(keys=set(derived), mode=block['translation'], root_signature=block['root_signature'],
                unique_pipelines=unique, native_batch=dict(requests=native[0], created=native[1],
                driver_calls=native[2], cached_blob_calls=native[3]))


def parse_report(document):
    """Successful native keys only. Inventory membership is not preparation."""
    if not isinstance(document, dict):
        raise Rejected('preparation report is not an object; coverage ratio withheld')
    if document.get('schema') == 'gt5p-pipeline-template':
        raise Rejected('template membership is not successful preparation; pass report.json; coverage ratio withheld')
    if type(document.get('schema')) is not int or document.get('schema') != 1:
        raise Rejected('unsupported preparation report schema; coverage ratio withheld')
    counts = document.get('counts')
    if (not isinstance(counts, dict) or any(type(v) is not int or v < 0 for v in counts.values())
            or 'template-rejected' in counts or document.get('template_sha256') is None):
        raise Rejected('preparation report rejected its template or is incomplete; coverage ratio withheld')
    for name in ('template_sha256', 'engine_sha256', 'decoder_sha256'):
        value = document.get(name)
        if not isinstance(value, str) or not HEX64.fullmatch(value):
            raise Rejected('preparation report is missing provenance hashes; coverage ratio withheld')
    seconds = document.get('preparation_seconds')
    records = document.get('records')
    if type(document.get('requested')) is not int or document['requested'] < 0:
        raise Rejected('malformed preparation requested count; coverage ratio withheld')
    if type(seconds) not in (int, float) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds < 0:
        raise Rejected('incomplete preparation report; coverage ratio withheld')
    if not isinstance(records, list) or len(records) > MAX_RECORDS or document['requested'] != len(records):
        raise Rejected('preparation records are missing or over the template bound; coverage ratio withheld')
    inventory = document.get('inventory')
    if not isinstance(inventory, dict) or 'valid_driver_blobs' not in inventory or 'rejected' not in inventory:
        raise Rejected('preparation report is missing default-stage driver inventory; coverage ratio withheld')
    blobs = inventory['valid_driver_blobs']
    rejected = inventory['rejected']
    if not isinstance(blobs, list) or len(blobs) > MAX_PREPARED_KEYS or not isinstance(rejected, list) or rejected:
        raise Rejected('preparation driver inventory is rejected or over its bound; coverage ratio withheld')
    blob_ids = {_hex16(item, 'driver blob id') for item in blobs}
    prepared, seen = [], set()
    observed = {}
    input_seen = set()
    inputs = document.get('template_format') == 3
    for row in records:
        if not isinstance(row, dict) or not isinstance(row.get('status'),str):
            raise Rejected('unsupported preparation record; coverage ratio withheld')
        status = row['status']
        observed[status] = observed.get(status, 0) + 1
        if inputs:
            input_key = row.get('input_key')
            if not isinstance(input_key, str) or not HEX64.fullmatch(input_key) or input_key in input_seen:
                raise Rejected('invalid or duplicate preparation input identity')
            input_seen.add(input_key)
            row = {k:v for k,v in row.items() if k != 'input_key'}
            if status != 'prepared':
                if row.get('key') != input_key or status not in ('unresolved-program','incompatible'):
                    raise Rejected('invalid failed input preparation')
                _failure_row(dict(row, key='1'*16))
                continue
        key = _hex16(row.get('key'), 'preparation record key')
        if key in seen and not inputs:
            raise Rejected('duplicate preparation record key; coverage ratio withheld')
        seen.add(key)
        if status == 'prepared':
            if set(row) != {'key', 'status', 'result'}:
                raise Rejected('unsupported prepared row; coverage ratio withheld')
            if not _result_ok(row['result'], key):
                raise Rejected('prepared row failed native key validation; coverage ratio withheld')
            if key not in blob_ids:
                raise Rejected('prepared row has no validated driver blob; coverage ratio withheld')
            prepared.append(key)
        else:
            _failure_row(row)
    if observed != counts:
        raise Rejected('preparation counts do not match its rows; coverage ratio withheld')
    if inputs and document.get('runtime_lookup_counts') != [len(set(prepared))] * 4:
        raise Rejected('runtime lookup did not confirm every persisted input pipeline')
    translation = None
    translated = set()
    if 'additional_translation' in document:
        translation = _translation(document['additional_translation'], set(prepared))
        translated = translation['keys']
    if len(set(prepared) | translated) > MAX_PREPARED_KEYS:
        raise Rejected('successful preparation keys exceed their bound; coverage ratio withheld')
    return dict(default_keys=prepared, translation=translation, translated_keys=translated,
                driver_blobs=len(blob_ids),
                provenance=dict(template_sha256=document['template_sha256'],
                                engine_sha256=document['engine_sha256'],
                                decoder_sha256=document['decoder_sha256']),
                player_settings=_player_settings(document.get('player_settings')))


def _player_settings(value):
    if value is None:
        return None
    if not isinstance(value, dict):
        return {'interpreted': False}
    digest = value.get('settings_sha256')
    mode = value.get('mode')
    if (value.get('schema') != 1 or not isinstance(mode, str) or not mode or len(mode) > 64
            or not isinstance(digest, str) or not HEX64.fullmatch(digest)):
        return {'interpreted': False}
    resolution = value.get('resolution')
    aspect = value.get('aspect')
    return dict(interpreted=True, schema=1, mode=mode, settings_sha256=digest,
                resolution=resolution if type(resolution) is int and 0 <= resolution <= 10000 else None,
                aspect=aspect if isinstance(aspect, str) and len(aspect) <= 16 else None,
                note='Preparation settings provenance only. This does not prove the gameplay log used them.')


def _limits(prepared, pending=None):
    lines = list(CORE_LIMITS)
    if prepared is None:
        lines.append('Preparation rows were not accepted, so no ratio was computed.')
    elif prepared['translation']:
        lines.append('Successful additional_translation rows are included. Their native_batch counts are offline creation counts, not live residency.')
    else:
        lines.append('No additional_translation block was present. Only successful default-stage rows count as prepared.')
    if pending is not None:
        lines.append(f'pending_shader_draws={pending} were excluded from the denominator.')
    return lines


def _document(available, reason, provenance, coverage, details, limits):
    return dict(schema=SCHEMA, version=VERSION, available=available, reason=reason, coverage=coverage,
                measures='fraction of distinct complete draw-requested native keys matching successful preparation report rows',
                does_not_measure=['GPU residency', 'shader compilation', 'driver pipeline creation', 'stutter or frame time'],
                gpu_residency=None, shader_compilation=None, driver_pipeline_creation=None, stutter=None,
                provenance=provenance, limitations=limits, **details)


def assess(log_text, report_document, provenance):
    """Coverage document. Unavailable results have coverage null and no ratio."""
    try:
        log = parse_log(log_text)
        prepared = parse_report(report_document)
    except Rejected as exc:
        return _document(False, str(exc), provenance, None, {}, _limits(None))
    ready = set(prepared['default_keys']) | set(prepared['translated_keys'])
    hits = [key for key in log['keys'] if key in ready]
    misses = [key for key in log['keys'] if key not in ready]
    translation = prepared['translation']
    details = dict(
        successful_preparation_keys=len(ready),
        successful_default_keys=len(prepared['default_keys']),
        successful_translation_keys=0 if translation is None else len(prepared['translated_keys']),
        valid_driver_blob_count=prepared['driver_blobs'],
        disk_note='valid_driver_blob_count is default-stage inventory membership. It is not the numerator and it is not GPU residency.',
        translation=None if translation is None else dict(
            mode=translation['mode'], root_signature=translation['root_signature'],
            unique_pipelines=translation['unique_pipelines'], native_batch=translation['native_batch'],
            note='Offline translation creation counts are not live residency or hitch avoidance.'),
        player_settings=prepared['player_settings'],
        pending_shader_draws=log['pending_shader_draws'],
        denominator_excludes='pending_shader_draws',
        outcome_lines=log['outcomes'],
        outcome_note='Missing outcome does not mean the pipeline was resident or was not resident.',
        summaries=log['summaries'],
        runtime_counters=log['runtime_counters'],
        runtime_counters_note=log['runtime_counters_note'],
        misses=misses, miss_count=len(misses))
    coverage = dict(requested_unique=len(log['keys']), prepared_intersection=len(hits),
                    ratio=f'{len(hits)}/{len(log["keys"])}', percent=100.0*len(hits)/len(log['keys']))
    return _document(True, None, dict(provenance, **prepared['provenance']), coverage, details,
                     _limits(prepared, log['pending_shader_draws']))


def _absolute(path):
    path = Path(path)
    if not path.is_absolute():
        path = Path.cwd() / path
    return path


def _reparse(path):
    return path.is_symlink() or path.is_junction()


def require_output(path):
    path = _absolute(path)
    if path.exists() or _reparse(path):
        raise Usage('Output exists; choose a new directory')
    parent = path.parent
    if _reparse(parent) or not parent.is_dir():
        raise Usage('Output parent is missing or is a reparse point')
    parent_real = parent.resolve()
    if ROOT != parent_real and ROOT not in parent_real.parents:
        raise Usage('Output must be inside this checkout')
    target = parent_real / path.name
    ignored = subprocess.run(['git', 'check-ignore', '-q', str(target / 'coverage.json')], cwd=ROOT)
    if ignored.returncode:
        raise Usage('Output must be gitignored')
    return target


def require_file(path):
    path = _absolute(path)
    if _reparse(path):
        raise Usage('Refusing a reparse-point input: ' + str(path))
    if not path.is_file():
        raise Usage('Input is not a file: ' + str(path))
    return path


def _fingerprint(path):
    info = path.lstat()
    return info.st_size, info.st_mtime_ns


def _read_bounded(path, limit):
    size = path.lstat().st_size
    if size > limit:
        return None, size
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        return None, len(data)
    return data, size


def _separated(output, log_path, report_path):
    paths = (log_path, report_path)
    if any(output == path or output in path.parents or path in output.parents for path in paths):
        raise Usage('Output must be separate from both inputs')
    if log_path == report_path:
        raise Usage('Log and preparation report must be different files')


def evaluate_files(log_path, report_path, output):
    output = require_output(output)
    log_path, report_path = require_file(log_path), require_file(report_path)
    _separated(output, log_path, report_path)
    before = (_fingerprint(log_path), _fingerprint(report_path))
    log_bytes, log_size = _read_bounded(log_path, MAX_LOG)
    report_bytes, report_size = _read_bounded(report_path, MAX_REPORT)
    if (_fingerprint(log_path), _fingerprint(report_path)) != before:
        raise Usage('Input files changed while reading; nothing was written')
    provenance = dict(log_bytes=log_size, report_bytes=report_size, inputs_unchanged=True,
                      log_sha256=None if log_bytes is None else _sha(log_bytes),
                      report_sha256=None if report_bytes is None else _sha(report_bytes))
    if log_bytes is None or report_bytes is None:
        reason = 'input exceeds its size bound; coverage ratio withheld'
        document = _document(False, reason, provenance, None, {}, _limits(None))
    else:
        try:
            text = log_bytes.decode('utf-8')
        except UnicodeError:
            document = _document(False, 'gameplay log is not UTF-8; coverage ratio withheld', provenance, None, {}, _limits(None))
        else:
            try:
                report = json.loads(report_bytes.decode('utf-8-sig'))
            except (UnicodeError, json.JSONDecodeError):
                document = _document(False, 'preparation report is not UTF-8 JSON; coverage ratio withheld',
                                     provenance, None, {}, _limits(None))
            else:
                document = assess(text, report, provenance)
    output.mkdir()
    temporary = output / 'coverage.json.tmp'
    temporary.write_text(json.dumps(document, indent=2) + '\n', encoding='utf-8', newline='\n')
    temporary.replace(output / 'coverage.json')
    return document


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', type=Path, required=True,
                        help='Gameplay log with pipeline-use lines, usually the route stderr')
    parser.add_argument('--report', type=Path, required=True,
                        help='Parent preparation report.json, not a template bundle or translation sidecar')
    parser.add_argument('--output', type=Path, required=True,
                        help='New gitignored directory. coverage.json is written here')
    args = parser.parse_args(argv)
    try:
        document = evaluate_files(args.log, args.report, args.output)
    except Usage as exc:
        parser.error(str(exc))
    print('coverage ' + document['coverage']['ratio'] if document['available'] else 'unavailable: ' + document['reason'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
