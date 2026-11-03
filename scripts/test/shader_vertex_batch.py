"""Vertex batch protocol, dedup, ownership flags and parent acceptance. No processes."""
import ctypes
from contextlib import redirect_stdout
import hashlib
import inspect
from io import BytesIO, StringIO
from pathlib import Path
import struct
import sys
import os
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import pipeline_template
import shader_vertex_batch as batch
os.environ['GT5P_PREPARE_COMPILER_WORKERS'] = '2'  # Existing protocol fixtures deliberately use two workers.
from prepare_material_shaders import source_key
from shader_coverage import fnv64

program = bytes(range(16))
other = bytes(range(16, 32))
reused_program = b'\xab' * 16
fragment = struct.pack('>4I', 0x00010000, 0, 0, 0)
hlsl = b'float4 main(){return 0;}\n'
dxbc = b'DXBCbatch-vertex'
source_id = f'{source_key(hlsl):016x}'
code_id = f'{fnv64(dxbc):016x}'
digest = hashlib.sha256(program).hexdigest()
other_digest = hashlib.sha256(other).hexdigest()
reused_digest = hashlib.sha256(reused_program).hexdigest()
fragment_digest = hashlib.sha256(fragment).hexdigest()


def assert_raises(func, kind=Exception):
    try:
        func()
    except kind:
        return
    raise AssertionError('Expected failure was accepted')


def record(name, code, gpu, source, bytecode, payload=program):
    return dict(key=f'{name:016x}', vp=dict(sha256=hashlib.sha256(payload).hexdigest(), size=len(payload)),
                fp=dict(sha256=fragment_digest, size=len(fragment)), vp_source=source, vs=bytecode,
                vp_gpu=gpu, state=dict(blend=0))


class Pool:
    def __init__(self, workers):
        self.workers = workers
        self.retired = 0
        self.ownership = 'scripted'
    def retire(self, workers):
        self.retired += 1
        for worker in workers:
            worker.retire()


class ScriptWorker:
    """In-memory peer. It never creates a process."""
    def __init__(self, handler):
        self.handler = handler
        self.inbox = bytearray()
        self.outbox = bytearray(batch.READY)
        self.retired = False
        self._alive = True
        self.requests = 0
        self.kinds = []
    def write(self, payload):
        if self.retired:
            raise OSError('retired')
        self.inbox.extend(payload)
        self._drain()
    def _kind(self):
        if self.inbox.startswith(batch.END):
            return 'end'
        if self.inbox.startswith(batch.DERIVE):
            return 'derive'
        if self.inbox.startswith(batch.REQUEST):
            return 'exact'
        if any(magic.startswith(self.inbox) for magic in (batch.END, batch.DERIVE, batch.REQUEST)):
            return 'partial'
        return 'unknown'
    def _drain(self):
        while True:
            kind = self._kind()
            if kind == 'partial':
                return
            if kind == 'end':
                self.outbox.extend(batch.DONE)
                self.inbox = self.inbox[len(batch.END):]
                self._alive = False
                return
            if kind not in ('exact', 'derive'):
                if len(self.inbox) >= len(batch.REQUEST):
                    self.outbox.extend(b'NOT-A-FRAME\n')
                    self.inbox.clear()
                return
            magic = batch.DERIVE if kind == 'derive' else batch.REQUEST
            rest = self.inbox[len(magic):]
            newline = rest.find(b'\n')
            if newline < 0:
                return
            header = rest[:newline].decode('ascii')
            if kind == 'derive':
                parsed = batch._parse_derive_header(header)
                if parsed is None:
                    self._alive = False
                    return
                sha, gpu, length = parsed
                echoed = (sha, gpu)
            else:
                try:
                    echoed, tail = batch._parse_echo(header)
                except batch.ProtocolError:
                    self._alive = False
                    return
                if not tail.isdigit():
                    self._alive = False
                    return
                length = int(tail)
            body = rest[newline + 1:]
            if len(body) < length:
                return
            program_bytes = bytes(body[:length])
            self.inbox = body[length:]
            self.requests += 1
            self.kinds.append(kind)
            reply = self.handler(echoed, program_bytes, self)
            if reply is None:
                self._alive = False
                return
            self.outbox.extend(reply)
    def read_available(self):
        data = bytes(self.outbox)
        self.outbox.clear()
        return data
    def alive(self):
        return self._alive and not self.retired
    def retire(self):
        self.retired = True
        self._alive = False


def opener_for(handler, launches):
    def open_workers(count, decoder, work):
        assert 1 <= count <= 4
        launches.append(count)
        workers = [ScriptWorker(handler) for _ in range(count)]
        return Pool(workers), workers
    return open_workers


def good_handler(echoed, payload, worker):
    assert hashlib.sha256(payload).hexdigest() == echoed[0]
    assert worker.requests == 1 or worker.alive()
    return batch.encode_result(echoed, hlsl, dxbc)


def clock():
    state = {'now': 0}
    def monotonic():
        return state['now']
    def sleep(seconds):
        state['now'] += seconds
    return monotonic, sleep


# Mode, command and ownership flags. No compiler and no process.
assert batch.poll_seconds({}) == .01
assert batch.poll_seconds({'GT5P_PREPARE_VERTEX_POLL_MS': '10'}) == .01
assert batch.poll_seconds({'GT5P_PREPARE_VERTEX_POLL_MS': '100'}) == .1
for invalid_interval in ('', '0', '1', '20', '1000', '010', '10 ', 'auto'):
    assert_raises(lambda: batch.poll_seconds({'GT5P_PREPARE_VERTEX_POLL_MS': invalid_interval}), ValueError)
assert batch.player_mode({}) == 'batch'
assert batch.player_mode({'GT5P_PREPARE_VERTEX_BATCH': '0'}) == 'serial'
assert batch.player_mode({'GT5P_PREPARE_VERTEX_BATCH': '1'}) == 'batch'
assert_raises(lambda: batch.player_mode({'GT5P_PREPARE_VERTEX_BATCH': ''}))
assert_raises(lambda: batch.player_mode({'GT5P_PREPARE_VERTEX_BATCH': 'true'}))
assert batch.worker_requested(['helper', batch.SENTINEL, 'decoder.dll'])
assert not batch.worker_requested(['helper', '--install', 'x'])
assert batch.worker_main(['helper']) == 2
assert batch.worker_main(['helper', batch.SENTINEL]) == 2
assert batch.worker_main(['helper', batch.SENTINEL, 'decoder.dll', 'extra']) == 2
source = batch.worker_command('C:/decoder/decoder.dll', frozen=False, executable='C:/Python/python.exe')
assert source[0] == 'C:/Python/python.exe' and source[2] == batch.SENTINEL
assert Path(source[1]).name == 'shader_vertex_batch.py'
assert Path(source[3]) == Path('C:/decoder/decoder.dll').resolve()
assert 'gt5p.exe' not in ' '.join(source).lower() and 'shadercache' not in ' '.join(source).lower()
frozen = batch.worker_command(r'C:\decoder\decoder.dll', frozen=True, executable=r'C:\app\GT5P-Prepare.exe')
assert frozen[:2] == [r'C:\app\GT5P-Prepare.exe', batch.SENTINEL]
assert Path(frozen[2]) == Path(r'C:\decoder\decoder.dll').resolve() and Path(frozen[2]).is_absolute()
relative = batch.worker_command('decoder.dll', frozen=True, executable='GT5P-Prepare.exe')
assert Path(relative[2]).is_absolute() and Path(relative[2]).name == 'decoder.dll'
assert batch.PROCESS_FLAGS & batch.CREATE_NO_WINDOW
assert batch.PROCESS_FLAGS & batch.CREATE_SUSPENDED
assert not batch.PROCESS_FLAGS & batch.CREATE_BREAKAWAY_FROM_JOB
assert not batch.PROCESS_FLAGS & batch.EXTENDED_STARTUPINFO_PRESENT
assert not batch.PROCESS_FLAGS & batch.CREATE_UNICODE_ENVIRONMENT
assert batch.DERIVE != batch.REQUEST and batch.DERIVE.endswith(b'\n')
flags = batch._process_flags(True, True)
assert flags & batch.CREATE_UNICODE_ENVIRONMENT
assert flags & batch.EXTENDED_STARTUPINFO_PRESENT
assert flags & batch.CREATE_NO_WINDOW and flags & batch.CREATE_SUSPENDED
assert not flags & batch.CREATE_BREAKAWAY_FROM_JOB
assert_raises(lambda: batch._process_flags(True, False))
assert_raises(lambda: batch._process_flags(False, False))
if ctypes.sizeof(ctypes.c_void_p) == 8:
    extended_type, process_type, _security_type = batch._startup(ctypes)
    startup_type = extended_type._fields_[0][1]
    assert ctypes.sizeof(startup_type) == 104 and ctypes.sizeof(extended_type) == 112
    assert ctypes.sizeof(process_type) == 24
    assert ctypes.sizeof(batch._extended_limits(ctypes)) == 144
prepare_signature = inspect.signature(pipeline_template.prepare)
assert prepare_signature.parameters['vertex_mode'].default == 'batch'
assert prepare_signature.parameters['fragment_mode'].default == 'batch'
assert inspect.signature(pipeline_template.prepare_document).parameters['vertex_mode'].default == 'batch'
# Exercise CLI dispatch without starting compilers or accessing game inputs.
cli = ['pipeline_template.py', 'prepare']
for option in ('template', 'elf', 'engine', 'decoder', 'game-root', 'output'):
    cli += ['--' + option, 'unused']
for arguments, expected in (([], 'batch'), (['--vertex-mode', 'serial'], 'serial')):
    with patch.object(sys, 'argv', cli + arguments), patch.object(pipeline_template, 'prepare',
            return_value=dict(counts={}, lookup={}, preparation_seconds=0)) as dispatched, redirect_stdout(StringIO()):
        pipeline_template.main()
    assert dispatched.call_args.kwargs['vertex_mode'] == expected
# Classification: dedup, gpu split, reuse bypass, conflict and unresolved inputs.
reused_code = b'DXBCreused-vertex'
reused_source = '00000000000000ab'
reused_id = f'{fnv64(reused_code):016x}'
first = record(1, program, 1, source_id, code_id)
duplicate = record(2, program, 1, source_id, code_id)
gpu_off = record(3, other, 0, source_id, code_id, other)
reused = record(4, reused_program, 1, reused_source, reused_id, reused_program)
conflict = record(5, program, 1, source_id, '00000000000000ff')
missing = record(6, program, 0, source_id, code_id)
missing['vp'] = dict(sha256='00' * 32, size=16)
vertices = {digest: program, other_digest: other, reused_digest: reused_program}
fragments = {fragment_digest: fragment}
decisions, jobs, identities, reused_variants = batch.plan_vertices(
    [first, duplicate, gpu_off, reused, missing], vertices, fragments, {reused_source: reused_code})
assert reused_variants == 1 and len(jobs) == 2
assert {(job['sha256'], job['gpu']) for job in jobs} == {(digest, 1), (other_digest, 0)}
assert all(job['sha256'] != reused_digest for job in jobs)
assert decisions[0][0] == 'ready' and decisions[-1][0] == 'unresolved'
_conflicted, conflict_jobs, conflict_ids, _count = batch.plan_vertices(
    [first, conflict], vertices, fragments, {})
assert conflict_jobs == [] and conflict_ids[(digest, 1)]['poison'] == 'Conflicting vertex identity'
only_reused, reused_jobs, _info, reused_count = batch.plan_vertices(
    [reused, record(7, reused_program, 1, reused_source, reused_id, reused_program)], vertices, fragments,
    {reused_source: reused_code})
assert reused_jobs == [] and reused_count == 1 and all(item[0] == 'ready' for item in only_reused)

# Parent recomputes ids. Echo and declared hashes are not enough.
job = dict(sha256=digest, gpu=1, program=program, expected_source=source_id, expected_code=code_id)
assert batch.accept_result(job, (digest, 1, source_id, code_id), hlsl, dxbc)[2] == dxbc
assert_raises(lambda: batch.accept_result(job, (other_digest, 1, source_id, code_id), hlsl, dxbc))
assert_raises(lambda: batch.accept_result(job, (digest, 1, source_id, code_id), hlsl, b'DXBC-tampered'))
assert_raises(lambda: batch.accept_result(job, (digest, 1, source_id, code_id), hlsl, b'NOTDXBC'))
frame, rest = batch.try_take(bytearray(batch.encode_result((digest, 1, source_id, code_id), hlsl, dxbc)))
assert frame[0] == 'result' and rest == b''
assert_raises(lambda: batch.try_take(bytearray(
    batch.RESULT + f'{digest} 1 {source_id} {code_id} 999999999 4\n'.encode('ascii'))), batch.ProtocolError)
assert_raises(lambda: batch.try_take(bytearray(b'GT5P_VP_UNKNOWN_V1\n')), batch.ProtocolError)
assert_raises(lambda: batch.try_take(bytearray(batch.RESULT + b'1' * 513 + b'\n')), batch.ProtocolError)

# In-process worker protocol. One decoder, serial calls, no cache write.
class Compiler:
    def __init__(self):
        self.calls = []
    def vertex(self, data, gpu):
        self.calls.append((bytes(data), bool(gpu)))
        if data == other:
            raise ValueError('asset vertex translation failed')
        return hlsl, dxbc

compiler = Compiler()
stdin = BytesIO(batch.encode_request(dict(sha256=digest, gpu=1, program=program,
                                         expected_source=source_id, expected_code=code_id)) +
                batch.encode_request(dict(sha256=other_digest, gpu=0, program=other,
                                         expected_source=source_id, expected_code=code_id)) + batch.END)
stdout = BytesIO()
assert batch.serve(compiler, stdin, stdout) == 0
assert compiler.calls == [(program, True), (other, False)]
output = bytearray(stdout.getvalue())
passed, output = batch.try_take(output)
assert passed[0] == 'result'
assert batch.accept_result(
    dict(sha256=digest, gpu=1, program=program, expected_source=source_id, expected_code=code_id),
    passed[1], passed[2], passed[3])[0] == source_id
failed, output = batch.try_take(output)
assert failed[0] == 'fail' and failed[1] == (other_digest, 0, source_id, code_id)
done, output = batch.try_take(output)
assert done == ('done',) and output == b''

# Scheduler bounds, cancellation, dead worker and empty reuse. No real spawn.
monotonic, sleep = clock()
launches = []
compiled, failures, report = batch.compile_jobs([], 'decoder.dll', Path('unused'), opener=opener_for(good_handler, launches),
                                                monotonic=monotonic, sleep=sleep)
assert compiled == {} and failures == {} and report['launches'] == 0 and launches == [] and report['workers'] == 0

seen_kinds = []
def answer(echoed, payload, worker):
    seen_kinds.append(worker.kinds[-1])
    if echoed[0] == other_digest:
        return batch.encode_result(echoed, b'other-source', b'DXBC-other')
    return batch.encode_result(echoed, hlsl, dxbc)

requests = [
    dict(sha256=digest, gpu=1, program=program, expected_source=source_id, expected_code=code_id),
    dict(sha256=other_digest, gpu=0, program=other, expected_source=f'{source_key(b"other-source"):016x}',
         expected_code=f'{fnv64(b"DXBC-other"):016x}'),
    dict(sha256=digest, gpu=0, program=program, expected_source=source_id, expected_code=code_id),
]
launches = []
with tempfile.TemporaryDirectory() as folder:
    compiled, failures, report = batch.compile_jobs(requests, 'decoder.dll', Path(folder), opener=opener_for(answer, launches),
                                                    monotonic=monotonic, sleep=sleep)
    assert not list(Path(folder).rglob('*.dxbc'))
assert not failures and set(compiled) == {(digest, 1), (other_digest, 0), (digest, 0)}
assert compiled[(digest, 1)][2] == dxbc and compiled[(digest, 0)][2] == dxbc
assert report['launches'] == 2 and report['workers'] == 2 and launches == [2]
assert report['inflight_jobs_max'] <= 2 and report['compiled_variants'] == 3
assert report['limits']['workers'] == 4
assert report['limits']['worker_job_commit_bytes'] == 1024**3
assert seen_kinds == ['exact', 'exact', 'exact']
assert report['translation'] == 'default' and report['derive'] is False and report['duplicate_variants'] == 0

four_requests = requests + [dict(requests[1], gpu=1)]
for count in (3,4):
    launches = []
    with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {'GT5P_PREPARE_COMPILER_WORKERS':str(count)}):
        more, errors, stats = batch.compile_jobs(four_requests, 'decoder.dll', Path(folder),
            opener=opener_for(answer, launches), monotonic=monotonic, sleep=sleep)
    assert len(more) == 4 and not errors and launches == [count]
    assert stats['inflight_jobs_max'] <= count and stats['workers'] == count
    assert stats['limits']['worker_job_commit_bytes'] == 1024**3

# Delay complete replies independently of the scheduler. Both intervals must
# return identical verified results, with unchanged two-worker ownership/caps.
def delayed_replies(interval):
    now, wait = clock()
    owned = []
    class DelayedWorker(ScriptWorker):
        ready_at = 0
        def read_available(self):
            return super().read_available() if now() >= self.ready_at else b''
    def delayed(echoed, payload, worker):
        worker.ready_at = now() + .015
        return answer(echoed, payload, worker)
    def open_delayed(count, decoder, work):
        owned.extend(DelayedWorker(delayed) for _ in range(count))
        return Pool(owned), owned
    with tempfile.TemporaryDirectory() as folder, patch.dict(batch.os.environ, {'GT5P_PREPARE_VERTEX_POLL_MS': interval}):
        result = batch.compile_jobs(requests, 'decoder.dll', Path(folder), opener=open_delayed,
                                    monotonic=now, sleep=wait)
    assert all(w.retired for w in owned)
    return result, now()

(quick_codes, quick_errors, quick_report), quick_time = delayed_replies('10')
(old_codes, old_errors, old_report), old_time = delayed_replies('100')
assert quick_codes == old_codes and not quick_errors and not old_errors
assert quick_time < old_time
assert quick_report['limits'] == old_report['limits'] and quick_report['workers'] == old_report['workers'] == 2
assert quick_report['poll_seconds'] == .01 and old_report['poll_seconds'] == .1

def garbage(echoed, payload, worker):
    return b'GT5P_VP_UNKNOWN_V1\n'

def run_jobs(items, handler, **kwargs):
    launches = []
    with tempfile.TemporaryDirectory() as folder:
        compiled, failures, report = batch.compile_jobs(
            items, 'decoder.dll', Path(folder), opener=opener_for(handler, launches),
            monotonic=monotonic, sleep=sleep, **kwargs)
        assert not list(Path(folder).rglob('*.dxbc'))
    return launches, compiled, failures, report

launches, compiled, failures, report = run_jobs(requests[:1], garbage)
assert compiled == {} and launches == [1] and report['failed_variants'] == 1
assert 'Unknown vertex worker result' in next(iter(failures.values()))

def mismatch(echoed, payload, worker):
    wrong = (other_digest, echoed[1], echoed[2], echoed[3])
    return batch.encode_result(wrong, hlsl, dxbc)

_launches, compiled, failures, report = run_jobs(requests[:1], mismatch)
assert compiled == {} and 'requested program' in next(iter(failures.values()))

def trailing(echoed, payload, worker):
    return batch.encode_result(echoed, hlsl, dxbc) + b'extra'

_launches, compiled, failures, report = run_jobs(requests[:1], trailing)
assert compiled == {} and 'trailing' in next(iter(failures.values()))

def die_once(echoed, payload, worker):
    if echoed[1] == 1:
        return None
    return batch.encode_result(echoed, hlsl, dxbc)

launches, compiled, failures, report = run_jobs([requests[0], requests[2]], die_once)
assert launches == [2] and report['launches'] == 2
assert (digest, 1) in failures and (digest, 0) in compiled

def silent(echoed, payload, worker):
    return b''

_launches, compiled, failures, report = run_jobs(requests[:1], silent, job_seconds=0)
assert compiled == {} and 'time budget' in next(iter(failures.values()))

pools = []
def tracking(handler):
    def open_workers(count, decoder, work):
        workers = [ScriptWorker(handler) for _ in range(count)]
        pool = Pool(workers)
        pools.append(pool)
        return pool, workers
    return open_workers

def cancel():
    raise KeyboardInterrupt('cancelled')

with tempfile.TemporaryDirectory() as folder:
    assert_raises(lambda: batch.compile_jobs(requests[:1], 'decoder.dll', Path(folder), poll=cancel,
                                             opener=tracking(good_handler), monotonic=monotonic, sleep=sleep), KeyboardInterrupt)
assert pools and pools[-1].retired == 1 and all(worker.retired for worker in pools[-1].workers)

# Parent integration: reused work starts no worker; a compiled variant is saved only after acceptance.
class Checkpoint:
    def __init__(self):
        self.progress = None
    def stage(self, *args, **kwargs):
        pass

def run_prepare(records, reused_map, handler):
    launches = []
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        cache = root / 'shadercache'
        cache.mkdir()
        report = dict(records=[], resume=dict(vertex_programs_reused=0, vertex_programs_compiled=0))
        document = dict(records=records)
        jobs, by_id = pipeline_template._prepare_vertex_batch(
            document, vertices, fragments, reused_map, root / 'decoder.dll', cache, root, Checkpoint(), report,
            opener=opener_for(handler, launches))
        dxbc_files = list(root.joinpath('requests', 'vertex-batch').rglob('*.dxbc')) if root.joinpath('requests').exists() else []
        saved = {path.name: path.read_bytes() for path in cache.glob('*.dxbc')}
        return launches, report, jobs, by_id, saved, dxbc_files

launches, report, jobs, by_id, saved, stray = run_prepare(
    [reused, record(7, reused_program, 1, reused_source, reused_id, reused_program)],
    {reused_source: reused_code}, good_handler)
assert launches == [] and report['vertex_preparation']['workers'] == 0
assert report['vertex_preparation']['launches'] == 0 and report['resume']['vertex_programs_compiled'] == 0
assert report['resume']['vertex_programs_reused'] == 1 and saved[reused_source + '.dxbc'] == reused_code
assert stray == [] and len(jobs) == 2

launches, report, jobs, by_id, saved, stray = run_prepare([first, duplicate], {}, good_handler)
assert launches == [1] and report['vertex_preparation']['compiled_variants'] == 1
assert report['resume']['vertex_programs_compiled'] == 1 and report['resume']['vertex_programs_reused'] == 0
assert saved[source_id + '.dxbc'] == dxbc and stray == [] and len(jobs) == 2
assert by_id[jobs[0]['id']][1] == dxbc and jobs[0]['fragment'] == fragment

launches, report, jobs, _by_id, saved, stray = run_prepare([first, conflict], {}, good_handler)
assert launches == [] and saved == {} and report['records']
assert {item['status'] for item in report['records']} == {'incompatible'}

# Derive jobs carry sha/gpu/program only. The parent recomputes ids and does not keep a lying echo.
compile_signature = inspect.signature(batch.compile_jobs)
assert compile_signature.parameters['translation'].default == 'default'
assert compile_signature.parameters['derive'].default is False
assert compile_signature.parameters['workers'].default is None

def derived_ids(source, code):
    return f'{source_key(source, batch.VERTEX_TARGET):016x}', f'{fnv64(code):016x}'

def derive_reply(echoed, payload, worker):
    assert len(echoed) == 2 and worker.kinds[-1] == 'derive'
    source, code = (b'other-source', b'DXBC-other') if payload == other else (hlsl, dxbc)
    source_hex, code_hex = derived_ids(source, code)
    return batch.encode_result((echoed[0], echoed[1], source_hex, code_hex), source, code)

derive_one = dict(sha256=digest, gpu=1, program=program)
derive_two = dict(sha256=other_digest, gpu=0, program=other)
derive_frame = batch.encode_request(derive_one, derive=True)
assert derive_frame.startswith(batch.DERIVE)
assert source_id.encode() not in derive_frame.split(b'\n', 1)[0]
assert derive_frame[len(batch.DERIVE):].startswith(f'{digest} 1 {len(program)}\n'.encode('ascii'))
exact_frame = batch.encode_request(job)
assert exact_frame.startswith(batch.REQUEST) and source_id.encode() in exact_frame.split(b'\n', 2)[1]

derive_compiler = Compiler()
stdin = BytesIO(batch.encode_request(derive_one, derive=True) +
                batch.encode_request(derive_two, derive=True) + batch.END)
stdout = BytesIO()
assert batch.serve(derive_compiler, stdin, stdout) == 0
assert derive_compiler.calls == [(program, True), (other, False)]
output = bytearray(stdout.getvalue())
passed, output = batch.try_take(output, derived=True)
accepted = batch.accept_derived(derive_one, passed[1], passed[2], passed[3])
assert passed[0] == 'result' and accepted == (source_id, code_id, dxbc)
failed, output = batch.try_take(output, derived=True)
assert failed[0] == 'fail' and (failed[1][0], failed[1][1]) == (other_digest, 0) and failed[1][2] is None
assert 'translation failed' in failed[2]
done, output = batch.try_take(output, derived=True)
assert done == ('done',) and output == b''
assert_raises(lambda: batch.try_take(bytearray(
    batch.encode_derive_fail(digest, 1, 'stopped'))), batch.ProtocolError)
assert batch.serve(Compiler(), BytesIO(batch.DERIVE + b'not-a-header\n'), BytesIO()) == 1

assert_raises(lambda: batch.compile_jobs(
    [dict(derive_one, expected_source=source_id, expected_code=code_id)],
    'decoder.dll', Path('unused'), derive=True, workers=1))
assert_raises(lambda: batch.compile_jobs(
    [dict(sha256=digest, gpu=1, program=program)], 'decoder.dll', Path('unused')))
for bad_workers in (0, 5, True):
    assert_raises(lambda: batch.compile_jobs([derive_one], 'decoder.dll', Path('unused'), derive=True, workers=bad_workers))
assert_raises(lambda: batch.compile_jobs(
    [derive_one], 'decoder.dll', Path('unused'), translation='1440p', derive=True, workers=1))
assert_raises(lambda: batch.compile_jobs(
    [derive_one], 'decoder.dll', Path('unused'), translation='ultrawide', derive=True, workers=1))
assert_raises(lambda: batch.compile_jobs(
    [dict(sha256=digest, gpu=True, program=program)], 'decoder.dll', Path('unused'), derive=True, workers=1))

launches, compiled, failures, report = run_jobs(
    [derive_one, derive_two, dict(derive_one)], derive_reply, derive=True, workers=1)
assert launches == [1] and not failures and report['workers'] == 1 and report['duplicate_variants'] == 1
assert report['translation'] == 'default' and report['derive'] is True and report['compiled_variants'] == 2
assert report['inflight_jobs_max'] == 1
assert compiled[(digest, 1)] == (source_id, code_id, dxbc)
assert compiled[(other_digest, 0)][0] == derived_ids(b'other-source', b'DXBC-other')[0]

def lie(echoed, payload, worker):
    return batch.encode_result((echoed[0], echoed[1], 'ffffffffffffffff', 'eeeeeeeeeeeeeeee'), hlsl, dxbc)

_launches, compiled, failures, report = run_jobs([derive_one], lie, derive=True, workers=1)
assert compiled == {} and 'returned bytes' in next(iter(failures.values()))

def wrong_sha(echoed, payload, worker):
    source_hex, code_hex = derived_ids(hlsl, dxbc)
    return batch.encode_result((other_digest, echoed[1], source_hex, code_hex), hlsl, dxbc)

_launches, compiled, failures, report = run_jobs([derive_one], wrong_sha, derive=True, workers=1)
assert compiled == {} and 'requested program' in next(iter(failures.values()))

def not_dxbc(echoed, payload, worker):
    source_hex, code_hex = derived_ids(hlsl, b'NOTDXBC-bytes')
    return batch.encode_result((echoed[0], echoed[1], source_hex, code_hex), hlsl, b'NOTDXBC-bytes')

_launches, compiled, failures, report = run_jobs([derive_one], not_dxbc, derive=True, workers=1)
assert compiled == {} and 'bytecode' in next(iter(failures.values())).lower()

launches, compiled, failures, report = run_jobs([derive_one, derive_two], derive_reply, derive=True, workers=2)
assert launches == [2] and not failures and report['workers'] == 2 and report['launches'] == 2

forwarded = {}
def fake_open(count, decoder, work, translation='missing'):
    forwarded['count'] = count
    forwarded['translation'] = translation
    return opener_for(derive_reply, [])(count, decoder, work)

with patch.object(batch, 'open_workers', fake_open), patch(
        'shader_reconstruct.NativeCompiler', side_effect=AssertionError('in-process latch')):
    with tempfile.TemporaryDirectory() as folder:
        compiled, failures, report = batch.compile_jobs(
            [derive_one, derive_two], 'decoder.dll', Path(folder), derive=True, workers=1,
            translation='ultrawide-native', monotonic=monotonic, sleep=sleep)
        assert not list(Path(folder).rglob('*.dxbc'))
assert forwarded == {'count': 1, 'translation': 'ultrawide-native'}
assert not failures and report['launches'] == 1 and compiled[(digest, 1)][0] == source_id

print('Vertex batch dedup, protocol, derive acceptance, reuse bypass and worker bounds passed')
