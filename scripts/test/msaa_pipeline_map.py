"""Phase 223 MSAA re-target stage: descriptor layout, re-targeting rules, keys and membership rewriting.

1. Compiles a two-line probe against the Windows SDK d3d12.h: SampleDesc.Count is at byte 616 (word 154) and
   Quality at 620 of the 656-byte D3D12_GRAPHICS_PIPELINE_STATE_DESC the template words hold.
2. Synthetic records: single-sample and same-count records are left alone; 2x/4x move to 1/2/4/8 with the key's
   sample bits (0 for 1x, as the renderer binds single-sample targets) and descriptor word together; a descriptor
   that disagrees with the key's sample bits is refused; the native key changes with the count and only with it.
3. stage_membership: re-targeted keys replace their sources in order, without duplicates, and keys without a
   local recipe are dropped.
4. Optional --report <preparation report.json> [--translation mode]: every multisampled record of a real
   preparation reproduces its native key from the cached shaders (the stage's precondition).
"""
import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))
import msaa_pipeline_map as m  # noqa: E402
from native_pipeline_key import native_key  # noqa: E402


def layout():
    work = ROOT/'scratch'/('msaa-layout-'+uuid.uuid4().hex)
    work.mkdir(parents=True)
    try:
        (work/'p.c').write_text('#include <stdio.h>\n#include <stddef.h>\n#include <d3d12.h>\n'
            'int main(void){printf("%zu %zu %zu",offsetof(D3D12_GRAPHICS_PIPELINE_STATE_DESC,SampleDesc),'
            'offsetof(D3D12_GRAPHICS_PIPELINE_STATE_DESC,SampleDesc)+offsetof(DXGI_SAMPLE_DESC,Quality),'
            'sizeof(D3D12_GRAPHICS_PIPELINE_STATE_DESC));return 0;}\n', encoding='ascii')
        (work/'b.cmd').write_text(f'''@echo off
call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul
"C:\\Program Files\\LLVM\\bin\\clang-cl.exe" /nologo /TC /W0 /Fo"{work}/" /Fe"{work}/p.exe" "{work}/p.c"
exit /b %errorlevel%
''')
        subprocess.run(['cmd', '/c', str(work/'b.cmd')], check=True, capture_output=True)
        count, quality, size = map(int, subprocess.run([str(work/'p.exe')], check=True, capture_output=True,
                                                       text=True).stdout.split())
    finally:
        import shutil
        shutil.rmtree(work)
    assert (count, quality, size) == (4 * m.SAMPLE_WORD, 4 * m.QUALITY_WORD, 656), (count, quality, size)
    print(f'descriptor layout: SampleDesc.Count at byte {count}, Quality at {quality}, size {size}')


def record(samples, cube_low=0x105):
    words = [0] * 164
    words[4], words[8] = 64, 96          # VS / PS bytecode lengths
    words[144], words[145] = 1, 11       # one R16G16B16A16_UNORM target
    words[m.SAMPLE_WORD] = samples or 1
    return dict(native=dict(words=words, inputs=[]), key='0' * 16, vs='1' * 16,
                fp=dict(sha256='a' * 64), state=dict(cube=cube_low | (samples << 16)))


def synthetic():
    vs, ps = b'DXBC' + bytes(60), b'DXBC' + bytes(range(92))
    root = 0x1234567890ABCDEF
    assert m.retarget(record(0), 8) is None, 'single-sample records stay'
    assert m.retarget(record(8), 8) is None, 'already at the count'
    base = record(2)
    keys = {}
    for n in (1, 2, 4, 8):
        moved = m.retarget(base, n) if n != 2 else copy.deepcopy(base)
        assert moved['native']['words'][m.SAMPLE_WORD] == n
        assert moved['state']['cube'] == 0x105 | ((n if n > 1 else 0) << 16)
        keys[n] = native_key(moved, vs, ps, root)
    assert len(set(keys.values())) == 4, 'each count is its own pipeline'
    assert base['native']['words'][m.SAMPLE_WORD] == 2 and base['state']['cube'] == 0x20105, 'source untouched'
    back = m.retarget(m.retarget(base, 8), 2)
    assert native_key(back, vs, ps, root) == keys[2] and back == base, 'only the count enters the key'
    bad = record(4)
    bad['native']['words'][m.SAMPLE_WORD] = 2
    try:
        m.retarget(bad, 8)
        raise AssertionError('descriptor/key disagreement accepted')
    except ValueError:
        pass
    for wrong in (0, 3, 16):
        try:
            m.retarget(base, wrong)
            raise AssertionError('bad count accepted')
        except ValueError:
            pass
    print('re-targeting: counts 1/2/4/8, key bits, descriptor word and refusals checked')


def membership():
    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        (d/'race-v1.txt').write_text('a\nb\nc\nd\n', encoding='ascii')
        (d/'menu-v1.txt').write_text('c\n', encoding='ascii')
        for k in ('A', 'b', 'C', 'd'):
            (d/f'pso_{k}.recipe').write_bytes(b'x')
        counts = m.stage_membership(d, {'a': 'A', 'c': 'C', 'd': 'A'})
        assert (d/'race-v1.txt').read_text() == 'A\nb\nC\n', (d/'race-v1.txt').read_text()
        assert (d/'menu-v1.txt').read_text() == 'C\n'
        assert counts['race'] == dict(before=4, after=3, retargeted=3)
    print('membership: replaced in order, de-duplicated, recipe-checked')


def real(report_path, translation):
    import os
    from native_pipeline_key import root_signature_hash
    os.environ.setdefault('GT5P_PREPARE_HASH_LIBRARY', r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue'
                          r'\Tourline-Prologue\out\preparer\dist\GT5P-Prepare\cache_hash.dll')
    report = json.loads(Path(report_path).read_text(encoding='utf-8'))
    recs = m.player_records(report, translation, Path(report_path).parent/'shadercache', root_signature_hash())
    print(f'real preparation ({translation}): {len(recs)} multisampled records reproduce their native keys')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--report', type=Path)
    ap.add_argument('--translation', default='default')
    a = ap.parse_args()
    layout()
    synthetic()
    membership()
    if a.report:
        real(a.report, a.translation)


if __name__ == '__main__':
    main()
