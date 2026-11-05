"""List each long display interval of an RSX_HITCH_LOG trace with its per-interval stage costs.

Offscreen batches are summed into the following display batch (as frame_hitches.py does).
Counter columns that are cumulative in the trace are differenced. Read-only; prints a table
and optionally writes JSON. Times are relative to the window start (grid arrival) when a
window.json is given.

Usage: hitch_list.py <trace.csv> [--window w.json] [--shots s.json] [--min-ms 50] [--json out.json]
"""
import argparse
import csv
import json

# Per-batch (non-cumulative) millisecond stages in the trace.
STAGES = ('batch_ms', 'present_ms', 'wait_ms')
# Cumulative counters (differenced between display rows).
COUNTERS = ('tex_ms', 'pre_ms', 'srv_ms', 'pso_ms', 'record_ms', 'vtx_ms', 'vs_ms', 'cb_ms', 'tex_alloc_ms', 'tex_decode_ms', 'tex_allocs', 'up_allocs', 'uploads', 'upload_bytes', 'tex_hash_ms',
            'tex_map_ms', 'tex_copy_ms', 'tex_srv_ms', 'driver_calls', 'driver_us', 'cache_reads', 'cache_us',
            'shader_compiles', 'skip_fp', 'skip_vp', 'skip_record', 'demand_queued', 'demand_done')


def load(path):
    with open(path, newline='') as f:
        rows = list(csv.DictReader(f))
    if rows and rows[-1].get('sync_read_ms') in (None, ''):
        rows = rows[:-1]          # killed writer's unterminated tail
    return rows


def intervals(rows):
    out, acc, prev_present, prev_counts = [], {k: 0.0 for k in STAGES}, None, None
    for r in rows:
        for k in STAGES:
            acc[k] += float(r[k] or 0)
        acc['draws'] = acc.get('draws', 0) + int(float(r['draws'] or 0))
        if r['present'] != '1':
            continue
        t = float(r['unix_ms'])
        counts = {k: float(r[k] or 0) for k in COUNTERS}
        if prev_present is not None:
            item = dict(end_unix_ms=t, interval_ms=t - prev_present, foreground=r['foreground'] == '1',
                        gpu_previous_ms=float(r['gpu_previous_ms'] or 0), pending=float(r['pending'] or 0))
            item.update({k: round(v, 3) for k, v in acc.items()})
            # cumulative snapshots can restart (stage probes reset at startup): a drop counts the new value only
            item.update({k: round(counts[k] - prev_counts[k] if counts[k] >= prev_counts[k] else counts[k], 3) for k in COUNTERS})
            out.append(item)
        prev_present, prev_counts, acc = t, counts, {k: 0.0 for k in STAGES}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('trace')
    ap.add_argument('--window')
    ap.add_argument('--shots')
    ap.add_argument('--min-ms', type=float, default=50)
    ap.add_argument('--json')
    a = ap.parse_args()
    items = intervals(load(a.trace))
    origin = None
    if a.window:
        w = json.load(open(a.window, encoding='utf-8-sig'))
        origin = w.get('grid_observed_ms') or w.get('sample_start_ms')
    shots = []
    if a.shots:
        shots = [(s['start_ms'], s['end_ms']) for s in json.load(open(a.shots, encoding='utf-8-sig'))]
    long = []
    for it in items:
        if it['interval_ms'] <= a.min_ms:
            continue
        start = it['end_unix_ms'] - it['interval_ms']
        it['shot_overlap'] = any(s < it['end_unix_ms'] and e > start for s, e in shots)
        it['t_s'] = round((it['end_unix_ms'] - origin) / 1000, 2) if origin else None
        long.append(it)
    print(f"{'t_s':>8} {'ms':>7} {'batch':>7} {'tex':>6} {'alloc':>6} {'#al':>4} {'#up':>4} {'upl':>5} {'MB':>6} {'pso':>6} {'drv':>4} {'rec':>6} {'gpu':>6} {'skipfp':>6} shot fg")
    for it in long:
        print(f"{it['t_s'] if it['t_s'] is not None else '':>8} {it['interval_ms']:7.1f} {it['batch_ms']:7.1f} {it['tex_ms']:6.1f} "
              f"{it['tex_alloc_ms']:6.1f} {int(it['tex_allocs']):4d} {int(it['up_allocs']):4d} {int(it['uploads']):5d} {it['upload_bytes'] / 1e6:6.1f} "
              f"{it['pso_ms']:6.1f} {int(it['driver_calls']):4d} {it['record_ms']:6.1f} {it['gpu_previous_ms']:6.1f} "
              f"{int(it['skip_fp']):6d} {'S' if it['shot_overlap'] else '-'}    {'Y' if it['foreground'] else 'n'}")
    clean = [it for it in long if not it['shot_overlap']]
    print(f"{len(long)} intervals > {a.min_ms} ms ({len(clean)} without screenshot overlap); "
          f"texture alloc in them {sum(i['tex_alloc_ms'] for i in clean):.0f} ms / {int(sum(i['tex_allocs'] for i in clean))} allocations")
    if a.json:
        json.dump(dict(min_ms=a.min_ms, intervals=long), open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
