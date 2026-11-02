"""Fresh default/ultrawide/scaled native keys, cancellation and verified resume.

Parent-only sequential proof; original assets are read-only and no cache is removed.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pipeline_template as template
from pipeline_translation import sidecar
from train_pipeline_cache import idle, isolated
from shader_coverage import bounded_read


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('elf', 'engine', 'decoder', 'output'):
        ap.add_argument('--'+name, type=Path, required=True)
    source=ap.add_mutually_exclusive_group(required=True)
    source.add_argument('--assets', type=Path)
    source.add_argument('--volume', type=Path)
    ap.add_argument('--fragment-chunk', type=int, default=8)
    ap.add_argument('--count', type=int, default=32)
    a = ap.parse_args()
    if not 1 <= a.fragment_chunk < a.count:
        ap.error('Select a positive fragment chunk smaller than the record count')
    idle()
    out = isolated(a.output)
    if out.exists():
        raise ValueError('Use a fresh ignored output')
    out.mkdir()
    (out/'input').mkdir()
    shutil.copyfile(a.elf, out/'input/EMAIN.ELF')
    bundle = template.ROOT/'assets/pipeline-templates/gt5p-disc-v2'
    document = template.read(bundle)
    if not 2 <= a.count <= len(document['records']):
        raise ValueError('Invalid bounded proof count')
    if a.count == len(document['records']):
        chosen = document['records']
    else:
        chosen, seen = [], set()
        for r in document['records']:
            identity = (r['vp']['sha256'], r['vp_gpu'])
            if identity not in seen:
                seen.add(identity)
                chosen.append(r)
            if len(chosen) == a.count:
                break
        if len(chosen) != a.count:
            raise ValueError('Insufficient distinct variants for this proof')
    selected = out/'template.json'
    selected.write_text(json.dumps(dict(document, records=chosen)))
    arguments = (selected, None, a.elf.resolve(), a.engine.resolve(), a.decoder.resolve(), out, out/'preparation')
    options = dict(assets=a.assets.resolve() if a.assets else None, asset_map=bundle/'player-map.json',
                   volume=a.volume.resolve() if a.volume else None,
                   volume_map=bundle/'volume-map.json' if a.volume else None)
    cancelled = []
    def cancel(phase, counts):
        if phase == 'translation-fragment' and 0 < counts.get('completed',0) < a.count:
            cancelled.append(True)
            raise KeyboardInterrupt('Test cancellation after verified fragment chunk')
    try:
        with patch.dict(os.environ, GT5P_PREPARE_FRAGMENT_CHUNK=str(a.fragment_chunk)):
            template.prepare(*arguments, translation='ultrawide-native', progress=cancel, **options)
        raise AssertionError('Cancellation did not occur')
    except KeyboardInterrupt:
        assert cancelled
    state=json.loads((sidecar(out/'preparation','ultrawide-native')/'preparation-state.json').read_text())
    assert state['phase']=='interrupted'
    manifest_path=sidecar(out/'preparation','ultrawide-native')/'manifests'/(state['progress']['manifest_sha256']+'.json')
    kept=json.loads(manifest_path.read_text())['fragments']
    assert 0 < len(kept) < a.count
    cache = out/'preparation/shadercache'
    defaults = {r[k]+'.dxbc' for r in chosen for k in ('vp_source', 'fp_source')}
    before = {name:hashlib.sha256((cache/name).read_bytes()).hexdigest() for name in defaults}
    reports = {}
    for mode in ('ultrawide-native', 'native-scaled'):
        report = template.prepare(*arguments, translation=mode, resume=True, **options)
        extra = report['additional_translation']
        assert report['counts'] == extra['counts'] == {'prepared': a.count}
        assert extra['vertex_preparation']['launches'] == 0
        if mode == 'ultrawide-native':
            assert extra['fragment_jobs_reused'] == len(kept)
        assert all((cache/f"pso_{row['key']}.bin").is_file() for row in extra['records'])
        assert all((cache/f"pso_{r['key']}.bin").is_file() for r in chosen)
        assert {name:hashlib.sha256((cache/name).read_bytes()).hexdigest() for name in defaults} == before
        records = {r['key']:r for r in chosen}
        for recipe in (sidecar(out/'preparation', mode)/'r').glob('*/pipeline/request.recipe'):
            raw = bounded_read(recipe, 16384)
            words = list(struct.unpack_from('<164I', raw, 48))
            key = f'{struct.unpack_from("<Q", raw, 16)[0]:016x}'
            origin = next(row['template_key'] for row in extra['records'] if row['key'] == key)
            assert all(words[i] == records[origin]['native']['words'][i]
                       for i in range(164) if i not in (4, 5, 8, 9))
        reports[mode] = extra
    by_mode = {mode:{row['template_key']:row for row in report['records']} for mode,report in reports.items()}
    assert all(by_mode['native-scaled'][r['key']]['vp_source'] == r['vp_source'] for r in chosen)
    assert all(by_mode['native-scaled'][r['key']]['fp_source'] ==
               by_mode['ultrawide-native'][r['key']]['fp_source'] for r in chosen)
    assert any(by_mode['ultrawide-native'][r['key']]['vp_source'] != r['vp_source'] for r in chosen)
    assert any(by_mode['ultrawide-native'][r['key']]['key'] != r['key'] for r in chosen)
    # A default-only rerun must not touch either translation sidecar.
    sidecars = out/'preparation/tr'
    saved = {str(p.relative_to(sidecars)):hashlib.sha256(p.read_bytes()).hexdigest()
             for p in sidecars.rglob('*') if p.is_file()}
    template.prepare(*arguments, resume=True, **options)
    assert saved == {str(p.relative_to(sidecars)):hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sidecars.rglob('*') if p.is_file()}
    result = dict(records=a.count, modes=reports, cancelled_after_fragment_chunk=True,
        fragments_checkpointed_before_cancel=len(kept),
        default_shader_files_unchanged=True, default_rollback_leaves_sidecars=True,
        limitation='Observed-state translation proof on one GPU; warm driver/OS caches, no live rendering/stutter claim.')
    (out/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Default, ultrawide and scaled native keys, persistence, cancellation/resume and rollback passed')


if __name__ == '__main__':
    main()
