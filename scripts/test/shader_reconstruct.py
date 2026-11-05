"""Synthetic tests of bounded asset vertex discovery and original-slice checks."""
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import os
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import shader_reconstruct as m
from preparation_workers import compiler_workers
from preparation_profile import enabled

assert not enabled({}) and enabled({'GT5P_PREPARE_SHADER_PROFILE':'1'})
for value in ('','2','true'):
    try:enabled({'GT5P_PREPARE_SHADER_PROFILE':value})
    except ValueError:pass
    else:raise AssertionError('Invalid shader profile accepted')
with patch.dict(os.environ,{'GT5P_PREPARE_SHADER_PROFILE':'0','RSX_PREPARE_SHADER_PROFILE':'1'}):
    assert 'RSX_PREPARE_SHADER_PROFILE' not in m.offline_env(Path('game'),Path('cache'))
with patch.dict(os.environ,{'GT5P_PREPARE_SHADER_PROFILE':'1'}):
    assert m.offline_env(Path('game'),Path('cache'))['RSX_PREPARE_SHADER_PROFILE']=='1'

with patch.dict(os.environ,{'GT5P_PREPARE_NATIVE_PROFILE':'0','RSX_PSO_PREPARE_PROFILE':'1'}):
    assert 'RSX_PSO_PREPARE_PROFILE' not in m.offline_env(Path('game'),Path('cache'))
with patch.dict(os.environ,{'GT5P_PREPARE_NATIVE_PROFILE':'1'}):
    assert m.offline_env(Path('game'),Path('cache'))['RSX_PSO_PREPARE_PROFILE']=='1'
for value in ('','2','true'):
    with patch.dict(os.environ,{'GT5P_PREPARE_NATIVE_PROFILE':value}):
        try:m.native_profile()
        except ValueError:pass
        else:raise AssertionError('Invalid native profile setting accepted')

# Default: logical processors minus two, 2..10, no RAM limit applied when unknown; `legacy` is the old 4-or-2 rule.
for cpus, expected, legacy in ((None,2,2),(2,2,2),(4,2,2),(7,5,2),(8,6,4),(12,10,4),(64,10,4)):
    with patch('preparation_workers.os.cpu_count',return_value=cpus), patch('preparation_workers._available_memory',return_value=None):
        assert compiler_workers({}) == compiler_workers({'GT5P_PREPARE_COMPILER_WORKERS':'auto'}) == expected
        assert compiler_workers({'GT5P_PREPARE_COMPILER_WORKERS':'legacy'}) == legacy
with patch('preparation_workers.os.cpu_count',return_value=12):
    for memory, expected in ((64*1024**3,10),(6*1024**3,10),(3*1024**3,8),(2*1024**3,4),(1024**3,2),(1,2)):
        with patch('preparation_workers._available_memory',return_value=memory):
            assert compiler_workers({}) == expected
os.environ['GT5P_PREPARE_COMPILER_WORKERS'] = '2'  # Controlled fixture for existing environment checks.
for count in ('2','3','4','6','10','12'):
    assert compiler_workers({'GT5P_PREPARE_COMPILER_WORKERS':count}) == int(count)
    with patch.dict(os.environ, {'GT5P_PREPARE_COMPILER_WORKERS':count, 'RSX_SHADER_WORKERS':'32'}):
        assert m.offline_env(Path('game'),Path('cache'))['RSX_SHADER_WORKERS'] == count
for count in ('','1','13','32','02','4 ','-3','x',True):
    try:compiler_workers({'GT5P_PREPARE_COMPILER_WORKERS':count})
    except ValueError:pass
    else:raise AssertionError('Unbounded compiler count accepted')

assert m.offline_warmup({}) == m.offline_warmup({'GT5P_PREPARE_OFFLINE_WARMUP':'0'}) == '0'
assert m.offline_warmup({'GT5P_PREPARE_OFFLINE_WARMUP':'1'}) == '1'
for warmup in ('','2','auto','1 ','01'):
    try:
        m.offline_warmup({'GT5P_PREPARE_OFFLINE_WARMUP':warmup})
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid offline warmup choice accepted')
with patch.dict(os.environ, {'GT5P_PREPARE_OFFLINE_WARMUP':'0','RSX_SHADER_WARMUP':'1','RSX_SHADER_WORKERS':'32'}):
    env = m.offline_env(Path('private-game'), Path('private-cache'))
    assert env['RSX_SHADER_WARMUP']=='1' and env['GT5P_PREPARE_OFFLINE_WARMUP']=='0'
    assert env['RSX_SHADER_WORKERS']=='2' and env['RSX_PSO_ASYNC']=='0'
with patch.dict(os.environ, {'GT5P_PREPARE_OFFLINE_WARMUP':'1'}):
    assert m.offline_env(Path('private-game'), Path('private-cache'))['GT5P_PREPARE_OFFLINE_WARMUP']=='1'

with patch.dict(os.environ, {'GT5P_OFFLINE_FLUSH':'0', 'GT5P_NO_PRESENT':'1', 'RSX_PSO_ASYNC':'1'}):
    env = m.offline_env(Path('private-game'), Path('private-cache'))
    assert env['GT5P_OFFLINE_FLUSH']=='0' and env['RSX_PSO_ASYNC']=='0'
    assert 'GT5P_NO_PRESENT' not in env
with patch.dict(os.environ, {'GT5P_OFFLINE_FLUSH':'1'}):
    assert 'GT5P_OFFLINE_FLUSH' not in m.offline_env(Path('private-game'), Path('private-cache'))


def bundle(base=0, header=0):
    data = bytearray(512)
    if base != header:
        data[base:base + 4] = b'MDL3'
    data[header:header + 4] = b'SHDS'
    struct.pack_into('>H', data, header + 0x18, 1)
    struct.pack_into('>I', data, header + 0x20, 128)
    struct.pack_into('>II', data, base + 128, 256, 80)
    struct.pack_into('>H', data, base + 256, 3)
    struct.pack_into('>I', data, base + 256 + 0x10, 32)
    data[base + 288:base + 336] = bytes(range(48))
    return data


plain = bundle()
result = list(m.vertex_programs(plain))
assert result == [dict(header=0, offset=288, size=48, wrapper=256, wrapper_size=80)]
assert list(m.vertex_programs(bundle(16, 64)))[0]['offset'] == 304
for offset, fmt, value in [(0x18, '>H', 8193), (0x20, '>I', 1024),
                            (256, '>H', 0), (256, '>H', 2049),
                            (272, '>I', 31), (272, '>I', 1024)]:
    data = bundle()
    struct.pack_into(fmt, data, offset, value)
    assert list(m.vertex_programs(data)) == []
assert list(m.vertex_programs(b'SHDS')) == []
assert m.word_swap(m.word_swap(bytes(range(48)))) == bytes(range(48))
try:
    m.word_swap(b'123')
except ValueError:
    pass
else:
    raise AssertionError('unaligned words accepted')

with tempfile.TemporaryDirectory() as folder:
    path = Path(folder) / 'synthetic-asset'
    path.write_bytes(plain)
    code = m.word_swap(plain[288:336])
    matches, count = m.discover_vertices([path], {48: {code: {'synthetic-id'}}})
    assert count == 1 and matches['synthetic-id']['order'] == 'swap32'
    assert matches['synthetic-id']['size'] == 48
    candidate = matches['synthetic-id']
    assert m.read_slice(candidate) == plain[288:336]
    path.write_bytes(bytes(len(plain)))
    try:
        m.read_slice(candidate)
    except ValueError:
        pass
    else:
        raise AssertionError('changed original asset accepted')
    # An empty file must not be mapped; an absent matching prefix isn't a hit.
    path.write_bytes(b'')
    assert m.discover_vertices([path], {48: {code: {'synthetic-id'}}}) == ({}, 0)

values = dict(blend=0, cmask=15, depth_bits=0x30000000, cull_enable=1, stencil_enable=0)
capture = dict(state=dict(blend=0, cmask=15, stencil=0x30000000, cull=5))
assert m.material_state_matches(values, capture)
for field, value in [('blend', 1), ('cmask', 14), ('depth_bits', 0x10000000),
                     ('cull_enable', 0), ('stencil_enable', 1)]:
    changed = dict(values); changed[field] = value
    assert not m.material_state_matches(changed, capture)
for stencil in (0x30000001, 0x34000000):
    changed = dict(state=dict(capture['state'], stencil=stencil))
    assert not m.material_state_matches(values, changed)

# Pass paths cannot silently enter a proof without explicit material samplers.
command = [sys.executable, str(Path(m.__file__))]
for flag in ('report', 'trace', 'catalog', 'cache', 'decoder', 'engine', 'game-root', 'output'):
    command += ['--' + flag, 'unused-test-input']
for flag, path in (('--environment-sampler-path', 'framebuffer-single'),
                   ('--environment-sampler-path', 'framebuffer-mipped'),
                   ('--mirror-sampler-path', 'scene-copy')):
    result = subprocess.run(command + [flag, path], capture_output=True, text=True)
    assert result.returncode != 0 and 'require a material sampler proof' in result.stderr

for flag in ('--material-texture-shapes', '--material-texture-state'):
    result = subprocess.run(command + [flag], capture_output=True, text=True)
    assert result.returncode != 0 and 'requires a material sampler proof' in result.stderr

result = subprocess.run(command + ['--environment-texture-path', 'framebuffer-cube'], capture_output=True, text=True)
assert result.returncode != 0 and 'requires framebuffer sampler and texture reconstruction options' in result.stderr

print('SHDS bounds, source integrity and prepared material-state eligibility checks passed')

from shader_pass_state import object_pass_fields, pass_matches, replace_pass_fields
for path, enabled_key in (('ccw', 5), ('cw', 1)):
    for enable in (0, 1):
        fields = object_pass_fields(path, dict(cull_enable=enable))
        state = dict(cull=enabled_key if enable else 0, cube=0x80011000, ghi=7)
        assert pass_matches(fields, state)
        assert replace_pass_fields(fields, dict(state, cull=7, cube=0x80010000)) == state
        assert not pass_matches(fields, dict(state, cube=state['cube'] ^ 4096))
        assert not pass_matches(fields, dict(state, cull=7))
result = subprocess.run(command + ['--object-pass-path', 'ccw'], capture_output=True, text=True)
assert result.returncode != 0 and 'requires --prepared-material-state' in result.stderr
print('Conditional object-pass selection, independent replacement and prerequisites passed')

from shader_pass_state import native_target_fields, target_matches, replace_target_fields, TARGET_PATHS
for path in TARGET_PATHS:
    fields = native_target_fields(path)
    state = dict(cube=0x80001000 | fields['cube_value'], stencil=0xb0000000,
                 rtfmt=fields['rtfmt'], nrt=1, cull=5)
    capture = dict(state=state, vp_gpu=1)
    assert target_matches(fields, capture)
    assert replace_target_fields(fields, dict(state, rtfmt=99, nrt=8, cube=0x800f1000)) == state
    for key, value in [('nrt', 2), ('rtfmt', 10), ('stencil', 0xb8000000)]:
        assert not target_matches(fields, dict(capture, state=dict(state, **{key: value})))
    assert not target_matches(fields, dict(capture, vp_gpu=0))
result = subprocess.run(command + ['--native-target-path', 'rgba16-msaa2'], capture_output=True, text=True)
assert result.returncode != 0 and 'requires --object-pass-path' in result.stderr
print('Explicit native target selection, masked sample replacement and unsupported path checks passed')

result = subprocess.run(command + ['--material-fragment-control'], capture_output=True, text=True)
assert result.returncode != 0 and 'requires --materials' in result.stderr
print('Authored fragment-control proof prerequisites passed')

result = subprocess.run(command + ['--independent-profile-path', 'ordinary-uploads'], capture_output=True, text=True)
assert result.returncode != 0 and 'Independent profile requires' in result.stderr
print('Whole independent profile prerequisites passed')
result = subprocess.run(command + ['--shared-cpu-inputs'], capture_output=True, text=True)
assert result.returncode != 0 and 'requires a named shared pass' in result.stderr
print('Authored shared CPU input-layout prerequisites passed')
