"""One-line-per-run summary of hitch_capture routes (read-only).

For each route directory: FrameTest line, grid-to-end display intervals (excluding screenshot overlap),
counts over 33/50/100 ms, the worst intervals, and texture allocation totals inside >50 ms intervals.

Usage: hitch_summary.py <route dir>... [--json out.json]
"""
import argparse
import json
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from hitch_list import intervals, load  # noqa: E402


def summarize(route):
    route = Path(route)
    tag = route.name
    trace = route / f'{tag}.trace.csv'
    window = json.load(open(route / f'{tag}.window.json', encoding='utf-8-sig'))
    shots = [(s['start_ms'], s['end_ms']) for s in json.load(open(route / f'{tag}.shots.json', encoding='utf-8-sig'))]
    grid = window['grid_observed_ms']
    items = [i for i in intervals(load(trace)) if i['end_unix_ms'] >= grid]
    clean = []
    for it in items:
        start = it['end_unix_ms'] - it['interval_ms']
        if not any(s < it['end_unix_ms'] and e > start for s, e in shots) and it['foreground']:
            clean.append(it)
    over = lambda ms: [i for i in clean if i['interval_ms'] > ms]  # noqa: E731
    big = over(50)
    log = (route / 'route.log').read_text(errors='replace')
    ft = re.findall(r'FrameTest: ([^\r\n]+)', log)
    worst = sorted((round(i['interval_ms']) for i in clean), reverse=True)[:5]
    ints = sorted(i['interval_ms'] for i in clean)
    return dict(route=tag, frame_test=ft[-1] if ft else None, intervals=len(clean),
                p99=round(ints[int(len(ints) * 0.99) - 1], 1) if ints else None,
                over33=len(over(33.4)), over50=len(big), over100=len(over(100)), worst=worst,
                alloc_ms_in_over50=round(sum(i['tex_alloc_ms'] for i in big)),
                allocs_in_over50=int(sum(i['tex_allocs'] for i in big)),
                allocs_total=int(sum(i['tex_allocs'] for i in clean)),
                alloc_ms_total=round(sum(i['tex_alloc_ms'] for i in clean)),
                pso_ms_in_over50=round(sum(i['pso_ms'] for i in big)),
                record_ms_in_over50=round(sum(i['record_ms'] for i in big)),
                tex_ms_in_over50=round(sum(i['tex_ms'] for i in big)),
                batch_ms_in_over50=round(sum(i['batch_ms'] for i in big)),
                excess_over50_ms=round(sum(i['interval_ms'] - 16.683 for i in big)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('routes', nargs='+')
    ap.add_argument('--json')
    a = ap.parse_args()
    rows = [summarize(r) for r in a.routes]
    for r in rows:
        print(json.dumps(r))
    if a.json:
        json.dump(rows, open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
