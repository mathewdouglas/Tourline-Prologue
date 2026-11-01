"""Require a built Windows executable to carry the multi-size player icon.

Reads the PE resource directory only. Does not launch the program.
"""
import struct
import sys
from pathlib import Path


def u16(data, offset):
    return struct.unpack_from('<H', data, offset)[0]


def u32(data, offset):
    return struct.unpack_from('<I', data, offset)[0]


def section_offset(data, rva, sections):
    for virtual, raw, raw_size in sections:
        if virtual <= rva < virtual + raw_size:
            return raw + (rva - virtual)
    raise ValueError('Resource address is outside the executable sections')


def resource_blobs(data, type_id):
    if data[:2] != b'MZ':
        raise ValueError('Expected a Windows executable')
    pe = u32(data, 0x3C)
    if data[pe:pe + 6] != b'PE\0\0\x64\x86':
        raise ValueError('Expected a Windows x64 executable')
    section_count = u16(data, pe + 6)
    optional_size = u16(data, pe + 20)
    optional = pe + 24
    if u16(data, optional) != 0x20B:
        raise ValueError('Expected a PE32+ optional header')
    resource_rva = u32(data, optional + 112 + 2 * 8)
    resource_size = u32(data, optional + 112 + 2 * 8 + 4)
    if resource_rva == 0 or resource_size == 0:
        raise ValueError('Executable has no resource directory')
    sections = []
    entry = optional + optional_size
    for _ in range(section_count):
        virtual = u32(data, entry + 12)
        raw_size = u32(data, entry + 16)
        raw = u32(data, entry + 20)
        sections.append((virtual, raw, max(raw_size, u32(data, entry + 8))))
        entry += 40

    def walk(offset, remaining):
        if remaining == 0:
            return
        named = u16(data, offset + 12)
        ids = u16(data, offset + 14)
        cursor = offset + 16
        entries = []
        for index in range(named + ids):
            name = u32(data, cursor)
            link = u32(data, cursor + 4)
            entries.append((index >= named, name, link))
            cursor += 8
        for is_id, name, link in entries:
            child = section_offset(data, resource_rva + (link & 0x7FFFFFFF), sections)
            if link & 0x80000000:
                if is_id and name == type_id and remaining == 3:
                    yield from walk(child, 2)
                elif remaining < 3:
                    yield from walk(child, remaining - 1)
            elif remaining == 1:
                blob_rva = u32(data, child)
                blob_size = u32(data, child + 4)
                start = section_offset(data, blob_rva, sections)
                yield data[start:start + blob_size]

    yield from walk(section_offset(data, resource_rva, sections), 3)


def icon_count(path):
    data = Path(path).read_bytes()
    groups = list(resource_blobs(data, 14))
    icons = list(resource_blobs(data, 3))
    if len(groups) != 1 or len(groups[0]) < 6:
        raise ValueError(f'{path} is missing its icon group')
    count = u16(groups[0], 4)
    if count < 7 or len(icons) < count:
        raise ValueError(f'{path} icon has {count} images and {len(icons)} payloads; expected at least 7')
    return count


def main():
    if len(sys.argv) < 2:
        raise SystemExit('Usage: exe_icon.py executable [executable...]')
    for path in sys.argv[1:]:
        print(f'{path}: {icon_count(path)} icon images')


if __name__ == '__main__':
    main()
