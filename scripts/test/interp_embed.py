"""Embed only original generic interpreter DXBC in a private engine build.

The generated header and bytecode never leave scratch. Rows are pinned to the
exact source/target/flags key used by the runtime; specialized game shaders
cannot enter this table. The normal shader-cache namespace is unchanged.
"""
import ast
import json
from pathlib import Path
import re
import struct
import sys


def source_body(path: Path) -> str:
    return "".join(ast.literal_eval(s) for s in re.findall(r'"(?:\\.|[^"\\])*"', path.read_text(encoding="utf-8")))


def source_key(source: str, target: str) -> int:
    h = 1469598103934665603
    for b in (source + target).encode("ascii"):
        h = ((h ^ b) * 1099511628211) & ((1 << 64) - 1)
    return (h * 1099511628211) & ((1 << 64) - 1)  # flags=0


def generate(video: Path, cache: Path) -> None:
    fp = source_body(video / "rsx_fp_interp_hlsl.inc")
    vp = source_body(video / "rsx_vp_interp_hlsl.inc")
    rows = []
    for full in range(2):
        for sample in range(2):
            for targets in range(1, 5):
                prefix = f"#define RSX_INTERP_FULLIN {full}\n#define RSX_INTERP_SAMPLE {sample}\n"
                if targets > 1:
                    prefix += f"#define RSX_INTERP_MRT 1\n#define RSX_INTERP_TARGETS {targets}\n"
                rows.append((prefix + fp, "ps_5_1"))
    rows += [(f"#define RSX_VP_INTERP_FETCH {fetch}\n" + vp, "vs_5_0") for fetch in range(2)]
    text = ["/* Private build output: original generic interpreters only. Never commit. */"]
    table = []
    total = 0
    for i, (source, target) in enumerate(rows):
        key = source_key(source, target)
        path = cache / f"{key:016x}.dxbc"
        data = path.read_bytes()
        if not 32 <= len(data) <= 256 * 1024 or data[:4] != b"DXBC" or struct.unpack_from("<I", data, 24)[0] != len(data):
            raise ValueError(f"invalid generic DXBC: {path}")
        text.append(f"static const unsigned char rsx_interp_dxbc_{i}[] = {{")
        text += [",".join(f"0x{b:02x}" for b in data[j:j+32]) + "," for j in range(0, len(data), 32)]
        text.append("};")
        table.append(f"    {{rsx_interp_dxbc_{i}, {len(data)}u, 0x{key:016x}ull}},")
        total += len(data)
    text.append("static const struct { const unsigned char* bytes; unsigned size; u64 key; } rsx_interp_embedded[] = {")
    text += table + ["};"]
    # Phase 220: one derivation shared with the preparation helper and its tests.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from interp_pipeline_classes import base_classes, load_template, render_c
    metadata = Path(__file__).resolve().parents[2] / "assets" / "pipeline-templates" / "gt5p-disc-v2"
    classes = base_classes(load_template(metadata))
    text += render_c(classes)
    (video / "rsx_interp_dxbc.inc").write_text("\n".join(text) + "\n", encoding="ascii", newline="\n")
    print(f"embedded {len(rows)} original generic shaders / {total} bytes; {len(classes)} native/input classes", flush=True)
