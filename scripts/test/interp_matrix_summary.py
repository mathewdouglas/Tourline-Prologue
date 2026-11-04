"""Summarize interpreter probe runs: python interp_matrix_summary.py <series> (reads scratch/interp-runs, scratch/pv)."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def last(pattern, text):
    m = re.findall(pattern, text, re.M)
    return m[-1] if m else None


def main() -> None:
    series = sys.argv[1]
    runs = sorted((ROOT / "scratch" / "interp-runs").glob(series + "-*"))
    print("run | frametest | omissions replay vp/fp, record vp | interp draws/fallback/gap | pso new/block_ms/max | wait/disk hit/save/rej | last gpu windows (ms)")
    for run in runs:
        tag = run.name
        probe = (run / "probe.log").read_text(errors="replace") if (run / "probe.log").is_file() else ""
        err = ROOT / "scratch" / "pv" / (tag + ".err")
        text = err.read_text(errors="replace") if err.is_file() else ""
        ft = last(r"FrameTest: (.*)", probe)
        pend = last(r"\[interp-pending\] replay_vp=(\d+) replay_fp=(\d+) record_vp=(\d+)", text)
        it = last(r"\[interp\] draws (\d+) fallback (\d+) reject (\d+) gap (\d+)", text)
        pso = last(r"\[interp-pso\] block_ms (\d+) block_max_ms (\d+) queued (\d+) queue_full (\d+) wait_draws (\d+) disk_hit (\d+) disk_save (\d+) disk_reject (\d+)", text)
        pn = last(r"pso (\d+) \(new ms total (\d+) max (\d+)\)", text)
        gpu = re.findall(r"presents=(\d+).*gpu ([\d.]+) ms avg ([\d.]+) max", text)[-4:]
        page = last(r"page at ([\d.]+) s", probe)
        print(f"{tag} | {ft or ('page at ' + page + ' s' if page else 'n/a')} | "
              f"{'/'.join(pend) if pend else '-'} | "
              f"{(it[0] + '/' + it[1] + '/' + it[3]) if it else '-'} | "
              f"{(pn[0] + '/' + pso[0] + '/' + pso[1]) if pn and pso else '-'} | "
              f"{('/'.join(pso[4:8])) if pso else '-'} | "
              f"{'; '.join(g[0] + 'p ' + g[1] + '/' + g[2] for g in gpu)}")


if __name__ == "__main__":
    main()
