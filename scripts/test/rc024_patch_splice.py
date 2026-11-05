"""Splice a regenerated per-file section into the main runtime patch (maintainer helper).

usage: rc024_patch_splice.py <scratch-repo> <patch> <file> [<file>...]
The scratch repo is a clean `git archive 4e8f3ca8` export of the pinned runtime with
the patch applied and then edited; only the named files' sections are replaced.
"""
import subprocess
import sys
from pathlib import Path


def sections(data):
    marker = b'diff --git a/'
    starts = [i for i in range(len(data)) if data.startswith(marker, i) and (i == 0 or data[i-1:i] == b'\n')]
    starts.append(len(data))
    return [(data[a:data[a:].index(b'\n') + a], a, b) for a, b in zip(starts, starts[1:])]


def main():
    repo, patch, *files = sys.argv[1:]
    patch = Path(patch)
    data = patch.read_bytes()
    for name in files:
        subprocess.run(['git', '-C', repo, 'add', name], check=True)
        new = subprocess.run(['git', '-C', repo, 'diff', '--binary', '--cached', '--abbrev=8', 'HEAD', '--', name],
                             check=True, capture_output=True).stdout
        head = b'diff --git a/' + name.encode() + b' b/' + name.encode()
        hit = [(a, b) for line, a, b in sections(data) if line.startswith(head)]
        if len(hit) != 1:
            raise SystemExit(f'{name}: {len(hit)} sections in {patch}')
        a, b = hit[0]
        data = data[:a] + new + data[b:]
    patch.write_bytes(data)


if __name__ == '__main__':
    main()
