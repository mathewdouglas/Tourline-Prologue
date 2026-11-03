"""Resolve the verified starter's VP inputs for the private WARP comparison.

Run under run_locked.py. Original inputs are read-only; resolved programs stay
under scratch, never in the repository or release package.
"""
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import game_volume
import pipeline_asset_map


def main() -> None:
    meta = ROOT / "assets" / "pipeline-templates" / "gt5p-disc-v2"
    locations = pipeline_asset_map.read(meta / "player-map.json")
    wanted = {(r["stage"], r["id"], r["size"]) for r in locations["records"] if r["stage"] == "vp"}
    game = Path(r"C:\Users\GGPC\Dev\Recomps\GT5P")
    os.environ.setdefault("GT5P_PREPARE_VOLUME_LIBRARY", str(Path(
        r"C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare\volume_reader.dll")))
    programs, _, stats = game_volume.resolve(locations, game_volume.read(meta / "volume-map.json"),
        game / "input" / "pkg" / "USRDIR" / "GT.VOL", game / "input" / "EMAIN.ELF", wanted=wanted)
    out = ROOT / "scratch" / "vp-programs"
    out.mkdir(parents=True, exist_ok=False)
    for identity, code in programs.items():
        (out / (identity + ".vp")).write_bytes(code)
    (out / "summary.json").write_text(json.dumps(stats, indent=2), encoding="utf-8")
    print(f"resolved {len(programs)}/{len(wanted)} verified vertex programs to private scratch", flush=True)


if __name__ == "__main__":
    main()
