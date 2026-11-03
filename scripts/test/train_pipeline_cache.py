"""Learned-recipe/dependency and completed-route validation checks."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import os
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import train_pipeline_cache as m


def envelope(key, vs, ps):
    data = bytearray(2760)
    struct.pack_into('<QIIQQQII', data, 0, 0x31574d5241503547, 1, 2760, key,
                     m.fnv64(vs), m.fnv64(ps), len(vs), len(ps))
    struct.pack_into('<Q', data, 2752, m.fnv64(data[:-8]))
    return data


with tempfile.TemporaryDirectory() as temporary:
    root = Path(temporary)
    cache = root / 'shadercache'
    warm = cache / 'warmup-v1'
    warm.mkdir(parents=True)
    vs, ps = b'DXBC-test-vertex', b'DXBC-test-fragment'
    for payload in (vs, ps):
        (warm / f'code_{m.fnv64(payload):016x}.dxbc').write_bytes(payload)
    recipe = warm / 'pso_0000000000000001.recipe'
    data = envelope(1, vs, ps)
    recipe.write_bytes(data)
    assert m.bounded_cache_read(recipe,2760) == data
    try:m.bounded_cache_read(recipe,2759)
    except ValueError:pass
    else:raise AssertionError('Oversized cache read accepted')
    actual_stat = os.fstat
    for delta in (-1,1):
        with patch.object(m.os,'fstat',side_effect=lambda fd:SimpleNamespace(st_size=actual_stat(fd).st_size+delta)):
            try:m.bounded_cache_read(recipe,16384)
            except ValueError:pass
            else:raise AssertionError('Changed/short cache read accepted')
    with patch.object(m.os,'fstat',side_effect=[SimpleNamespace(st_size=len(data)),SimpleNamespace(st_size=len(data)+1)]):
        try:m.bounded_cache_read(recipe,16384)
        except ValueError:pass
        else:raise AssertionError('Post-read growth accepted')
    assert m.validate_recipe(recipe) == '0000000000000001'
    assert m.inventory(cache)['recipes'] == ['0000000000000001']
    assert not m.inventory(cache, True)['valid_driver_blobs']
    blob = b'local-test-driver-blob'
    native = cache / 'pso_0000000000000001.bin'
    native.write_bytes(struct.pack('<QQQ', 0x31534f5035505447, len(blob), m.fnv64(blob)) + blob)
    assert m.inventory(cache, True)['valid_driver_blobs'] == ['0000000000000001']
    native.write_bytes(native.read_bytes()[:-1])
    assert not m.inventory(cache, True)['valid_driver_blobs']
    for offset in (0, 8, 12, 16, 40, 2752):
        damaged = bytearray(data)
        damaged[offset] ^= 1
        recipe.write_bytes(damaged)
        assert len(m.inventory(cache)['rejected']) == 1
        assert not m.inventory(cache)['recipes']
    recipe.write_bytes(data)
    code = warm / f'code_{m.fnv64(vs):016x}.dxbc'
    code.write_bytes(b'DXBC-bad-hash')
    assert len(m.inventory(cache)['rejected']) == 1
    code.write_bytes(vs)
    assert not m.inventory(cache)['rejected']
    # Shared dependencies are checked once per identity, including under four
    # readers; any damaged shared code rejects every referencing recipe.
    for key in range(2,98):
        (warm/f'pso_{key:016x}.recipe').write_bytes(envelope(key,vs,ps))
    original_read = m.bounded_cache_read
    reads = []
    def counted(path, maximum):
        if path.suffix == '.dxbc':reads.append(path.name)
        return original_read(path, maximum)
    with patch.object(m,'bounded_cache_read',side_effect=counted):
        fast = m.inventory_batched(cache,True)
    assert len(reads) == 2 and len(set(reads)) == 2
    assert fast == m.inventory_legacy(cache,True)
    code.write_bytes(b'DXBC-corrupt')
    fast = m.inventory_batched(cache,True)
    assert len(fast['rejected']) == 97 and not fast['recipes']
    assert fast == m.inventory_legacy(cache,True)
    code.write_bytes(vs)
    # A valid recipe checksum cannot authorize an incorrect dependency length.
    mismatch = bytearray(envelope(98,vs,ps))
    struct.pack_into('<I',mismatch,40,len(vs)+1)
    struct.pack_into('<Q',mismatch,2752,m.fnv64(mismatch[:-8]))
    (warm/'pso_0000000000000062.recipe').write_bytes(mismatch)
    checked = m.inventory_batched(cache,True)
    assert len(checked['recipes']) == 97 and len(checked['rejected']) == 1
    assert checked == m.inventory_legacy(cache,True)
    (warm/'pso_0000000000000062.recipe').unlink()
    # Cancellation must join all submitted reads before returning to its owner.
    calls = []
    def cancelled(phase,counts):
        calls.append(counts)
        raise KeyboardInterrupt('cancel scan')
    try:m.inventory_batched(cache,True,cancelled)
    except KeyboardInterrupt:pass
    else:raise AssertionError('Scan cancellation swallowed')
    assert len(calls) == 1
    for value in ('1','32'):assert m.verification_batch({'GT5P_PREPARE_VERIFY_BATCH':value}) == int(value)
    for value in ('','0','2','64',True):
        try:m.verification_batch({'GT5P_PREPARE_VERIFY_BATCH':value})
        except ValueError:pass
        else:raise AssertionError('Unbounded verification batch accepted')
    logs = root / 'logs'
    logs.mkdir()
    window = dict(sample_start_ms=1000, sample_end_ms=2000)
    (logs / 'route.window.json').write_text(json.dumps(window))
    (logs / 'route.out').write_text('[milestone] QuickArcadeRoot at 900 ms\n')
    (logs / 'route.frames.csv').write_text('\n'.join(f'{t},1,1' for t in range(1000, 2001, 20)))
    assert m.route_result(logs, 'route')['presented_samples'] == 51
    (logs / 'route.frames.csv').write_text('1000,1,1\n900,1,1\n')
    try:
        m.route_result(logs, 'route')
    except ValueError:
        pass
    else:
        raise AssertionError('Insufficient presented frames accepted')
    assert recipe.exists() and native.exists(), 'Validation must never delete damaged cache files'
    m.writable_tree(cache, root)
    try:
        m.writable_tree(cache, logs)
    except ValueError:
        pass
    else:
        raise AssertionError('Escaping writable path accepted')
    report = root / 'report.json'
    m.save_report(report, dict(status='visiting'))
    m.save_report(report, dict(status='complete'))
    assert json.loads(report.read_text()) == dict(status='complete')
print('Recipe checksums/dependencies, driver envelopes, route validation and preservation checks passed')
