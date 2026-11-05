"""Regenerate patches/ps3recomp-shader-interp.patch from the private working tree.

scratch/interp-base holds the D3D12 backend after patches/ps3recomp-4e8f3ca8-local.patch
(the baseline). scratch/runtime-src/libs/video holds the edited backend plus the
overlay's own files. The diff is written with LF endings and `a/libs/video/...`
paths so interp_private_build.py can `git apply` it after the main patch.

Usage: python scripts/test/interp_make_patch.py [--check]
  --check   compare against the committed patch and exit 1 when they differ
"""
import os
import pathlib
import shutil
import stat
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = ROOT / "scratch" / "interp-base" / "libs" / "video"
WORK = ROOT / "scratch" / "runtime-src" / "libs" / "video"
PATCH = ROOT / "patches" / "ps3recomp-shader-interp.patch"
TMP = ROOT / "scratch" / "patch-gen"
EDITED = ["rsx_d3d12_backend.c"]
ADDED = ["rsx_fp_interp.h", "rsx_fp_interp_hlsl.inc", "rsx_fp_interp_backend.inc",
         "rsx_vp_interp.h", "rsx_vp_interp_hlsl.inc", "rsx_vp_interp_backend.inc"]


def _force_remove(func, path, exc):
    os.chmod(path, stat.S_IWRITE)
    func(path)


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", "-c", "core.autocrlf=false", "-c", "core.safecrlf=false",
                                    "-C", str(TMP)] + list(args))


def main() -> int:
    if TMP.exists():
        shutil.rmtree(TMP, onerror=_force_remove)
    video = TMP / "libs" / "video"
    video.mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(TMP)], check=True)
    git("config", "user.email", "x@example.invalid")
    git("config", "user.name", "x")
    for name in EDITED:
        shutil.copyfile(BASE / name, video / name)
    git("add", "-A")
    git("commit", "-q", "-m", "base")
    for name in EDITED + ADDED:
        shutil.copyfile(WORK / name, video / name)
    git("add", "-A")
    patch = git("diff", "--cached", "--no-color", "--src-prefix=a/", "--dst-prefix=b/")
    if "--check" in sys.argv:
        same = PATCH.is_file() and PATCH.read_bytes() == patch
        print("patch matches" if same else "patch differs")
        return 0 if same else 1
    PATCH.write_bytes(patch)
    print(f"{PATCH} ({len(patch)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
