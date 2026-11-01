"""Verify locally prepared asset recipes, both bytecodes and native keys.

Read-only; no game/compiler starts. Inputs and game-derived data stay local.
"""
import argparse
import json
from pathlib import Path
import struct
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from shader_coverage import bounded_read, fnv64
from pipeline_template import native_state
from native_pipeline_key import native_key, root_signature_hash
from train_pipeline_cache import inventory

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--output', required=True, type=Path)
args = ap.parse_args()
root = args.output.resolve()
report = json.loads(bounded_read(root / 'report.json', 32 * 1024 ** 2))
manifest = json.loads(bounded_read(root / 'manifest.json', 32 * 1024 ** 2))
assert report['selected_jobs'] == len(report['jobs']) == len(manifest) > 0
jobs = {j['id']: j for j in manifest}
assert len(jobs) == len(manifest)
root_hash = root_signature_hash()
keys = set()
for result in report['jobs']:
    job = jobs[result['id']]
    assert result['status'] == 'prepared' and result['native_result']['expected'] == '0000000000000000'
    request = bounded_read(root / 'jobs' / job['id'] / 'pipeline/request.recipe', 16384)
    assert struct.unpack_from('<Q', request, 16)[0] == 0
    # Only bytecode lengths may appear in the native descriptor supplied to the
    # renderer: the material/pass/target construction must not depend on captures.
    empty = bytearray(request[48:704]); empty[16:24] = bytes(8); empty[32:40] = bytes(8)
    assert not any(empty)
    key = result['pipeline']
    recipe = bounded_read(root / 'shadercache/warmup-v1' / f'pso_{key}.recipe', 16384)
    assert struct.unpack_from('<Q', recipe, 16)[0] == int(key, 16)
    assert struct.unpack_from('<Q', recipe, 2752)[0] == fnv64(recipe[:-8])
    blobs = []
    for code_id, source_id, offset in ((result['vs'], result['vs_source'], 24),
                                       (result['ps'], result['ps_source'], 32)):
        assert struct.unpack_from('<Q', recipe, offset)[0] == int(code_id, 16)
        code = bounded_read(root / 'shadercache' / f'{source_id}.dxbc', 4 * 1024 ** 2)
        assert f'{fnv64(code):016x}' == code_id
        blobs.append(code)
    assert native_key(dict(native=native_state(recipe)), *blobs, root_hash) == key
    keys.add(key)
checked = inventory(root / 'shadercache', validate_blobs=True)
assert not checked['rejected'] and keys <= set(checked['valid_driver_blobs'])
print(f"Verified {len(report['jobs'])} asset requests, {len(keys)} distinct native keys, both stages and persisted driver blobs")
