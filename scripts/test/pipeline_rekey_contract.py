"""Check the shipped starter against an explicit baseline after a sample-share re-key.

Only one-sample fragment identity (fp_source, ps, native ps length) and the pipeline
key may differ; multisample records, vertex state, record order, maps and observed
warmup membership (after old->new key mapping) must not change.
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from pipeline_template import read, renderer_contract, template_digest
from pipeline_template_rekey import check_change, single_sample


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline', required=True)
    a = ap.parse_args()

    def previous(path):
        return json.loads(subprocess.check_output(['git', '-C', str(ROOT), 'show', a.baseline + ':' + path]))
    base = 'assets/pipeline-templates/gt5p-disc-v2/'
    index = previous(base + 'index.json')
    parts = [previous(base + entry['file']) for entry in index['parts']]
    old = [record for part in parts for record in part['records']]
    current = read(ROOT / base)
    new = current['records']
    assert len(old) == len(new)
    mapping, changed, one, msaa = {}, 0, 0, 0
    for before, after in zip(old, new):
        check_change(before, after)
        mapping[before['key']] = after['key']
        if single_sample(before):
            one += 1
            changed += before != after
        else:
            msaa += 1
            assert before == after
    assert len(set(mapping.values())) == len(new) and len(mapping) == len(old)
    # Every changed record must carry the shared fragment text with its multisample twin.
    assert changed > 0
    compat_old = dict(parts[0]['compatibility'])
    compat_new = dict(current['compatibility'])
    assert compat_new.pop('renderer_sha256') == renderer_contract()
    assert compat_new == {k: v for k, v in compat_old.items() if k != 'renderer_sha256'}
    plan_path = 'config/pipeline-warmup/gt5p-disc-v2.json'
    before = previous(plan_path)
    after = json.loads((ROOT / plan_path).read_text())
    assert after.pop('template_sha256') == template_digest(ROOT / base)
    assert before.pop('template_sha256')
    assert before['phases'].keys() == after['phases'].keys()
    for phase, keys in before['phases'].items():
        assert [mapping[k] for k in keys] == after['phases'][phase]
        del after['phases'][phase]
    before.pop('phases'); after.pop('phases')
    assert before == after, 'Warmup plan metadata changed'
    for name in ('asset-map.json', 'player-map.json', 'volume-map.json', 'search-map.json'):
        assert previous(base + name) == json.loads((ROOT / base / name).read_text())
    assert b'\r\n' not in (ROOT / base / 'index.json').read_bytes()
    print(f'Re-key audit: {len(new)} records, {changed} one-sample records re-keyed '
          f'({one - changed} unchanged), {msaa} multisample unchanged; vertex state, maps and '
          'warmup membership preserved; contract reissued')


if __name__ == '__main__':
    main()
