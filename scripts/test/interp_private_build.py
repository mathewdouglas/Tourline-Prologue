"""Private gt5p.exe with the shader-interpreter overlay on the D3D12 backend.

Applies the current local ps3recomp patch, then patches/ps3recomp-shader-interp.patch,
compiles that backend, and relinks against the read-only reference objects.
Does not assert the runtime working tree matches an older baseline: that tree
is dirty. Headers the overlay adds sit next to the patched .c so quoted
includes resolve there. The reference ninja -I paths still supply the rest.

Run from an x64 VS environment. The engine link is heavy: call this through
run_locked.py. Prints the exe path on stdout.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
RUNTIME = Path(os.environ.get(
    "GT5P_RUNTIME", r"C:\GT5P-CI\tourline-runtime-cache\d2be355a7fe73c59750f"))
REFERENCE = Path(os.environ.get(
    "GT5P_REFERENCE_BUILD",
    r"C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\build"))


def apply_sources(tree: Path) -> Path:
    video = tree / "libs" / "video"
    video.mkdir(parents=True)
    name = "libs/video/rsx_d3d12_backend.c"
    original = subprocess.check_output(["git", "-C", str(RUNTIME), "show", "HEAD:" + name])
    subprocess.run(["git", "init", "-q", str(tree)], check=True)
    subprocess.run(["git", "-C", str(tree), "config", "core.autocrlf", "false"], check=True)
    (tree / name).parent.mkdir(parents=True, exist_ok=True)
    (tree / name).write_bytes(original)
    subprocess.run(["git", "-C", str(tree), "apply", "--whitespace=nowarn",
                    "--include=" + name, "--include=libs/video/rsx_offline_batch.h",
                    str(ROOT / "patches" / "ps3recomp-4e8f3ca8-local.patch")], check=True)
    subprocess.run(["git", "-C", str(tree), "apply", "--whitespace=nowarn",
                    str(ROOT / "patches" / "ps3recomp-shader-interp.patch")], check=True)
    # Quoted includes search the source directory first. The typecheck used the
    # private post-local-patch headers, not the dirty runtime working tree.
    scratch_video = ROOT / "scratch" / "runtime-src" / "libs" / "video"
    for header in scratch_video.glob("*.h"):
        target = video / header.name
        if not target.exists():
            shutil.copyfile(header, target)
    backend = tree / name
    for extra in ("rsx_fp_interp.h", "rsx_fp_interp_hlsl.inc", "rsx_fp_interp_backend.inc"):
        if not (video / extra).is_file():
            raise SystemExit("overlay did not add " + extra)
    return backend


def compile_backend(backend: Path, objects: Path) -> Path:
    obj = r"ps3recomp\CMakeFiles\ps3recomp_runtime.dir\libs\video\rsx_d3d12_backend.c.obj"
    command = subprocess.check_output(
        ["ninja", "-t", "commands", obj], cwd=REFERENCE, text=True).splitlines()[-1]
    runtime_src = str(RUNTIME / "libs" / "video" / "rsx_d3d12_backend.c")
    if runtime_src not in command:
        raise SystemExit("ninja command does not name the runtime backend")
    (objects / "libs" / "video").mkdir(parents=True)
    command = command.replace(runtime_src, str(backend))
    command = command.replace(r"ps3recomp\CMakeFiles\ps3recomp_runtime.dir", str(objects))
    if " -c -- " not in command:
        raise SystemExit("unexpected compile command")
    command = command.replace(" -c -- ", " /D_CRT_SECURE_NO_WARNINGS /W0 -c -- ")
    subprocess.run(command, cwd=objects, check=True)
    out = objects / "libs" / "video" / "rsx_d3d12_backend.c.obj"
    if not out.is_file():
        raise SystemExit("backend object missing")
    return out


def link_engine(fresh: Path, backend_obj: Path) -> Path:
    source = REFERENCE.parent / "src" / "gt5p_present.cpp"
    obj = r"CMakeFiles\gt5p.dir\src\gt5p_present.cpp.obj"
    command = subprocess.check_output(
        ["ninja", "-t", "commands", obj], cwd=REFERENCE, text=True).splitlines()[-1]
    if str(source) not in command:
        raise SystemExit("present compile command does not name the reference source")
    objects = fresh / "present-objects"
    (objects / "src").mkdir(parents=True)
    command = command.replace(str(source), str(ROOT / "src" / "gt5p_present.cpp"))
    command = command.replace(r"CMakeFiles\gt5p.dir", str(objects))
    subprocess.run(command, cwd=fresh, check=True)
    lines = (REFERENCE / "build.ninja").read_text(encoding="utf-8", errors="replace").splitlines()
    link = next(i for i, line in enumerate(lines) if line.startswith("build gt5p.exe: "))
    inputs = lines[link].split("Release ", 1)[1].split(" | ")[0].split()
    libraries = next(line.split(" = ", 1)[1] for line in lines[link + 1:link + 15]
                     if line.startswith("  LINK_LIBRARIES = ")).split()
    runtime = fresh / "install" / "runtime"
    runtime.mkdir(parents=True)
    linker = r"C:\Program Files\LLVM\bin\lld-link.exe"
    args = [linker, "/nologo", "/machine:x64", "/INCREMENTAL:NO", "/subsystem:console"]
    args += [str(objects / "src" / "gt5p_present.cpp.obj") if item == obj else str(REFERENCE / item)
             for item in inputs]
    args.append(str(backend_obj))
    args += [str(REFERENCE / name) if "\\" in name else name for name in libraries]
    exe = runtime / "gt5p.exe"
    args += ["/out:" + str(exe), "/pdb:" + str(fresh / "gt5p.pdb"),
             "/implib:" + str(fresh / "gt5p.lib")]
    subprocess.run(args, cwd=fresh, check=True)
    for dll in REFERENCE.glob("*.dll"):
        shutil.copyfile(dll, runtime / dll.name)
    return exe


def install_worktree(exe: Path) -> Path:
    dest = ROOT / "build"
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(exe, dest / "gt5p.exe")
    for dll in exe.parent.glob("*.dll"):
        shutil.copyfile(dll, dest / dll.name)
    return dest / "gt5p.exe"


def main() -> None:
    if os.environ.get("VSCMD_ARG_TGT_ARCH", "").lower() != "x64":
        raise SystemExit("Use an x64 VS environment")
    fresh = ROOT / "scratch" / "interp-engine"
    if fresh.exists():
        shutil.rmtree(fresh)
    fresh.mkdir(parents=True)
    backend = apply_sources(fresh / "tree")
    obj = compile_backend(backend, fresh / "backend-objects")
    exe = link_engine(fresh, obj)
    installed = install_worktree(exe)
    print(installed)


if __name__ == "__main__":
    main()
