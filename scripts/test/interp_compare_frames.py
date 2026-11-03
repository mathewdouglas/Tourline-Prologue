"""Quantify adjacent specialized/interpreted backbuffer captures.

Run under the test lock. Adjacent moving scenes are not equivalent inputs;
whole-frame differences describe the captures, not an interpreter error bound.
The fixed title crop is reported separately. No screenshots enter git.
"""
import argparse
import json
from pathlib import Path
import struct


def read_bmp(path: Path) -> tuple:
    data = path.read_bytes()
    if data[:2] != b"BM" or len(data) < 54:
        raise ValueError("not a complete BMP")
    offset = struct.unpack_from("<I", data, 10)[0]
    width, height, planes, bits, compression = struct.unpack_from("<iiHHI", data, 18)
    if not 0 < width <= 16384 or not 0 < abs(height) <= 16384 or planes != 1 or bits != 24 or compression:
        raise ValueError("expected the renderer's uncompressed 24-bit BMP")
    pitch = (width * 3 + 3) & ~3
    if offset + pitch * abs(height) != len(data):
        raise ValueError("incomplete BMP pixel data")
    rows = range(abs(height) - 1, -1, -1) if height > 0 else range(-height)
    return width, abs(height), b"".join(data[offset + y*pitch:offset + y*pitch + width*3] for y in rows)


def crop(image: tuple, rect: tuple) -> bytes:
    width, height, pixels = image
    x0, y0, x1, y1 = rect
    if not 0 <= x0 < x1 <= width or not 0 <= y0 < y1 <= height:
        raise ValueError("crop outside image")
    return b"".join(pixels[(y*width+x0)*3:(y*width+x1)*3] for y in range(y0, y1))


def metrics(a: bytes, b: bytes) -> dict:
    total = maximum = changed = 0
    for i in range(0, len(a), 3):
        x, y, z = abs(a[i]-b[i]), abs(a[i+1]-b[i+1]), abs(a[i+2]-b[i+2])
        total += x+y+z
        maximum = max(maximum, x, y, z)
        changed += bool(x or y or z)
    return {"mean_abs_0_255": total / len(a), "max_abs_0_255": maximum,
            "changed_percent": 300 * changed / len(a)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("directory", type=Path)
    a = p.parse_args()
    directory = a.directory.resolve()
    scratch = Path(__file__).resolve().parents[2] / "scratch"
    if not directory.is_relative_to(scratch.resolve()):
        p.error("capture directory must be in this worktree's scratch")
    paths = sorted(directory.glob("*.bmp"), key=lambda path: int(path.stem.rsplit("_", 1)[1]))
    rows = []
    for one, two in zip(paths, paths[1:]):
        if one.stem.split("_")[0] == two.stem.split("_")[0]:
            continue
        rgb1, rgb2 = read_bmp(one), read_bmp(two)
        if rgb1[:2] != rgb2[:2]:
            raise ValueError("capture sizes differ")
        rows.append({"a": one.name, "b": two.name, "frame": metrics(rgb1[2], rgb2[2]),
                     "title_crop_60_40_365_70": metrics(crop(rgb1, (60, 40, 365, 70)), crop(rgb2, (60, 40, 365, 70)))})
    if not rows:
        raise ValueError("no adjacent specialized/interpreter pairs")
    (directory / "differences.json").write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
