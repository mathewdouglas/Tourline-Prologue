"""Maintainer-only numeric archive map; users need no unpacker or extracted assets.

The input listing is local GTToolsSharp `listfiles` output. All resulting member
and program locations must verify directly against the original volume before
metadata is written. No filenames, key bytes or shader contents are emitted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline_asset_map import read as read_programs,files
from game_volume import SCHEMA,validate,resolve


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('entries','assets','elf','volume','program-map','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    for name in ('magic-offset','magic-size','polynomials-offset','data-offset'):
        ap.add_argument('--'+name,type=lambda value:int(value,0),required=True)
    a=ap.parse_args()
    if a.output.exists():ap.error('Choose a fresh metadata output')
    locations=read_programs(a.program_map)
    elf_id=hashlib.sha256(a.elf.read_bytes()).hexdigest()
    wanted={r['container']:r['container_size'] for r in locations['records'] if r['container']!=elf_id}
    if a.entries.stat().st_size>4*1024**2:raise ValueError('Archive listing budget exceeded')
    pattern=re.compile(r'^(.*?) - Flags: (.*?) \| FileIndex: (\d+) .*?\| SegIndex: (\d+), ZSize: ([0-9A-Fa-f]+) \| Size: ([0-9A-Fa-f]+) \|')
    entries={}
    for line in a.entries.read_text().splitlines():
        m=pattern.match(line)
        if not m:continue
        if m[1] in entries:raise ValueError('Duplicate archive entry')
        if m[2] not in ('Compressed','None'):continue
        entries[m[1]]=dict(compressed=m[2]=='Compressed',seed=int(m[3]),
            offset=a.data_offset+2048*int(m[4]),stored_size=int(m[5],16),size=int(m[6],16))
    rows={};sizes=set(wanted.values())
    assets=a.assets.resolve()
    for path in files(assets,a.elf):
        if assets not in path.resolve().parents or path.stat().st_size not in sizes:continue
        with path.open('rb') as stream:identity=hashlib.file_digest(stream,'sha256').hexdigest()
        if identity in wanted and identity not in rows:
            entry=entries[path.relative_to(assets).as_posix()]
            if entry['size']!=wanted[identity]:raise ValueError('Listing/container size mismatch')
            rows[identity]=dict(container=identity,**entry)
    if set(rows)!=set(wanted):raise ValueError('Archive locations do not cover every required container')
    with a.volume.open('rb') as stream:volume_id=hashlib.file_digest(stream,'sha256').hexdigest()
    document=validate(dict(schema=SCHEMA,version=1,elf_sha256=elf_id,volume_sha256=volume_id,
        volume_size=a.volume.stat().st_size,key_location=dict(magic_offset=a.magic_offset,
        magic_size=a.magic_size,polynomials_offset=a.polynomials_offset),records=sorted(rows.values(),key=lambda r:r['offset'])))
    vp,fp,report=resolve(locations,document,a.volume,a.elf)
    if len(vp)+len(fp)!=len({(r['stage'],r['id']) for r in locations['records']}):raise ValueError('Program lookup did not verify every identity')
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(document,indent=2)+'\n')
    print(json.dumps(dict(archive_members=len(rows),vertices=len(vp),fragments=len(fp),lookup=report)))


if __name__=='__main__':main()
