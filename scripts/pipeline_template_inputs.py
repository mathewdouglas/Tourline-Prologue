"""Format 3: canonical pipeline inputs, independent of renderer outputs.

The historical ``key`` field is a SHA-256 input identity in this format, never
a native PSO key. Output identifiers and shader lengths exist only in local
preparation reports/checkpoints. Format 2 remains readable for migration.
"""
import argparse
import copy
import json
from pathlib import Path

FIELDS = {'vp', 'fp', 'vp_gpu', 'state', 'native'}
OUTPUTS = ('key', 'vs', 'ps', 'vp_source', 'fp_source')
LENGTH_WORDS = (4, 5, 8, 9)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def identity(record):
    from pipeline_template import sha
    return sha(b'gt5p-pipeline-input-v3\n' + canonical({k: record[k] for k in sorted(FIELDS)}))


def input_contract(contract):
    return {k: copy.deepcopy(v) for k, v in contract.items() if k != 'renderer_sha256'}


def convert(document):
    from pipeline_template import validate_legacy
    if not isinstance(document,dict):
        raise ValueError('Malformed template document')
    if document.get('version') == 3:
        return validate(copy.deepcopy(document))
    document = validate_legacy(copy.deepcopy(document))
    records = []
    for old in document['records']:
        row = {k: copy.deepcopy(old[k]) for k in sorted(FIELDS)}
        for index in LENGTH_WORDS:
            row['native']['words'][index] = 0
        row['key'] = identity(row)
        records.append(row)
    return validate(dict(document, version=3, compatibility=input_contract(document['compatibility']), records=records))


def validate(document):
    from pipeline_template import validate_legacy, SHA, MAX_RECORDS
    try:
        if (set(document) != {'schema', 'version', 'compatibility', 'records'} or
                document['schema'] != 'gt5p-pipeline-template' or type(document['version']) is not int or
                document['version'] != 3 or 'renderer_sha256' in document['compatibility']):
            raise ValueError('Incompatible input template schema/contract')
        old = copy.deepcopy(document)
        old['version'] = 2
        old['compatibility']['renderer_sha256'] = '0' * 64
        if not isinstance(document['records'], list) or len(document['records']) > MAX_RECORDS:
            raise ValueError('Invalid input records')
        seen = {}
        for row, surrogate in zip(document['records'], old['records']):
            if (set(row) != FIELDS | {'key'} or not isinstance(row['key'], str) or
                    not SHA.fullmatch(row['key']) or
                    any(row['native']['words'][i] != 0 for i in LENGTH_WORDS)):
                raise ValueError('Unknown input fields or renderer output lengths')
            if row['key'] != identity(row):
                raise ValueError('Input identity/content conflict')
            if row['key'] in seen and row != seen[row['key']]:
                raise ValueError('Conflicting duplicate input identity')
            seen[row['key']] = row
            # Reuse the complete pointer, numeric, semantic and bounds validator.
            surrogate.update({k: f'{len(seen):016x}' for k in OUTPUTS})
        validate_legacy(old)
        document['records'] = list(seen.values())
        return document
    except (TypeError, KeyError, IndexError, AttributeError, OverflowError) as exc:
        raise ValueError('Malformed input template') from exc


def reference_outputs(document):
    """Maintainer-only format-2 expectations indexed by canonical inputs."""
    from pipeline_template import validate_legacy
    document = validate_legacy(copy.deepcopy(document))
    out = {}
    for row in document['records']:
        key = convert(dict(document, records=[row]))['records'][0]['key']
        outputs = {k: row[k] for k in OUTPUTS}
        if key in out and out[key] != outputs:
            raise ValueError('Reference run has conflicting outputs for identical inputs')
        out[key] = outputs
    return out


def review_inputs(document):
    """Structural validation for quarantine only; never authorizes preparation.

    Preserve a submitted identity/content mismatch so review can quarantine it.
    Strict readers and the acceptance path continue to reject that mismatch.
    """
    if not isinstance(document,dict):
        raise ValueError('Malformed review template')
    if document.get('version') != 3:
        return convert(document)
    from pipeline_template import SHA, MAX_RECORDS
    original = copy.deepcopy(document)
    checked = copy.deepcopy(document)
    if not isinstance(checked.get('records'),list) or len(checked['records']) > MAX_RECORDS:
        raise ValueError('Review record limit exceeded')
    try:
        for row in checked['records']:
            if not isinstance(row['key'],str) or not SHA.fullmatch(row['key']):
                raise ValueError('Invalid submitted input identity')
            row['key'] = identity(row)
        validate(checked)
    except (KeyError,TypeError) as exc:
        raise ValueError('Malformed review inputs') from exc
    return original


def main():
    from pipeline_template import read, bundle, template_digest
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--template', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--warmup-plan', type=Path)
    ap.add_argument('--output-plan', type=Path)
    a = ap.parse_args()
    if bool(a.warmup_plan) != bool(a.output_plan):
        ap.error('Supply both warmup plan paths')
    old = read(a.template, legacy=True)
    new = convert(old)
    plan = None
    if a.warmup_plan:
        from pipeline_warmup_plan import read as read_plan
        from pipeline_template_rekey import remap_plan
        mapping = {r['key']: convert(dict(old, records=[r]))['records'][0]['key'] for r in old['records']}
        plan = read_plan(a.warmup_plan)
        if a.output_plan.exists():
            raise ValueError('Output plan exists')
        # Check source membership before writing anything.
        plan = remap_plan(plan, mapping, template_digest(a.template), '0' * 64, inputs=True)
    bundle(new, a.output)
    if a.template.is_dir():
        for name in ('asset-map.json', 'player-map.json', 'volume-map.json', 'search-map.json'):
            source = a.template / name
            if source.exists():
                (a.output / name).write_bytes(source.read_bytes())
    if plan:
        plan['template_sha256'] = template_digest(a.output)
        a.output_plan.write_text(json.dumps(plan, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(source_records=len(old['records']), input_records=len(new['records']),
                          template_sha256=template_digest(a.output))))


if __name__ == '__main__':
    main()
