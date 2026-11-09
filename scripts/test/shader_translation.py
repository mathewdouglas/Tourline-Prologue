"""Translation environments and derive acceptance. No compiler process and no game."""
import hashlib
import ctypes
import json
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
from shader_reconstruct import offline_env
import shader_fragment_batch
import shader_translation
import shader_vertex_batch as batch
from prepare_material_shaders import source_key
from shader_coverage import fnv64

program = bytes(range(16))
hlsl = b'float4 main(){return 0;}\n'
dxbc = b'DXBCderived-vertex'
digest = hashlib.sha256(program).hexdigest()
source_id = f'{source_key(hlsl, __import__('shader_compiler').targets()[0]):016x}'
code_id = f'{fnv64(dxbc):016x}'


def assert_raises(func, kind=Exception):
    try:
        func()
    except kind:
        return
    raise AssertionError('Expected failure was accepted')


def clock():
    state = {'now': 0}
    def monotonic():
        return state['now']
    def sleep(seconds):
        state['now'] += seconds
    return monotonic, sleep


# Fixed modes. Names are not resolutions, and the returned dict cannot change the table.
assert shader_translation.MODES == ('default', 'ultrawide-native', 'native-scaled')
assert shader_translation.overlay('default') == {'RSX_ULTRAWIDE': '0'}
assert shader_translation.overlay('ultrawide-native') == {'RSX_ULTRAWIDE': '2'}
assert shader_translation.overlay('native-scaled') == {'RSX_ULTRAWIDE': '0', 'RSX_RENDER_HEIGHT': '1440'}
changed = shader_translation.overlay('default')
changed['RSX_ULTRAWIDE'] = '9'
changed['RSX_RENDER_HEIGHT'] = '2160'
assert shader_translation.overlay('default') == {'RSX_ULTRAWIDE': '0'}
for bad in ('', '1440p', '1080p', 'UW2', 'ultrawide', 'native', 'default-ultrawide', None, 1440):
    assert_raises(lambda: shader_translation.overlay(bad))
    assert_raises(lambda: shader_translation.environment(bad, {}))

base = {
    'PATH': 'C:\\tools',
    'TEMP': 'C:\\temp\\café',
    'RSX_ULTRAWIDE': '2',
    'rsx_render_height': '2160',
    'RSX_ULTRAWIDE_ASPECT': '2.370',
    'FP_LEAK': '1',
    'VP_LEAK': '1',
    'GT5P_ROOT': 'C:\\game',
    'GT5P_PREPARE_HASH_LIBRARY': 'C:\\cache-hash.dll',
    'PAD_HOLD': '1',
    'PPU_X': '1',
    'SPU_X': '1',
    'D3D12_X': '1',
    'CULL_X': '1',
    'PS3_HEADLESS': '1',
    'ps3_headless': '1',
}
with patch.dict(os.environ, {'rsx_aniso':'1', 'fp_constbuf':'0', 'ps3_headless':'1'}):
    native_env = offline_env(Path('unused'), Path('unused-cache'))
assert all(key not in native_env for key in ('rsx_aniso', 'fp_constbuf', 'ps3_headless'))
default_env = shader_translation.environment('default', base)
assert base['RSX_ULTRAWIDE'] == '2' and default_env is not base
assert default_env['PATH'] == 'C:\\tools' and default_env['TEMP'].endswith('café')
assert default_env['RSX_ULTRAWIDE'] == '0'
assert 'RSX_RENDER_HEIGHT' not in default_env and 'rsx_render_height' not in default_env
for key in default_env:
    folded = key.upper()
    # Phase 231: the compiler and its DLL are passed on explicitly (the workers must compile as the parent does).
    assert folded in ('RSX_ULTRAWIDE', 'RSX_SHADER_COMPILER', 'GT5P_PREPARE_DXC_LIBRARY') or not folded.startswith(shader_translation.PREFIXES)
    assert folded != 'PS3_HEADLESS'
assert default_env['RSX_SHADER_COMPILER'] == __import__('shader_compiler').mode(base) and default_env['GT5P_PREPARE_DXC_LIBRARY'].endswith('dxcompiler.dll')
assert shader_translation.environment('default', dict(base, RSX_SHADER_COMPILER='fxc'))['RSX_SHADER_COMPILER'] == 'fxc'
assert shader_translation.environment('default', dict(base, RSX_SHADER_COMPILER='dxc', RSX_SHADER_INTERP='1'))['RSX_SHADER_COMPILER'] == 'fxc'
assert 'GT5P_PREPARE_HASH_LIBRARY' not in default_env
assert 'shadercache' not in ''.join(default_env.values()).lower()
ultrawide = shader_translation.environment('ultrawide-native', base)
assert ultrawide['RSX_ULTRAWIDE'] == '2' and 'RSX_RENDER_HEIGHT' not in ultrawide
assert 'RSX_ULTRAWIDE_ASPECT' not in ultrawide
scaled = shader_translation.environment('native-scaled', {'PATH': 'C:\\cache-1080\\bin'})
assert scaled['RSX_ULTRAWIDE'] == '0' and scaled['RSX_RENDER_HEIGHT'] == '1440'
assert scaled['PATH'] == 'C:\\cache-1080\\bin'
assert_raises(lambda: shader_translation.environment('default', {'PATH': 1}))

installed = {
    'RSX_SHADER_CACHE': 'C:\\cache-1080',
    'RSX_SHADER_LIBRARY_BATCH': 'C:\\work',
    'RSX_FINAL_DITHER': '1',
    'RSX_ULTRAWIDE': '2',
    'rsx_RENDER_HEIGHT': '2160',
    'GT5P_NO_SETTINGS': '1',
    'PATH': 'C:\\tools',
}
shader_translation.apply(installed, 'default')
assert installed['RSX_ULTRAWIDE'] == '0' and 'RSX_RENDER_HEIGHT' not in installed
assert 'rsx_RENDER_HEIGHT' not in installed
assert installed['RSX_SHADER_CACHE'] == 'C:\\cache-1080'
assert installed['RSX_SHADER_LIBRARY_BATCH'] == 'C:\\work' and installed['RSX_FINAL_DITHER'] == '1'
assert installed['GT5P_NO_SETTINGS'] == '1'
shader_translation.apply(installed, 'native-scaled')
assert installed['RSX_RENDER_HEIGHT'] == '1440' and installed['RSX_SHADER_CACHE'] == 'C:\\cache-1080'
shader_translation.apply(installed, 'ultrawide-native')
assert installed['RSX_ULTRAWIDE'] == '2' and 'RSX_RENDER_HEIGHT' not in installed

text = batch._environment_text(default_env)
assert text.endswith('\0\0') and not text.endswith('\0\0\0')
entries = text.split('\0')
assert entries[-2:] == ['', '']
body = entries[:-2]
assert [item.split('=', 1)[0] for item in body] == sorted(
    (item.split('=', 1)[0] for item in body), key=str.upper)
assert 'RSX_ULTRAWIDE=0' in body and 'TEMP=C:\\temp\\café' in body
assert all(not item.startswith('RSX_RENDER_HEIGHT=') for item in body)
assert all('FP_LEAK' not in item and 'GT5P_ROOT' not in item for item in body)
block = batch._environment_block(default_env)
assert ctypes.string_at(block, len(text.encode('utf-16-le'))) == text.encode('utf-16-le')
unicode_env = shader_translation.environment('default', {'PATH': 'C:\\tools\\\U0001f3ce'})
expected_unicode = batch._environment_text(unicode_env).encode('utf-16-le')
assert ctypes.string_at(batch._environment_block(unicode_env), len(expected_unicode)) == expected_unicode
assert_raises(lambda: batch._environment_text({'PATH': 'C:\\bin', 'path': 'C:\\other'}))
assert_raises(lambda: batch._environment_text({'PATH': 'C:\\bin\n'}))
assert_raises(lambda: batch._environment_text({}))

# Fragment overlay is after offline_env. A cache path that mentions 1080 does not select a height.
raw = b'\0' * 16
state = dict(exp32=0, cube=0, stencil=0, unnorm=0, samplers='0' * 16, ghi=0, shd=0, unhi=0,
             rtfmt=28, nrt=1, cmask=15)
fragment_job = dict(id='first', fragment=raw, fragment_sha256=hashlib.sha256(raw).hexdigest(), state=state, used=0)
dirty = {
    'RSX_ULTRAWIDE': '2',
    'RSX_RENDER_HEIGHT': '2160',
    'FP_LEAK': '1',
    'VP_LEAK': '1',
    'GT5P_LEAK': '1',
    'PAD_LEAK': '1',
    'PPU_LEAK': '1',
    'SPU_LEAK': '1',
    'D3D12_LEAK': '1',
    'CULL_LEAK': '1',
    'PS3_HEADLESS': '1',
}

def answer(env):
    work = Path(env['RSX_SHADER_LIBRARY_BATCH'])
    cache = Path(env['RSX_SHADER_CACHE'])
    lines = (work / 'jobs.txt').read_text(encoding='ascii').splitlines()
    count = int(lines[0].split()[1])
    rows = []
    for line in lines[1:]:
        identity, digest_text, raw_hash = line.split()[:3]
        key = hashlib.sha256(line.encode()).hexdigest()[:16]
        (cache / (key + '.dxbc')).write_bytes(b'DXBC synthetic ' + identity.encode())
        rows.append(f'{identity} {raw_hash} {key} 1')
    (work / 'compiled.tsv').write_text(f'GT5P_FP_BATCH_RESULTS_V1 {count}\n' + '\n'.join(rows) + '\n', encoding='ascii')
    return f'[fp-batch] finished: requests={count} rejected=0 compiled={count} elapsed_ms=1'

with tempfile.TemporaryDirectory() as folder:
    root = Path(folder)
    cache = root / 'cache-1080'
    cache.mkdir()
    calls = []
    def run(translation='default', work_prefix=None, items=None):
        def fake(engine, game, env, log, timeout):
            calls.append(dict(env))
            return answer(env)
        with patch.dict(os.environ, dirty, clear=False), patch(
                'shader_fragment_batch.run_offline', side_effect=fake):
            return shader_fragment_batch.compile_batch(
                [fragment_job] if items is None else items, root, cache, root / 'engine', root,
                translation=translation, work_prefix=work_prefix)
    compiled, failures = run()
    assert not failures and 'first' in compiled
    env = calls[-1]
    assert env['RSX_ULTRAWIDE'] == '0' and 'RSX_RENDER_HEIGHT' not in env
    assert env['RSX_SHADER_CACHE'] == str(cache) and env['GT5P_NO_SETTINGS'] == '1'
    assert env['RSX_FINAL_DITHER'] in ('0', '1') and 'RSX_SHADER_LIBRARY_BATCH' in env
    assert 'FP_LEAK' not in env and 'PS3_HEADLESS' not in env and 'GT5P_LEAK' not in env
    batch_dir = Path(env['RSX_SHADER_LIBRARY_BATCH'])
    assert batch_dir.parent == root and batch_dir.name.startswith('fragment-batch-')
    report = json.loads((root / 'fragment-preparation-report.json').read_text(encoding='utf-8'))
    assert report['translation'] == 'default' and report['prepared_jobs'] == 1
    calls.clear()
    compiled, failures = run('ultrawide-native', 'uw-native')
    assert not failures and calls[-1]['RSX_ULTRAWIDE'] == '2' and 'RSX_RENDER_HEIGHT' not in calls[-1]
    assert Path(calls[-1]['RSX_SHADER_LIBRARY_BATCH']).parent == root / 'uw-native'
    uw_report = json.loads((root / 'uw-native' / 'fragment-preparation-report.json').read_text(encoding='utf-8'))
    assert uw_report['translation'] == 'ultrawide-native'
    assert json.loads((root / 'fragment-preparation-report.json').read_text(encoding='utf-8'))['translation'] == 'default'
    calls.clear()
    compiled, failures = run('native-scaled', 'native-scaled')
    assert not failures
    assert calls[-1]['RSX_ULTRAWIDE'] == '0' and calls[-1]['RSX_RENDER_HEIGHT'] == '1440'
    assert '1080' in calls[-1]['RSX_SHADER_CACHE']
    assert Path(calls[-1]['RSX_SHADER_LIBRARY_BATCH']).parent == root / 'native-scaled'
    scaled_report = json.loads((root / 'native-scaled' / 'fragment-preparation-report.json').read_text(encoding='utf-8'))
    assert scaled_report['translation'] == 'native-scaled'
    def rejected(translation='default', work_prefix=None):
        started = []
        def boom(*args, **kwargs):
            started.append(True)
            raise AssertionError('compiler started')
        with patch('shader_fragment_batch.run_offline', side_effect=boom):
            try:
                shader_fragment_batch.compile_batch(
                    [fragment_job], root, cache, root / 'engine', root,
                    translation=translation, work_prefix=work_prefix)
            except ValueError:
                pass
            else:
                raise AssertionError('invalid fragment translation workspace accepted')
        assert started == []
    rejected(translation='1440p')
    rejected(translation='ultrawide')
    for prefix in ('', '.', '..', '../out', 'a/b', 'a\\b', '.hidden', 'foo.', 'has space', 'x' * 65):
        rejected(work_prefix=prefix)

# Derive acceptance uses the recomputed ids. A fresh one-worker pool is the only path.
job = dict(sha256=digest, gpu=1, program=program)
assert batch.accept_derived(job, (digest, 1, source_id, code_id), hlsl, dxbc) == (source_id, code_id, dxbc)
assert_raises(lambda: batch.accept_derived(
    job, (digest, 1, 'ffffffffffffffff', 'eeeeeeeeeeeeeeee'), hlsl, dxbc), batch.ProtocolError)
assert_raises(lambda: batch.accept_derived(
    job, ('ab' * 32, 1, source_id, code_id), hlsl, dxbc), batch.ProtocolError)
assert_raises(lambda: batch.accept_derived(job, (digest, 1, source_id, code_id), hlsl, b'NOTDXBC'))

class Pool:
    def __init__(self, workers):
        self.workers = workers
        self.retired = 0
    def retire(self, workers):
        self.retired += 1
        for worker in workers:
            worker.retire()

class Peer:
    """In-memory derive peer. It never loads a decoder."""
    def __init__(self, reply):
        self.reply = reply
        self.inbox = bytearray()
        self.outbox = bytearray(batch.READY)
        self._alive = True
        self.retired = False
    def write(self, payload):
        self.inbox.extend(payload)
        if self.inbox.startswith(batch.END):
            self.outbox.extend(batch.DONE)
            self.inbox = self.inbox[len(batch.END):]
            self._alive = False
            return
        if not self.inbox.startswith(batch.DERIVE):
            if len(self.inbox) >= len(batch.DERIVE):
                self._alive = False
            return
        rest = self.inbox[len(batch.DERIVE):]
        newline = rest.find(b'\n')
        if newline < 0:
            return
        parsed = batch._parse_derive_header(rest[:newline].decode('ascii'))
        if parsed is None:
            self._alive = False
            return
        sha, gpu, length = parsed
        body = rest[newline + 1:]
        if len(body) < length:
            return
        program_bytes = bytes(body[:length])
        self.inbox = body[length:]
        self.outbox.extend(self.reply(sha, gpu, program_bytes))
    def read_available(self):
        data = bytes(self.outbox)
        self.outbox.clear()
        return data
    def alive(self):
        return self._alive and not self.retired
    def retire(self):
        self.retired = True
        self._alive = False

def honest(sha, gpu, payload):
    assert hashlib.sha256(payload).hexdigest() == sha
    source_hex, code_hex = batch._translated_ids(hlsl, dxbc)
    return batch.encode_result((sha, gpu, source_hex, code_hex), hlsl, dxbc)

def lying(sha, gpu, payload):
    return batch.encode_result((sha, gpu, 'ffffffffffffffff', 'eeeeeeeeeeeeeeee'), hlsl, dxbc)

monotonic, sleep = clock()
launched = []
def open_one(count, decoder, work):
    launched.append((count, decoder))
    worker = Peer(honest)
    return Pool([worker]), [worker]

with tempfile.TemporaryDirectory() as folder, patch(
        'shader_reconstruct.NativeCompiler', side_effect=AssertionError('in-process latch')):
    compiled, failures, report = batch.compile_jobs(
        [job, dict(job)], 'decoder.dll', Path(folder), derive=True, workers=1, translation='native-scaled',
        opener=open_one, monotonic=monotonic, sleep=sleep)
    assert not list(Path(folder).rglob('*.dxbc'))
assert launched == [(1, 'decoder.dll')]
assert not failures and compiled[(digest, 1)] == (source_id, code_id, dxbc)
assert report['translation'] == 'native-scaled' and report['derive'] is True
assert report['workers'] == 1 and report['duplicate_variants'] == 1 and report['compiled_variants'] == 1

launched.clear()
def open_lie(count, decoder, work):
    launched.append(count)
    worker = Peer(lying)
    return Pool([worker]), [worker]

with tempfile.TemporaryDirectory() as folder:
    compiled, failures, report = batch.compile_jobs(
        [job], 'decoder.dll', Path(folder), derive=True, workers=1, opener=open_lie,
        monotonic=monotonic, sleep=sleep)
assert launched == [1] and compiled == {} and report['failed_variants'] == 1
assert 'returned bytes' in next(iter(failures.values()))

print('Shader translation environments, fragment overlay and derive acceptance passed')
