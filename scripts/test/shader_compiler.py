"""Phase 231 shader compiler selection for preparation (scripts/shader_compiler.py). Needs third_party/dxc.

1. RSX_SHADER_COMPILER: unset/dxc -> dxc, fxc -> fxc, anything else refused; RSX_SHADER_INTERP=1 -> fxc (the
   engine does the same). Targets vs_6_0/ps_6_0 against vs_5_0/ps_5_0, and source keys differ by target.
2. DXC (the pinned third_party/dxc/dxcompiler.dll): a vertex and a pixel shader compile to a signed DXIL container
   (DXBC magic, DXIL and HASH parts, no unsigned zero hash); the same text gives the same bytes twice and from a
   second compiler object; a vector ?: compiles (HLSL 2018 mode, as the engine asks); errors return text; a shader
   with the engine-only resource arrays is refused; a missing DLL is a clear error.
3. NativeCompiler (the helper's vertex compiler) uses DXC with RSX_SHADER_COMPILER=dxc and FXC with RSX_SHADER_COMPILER=fxc.
"""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import shader_compiler as sc  # noqa: E402
from native_pipeline_key import source_key  # noqa: E402

VS = b"""struct O { float4 p : SV_Position; float4 c : COLOR0; };
cbuffer C : register(b0) { float4 k[4]; };
O main(uint id : SV_VertexID) { O o; float4 v = float4(id, id * 2, 0, 1);
  o.p = float4(dot(v, k[0]), dot(v, k[1]), dot(v, k[2]), dot(v, k[3]));
  o.c = abs(v) > 0.5 ? v : (float4)0; return o; }
"""
PS = b"""Texture2D t : register(t0); SamplerState s : register(s4);
float4 main(float4 p : SV_Position, float4 c : COLOR0) : SV_TARGET { return t.Sample(s, c.xy) * c; }
"""


def parts(code):
    count = int.from_bytes(code[28:32], 'little')
    out = {}
    for i in range(count):
        off = int.from_bytes(code[32 + 4 * i:36 + 4 * i], 'little')
        out[code[off:off + 4]] = code[off + 8:off + 8 + int.from_bytes(code[off + 4:off + 8], 'little')]
    return out


def selection():
    assert sc.mode({}) == 'dxc' and sc.mode({'RSX_SHADER_COMPILER': 'dxc'}) == 'dxc'
    assert sc.mode({'RSX_SHADER_COMPILER': 'fxc'}) == 'fxc'
    assert sc.mode({'RSX_SHADER_COMPILER': 'dxc', 'RSX_SHADER_INTERP': '1'}) == 'fxc'
    assert sc.mode({'RSX_SHADER_INTERP': '1'}) == 'fxc' and sc.mode({'RSX_SHADER_INTERP': '0'}) == 'dxc'
    for stage in ('RSX_SHADER_INTERP', 'RSX_SHADER_INTERP_VP'):
        for enabled in ('1', 'force', 'Force'):
            assert sc.mode({'RSX_SHADER_COMPILER': 'dxc', stage: enabled}) == 'fxc'
        for disabled in ('', '0', '2'):
            assert sc.mode({stage: disabled}) == 'dxc'
    for bad in ('', 'DXC', 'llvm'):
        try:
            sc.mode({'RSX_SHADER_COMPILER': bad})
            raise AssertionError('accepted ' + bad)
        except ValueError:
            pass
    assert sc.targets({'RSX_SHADER_COMPILER': 'dxc'}) == (b'vs_6_0', b'ps_6_0') and sc.targets({'RSX_SHADER_COMPILER': 'fxc'}) == (b'vs_5_0', b'ps_5_0')
    assert source_key(VS, b'vs_6_0') != source_key(VS, b'vs_5_0')
    from shader_coverage import fnv64
    assert source_key(VS, b'vs_6_0') == ((fnv64(VS + b'vs_6_0') ^ 0x2000) * 1099511628211) & 0xffffffffffffffff
    assert source_key(VS, b'vs_6_0') != (fnv64(VS + b'vs_6_0') * 1099511628211) & 0xffffffffffffffff
    assert sc.library({'GT5P_PREPARE_DXC_LIBRARY': 'x/y.dll'}) == Path('x/y.dll')
    print('selection: passed')


def dxc():
    one, two = sc.Dxc(), sc.Dxc()
    for source, target in ((VS, b'vs_6_0'), (PS, b'ps_6_0')):
        code, error = one.compile(source, target)
        assert code[:4] == b'DXBC' and not error, error
        p = parts(code)
        assert b'DXIL' in p and b'HASH' in p, list(p)
        assert code[4:20] != bytes(16), 'unsigned container (dxil.dll not used)'
        assert one.compile(source, target)[0] == code and two.compile(source, target)[0] == code, 'not deterministic'
    code, error = one.compile(b'float4 main() : SV_TARGET { return undefined_name; }', b'ps_6_0')
    assert not code and 'undefined_name' in error, error
    try:
        one.compile(b'SamplerState rsx_samp[16] : register(s0);' + PS, b'ps_6_0')
        raise AssertionError('resource array accepted')
    except ValueError:
        pass
    try:
        sc.Dxc(ROOT / 'scratch/no-such/dxcompiler.dll')
        raise AssertionError('missing DLL accepted')
    except ValueError as exc:
        assert 'not found' in str(exc)
    print('dxc: passed')


def native_compiler():
    from shader_reconstruct import NativeCompiler
    decoder = Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare\decoder.dll')
    if not decoder.is_file():
        print('native compiler: skipped (no reference decoder.dll)')
        return
    saved = os.environ.get('RSX_SHADER_COMPILER')
    try:
        os.environ['RSX_SHADER_COMPILER'] = 'dxc'
        c = NativeCompiler(decoder)
        assert c.dxc is not None and c.vertex_target == b'vs_6_0'
        os.environ['RSX_SHADER_COMPILER'] = 'fxc'
        c = NativeCompiler(decoder)
        assert c.dxc is None and c.vertex_target == b'vs_5_0'
    finally:
        if saved is None:
            os.environ.pop('RSX_SHADER_COMPILER', None)
        else:
            os.environ['RSX_SHADER_COMPILER'] = saved
    print('native compiler: passed')


if __name__ == '__main__':
    selection()
    dxc()
    native_compiler()
