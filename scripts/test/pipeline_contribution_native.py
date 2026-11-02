"""Frozen collector/export probe: no real game, device or shader compilation.

Uses an existing private recorder/cache fixture and a tiny native launcher probe.
All generated source, original program bytes and output remain in ignored storage.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline_contribution import decode, read_json
from pipeline_template import read
from train_pipeline_cache import idle, isolated


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('helper-dir','reference-install','trace','cache','elf','output'):
        ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();idle();out=isolated(a.output)
    if out.exists():raise ValueError('Use a fresh ignored output')
    install=out/'Install';storage=out/'Storage';home=out/'Home'
    install.mkdir(parents=True);(storage/'input').mkdir(parents=True);home.mkdir()
    (install/'runtime').mkdir()
    shutil.copyfile(a.reference_install/'runtime/gt5p.exe',install/'runtime/gt5p.exe')
    shutil.copytree(a.reference_install/'assets',install/'assets')
    shutil.copytree(a.helper_dir,install/'preparation')
    shutil.copyfile(a.elf,storage/'input/EMAIN.ELF')
    (home/'storage.ini').write_text('[game]\ndirectory='+str(storage)+'\n',encoding='utf-16')
    cache=storage/'preparation'/('a'*24)/'shadercache'
    (cache/'warmup-v1').mkdir(parents=True)
    # Copy only dependencies of this bounded recorder fixture, not a whole cache.
    for p in a.trace.glob('links_*.jsonl'):
        for line in p.read_text().splitlines():
            r=json.loads(line)
            for name in ('pso_'+r['pipeline']+'.recipe','code_'+r['vs']+'.dxbc','code_'+r['ps']+'.dxbc'):
                shutil.copyfile(a.cache/'warmup-v1'/name,cache/'warmup-v1'/name)
    (storage/'prepared-cache.txt').write_text(cache.relative_to(storage).as_posix())
    before={p:p.read_bytes() for p in cache.rglob('*') if p.is_file()}
    # This is our own test launcher. Production collection uses the ordinary
    # launcher and therefore its existing storage locks/game job/restart logic.
    source=out/'launcher-probe.cpp'
    source.write_text(r'''
#include <windows.h>
#include <filesystem>
#include <string>
std::wstring env(const wchar_t* key) {
 wchar_t value[32768]; DWORD n=GetEnvironmentVariableW(key,value,32768);
 return n && n<32768 ? std::wstring(value,n) : L"";
}
int WINAPI wWinMain(HINSTANCE,HINSTANCE,PWSTR,int) {
 if(env(L"PS3_VERBOSE")!=L"0" || env(L"RSX_PSO_PROVENANCE_LIMIT")!=L"4096" ||
    env(L"RSX_SHADER_ASYNC")!=L"1" || env(L"RSX_PSO_ASYNC")!=L"1")return 20;
 try {
  for(auto& entry:std::filesystem::directory_iterator(env(L"GT5P_CONTRIBUTION_TEST_INPUT")))
   if(entry.is_regular_file())std::filesystem::copy_file(entry.path(),
      std::filesystem::path(env(L"RSX_PSO_PROVENANCE"))/entry.path().filename());
 } catch(...) {return 21;}
 return 0;
}
''')
    build=out/'build.cmd'
    build.write_text(f'''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
"C:\\Program Files\\LLVM\\bin\\clang-cl.exe" /nologo /std:c++17 /O2 /MT /EHsc /Fo"{out}/probe.obj" /Fe"{install}/tourline-prologue.exe" "{source}" /link /subsystem:windows
exit /b %errorlevel%
''')
    subprocess.run(['cmd','/c',str(build)],check=True)
    env={k:v for k,v in os.environ.items() if not k.upper().startswith(('GT5P_','RSX_'))}
    env.update(GT5P_LAUNCHER_HOME=str(home),GT5P_CONTRIBUTION_TEST_INPUT=str(a.trace.resolve()),
               RSX_SHADER_ASYNC='1',RSX_PSO_ASYNC='1',PATH=str(Path(os.environ['SystemRoot'])/'System32'))
    command=[str(install/'preparation/GT5P-Prepare.exe'),'--collect-contribution','--install',str(install)]
    settings=storage/'gt5p_settings.toml'
    settings.write_text('[video]\nresolution="1440p"\naspect="16:9"\n')
    with (out/'unsupported.log').open('wb') as stream:
        result=subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==1 and not (storage/'pipeline-contributions').exists()
    settings.write_text('[video]\nresolution="720p"\naspect="16:9"\n')
    original=settings.read_bytes()
    with (out/'collected.log').open('wb') as stream:
        subprocess.run(command,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=60,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
    exports=list((storage/'pipeline-contributions').glob('*/share-this-template.json'))
    assert len(exports)==1
    document=decode(read_json(exports[0]))
    assert document['records'] and document['compatibility']==read(install/'assets/pipeline-templates/gt5p-disc-v2')['compatibility']
    assert settings.read_bytes()==original and all(p.read_bytes()==b for p,b in before.items())
    assert 'private-recorder' not in exports[0].read_text() and str(storage) not in exports[0].read_text()
    (out/'validation.json').write_text(json.dumps(dict(frozen_collector=True,unsupported_settings_rejected_before_launch=True,
        metadata_only=True,cache_and_settings_unchanged=True,records=len(document['records']),
        limitation='Native launcher probe copies a prior local recorder fixture. No live game, new coverage or stutter claim.'),indent=2)+'\n')
    print('Frozen collection, storage discovery, unsupported settings, metadata export and cache preservation pass:',out)


if __name__=='__main__':main()
