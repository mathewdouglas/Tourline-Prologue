"""Optional final preparation stage: shader-interpreter pipelines (Phase 220).

Runs the installed engine once, offline (no guest entry), with the interpreter
configured and RSX_SHADER_INTERP_PIPELINE_PREP=sync. The engine maps its
embedded starter classes to the player's MSAA / colour precision / anisotropy,
creates each paired generic pipeline on this GPU and driver, and persists the
driver blob as ipso_<hash>.bin in the given cache (same header/size/checksum
validation as other pipeline blobs; the driver itself rejects a foreign blob).

This stage is separate from shader preparation: it never changes the
preparation token, the prepared shaders, native pipeline blobs, packs or the
cache selection, and its result lives in its own interp-pipelines.json. It is
cheap (seconds to about 15 s cold) and is skipped, not failed, when the engine
was built without the interpreter (released engines) or the settings cannot be
read safely; the game's own startup step covers those cases when the
interpreter is enabled. GT5P_PREPARE_INTERP_PIPELINES=0 skips it.
"""
import json
import os
from pathlib import Path
import re
import time

from interp_pipeline_classes import base_classes, load_template, map_settings, player_settings, digest

LINE = re.compile(r'\[interp-prep\] version=1 mode=sync ([^\r\n]+)')
UNAVAILABLE = ('[interp-prep] unavailable', '[interp-prep] skipped')
REPORT = 'interp-pipelines.json'


def enabled(environ=None):
    value = (os.environ if environ is None else environ).get('GT5P_PREPARE_INTERP_PIPELINES', '1')
    if value not in ('0', '1'):
        raise ValueError('GT5P_PREPARE_INTERP_PIPELINES must be unset, 0 or 1')
    return value == '1'


def engine_env(base, settings):
    msaa, high_precision, anisotropy = settings
    env = dict(base)
    # No recipe replay, no other batch: this run only prepares the interpreter classes.
    for key in ('RSX_PSO_PREPARE_BATCH', 'RSX_PSO_TEMPLATE_PREPARE', 'RSX_SHADER_LIBRARY_BATCH',
                'RSX_PSO_PREPARE_REQUESTS', 'RSX_PSO_PREPARE_RESULTS'):
        env.pop(key, None)
    # RSX_SHADER_WARMUP=1 keeps the offline startup barrier (device init before exit); the recipe replay
    # itself stays off (GT5P_PREPARE_OFFLINE_WARMUP=0).
    env.update(RSX_SHADER_WARMUP='1', GT5P_PREPARE_OFFLINE_WARMUP='0',
               RSX_SHADER_INTERP='1', RSX_SHADER_INTERP_VP='1', RSX_SHADER_INTERP_PIPELINE_PREP='sync',
               RSX_SHADER_INTERP_PSO_DISK='1', RSX_SHADER_INTERP_PSO_ASYNC='0',
               RSX_MSAA=str(msaa), RSX_HIGH_PRECISION='1' if high_precision else '0', RSX_ANISO=str(anisotropy))
    return env


def parse(text):
    found = LINE.findall(text)
    if len(found) != 1:
        return None
    fields = dict(re.findall(r'(\w+)=([0-9a-f]+)', found[0]))
    numeric = {k: int(v) for k, v in fields.items() if k != 'identity' and v.isdigit()}
    if not re.fullmatch('[0-9a-f]{16}', fields.get('identity', '')):
        raise ValueError('Interpreter preparation identity missing')
    numeric['identity'] = fields['identity']
    return numeric


def prepare(engine, game_root, cache, storage, template, output, base_env, runner, progress=None, timeout=900):
    """Returns the stage report (also written to output/interp-pipelines.json). Never raises for skips."""
    started = time.perf_counter()
    report = dict(schema=1, stage='interpreter-pipelines', status='skipped')
    path = Path(output) / REPORT
    def finish():
        report['seconds'] = round(time.perf_counter() - started, 3)
        path.write_text(json.dumps(report, indent=1, sort_keys=True), encoding='utf-8')
        return report
    if not enabled():
        report['reason'] = 'GT5P_PREPARE_INTERP_PIPELINES=0'
        return finish()
    settings = player_settings(storage)
    if settings is None:
        report['reason'] = 'Settings not safely readable; the game prepares them at startup when the interpreter is on.'
        return finish()
    rows = base_classes(load_template(template))
    expected = len(map_settings(rows, settings[0], settings[1], True))
    report.update(settings=dict(msaa=settings[0], high_precision=settings[1], anisotropy=settings[2]),
                  classes=len(rows), classes_sha256=digest(rows), expected_pipelines=expected)
    if progress:
        progress('interpreter-pipelines', dict(completed=0, total=expected))
    log = Path(output) / 'interp-pipelines.log'
    text = runner(engine, game_root, engine_env(base_env, settings), log, timeout=timeout)
    result = parse(text)
    if result is None:
        if any(marker in text for marker in UNAVAILABLE) or '[interp-prep]' not in text:
            report['reason'] = 'This engine has no shader-interpreter class preparation.'
            return finish()
        raise ValueError('Interpreter pipeline preparation was not confirmed; see ' + str(log))
    report['engine'] = result
    if result.get('pipelines') != expected:
        raise ValueError(f"Interpreter pipelines {result.get('pipelines')} differ from the derived {expected}")
    if result.get('complete') != 1 or result.get('failed') or result.get('ready') != expected:
        raise ValueError('Interpreter pipelines incomplete; prepared shaders unchanged. See ' + str(log))
    marker = Path(cache) / f"ipso-set-{result['identity']}.txt"
    if result.get('persisted') == 1 and not marker.is_file():
        raise ValueError('Interpreter pipeline set marker missing')
    report['status'] = 'complete'
    if progress:
        progress('interpreter-pipelines', dict(completed=expected, total=expected))
    return finish()
