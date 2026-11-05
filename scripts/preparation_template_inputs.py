"""Resolve input templates into private, engine-specific preparation outputs."""
from collections import Counter
import time


def successful_inputs(report):
    """Reject incomplete native evidence before exposing its input-to-key map."""
    from pipeline_runtime_coverage import parse_report
    parse_report(report)
    return {r.get('input_key',r['key']):r['key'] for r in report['records'] if r['status'] == 'prepared'}


def resolved_document(document, report):
    """Join local output metadata to inputs; never use template expectations."""
    from pipeline_template_inputs import convert
    mapping = successful_inputs(report)
    expected = {r['key']:r for r in document['records']}
    records = report.get('derived_records',[])
    seen = set()
    for row in records:
        key = row.get('input_key')
        if key in seen or key not in mapping or key not in expected or mapping[key] != row.get('key'):
            raise ValueError('Invalid local input/output derivation')
        seen.add(key)
        old = {k:v for k,v in row.items() if k != 'input_key'}
        legacy = dict(document,version=2,compatibility=dict(document['compatibility'],renderer_sha256='0'*64),records=[old])
        if convert(legacy)['records'] != [expected[key]]:
            raise ValueError('Local derivation changes template inputs')
    if seen != set(mapping):
        raise ValueError('Missing local output derivation')
    return dict(document,records=records)


def prepare(document, template, catalog, elf, engine, decoder, game_root, output,
            asset_map, assets, checkpoint, started, volume, volume_map, vertex_mode,
            reuse_cache=None, reference_template=None, reference_report=None):
    from pipeline_template import locate, template_digest, read, has_flow
    from pipeline_translation import prepare as derive
    from pipeline_template_inputs import reference_outputs, OUTPUTS
    from train_pipeline_cache import save_report
    checkpoint.stage('lookup')
    tick = time.perf_counter()
    vertices, fragments, lookup = locate(document['records'],catalog,elf,asset_map,assets,
                                         volume,volume_map,checkpoint.progress)
    lookup['seconds'] = time.perf_counter()-tick
    ready, missing = [], []
    for row in document['records']:
        if row['vp']['sha256'] in vertices and row['fp']['sha256'] in fragments:
            if has_flow(vertices[row['vp']['sha256']]):
                missing.append(dict(key=row['key'],input_key=row['key'],status='incompatible',
                                    reason='Branching vertex context not supported'))
            else:
                ready.append(row)
        else:
            missing.append(dict(key=row['key'], input_key=row['key'], status='unresolved-program'))
    cache = output/'shadercache'
    cache.mkdir(exist_ok=True)
    def progress(phase, counts):
        if checkpoint.progress:
            checkpoint.progress(phase.removeprefix('translation-'), counts)
    if ready:
        derived = derive(dict(document, records=ready),decoder,engine,game_root,output,
            checkpoint.contract,vertices,fragments,'default',__import__('pipeline_template').run_offline,
            progress,vertex_mode,input_template=True,reuse_cache=reuse_cache)
    else:
        (cache/'warmup-v1').mkdir(exist_ok=True)
        derived = dict(resolved_records=[],records=[],inventory=dict(recipes=[],valid_driver_blobs=[],rejected=[]),
            runtime_lookup_counts=[0]*4,cache_reuse=None,vertex_preparation={},fragment_preparation={},
            native_handoff={},native_timings=[],vertex_variants_reused=0,fragment_jobs_reused=0)
    resolved = dict(document, records=derived['resolved_records'])
    rows = [dict(key=r['key'], input_key=r['template_key'], status='prepared', result=r['result'])
            for r in derived['records']] + missing
    if reference_template is not None or reference_report is not None:
        if reference_template is not None:
            reference = reference_outputs(read(reference_template, legacy=True))
        else:
            import json
            from preparation_reuse import regular_read
            previous = resolved_document(document,json.loads(regular_read(reference_report,128*1024**2)))
            reference = {r['input_key']:{k:r[k] for k in OUTPUTS} for r in previous['records']}
        actual = {proof['template_key']: {k: r[k] for k in OUTPUTS}
                  for proof,r in zip(derived['records'],resolved['records'])}
        if set(reference) != {r['key'] for r in document['records']} or actual != reference:
            raise ValueError('Maintainer reference output regression; cache retained, selection unchanged')
    report = dict(schema=1, template_format=3, template_sha256=template_digest(template),
        engine_sha256=checkpoint.contract['engine'], decoder_sha256=checkpoint.contract['decoder'],
        requested=len(document['records']),records=rows,counts=dict(Counter(r['status'] for r in rows)),
        derived_records=resolved['records'],
        # Phase 221: structural identity of each fragment program (the renderer's fast lookup key; written as a
        # table by fast_lookup_table.py). Hashes only; no program bytes.
        fp_code_identity={sha: f'{__import__("fast_lookup_table").structural_hash(code):016x}'
                          for sha, code in fragments.items()},
        lookup=lookup, inventory=derived['inventory'], cache_reuse=derived['cache_reuse'],
        runtime_lookup_counts=derived['runtime_lookup_counts'],
        native_counts=derived.get('native_counts',[0]*4),
        vertex_preparation=derived['vertex_preparation'],fragment_preparation=derived['fragment_preparation'],
        native_handoff=derived['native_handoff'],native_timings=derived['native_timings'],
        resume=dict(attempt=checkpoint.state['attempt'],vertex_programs_reused=derived['vertex_variants_reused'],
                    fragment_jobs_reused=derived['fragment_jobs_reused']),
        strict_reference=reference_template is not None or reference_report is not None,
        preparation_seconds=time.perf_counter()-started,
        policy='Input identities; local derived keys confirmed by native creation, persistence and fresh-process runtime lookup.')
    save_report(output/'report.json',report)
    checkpoint.stage('complete',counts=report['counts'])
    return report, resolved
