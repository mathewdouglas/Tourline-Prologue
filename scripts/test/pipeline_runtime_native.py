"""Exercise the isolated renderer's bounded coverage collector without starting a game."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import uuid


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--runtime', type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    source = (args.runtime / 'libs/video/rsx_d3d12_backend.c').read_text(encoding='utf-8')
    start = source.index('#define PSO_COVERAGE_CAP')
    end = source.index('static void pso_metrics_report(', start)
    collector = source[start:end]
    assert 'AcquireSRWLockExclusive' in collector and 'ReleaseSRWLockExclusive' in collector
    stop = source[source.index('static void rt_stop(void)'):].split('\n}\n', 1)[0]
    # Source invariant, not a simulated join: the diagnostic adds no lock, IO,
    # timeout handler, or other collector call to shutdown.
    assert 'WaitForSingleObject(s_rt_thr, 2000);' in stop
    assert 'pso_coverage' not in stop and 's_pso_use' not in stop
    assert 'pso_coverage_summary(1)' not in source
    folder = root / 'scratch' / ('pipeline-runtime-native-' + uuid.uuid4().hex)
    folder.mkdir()
    prefix = '#include <windows.h>\n#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n#include <assert.h>\n#include <thread>\nusing u64=unsigned long long;using u32=unsigned int;\n'
    suffix = r'''
int main(int argc,char** argv) {
 assert(argc==2);s_pso_use_draw=1;
 if(!strcmp(argv[1],"cap")) {
  for(u32 i=0;i<PSO_COVERAGE_CAP;i++) {pso_coverage_note(i);pso_coverage_note(i);}
  assert(s_pso_use_unique==PSO_COVERAGE_CAP && !s_pso_use_truncated);
  pso_coverage_note(PSO_COVERAGE_CAP);pso_coverage_note(0);
  assert(s_pso_use_unique==PSO_COVERAGE_CAP && s_pso_use_truncated);
  // No periodic/final snapshot after overflow: the overflow itself must log it.
  return 0;
 } else {
  std::thread summary([] {for(int i=0;i<20;i++) {pso_coverage_count_pending();pso_coverage_summary(1);}});
  for(u32 i=0;i<1000;i++) {pso_coverage_note(i);pso_coverage_note(i);}
  summary.join();
  assert(s_pso_use_unique==(pso_coverage_on()?1000u:0u));
  assert(s_pso_use_pending==(pso_coverage_on()?20:0));
 }
 assert(s_pso_use_unique==s_pso_use_recorded);pso_coverage_summary(1);
 return 0;
}
'''
    (folder/'probe.cpp').write_text(prefix+collector+suffix)
    vc = 'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat'
    (folder/'build.cmd').write_text(f'@echo off\ncall "{vc}" >nul\nif errorlevel 1 exit /b 1\n"C:/Program Files/LLVM/bin/clang-cl.exe" /nologo /O2 /MD /std:c++20 /Feprobe.exe probe.cpp\n')
    env = dict(os.environ)
    env['PATH'] += ';C:/Program Files (x86)/Microsoft Visual Studio/Installer'
    build = subprocess.run(['cmd','/c',str(folder/'build.cmd')],cwd=folder,env=env,capture_output=True,text=True,timeout=120)
    (folder/'build.log').write_text(build.stdout+build.stderr)
    if build.returncode:raise RuntimeError('Collector build failed: '+str(folder/'build.log'))
    cases=[]
    for value,mode in [('1','cap'),('1','race'),('0','race'),(None,'race'),('invalid','race')]:
        child = dict(env)
        child.pop('RSX_PSO_COVERAGE',None)
        if value is not None:child['RSX_PSO_COVERAGE']=value
        result=subprocess.run([str(folder/'probe.exe'),mode],env=child,capture_output=True,text=True,timeout=30)
        assert result.returncode==0,result.stderr[-1000:]
        lines=re.findall(r'^\[pipeline-use\] key=([0-9a-f]{16})$',result.stderr,re.M)
        assert len(lines)==len(set(lines))
        summaries=re.findall(r'\[pipeline-use-summary\] format=1 unique=(\d+) recorded=(\d+) truncated=([01]) pending_shader_draws=(\d+)',result.stderr)
        if value=='1':
            expected=16384 if mode=='cap' else 1000
            assert len(lines)==expected and '0000000000000000' in lines
            assert tuple(map(int,summaries[-1]))==(expected,expected,int(mode=='cap'),0 if mode=='cap' else 20)
            assert all(a==b for a,b,_,_ in summaries)
            if mode=='cap':
                sys.path.insert(0, str(root/'scripts'))
                from pipeline_runtime_coverage import parse_log, Rejected
                try:
                    parse_log(result.stderr)
                except Rejected as exc:
                    assert 'truncated' in str(exc)
                else:
                    raise AssertionError('Overflow without a final callback produced a ratio')
        else:assert not lines and not summaries
        cases.append(dict(value=value,mode=mode,keys=len(lines),summaries=len(summaries)))
    (folder/'report.json').write_text(json.dumps(dict(cases=cases,
        source_sha256=hashlib.sha256(source.encode('utf-8')).hexdigest(),
        shutdown_check='Source invariant only: no diagnostic shutdown hook or wait change',
        overflow_without_final_callback_rejected=True),indent=2))
    print('Collector cap rejection without a final callback, deduplication, zero key, concurrent snapshots, pending counts and disabled modes pass:',folder/'report.json')

if __name__=='__main__':main()
