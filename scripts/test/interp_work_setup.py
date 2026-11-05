"""Create scratch/interp-base and scratch/runtime-src for interp_make_patch.py.

interp-base holds the D3D12 backend after patches/ps3recomp-4e8f3ca8-local.patch.
runtime-src/libs/video holds that backend plus the overlay (the editing copy).
Run once per checkout, then edit runtime-src and regenerate the overlay with
interp_make_patch.py. Reads the runtime source tree; writes only under scratch/.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import interp_private_build as b  # noqa: E402

ROOT = b.ROOT


def main() -> None:
    base = ROOT / "scratch" / "interp-base"
    work = ROOT / "scratch" / "runtime-src"
    for d in (base, work):
        if d.exists():
            shutil.rmtree(d)
    name = "libs/video/rsx_d3d12_backend.c"
    for tree, with_overlay in ((base, False), (work, True)):
        tree.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(tree)], check=True)
        subprocess.run(["git", "-C", str(tree), "config", "core.autocrlf", "false"], check=True)
        # HEAD of the runtime source (its working tree is dirty): libs/video and
        # include, then the main patch for those paths. The video headers are
        # what the overlay's offline tools and the backend compile against.
        names = subprocess.check_output(["git", "-C", str(b.RUNTIME), "ls-tree", "-r", "--name-only", "HEAD",
                                         "libs/video", "include"], text=True).splitlines()
        for n in names:
            dest = tree / n
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(subprocess.check_output(["git", "-C", str(b.RUNTIME), "show", "HEAD:" + n]))
        b.apply_patch(tree, ROOT / "patches" / "ps3recomp-4e8f3ca8-local.patch",
                      ["libs/video/*", "include/*"])
        if with_overlay:
            b.apply_patch(tree, ROOT / "patches" / "ps3recomp-shader-interp.patch")
    # keep only what interp_make_patch.py and the builder read
    for tree in (base, work):
        shutil.rmtree(tree / ".git", ignore_errors=True)
    print("ok")


if __name__ == "__main__":
    main()
