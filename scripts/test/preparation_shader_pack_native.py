"""Compile the production pack reader; check both prepared shader stages.

Run sequentially, with --cache pointing at an idle private generated pack copy.
No game, device or shader compiler runs; clang only builds the reader harness.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_template import read, template_digest
from pipeline_warmup_plan import read as read_plan, bounded
from pipeline_runtime_coverage import MAX_REPORT
from preparation_shader_pack import dependencies


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('cache', 'template', 'plan', 'report'):
        ap.add_argument('--'+name, type=Path, required=True)
    args = ap.parse_args()
    root = Path(__file__).resolve().parents[2]
    runtime = Path(os.environ.get('PS3RECOMP_DIR', root.parent/'ps3recomp-gt5p-provenance'))
    source = (runtime/'libs/video/rsx_d3d12_backend.c').read_text(encoding='utf-8')
    block = source[source.index('#define SPACK_SLOTS'):source.index('static HRESULT d3d_compile_cached_file')]
    plan, template = read_plan(args.plan), read(args.template)
    if plan['template_sha256'] != template_digest(args.template):
        raise ValueError('Template mismatch')
    report = json.loads(bounded(args.report, MAX_REPORT))
    phases, expected = dependencies(plan, template, report)
    work = root/'scratch'/('shader-pack-native-'+uuid.uuid4().hex)
    work.mkdir()
    (work/'pack.inc').write_text(block, encoding='utf-8')
    manifest = work/'expected.txt'
    manifest.write_text(''.join(f'{scope} {s} {expected[s][0]} {expected[s][1]}\n'
        for scope,phase in enumerate(('menu', 'race')) for s in phases[phase]), encoding='ascii')
    command = work/'build.cmd'
    command.write_text(f'''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
"C:\\Program Files\\LLVM\\bin\\clang-cl.exe" /nologo /TC /O2 /MD /D_CRT_SECURE_NO_WARNINGS /I"{work}" /Fo"{work}/test.obj" /Fe"{work}/test.exe" "{root}/scripts/test/preparation_shader_pack_native.c" /link d3dcompiler.lib
exit /b %errorlevel%
''', encoding='ascii')
    subprocess.run(['cmd', '/c', str(command)], cwd=root, check=True)
    results = []
    for enabled in ('0', '1'):
        env = dict(os.environ, RSX_SHADER_PACK=enabled, RSX_SHADER_PACK_MB='64')
        result = subprocess.run([str(work/'test.exe'), str(args.cache.resolve()), str(manifest)],
            env=env, capture_output=True, text=True)
        (work/('enabled-'+enabled+'.log')).write_text(result.stdout+result.stderr, encoding='utf-8')
        results.append(dict(enabled=enabled, stdout=result.stdout, stderr=result.stderr))
        print(result.stdout, end='')
        if result.returncode:
            print(result.stderr)
            result.check_returncode()
    (work/'report.json').write_text(json.dumps(dict(runtime=str(runtime), results=results), indent=2)+'\n')
    print('Evidence:', work)


if __name__ == '__main__':
    main()
