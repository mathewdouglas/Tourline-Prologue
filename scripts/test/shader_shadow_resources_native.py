"""Production shadow alias, first-depth comparison and sampled-unit trimming.

No GPU/game starts. The allocation boundary is controlled; production conditions
and compare/key statements are extracted read-only into ignored local storage.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
sys.path.insert(0, str(Path(__file__).parents[1]))
from shader_material_state_native import function
from shader_coverage import ROOT

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument('--runtime', required=True, type=Path)
args = ap.parse_args()
source = (args.runtime / 'libs/video/rsx_d3d12_backend.c').read_text()
start = source.index('            if (zb_on() && dr->tex[_u].set')
end = source.index('            /* A unit whose remap', start)
alias = source[start:end]
start = source.index('    /* The compare of a unit bound with a depth format')
compare = source[start:source.index('\n}', start)]
start = source.index('          s_pso_shd = (s_pso_shd & used & 0xFFFFu) ?')
trim = source[start:source.index(';', start) + 1]
prefix = '''#include <stdint.h>
#include <stdlib.h>
typedef uint32_t u32;typedef uint16_t u16;typedef uint8_t u8;
#define RSX_MAX_TEXTURES 16
#define DXGI_FORMAT_R24_UNORM_X8_TYPELESS 1
#define D3D12_DEFAULT_SHADER_4_COMPONENT_MAPPING 1
static int enabled,allocated;
static int zb_on(void) {return enabled;}
static int zb_find(u32 a) {return -1;}
static int zb_get(u32 a,u32 w,u32 h) {return allocated ? 0 : -1;}
static void srv_write(u32 slot,void* res,u32 fmt,u32 mapping) {}
static struct {void* res;} s_zb[1];
typedef struct {struct {u32 set,depth,cube,local,fmt,raw,w,h;} tex[16];u16 tex_shd;u8 shd_func;} Draw;
typedef struct {struct {u32 format,address;} textures[16];} State;
'''
suffix = '''
__declspec(dllexport) u32 shadow(u32 unit,u32 earlier,u32 on,u32 alloc,u32 local,u32 cube,u32 volume,u32 fmt,u32 used) {
 Draw record={0},*dr=&record;State state={0},*st=&state;
 enabled=on;allocated=alloc;s_zb[0].res=(void*)1;
 dr->tex[unit].set=1;dr->tex[unit].depth=volume;dr->tex[unit].cube=cube;
 dr->tex[unit].local=local;dr->tex[unit].fmt=fmt;dr->tex[unit].raw=0x2000;
 dr->tex[unit].w=64;dr->tex[unit].h=64;
 st->textures[unit].format=fmt<<8;st->textures[unit].address=6u<<28;
 if(earlier<unit) {st->textures[earlier].format=0x90<<8;st->textures[earlier].address=3u<<28;}
''' + compare + '''
 for(int _u=0;_u<16;_u++) {u32 wslot=_u;
''' + alias + '''
 }
 u32 s_pso_shd=dr->tex_shd ? dr->tex_shd | ((u32)dr->shd_func<<16) : 0;
''' + trim + '''
 return s_pso_shd;
}
'''
folder = ROOT / 'scratch' / ('shadow-resources-native-' + uuid.uuid4().hex)
folder.mkdir()
(folder / 'oracle.c').write_text(prefix + function(source, 'texture_can_alias_rt') + suffix)
vc = 'C:/Program Files/Microsoft Visual Studio/2022/Community/VC/Auxiliary/Build/vcvars64.bat'
compiler = 'C:/Program Files/LLVM/bin/clang-cl.exe'
(folder / 'build.cmd').write_text(f'@echo off\ncall "{vc}" >nul\nif errorlevel 1 exit /b 1\n'
    f'"{compiler}" /nologo /O2 /MD /LD /Fooracle.obj /Feoracle.dll oracle.c\n')
subprocess.run(['cmd', '/c', str(folder / 'build.cmd')], cwd=folder, check=True)
for key in list(os.environ):
    if key.upper() == 'RSX_RT_LOCATION':
        del os.environ[key]
lib = ctypes.CDLL(str(folder / 'oracle.dll'))
lib.shadow.argtypes = [ctypes.c_uint32] * 9
lib.shadow.restype = ctypes.c_uint32
checks = 0
for unit in range(16):
    for fmt in (0x85, 0x90, 0x91, 0x92, 0x93, 0x94):
        for bits in range(64):
            on, allocated, local, cube, volume, sampled = [(bits >> i) & 1 for i in range(6)]
            used = (1 << unit) if sampled else 0
            actual = lib.shadow(unit, 16, on, allocated, local, cube, volume, fmt, used)
            expected = (6 << 16) | used if on and allocated and local and not cube and not volume and sampled and 0x90 <= fmt <= 0x93 else 0
            assert actual == expected, (unit, fmt, bits, hex(actual), hex(expected))
            checks += 1
    if unit:
        assert lib.shadow(unit, 0, 1, 1, 1, 0, 0, 0x90, 1 << unit) == (3 << 16) | (1 << unit)
        checks += 1
report = dict(checks=checks, scope='Original production alias/compare/trim statements; controlled alias allocation, default location policy; no GPU/game')
(folder / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
print(report)
print('Evidence:', folder / 'report.json')
