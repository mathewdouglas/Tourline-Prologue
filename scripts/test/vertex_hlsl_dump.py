"""Developer measurement helper: write the decoder's vertex HLSL for a sample of enumeration vertex jobs.

Reads the original packed volume (read-only) exactly like the enumeration stage, translates each sampled
(program, GPU-fetch mode) with the decoder DLL and writes <program-prefix>.<mode>.vs_5_0.hlsl into an
ignored directory. Output is game-derived: keep it under scratch/. Run through run_locked.py.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT/'scripts'))
sys.path[:] = [p for p in sys.path if Path(p or '.').resolve() != ROOT/'scripts/test']


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--inputs', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--sample', type=int, default=150)
    ap.add_argument('--seed', type=int, default=3)
    ap.add_argument('--decoder', type=Path, help='Decoder DLL (default: the reference helper decoder)')
    a = ap.parse_args()
    inputs = json.loads(a.inputs.read_text())
    helper, game, elf = (Path(inputs[k]).resolve() for k in ('reference_helper', 'game', 'elf'))
    os.environ['GT5P_PREPARE_VOLUME_LIBRARY'] = str(helper/'volume_reader.dll')
    import preparation_enumeration as enum
    from game_volume import resolve
    metadata = enum.load(ROOT/'assets/shader-enumeration/gt5p-disc-v1', ROOT/'assets/pipeline-templates/gt5p-disc-v2')
    vertices, _fragments, _stats = resolve(metadata['programs'], metadata['volume'], game/'USRDIR/GT.VOL', elf)
    jobs = [tuple(j) for j in metadata['plan']['vertex_jobs']]
    random.Random(a.seed).shuffle(jobs)
    decoder = ctypes.CDLL(str((a.decoder or helper/'decoder.dll').resolve()))
    for name in ('rsx_vp_decompile', 'rsx_vp_decompile_gpufetch'):
        function = getattr(decoder, name)
        function.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
        function.restype = ctypes.c_int
    a.output.mkdir(parents=True, exist_ok=True)
    written = {0: 0, 1: 0}
    for sha, gpu in jobs:
        if sum(written.values()) >= a.sample:
            break
        data = vertices[sha]
        buffer = ctypes.create_string_buffer(data)
        output = ctypes.create_string_buffer(262144)
        name = 'rsx_vp_decompile_gpufetch' if gpu else 'rsx_vp_decompile'
        count = getattr(decoder, name)(buffer, len(data), output, len(output))
        if count <= 0:
            continue
        (a.output/f'{sha[:16]}.gpu{gpu}.vs_5_0.hlsl').write_bytes(output.value)
        written[gpu] += 1
    print(json.dumps(dict(written=written, programs=len(vertices))))


if __name__ == '__main__':
    main()
