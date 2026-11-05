"""One isolated interpreter game probe. Invoke through run_locked.py.

Copies save data (excluding the hidden movie contents) and the ELF to a new
scratch root; the original disc folder is mapped only as the game's input.
--cache must explicitly name a private scratch cache. A new cache starts empty,
including generic interpreter DXBC. Results and screenshots stay in scratch.
"""
import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
GAME = Path(r"C:\Users\GGPC\Dev\Recomps\GT5P")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("route", choices=("dealer", "race"))
    p.add_argument("--tag", required=True)
    p.add_argument("--cache", required=True, type=Path)
    p.add_argument("--fp", choices=("0", "1", "force"), default="0")
    p.add_argument("--vp", choices=("0", "1", "force"), default="0")
    p.add_argument("--seconds", type=int)
    p.add_argument("--track", choices=("HighSpeedRing", "Daytona", "FujiSpeedwayF"), default="HighSpeedRing")
    p.add_argument("--frame-test", action="store_true")
    p.add_argument("--ab", action="store_true")
    p.add_argument("--cold", action="store_true", help="require a completely empty cache")
    p.add_argument("--paired-prewarm", action="store_true", help="interpret both stages together while either is pending; precreate starter native classes")
    p.add_argument("--engine", type=Path, default=ROOT / "scratch" / "interp-engine" / "install" / "runtime" / "gt5p.exe",
                   help="private engine to launch (default: the latest private build)")
    p.add_argument("--env", action="append", default=[], metavar="NAME=VALUE", help="extra game environment variable")
    p.add_argument("--menu-delay", type=int, help="seconds to wait before menu navigation (default 30 with --cold, else 0)")
    p.add_argument("--settle", type=int, help="dealer settle seconds (default 0 with --cold, else 15)")
    p.add_argument("--gamma-read-off", action="store_true", help="diagnostic: bypass only interpreter texture gamma decoding")
    a = p.parse_args()
    cache = a.cache.resolve()
    if not cache.is_relative_to((ROOT / "scratch").resolve()):
        p.error("cache must be under this worktree's scratch")
    if a.cold and cache.exists() and any(cache.iterdir()):
        p.error("--cold requires an empty cache, including generic interpreter DXBC")
    if not a.tag or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_" for c in a.tag):
        p.error("tag must contain only letters, numbers, hyphens and underscores")
    owned = ROOT / "scratch" / "interp-runs" / a.tag
    owned.mkdir(parents=True, exist_ok=False)
    game = owned / "game-root"
    (game / "input").mkdir(parents=True)
    shutil.copyfile(GAME / "input" / "EMAIN.ELF", game / "input" / "EMAIN.ELF")
    shutil.copytree(GAME / "gamedata", game / "gamedata", ignore=shutil.ignore_patterns("contents"))
    seed = hashlib.sha256()
    for path in sorted((game / "gamedata").rglob("*")):
        if path.is_file():
            seed.update(path.relative_to(game).as_posix().encode("utf-8") + b"\0")
            with path.open("rb") as stream:
                seed.update(hashlib.file_digest(stream, "sha256").digest())
    (owned / "save-seed.sha256").write_text(seed.hexdigest() + "\n", encoding="ascii")
    cache.mkdir(parents=True, exist_ok=True)
    print(f"private root={game}; cache entries before launch={sum(1 for _ in cache.iterdir())}; save seed={seed.hexdigest()}", flush=True)
    env = ["PS3_VERBOSE=0", "GT5P_NO_SETTINGS=1", "FS_HIDE=grim/file/contents",
           "GT5P_ROOT=" + str(game), "PS3_VFS_ROOT=" + str(game),
           "GT5P_GAME_DIR=" + str(GAME / "input" / "pkg") + "/",
           "RSX_SHADER_CACHE=" + str(cache), "RSX_SHADER_INTERP=" + a.fp,
           "RSX_SHADER_INTERP_VP=" + a.vp, "RSX_SSAA=0", "GT5P_PRESENT_PROF=1",
           "RSX_SHADER_INTERP_STATS=1"]
    if a.paired_prewarm:
        if a.fp == "0" or a.vp == "0":
            p.error("--paired-prewarm requires both stage switches")
        env += ["RSX_SHADER_INTERP_PAIR=1", "RSX_SHADER_INTERP_PREWARM=1"]
    if a.gamma_read_off:
        env += ["RSX_SHADER_INTERP_GAMMA_READ=0"]
    env += a.env
    if a.ab:
        dumps = owned / "dumps"
        dumps.mkdir()
        env += ["RSX_SHADER_INTERP_AB=1", "CELLMARK_DUMP=12", "CELLMARK_DUMP_SKIP=20",
                "CELLMARK_DUMP_MINDRAWS=2000" if a.route == "dealer" else "CELLMARK_DUMP_MINDRAWS=1000",
                "CELLMARK_DUMP_DIR=" + str(dumps)]
    args = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File"]
    if a.route == "dealer":
        args += [str(ROOT / "scripts" / "test" / "winshot.ps1"), "-Tag", a.tag,
                 "-Settle", str(a.settle if a.settle is not None else (0 if a.cold else 15)), "-Shots", "12" if a.cold else "1", "-Gap", "1",
                 "-Engine", str(a.engine.resolve()),
                 "-GameRoot", str(game), "-TimeoutSec", "240", "-MenuDelaySec", str(a.menu_delay if a.menu_delay is not None else (30 if a.cold else 0))]
    else:
        args += [str(ROOT / "scripts" / "test" / "race.ps1"), "-Track", a.track,
                 "-Tag", a.tag, "-Seconds", str(a.seconds or (60 if a.frame_test else 35)),
                 "-SampleDelay", "12", "-RaceShots", "12",
                 "-Engine", str(a.engine.resolve()),
                 "-GameRoot", str(game), "-GridTimeoutSec", "240", "-MenuDelaySec", str(a.menu_delay if a.menu_delay is not None else (30 if a.cold else 0))]
        if a.frame_test:
            args += ["-FrameTest", "-SampleDelay", "45", "-RequireForeground", "-IntroShots"]
            # PowerShell accepts each named parameter only once.
            i = args.index("-SampleDelay")
            del args[i:i + 2]
    with (owned / "probe.log").open("w", encoding="utf-8") as log:
        try:
            result = subprocess.run(args + env, cwd=ROOT, stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT, text=True, errors="replace")
        finally:
            # The private game root is a ~2 GB copy of the save; keep only logs/shots/dumps.
            # RSX_INTERP_KEEP_ROOT=1 keeps it. (A matrix of runs filled the volume without this.)
            if not os.environ.get("RSX_INTERP_KEEP_ROOT"):
                shutil.rmtree(game, ignore_errors=True)
        log.write(result.stdout)
        print(result.stdout, end="", flush=True)
        result.check_returncode()
        if a.route == "dealer" and "page at " not in result.stdout:
            raise SystemExit("dealership was not reached; probe rejected")


if __name__ == "__main__":
    main()
