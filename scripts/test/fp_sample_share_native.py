"""Compile the patched sample-qualifier helpers and check them. No GPU."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fp_sample_share_build import ROOT, patched_source


def function(source, name):
    match = re.search(r'^static (?:int|u32) ' + name + r'\(', source, re.M)
    if not match:
        raise ValueError('Production function signature changed: ' + name)
    start = source.index('{', match.start())
    tokens = r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*.*?\*/|//[^\n]*|[{}]'
    depth = 0
    for token in re.finditer(tokens, source[start:], re.S):
        if token[0] == '{':
            depth += 1
        elif token[0] == '}':
            depth -= 1
            if depth == 0:
                return source[match.start():start + token.end()]
    raise ValueError('Unterminated production function: ' + name)


MASKS = (0, 0x10000, 0x20000, 0x40000, 0x60000, 1 << 30, 0xF | (1 << 30), 0x20000 | (1 << 30))


def expect_qualifier(enabled, mask):
    return 1 if enabled or ((mask >> 16) & 0xF) > 1 else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--vcvars', type=Path, default=Path(r'C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat'))
    ap.add_argument('--compiler', type=Path, default=Path(r'C:\Program Files\LLVM\bin\clang-cl.exe'))
    args = ap.parse_args()
    source_path = patched_source(ROOT / 'scratch' / 'fp-sample-share' / 'native-src')
    source = source_path.read_text(encoding='utf-8')
    if source.count('if (ss && fp_sample_qualifier(cube_mask))') != 1:
        raise ValueError('Sample qualifier is not the sole call site')
    if 'if (ss && ((cube_mask >> 16) & 0xFu) > 1)' in source:
        raise ValueError('Old sample-count test is still compiled in')
    if 'pd.SampleDesc.Count = ((cube_mask >> 16) & 0xFu) ? ((cube_mask >> 16) & 0xFu) : 1;' not in source:
        raise ValueError('Pipeline sample count no longer follows bits 16-19')
    snippets = '\n'.join(function(source, name) for name in
                          ('cube_units16', 'fp_sample_share_on', 'fp_sample_qualifier'))
    folder = source_path.parents[2]
    driver = r'''
#include <stdio.h>
#include <stdlib.h>
typedef unsigned int u32;
''' + snippets + r'''
int main(void) {
    unsigned masks[] = {0, 0x10000u, 0x20000u, 0x40000u, 0x60000u, 1u << 30, 0xFu | (1u << 30), 0x20000u | (1u << 30)};
    printf("dual %d\n", fp_sample_share_on());
    printf("units %u %u %u %u %u\n",
        cube_units16(1u << 30), cube_units16(0x20000u), cube_units16(0x40000u),
        cube_units16(0xFu | (1u << 30)), cube_units16(0x20000u | 0xFu));
    for (int i = 0; i < 8; i++) printf("q %08x %d\n", masks[i], fp_sample_qualifier(masks[i]));
    return 0;
}
'''
    (folder / 'qualifier.c').write_text(driver, encoding='ascii', newline='\n')
    command = ('@echo off\ncall "' + str(args.vcvars.resolve()) + '" >nul\n'
               'if errorlevel 1 exit /b 1\n"' + str(args.compiler.resolve()) +
               '" /nologo /O2 /MD /D_CRT_SECURE_NO_WARNINGS /Fo"' + str(folder / 'qualifier.obj') +
               '" /Fe"' + str(folder / 'qualifier.exe') + '" "' + str(folder / 'qualifier.c') + '"\n')
    (folder / 'build.cmd').write_text(command, encoding='ascii', newline='\r\n')
    subprocess.run(['cmd', '/c', str(folder / 'build.cmd')], check=True, cwd=folder)
    exe = folder / 'qualifier.exe'

    def run(value):
        env = os.environ.copy()
        env.pop('RSX_FP_SAMPLE_SHARE', None)
        if value is not None:
            env['RSX_FP_SAMPLE_SHARE'] = value
        out = subprocess.check_output([str(exe)], env=env, text=True)
        lines = out.splitlines()
        dual = int(lines[0].split()[1])
        units = [int(x) for x in lines[1].split()[1:]]
        quals = {int(parts[1], 16): int(parts[2]) for parts in (line.split() for line in lines[2:])}
        return dual, units, quals

    cases = (('unset', None, 1), ('zero', '0', 0), ('one', '1', 1), ('two', '2', 1), ('empty', '', 1), ('zero-prefix', '00', 1))
    for name, value, enabled in cases:
        dual, units, quals = run(value)
        if dual != enabled:
            raise SystemExit(f'{name}: switch read {dual}, expected {enabled}')
        if units != [1 << 14, 0, 0, 0xF | (1 << 14), 0xF]:
            raise SystemExit(f'{name}: cube unit unpack {units}')
        for mask in MASKS:
            got = quals[mask]
            want = expect_qualifier(enabled, mask)
            if got != want:
                raise SystemExit(f'{name}: mask 0x{mask:x} qualifier {got}, expected {want}')
    print('sample qualifier matches bits 16-19 only with RSX_FP_SAMPLE_SHARE=0; cube units 17/18 unpack to none')


if __name__ == '__main__':
    main()
