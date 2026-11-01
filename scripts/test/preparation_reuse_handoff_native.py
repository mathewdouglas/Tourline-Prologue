"""Sequential handoff/rollback reuse proofs in separate empty application caches."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from pipeline_template import prepare, read
from train_pipeline_cache import idle, isolated


def snapshot(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob('*') if p.is_file()}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ('template', 'source-cache', 'elf', 'assets', 'asset-map', 'engine', 'decoder', 'output'):
        ap.add_argument('--' + name, type=Path, required=True)
    a = ap.parse_args()
    idle()
    out = isolated(a.output)
    if out.exists():
        raise ValueError('Use a fresh ignored output; caches are preserved')
    out.mkdir()
    (out/'input').mkdir()
    shutil.copyfile(a.elf, out/'input/EMAIN.ELF')
    document = read(a.template)
    before = snapshot(a.source_cache)
    results = []
    code_sets = []
    for mode in ('0', '1'):
        target = out/('rollback' if mode == '0' else 'handoff')
        with patch.dict(os.environ, GT5P_PREPARE_REUSE_HANDOFF=mode, PS3_VERBOSE='0'):
            report = prepare(a.template.resolve(), None, a.elf.resolve(), a.engine.resolve(),
                a.decoder.resolve(), out, target, assets=a.assets.resolve(),
                asset_map=a.asset_map.resolve(), reuse_cache=a.source_cache.resolve())
        assert report['counts'] == {'prepared': len(document['records'])}
        assert report['cache_reuse']['shader_handoff'] == (mode == '1')
        assert report['resume']['vertex_programs_compiled'] == 0
        assert report['vertex_preparation']['launches'] == 0
        assert report['fragment_preparation']['processes'] == 0
        match = re.search(r'requests=(\d+) created=(\d+) driver_calls=(\d+) cached_blob_calls=(\d+)',
                          (target/'native.log').read_text(errors='replace'))
        assert match and list(map(int, match.groups())) == [len(document['records'])]*4
        assert snapshot(a.source_cache) == before
        code_sets.append({p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in (target/'shadercache').glob('*.dxbc')})
        results.append(dict(handoff=mode == '1', counts=report['counts'],
            cache_reuse=report['cache_reuse'], verification=report['resume'],
            native_counts=list(map(int, match.groups())), seconds=report['preparation_seconds']))
    assert code_sets[0] == code_sets[1]
    result = dict(cases=results, identical_shader_files=True, source_unchanged=True,
                  limitation='Small sequential sample; warm OS/driver caches, no gameplay or speedup claim.')
    (out/'validation.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Handoff and rollback: exact native keys, zero shader compiles, identical shaders and preserved source passed')


if __name__ == '__main__':
    main()
