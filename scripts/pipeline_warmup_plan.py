"""Export observed phase membership; stage metadata for the existing PSO worker.

No shaders, recipes or driver blobs are exported. Only default template keys
are supported; the replay benchmark uses 1080p/2x MSAA. This is a developer
experiment, not a claim of phase ownership beyond the recorded notifier scope.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import uuid

from pipeline_runtime_coverage import parse_report, MAX_REPORT, require_output

SCHEMA = 'gt5p-pipeline-warmup-plan'
VERSION = 1
MAX_PLAN = 1024 * 1024  # SHA-256 input identities, still at most 4,096 targets.
MAX_INDEX = 1024 * 1024
MAX_LINES = 32768
MAX_KEYS = 4096
MAX_EVIDENCE = 16
HEX = re.compile(r'[0-9a-f]{16}')
SHA = re.compile(r'[0-9a-f]{64}')
CONTEXT = 'default-template-keys-v1'
CONDITIONS = '1080p/2x MSAA/VSync; async shaders/PSOs; PS3_VERBOSE=0'
SCOPE = 'Observed renderer notifier membership, including prepass requests; not first-draw readiness or residency.'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def bounded(path, limit):
    path = Path(path)
    if path.is_symlink() or path.is_junction() or not path.is_file():
        raise ValueError('Expected a regular local file: '+str(path))
    with path.open('rb') as stream:
        data = stream.read(limit + 1)
    if len(data) > limit:
        raise ValueError('Input exceeds its bound: '+str(path))
    return data


def index(data):
    if len(data) > MAX_INDEX:
        raise ValueError('Membership index exceeds its byte bound')
    lines = data.decode('ascii').splitlines()
    if len(lines) > MAX_LINES:
        raise ValueError('Membership index exceeds its line bound')
    keys = []
    seen = set()
    for line in lines:
        if not HEX.fullmatch(line) or int(line, 16) == 0:
            raise ValueError('Malformed membership key')
        if line not in seen:
            keys.append(line)
            seen.add(line)
    return keys


def validate(plan):
    fields = {'schema', 'version', 'template_sha256', 'context', 'scope', 'phases', 'evidence'}
    if (not isinstance(plan, dict) or set(plan) != fields or plan['schema'] != SCHEMA
            or type(plan['version']) is not int or plan['version'] not in (1, 2)
            or plan['context'] != (CONTEXT if plan['version'] == 1 else 'default-template-inputs-v3') or plan['scope'] != SCOPE
            or not isinstance(plan['template_sha256'], str) or not SHA.fullmatch(plan['template_sha256'])):
        raise ValueError('Incompatible warmup plan')
    phases = plan['phases']
    if not isinstance(phases, dict) or set(phases) != {'menu', 'race'}:
        raise ValueError('Unsupported phase scope')
    total = set()
    for keys in phases.values():
        if (not isinstance(keys, list) or len(keys) > MAX_KEYS
                or any(not isinstance(k, str) or not (HEX if plan['version'] == 1 else SHA).fullmatch(k) or int(k, 16) == 0 for k in keys)):
            raise ValueError('Malformed or oversized phase keys')
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate phase key')
        total.update(keys)
    if not total or len(total) > MAX_KEYS:
        raise ValueError('Warmup plan union is empty or oversized')
    evidence = plan['evidence']
    fields = {'source_kind', 'source_sha256', 'report_sha256', 'menu_index_sha256', 'race_index_sha256'}
    if not isinstance(evidence, list) or not 1 <= len(evidence) <= MAX_EVIDENCE:
        raise ValueError('Warmup evidence bound exceeded')
    for row in evidence:
        if (not isinstance(row, dict) or set(row) != fields
                or row['source_kind'] not in ('completed-indexed-benchmark', 'local-notifier-indices')
                or any(not isinstance(v, str) or not SHA.fullmatch(v) for k,v in row.items() if k != 'source_kind')):
            raise ValueError('Malformed warmup evidence')
    return plan


def read(path):
    return validate(json.loads(bounded(path, MAX_PLAN).decode('utf-8')))


def load(path, template):
    """Convert a format-2 bundle's historical key membership on load."""
    plan = read(path)
    if plan['version'] == 2:
        return plan
    from pipeline_template import read as read_template, template_digest
    from pipeline_template_inputs import convert
    from pipeline_template_rekey import remap_plan
    old = read_template(template,legacy=True)
    if old['version'] != 2:
        raise ValueError('A native-key plan needs its original format-2 template')
    mapping = {r['key']:convert(dict(old,records=[r]))['records'][0]['key'] for r in old['records']}
    pin = template_digest(template)
    return remap_plan(plan,mapping,pin,pin,inputs=True)


def report_keys(document):
    accepted = parse_report(document)
    # Derived translation membership needs its own measured context. Never
    # alias those keys to this default-translation experiment.
    return set(accepted['default_keys'])


def export(session_path, tag, report_path):
    session_bytes = bounded(session_path, MAX_REPORT)
    report_bytes = bounded(report_path, MAX_REPORT)
    session = json.loads(session_bytes.decode('utf-8'))
    document = json.loads(report_bytes.decode('utf-8'))
    if document.get('warmup_plan') is not None:
        raise ValueError('Collect from a generation without seeded phase membership')
    ready = report_keys(document)
    if not re.fullmatch(r'[1-4]-prepared(?:-indexed)?', tag):
        raise ValueError('Expected an owned prepared benchmark trial tag')
    if session.get('conditions') != CONDITIONS or session.get('startup_policy') != 'indexed':
        raise ValueError('Session does not establish the supported indexed context')
    trials = session.get('trials')
    if not isinstance(trials, list):
        raise ValueError('Session has no completed trials')
    matches = [r for r in trials if isinstance(r, dict) and r.get('tag') == tag]
    if len(matches) != 1:
        raise ValueError('Trial is missing or ambiguous')
    trial = matches[0]
    if trial.get('warmup_plan') is not None:
        raise ValueError('Collect without a seed plan before exporting observed membership')
    condition = trial.get('coverage_condition', {})
    coverage = trial.get('reference_pipeline_coverage', {})
    window = trial.get('window', {})
    if (trial.get('condition') != 'prepared' or condition.get('prepared_cache_selected') is not True
            or condition.get('reference_report_sha256') != digest(report_bytes)
            or coverage.get('available') is not True
            or coverage.get('provenance', {}).get('report_sha256') != digest(report_bytes)):
        raise ValueError('Trial does not confirm its preparation reference')
    grid, end = window.get('grid_observed_ms'), window.get('sample_end_ms')
    if (type(grid) not in (int, float) or type(end) not in (int, float)
            or not 89000 <= end-grid <= 300000):
        raise ValueError('Trial does not confirm a completed sampling window')
    engine = session.get('engine_sha256')
    if not isinstance(engine, str) or not SHA.fullmatch(engine):
        raise ValueError('Missing session engine identity')
    folder = Path(session_path).parent / tag / 'shadercache' / 'warmup-v1'
    phases, rejected, hashes = {}, {}, {}
    for phase in ('menu', 'race'):
        data = bounded(folder/(phase+'-v1.txt'), MAX_INDEX)
        observed = index(data)
        phases[phase] = [key for key in observed if key in ready]
        rejected[phase] = len(observed)-len(phases[phase])
        hashes[phase+'_index_sha256'] = digest(data)
    plan = validate(dict(schema=SCHEMA, version=VERSION, template_sha256=document['template_sha256'],
        context=CONTEXT, scope=SCOPE, phases=phases, evidence=[dict(source_kind='completed-indexed-benchmark',
        source_sha256=digest(session_bytes), report_sha256=digest(report_bytes), **hashes)]))
    return input_plan(plan,document), dict(excluded_unprepared_keys=rejected, phase_counts={p:len(k) for p,k in phases.items()})


def export_local(cache, report_path):
    """Read existing notifier indices without inventing a completed route.

    Historical local membership may span cars/tracks/settings. Exact default
    native-key intersection is the compatibility filter, not a new setting or
    first-use claim. No source cache file is written or copied.
    """
    raw = bounded(report_path, MAX_REPORT)
    document = json.loads(raw.decode('utf-8'))
    ready = report_keys(document)
    phases, hashes, audit = {}, {}, {}
    for phase in ('menu', 'race'):
        data = bounded(Path(cache)/'warmup-v1'/(phase+'-v1.txt'), MAX_INDEX)
        observed = index(data)
        phases[phase] = [key for key in observed if key in ready]
        hashes[phase+'_index_sha256'] = digest(data)
        audit[phase] = dict(observed=len(observed), matched=len(phases[phase]),
                            excluded=len(observed)-len(phases[phase]))
    source = digest(json.dumps(hashes, sort_keys=True).encode('ascii'))
    plan = validate(dict(schema=SCHEMA, version=VERSION, template_sha256=document['template_sha256'],
        context=CONTEXT, scope=SCOPE, phases=phases, evidence=[dict(source_kind='local-notifier-indices',
        source_sha256=source, report_sha256=digest(raw), **hashes)]))
    return input_plan(plan,document), dict(phases=audit, scope=SCOPE,
        limitation='Historical phase membership only; no completed route, draw readiness or stutter measurement is inferred.')


def merge(plans):
    if not 1 <= len(plans) <= MAX_EVIDENCE:
        raise ValueError('Warmup merge input bound exceeded')
    first = validate(plans[0])
    phases, evidence = {'menu': [], 'race': []}, []
    for plan in plans:
        validate(plan)
        if plan['template_sha256'] != first['template_sha256'] or plan['context'] != first['context']:
            raise ValueError('Cannot merge incompatible warmup plans')
        for phase in phases:
            phases[phase] = list(dict.fromkeys(phases[phase]+plan['phases'][phase]))
        for row in plan['evidence']:
            if row not in evidence:
                evidence.append(row)
    return validate(dict(first, phases=phases, evidence=evidence))


def validate_preparation(plan, document):
    plan = native_plan(plan, document)
    validate(plan)
    if document.get('template_sha256') != plan['template_sha256']:
        raise ValueError('Warmup plan template changed')
    ready = report_keys(document)
    keys = set(plan['phases']['menu']) | set(plan['phases']['race'])
    if not keys <= ready:
        raise ValueError('Warmup plan references an unprepared or incompatible key')
    return keys


def native_plan(plan, report):
    """Resolve portable input membership only through successful native proof."""
    validate(plan)
    if plan['version'] == 1:
        return plan
    from preparation_template_inputs import successful_inputs
    mapping = successful_inputs(report)
    if any(key not in mapping for values in plan['phases'].values() for key in values):
        raise ValueError('Warmup plan references an unprepared input identity')
    return dict(plan,version=1,context=CONTEXT,
                phases={phase:list(dict.fromkeys(mapping[k] for k in values)) for phase,values in plan['phases'].items()})


def input_plan(plan, report):
    """Export observed native membership as portable identities for new reports."""
    if report.get('template_format') != 3:
        return plan
    from preparation_template_inputs import successful_inputs
    mapping = successful_inputs(report)
    reverse = {}
    for identity,key in mapping.items():
        reverse.setdefault(key,[]).append(identity)
    return validate(dict(plan,version=2,context='default-template-inputs-v3',
        phases={p:list(dict.fromkeys(i for key in keys for i in reverse.get(key,[])))
                for p,keys in plan['phases'].items()}))


def stage(plan, document, folder, resume=False):
    """Stage into an idle private cache copy, never replace learned membership."""
    plan = native_plan(plan, document)
    keys = validate_preparation(plan, document)
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink() or folder.is_junction():
        raise ValueError('Expected a private regular warmup directory')
    # Validate everything before writing either index. Recipes and bytecode are
    # revalidated by the existing worker, including root-signature/native keys.
    for key in keys:
        recipe = folder/('pso_'+key+'.recipe')
        if recipe.is_symlink() or recipe.is_junction() or not recipe.is_file():
            raise ValueError('Missing local recipe for warmup key')
    pending = []
    for phase, values in plan['phases'].items():
        path = folder/(phase+'-v1.txt')
        expected = ''.join(key+'\n' for key in values).encode('ascii')
        if path.is_symlink() or path.is_junction():
            raise ValueError('Refusing to replace existing learned membership')
        existing = bounded(path, MAX_INDEX) if path.exists() else b''
        if existing:
            if resume and existing == expected:
                continue
            raise ValueError('Refusing to replace existing learned membership')
        pending.append((path, expected))
    for path, expected in pending:
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        with temporary.open('x', encoding='ascii', newline='\n') as stream:
            stream.write(expected.decode('ascii'))
        temporary.replace(path)
    return dict(context=CONTEXT, phase_counts={p:len(k) for p,k in plan['phases'].items()},
                unique_keys=len(keys), scope=SCOPE, indices_written=len(pending))



def stage_translated(plan, report, folder):
    """Phase 221: publish menu/race membership for an additional translation (ultrawide-native or
    native-scaled preparation), so the race prewarm and fast lookup work in the mode the player runs.

    The observed plan names default pipelines; each maps through the translation pass's own records
    (template_key = default native key -> key = translated native key) to the pipeline the game will draw
    in that mode. Only keys with a local recipe are written. Never replaces membership the game learned:
    an existing non-empty index is left alone. GT5P_PREPARE_TRANSLATED_PLAN=0 skips it.
    """
    import os
    if os.environ.get('GT5P_PREPARE_TRANSLATED_PLAN') == '0':
        return dict(status='skipped', reason='GT5P_PREPARE_TRANSLATED_PLAN=0')
    extra = report.get('additional_translation')
    if not isinstance(extra, dict) or not extra.get('records'):
        return dict(status='skipped', reason='no additional translation')
    plan = native_plan(plan, report)
    mapping = {r['template_key']: r['key'] for r in extra['records']
               if isinstance(r.get('template_key'), str) and isinstance(r.get('key'), str)}
    folder = Path(folder)
    if not folder.is_dir() or folder.is_symlink() or folder.is_junction():
        raise ValueError('Expected a private regular warmup directory')
    counts, written = {}, 0
    for phase, values in plan['phases'].items():
        keys = list(dict.fromkeys(mapping[k] for k in values if k in mapping))
        keys = [k for k in keys if (folder/('pso_'+k+'.recipe')).is_file()]
        counts[phase] = len(keys)
        path = folder/(phase+'-v1.txt')
        if path.is_symlink() or path.is_junction():
            raise ValueError('Refusing to replace existing learned membership')
        if path.exists() and bounded(path, MAX_INDEX):
            continue
        temporary = path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
        with temporary.open('x', encoding='ascii', newline='\n') as stream:
            stream.write(''.join(k+'\n' for k in keys))
        temporary.replace(path)
        written += 1
    return dict(status='complete', translation=extra.get('translation'), phase_counts=counts,
                indices_written=written)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    e = sub.add_parser('export')
    e.add_argument('--session', type=Path, required=True)
    e.add_argument('--trial', required=True)
    e.add_argument('--report', type=Path, required=True)
    e.add_argument('--output', type=Path, required=True)
    local = sub.add_parser('export-local')
    local.add_argument('--cache', type=Path, required=True)
    local.add_argument('--report', type=Path, required=True)
    local.add_argument('--output', type=Path, required=True)
    m = sub.add_parser('merge')
    m.add_argument('--plan', type=Path, action='append', required=True)
    m.add_argument('--output', type=Path, required=True)
    a = ap.parse_args()
    out = require_output(a.output)
    if a.command == 'export':
        plan, audit = export(a.session, a.trial, a.report)
    elif a.command == 'export-local':
        plan, audit = export_local(a.cache, a.report)
    else:
        if len(a.plan) > MAX_EVIDENCE:
            raise ValueError('Warmup merge input bound exceeded')
        plan, audit = merge([read(p) for p in a.plan]), {}
    data = json.dumps(plan, indent=2)+'\n'
    if len(data.encode('utf-8')) > MAX_PLAN:
        raise ValueError('Encoded warmup plan exceeds its bound')
    out.mkdir()
    (out/'warmup-plan.json').write_text(data, encoding='utf-8')
    (out/'report.json').write_text(json.dumps(audit, indent=2)+'\n', encoding='utf-8')
    print('Observed warmup plan:', out/'warmup-plan.json')


if __name__ == '__main__':
    main()
