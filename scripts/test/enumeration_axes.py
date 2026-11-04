"""Which profile axes split enumerated fragment shaders, from a finished enumeration stage's checkpoints.

    enumeration_axes.py --run <enumeration run directory> [--collapse] [--json out.json]

<run>/enumeration/fragment-NNNN.json hold, for each job of preparation_enumeration.fragment_jobs() in plan
order, [source key, DXBC sha256, size] (source key = the generated HLSL's cache key). For each axis (and
selected combinations) the jobs are grouped by (program, profile with that axis removed). If the axis were a
run-time value instead of a compile-time one, the best case is one shader per group; sources that a group holds several of merge, sources that groups share
stay shared, so the new count is the number of connected components of the group/source graph and the saving is
(distinct sources - components). It is an upper bound: removing an
axis from the text needs a uniform, a branch, and plumbing in the renderer that this does not measure.
Only identifiers and counts are printed; nothing game-derived is stored.
"""
import argparse
import collections
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
NAMES = ['exp32', 'cube', 'stencil26', 'unnorm', 'samplers', 'ghi', 'shd', 'unhi', 'used', 'dither']
GAMMA_BITS = 0x1F00      # cube word: sRGB read on units 0-3 (bits 8-11) and sRGB encode on write (bit 12)


def load(run, collapse):
    from preparation_enumeration import fragment_jobs
    plan = json.loads((ROOT / 'assets/shader-enumeration/gt5p-disc-v1/plan.json').read_text())
    jobs = fragment_jobs(plan, collapse)
    rows = []
    for path in sorted((run / 'enumeration').glob('fragment-*.json')):
        saved = json.loads(path.read_text())
        rows[saved['start']:saved['start'] + len(saved['rows'])] = saved['rows']
    if len(rows) != len(jobs):
        raise ValueError(f'{len(rows)} checkpoint rows for {len(jobs)} jobs')
    return jobs, rows


def saving(jobs, rows, project):
    """(sources removed, groups): sources are merged when one group holds several of them, and any source
    shared between groups stays shared, so the new count is the number of connected components."""
    groups = collections.defaultdict(set)
    for (program, profile), row in zip(jobs, rows):
        if row is not None:
            groups[(program, project(profile))].add(row[0])
    parent = {}

    def find(key):
        while parent.setdefault(key, key) != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key
    for keys in groups.values():
        keys = list(keys)
        for other in keys[1:]:
            parent[find(other)] = find(keys[0])
        find(keys[0])
    components = len({find(key) for key in parent})
    return len(parent) - components, len(groups)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--run', type=Path, required=True)
    ap.add_argument('--collapse', action='store_true', default=True)
    ap.add_argument('--json', type=Path)
    a = ap.parse_args()
    jobs, rows = load(a.run, a.collapse)
    ok = [row for row in rows if row is not None]
    sources = {row[0] for row in ok}
    result = dict(jobs=len(jobs), prepared=len(ok), distinct_sources=len(sources),
                  distinct_bytecode=len({row[1] for row in ok}), axes={}, combinations={})
    print(f"jobs {len(jobs)}, prepared {len(ok)}, distinct sources {len(sources)}, distinct bytecode {result['distinct_bytecode']}")

    def without(index, mask=None):
        def project(profile):
            profile = list(profile)
            profile[index] = 0 if mask is None else profile[index] & ~mask
            return tuple(profile)
        return project

    def many(*projections):
        def project(profile):
            for step in projections:
                profile = step(profile)
            return profile
        return project

    for index, name in enumerate(NAMES):
        if index == 1:
            continue
        saved, groups = saving(jobs, rows, without(index))
        result['axes'][name] = dict(saved=saved, groups=groups)
        print(f'{name:12} saved <= {saved:6} of {len(sources)} sources ({100 * saved / len(sources):.1f}%)')
    for label, project in (
            ('cube gamma bits 8-12', without(1, GAMMA_BITS)),
            ('cube env bit 30', without(1, 1 << 30)),
            ('cube all', without(1)),
            ('gamma + samplers', many(without(1, GAMMA_BITS), without(4))),
            ('gamma + samplers + dither', many(without(1, GAMMA_BITS), without(4), without(9))),
            ('gamma + samplers + dither + stencil', many(without(1, GAMMA_BITS), without(4), without(9), without(2))),
            ('everything but used', many(without(0), without(1), without(2), without(3), without(4), without(5),
                                         without(6), without(7), without(9)))):
        saved, groups = saving(jobs, rows, project)
        result['combinations'][label] = dict(saved=saved, groups=groups)
        print(f'{label:36} saved <= {saved:6} ({100 * saved / len(sources):.1f}%), groups {groups}')
    if a.json:
        a.json.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
