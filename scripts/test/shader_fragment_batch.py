"""Exact request deduplication, dither separation and fail-closed result joins."""
import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).parents[1]))
from shader_fragment_batch import compile_batch,io_mode
from shader_coverage import fnv64

raw=b'\0'*16
state=dict(exp32=0,cube=0,stencil=0,unnorm=0,samplers='0'*16,ghi=0,shd=0,unhi=0,rtfmt=28,nrt=1,cmask=15)
job=dict(id='first',fragment=raw,fragment_sha256=hashlib.sha256(raw).hexdigest(),state=state,used=0)
duplicate=dict(job,id='duplicate')
other=copy.deepcopy(job);other['id']='other';other['state']['cube']=1
no_dither=copy.deepcopy(job);no_dither['id']='no-dither';no_dither['state']['rtfmt']=11
jobs=[job,duplicate,other,no_dither]
assert io_mode({}) and not io_mode({'GT5P_PREPARE_FRAGMENT_IO':'0'})
for value in ('','2','true'):
    try:io_mode({'GT5P_PREPARE_FRAGMENT_IO':value})
    except ValueError:pass
    else:raise AssertionError('Invalid fragment I/O accepted')

def fake(engine,game,env,log,timeout):
    work=Path(env['RSX_SHADER_LIBRARY_BATCH']);cache=Path(env['RSX_SHADER_CACHE'])
    lines=(work/'jobs.txt').read_text().splitlines();count=int(lines[0].split()[1])
    assert count==len(lines)-1 and count<=4096
    rows=[]
    for line in lines[1:]:
        values=line.split();assert len(values)==12
        identity,digest,raw_hash=values[:3]
        assert raw_hash==f'{fnv64((work/(digest+".fp")).read_bytes()):016x}'
        key=hashlib.sha256(line.encode()).hexdigest()[:16]
        (cache/(key+'.dxbc')).write_bytes(b'DXBC synthetic '+identity.encode())
        rows.append(f'{identity} {raw_hash} {key} 1')
    (work/'compiled.tsv').write_text(f'GT5P_FP_BATCH_RESULTS_V1 {count}\n'+'\n'.join(rows)+'\n')
    return f'[fp-batch] finished: requests={count} rejected=0 compiled={count} elapsed_ms=1'

with tempfile.TemporaryDirectory() as folder:
    root=Path(folder)
    def run(name,callback=fake,items=jobs,**options):
        work=root/name;work.mkdir();cache=work/'shadercache';cache.mkdir()
        with patch('shader_fragment_batch.run_offline',side_effect=callback):
            return compile_batch(items,work,cache,root/'engine',root,**options)
    compiled,failures=run('good')
    assert not failures and set(compiled)=={j['id'] for j in jobs}
    assert compiled['first']==compiled['duplicate'] and compiled['first']!=compiled['other']
    report=json.loads((root/'good/fragment-preparation-report.json').read_text())
    assert report['unique_requests']==3 and report['processes']==2
    assert report['compact_io'] and report['input_file_checks']==2 and report['code_file_reads']==3
    with patch.dict(os.environ,{'GT5P_PREPARE_FRAGMENT_IO':'0'}):
        legacy,legacy_failures=run('io-rollback')
    assert legacy==compiled and not legacy_failures
    rollback=json.loads((root/'io-rollback/fragment-preparation-report.json').read_text())
    assert not rollback['compact_io'] and rollback['input_file_checks']==3
    with patch('shader_fragment_batch.run_offline',side_effect=fake):
        repeated,repeated_failures=compile_batch(jobs,root/'good',root/'good/shadercache',root/'engine',root)
    assert repeated==compiled and not repeated_failures
    def bad_rows(*args,**kwargs):
        text=fake(*args,**kwargs);env=args[2];p=Path(env['RSX_SHADER_LIBRARY_BATCH'])/'compiled.tsv'
        lines=p.read_text().splitlines();p.write_text('\n'.join(lines+[lines[-1]])+'\n');return text
    compiled,failures=run('duplicate-result',bad_rows)
    assert not compiled and len(failures)==4
    def missing_summary(*args,**kwargs):fake(*args,**kwargs);return ''
    compiled,failures=run('missing-summary',missing_summary)
    assert not compiled and len(failures)==4
    published=[]
    compiled,failures=run('missing-summary-publication',missing_summary,on_batch_ready=published.append)
    assert not compiled and not published and len(failures)==4
    def wrong_count(*args,**kwargs):
        return fake(*args,**kwargs).replace('requests=2', 'requests=99').replace('requests=1', 'requests=99')
    compiled,failures=run('wrong-summary-count',wrong_count,on_batch_ready=published.append)
    assert not compiled and not published and len(failures)==4
    published=[];polls=[]
    compiled,failures=run('chunks',batch_size=1,on_batch_ready=lambda rows:published.append(dict(rows)),
                          poll=lambda:polls.append(True))
    assert not failures and len(published)==len(polls)==3
    assert set().union(*(set(rows) for rows in published))=={j['id'] for j in jobs}
    assert any(set(rows)=={'first','duplicate'} for rows in published)
    many=[]
    for index in range(270):
        item=copy.deepcopy(job);item['id']=str(index);item['state']['cube']=index
        many.append(item)
    chunks=[]
    compiled,failures=run('default-checkpoint-boundary',items=many,batch_size=256,
                          on_batch_ready=lambda rows:chunks.append(len(rows)))
    assert not failures and len(compiled)==270 and chunks==[256,14]
    def cancel(rows):
        published.append(dict(rows))
        raise KeyboardInterrupt('Test cancel after verified chunk')
    calls=[]
    def counted(*args,**kwargs):calls.append(True);return fake(*args,**kwargs)
    try:run('cancel-chunk',counted,batch_size=1,on_batch_ready=cancel)
    except KeyboardInterrupt:pass
    else:raise AssertionError('Cancellation swallowed')
    assert len(calls)==1
    def failed_publication(rows):raise ValueError('Checkpoint write failed')
    calls.clear()
    try:run('publication-error',counted,batch_size=1,on_batch_ready=failed_publication)
    except ValueError as exc:assert str(exc)=='Checkpoint write failed'
    else:raise AssertionError('Publication error swallowed')
    assert len(calls)==1
    aliases=[]
    def aliased(*args,**kwargs):
        text=fake(*args,**kwargs)
        work=Path(args[2]['RSX_SHADER_LIBRARY_BATCH']);cache=Path(args[2]['RSX_SHADER_CACHE'])
        rows=(work/'compiled.tsv').read_text().splitlines()
        key='f'*16
        (cache/(key+'.dxbc')).write_bytes(b'DXBC shared '+(b'A' if not aliases else aliases[0]))
        aliases.append(b'B')
        (work/'compiled.tsv').write_text(rows[0]+'\n'+'\n'.join(' '.join(row.split()[:2]+[key,'1']) for row in rows[1:])+'\n')
        return text
    compiled,failures=run('cross-chunk-source-conflict',aliased,batch_size=1)
    assert failures and all('changed across native chunks' in error for error in failures.values())
    assert len(compiled)+len(failures)==len(jobs)
    for size in (0,4097,True,'2'):
        with patch('shader_fragment_batch.run_offline',side_effect=AssertionError('Compiler started')):
            try:run('invalid-size-'+str(size),batch_size=size)
            except ValueError:pass
            else:raise AssertionError('Invalid chunk size accepted')
    def timeout(*args,**kwargs):raise subprocess.TimeoutExpired('owned offline compiler',1)
    compiled,failures=run('timeout',timeout)
    assert not compiled and len(failures)==4
    broken=copy.deepcopy(job);broken['fragment_sha256']='0'*64
    bad_work=root/'bad-payload';bad_work.mkdir();(bad_work/'shadercache').mkdir()
    with patch('shader_fragment_batch.run_offline',side_effect=AssertionError('Compiler started')):
        try:compile_batch([broken],bad_work,bad_work/'shadercache',root/'engine',root)
        except ValueError:pass
        else:raise AssertionError('Bad payload accepted')
    conflict=copy.deepcopy(other);conflict['id']='first'
    try:run('conflict',items=[job,conflict])
    except ValueError:pass
    else:raise AssertionError('Conflicting job identifier selected')
print('Exact-request deduplication, dither split, result joins, corruption and timeout checks passed')
