"""Run under run_locked.py from an x64 VS environment.

Compile the original synthetic WARP test and our private runtime's decompiler;
only private scratch outputs are written. This is a vertex-output comparison,
not a rasterization, catalogue coverage or whole-game correctness claim.
"""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = ROOT / "scratch" / "runtime-src"


def main() -> None:
    out = ROOT / "scratch" / "vp-warp"
    out.mkdir(parents=True, exist_ok=True)
    exe = out / "vp_interp_warp.exe"
    subprocess.run([
        r"C:\Program Files\LLVM\bin\clang-cl.exe", "/nologo", "/TC", "/O2", "/MD",
        "/D_CRT_SECURE_NO_WARNINGS", "/I" + str(RUNTIME / "include"),
        "/I" + str(RUNTIME / "libs" / "video"), "/Fo" + str(out) + "\\",
        "/Fe" + str(exe), str(ROOT / "scripts" / "test" / "vp_interp_warp.c"),
        str(RUNTIME / "libs" / "video" / "rsx_vp_decompiler.c"),
        "/link", "d3d11.lib", "d3dcompiler.lib",
    ], cwd=out, check=True)
    subprocess.run([str(exe)], check=True)


if __name__ == "__main__":
    main()
