"""Private engine for interpreter frame-time routes: main patch + shader-interpreter overlay + frame-hitch trace.

Same steps as interp_private_build.py (precompiled, embedded generic interpreter DXBC; reference objects
relinked read-only), plus patches/ps3recomp-frame-hitch-trace.patch so scripts/test/hitch_capture.py can
record per-interval costs. Output: <--output>/install/runtime/gt5p.exe (under scratch). The worktree's
build/ is not touched. Run from an x64 VS environment through run_locked.py, with GT5P_RUNTIME naming
the runtime source the reference build used.
"""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import interp_embed  # noqa: E402
import interp_private_build as b  # noqa: E402


def trace(tree, backend):
    """The trace overlay's three skip counters sit on lines the interpreter overlay rewrites: apply the rest
    with --reject, then put the same counters on the interpreter's versions of those lines."""
    data = (b.ROOT / 'patches' / 'ps3recomp-frame-hitch-trace.patch').read_bytes().replace(b'\r\n', b'\n')
    lf = tree.parent / 'trace.patch.lf'
    lf.write_bytes(data)
    r = subprocess.run(['git', '-C', str(tree), 'apply', '--whitespace=nowarn', '--reject', str(lf)],
                       capture_output=True, text=True)
    rejects = list(tree.rglob('*.rej'))
    if [x.name for x in rejects] != ['rsx_d3d12_backend.c.rej'] or r.stderr.count('Rejected hunk') != 3:
        raise SystemExit('unexpected trace overlay rejects:\n' + r.stderr)
    rejects[0].unlink()
    text = backend.read_text(encoding='utf-8')
    swaps = [('interp_note_skip(0); if (!_ib) interp_budget_note_denied(); continue;',
              'interp_note_skip(0); if (!_ib) interp_budget_note_denied(); if (hitch_on()) s_hitch_skip_vp++; continue;', 2),
             ('interp_note_skip(1); if (!_ib) interp_budget_note_denied(); continue;',
              'interp_note_skip(1); if (!_ib) interp_budget_note_denied(); if (hitch_on()) s_hitch_skip_fp++; continue;', 1),
             ('FR->shader_pending = 1; interp_note_skip(2); }',
              'FR->shader_pending = 1; interp_note_skip(2); if (hitch_on()) s_hitch_skip_record++; }', 1)]
    for old, new, n in swaps:
        if text.count(old) != n:
            raise SystemExit('trace counter site not found: ' + old)
        text = text.replace(old, new)
    with open(backend, 'w', encoding='utf-8', newline='') as f:
        f.write(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output', type=Path, default=b.ROOT / 'scratch/hitch/build-interp')
    a = ap.parse_args()
    if os.environ.get('VSCMD_ARG_TGT_ARCH', '').lower() != 'x64':
        raise SystemExit('Use an x64 VS environment')
    fresh = a.output.resolve()
    if not fresh.is_relative_to((b.ROOT / 'scratch').resolve()):
        raise SystemExit('Build must remain under scratch')
    if fresh.exists():
        shutil.rmtree(fresh)
    fresh.mkdir(parents=True)
    backend = b.apply_sources(fresh / 'tree')
    trace(fresh / 'tree', backend)
    cache = b.ROOT / 'scratch' / 'interp-cache'
    if os.environ.get('INTERP_SKIP_PRECOMPILE') != '1':
        b.precompile_interpreters(fresh / 'tree', cache)
    interp_embed.generate(backend.parent, cache)
    obj = b.compile_backend(backend, fresh / 'backend-objects')
    print(b.link_engine(fresh, obj, b.compile_decompilers(fresh)), flush=True)


if __name__ == '__main__':
    main()
