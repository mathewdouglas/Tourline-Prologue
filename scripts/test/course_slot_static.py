"""Static checks for course-slot selection and provenance paths.

Does not launch the game, build, compile, or start a process.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from train_pipeline_cache import (COURSE_SLOT_MAX, MEASURED_COURSE_SLOTS, PROVENANCE_LIMIT,
                                  provenance_directory, resolve_routes, template_destination)


def expect_error(func):
    try:
        func()
    except ValueError:
        return
    raise SystemExit('expected a ValueError')


def main():
    default = resolve_routes(None, None)
    if [item['label'] for item in default] != ['HighSpeedRing', 'Daytona']:
        raise SystemExit('default route order changed')
    if [item['slot'] for item in default] != [0, 1] or any(item['tag_kind'] != 'track' or item['identity'] != 'measured' for item in default):
        raise SystemExit('default routes are no longer the measured named tracks')
    named = resolve_routes(['Daytona'], None)
    if named != [dict(slot=1, label='Daytona', tag_kind='track', identity='measured')]:
        raise SystemExit('single measured track mapping changed')
    slots = resolve_routes(None, [0, 2, 9])
    if [item['slot'] for item in slots] != [0, 2, 9]:
        raise SystemExit('explicit course slots were reordered')
    if slots[0]['label'] != 'HighSpeedRing' or slots[0]['identity'] != 'measured' or slots[0]['tag_kind'] != 'slot':
        raise SystemExit('slot 0 lost its measured name')
    if slots[1]['label'] != 'FujiSpeedwayF' or slots[1]['identity'] != 'measured':
        raise SystemExit('visually verified Fuji Speedway F slot was lost')
    if resolve_routes(['FujiSpeedwayF'],None)!=[dict(slot=2,label='FujiSpeedwayF',tag_kind='track',identity='measured')]:
        raise SystemExit('named Fuji Speedway F route does not select slot 2')
    if slots[2]['label'] != 'slot9':
        raise SystemExit('the experimental ceiling was renamed')
    expect_error(lambda: resolve_routes(['HighSpeedRing'], [2]))
    expect_error(lambda: resolve_routes(None, [10]))
    expect_error(lambda: resolve_routes(None, [1, 1]))
    expect_error(lambda: resolve_routes(None, []))
    expect_error(lambda: resolve_routes(None, [True]))
    if COURSE_SLOT_MAX != 9 or MEASURED_COURSE_SLOTS != {'HighSpeedRing': 0, 'Daytona': 1, 'FujiSpeedwayF': 2}:
        raise SystemExit('measured slot map changed')
    if PROVENANCE_LIMIT != 16384:
        raise SystemExit('provenance limit is not the runtime maximum')
    root = Path(__file__).with_name('course_slot_static_absent')
    if root.exists():
        raise SystemExit('the absent-path fixture must not be created')
    path = provenance_directory(root)
    if path.name != 'provenance' or path.parent != root.resolve():
        raise SystemExit('provenance directory is not owned by the run output')
    if template_destination(root) != root / 'session-template.json':
        raise SystemExit('the first template path changed')
    source = Path(sys.modules['train_pipeline_cache'].__file__).read_text(encoding='utf-8')
    for banned in ('Stop-Stragglers', 'dealer.ps1'):
        if banned in source:
            raise SystemExit('training references a global game terminator')
    for required in ("PS3_VERBOSE='0'", "RSX_PSO_ASYNC='1'", "RSX_SHADER_ASYNC='1'",
                     "RSX_PSO_PROVENANCE='0' if prov is None else str(prov)"):
        if required not in source:
            raise SystemExit('training dropped an existing runtime policy: ' + required)
    print('course slot and provenance helpers ok')


if __name__ == '__main__':
    main()
