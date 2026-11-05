"""One isolated badge probe to the dealership. Invoke through run_locked.py.

Copies save data (excluding the hidden movie contents) and the ELF to a new scratch root,
launches the private engine with a private shader cache and records which shader badge
("Compiling shaders" / "Loading shaders") is up (badge_dealer.ps1). The same cache can be
named again to learn recipes in a first run and preload them in the next one.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
GAME = Path(r"C:\Users\GGPC\Dev\Recomps\GT5P")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tag", required=True)
    p.add_argument("--cache", required=True, type=Path)
    p.add_argument("--engine", required=True, type=Path)
    p.add_argument("--settle", type=int, default=25)
    p.add_argument("--env", action="append", default=[], metavar="NAME=VALUE")
    a = p.parse_args()
    cache = a.cache.resolve()
    if not cache.is_relative_to((ROOT / "scratch").resolve()):
        p.error("cache must be under this worktree's scratch")
    if not a.tag or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in a.tag):
        p.error("tag must contain only letters, numbers, hyphens and underscores")
    owned = ROOT / "scratch" / "rc024-runs" / a.tag
    owned.mkdir(parents=True, exist_ok=False)
    game = owned / "game-root"
    (game / "input").mkdir(parents=True)
    shutil.copyfile(GAME / "input" / "EMAIN.ELF", game / "input" / "EMAIN.ELF")
    shutil.copytree(GAME / "gamedata", game / "gamedata", ignore=shutil.ignore_patterns("contents"))
    cache.mkdir(parents=True, exist_ok=True)
    print(f"private root={game}; cache entries before launch={sum(1 for _ in cache.iterdir())}", flush=True)
    env = ["PS3_VERBOSE=0", "GT5P_NO_SETTINGS=1", "FS_HIDE=grim/file/contents",
           "GT5P_ROOT=" + str(game), "PS3_VFS_ROOT=" + str(game),
           "GT5P_GAME_DIR=" + str(GAME / "input" / "pkg") + "/",
           "RSX_SHADER_CACHE=" + str(cache), "RSX_SHADER_ASYNC=1", "RSX_SSAA=0"] + a.env
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
            str(ROOT / "scripts" / "test" / "badge_dealer.ps1"), "-Tag", a.tag, "-Settle", str(a.settle),
            "-Engine", str(a.engine.resolve()), "-GameRoot", str(game), "-OutputDirectory", str(owned)]
    try:
        result = subprocess.run(args + env, cwd=ROOT, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, errors="replace")
    finally:
        # The private game root is a copy of the save; keep only logs/shots.
        if not os.environ.get("RC024_KEEP_ROOT"):
            shutil.rmtree(game, ignore_errors=True)
    (owned / "probe.log").write_text(result.stdout, encoding="utf-8")
    print(result.stdout, end="", flush=True)
    result.check_returncode()


if __name__ == "__main__":
    main()
