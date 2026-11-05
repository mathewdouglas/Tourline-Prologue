"""Maintainer metadata generator. Original program bytes never enter the output."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import shader_enumerate as enum
import pipeline_asset_map as locations
import game_volume
import pipeline_template


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    root = Path(__file__).resolve().parents[2]
    template = root / 'assets/pipeline-templates/gt5p-disc-v2'
    for name in ('catalog', 'volume', 'elf'):
        ap.add_argument('--'+name, type=Path, required=True)
    ap.add_argument('--template', type=Path, default=template, help='starter folder (default: the shipped one)')
    ap.add_argument('--volume-map', type=Path, default=None, help='default: <template>/search-map.json')
    ap.add_argument('--output', type=Path, default=None,
                    help='fresh folder; default is a private scratch folder whose result replaces '
                         'assets/shader-enumeration/gt5p-disc-v1 after the player loader accepts it')
    a = ap.parse_args()
    a.volume_map = a.volume_map or a.template / 'search-map.json'
    final = root / 'assets/shader-enumeration/gt5p-disc-v1'
    replace = a.output is None
    if replace:
        a.output = root / 'scratch' / 'enumeration-repin'
        if a.output.exists():
            raise ValueError('Remove scratch/enumeration-repin first')
        a.output.parent.mkdir(exist_ok=True)
    a.output.mkdir(parents=True, exist_ok=False)
    fragments, rejected = enum.fragment_inventory(a.catalog, print)
    files = enum.container_files(a.catalog)
    vertices = enum.vertex_inventory(files, print)
    materials = enum.material_index(files, print)
    records = pipeline_template.read(a.template)['records']
    infos = enum._make_infos(fragments, materials, set(fragments))
    contexts = enum.train_contexts(enum.template_rows(records, fragments, materials), infos)
    jobs = enum.fragment_jobs_for(infos, fragments, contexts, set(fragments), [2], None, 4, None)
    sources = json.loads((a.catalog/'index.json').read_text())['sources']
    by_payload = {}
    for source in sources:
        by_payload.setdefault(source['sha256'], []).append(source)
    hashes = {}
    def container(name):
        if name not in hashes:
            with open(name, 'rb') as stream:
                hashes[name] = hashlib.file_digest(stream, 'sha256').hexdigest()
        return hashes[name]
    archive = game_volume.read(a.volume_map)
    members = {r['container']: r for r in archive['records']}
    rows = []
    for identity, payloads in sorted(fragments.items()):
        # Catalogue constants can differ; locate the selected exact payload.
        payload = payloads[0]
        candidates = by_payload[payload['payload']]
        source = next((s for s in candidates if container(s['file']) in members or
                       container(s['file']) == archive['elf_sha256']), None)
        if source is None:
            raise ValueError('Missing verified archive container for '+identity)
        raw = enum.bounded_read(a.catalog/(payload['payload']+'.fp'), enum.MAX_FP)
        with open(source['file'], 'rb') as stream:
            stream.seek(source['offset'])
            if stream.read(len(raw)) != raw:
                raise ValueError('Catalogue source does not match payload')
        rows.append(dict(stage='fp', id=identity, size=payload['size'], offset=source['offset'],
                         encoding='native', container=container(source['file']),
                         container_size=Path(source['file']).stat().st_size))
    for identity, entry in sorted(vertices.items()):
        enum.read_vertex(entry, identity)
        digest = container(entry['file'])
        if digest not in members and digest != archive['elf_sha256']:
            raise ValueError('Missing verified vertex container')
        rows.append(dict(stage='vp', id=identity, size=entry['size'], offset=entry['offset'],
                         encoding='swap32', container=digest,
                         container_size=Path(entry['file']).stat().st_size))
    programs = locations.validate(dict(schema=locations.SCHEMA, version=1, records=rows))
    needed = {r['container'] for r in rows}
    archive = dict(archive, records=[r for r in archive['records'] if r['container'] in needed])
    vp, fp, lookup = game_volume.resolve(programs, archive, a.volume, a.elf)
    if len(vp) != len(vertices) or len(fp) != len(fragments):
        raise ValueError('Packed volume did not verify every enumerable program')
    def write(name, document):
        data = json.dumps(document, sort_keys=True, separators=(',', ':')).encode('ascii')
        (a.output/name).write_bytes(data)
        return hashlib.sha256(data).hexdigest()
    pins = dict(programs=[write(f'programs-{n//3000:04d}.json',dict(programs,records=rows[n:n+3000]))
                          for n in range(0,len(rows),3000)], volume=write('volume.json', archive))
    # Intern profiles and identities to avoid repeating 64-byte identifiers per job.
    ids = sorted(fragments)
    profiles = sorted({tuple(p) for _, _, p in jobs})
    id_index = {v:i for i,v in enumerate(ids)}
    profile_index = {v:i for i,v in enumerate(profiles)}
    plan = dict(schema='gt5p-player-shader-enumeration', version=1,
                elf_sha256=archive['elf_sha256'], volume_sha256=archive['volume_sha256'],
                template_sha256=pipeline_template.template_digest(a.template), files=pins,
                identities=ids, profiles=profiles,
                fragment_jobs=[[id_index[i], profile_index[tuple(p)]] for i, _, p in jobs],
                vertex_jobs=[[i,g] for i in sorted(vertices) for g in (0,1)])
    write('plan.json', plan)
    summary = dict(fragments=len(fragments), vertices=len(vertices), fragment_jobs=len(jobs),
                          vertex_jobs=len(vertices)*2, profiles=len(profiles), containers=len(archive['records']),
                          rejected_payloads=len(rejected), lookup=lookup,
                          sizes={p.name:p.stat().st_size for p in a.output.iterdir()})
    if replace:
        from preparation_enumeration import load
        load(a.output, a.template)
        for old in final.glob('*.json'):
            old.unlink()
        for new in a.output.iterdir():
            new.replace(final / new.name)
        a.output.rmdir()
        summary['installed'] = str(final)
    print(json.dumps(summary))


if __name__ == '__main__':
    main()
