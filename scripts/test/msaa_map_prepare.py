"""Phase 223: run the MSAA re-target stage on a completed attribution preparation (scratch/hitch/<name>).

Mirrors scripts/player_prepare.py after the default/translation preparation: re-targeted native pipelines,
the fast lookup table (with the re-targeted rows) and the menu/race lists. Invoke through run_locked.py.
Usage: msaa_map_prepare.py --name prep-uw8 --translation ultrawide-native --msaa 8 --engine <gt5p.exe>
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'scripts'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--name', required=True)
    ap.add_argument('--translation', choices=('default', 'ultrawide-native', 'native-scaled'), default='default')
    ap.add_argument('--msaa', type=int, choices=(1, 2, 4, 8), required=True)
    ap.add_argument('--engine', type=Path, required=True)
    a = ap.parse_args()
    home = ROOT/'scratch/hitch'
    output = home/a.name
    game = home/('msaa-game-'+a.name)
    ref = Path(r'C:\actions-runner-tourline-prologue\_work\Tourline-Prologue\Tourline-Prologue\out\preparer\dist\GT5P-Prepare')
    os.environ['GT5P_PREPARE_HASH_LIBRARY'] = str(ref/'cache_hash.dll')
    (game/'input').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(r'C:\Users\GGPC\Dev\Recomps\GT5P/input/EMAIN.ELF'), game/'input/EMAIN.ELF')
    import msaa_pipeline_map, fast_lookup_table
    from shader_reconstruct import run_offline
    engine = a.engine.resolve()
    report = json.loads((output/'report.json').read_text(encoding='utf-8'))
    begin, last = time.monotonic(), [0.0]

    def progress(phase, counts):
        if time.monotonic()-last[0] > 5:
            print(round(time.monotonic()-begin, 1), phase, counts, flush=True)
            last[0] = time.monotonic()
    try:
        result = msaa_pipeline_map.prepare(output, engine, game, report, a.translation, a.msaa, run_offline, progress)
        print('msaa:', json.dumps(msaa_pipeline_map.compact(result)), flush=True)
        lookup = fast_lookup_table.write_for_preparation(output, engine, report,
                                                         extra_rows={a.translation: result['lookup_rows']})
        print('fast lookup:', json.dumps(lookup), flush=True)
        membership = msaa_pipeline_map.stage_membership(output/'shadercache/warmup-v1', result['mapping'])
        print('membership:', json.dumps(membership), flush=True)
    finally:
        shutil.rmtree(game)
    print(json.dumps(dict(seconds=round(time.monotonic()-begin, 1))), flush=True)


if __name__ == '__main__':
    main()
