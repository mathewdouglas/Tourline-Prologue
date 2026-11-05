"""Build the fragment-interpreter harness and run one stage of it.

compile and encode do not draw. compare draws on WARP and must be started
under the test lock by the caller.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = ROOT / "scratch" / "fp-interp"
RT = ROOT / "scratch" / "runtime-src"
CLANG = Path(r"C:\Program Files\LLVM\bin\clang-cl.exe")
CATALOGUE = Path(r"C:\Users\GGPC\Dev\Recomps\GT5P\shadercache\library-v1\all")


def build() -> Path:
    SCRATCH.mkdir(parents=True, exist_ok=True)
    exe = SCRATCH / "fp_interp_harness.exe"
    cmd = [
        str(CLANG), "/nologo", "/TC", "/O2", "/MD", "/W0", "/D_CRT_SECURE_NO_WARNINGS",
        "/I" + str(RT / "include"),
        "/I" + str(RT / "libs" / "video"),
        "/Fo" + str(SCRATCH) + "\\",
        "/Fe" + str(exe),
        str(ROOT / "scripts" / "test" / "fp_interp_harness.c"),
        str(RT / "libs" / "video" / "rsx_fp_decompiler.c"),
        "/link", "d3d12.lib", "dxgi.lib", "d3dcompiler.lib", "uuid.lib",
    ]
    subprocess.check_call(cmd)
    return exe


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "compile"
    exe = build()
    if mode == "compile":
        return subprocess.call([str(exe), "compile", str(SCRATCH)])
    if mode == "encode":
        cat = sys.argv[2] if len(sys.argv) > 2 else str(CATALOGUE)
        return subprocess.call([str(exe), "encode", cat])
    if mode == "compare":
        cat = sys.argv[2] if len(sys.argv) > 2 else str(CATALOGUE)
        summary = SCRATCH / "compare.txt"
        return subprocess.call([str(exe), "compare", cat, str(SCRATCH), str(summary)])
    print("usage: fp_interp_warp.py compile|encode|compare", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
