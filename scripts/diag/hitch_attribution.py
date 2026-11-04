"""Conservative display-interval accounting for RSX_HITCH_LOG CSV files.

Wall partitions are replay occupancy, not causal excess above a frame budget.
Async worker time and previous-batch GPU time are correlations, never added.
"""
import argparse
import bisect
import csv
import io
import json
import math
from pathlib import Path
from frame_hitches import read_trace, STAGES, COUNTERS, TEXTURE_COUNTERS

PARTITIONS = ('specialized_compile_on_replay', 'driver_creation_on_replay', 'dxbc_read_on_replay', 'texture_handling', 'pipeline_lookup', 'other_prepass',
              'gpu_fence_wait', 'present_call', 'other_replay', 'outside_replay')
EXTENDED = ('sync_compile_ms','sync_driver_ms','sync_read_ms','compile_us','skip_vp','skip_fp','skip_record')

CORRELATIONS = {'specialized_shader_compile': 'shader_compiles',
                'driver_pipeline_creation_us': 'driver_us',
                'driver_pipeline_calls': 'driver_calls',
                'successful_dxbc_reads_us': 'cache_us', 'compiler_worker_and_sync_us': 'compile_us',
                'shader_pending_vertex_skips': 'skip_vp',
                'shader_pending_fragment_or_pso_skips': 'skip_fp',
                'shader_pending_recording_skips': 'skip_record',
                'texture_allocations': 'tex_allocs', 'texture_allocation_ms': 'tex_alloc_ms',
                'texture_decode_ms': 'tex_decode_ms', 'uploads': 'uploads',
                'upload_bytes': 'upload_bytes'}


def events(rows, shots=()):
    previous = None
    batches = []
    for row in rows:
        batches.append(row)
        if not row['present']:
            continue
        if previous is not None:
            dt = row['qpc_ms'] - previous['qpc_ms']
            # Replay is serial on one renderer thread. Clip batches straddling
            # the previous display endpoint; never count parallel recording.
            replay = sum(max(0, min(r['batch_ms'], r['qpc_ms']-previous['qpc_ms'])) for r in batches)
            replay = min(dt, replay)
            keys = set(STAGES + COUNTERS + TEXTURE_COUNTERS) | set(CORRELATIONS.values()) | {'sync_compile_ms','sync_driver_ms','sync_read_ms'}
            delta = {k: row[k]-previous[k] for k in keys if k in row and k in previous}
            sync = sum(delta.get(k,0) for k in ('sync_compile_ms','sync_driver_ms','sync_read_ms'))
            measured = dict(specialized_compile_on_replay=delta.get('sync_compile_ms',0),
                driver_creation_on_replay=delta.get('sync_driver_ms',0),
                dxbc_read_on_replay=delta.get('sync_read_ms',0),
                texture_handling=delta.get('tex_ms', 0),
                pipeline_lookup=max(0,delta.get('pso_ms', 0)-sync),
                other_prepass=max(0, delta.get('pre_ms', 0)-delta.get('srv_ms', 0)-delta.get('pso_ms', 0))
                    + max(0, delta.get('srv_ms', 0)-delta.get('tex_ms', 0)),
                gpu_fence_wait=delta.get('wait_ms', 0),
                present_call=sum(r['present_ms'] for r in batches))
            # Snapshot jitter/thread overlap must not invent extra wall time.
            raw = sum(measured.values())
            scale = min(1, replay/raw) if raw else 1
            parts = {k: v*scale for k,v in measured.items()}
            parts['other_replay'] = max(0, replay-sum(parts.values()))
            parts['outside_replay'] = dt-replay
            yield dict(start_ms=previous['unix_ms'], end_ms=row['unix_ms'], interval_ms=dt,
                partitions_ms=parts, clipped_stage_ms=max(0,raw-replay), deltas=delta,
                foreground=all(r['foreground'] for r in batches),
                shot_overlap=any(s['start_ms'] <= row['unix_ms'] and s['end_ms'] >= previous['unix_ms'] for s in shots),
                previous_gpu_ms=row['gpu_previous_ms'])
        previous = row
        batches = []


def summarize(samples, threshold, budget):
    late = [e for e in samples if e['interval_ms'] > threshold]
    total = sum(e['interval_ms'] for e in late)
    parts = {k:sum(e['partitions_ms'][k] for e in late) for k in PARTITIONS}
    return dict(threshold_ms=threshold, frames=len(late), total_interval_ms=total,
        excess_over_budget_ms=sum(max(0,e['interval_ms']-budget) for e in late),
        partitions=[dict(category=k, ms=v, share_percent=100*v/total if total else 0)
                    for k,v in sorted(parts.items(),key=lambda p:-p[1])],
        correlations={k:sum(e['deltas'].get(v,0) for e in late) for k,v in CORRELATIONS.items()},
        previous_gpu_over_budget_frames=sum(e['previous_gpu_ms'] > budget for e in late),
        zero_compile_and_driver_frames=sum(not e['deltas'].get('shader_compiles',0) and not e['deltas'].get('driver_calls',0) for e in late),
        clipped_stage_ms=sum(e['clipped_stage_ms'] for e in late),
        worst=sorted(late,key=lambda e:-e['interval_ms'])[:10])


def analyze(rows, shots=(), start=0, end=math.inf, budget=1000/59.94, include_contaminated=False):
    offsets=[row['unix_ms']-row['qpc_ms'] for row in rows]
    drift=max(offsets)-min(offsets)
    if drift>5:raise ValueError('Wall/QPC clock mapping drift exceeds 5 ms')
    for i,row in enumerate(rows):
        if i and row['unix_ms']<=rows[i-1]['unix_ms']:raise ValueError('Non-monotonic wall clock')
        for key in EXTENDED:
            if key not in row or not math.isfinite(row[key]) or row[key] < 0 or (i and row[key] < rows[i-1][key]):
                raise ValueError('Missing, invalid or reset extended trace counter: '+key)
    all_samples=[e for e in events(rows,shots) if e['start_ms'] >= start and e['end_ms'] <= end]
    samples=[e for e in all_samples if include_contaminated or (e['foreground'] and not e['shot_overlap'])]
    values=sorted(e['interval_ms'] for e in samples)
    if not values:
        raise ValueError('No accepted display intervals in window')
    return dict(clock_offset_spread_ms=drift, accepted_intervals=len(samples), accepted_interval_ms=sum(e['interval_ms'] for e in samples),
        trace_start_ms=rows[0]['unix_ms'], trace_end_ms=rows[-1]['unix_ms'],
        window_start_ms=start, window_end_ms=end if math.isfinite(end) else None,
        untraced_window_tail_ms=max(0,end-rows[-1]['unix_ms']) if math.isfinite(end) else None,
        excluded_background=sum(not e['foreground'] for e in all_samples),
        excluded_shot_overlap=sum(e['shot_overlap'] for e in all_samples),
        interval_median_ms=values[len(values)//2], interval_p99_ms=values[math.ceil(.99*len(values))-1],
        max_interval_ms=values[-1], budget_ms=budget,
        thresholds=[summarize(samples,t,budget) for t in (20,50)],
        totals={k:sum(e['deltas'].get(v,0) for e in samples) for k,v in CORRELATIONS.items()},
        discarded_tail_bytes=getattr(rows,'discarded_tail_bytes',0), trace_at_cap=len(rows)==32768,
        unresolved_categories=['guest CPU/SPU critical path','FIFO/command production stalls',
            'present/vblank pacing outside Present','pack/native-blob/guest file reads',
            'GPU bound status (previous sample only)','texture eviction cause versus first allocation'],
        limits='Partitions sum to accepted long-interval wall time, not causal hitch time. '
            'Texture includes allocation/upload handling. Pipeline lookup includes reads/translation/queueing; '
            'direct sync counters cover only cached-file D3DCompile and instrumented guest PSO calls. Async completions/read totals and previous GPU timings overlap '
            'wall partitions and are correlations only. Outside replay includes guest production, recording, '
            'pacing, scheduling, I/O and waits; it is not measured guest CPU. Missing geometry is counted in draws, not milliseconds.')


def host_summary(path, rows, shots, start, end, budget, allow_tail=False):
    """Separate host-thread ledger; never add it to parallel replay time."""
    if path.stat().st_size > 8*1024**2:
        raise ValueError('Host trace exceeds 8 MiB')
    data=path.read_bytes()
    discarded=0
    if data and not data.endswith(b'\n'):
        if not allow_tail:raise ValueError('Incomplete host trace tail')
        cut=data.rfind(b'\n')+1;discarded=len(data)-cut;data=data[:cut]
    records=[]
    required=('qpc_ms','fifo_ms','present_ms','pump_ms','vblank_ms','flip_ms','idle_ms','walk_cpu_ms')
    for raw in csv.DictReader(io.StringIO(data.decode('ascii'))):
        if None in raw or set(raw)!=set(required) or any(v is None for v in raw.values()):
            raise ValueError('Malformed host trace row')
        r={k:float(v) for k,v in raw.items()}
        if any(not math.isfinite(v) or v < 0 for v in r.values()):raise ValueError('Invalid host value')
        if records and (r['qpc_ms']<=records[-1]['qpc_ms'] or any(r[k]<records[-1][k] for k in required[1:])):
            raise ValueError('Reset host counter or clock')
        records.append(r)
        if len(records)>32768:raise ValueError('Host row cap exceeded')
    backend=list(events(rows,shots))
    accepted=[]
    begins=[e['start_ms'] for e in backend]
    ends=[e['end_ms'] for e in backend]
    # Unix and QPC are both captured in each backend row; use the nearest
    # backend endpoint for window/contamination membership, not wall-clock CPU.
    offset=rows[0]['unix_ms']-rows[0]['qpc_ms']
    excluded=0
    for previous,r in zip(records,records[1:]):
        begin,finish=previous['qpc_ms']+offset,r['qpc_ms']+offset
        if begin < start or finish > end:continue
        overlap=backend[bisect.bisect_right(ends,begin):bisect.bisect_left(begins,finish)]
        if not overlap or any(not e['foreground'] or e['shot_overlap'] for e in overlap):
            excluded+=1;continue
        delta={k:r[k]-previous[k] for k in required[1:]}
        dt=r['qpc_ms']-previous['qpc_ms']
        # walk CPU is a cycle-derived estimate contained in FIFO wall time.
        delta['unmeasured_ms']=max(0,dt-sum(delta[k] for k in required[1:-1]))
        accepted.append(dict(interval_ms=dt,stages=delta))
    return dict(accepted_intervals=len(accepted),excluded_intervals=excluded,discarded_tail_bytes=discarded,
        thresholds=[dict(threshold_ms=t,frames=sum(e['interval_ms']>t for e in accepted),
            total_interval_ms=sum(e['interval_ms'] for e in accepted if e['interval_ms']>t),
            stage_ms={k:sum(e['stages'][k] for e in accepted if e['interval_ms']>t) for k in (*required[1:],'unmeasured_ms')}) for t in (20,50)],
        limits='Host submission intervals, separate from backend replay/display intervals. FIFO includes command decoding/recording and blocking. '
            'walk_cpu_ms is a cycle-calibrated CPU estimate inside FIFO wall time. Idle is FIFO-kick waiting, including ordinary cadence. '
            'Unmeasured includes scheduling and unprobed host work. This does not isolate guest PPU/SPU critical paths.')


def read_producer(path):
    """Read existing PS3_TIMELINE C/Y/S/Q events; no guest program bytes."""
    if path.stat().st_size > 256*1024**2:raise ValueError('Timeline exceeds 256 MiB')
    counts={};first_present=None;overflow=False;events=0;declared=None
    def parse(line):
        cells=line.strip().split(',')
        if len(cells)!=5:raise ValueError('Malformed timeline row')
        t,tid,kind,a,b=cells
        values=tuple(map(int,(t,tid,a,b)))
        if any(v<0 for v in values) or len(kind)!=1:raise ValueError('Invalid timeline value')
        return values[0],values[1],kind,values[2],values[3]
    with path.open(encoding='ascii') as f:
        for line in f:
            if line.startswith('#events '):
                import re
                match=re.fullmatch(r'#events (\d+) \(capacity (\d+)\)\s*',line)
                if not match:raise ValueError('Malformed timeline completion marker')
                if declared is not None:raise ValueError('Duplicate timeline completion marker')
                declared=min(int(match[1]),int(match[2]))
                overflow=int(match[1])>=int(match[2])
            elif line.startswith('#'):continue
            else:
                t,tid,k,a,b=parse(line);events+=1
                if events>4194304:raise ValueError('Timeline event cap exceeded')
                if k=='C':counts[tid]=counts.get(tid,0)+1
                if k=='P' and (first_present is None or t<first_present):first_present=t
    if declared is None or declared!=events:raise ValueError('Missing or inconsistent timeline completion marker')
    if not counts or first_present is None:raise ValueError('Timeline lacks producer or host-present anchors')
    tid=max(counts,key=counts.get);mine=[]
    with path.open(encoding='ascii') as f:
        for line in f:
            if not line.startswith('#'):
                e=parse(line)
                if e[1]==tid and e[2] in ('C','Y','S','Q'):mine.append(e)
    mine.sort();ts=[e[0] for e in mine]
    prefix={k:[0] for k in ('Y','S','Q')}
    for e in mine:
        for k in prefix:prefix[k].append(prefix[k][-1]+(e[4] if e[2]==k else 0))
    frames=[]
    for t,_tid,k,cpu,wall in mine:
        if k!='C' or wall==0 or t<wall:continue
        left,right=bisect.bisect_right(ts,t-wall),bisect.bisect_right(ts,t)
        waits={k:(v[right]-v[left])/1000 for k,v in prefix.items()}
        residual=wall/1000-cpu/1000-waits['Y']-waits['Q']
        frames.append(dict(end_us=t,wall_ms=wall/1000,cpu_ms=cpu/1000,
            syscall_wait_ms=max(0,waits['Y']-waits['S']),sleep_ms=waits['S'],
            spin_sleep_ms=waits['Q'],unaccounted_ms=max(0,residual),overlap_ms=max(0,-residual)))
    return dict(tid=tid,frames=frames,first_present_us=first_present,overflow=overflow,
                recorded_events=events,other_producer_C_events=sum(counts.values())-counts[tid])


def producer_summary(path,host,rows,shots,start,end):
    producer=read_producer(path)
    with host.open(encoding='ascii') as f:
        first=next(csv.DictReader(f))
    base=rows[0]['unix_ms']-rows[0]['qpc_ms']+float(first['qpc_ms'])-producer['first_present_us']/1000
    backend=list(events(rows,shots));begins=[e['start_ms'] for e in backend];ends=[e['end_ms'] for e in backend]
    accepted=[]
    for frame in producer['frames']:
        finish=base+frame['end_us']/1000;begin=finish-frame['wall_ms']
        if begin<start or finish>end:continue
        overlap=backend[bisect.bisect_right(ends,begin):bisect.bisect_left(begins,finish)]
        if overlap and all(e['foreground'] and not e['shot_overlap'] for e in overlap):accepted.append(frame)
    stages=('cpu_ms','syscall_wait_ms','sleep_ms','spin_sleep_ms','unaccounted_ms','overlap_ms')
    return dict(tid=producer['tid'],accepted_producer_intervals=len(accepted),
        recorded_events=producer['recorded_events'],overflow=producer['overflow'],
        other_producer_C_events=producer['other_producer_C_events'],
        producer_trace_start_ms=base+producer['frames'][0]['end_us']/1000-producer['frames'][0]['wall_ms'] if producer['frames'] else None,
        producer_trace_end_ms=base+producer['frames'][-1]['end_us']/1000 if producer['frames'] else None,
        thresholds=[dict(threshold_ms=t,frames=sum(e['wall_ms']>t for e in accepted),
            total_interval_ms=sum(e['wall_ms'] for e in accepted if e['wall_ms']>t),
            stage_ms={k:sum(e[k] for e in accepted if e['wall_ms']>t) for k in stages}) for t in (20,50)],
        limits='Guest flip-producer intervals, not displayed frames. CPU is cycle-calibrated; '
            'syscall and spin sleeps include waiting for work/synchronization. Spin sleeps do not isolate SPU execution. '
            'S sleeps are contained in Y syscall timing and are subtracted there. CPU inside timed syscalls can overlap; overlap_ms reports negative residual. '
            'The first host P event anchors the clock with a small logging-call offset. Timeline collection/dump has extra overhead; '
            'a short diagnostic window is not a replacement for the primary route tables.')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace',type=Path)
    ap.add_argument('--window',type=Path)
    ap.add_argument('--host',type=Path)
    ap.add_argument('--timeline',type=Path,help='Optional PS3_TIMELINE diagnostic; requires --host')
    ap.add_argument('--shots',type=Path)
    ap.add_argument('--period',choices=('sample','grid','all'),default='sample')
    ap.add_argument('--budget-ms',type=float,default=1000/59.94)
    ap.add_argument('--allow-incomplete-tail',action='store_true')
    ap.add_argument('--include-contaminated',action='store_true')
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args()
    if not math.isfinite(a.budget_ms) or a.budget_ms <= 0:
        ap.error('Budget must be finite and positive')
    window=json.loads(a.window.read_text(encoding='utf-8-sig')) if a.window else {}
    shots=json.loads(a.shots.read_text(encoding='utf-8-sig')) if a.shots else []
    if a.period!='all' and not window:
        ap.error('Selected period requires --window')
    start=window.get('sample_start_ms',0) if a.period=='sample' else window.get('grid_observed_ms',0) if a.period=='grid' else 0
    end=window.get('sample_end_ms',math.inf) if a.period!='all' else math.inf
    if a.timeline and not a.host:ap.error('--timeline requires --host')
    rows=read_trace(a.trace,a.allow_incomplete_tail)
    result=analyze(rows,shots,start,end,a.budget_ms,a.include_contaminated)
    if a.host:result['host_submission']=host_summary(a.host,rows,shots,start,end,a.budget_ms,a.allow_incomplete_tail)
    if a.timeline:result['producer']=producer_summary(a.timeline,a.host,rows,shots,start,end)
    result.update(trace=str(a.trace),period=a.period)
    with a.output.open('x',encoding='utf-8') as f:
        json.dump(result,f,indent=2)
        f.write('\n')


if __name__=='__main__':
    main()
