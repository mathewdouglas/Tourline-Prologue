"""Check a compatibility-only starter reissue against an explicit Git baseline."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from pipeline_template import read,renderer_contract,template_digest


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--baseline',required=True)
    a=ap.parse_args()
    def previous(path):
        return json.loads(subprocess.check_output(['git','-C',str(ROOT),'show',a.baseline+':'+path]))
    base='assets/pipeline-templates/gt5p-disc-v2/'
    index=previous(base+'index.json')
    parts=[previous(base+entry['file']) for entry in index['parts']]
    records=[record for part in parts for record in part['records']]
    current=read(ROOT/base)
    assert current['records']==records,'Pipeline records changed during contract reissue'
    old=parts[0]['compatibility'];new=dict(current['compatibility'])
    assert new.pop('renderer_sha256')==renderer_contract()
    assert new=={key:value for key,value in old.items() if key!='renderer_sha256'}
    plan='config/pipeline-warmup/gt5p-disc-v2.json'
    before=previous(plan);after=json.loads((ROOT/plan).read_text())
    assert after.pop('template_sha256')==template_digest(ROOT/base)
    before.pop('template_sha256');assert before==after,'Observed warmup membership changed'
    for name in ('asset-map.json','player-map.json','volume-map.json','search-map.json'):
        assert previous(base+name)==json.loads((ROOT/base/name).read_text())
    assert b'\r\n' not in (ROOT/base/'index.json').read_bytes()
    print(f'Contract reissue: {len(records)} unchanged records, maps and observed membership; LF index pin verified')


if __name__=='__main__':main()
