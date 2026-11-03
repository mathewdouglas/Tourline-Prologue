"""Shader-first enumeration of asset programs across a small observed context set.

Developer-only and default-off: nothing here is wired into player preparation.

Idea: a fragment pipeline's translation profile is (program-local state) x (a few
global contexts). The program-local part (sampler lanes, texel-addressing and
shape bits of the units a material binds itself) is recovered from the game's
own material tables. The global part (MSAA sample count, LV shadow, environment
cube, dither unit, final-dither flag...) takes only a handful of values across
the observed starter. Every asset program is compiled for local x contexts with
the production exact batch compilers, into a PRIVATE cache. Native pipelines
stay with the runtime's background worker and the observed templates.

Subcommands (outputs are local game-derived data; keep them in ignored storage):
  inventory   index catalogue payloads, vertex programs and material locals
  plan        candidate (program, profile) jobs for a scope
  compile     fragment + vertex compile of a plan into <output>/shadercache
  recall      held-out recall of the model against the observed starter
  report      counts for a finished or partial run

Switches: GT5P_ENUM_STOP=<file> stops between chunks when the file exists.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import mmap
import os
from pathlib import Path
import random
import re
import struct
import sys
import time

from shader_coverage import MAX_FP, bounded_read, fnv64, fp_identity

SCHEMA = 'gt5p-shader-enumeration'
HEX64 = re.compile('[0-9a-f]{64}')
HEX16 = re.compile('[0-9a-f]{16}')
MAX_CHUNK = 4096
# Observed convention: which texture unit a global sampler identifier occupies.
# Used only for programs whose materials cannot be parsed (no declared globals).
CONVENTIONAL_GLOBALS = {15: 103, 13: 87, 14: 71, 12: 96, 11: 104}
UNIT_FIELDS = ('cube', 'gamma', 'volume', 'shadow', 'texel', 'sampler')
PROFILE_FIELDS = ('exp32', 'cube', 'stencil', 'unnorm', 'samplers', 'ghi', 'shd', 'unhi', 'used', 'dither')


def sha256(data):
    return hashlib.sha256(data).hexdigest()


# --------------------------------------------------------------------------
# Profile <-> state. The tuple is exactly prepare_material_shaders.fragment_profile.
# --------------------------------------------------------------------------

def profile_of(state, used):
    from prepare_material_shaders import fragment_profile
    return tuple(fragment_profile(dict(state=state, used=used)))


def state_of(profile):
    """A job state that fragment_profile maps back to `profile` (other fields are inert)."""
    exp32, cube, stencil, unnorm, samplers, ghi, shd, unhi, used, dither = profile
    return dict(exp32=exp32, cube=cube, stencil=stencil, unnorm=unnorm, samplers=f'{samplers:016x}', ghi=ghi,
                shd=shd, unhi=unhi, rtfmt=28 if dither else 0, nrt=1, cmask=15 if dither else 0)


# --------------------------------------------------------------------------
# Decomposition. A profile is scalars + a state per sampled texture unit.
#   unit state = (cube, gamma, volume, shadow, texel, sampler nibble)
# --------------------------------------------------------------------------

def decompose(profile):
    """-> (scalars, unnorm, units, used). scalars = (msaa, out_gamma, shadow_flags, dither, stencil)."""
    exp32, cube, stencil, unnorm, samplers, ghi, shd, unhi, used, dither = profile
    units = {}
    for u in range(16):
        if not used >> u & 1:
            continue
        units[u] = (((cube >> u) & 1) if u < 4 else ((cube >> (20 + u - 4)) & 1),
                    ((cube >> (8 + u)) & 1) if u < 4 else ((ghi >> u) & 1),
                    (ghi >> (16 + u)) & 1, (shd >> u) & 1,
                    ((unhi >> u) & 1) if u >= 4 else 0, (samplers >> (4 * u)) & 15)
    scalars = ((cube >> 16) & 15, (cube >> 12) & 1, shd >> 16, dither, stencil)
    return scalars, unnorm, units, used, exp32


def compose(scalars, unnorm, units, used, exp32):
    msaa, out_gamma, shadow_flags, dither, stencil = scalars
    cube = ghi = shd = unhi = samplers = 0
    for u in range(16):
        if not used >> u & 1:
            continue
        cu, gm, vol, sh, tx, sa = units.get(u, (0, 0, 0, 0, 0, 0))
        if u < 4:
            cube |= (cu << u) | (gm << (8 + u))
        else:
            cube |= cu << (20 + u - 4)
            ghi |= gm << u
            unhi |= tx << u
        ghi |= vol << (16 + u)
        shd |= sh << u
        samplers |= sa << (4 * u)
    cube |= (msaa << 16) | (out_gamma << 12)
    if shd & 0xFFFF:                       # production trims the flags when no unit is a shadow map
        shd |= shadow_flags << 16
    return (exp32, cube, stencil, unnorm, samplers, ghi, shd, unhi, used, dither)


def context_of(profile, gmap):
    """Global context of a profile: scalar bits + the state of each global texture type it samples."""
    scalars, _, units, used, _ = decompose(profile)
    return scalars, tuple(sorted((gmap[u], units[u]) for u in gmap if u in units))


def local_of(profile, gmap):
    _, unnorm, units, _, exp32 = decompose(profile)
    return exp32, unnorm, tuple((u, units[u]) for u in sorted(units) if u not in gmap)


def build_profile(info, local, context):
    """Combine a program's local vector with one global context (units trimmed to the program's samples)."""
    exp32, unnorm, local_units = local
    scalars, global_states = context
    units = dict(local_units)
    wanted = dict(global_states)
    for unit, kind in info['gmap'].items():
        if kind in wanted and info['used'] >> unit & 1:
            units[unit] = wanted[kind]
    return compose(scalars, unnorm, units, info['used'], exp32)


# --------------------------------------------------------------------------
# Material-derived local state.
# --------------------------------------------------------------------------

def material_local(definition, control=0):
    """Local vector from one parsed material definition, or None if a sampled local unit is unbound."""
    gunits = {g[0] for g in definition['globals']}
    units, unnorm = {}, 0
    for u in range(16):
        if not definition['used'] >> u & 1 or u in gunits:
            continue
        b = next((b for b in definition['local'] if b['unit'] == u), None)
        if b is None:
            return None
        texel = int(bool(b['unnorm']) and b['shape'] == '2d')
        if u < 4 and texel:
            unnorm |= 1 << u
        units[u] = (int(b['shape'] == 'cube'), int(bool(b['gamma'])), int(b['shape'] == 'volume'), 0,
                    texel if u >= 4 else 0, b['sampler'])
    return int(bool(control & 0x40)), unnorm, tuple(sorted(units.items()))


def _hashable(local):
    exp32, unnorm, units = local
    return exp32, unnorm, tuple((u, tuple(s)) for u, s in units)


# --------------------------------------------------------------------------
# Inventories (all local; identities and numeric facts only).
# --------------------------------------------------------------------------

def fragment_inventory(catalog, progress=None):
    """identity -> payload list for every catalogue .fp (named by raw SHA-256)."""
    out, failed = defaultdict(list), []
    names = sorted(p for p in os.listdir(catalog) if p.endswith('.fp'))
    for number, name in enumerate(names):
        raw = bounded_read(Path(catalog) / name, MAX_FP)
        if sha256(raw) != name[:-3]:
            raise ValueError('Catalogue payload name differs from its SHA-256: ' + name)
        try:
            info = fp_identity(raw)
        except ValueError as exc:
            failed.append(name[:-3])
            continue
        out[info['identity']].append(dict(payload=name[:-3], size=info['size'], textures=info['textures']))
        if progress and number % 1000 == 0:
            progress(f'catalogue payloads {number + 1}/{len(names)}')
    for payloads in out.values():
        payloads.sort(key=lambda p: p['payload'])
    return dict(out), failed


def container_files(catalog):
    index = json.loads(bounded_read(Path(catalog) / 'index.json', 64 * 1024**2))
    files = sorted({s['file'] for s in index['sources']})
    if len(files) > 8192:
        raise ValueError('Container count exceeds the lookup budget')
    return files


def vertex_inventory(files, progress=None):
    """Distinct full-length SHDS vertex programs: sha256 -> dict(size, file, offset, wrappers)."""
    from shader_reconstruct import vertex_programs, word_swap
    out = {}
    for number, name in enumerate(files):
        p = Path(name)
        if not 0 < p.stat().st_size <= 1024**3:
            continue
        with p.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            for item in vertex_programs(data):
                raw = word_swap(data[item['offset']:item['offset'] + item['size']])
                digest = sha256(raw)
                entry = out.setdefault(digest, dict(size=len(raw), file=name, offset=item['offset'], wrappers=0))
                entry['wrappers'] += 1
        if progress and number % 100 == 0:
            progress(f'vertex containers {number + 1}/{len(files)}: {len(out)} distinct programs')
    return out


def read_vertex(entry, digest):
    from shader_reconstruct import word_swap
    with open(entry['file'], 'rb') as stream:
        stream.seek(entry['offset'])
        raw = word_swap(stream.read(entry['size']))
    if len(raw) != entry['size'] or sha256(raw) != digest:
        raise ValueError('Vertex program changed since indexing')
    return raw


def material_index(files, progress=None):
    """identity -> used mask, declared globals, material-derived local vectors, vertex pairs.

    Parses the original MDL3 tables (no captures). A definition whose sampled local
    unit has no texture binding is counted but contributes no local vector.
    """
    from shader_materials import scan
    from shader_material_textures import model_textures
    from shader_texture_shapes import texture_shape
    out = {}
    for number, name in enumerate(files):
        p = Path(name)
        if not 0 < p.stat().st_size <= 1024**3:
            continue
        with p.open('rb') as stream, mmap.mmap(stream.fileno(), 0, access=mmap.ACCESS_READ) as data:
            for base, pairs, _, error in scan(data):
                if error:
                    continue
                controls = {pair['material']: pair['fragment_control'] for pair in pairs}
                try:
                    definitions, _ = model_textures(data, base)
                except (ValueError, KeyError, struct.error):
                    continue
                for d in definitions:
                    local = []
                    for b in d['bindings']:
                        try:
                            shape = texture_shape(b)
                        except ValueError:
                            shape = None
                        local.append(dict(unit=b['unit'], sampler=b['sampler'], shape=shape,
                                          gamma=bool((b['address'] >> 20) & 7), unnorm=bool(b['format'] & 0x4000)))
                    definition = dict(used=d['used'], globals=[(g['unit'], g['name'], g['kind'], g['identifier'])
                                                               for g in d['globals']], local=local)
                    entry = out.setdefault(d['fragment_identity'], dict(
                        used=d['used'], gmap={g[0]: g[3] for g in definition['globals']}, locals=set(),
                        incomplete=0, complete=0, vps=set()))
                    entry['vps'].add(sha256(d['vertex_code']))
                    found = material_local(definition, controls.get(d['material'], 0))
                    if found is None:
                        entry['incomplete'] += 1
                    else:
                        entry['complete'] += 1
                        entry['locals'].add(_hashable(found))
        if progress and number % 100 == 0:
            progress(f'material containers {number + 1}/{len(files)}: {len(out)} programs')
    return out


def _dump_materials(index):
    return {k: dict(used=v['used'], gmap={str(u): t for u, t in v['gmap'].items()},
                    locals=sorted([e, n, [[u, list(s)] for u, s in units]] for e, n, units in v['locals']),
                    incomplete=v['incomplete'], complete=v['complete'], vps=sorted(v['vps']))
            for k, v in sorted(index.items())}


def _load_materials(raw):
    return {k: dict(used=v['used'], gmap={int(u): t for u, t in v['gmap'].items()},
                    locals={(e, n, tuple((u, tuple(s)) for u, s in units)) for e, n, units in v['locals']},
                    incomplete=v['incomplete'], complete=v['complete'], vps=set(v['vps']))
            for k, v in raw.items()}


# --------------------------------------------------------------------------
# Program info: used mask, global-unit map, local vectors.
# --------------------------------------------------------------------------

def program_info(identity, fragments, materials):
    """fragments[identity] = payload list; materials may lack the program."""
    used = fragments[identity][0]['textures']
    m = materials.get(identity)
    if m and m['used'] != used:
        raise ValueError('Material used-unit mask differs from the catalogue program')
    if m and m['complete']:
        return dict(identity=identity, used=used, gmap=dict(m['gmap']), locals=sorted(m['locals']), source='materials')
    gmap = {u: t for u, t in CONVENTIONAL_GLOBALS.items() if used >> u & 1}
    if m:
        gmap = dict(m['gmap'])
    return dict(identity=identity, used=used, gmap=gmap, locals=[], source='fallback')


class ContextSet:
    """Observed global contexts, keyed by the global types a program samples."""

    def __init__(self):
        self.by_types = defaultdict(lambda: defaultdict(set))   # types -> context -> programs
        self.locals = defaultdict(lambda: defaultdict(set))     # local-unit mask -> local vector -> programs

    def add(self, identity, info, profile):
        types = tuple(sorted(set(info['gmap'].values())))
        self.by_types[types][context_of(profile, info['gmap'])].add(identity)
        mask = info['used'] & ~sum(1 << u for u in info['gmap'])
        self.locals[mask][local_of(profile, info['gmap'])].add(identity)

    def project(self, types, msaa=None, cap=None):
        """Contexts for a program with global `types`, most common first. msaa: nonzero sample counts
        to enumerate (an explicit setting axis, never trained): every multisampled context is
        replicated for each, the unsampled one is kept as is."""
        wanted = set(types)
        merged = defaultdict(set)
        for known, contexts in self.by_types.items():
            if wanted <= set(known):
                for (scalars, states), programs in contexts.items():
                    kept = tuple(s for s in states if s[0] in wanted)
                    if not any(state[3] for _, state in kept):     # no shadow map sampled: flags are inert
                        scalars = scalars[:2] + (0,) + scalars[3:]
                    projected = (scalars, kept)
                    if msaa is None or scalars[0] == 0:
                        merged[projected] |= programs
                    else:
                        for count in msaa:
                            replica = ((count,) + scalars[1:], projected[1])
                            merged[replica] |= programs
        order = sorted(merged.items(), key=lambda item: (-len(item[1]), repr(item[0])))
        result = [context for context, _ in order]
        if not result:
            result = self._marginal(types, msaa)
        return result[:cap] if cap else result

    def _marginal(self, types, msaa):
        """No observed program samples all of `types`: product of the commonest per-type states."""
        scalar_votes, type_votes = Counter(), defaultdict(Counter)
        for contexts in self.by_types.values():
            for (scalars, states), programs in contexts.items():
                scalar_votes[scalars] += len(programs)
                for kind, state in states:
                    type_votes[kind][state] += len(programs)
        if not scalar_votes or any(t not in type_votes for t in types):
            return []
        out = []
        for scalars, _ in scalar_votes.most_common(3):
            if msaa is not None and scalars[0] != 0:
                variants = [((count,) + scalars[1:]) for count in msaa]
            else:
                variants = [scalars]
            for variant in variants:
                states = [[(t, s) for s, _ in type_votes[t].most_common(2)] for t in sorted(types)]
                combos = [()]
                for options in states:
                    combos = [c + (o,) for c in combos for o in options]
                out.extend((variant, combo) for combo in combos)
        return out

    def donor_locals(self, info, cap=None):
        mask = info['used'] & ~sum(1 << u for u in info['gmap'])
        ranked = sorted(self.locals.get(mask, {}).items(), key=lambda item: (-len(item[1]), repr(item[0])))
        return [vector for vector, _ in ranked][:cap] if cap else [vector for vector, _ in ranked]


def candidates(info, contexts, fallback_locals=None, msaa=None, context_cap=None, local_cap=None):
    """Distinct candidate profiles for one program."""
    locals_ = info['locals']
    if not locals_ and info['source'] == 'fallback':
        locals_ = contexts.donor_locals(info, fallback_locals)
    types = tuple(sorted(set(info['gmap'].values())))
    projected = contexts.project(types, msaa, context_cap)
    if local_cap:
        locals_ = locals_[:local_cap]
    return {build_profile(info, local, context) for local in locals_ for context in projected}


# --------------------------------------------------------------------------
# Template ingest and held-out evaluation.
# --------------------------------------------------------------------------

def template_rows(records, fragments, materials):
    """Observed (identity, profile, ps key, label) tuples for programs present in the catalogue."""
    rows = []
    for r in records:
        identity = r['fp']['sha256']
        if identity not in fragments:
            continue
        used = fragments[identity][0]['textures']
        rows.append((identity, profile_of(r['state'], used), r['fp_source'], r['key']))
    return rows


def train_contexts(rows, infos):
    cs = ContextSet()
    for identity, profile, _, _ in rows:
        cs.add(identity, infos[identity], profile)
    return cs


def evaluate(train_rows, test_rows, infos, key_of=None, msaa=None, context_cap=None, fallback_locals=None,
             local_cap=None):
    """Recall of test_rows' (program, profile) and (program, ps key) pairs from candidates built with
    contexts learned from train_rows only. key_of(identity, profile) -> key or None (not compiled)."""
    cs = train_contexts(train_rows, infos)
    train_programs = {identity for identity, *_ in train_rows}
    observed = defaultdict(lambda: (set(), set()))
    for identity, profile, key, _ in test_rows:
        observed[identity][0].add(profile)
        observed[identity][1].add(key)
    result = Counter()
    misses = Counter()
    wasted = 0
    unresolved = 0
    for identity, (profiles, keys) in observed.items():
        generated = candidates(infos[identity], cs, fallback_locals, msaa, context_cap, local_cap)
        new = identity not in train_programs
        result['programs'] += 1
        result['programs_new'] += new
        result['candidates'] += len(generated)
        result['profiles'] += len(profiles)
        hits = profiles & generated
        result['profile_hits'] += len(hits)
        result['profiles_new'] += len(profiles) * new
        result['profile_hits_new'] += len(hits) * new
        for profile in profiles - generated:
            misses[miss_axis(profile, infos[identity], cs, msaa)] += 1
        if key_of is not None:
            produced = set()
            for profile in generated:
                key = key_of(identity, profile)
                if key is None:
                    unresolved += 1
                else:
                    produced.add(key)
            result['keys'] += len(keys)
            result['key_hits'] += len(keys & produced)
            result['keys_new'] += len(keys) * new
            result['key_hits_new'] += len(keys & produced) * new
            result['distinct_candidate_keys'] += len(produced)
            wasted += len(produced - keys)
            result['programs_fully_covered'] += keys <= produced
    out = dict(result)
    out['unresolved_candidates'] = unresolved
    out['wasted_keys'] = wasted
    out['misses'] = dict(misses)
    return out


def miss_axis(profile, info, cs, msaa):
    """Name the first axis along which an uncovered observed profile leaves the model."""
    gmap = info['gmap']
    scalars, states = context_of(profile, gmap)
    exp32, unnorm, local_units = local_of(profile, gmap)
    types = tuple(sorted(set(gmap.values())))
    projected = cs.project(types, msaa)
    if info['source'] == 'materials' and _hashable((exp32, unnorm, local_units)) not in {_hashable(l) for l in info['locals']}:
        return 'local'
    if info['source'] != 'materials' and (exp32, unnorm, local_units) not in set(cs.donor_locals(info)):
        return 'local(fallback)'
    if (scalars, states) in set(projected):
        return 'cap/combination'
    if scalars not in {c[0] for c in projected}:
        return f'scalar:msaa={scalars[0]}' if scalars[0] not in {c[0][0] for c in projected} else 'scalar:other'
    for kind, state in states:
        if not any((kind, state) in c[1] for c in projected):
            return f'type:{kind}'
    return 'joint'


def split_by_program(rows, seed, fraction=0.5):
    programs = sorted({identity for identity, *_ in rows})
    random.Random(seed).shuffle(programs)
    test = set(programs[:int(len(programs) * fraction)])
    return [r for r in rows if r[0] not in test], [r for r in rows if r[0] in test]


# --------------------------------------------------------------------------
# Plan / compile (chunked, resumable, cancellable).
# --------------------------------------------------------------------------

def plan_hash(jobs):
    h = hashlib.sha256()
    for identity, payload, profile in jobs:
        h.update(repr((identity, payload, profile)).encode())
    return h.hexdigest()


def write_atomic(path, payload):
    path = Path(path)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(payload, sort_keys=True, separators=(',', ':')), encoding='ascii')
    tmp.replace(path)


def stop_requested(environ=None):
    name = (os.environ if environ is None else environ).get('GT5P_ENUM_STOP')
    return bool(name) and Path(name).exists()


def fragment_jobs_for(infos, fragments, contexts, scope_programs, msaa, context_cap, fallback_locals, local_cap):
    jobs = []
    for identity in sorted(scope_programs):
        info = infos[identity]
        payload = fragments[identity][0]['payload']
        for profile in sorted(candidates(info, contexts, fallback_locals, msaa, context_cap, local_cap)):
            jobs.append((identity, payload, profile))
    return jobs


def compile_fragments_chunked(jobs, output, catalog, engine, game_root, chunk, poll=None, log=print, max_chunks=0):
    """Compile jobs in chunks into <output>/shadercache. Each chunk's result is published atomically;
    an existing chunk result (same plan hash) is reused on resume. max_chunks > 0 stops after that
    many NEW chunks (stats['complete'] False), so a long plan can run as several short locked sessions."""
    from shader_fragment_batch import compile_batch
    if not 1 <= chunk <= MAX_CHUNK:
        raise ValueError('chunk must be 1..4096')
    output = Path(output)
    cache = output / 'shadercache'
    results = output / 'results'
    for folder in (cache, results, output / 'work'):
        folder.mkdir(parents=True, exist_ok=True)
    digest = plan_hash(jobs)
    stats = dict(chunks=0, reused_chunks=0, new_chunks=0, compiled_jobs=0, failed_jobs=0, seconds=0.0, complete=True)
    started = time.perf_counter()
    for number in range(0, len(jobs), chunk):
        block = jobs[number:number + chunk]
        name = results / f'f-{number // chunk:05d}.json'
        stats['chunks'] += 1
        if max_chunks and stats['new_chunks'] >= max_chunks and not name.exists():
            stats['complete'] = False
            stats['chunks'] -= 1
            break
        if name.exists():
            saved = json.loads(bounded_read(name, 64 * 1024**2))
            if saved.get('plan') != digest or saved.get('start') != number or len(saved['rows']) != len(block):
                raise ValueError('Existing chunk result belongs to another plan; use a fresh output')
            stats['reused_chunks'] += 1
            stats['compiled_jobs'] += sum(1 for row in saved['rows'] if row[3])
            continue
        if poll:
            poll()
        batch = []
        for identity, payload, profile in block:
            raw = bounded_read(Path(catalog) / (payload + '.fp'), MAX_FP)
            used = profile[8]
            batch.append(dict(id=sha256(repr((identity, payload, profile)).encode()), fragment=raw,
                              fragment_sha256=sha256(raw), state=state_of(profile), used=used))
        work = output / 'work' / f'chunk-{number // chunk:05d}'
        work.mkdir(parents=True, exist_ok=True)
        compiled, failures = compile_batch(batch, work, cache, engine, game_root, batch_size=min(chunk, MAX_CHUNK), poll=poll)
        rows = []
        for (identity, payload, profile), job in zip(block, batch):
            got = compiled.get(job['id'])
            rows.append([identity, payload, list(profile), got[0] if got else None,
                         f'{fnv64(got[1]):016x}' if got else None, len(got[1]) if got else None])
        write_atomic(name, dict(schema=SCHEMA, kind='fragment', plan=digest, start=number, rows=rows))
        stats['new_chunks'] += 1
        stats['compiled_jobs'] += len(compiled)
        stats['failed_jobs'] += len(failures)
        for leftover in work.glob('*'):
            if leftover.is_dir():
                import shutil
                shutil.rmtree(leftover, ignore_errors=True)
            else:
                leftover.unlink(missing_ok=True)
        work.rmdir()
        log(f'fragment chunk {number // chunk + 1}/{-(-len(jobs) // chunk)}: {len(compiled)} compiled, '
            f'{len(failures)} failed, {time.perf_counter() - started:.0f}s')
    stats['seconds'] = time.perf_counter() - started
    return stats


def compile_vertices(inventory, selected, output, decoder, chunk=256, workers=None, poll=None, log=print, max_chunks=0):
    """Compile (vertex program, gpu 0/1) derive jobs through the batch worker pool."""
    from shader_vertex_batch import compile_jobs
    from prepare_material_shaders import save_code
    output = Path(output)
    cache = output / 'shadercache'
    results = output / 'results'
    for folder in (cache, results, output / 'work'):
        folder.mkdir(parents=True, exist_ok=True)
    jobs = [(digest, gpu) for digest in sorted(selected) for gpu in (0, 1)]
    digest_all = plan_hash([(d, str(g), ()) for d, g in jobs])
    stats = dict(chunks=0, reused_chunks=0, new_chunks=0, compiled=0, failed=0, seconds=0.0, complete=True)
    started = time.perf_counter()
    for number in range(0, len(jobs), chunk):
        block = jobs[number:number + chunk]
        name = results / f'v-{number // chunk:05d}.json'
        stats['chunks'] += 1
        if max_chunks and stats['new_chunks'] >= max_chunks and not name.exists():
            stats['complete'] = False
            stats['chunks'] -= 1
            break
        if name.exists():
            saved = json.loads(bounded_read(name, 64 * 1024**2))
            if saved.get('plan') != digest_all or saved.get('start') != number:
                raise ValueError('Existing vertex chunk belongs to another plan; use a fresh output')
            stats['reused_chunks'] += 1
            stats['compiled'] += sum(1 for row in saved['rows'] if row[2])
            continue
        if poll:
            poll()
        batch = [dict(sha256=d, gpu=g, program=read_vertex(inventory[d], d)) for d, g in block]

        def ready(job, source, code_id, code):
            save_code(cache / (source + '.dxbc'), code)

        compiled, failures, report = compile_jobs(batch, decoder, output / 'work' / f'vertex-{number // chunk:05d}',
                                                  derive=True, workers=workers, on_ready=ready, poll=poll)
        rows = [[d, g, compiled[(d, g)][0] if (d, g) in compiled else None,
                 compiled[(d, g)][1] if (d, g) in compiled else None] for d, g in block]
        write_atomic(name, dict(schema=SCHEMA, kind='vertex', plan=digest_all, start=number, rows=rows))
        stats['new_chunks'] += 1
        stats['compiled'] += len(compiled)
        stats['failed'] += len(failures)
        log(f'vertex chunk {number // chunk + 1}/{-(-len(jobs) // chunk)}: {len(compiled)} compiled, '
            f'{len(failures)} failed, {time.perf_counter() - started:.0f}s')
    stats['seconds'] = time.perf_counter() - started
    return stats


def load_key_memo(output):
    """(identity, profile tuple) -> ps source key from every finished fragment chunk."""
    memo = {}
    for path in sorted((Path(output) / 'results').glob('f-*.json')):
        for identity, _, profile, key, _, _ in json.loads(bounded_read(path, 64 * 1024**2))['rows']:
            if key:
                memo[(identity, tuple(profile))] = key
    return memo


def load_vertex_memo(output):
    """(vertex program sha256, gpu) -> (source key, code id) from finished vertex chunks."""
    memo = {}
    for path in sorted((Path(output) / 'results').glob('v-*.json')):
        for digest, gpu, source, code in json.loads(bounded_read(path, 64 * 1024**2))['rows']:
            if source:
                memo[(digest, gpu)] = (source, code)
    return memo


def vertex_recall(records, memo):
    """Do the enumerated vertex variants contain every observed (vertex source key, bytecode id)?

    Counted per distinct observed variant (program, gpu mode). A variant is covered when its source key is
    among the enumerated ones; a program shorter than its wrapper (prefix upload) is still found by key.
    """
    produced = {source for source, _ in memo.values()}
    seen = {}
    for r in records:
        seen[(r['vp']['sha256'], r['vp_gpu'])] = (r['vp_source'], r['vs'])
    covered = {k: v for k, v in seen.items() if v[0] in produced}
    direct = sum(1 for k in seen if k in memo)
    return dict(observed_variants=len(seen), covered_by_key=len(covered), covered_same_program=direct,
                by_gpu={str(g): [sum(1 for k, v in seen.items() if k[1] == g and v[0] in produced),
                                  sum(1 for k in seen if k[1] == g)] for g in (0, 1)},
                bytecode_matches=sum(1 for k, v in covered.items() if any(m[1] == v[1] for m in memo.values() if m[0] == v[0])),
                enumerated_variants=len(memo), enumerated_distinct_sources=len(produced))


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _paths(a):
    out = Path(a.output).resolve()
    return out, out / 'index'


def _load_inventories(a, need_materials=True):
    out, index = _paths(a)
    fragments = json.loads(bounded_read(index / 'fragments.json', 64 * 1024**2))
    materials = _load_materials(json.loads(bounded_read(index / 'materials.json', 512 * 1024**2))) if need_materials else {}
    return fragments, materials


def cmd_inventory(a):
    out, index = _paths(a)
    index.mkdir(parents=True, exist_ok=True)
    files = container_files(a.catalog)
    started = time.perf_counter()
    fragments, failed = fragment_inventory(a.catalog, print)
    write_atomic(index / 'fragments.json', fragments)
    print(f'fragments: {len(fragments)} program identities from {sum(map(len, fragments.values()))} payloads '
          f'({len(failed)} rejected)', flush=True)
    vertices = vertex_inventory(files, print)
    write_atomic(index / 'vertices.json', vertices)
    print(f'vertices: {len(vertices)} distinct programs', flush=True)
    materials = material_index(files, print)
    write_atomic(index / 'materials.json', _dump_materials(materials))
    print(f'materials: {len(materials)} programs ({sum(1 for m in materials.values() if m["complete"])} with a complete '
          f'local vector) in {time.perf_counter() - started:.0f}s', flush=True)


def _parse_msaa(text):
    values = sorted({int(v) for v in text.split(',') if v.strip()} - {0, 1}) if text else None
    if values is not None and any(v not in (2, 4, 8) for v in values):
        raise ValueError('--msaa takes sample counts 2, 4 or 8')
    return values


def _template(a):
    from pipeline_template import read as read_template
    return read_template(Path(a.template))['records']


def _make_infos(fragments, materials, scope):
    return {identity: program_info(identity, fragments, materials) for identity in scope}


def cmd_plan(a):
    out, index = _paths(a)
    fragments, materials = _load_inventories(a)
    records = _template(a)
    msaa = _parse_msaa(a.msaa)
    rows = template_rows(records, fragments, materials)
    scope = set(fragments) if a.scope == 'catalogue' else {identity for identity, *_ in rows}
    infos = _make_infos(fragments, materials, set(fragments))
    contexts = train_contexts(rows, infos)
    jobs = fragment_jobs_for(infos, fragments, contexts, scope, msaa, a.context_cap, a.fallback_locals, a.local_cap)
    write_atomic(out / 'plan.json', dict(schema=SCHEMA, scope=a.scope, msaa=msaa, context_cap=a.context_cap,
                                          fallback_locals=a.fallback_locals, local_cap=a.local_cap,
                                          jobs=[[i, p, list(prof)] for i, p, prof in jobs]))
    sources = Counter(infos[i]['source'] for i in scope)
    print(json.dumps(dict(scope_programs=len(scope), jobs=len(jobs), per_program=len(jobs) / max(1, len(scope)),
                          program_sources=dict(sources), contexts={str(k): len(v) for k, v in contexts.by_types.items()})))


def cmd_compile(a):
    out, index = _paths(a)
    plan = json.loads(bounded_read(out / 'plan.json', 1024**3))
    jobs = [(i, p, tuple(prof)) for i, p, prof in plan['jobs']]
    stop = lambda: (_ for _ in ()).throw(KeyboardInterrupt('stop file present')) if stop_requested() else None
    report = {}
    if not a.vertex_only:
        report['fragment'] = compile_fragments_chunked(jobs, out, a.catalog, Path(a.engine).resolve(),
                                                       Path(a.game_root).resolve(), a.chunk, poll=stop,
                                                       max_chunks=a.max_chunks)
    if not a.fragment_only:
        vertices = json.loads(bounded_read(index / 'vertices.json', 64 * 1024**2))
        selected = sorted(vertices)[:a.vertex_limit] if a.vertex_limit else sorted(vertices)
        report['vertex'] = compile_vertices(vertices, selected, out, Path(a.decoder).resolve(), workers=a.workers,
                                            poll=stop, max_chunks=a.max_chunks)
    write_atomic(out / f'compile-report-{int(time.time())}.json', report)
    print(json.dumps(report))


def cmd_recall(a):
    out, index = _paths(a)
    fragments, materials = _load_inventories(a)
    records = _template(a)
    msaa = _parse_msaa(a.msaa)
    rows = template_rows(records, fragments, materials)
    infos = _make_infos(fragments, materials, {identity for identity, *_ in rows})
    memo = load_key_memo(out) if a.keys else None
    key_of = (lambda i, p: memo.get((i, p))) if memo is not None else None
    split = []
    train, test = split_by_program(rows, a.seed)
    split.append(('program-split seed=%s (50%%)' % a.seed, train, test))
    if a.provenance:
        labels = json.loads(bounded_read(Path(a.provenance), 64 * 1024**2))
        for name, before, after in json.loads(a.content_splits):
            tr = [r for r in rows if labels.get(r[3]) in set(before)]
            te = [r for r in rows if labels.get(r[3]) in set(after)]
            split.append((name, tr, te))
    for name, tr, te in split:
        report = evaluate(tr, te, infos, key_of, msaa, a.context_cap, a.fallback_locals, a.local_cap)
        print(name, json.dumps(report, sort_keys=True))
    if a.vertex:
        print('vertex', json.dumps(vertex_recall(records, load_vertex_memo(out)), sort_keys=True))


def cmd_report(a):
    out, _ = _paths(a)
    memo = load_key_memo(out)
    cache = out / 'shadercache'
    files = list(cache.glob('*.dxbc')) if cache.exists() else []
    print(json.dumps(dict(fragment_results=len(memo), distinct_fragment_keys=len(set(memo.values())),
                          dxbc_files=len(files), dxbc_bytes=sum(f.stat().st_size for f in files))))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='command', required=True)

    def common(p):
        p.add_argument('--output', required=True, help='Private ignored directory')
        p.add_argument('--catalog', help='Catalogue folder: *.fp named by SHA-256 plus index.json')
        p.add_argument('--template', help='Starter template bundle (observed contexts)')

    def model(p):
        p.add_argument('--msaa', default='2,4', help='Nonzero MSAA sample counts to enumerate (setting axis)')
        p.add_argument('--context-cap', type=int, default=None, help='Most common N contexts per program')
        p.add_argument('--local-cap', type=int, default=None)
        p.add_argument('--fallback-locals', type=int, default=4, help='Donor local vectors for programs with no usable material')

    p = sub.add_parser('inventory'); common(p)
    p = sub.add_parser('plan'); common(p); model(p)
    p.add_argument('--scope', choices=('observed', 'catalogue'), default='observed')
    p = sub.add_parser('compile'); common(p)
    p.add_argument('--engine'); p.add_argument('--decoder'); p.add_argument('--game-root')
    p.add_argument('--chunk', type=int, default=1024)
    p.add_argument('--max-chunks', type=int, default=0, help='Stop after this many new chunks (resume later)')
    p.add_argument('--workers', type=int, default=None)
    p.add_argument('--vertex-limit', type=int, default=0)
    p.add_argument('--fragment-only', action='store_true'); p.add_argument('--vertex-only', action='store_true')
    p = sub.add_parser('recall'); common(p); model(p)
    p.add_argument('--seed', type=int, default=0x47543550)
    p.add_argument('--keys', action='store_true', help='Also score exact ps keys from finished compile chunks')
    p.add_argument('--vertex', action='store_true', help='Also score observed vertex variants against finished vertex chunks')
    p.add_argument('--provenance', help='JSON: record key -> label (content splits)')
    p.add_argument('--content-splits', default='[]', help='JSON [[name,[train labels],[test labels]],...]')
    p = sub.add_parser('report'); common(p)
    a = ap.parse_args(argv)
    {'inventory': cmd_inventory, 'plan': cmd_plan, 'compile': cmd_compile, 'recall': cmd_recall, 'report': cmd_report}[a.command](a)


if __name__ == '__main__':
    main()
