"""Synthetic tests of shader_enumerate: decomposition, material locals, context
projection, held-out evaluation, chunked resume. No game files, GPU or engine."""
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile

SCRIPTS = Path(__file__).parents[1]
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location('shader_enumerate', SCRIPTS / 'shader_enumerate.py')
module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
sys.modules['shader_enumerate'] = module

E = module

# ---- 1. decomposition round trip over structurally valid random profiles --------------------------
rng = random.Random(1234)


def random_profile(rng):
    used = rng.getrandbits(16) & rng.getrandbits(16)
    scalars = (rng.choice((0, 2, 4)), rng.randint(0, 1), 0, rng.randint(0, 1), rng.choice((0, 1 << 26)))
    units = {}
    for u in range(16):
        if used >> u & 1:
            units[u] = (rng.randint(0, 1), rng.randint(0, 1), rng.randint(0, 1), rng.randint(0, 1),
                        rng.randint(0, 1) if u >= 4 else 0, rng.randint(0, 15))
    shadow = any(s[3] for s in units.values())
    scalars = scalars[:2] + ((rng.choice((0, 6)) if shadow else 0),) + scalars[3:]
    return E.compose(scalars, rng.choice((0, 1, 5)), units, used, rng.randint(0, 1))


for _ in range(500):
    profile = rng.choice([random_profile(rng) for _ in range(1)])
    scalars, unnorm, units, used, exp32 = E.decompose(profile)
    assert E.compose(scalars, unnorm, units, used, exp32) == profile
    assert E.profile_of(E.state_of(profile), profile[8]) == profile, 'state/profile mismatch'

# Known bit positions (see vp_get_fp_pso): unit 14 cube -> bit 30, msaa nibble -> bits 16..19, unit 0 gamma -> bit 8.
p = E.compose((4, 1, 0, 0, 0), 0, {14: (1, 1, 0, 0, 0, 13), 0: (0, 1, 0, 0, 0, 12)}, (1 << 14) | 1, 0)
assert p[1] & (1 << 30) and (p[1] >> 16) & 15 == 4 and p[1] & (1 << 8) and p[1] & (1 << 12)
assert p[5] & (1 << 14) and p[4] == (13 << 56) | 12
# Unused units never carry state (the runtime trims them).
assert E.compose((0, 0, 0, 0, 0), 0, {7: (1, 1, 1, 1, 1, 15)}, 1, 0) == (0, 0, 0, 0, 0, 0, 0, 0, 1, 0)
# Shadow flags are inert without a shadow-map unit.
assert E.compose((0, 0, 6, 0, 0), 0, {0: (0, 0, 0, 0, 0, 12)}, 1, 0)[6] == 0
assert E.compose((0, 0, 6, 0, 0), 0, {13: (0, 0, 0, 1, 0, 9)}, 1 << 13, 0)[6] == (6 << 16) | (1 << 13)

# ---- 2. material-derived local vectors -----------------------------------------------------------
definition = dict(used=0b1011 | (1 << 15), globals=[(15, 'ditherMap', 0x801, 103)],
                  local=[dict(unit=0, sampler=12, shape='2d', gamma=True, unnorm=True),
                         dict(unit=1, sampler=9, shape='2d', gamma=False, unnorm=False),
                         dict(unit=3, sampler=13, shape='2d', gamma=True, unnorm=False)])
local = E.material_local(definition, 0x40)
assert local == (1, 1, ((0, (0, 1, 0, 0, 0, 12)), (1, (0, 0, 0, 0, 0, 9)), (3, (0, 1, 0, 0, 0, 13)))), local
assert E.material_local(definition, 0)[0] == 0
broken = dict(definition, local=definition['local'][:2])           # unit 3 sampled but unbound
assert E.material_local(broken) is None
high = dict(used=1 << 5, globals=[], local=[dict(unit=5, sampler=11, shape='2d', gamma=False, unnorm=True)])
assert E.material_local(high) == (0, 0, ((5, (0, 0, 0, 0, 1, 11)),)), 'texel bit belongs to unhi for units >= 4'
cube = dict(used=1 << 2, globals=[], local=[dict(unit=2, sampler=7, shape='cube', gamma=False, unnorm=False)])
assert E.material_local(cube)[2] == ((2, (1, 0, 0, 0, 0, 7)),)

# ---- 3. a synthetic game: locals per program x a few true contexts ---------------------------------
TYPES = {15: 103, 13: 87, 14: 71}
STATE = {103: (0, 0, 0, 0, 1, 4), 87: (0, 0, 0, 1, 0, 9), 71: (1, 1, 0, 0, 0, 13)}
OFF = {87: (0, 0, 0, 0, 0, 8)}
CONTEXTS = []     # (scalars, {type: state})
for msaa in (0, 2):
    for shadow_on in (True, False):
        states = {103: STATE[103], 71: STATE[71], 87: STATE[87] if shadow_on else OFF[87]}
        CONTEXTS.append(((msaa, 1, 6 if shadow_on else 0, 0, 0), states))


def make_program(rng, number):
    base = rng.choice((0b1, 0b11, 0b111))
    used = base | (1 << 15) | (1 << 13) | (1 << 14) if rng.random() < 0.7 else base | (1 << 15) | (1 << 13)
    gmap = {u: t for u, t in TYPES.items() if used >> u & 1}
    locals_ = []
    for _ in range(rng.randint(1, 2)):
        units = {u: (0, rng.randint(0, 1), 0, 0, 0, rng.choice((9, 12, 13))) for u in range(3) if base >> u & 1}
        locals_.append((0, 0, tuple(sorted(units.items()))))
    return dict(identity='%064x' % number, used=used, gmap=gmap, locals=sorted(set(locals_)), source='materials')


def true_profiles(info):
    out = set()
    for scalars, states in CONTEXTS:
        for local in info['locals']:
            units = dict(local[2])
            for u, t in info['gmap'].items():
                units[u] = states[t]
            if info['used'] >> 13 & 1 and not units[13][3]:
                pass
            out.add(E.compose(scalars, local[1], units, info['used'], local[0]))
    return out


programs = [make_program(rng, n) for n in range(60)]
infos = {p['identity']: p for p in programs}
rows = []
for p in programs:
    for profile in true_profiles(p):
        rows.append((p['identity'], profile, 'k' + E.sha256(repr((p['identity'], profile)).encode())[:15], 'r'))
train, test = E.split_by_program(rows, seed=5)
assert {r[0] for r in train}.isdisjoint({r[0] for r in test}) and test and train
assert (train, test) == E.split_by_program(rows, seed=5), 'split must be deterministic'

report = E.evaluate(train, test, infos, msaa=None)
assert report['profile_hits'] == report['profiles'], report            # perfect model, held-out programs
assert report['programs_new'] == report['programs']
# One candidate per (local x observed context): the model does not invent contexts.
assert report['candidates'] == sum(len(true_profiles(infos[i])) for i in {r[0] for r in test}), report

memo = {(i, pr): k for i, pr, k, _ in rows}
keyed = E.evaluate(train, test, infos, key_of=lambda i, pr: memo.get((i, pr)), msaa=None)
assert keyed['key_hits'] == keyed['keys'] == keyed['profiles'] and keyed['wasted_keys'] == 0, keyed
# Profiles that compile to one shader share a key: recall counts distinct keys, so hits <= observed keys.
first_key = {}
for i, pr, k, _ in sorted(test):
    first_key.setdefault(i, k)
collapsed = E.evaluate(train, test, infos, key_of=lambda i, pr: first_key[i], msaa=None)
assert collapsed['key_hits'] == len({r[0] for r in test}) < collapsed['keys'], collapsed
assert collapsed['distinct_candidate_keys'] == collapsed['programs'] and collapsed['wasted_keys'] == 0
# Candidates the compiler never saw are reported, not silently dropped.
partial = E.evaluate(train, test, infos, key_of=lambda i, pr: None, msaa=None)
assert partial['key_hits'] == 0 and partial['unresolved_candidates'] == partial['candidates'], partial

# ---- 4. MSAA is a setting axis, never learned --------------------------------------------------
only_zero = [r for r in rows if E.decompose(r[1])[0][0] == 0]
cs = E.train_contexts(only_zero, infos)
types = (71, 87, 103)
base_contexts = cs.project(types)
assert all(c[0][0] == 0 for c in base_contexts) and len(base_contexts) == 2          # shadow on/off
axis = cs.project(types, msaa=None)
assert axis == base_contexts
cs_full = E.train_contexts(rows, infos)
assert {c[0][0] for c in cs_full.project(types)} == {0, 2}
swapped = cs_full.project(types, msaa=[4])
assert {c[0][0] for c in swapped} == {0, 4} and len(swapped) == len(cs_full.project(types))
both = cs_full.project(types, msaa=[2, 4])
assert {c[0][0] for c in both} == {0, 2, 4} and len(both) == 6
# Held-out recall at an MSAA count the training half never saw.
unseen = [r for r in rows if E.decompose(r[1])[0][0] != 2] + []
rows4 = [(i, E.compose((4,) + E.decompose(pr)[0][1:], *E.decompose(pr)[1:]), k, r) for i, pr, k, r in rows
         if E.decompose(pr)[0][0] == 2]
miss = E.evaluate(rows, rows4, infos, msaa=None)
assert miss['profile_hits'] == 0 and miss['misses'].get('scalar:msaa=4') == len(rows4), miss
hit = E.evaluate(rows, rows4, infos, msaa=[2, 4])
assert hit['profile_hits'] == hit['profiles'], hit

# ---- 5. superset projection, cap order, marginal fallback --------------------------------------------
sub = E.ContextSet()
a = dict(used=(1 << 15) | (1 << 13), gmap={15: 103, 13: 87}, locals=[], source='fallback', identity='a')
b = dict(used=(1 << 15), gmap={15: 103}, locals=[], source='fallback', identity='b')
pa = E.compose(((0, 1, 6, 0, 0)), 0, {15: STATE[103], 13: STATE[87]}, a['used'], 0)
sub.add('a', a, pa)
pb = E.compose(((2, 1, 0, 0, 0)), 0, {15: STATE[103]}, b['used'], 0)
sub.add('b', b, pb)
projected = sub.project((103,))
assert len(projected) == 2 and projected[0][1] == ((103, STATE[103]),), projected
assert all(c[0][2] == 0 for c in projected), 'shadow flags are zeroed when no shadow type is sampled'
assert len(sub.project((103,), cap=1)) == 1
assert sub.project((87, 103)) == [((0, 1, 6, 0, 0), ((87, STATE[87]), (103, STATE[103])))]
marginal = sub.project((71,))                                         # nobody sampled an environment map
assert marginal == [], marginal
only = sub.project((87, 103), msaa=[4])
assert only[0][0][0] == 0, 'unsampled contexts are not replicated'

# ---- 6. build_profile honours a global unit that moved ---------------------------------------------
moved = dict(used=(1 << 11) | 1, gmap={11: 103}, locals=[], source='materials', identity='m')
profile = E.build_profile(moved, (0, 0, ((0, (0, 0, 0, 0, 0, 12)),)), ((0, 1, 0, 0, 0), ((103, STATE[103]),)))
assert E.decompose(profile)[2][11] == STATE[103] and profile[7] == 1 << 11, profile

# ---- 7. chunked compile: atomic publication, resume, plan mismatch --------------------------------------
import shader_fragment_batch
calls = []


def fake_compile_batch(jobs, root, cache, engine, game_root, translation='default', work_prefix=None,
                       batch_size=4096, on_batch_ready=None, poll=None):
    if poll:
        poll()
    calls.append(len(jobs))
    compiled = {}
    for job in jobs:
        key = job['id'][:16]
        (Path(cache) / (key + '.dxbc')).write_bytes(b'DXBC' + bytes(8))
        compiled[job['id']] = (key, b'DXBC' + bytes(8))
    return compiled, {}


original = shader_fragment_batch.compile_batch
shader_fragment_batch.compile_batch = fake_compile_batch
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        catalog = root / 'cat'; catalog.mkdir()
        payload = bytes(16)
        name = E.sha256(payload)
        (catalog / (name + '.fp')).write_bytes(payload)
        jobs = [('%064x' % n, name, E.compose((0, 1, 0, 0, 0), 0, {0: (0, 0, 0, 0, 0, 12 + (n % 2))}, 1, 0)) for n in range(5)]
        jobs = sorted(set(jobs))
        out = root / 'out'
        seen = {'n': 0}

        def stop_after_first():
            seen['n'] += 1
            if seen['n'] == 3:        # chunk 0 polls twice (loop + compile_batch); stop at chunk 1
                raise KeyboardInterrupt('stop')

        try:
            E.compile_fragments_chunked(jobs, out, catalog, root / 'e.exe', root, chunk=2, poll=stop_after_first, log=lambda *_: None)
            raise AssertionError('expected a stop')
        except KeyboardInterrupt:
            pass
        assert len(list((out / 'results').glob('f-*.json'))) == 1 and not list((out / 'results').glob('*.tmp'))
        assert calls == [2], calls
        stats = E.compile_fragments_chunked(jobs, out, catalog, root / 'e.exe', root, chunk=2, log=lambda *_: None)
        assert stats['reused_chunks'] == 1 and calls == [2, 2, 1], (stats, calls)
        memo = E.load_key_memo(out)
        assert len(memo) == len(jobs) and all(len(v) == 16 for v in memo.values())
        try:
            E.compile_fragments_chunked(jobs[:-1], out, catalog, root / 'e.exe', root, chunk=2, log=lambda *_: None)
            raise AssertionError('another plan must be rejected')
        except ValueError:
            pass
        leftover = [p for p in (out / 'work').glob('*')]
        assert not leftover, leftover
        # Staged runs: --max-chunks stops after N NEW chunks and a later session continues the same plan.
        calls.clear()
        staged = root / 'staged'
        first = E.compile_fragments_chunked(jobs, staged, catalog, root / 'e.exe', root, chunk=2, log=lambda *_: None, max_chunks=2)
        assert not first['complete'] and first['new_chunks'] == 2 and calls == [2, 2], (first, calls)
        second = E.compile_fragments_chunked(jobs, staged, catalog, root / 'e.exe', root, chunk=2, log=lambda *_: None, max_chunks=2)
        assert second['complete'] and second['reused_chunks'] == 2 and second['new_chunks'] == 1 and calls == [2, 2, 1], (second, calls)
        assert len(E.load_key_memo(staged)) == len(jobs)
        # Stop file switch.
        flag = root / 'stop'
        assert not E.stop_requested({'GT5P_ENUM_STOP': str(flag)})
        flag.write_text('x')
        assert E.stop_requested({'GT5P_ENUM_STOP': str(flag)}) and not E.stop_requested({})
finally:
    shader_fragment_batch.compile_batch = original

# ---- 8. vertex chunking (fake workers) ---------------------------------------------------------------
import shader_vertex_batch
original_vertex = shader_vertex_batch.compile_jobs


def fake_jobs(jobs, decoder, work, derive=False, workers=None, on_ready=None, poll=None, **_):
    compiled = {}
    for job in jobs:
        source = E.sha256(job['program'] + bytes([job['gpu']]))[:16]
        on_ready(job, source, 'c' * 16, b'DXBC' + bytes(4))
        compiled[(job['sha256'], job['gpu'])] = (source, 'c' * 16, b'DXBC' + bytes(4))
    return compiled, {}, {}


shader_vertex_batch.compile_jobs = fake_jobs
try:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        word = bytes(range(16))
        (root / 'asset.bin').write_bytes(b'\0' * 8 + word)
        raw = shader_vertex = None
        from shader_reconstruct import word_swap
        digest = E.sha256(word_swap(word))
        inventory = {digest: dict(size=16, file=str(root / 'asset.bin'), offset=8, wrappers=1)}
        stats = E.compile_vertices(inventory, [digest], root / 'out', root / 'decoder.dll', chunk=1, log=lambda *_: None)
        assert stats['compiled'] == 2 and len(list((root / 'out/shadercache').glob('*.dxbc'))) == 2, stats
        again = E.compile_vertices(inventory, [digest], root / 'out', root / 'decoder.dll', chunk=1, log=lambda *_: None)
        assert again['reused_chunks'] == 2 and again['compiled'] == 2
        inventory[digest]['offset'] = 7
        try:
            E.read_vertex(inventory[digest], digest)
            raise AssertionError('a moved program must not verify')
        except ValueError:
            pass
finally:
    shader_vertex_batch.compile_jobs = original_vertex

# ---- 8b. vertex recall counts variants by source key, per GPU-fetch mode ---------------------------------
records = [dict(vp=dict(sha256='a' * 64), vp_gpu=1, vp_source='1' * 16, vs='2' * 16),
           dict(vp=dict(sha256='b' * 64), vp_gpu=0, vp_source='3' * 16, vs='4' * 16),
           dict(vp=dict(sha256='c' * 64), vp_gpu=1, vp_source='5' * 16, vs='6' * 16)]
vmemo = {('a' * 64, 1): ('1' * 16, '2' * 16), ('b' * 64, 0): ('3' * 16, '9' * 16), ('d' * 64, 1): ('7' * 16, '8' * 16)}
vr = E.vertex_recall(records, vmemo)
assert vr['observed_variants'] == 3 and vr['covered_by_key'] == 2 and vr['covered_same_program'] == 2, vr
assert vr['by_gpu'] == {'0': [1, 1], '1': [1, 2]} and vr['bytecode_matches'] == 1, vr
with tempfile.TemporaryDirectory() as folder:
    results = Path(folder) / 'results'; results.mkdir()
    (results / 'v-00000.json').write_text(json.dumps(dict(rows=[['a' * 64, 1, '1' * 16, '2' * 16], ['b' * 64, 0, None, None]])))
    assert E.load_vertex_memo(folder) == {('a' * 64, 1): ('1' * 16, '2' * 16)}

# ---- 9. serialisation of the material index ------------------------------------------------------------
index = {'a' * 64: dict(used=3, gmap={15: 103}, locals={local}, incomplete=1, complete=2, vps={'b' * 64})}
assert E._load_materials(json.loads(json.dumps(E._dump_materials(index)))) == {
    'a' * 64: dict(used=3, gmap={15: 103}, locals={E._hashable(local)}, incomplete=1, complete=2, vps={'b' * 64})}
assert E._parse_msaa('2,4') == [2, 4] and E._parse_msaa('0,1,2') == [2] and E._parse_msaa('') is None
try:
    E._parse_msaa('3')
    raise AssertionError('only 2, 4 and 8 are sample counts')
except ValueError:
    pass
print('shader_enumerate: decomposition, material locals, context projection, MSAA axis, held-out evaluation, '
      'chunked resume and vertex chunking checks passed')
