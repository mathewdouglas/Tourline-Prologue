"""Compile every unique starter fragment profile with the private engine.

RSX_FP_SAMPLE_SHARE is set only for --mode on, and only after offline_env
clears inherited renderer settings. Counts go to the output JSON. Shader
bytes stay in the scratch cache.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
from shader_coverage import fnv64, fp_identity
from prepare_material_shaders import fragment_profile
import shader_fragment_batch
import shader_reconstruct


def load_records(template):
    records = []
    for part in sorted(Path(template).glob('part-*.json')):
        document = json.loads(part.read_text(encoding='utf-8'))
        records.extend(document['records'])
    return records


def install_mode(mode):
    original_env = shader_fragment_batch.offline_env
    original_run = shader_fragment_batch.run_offline

    def offline_env(game_root, cache):
        env = original_env(game_root, cache)
        env.pop('RSX_FP_SAMPLE_SHARE', None)
        if mode == 'off':
            env['RSX_FP_SAMPLE_SHARE'] = '0'
        return env

    def run_offline(engine, game_root, env, log, timeout=180):
        return original_run(engine, game_root, env, log, timeout=3600)

    shader_fragment_batch.offline_env = offline_env
    shader_fragment_batch.run_offline = run_offline
    shader_reconstruct.offline_env = offline_env
    shader_reconstruct.run_offline = run_offline


def volume_programs(records, player_map, volume_map, volume, elf, volume_library):
    """Bytes for every starter fragment, checked against fp_identity().

    The starter stores that normalized identity. Catalogue filenames are the
    raw SHA-256, and 215 of these 1,404 identities are not in the local
    catalogue, so the verified player-map offsets in the original volume are
    the complete source. Nothing is written back to the game.
    """
    from game_volume import read as read_volume
    from game_volume import resolve
    from pipeline_asset_map import read as read_map
    wanted = {('fp', record['fp']['sha256'], record['fp']['size']) for record in records}
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY'] = str(volume_library)
    try:
        _vertices, fragments, stats = resolve(
            read_map(player_map), read_volume(volume_map), volume, elf, wanted)
    finally:
        os.environ.pop('GT5P_PREPARE_VOLUME_LIBRARY', None)
    if set(fragments) != {item[1] for item in wanted}:
        raise ValueError('Volume resolve did not return every starter fragment')
    print(f"volume programs {stats['programs_found']} in {stats['seconds']:.1f}s", flush=True)
    return fragments


def jobs_for(records, programs):
    chosen = {}
    expected = {}
    for record in records:
        raw = programs[record['fp']['sha256']]
        digest = hashlib.sha256(raw).hexdigest()
        job = dict(id='pending', fragment=raw, fragment_sha256=digest, state=record['state'],
                   used=fp_identity(raw)['textures'])
        profile = fragment_profile(job)
        identity = hashlib.sha256(repr((digest, profile)).encode()).hexdigest()
        job['id'] = identity
        chosen.setdefault(identity, job)
        expected.setdefault(identity, set()).add((record['fp_source'], record['ps']))
    return list(chosen.values()), expected


def summarize(mode, jobs, expected, compiled, failures, started, output):
    sources = sorted({key for key, _blob in compiled.values()})
    bytecode = sorted({f'{fnv64(blob):016x}' for _key, blob in compiled.values()})
    source_match = ps_match = singleton = 0
    for identity, pairs in expected.items():
        if identity not in compiled:
            continue
        key, blob = compiled[identity]
        code = f'{fnv64(blob):016x}'
        if len(pairs) == 1:
            singleton += 1
            source, ps = next(iter(pairs))
            source_match += source == key
            ps_match += ps == code
    summary = dict(mode=mode, unique_requests=len(jobs), compiled=len(compiled), failed=len(failures),
                   distinct_source_keys=len(sources), distinct_bytecode_keys=len(bytecode),
                   template_singleton_profiles=singleton, template_source_matches=source_match,
                   template_bytecode_matches=ps_match, seconds=round(time.perf_counter() - started, 3),
                   failure_samples=sorted(set(failures.values()))[:8])
    Path(output).write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(summary, indent=2))
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--mode', choices=('off', 'on'), required=True)
    ap.add_argument('--engine', type=Path, required=True)
    ap.add_argument('--game-root', type=Path, required=True)
    ap.add_argument('--player-map', type=Path, required=True)
    ap.add_argument('--volume-map', type=Path, required=True)
    ap.add_argument('--volume', type=Path, required=True)
    ap.add_argument('--elf', type=Path, required=True)
    ap.add_argument('--volume-library', type=Path, required=True)
    ap.add_argument('--template', type=Path, required=True)
    ap.add_argument('--cache', type=Path, required=True)
    ap.add_argument('--work', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    for path in (args.cache, args.work, args.output.parent):
        resolved = path.resolve()
        scratch = (ROOT / 'scratch').resolve()
        if resolved != scratch and scratch not in resolved.parents:
            raise ValueError('Batch cache, work, and summary must stay under scratch')
    started = time.perf_counter()
    records = load_records(args.template)
    programs = volume_programs(records, args.player_map, args.volume_map, args.volume, args.elf, args.volume_library)
    jobs, expected = jobs_for(records, programs)
    print(f'starter records {len(records)}; unique fragment profiles {len(jobs)}', flush=True)
    install_mode(args.mode)
    args.cache.mkdir(parents=True, exist_ok=True)
    args.work.mkdir(parents=True, exist_ok=True)
    # Inherited renderer switches must not reach the compiler. offline_env drops them;
    # the mode hook above is the only place RSX_FP_SAMPLE_SHARE is put back.
    os.environ.pop('RSX_FP_SAMPLE_SHARE', None)
    compiled, failures = shader_fragment_batch.compile_batch(
        jobs, args.work, args.cache, args.engine, args.game_root, translation='default', batch_size=4096)
    summary = summarize(args.mode, jobs, expected, compiled, failures, started, args.output)
    if failures or summary['compiled'] != summary['unique_requests']:
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
