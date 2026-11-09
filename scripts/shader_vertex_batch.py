"""Bounded vertex preparation. Workers are owned compiler processes.

Each worker loads one production decoder and runs jobs one at a time. The
decoder's C globals are not shared across workers or threads. Branch-base
setters stay unused, matching the serial translator. Exact jobs still require
the caller's expected source and bytecode ids. Derive jobs carry only the
program, its sha256 and the GPU flag; the parent recomputes source_key and
fnv64 itself. Workers never see the selected cache, the game, or gt5p.exe.

RSX_ULTRAWIDE latches inside a process, so every worker is started with one
explicit shader_translation environment. The default is ultrawide off and no
render height, even when the parent shell says otherwise.
"""
import hashlib
import os
from pathlib import Path
import re
import subprocess
import sys
import time

import shader_source_policy
import shader_translation
from preparation_workers import compiler_workers
from shader_coverage import MAX_FP, fnv64


SENTINEL = '--gt5p-vertex-worker'
READY = b'GT5P_VP_WORKER_READY_V1\n'
REQUEST = b'GT5P_VP_REQUEST_V1\n'
DERIVE = b'GT5P_VP_DERIVE_V1\n'
RESULT = b'GT5P_VP_RESULT_V1\n'
FAIL = b'GT5P_VP_FAIL_V1\n'
END = b'GT5P_VP_END_V1\n'
DONE = b'GT5P_VP_DONE_V1\n'
VERTEX_TARGET = b'vs_5_0'
MAX_PROGRAM = MAX_FP
MAX_SOURCE = 262144  # NativeCompiler decoder output buffer
MAX_BYTECODE = 4 * 1024 * 1024
MAX_TOTAL = 128 * 1024 * 1024
MAX_WORKERS = 12
MAX_JOBS = 4096
JOB_SECONDS = 180
START_SECONDS = 60
SHUTDOWN_SECONDS = 10
POLL_SECONDS = 0.01
CREATE_SUSPENDED = 0x00000004
CREATE_NEW_PROCESS_GROUP = 0x00000200
CREATE_UNICODE_ENVIRONMENT = 0x00000400
CREATE_NO_WINDOW = 0x08000000
CREATE_BREAKAWAY_FROM_JOB = 0x01000000
EXTENDED_STARTUPINFO_PRESENT = 0x00080000
PROCESS_FLAGS = CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP | CREATE_SUSPENDED
JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000
JOB_OBJECT_LIMIT_PROCESS_MEMORY = 0x00000100
JOB_OBJECT_LIMIT_JOB_MEMORY = 0x00000200
WORKER_MEMORY = 512 * 1024 * 1024
WORKER_JOB_SHARE = 256 * 1024 * 1024  # aggregate commit allowance per worker (1 GiB floor)
JOB_OBJECT_EXTENDED_LIMIT = 9
PROC_THREAD_ATTRIBUTE_JOB_LIST = 0x0002000D
HEX16 = re.compile(r'[0-9a-f]{16}')
SHA256 = re.compile(r'[0-9a-f]{64}')
LIMITS = dict(workers=MAX_WORKERS, program_bytes=MAX_PROGRAM, source_bytes=MAX_SOURCE,
              worker_commit_bytes=WORKER_MEMORY, worker_job_commit_bytes=2 * WORKER_MEMORY,
              bytecode_bytes=MAX_BYTECODE, total_bytecode_bytes=MAX_TOTAL, job_seconds=JOB_SECONDS,
              startup_seconds=START_SECONDS, inflight_jobs=MAX_WORKERS,
              inflight_bytes=MAX_WORKERS * (MAX_PROGRAM + MAX_SOURCE + MAX_BYTECODE))


class ProtocolError(ValueError):
    """The worker stream can no longer be attributed to one request."""


def poll_seconds(environ=None):
    """Bounded pipe polling; 100 restores historical scheduling latency."""
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_VERTEX_POLL_MS', '10')
    if value not in ('10', '100'):
        raise ValueError('GT5P_PREPARE_VERTEX_POLL_MS must be unset, 10, or 100')
    return POLL_SECONDS if value == '10' else 0.1


def player_mode(environ=None):
    """Default to bounded batches; 0 explicitly restores serial compilation."""
    if environ is None:
        environ = os.environ
    if 'GT5P_PREPARE_VERTEX_BATCH' not in environ:
        return 'batch'
    value = environ['GT5P_PREPARE_VERTEX_BATCH']
    if value == '0':
        return 'serial'
    if value == '1':
        return 'batch'
    raise ValueError('GT5P_PREPARE_VERTEX_BATCH must be unset, 0, or 1')


def worker_requested(argv):
    return len(argv) >= 2 and argv[1] == SENTINEL


def worker_command(decoder, frozen=None, executable=None):
    if frozen is None:
        frozen = bool(getattr(sys, 'frozen', False))
    executable = sys.executable if executable is None else executable
    # Absolute before the child cwd becomes the batch directory.
    decoder = str(Path(decoder).resolve())
    if frozen:
        return [executable, SENTINEL, decoder]
    return [executable, str(Path(__file__).resolve()), SENTINEL, decoder]


def _clean(exc):
    text = ''.join(ch if 32 <= ord(ch) < 127 else '?' for ch in str(exc))
    return text[:200] or 'vertex compilation failed'


def _echo(sha256, gpu, source, code):
    return sha256, int(gpu), source, code


def _translated_ids(source, code):
    """Parent and worker share this. The echoed hex is not the stored identity."""
    from prepare_material_shaders import source_key
    if (not isinstance(source, (bytes, bytearray)) or not source or len(source) > MAX_SOURCE or
            not isinstance(code, (bytes, bytearray)) or not code.startswith(b'DXBC') or len(code) > MAX_BYTECODE):
        raise ValueError('Vertex source or bytecode exceeds its bound')
    import shader_compiler
    source_id = f'{source_key(bytes(source), shader_compiler.targets()[0]):016x}'
    code_id = f'{fnv64(bytes(code)):016x}'
    if int(source_id, 16) == 0 or int(code_id, 16) == 0:
        raise ValueError('Vertex source or bytecode identifier is empty')
    return source_id, code_id


def encode_request(job, derive=False):
    program = job['program']
    if not isinstance(program, (bytes, bytearray)):
        raise ValueError('Vertex program is not bytes')
    program = bytes(program)
    if derive:
        # No expected source or bytecode id. The worker computes those and the parent recomputes them.
        header = f"{job['sha256']} {int(job['gpu'])} {len(program)}\n".encode('ascii')
        return DERIVE + header + program
    header = (f"{job['sha256']} {int(job['gpu'])} {job['expected_source']} "
              f"{job['expected_code']} {len(program)}\n").encode('ascii')
    return REQUEST + header + program


def _parse_echo(line):
    parts = line.split(' ', 4)
    if len(parts) < 4 or not SHA256.fullmatch(parts[0]) or parts[1] not in ('0', '1'):
        raise ProtocolError('Malformed vertex worker identity')
    if not HEX16.fullmatch(parts[2]) or not HEX16.fullmatch(parts[3]):
        raise ProtocolError('Malformed vertex worker identity')
    if int(parts[2], 16) == 0 or int(parts[3], 16) == 0:
        raise ProtocolError('Malformed vertex worker identity')
    rest = parts[4] if len(parts) == 5 else ''
    return _echo(parts[0], parts[1], parts[2], parts[3]), rest


def _parse_derive_header(line):
    parts = line.split(' ')
    if len(parts) != 3 or not SHA256.fullmatch(parts[0]) or parts[1] not in ('0', '1') or not parts[2].isdigit():
        return None
    return parts[0], int(parts[1]), int(parts[2])


def try_take(buf, derived=False):
    """Return one complete parent-side frame, or None when more bytes are required."""
    if len(buf) > LIMITS['inflight_bytes']:
        raise ProtocolError('Vertex result exceeds its bound')
    newline = buf.find(b'\n')
    if newline < 0:
        if len(buf) > 64:
            raise ProtocolError('Unknown vertex worker result')
        return None, buf
    magic = bytes(buf[:newline + 1])
    rest = buf[newline + 1:]
    if magic == DONE:
        return ('done',), rest
    if magic not in (RESULT, FAIL):
        raise ProtocolError('Unknown vertex worker result')
    header_end = rest.find(b'\n')
    if header_end > 512:
        raise ProtocolError('Vertex result header exceeds its bound')
    if header_end < 0:
        if len(rest) > 512:
            raise ProtocolError('Vertex result exceeds its bound')
        return None, buf
    if magic == FAIL and derived:
        # Derive failures have no expected ids to echo. Sha and gpu still have to name the job.
        header = rest[:header_end].decode('ascii', errors='replace')
        parts = header.split(' ', 2)
        if (len(parts) != 3 or not SHA256.fullmatch(parts[0]) or parts[1] not in ('0', '1') or
                not parts[2] or len(parts[2]) > 200):
            raise ProtocolError('Malformed vertex worker failure')
        return ('fail', (parts[0], int(parts[1]), None, None), parts[2]), rest[header_end + 1:]
    echoed, tail = _parse_echo(rest[:header_end].decode('ascii', errors='replace'))
    body = rest[header_end + 1:]
    if magic == FAIL:
        if not tail or len(tail) > 200:
            raise ProtocolError('Malformed vertex worker failure')
        return ('fail', echoed, tail), body
    lengths = tail.split(' ')
    if len(lengths) != 2 or not all(part.isdigit() for part in lengths):
        raise ProtocolError('Malformed vertex worker result')
    source_len, code_len = (int(part) for part in lengths)
    if (source_len <= 0 or source_len > MAX_SOURCE or code_len <= 0 or code_len > MAX_BYTECODE):
        raise ProtocolError('Vertex result exceeds its bound')
    if len(body) < source_len + code_len:
        return None, buf
    source = bytes(body[:source_len])
    code = bytes(body[source_len:source_len + code_len])
    return ('result', echoed, source, code), body[source_len + code_len:]


def accept_result(job, echoed, source, code):
    """Recompute the template ids. The worker's echo alone is not authority."""
    from prepare_material_shaders import source_key
    expected = _echo(job['sha256'], job['gpu'], job['expected_source'], job['expected_code'])
    if echoed != expected:
        raise ProtocolError('Vertex result does not match the requested program')
    program = job['program']
    if hashlib.sha256(program).hexdigest() != job['sha256']:
        raise ValueError('Vertex program changed before acceptance')
    if not source or len(source) > MAX_SOURCE or not code.startswith(b'DXBC') or len(code) > MAX_BYTECODE:
        raise ValueError('Vertex source or bytecode exceeds its bound')
    source_id = f'{source_key(source):016x}'
    code_id = f'{fnv64(code):016x}'
    if source_id != job['expected_source'] or code_id != job['expected_code']:
        raise ValueError(f'Rebuilt vertex identifier differs: source={source_id}, bytecode={code_id}')
    return source_id, code_id, code


def accept_derived(job, echoed, source, code):
    """Recompute the new identity. A matching echo is checked, not trusted as the source of it."""
    sha, gpu = echoed[0], int(echoed[1])
    if sha != job['sha256'] or gpu != int(job['gpu']):
        raise ProtocolError('Vertex result does not match the requested program')
    program = job['program']
    if hashlib.sha256(program).hexdigest() != job['sha256']:
        raise ValueError('Vertex program changed before acceptance')
    source_id, code_id = _translated_ids(source, code)
    echo_source = echoed[2] if len(echoed) > 2 else None
    echo_code = echoed[3] if len(echoed) > 3 else None
    if echo_source != source_id or echo_code != code_id:
        raise ProtocolError('Vertex derive identity does not match the returned bytes')
    return source_id, code_id, code


def _program_reason(record, program):
    if type(record.get('vp_gpu')) is not int or record['vp_gpu'] not in (0, 1):
        return 'Invalid vertex translation mode'
    declared = record['vp']
    if (hashlib.sha256(program).hexdigest() != declared['sha256'] or len(program) != declared['size'] or
            len(program) > MAX_PROGRAM or len(program) < 16 or len(program) % 16):
        return 'Located vertex program differs from template identity'
    if (not isinstance(record['vp_source'], str) or not isinstance(record['vs'], str) or
            not HEX16.fullmatch(record['vp_source']) or not HEX16.fullmatch(record['vs']) or
            int(record['vp_source'], 16) == 0 or int(record['vs'], 16) == 0):
        return 'Invalid vertex source identity'
    return None


def plan_vertices(records, vertices, fragments, reused):
    """Classify records without loading a decoder or starting a process."""
    decisions, identities = [], {}
    for record in records:
        try:
            program = vertices[record['vp']['sha256']]
            fragment = fragments[record['fp']['sha256']]
        except KeyError:
            decisions.append(('unresolved', record))
            continue
        reason = _program_reason(record, program)
        if reason:
            decisions.append(('incompatible', record, reason))
            continue
        identity = (record['vp']['sha256'], record['vp_gpu'])
        kind = 'reused' if record['vp_source'] in reused else 'compile'
        info = identities.get(identity)
        if info is None:
            info = dict(kind=kind, source=record['vp_source'], code_id=record['vs'], program=program,
                        code=reused.get(record['vp_source']) if kind == 'reused' else None,
                        poison=None, gpu=record['vp_gpu'], sha256=record['vp']['sha256'], records=0)
            if kind == 'reused' and (not info['code'] or not info['code'].startswith(b'DXBC')):
                info['poison'] = 'Reused vertex bytecode is unavailable'
            identities[identity] = info
        elif (info['kind'] != kind or info['source'] != record['vp_source'] or info['code_id'] != record['vs'] or
              info['program'] != program):
            info['poison'] = 'Conflicting vertex identity'
            decisions.append(('incompatible', record, info['poison']))
            continue
        info['records'] += 1
        decisions.append(('ready', record, identity, fragment))
    compile_jobs = []
    for info in identities.values():
        if info['poison'] or info['kind'] != 'compile':
            continue
        compile_jobs.append(dict(sha256=info['sha256'], gpu=info['gpu'], program=info['program'],
                                 expected_source=info['source'], expected_code=info['code_id']))
    reused_variants = sum(1 for info in identities.values() if info['kind'] == 'reused' and not info['poison'])
    return decisions, compile_jobs, identities, reused_variants


def _read_line(stream, limit):
    data = bytearray()
    while len(data) <= limit:
        chunk = stream.read(1)
        if not chunk:
            raise EOFError
        data += chunk
        if chunk == b'\n':
            return bytes(data)
    raise ValueError('Vertex worker line exceeds its bound')


def _read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        chunk = stream.read(size - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return bytes(data)


def _write_frame(stream, payload):
    stream.write(payload)
    stream.flush()


def encode_result(echoed, source, code):
    sha256, gpu, source_id, code_id = echoed
    header = f'{sha256} {int(gpu)} {source_id} {code_id} {len(source)} {len(code)}\n'.encode('ascii')
    return RESULT + header + source + code


def encode_fail(echoed, message):
    sha256, gpu, source_id, code_id = echoed
    text = _clean(message).encode('ascii')
    return FAIL + f'{sha256} {int(gpu)} {source_id} {code_id} '.encode('ascii') + text + b'\n'


def encode_derive_fail(sha, gpu, message):
    text = _clean(message).encode('ascii')
    return FAIL + f'{sha} {int(gpu)} '.encode('ascii') + text + b'\n'


def serve(compiler, stdin, stdout):
    """Serial jobs on one decoder. No cache, filesystem shader output, or child process."""
    while True:
        try:
            magic = _read_line(stdin, 64)
        except EOFError:
            return 1
        if magic == END:
            _write_frame(stdout, DONE)
            return 0
        if magic not in (REQUEST, DERIVE):
            return 1
        derived = magic == DERIVE
        echoed = None
        try:
            header = _read_line(stdin, 256).decode('ascii')
            if derived:
                parsed = _parse_derive_header(header.rstrip('\n'))
                if parsed is None:
                    return 1
                sha, gpu, length = parsed
                echoed = (sha, gpu)
            else:
                echoed, tail = _parse_echo(header.rstrip('\n'))
                if not tail.isdigit():
                    return 1
                length = int(tail)
            # Reject before consuming an unaligned body. The parent then sees the worker stop.
            if length <= 0 or length > MAX_PROGRAM or length % 16:
                return 1
            program = _read_exact(stdin, length)
            sha, gpu = echoed[0], int(echoed[1])
            if hashlib.sha256(program).hexdigest() != sha or gpu not in (0, 1):
                raise ValueError('Vertex payload differs from the requested program')
            source, code = compiler.vertex(program, bool(gpu))
            if derived:
                source_id, code_id = _translated_ids(source, code)
                echoed = (sha, gpu, source_id, code_id)
            elif (not source or len(source) > MAX_SOURCE or not code.startswith(b'DXBC') or len(code) > MAX_BYTECODE):
                raise ValueError('Vertex source or bytecode exceeds its bound')
        except (ValueError, OSError, ProtocolError) as exc:
            # A header that never parsed leaves the stream unaligned. Stop.
            if echoed is None:
                return 1
            if derived:
                _write_frame(stdout, encode_derive_fail(echoed[0], echoed[1], exc))
            else:
                _write_frame(stdout, encode_fail(echoed, exc))
            continue
        _write_frame(stdout, encode_result(echoed, source, code))


def worker_main(argv):
    if len(argv) != 3 or argv[1] != SENTINEL:
        return 2
    try:
        from shader_reconstruct import NativeCompiler
        compiler = NativeCompiler(Path(argv[2]))
        sys.stdout.buffer.write(READY)
        sys.stdout.buffer.flush()
        try:
            return serve(compiler, sys.stdin.buffer, sys.stdout.buffer)
        finally:
            if compiler.profile:
                import json
                sys.stderr.write('[vertex-profile] ' + json.dumps(compiler.timings) + '\n')
    except BrokenPipeError:
        return 1
    except Exception as exc:
        sys.stderr.write(_clean(exc) + '\n')
        return 1


def _check_job(job):
    program = job['program']
    if (not SHA256.fullmatch(job['sha256']) or int(job['gpu']) not in (0, 1) or
            not HEX16.fullmatch(job['expected_source']) or not HEX16.fullmatch(job['expected_code']) or
            hashlib.sha256(program).hexdigest() != job['sha256'] or not 16 <= len(program) <= MAX_PROGRAM or
            len(program) % 16):
        raise ValueError('Invalid bounded vertex request')


def _check_derive_job(job):
    if 'expected_source' in job or 'expected_code' in job:
        raise ValueError('Derive request cannot carry an expected shader identity')
    program = job.get('program')
    gpu = job.get('gpu')
    if (not isinstance(job.get('sha256'), str) or not SHA256.fullmatch(job['sha256']) or type(gpu) is not int or
            gpu not in (0, 1) or not isinstance(program, (bytes, bytearray)) or
            hashlib.sha256(program).hexdigest() != job['sha256'] or not 16 <= len(program) <= MAX_PROGRAM or
            len(program) % 16):
        raise ValueError('Invalid bounded vertex request')


def _select_jobs(jobs, derive):
    """Exact requests stay in order. Derive requests collapse identical program/GPU pairs."""
    if len(jobs) > MAX_JOBS:
        raise ValueError('Vertex batch request limit exceeded')
    if not derive:
        for job in jobs:
            _check_job(job)
        return list(jobs), 0
    unique = []
    seen = {}
    duplicates = 0
    for job in jobs:
        _check_derive_job(job)
        identity = (job['sha256'], job['gpu'])
        previous = seen.get(identity)
        if previous is None:
            seen[identity] = bytes(job['program'])
            unique.append(job)
            continue
        if previous != bytes(job['program']):
            raise ValueError('Conflicting vertex identity')
        duplicates += 1
    return unique, duplicates


def _drain(worker, buf, derived=False):
    while True:
        chunk = worker.read_available()
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > LIMITS['inflight_bytes']:
            raise ProtocolError('Vertex result exceeds its bound')
    frame, remaining = try_take(buf, derived=derived)
    if frame is None:
        return None
    buf[:] = remaining
    return frame


def compile_jobs(jobs, decoder, work, poll=None, on_ready=None, opener=None, monotonic=None, sleep=None,
                 job_seconds=JOB_SECONDS, startup_seconds=START_SECONDS, translation='default',
                 derive=False, workers=None):
    """Compile one translation mode. An empty job list starts no worker.

    derive=False keeps the exact expected-id contract. derive=True never calls
    the decoder in this process: even one job uses a fresh worker, because the
    ultrawide latch is process-wide. Explicit worker counts are bounded to 1..4.
    """
    if derive is not True and derive is not False:
        raise ValueError('Vertex derive mode is not explicit')
    if workers is not None and (type(workers) is not int or not 1 <= workers <= MAX_WORKERS):
        raise ValueError('Vertex compiler worker cap exceeded')
    shader_translation.overlay(translation)
    worker_limit = compiler_workers() if workers is None else workers
    interval = poll_seconds()
    monotonic = monotonic or time.monotonic
    sleep = sleep or time.sleep
    started = time.perf_counter()
    from preparation_profile import enabled
    profiling = enabled()
    profile = dict(startup_us=0, dispatch_us=0, accept_us=0, checkpoint_us=0,
                   idle_poll_us=0, shutdown_us=0)
    def tick():
        return time.perf_counter_ns() if profiling else 0
    selected, duplicates = _select_jobs(jobs, derive)
    report = dict(mode='batch', translation=translation, derive=derive, requested_variants=len(jobs),
                  duplicate_variants=duplicates, compiled_variants=0, failed_variants=0,
                  workers=0, launches=0, seconds=0, poll_seconds=interval, limits=dict(LIMITS), inflight_jobs_max=0,
                  inflight_bytes_max=0, ownership=None)
    compiled, failures = {}, {}
    pool = None
    workers = []
    try:
        if not selected:
            return compiled, failures, report
        if work.exists() and (work.is_symlink() or getattr(work.lstat(), 'st_file_attributes', 0) & 0x400):
            raise ValueError('Vertex batch workspace must not be redirected')
        work.mkdir(parents=True, exist_ok=True)
        def launch(count, decoder_path, workspace):
            return open_workers(count, decoder_path, workspace, translation=translation)
        stamp = tick()
        pool, workers = (opener or launch)(min(worker_limit, len(selected)), decoder, work)
        report.update(workers=len(workers), launches=len(workers), ownership=getattr(pool, 'ownership', None))
        if len(workers) > worker_limit:
            raise ValueError('Vertex compiler worker cap exceeded')
        for worker in workers:
            deadline = monotonic() + startup_seconds
            buf = bytearray()
            while True:
                if poll:
                    poll()
                if monotonic() > deadline:
                    raise TimeoutError('Vertex worker startup exceeded its time budget')
                buf.extend(worker.read_available())
                if buf.startswith(READY):
                    if len(buf) != len(READY):
                        raise ProtocolError('Unexpected vertex worker preamble')
                    break
                if not READY.startswith(buf) or not worker.alive():
                    raise ProtocolError('Unknown vertex worker preamble')
                sleep(interval)
        if profiling:profile['startup_us'] = (tick() - stamp) // 1000
        pending = list(selected)
        inflight = {}
        buffers = {}
        usable = set(id(worker) for worker in workers)

        def fail_inflight(worker, message, protocol=False):
            job, _deadline, _size = inflight.pop(id(worker))
            failures[(job['sha256'], int(job['gpu']))] = message
            report['failed_variants'] += 1
            usable.discard(id(worker))
            worker.retire()
            if protocol:
                buffers.pop(id(worker), None)

        while pending or inflight:
            if poll:
                poll()
            progressed = False
            for worker in workers:
                if id(worker) in usable and id(worker) not in inflight and pending and worker.alive():
                    job = pending.pop(0)
                    stamp = tick()
                    payload = encode_request(job, derive=derive)
                    try:
                        worker.write(payload)
                    except OSError as exc:
                        failures[(job['sha256'], int(job['gpu']))] = _clean(exc)
                        report['failed_variants'] += 1
                        usable.discard(id(worker))
                        worker.retire()
                        progressed = True
                        continue
                    inflight[id(worker)] = (job, monotonic() + job_seconds, len(payload))
                    buffers[id(worker)] = bytearray()
                    report['inflight_jobs_max'] = max(report['inflight_jobs_max'], len(inflight))
                    report['inflight_bytes_max'] = max(report['inflight_bytes_max'],
                                                       sum(item[2] for item in inflight.values()))
                    progressed = True
                    if profiling:profile['dispatch_us'] += (tick() - stamp) // 1000
            for worker in list(workers):
                if id(worker) not in inflight:
                    continue
                job, deadline, _size = inflight[id(worker)]
                identity = (job['sha256'], int(job['gpu']))
                # A slow/incomplete stream must not extend the absolute job deadline.
                if monotonic() > deadline:
                    fail_inflight(worker, 'Vertex job exceeded its time budget')
                    progressed = True
                    continue
                try:
                    frame = _drain(worker, buffers[id(worker)], derived=derive)
                except ProtocolError as exc:
                    fail_inflight(worker, str(exc), protocol=True)
                    progressed = True
                    continue
                if frame is None:
                    if not worker.alive():
                        fail_inflight(worker, 'Vertex worker exited before a valid result')
                        progressed = True
                    continue
                inflight.pop(id(worker))
                payload_bytes = len(job['program'])
                if frame[0] == 'result':
                    payload_bytes += len(frame[2]) + len(frame[3])
                report['inflight_bytes_max'] = max(report['inflight_bytes_max'], payload_bytes +
                    sum(item[2] for item in inflight.values()) + sum(len(buf) for buf in buffers.values()))
                try:
                    if buffers[id(worker)]:
                        raise ProtocolError('Unexpected trailing vertex worker output')
                    if frame[0] == 'fail':
                        if derive:
                            if (frame[1][0], frame[1][1]) != (job['sha256'], int(job['gpu'])):
                                raise ProtocolError('Vertex result does not match the requested program')
                        elif frame[1] != _echo(job['sha256'], job['gpu'], job['expected_source'], job['expected_code']):
                            raise ProtocolError('Vertex result does not match the requested program')
                        raise ValueError(frame[2])
                    if frame[0] != 'result':
                        raise ProtocolError('Unknown vertex worker result')
                    if derive:
                        stamp = tick()
                        source_id, code_id, code = accept_derived(job, frame[1], frame[2], frame[3])
                    else:
                        stamp = tick()
                        source_id, code_id, code = accept_result(job, frame[1], frame[2], frame[3])
                    if profiling:profile['accept_us'] += (tick() - stamp) // 1000
                    if on_ready:
                        stamp = tick()
                        on_ready(job, source_id, code_id, code)
                        if profiling:profile['checkpoint_us'] += (tick() - stamp) // 1000
                    compiled[identity] = (source_id, code_id, code)
                    report['compiled_variants'] += 1
                except ProtocolError as exc:
                    failures[identity] = str(exc)
                    report['failed_variants'] += 1
                    usable.discard(id(worker))
                    worker.retire()
                except ValueError as exc:
                    failures[identity] = str(exc)
                    report['failed_variants'] += 1
                progressed = True
            if pending and not inflight and not any(id(worker) in usable and worker.alive() for worker in workers):
                while pending:
                    job = pending.pop(0)
                    failures[(job['sha256'], int(job['gpu']))] = 'No owned vertex worker remains'
                    report['failed_variants'] += 1
                progressed = True
            if not progressed:
                stamp = tick()
                sleep(interval)
                if profiling:profile['idle_poll_us'] += (tick() - stamp) // 1000
        stamp = tick()
        shutdown = monotonic() + SHUTDOWN_SECONDS
        for worker in workers:
            if worker.alive():
                try:
                    worker.write(END)
                except OSError:
                    worker.retire()
        while monotonic() < shutdown and any(worker.alive() for worker in workers):
            if poll:
                poll()
            for worker in workers:
                try:
                    worker.read_available()
                except OSError:
                    pass
            sleep(interval)
        if profiling:profile['shutdown_us'] = (tick() - stamp) // 1000
        return compiled, failures, report
    finally:
        if pool is not None:
            try:
                if hasattr(pool, 'statistics'):
                    report.update(pool.statistics())
            finally:
                pool.retire(workers)
        report['seconds'] = time.perf_counter() - started
        if profiling:
            import json
            from shader_coverage import bounded_read
            rows = []
            for path in sorted(work.glob('worker-*.log')):
                try:
                    for line in bounded_read(path, 65536).decode('ascii', errors='replace').splitlines():
                        if line.startswith('[vertex-profile] '):
                            rows.append(json.loads(line[len('[vertex-profile] '):]))
                except (ValueError, OSError):
                    pass  # Cancellation may stop a worker in its final diagnostic write.
            profile['workers'] = rows
            report['timings'] = profile


def ctypes_kernel():
    import ctypes
    library = ctypes.WinDLL('kernel32', use_last_error=True)
    void_p = ctypes.c_void_p
    library.CreateJobObjectW.argtypes = [void_p, ctypes.c_wchar_p]
    library.CreateJobObjectW.restype = void_p
    library.SetInformationJobObject.argtypes = [void_p, ctypes.c_int, void_p, ctypes.c_ulong]
    library.SetInformationJobObject.restype = ctypes.c_int
    library.QueryInformationJobObject.argtypes = [void_p, ctypes.c_int, void_p, ctypes.c_ulong, void_p]
    library.QueryInformationJobObject.restype = ctypes.c_int
    library.CreatePipe.argtypes = [ctypes.POINTER(void_p), ctypes.POINTER(void_p), void_p, ctypes.c_ulong]
    library.CreatePipe.restype = ctypes.c_int
    library.SetHandleInformation.argtypes = [void_p, ctypes.c_ulong, ctypes.c_ulong]
    library.SetHandleInformation.restype = ctypes.c_int
    library.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, void_p, ctypes.c_ulong,
                                    ctypes.c_ulong, void_p]
    library.CreateFileW.restype = void_p
    library.CreateProcessW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p, void_p, void_p, ctypes.c_int,
                                       ctypes.c_ulong, void_p, ctypes.c_wchar_p, void_p, void_p]
    library.CreateProcessW.restype = ctypes.c_int
    library.InitializeProcThreadAttributeList.argtypes = [void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(ctypes.c_size_t)]
    library.InitializeProcThreadAttributeList.restype = ctypes.c_int
    library.UpdateProcThreadAttribute.argtypes = [void_p, ctypes.c_ulong, ctypes.c_size_t, void_p, ctypes.c_size_t, void_p, void_p]
    library.UpdateProcThreadAttribute.restype = ctypes.c_int
    library.DeleteProcThreadAttributeList.argtypes = [void_p]
    library.ResumeThread.argtypes = [void_p]
    library.ResumeThread.restype = ctypes.c_ulong
    library.TerminateProcess.argtypes = [void_p, ctypes.c_uint]
    library.TerminateProcess.restype = ctypes.c_int
    library.WaitForSingleObject.argtypes = [void_p, ctypes.c_ulong]
    library.WaitForSingleObject.restype = ctypes.c_ulong
    library.CloseHandle.argtypes = [void_p]
    library.CloseHandle.restype = ctypes.c_int
    library.PeekNamedPipe.argtypes = [void_p, void_p, ctypes.c_ulong, void_p, ctypes.POINTER(ctypes.c_ulong), void_p]
    library.PeekNamedPipe.restype = ctypes.c_int
    library.ReadFile.argtypes = [void_p, void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), void_p]
    library.ReadFile.restype = ctypes.c_int
    library.WriteFile.argtypes = [void_p, void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), void_p]
    library.WriteFile.restype = ctypes.c_int
    library.IsProcessInJob.argtypes = [void_p, void_p, ctypes.POINTER(ctypes.c_int)]
    library.IsProcessInJob.restype = ctypes.c_int
    library.GetCurrentProcess.restype = void_p
    return library


class _WinWorker:
    def __init__(self, kernel, process, stdin_write, stdout_read, pid):
        self.kernel = kernel
        self.process = process
        self.stdin_write = stdin_write
        self.stdout_read = stdout_read
        self.pid = pid
        self._retired = False

    def write(self, payload):
        import ctypes
        offset = 0
        while offset < len(payload):
            chunk = payload[offset:offset + 65536]
            written = ctypes.c_ulong()
            buffer = ctypes.create_string_buffer(chunk)
            if not self.kernel.WriteFile(self.stdin_write, buffer, len(chunk), ctypes.byref(written), None):
                raise OSError('Vertex worker stopped reading')
            if not written.value:
                raise OSError('Vertex worker stopped reading')
            offset += written.value

    def read_available(self):
        import ctypes
        available = ctypes.c_ulong()
        if not self.kernel.PeekNamedPipe(self.stdout_read, None, 0, None, ctypes.byref(available), None):
            return b''
        if not available.value:
            return b''
        size = min(int(available.value), 65536)
        buffer = ctypes.create_string_buffer(size)
        got = ctypes.c_ulong()
        if not self.kernel.ReadFile(self.stdout_read, buffer, size, ctypes.byref(got), None):
            return b''
        return buffer.raw[:got.value]

    def alive(self):
        return self.kernel.WaitForSingleObject(self.process, 0) == 258

    def retire(self):
        # Terminate only the process handle this pool created.
        if self._retired:
            return
        self._retired = True
        if self.process and self.alive():
            self.kernel.TerminateProcess(self.process, 1)
        if self.process:
            self.kernel.WaitForSingleObject(self.process, 15000)
            if self.alive():
                self.kernel.TerminateProcess(self.process, 1)
                self.kernel.WaitForSingleObject(self.process, 15000)
        for handle in (self.stdin_write, self.stdout_read, self.process):
            if handle:
                self.kernel.CloseHandle(handle)
        self.stdin_write = self.stdout_read = self.process = None


def job_commit_limit(count):
    """1 GiB for up to four workers (unchanged); 256 MiB each beyond that. Per-process cap stays 512 MiB."""
    return max(LIMITS['worker_job_commit_bytes'], count * WORKER_JOB_SHARE)


class _WinPool:
    def __init__(self, count=4):
        import ctypes
        self.ctypes = ctypes
        self.kernel = ctypes_kernel()
        self.job_limit = job_commit_limit(count)
        self.job = self.kernel.CreateJobObjectW(None, None)
        if not self.job:
            raise ValueError('Could not own vertex compiler workers')
        info = _extended_limits(ctypes)
        info.BasicLimitInformation.LimitFlags = (JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE |
            JOB_OBJECT_LIMIT_PROCESS_MEMORY | JOB_OBJECT_LIMIT_JOB_MEMORY)
        info.ProcessMemoryLimit = WORKER_MEMORY
        info.JobMemoryLimit = self.job_limit
        if not self.kernel.SetInformationJobObject(self.job, JOB_OBJECT_EXTENDED_LIMIT, ctypes.byref(info), ctypes.sizeof(info)):
            self.kernel.CloseHandle(self.job)
            raise ValueError('Could not own vertex compiler workers')
        self.ownership = 'private-job'
        self._closed = False
        self.workers = []

    def spawn(self, slot, decoder, work, environment):
        command = subprocess.list2cmdline(worker_command(decoder))
        worker = _create_worker(self, slot, command, work, environment)
        self.workers.append(worker)
        return worker

    def statistics(self):
        info = _extended_limits(self.ctypes)
        if not self.kernel.QueryInformationJobObject(self.job, JOB_OBJECT_EXTENDED_LIMIT,
                self.ctypes.byref(info), self.ctypes.sizeof(info), None):
            return dict(worker_peak_commit_bytes=None, worker_job_peak_commit_bytes=None)
        return dict(worker_peak_commit_bytes=int(info.PeakProcessMemoryUsed),
                    worker_job_peak_commit_bytes=int(info.PeakJobMemoryUsed))

    def retire(self, workers):
        for worker in workers:
            worker.retire()
        if self.job and not self._closed:
            self.kernel.CloseHandle(self.job)
            self.job = None
            self._closed = True


def _extended_limits(ctypes):
    class Basic(ctypes.Structure):
        _fields_ = [('PerProcessUserTimeLimit', ctypes.c_longlong), ('PerJobUserTimeLimit', ctypes.c_longlong),
                    ('LimitFlags', ctypes.c_ulong), ('MinimumWorkingSetSize', ctypes.c_size_t),
                    ('MaximumWorkingSetSize', ctypes.c_size_t), ('ActiveProcessLimit', ctypes.c_ulong),
                    ('Affinity', ctypes.c_size_t), ('PriorityClass', ctypes.c_ulong), ('SchedulingClass', ctypes.c_ulong)]

    class Counters(ctypes.Structure):
        _fields_ = [('ReadOperationCount', ctypes.c_ulonglong), ('WriteOperationCount', ctypes.c_ulonglong),
                    ('OtherOperationCount', ctypes.c_ulonglong), ('ReadTransferCount', ctypes.c_ulonglong),
                    ('WriteTransferCount', ctypes.c_ulonglong), ('OtherTransferCount', ctypes.c_ulonglong)]

    class Extended(ctypes.Structure):
        _fields_ = [('BasicLimitInformation', Basic), ('IoInfo', Counters),
                    ('ProcessMemoryLimit', ctypes.c_size_t), ('JobMemoryLimit', ctypes.c_size_t),
                    ('PeakProcessMemoryUsed', ctypes.c_size_t), ('PeakJobMemoryUsed', ctypes.c_size_t)]
    return Extended()


def _startup(ctypes):
    class Startup(ctypes.Structure):
        _fields_ = [('cb', ctypes.c_ulong), ('lpReserved', ctypes.c_wchar_p), ('lpDesktop', ctypes.c_wchar_p),
                    ('lpTitle', ctypes.c_wchar_p), ('dwX', ctypes.c_ulong), ('dwY', ctypes.c_ulong),
                    ('dwXSize', ctypes.c_ulong), ('dwYSize', ctypes.c_ulong), ('dwXCountChars', ctypes.c_ulong),
                    ('dwYCountChars', ctypes.c_ulong), ('dwFillAttribute', ctypes.c_ulong), ('dwFlags', ctypes.c_ulong),
                    ('wShowWindow', ctypes.c_ushort), ('cbReserved2', ctypes.c_ushort), ('lpReserved2', ctypes.c_void_p),
                    ('hStdInput', ctypes.c_void_p), ('hStdOutput', ctypes.c_void_p), ('hStdError', ctypes.c_void_p)]

    class Extended(ctypes.Structure):
        _fields_ = [('StartupInfo', Startup), ('lpAttributeList', ctypes.c_void_p)]

    class Process(ctypes.Structure):
        _fields_ = [('hProcess', ctypes.c_void_p), ('hThread', ctypes.c_void_p),
                    ('dwProcessId', ctypes.c_ulong), ('dwThreadId', ctypes.c_ulong)]

    class Security(ctypes.Structure):
        _fields_ = [('nLength', ctypes.c_ulong), ('lpSecurityDescriptor', ctypes.c_void_p), ('bInheritHandle', ctypes.c_int)]
    return Extended, Process, Security


def _pipe(kernel, ctypes, size):
    security_type = _startup(ctypes)[2]
    security = security_type(ctypes.sizeof(security_type), None, 1)
    read = ctypes.c_void_p()
    write = ctypes.c_void_p()
    if not kernel.CreatePipe(ctypes.byref(read), ctypes.byref(write), ctypes.byref(security), size):
        raise ValueError('Could not own vertex compiler workers')
    return read.value, write.value


def _hide_inherit(kernel, handle):
    if not kernel.SetHandleInformation(handle, 1, 0):
        raise ValueError('Could not own vertex compiler workers')


def _invalid_handle(value):
    if not isinstance(value, int) or value <= 0:
        return True
    unsigned = value & ((1 << 64) - 1)
    return unsigned in (0xFFFFFFFF, 0xFFFFFFFFFFFFFFFF)


def _close_handles(kernel, handles):
    for handle in handles:
        if handle:
            kernel.CloseHandle(handle)


def _environment_text(env):
    """Unicode environment block text, including the final extra NUL."""
    if not isinstance(env, dict) or not env:
        raise ValueError('Vertex worker environment is not explicit')
    seen = set()
    items = []
    for key in sorted(env, key=str.upper):
        value = env[key]
        if not isinstance(key, str) or not isinstance(value, str):
            raise ValueError('Vertex worker environment must be text')
        if not key or '=' in key or any(ch in key or ch in value for ch in '\0\r\n'):
            raise ValueError('Vertex worker environment contains an invalid entry')
        marker = key.upper()
        if marker in seen:
            raise ValueError('Vertex worker environment contains a duplicate name')
        seen.add(marker)
        items.append(key + '=' + value)
    return '\0'.join(items) + '\0\0'


def _environment_block(env):
    """UTF-16 environment block, including surrogate pairs and embedded NUL separators."""
    import ctypes
    return ctypes.create_string_buffer(_environment_text(env).encode('utf-16-le'))


def _process_flags(private_job, explicit_environment):
    """Kill-on-close job stays mandatory. The environment is an explicit Unicode block."""
    flags = PROCESS_FLAGS
    if flags & CREATE_BREAKAWAY_FROM_JOB or not explicit_environment:
        raise ValueError('Could not own vertex compiler workers')
    if private_job:
        flags |= EXTENDED_STARTUPINFO_PRESENT
    return flags | CREATE_UNICODE_ENVIRONMENT


def _create_worker(pool, slot, command, work, environment):
    import ctypes
    kernel = pool.kernel
    log = work / f'worker-{slot}.log'
    stdin_read = stdin_write = stdout_read = stdout_write = None
    stderr = None
    process = None
    try:
        stdin_read, stdin_write = _pipe(kernel, ctypes, 65536)
        stdout_read, stdout_write = _pipe(kernel, ctypes, MAX_SOURCE + MAX_BYTECODE + 4096)
        _hide_inherit(kernel, stdin_write)
        _hide_inherit(kernel, stdout_read)
        security_type = _startup(ctypes)[2]
        security = security_type(ctypes.sizeof(security_type), None, 1)
        stderr = kernel.CreateFileW(str(log), 0x40000000, 1, ctypes.byref(security), 2, 0x80, None)
        if _invalid_handle(stderr):
            stderr = None
            raise ValueError('Could not own vertex compiler workers')
        extended_type, process_type, _security = _startup(ctypes)
        process = process_type()
        command_buffer = ctypes.create_unicode_buffer(command)
        # Explicit Unicode environment. Only the three standard handles stay inheritable.
        block = _environment_block(environment)
        created, error = _create_process(pool, extended_type, process, command_buffer, block, work,
                                         stdin_read, stdout_write, stderr, True)
        if not created:
            # Being in some parent job does not prove workers die if this helper
            # exits. Require our non-inherited kill-on-close job even when nested.
            raise ValueError(f'Could not own vertex compiler workers (Windows error {error})')
        if kernel.ResumeThread(process.hThread) == 0xFFFFFFFF:
            kernel.TerminateProcess(process.hProcess, 1)
            kernel.WaitForSingleObject(process.hProcess, 15000)
            raise ValueError('Could not own vertex compiler workers')
        _close_handles(kernel, (stdin_read, stdout_write, stderr, process.hThread))
        return _WinWorker(kernel, process.hProcess, stdin_write, stdout_read, process.dwProcessId)
    except BaseException:
        if process is not None and process.hProcess:
            kernel.TerminateProcess(process.hProcess, 1)
            kernel.WaitForSingleObject(process.hProcess, 15000)
            kernel.CloseHandle(process.hProcess)
            if process.hThread:
                kernel.CloseHandle(process.hThread)
        _close_handles(kernel, (stdin_read, stdin_write, stdout_read, stdout_write, stderr))
        raise


def _create_process(pool, extended_type, process, command, environment, work, stdin, stdout, stderr, private_job):
    import ctypes
    kernel = pool.kernel
    info = extended_type()
    startup = info.StartupInfo
    startup.cb = ctypes.sizeof(extended_type if private_job else startup)
    startup.dwFlags = 0x00000100 | 0x00000001  # STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW
    startup.wShowWindow = 0  # SW_HIDE
    startup.hStdInput = stdin
    startup.hStdOutput = stdout
    startup.hStdError = stderr
    flags = _process_flags(private_job, environment is not None)
    attribute = None
    jobs = None
    if private_job:
        size = ctypes.c_size_t()
        kernel.InitializeProcThreadAttributeList(None, 1, 0, ctypes.byref(size))
        attribute = ctypes.create_string_buffer(size.value)
        if not kernel.InitializeProcThreadAttributeList(attribute, 1, 0, ctypes.byref(size)):
            attribute = None
            raise ValueError('Could not own vertex compiler workers')
        jobs = (ctypes.c_void_p * 1)(pool.job)
        info.lpAttributeList = ctypes.cast(attribute, ctypes.c_void_p)
    try:
        if private_job and not kernel.UpdateProcThreadAttribute(
                attribute, 0, PROC_THREAD_ATTRIBUTE_JOB_LIST, ctypes.cast(jobs, ctypes.c_void_p),
                ctypes.sizeof(jobs), None, None):
            raise ValueError('Could not own vertex compiler workers')
        # bInheritHandles is 1 so the prepared standard handles are inherited. Pipe ends the
        # parent still uses have HANDLE_FLAG_INHERIT cleared. lpEnvironment is the Unicode block.
        env_ptr = ctypes.cast(environment, ctypes.c_void_p)
        ok = kernel.CreateProcessW(None, command, None, None, 1, flags, env_ptr, str(work),
                                   ctypes.byref(info), ctypes.byref(process))
        error = ctypes.get_last_error() if not ok else 0
        return ok, error
    finally:
        if attribute is not None:
            kernel.DeleteProcThreadAttributeList(attribute)


def open_workers(count, decoder, work, translation='default'):
    if not 1 <= count <= MAX_WORKERS:
        raise ValueError('Vertex compiler worker cap exceeded')
    environment = shader_translation.environment(translation)
    from preparation_profile import enabled
    if enabled():environment['GT5P_PREPARE_SHADER_PROFILE']='1'
    environment.update(shader_source_policy.overlay())
    pool = _WinPool(count)
    workers = []
    try:
        for slot in range(count):
            workers.append(pool.spawn(slot, decoder, work, environment))
        return pool, workers
    except BaseException:
        pool.retire(workers)
        raise


if __name__ == '__main__':
    sys.exit(worker_main(sys.argv))
