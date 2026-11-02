"""Conservative default selection of existing translation modes for launcher play.

This selects generated shader text only. Template target/MSAA/pass state stays
observed, and root signature stays pinned. Unsupported overrides use the ordinary
default set rather than guessing. No setting or cache is written here.
"""
import hashlib
import os
from pathlib import Path
import tomllib

from pipeline_translation import player_mode
from preparation_reuse import regular_read

MAX_SETTINGS = 64 * 1024
OVERRIDES = ('GT5P_NO_SETTINGS', 'GT5P_RESOLUTION', 'GT5P_ULTRAWIDE',
             'GT5P_RENDER_NATIVE', 'RSX_ULTRAWIDE', 'RSX_RENDER_HEIGHT',
             'RSX_FP_OPT', 'RSX_PSO_KEY_RS', 'RSX_ANISO', 'RSX_HIGH_PRECISION')
LIMIT = 'Translation selection only; other settings, unseen passes and missing states use demand compilation.'


def select(storage, environ=None):
    env = {k.upper(): v for k,v in (os.environ if environ is None else environ).items()}
    requested = env.get('GT5P_PREPARE_TRANSLATION', 'auto')
    result = dict(schema=1, requested=requested, mode='default', source='explicit',
                  settings_sha256=None, limitation=LIMIT)
    if requested != 'auto':
        result['mode'] = player_mode(env)
        return result
    result['source'] = 'launcher-settings'
    overrides = [key for key in OVERRIDES if key in env]
    if overrides:
        result['reason'] = 'Automatic selection does not interpret overrides: '+', '.join(overrides)
        return result
    path = Path(storage)/'gt5p_settings.toml'
    if not str(path).isascii():
        result['reason'] = 'Automatic settings lookup is not validated for non-ASCII storage paths; only default preparation selected.'
        return result
    try:
        payload = regular_read(path, MAX_SETTINGS)
    except FileNotFoundError:
        # The launcher writes its 720p/16:9 first-run preset after the offer.
        result['source'] = 'launcher-first-run-preset'
        result['reason'] = 'No saved settings; the launcher starts at 720p and 16:9.'
        return result
    except (OSError, ValueError):
        result['reason'] = 'Settings were not safely readable; only default preparation selected.'
        return result
    result['settings_sha256'] = hashlib.sha256(payload).hexdigest()
    try:
        document = tomllib.loads(payload.decode('utf-8-sig'))
    except (UnicodeError, tomllib.TOMLDecodeError):
        result['reason'] = 'Invalid settings; only default preparation selected.'
        return result
    video, game = document.get('video', {}), document.get('game', {})
    if not isinstance(video, dict) or not isinstance(game, dict):
        result['reason'] = 'Unsupported settings table shape; only default preparation selected.'
        return result
    resolution, aspect = video.get('resolution', '720p'), video.get('aspect', '16:9')
    heights = {'720p':720, '720':720, '1080p':1080, '1080':1080,
               '1440p':1440, '1440':1440, '2160p':2160, '2160':2160, '4k':2160, '4K':2160}
    if type(resolution) is int:
        height = resolution if resolution in (720,1080,1440,2160) else None
    elif isinstance(resolution,str):
        height = heights.get(resolution)
    else:
        height = None
    if height is None or aspect not in ('16:9','21:9'):
        result['reason'] = 'Unsupported resolution/aspect value; only default preparation selected.'
        return result
    anisotropy, precision = game.get('anisotropy',16), game.get('smooth_colour',True)
    if type(anisotropy) is not int or anisotropy != 16 or precision is not True:
        result['reason'] = 'Automatic preparation currently requires anisotropy 16 and smooth colour enabled.'
        return result
    result.update(resolution=height, aspect=aspect,
                  mode='ultrawide-native' if aspect=='21:9' else 'native-scaled' if height>1080 else 'default')
    result['reason'] = 'Selected from saved launcher resolution/aspect; numeric template state is unchanged.'
    return result


def verify(selection, storage, environ=None):
    """Do not publish a result labelled for settings that changed during the pass."""
    if selection['requested']=='auto' and select(storage,environ)!=selection:
        raise ValueError('Settings changed during preparation; cache selection preserved. Run preparation again.')
