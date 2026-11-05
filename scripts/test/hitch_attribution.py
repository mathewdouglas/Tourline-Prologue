"""Synthetic hitch accounting: offscreen join, overlap, worker correlation, rejection."""
import math
import csv
import tempfile
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'diag'))
from hitch_attribution import analyze, events, host_summary, read_producer, PARTITIONS
from frame_hitches import read_trace, STAGES, COUNTERS, TEXTURE_COUNTERS


def row(t,present=1,**kw):
    r=dict.fromkeys((*STAGES,*COUNTERS,*TEXTURE_COUNTERS),0.)
    r.update(unix_ms=1000+t,qpc_ms=t,batch_ms=0,present=present,foreground=1,
        present_ms=0,gpu_previous_ms=0,pending=0,skip_vp=0,skip_fp=0,skip_record=0,
        compile_us=0,sync_compile_ms=0,sync_driver_ms=0,sync_read_ms=0)
    r.update(kw)
    return r


def main():
    rows=[row(0),row(30,0,batch_ms=20,tex_ms=10,pre_ms=15,srv_ms=10),
          row(100,batch_ms=30,tex_ms=12,pre_ms=20,srv_ms=12,pso_ms=5,
              present_ms=2,driver_us=900000,driver_calls=1,shader_compiles=2,compile_us=1000000,
              skip_fp=25,sync_driver_ms=3)]
    e=list(events(rows))[0]
    assert e['interval_ms']==100
    assert sum(e['partitions_ms'].values())==100
    assert e['partitions_ms']['outside_replay']==50
    assert e['partitions_ms']['texture_handling']==12
    assert e['partitions_ms']['driver_creation_on_replay']==3
    assert e['partitions_ms']['pipeline_lookup']==2
    a=analyze(rows)
    assert analyze(rows,end=1500)['untraced_window_tail_ms']==400
    assert a['thresholds'][1]['correlations']['driver_pipeline_creation_us']==900000
    assert a['thresholds'][1]['correlations']['shader_pending_fragment_or_pso_skips']==25
    assert sum(p['ms'] for p in a['thresholds'][1]['partitions'])==100
    # Worker aggregate exceeds frame wall: it must never become a partition.
    assert max(p['ms'] for p in a['thresholds'][1]['partitions'])<=100
    for bad in ([dict(file='shot',start_ms=1030,end_ms=1040)],):
        try:analyze(rows,bad)
        except ValueError:pass
        else:raise AssertionError('Screenshot contaminated interval accepted')
        assert analyze(rows,bad,include_contaminated=True)['excluded_shot_overlap']==1
    rows[-1]['foreground']=0
    try:analyze(rows)
    except ValueError:pass
    else:raise AssertionError('Background accepted')
    rows[-1]['foreground']=1
    rows[-1]['tex_ms']=1000
    clipped=analyze(rows)
    assert clipped['thresholds'][0]['clipped_stage_ms']>0
    assert math.isclose(sum(p['ms'] for p in clipped['thresholds'][0]['partitions']),100)
    assert set(PARTITIONS)=={p['category'] for p in a['thresholds'][0]['partitions']}
    rows[-1]['tex_ms']=12
    with tempfile.TemporaryDirectory() as directory:
        trace=Path(directory)/'trace.csv'
        with trace.open('w',newline='') as f:
            writer=csv.DictWriter(f,fieldnames=rows[0].keys())
            writer.writeheader();writer.writerows(rows)
        parsed=read_trace(trace)
        assert analyze(parsed)['thresholds'][1]['frames']==1
        with trace.open('ab') as f:f.write(b'unterminated')
        parsed=read_trace(trace,True)
        assert parsed.discarded_tail_bytes==12
        assert analyze(parsed)['discarded_tail_bytes']==12
        host=Path(directory)/'host.csv'
        host.write_text('qpc_ms,fifo_ms,present_ms,pump_ms,vblank_ms,flip_ms,idle_ms,walk_cpu_ms\n'
                        '0,0,0,0,0,0,0,0\n100,20,20,0,0,0,50,10\n')
        h=host_summary(host,rows,[],0,math.inf,16.7)
        assert h['thresholds'][1]['frames']==1
        assert h['thresholds'][1]['stage_ms']['unmeasured_ms']==10
        assert h['thresholds'][1]['stage_ms']['walk_cpu_ms']==10
        timeline=Path(directory)/'timeline.csv'
        timeline.write_text('0,99,P,0,1\n20000,7,Y,0,6000\n21000,7,S,2000,2000\n'
                            '30000,7,Q,65,4000\n50000,7,C,10000,50000\n#events 5 (capacity 4194304)\n')
        producer=read_producer(timeline)
        assert producer['tid']==7 and len(producer['frames'])==1
        frame=producer['frames'][0]
        assert frame['cpu_ms']==10 and frame['syscall_wait_ms']==4
        assert frame['sleep_ms']==2 and frame['spin_sleep_ms']==4 and frame['unaccounted_ms']==30
        timeline.write_text(timeline.read_text().replace('#events 5','#events 6'))
        try:read_producer(timeline)
        except ValueError:pass
        else:raise AssertionError('Inconsistent timeline marker accepted')
        host.write_text(host.read_text().replace('50,10','-1,10'))
        try:host_summary(host,rows,[],0,math.inf,16.7)
        except ValueError:pass
        else:raise AssertionError('Invalid host counter accepted')
    original_clock=rows[-1]['unix_ms']
    rows[-1]['unix_ms']+=10
    try:analyze(rows)
    except ValueError:pass
    else:raise AssertionError('Discontinuous wall/QPC mapping accepted')
    rows[-1]['unix_ms']=original_clock
    rows[-1]['sync_compile_ms']=-1
    try:analyze(rows)
    except ValueError:pass
    else:raise AssertionError('Invalid extended counter accepted')
    print('Hitch attribution synthetic checks passed')


if __name__=='__main__':main()
