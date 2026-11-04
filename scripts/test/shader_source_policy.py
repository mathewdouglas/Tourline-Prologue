"""Rollback switches for the cheaper shader text: helper policy, offline environment and generation token."""
import os
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts'))
import shader_source_policy as policy


def raises(function):
    try:
        function()
    except ValueError:
        return True
    return False


assert policy.overlay({}) == {} and policy.marker({}) == ''
assert policy.overlay({'GT5P_PREPARE_VFETCH_LOOP': '0'}) == {'RSX_VFETCH_LOOP': '0'}
assert policy.overlay({'GT5P_PREPARE_FP_REG_SIZE': '0'}) == {'RSX_FP_REG_SIZE': '0'}
assert policy.overlay({'GT5P_PREPARE_FP_REG_SIZE': '1'}) == {}
assert policy.overlay({'GT5P_PREPARE_FP_GAMMA_LAZY': '0'}) == {'RSX_FP_GAMMA_LAZY': '0'}
assert policy.overlay({'GT5P_PREPARE_FP_GAMMA_LAZY': '1'}) == {}
both = {'GT5P_PREPARE_VFETCH_LOOP': '1', 'GT5P_PREPARE_FP_REG_SIZE': '0'}
assert policy.overlay(both) == {'RSX_FP_REG_SIZE': '0', 'RSX_VFETCH_LOOP': '1'}
assert policy.marker(both) == 'RSX_FP_REG_SIZE=0;RSX_VFETCH_LOOP=1;'
for name in ('GT5P_PREPARE_VFETCH_LOOP', 'GT5P_PREPARE_FP_REG_SIZE', 'GT5P_PREPARE_FP_GAMMA_LAZY'):
    for bad in ('', '3', 'yes', ' 0'):
        assert raises(lambda: policy.overlay({name: bad})), (name, bad)

# Offline environment: inherited RSX_* values are stripped, only the explicit helper switches reach the engine.
import shader_reconstruct
clean = {key: value for key, value in os.environ.items() if not key.startswith(('GT5P_PREPARE_VFETCH', 'GT5P_PREPARE_FP_REG', 'RSX_VFETCH', 'RSX_FP_REG', 'RSX_FP_GAMMA', 'GT5P_PREPARE_FP_GAMMA'))}
with patch.dict(os.environ, clean, clear=True):
    env = shader_reconstruct.offline_env(Path('game'), Path('cache'))
    assert 'RSX_VFETCH_LOOP' not in env and 'RSX_FP_REG_SIZE' not in env and 'RSX_FP_GAMMA_LAZY' not in env
with patch.dict(os.environ, dict(clean, RSX_VFETCH_LOOP='1', RSX_FP_REG_SIZE='0', RSX_FP_GAMMA_LAZY='0'), clear=True):
    env = shader_reconstruct.offline_env(Path('game'), Path('cache'))
    assert 'RSX_VFETCH_LOOP' not in env and 'RSX_FP_REG_SIZE' not in env and 'RSX_FP_GAMMA_LAZY' not in env, 'inherited renderer values must not leak'
with patch.dict(os.environ, dict(clean, GT5P_PREPARE_VFETCH_LOOP='0', GT5P_PREPARE_FP_REG_SIZE='0'), clear=True):
    env = shader_reconstruct.offline_env(Path('game'), Path('cache'))
    assert env['RSX_VFETCH_LOOP'] == '0' and env['RSX_FP_REG_SIZE'] == '0'

# Generation token: unchanged by default, different for each rollback.
import player_prepare
args = ('m', 'e', 'd', False)
with patch.dict(os.environ, clean, clear=True):
    base = player_prepare.preparation_token(*args)
    assert base == player_prepare.preparation_token(*args)
tokens = {base}
for extra in ({'GT5P_PREPARE_VFETCH_LOOP': '0'}, {'GT5P_PREPARE_VFETCH_LOOP': '1'}, {'GT5P_PREPARE_FP_REG_SIZE': '0'},
              {'GT5P_PREPARE_VFETCH_LOOP': '0', 'GT5P_PREPARE_FP_REG_SIZE': '0'}, {'GT5P_PREPARE_FP_GAMMA_LAZY': '0'}):
    with patch.dict(os.environ, dict(clean, **extra), clear=True):
        tokens.add(player_prepare.preparation_token(*args))
assert len(tokens) == 6
print('shader source policy passed')
