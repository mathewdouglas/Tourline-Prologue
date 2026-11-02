"""Explicit environment absence composes with LV resources; unknown owners do not."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from shader_material_textures import with_global_sampler_path, complete_sampler_key
from shader_material_profile import shadow_lv_profile
from prepare_material_shaders import enumerate_jobs

material = dict(stencil_enable=0, cull_enable=1, blend=0, cmask=15, depth_bits=0x30000000)
checks = 0
for unit in range(16):
    env = dict(name='envMapSampler', kind=0x901, identifier=71, unit=unit)
    definition = dict(used=1 << unit, bindings=[], globals=[env])
    selected = with_global_sampler_path(definition, environment_resource_path='absent')
    assert complete_sampler_key(selected) == 8 << (unit * 4)
    assert selected['bindings'][0]['texture_facts'] == dict(shape='cube', gamma=False, unnormalized=False)
    assert with_global_sampler_path(definition) is definition
    assert complete_sampler_key(definition) is None
    for change in (dict(name='unknown'), dict(kind=0x601), dict(identifier=115)):
        bad = dict(definition, globals=[dict(env, **change)])
        assert complete_sampler_key(with_global_sampler_path(bad, environment_resource_path='absent')) is None
    for key in ('bindings', 'unresolved'):
        bad = dict(definition, **{key: [dict(unit=unit)]})
        assert complete_sampler_key(with_global_sampler_path(bad, environment_resource_path='absent')) is None
    duplicate = dict(definition, globals=[env, env])
    assert complete_sampler_key(with_global_sampler_path(duplicate, environment_resource_path='absent')) is None
    checks += 1

definition = dict(used=0xf000, bindings=[], globals=[
    dict(name='realTimeShadowMap', kind=0x601, identifier=87, unit=13),
    dict(name='realTimeShadowMapColor', kind=0x601, identifier=96, unit=12),
    dict(name='envMapSampler', kind=0x901, identifier=71, unit=14),
    dict(name='ditherMap', kind=0x801, identifier=103, unit=15)])
selected = with_global_sampler_path(definition, 'active', shadow_path='shadow-lv-depth', environment_resource_path='absent')
profile = shadow_lv_profile(selected, material, 0, 'ccw', 'rgba16-msaa2')
assert profile['shd'] == 0x62000 and profile['ghi'] == 0 and profile['unhi'] == 0x8000
assert profile['cube'] & (1 << 30)
assert len(selected['bindings']) == 4 and not selected['globals']
assert len(definition['globals']) == 4 and not definition['bindings'], 'Input mutated'
# The environment-only choice does not also resolve shadow or mirror ownership.
partial = with_global_sampler_path(definition, environment_resource_path='absent')
assert [g['identifier'] for g in partial['globals']] == [87, 96, 103]

for options in (dict(dynamic_path='absent'), dict(environment_path='framebuffer-single'),
                dict(environment_texture_path='framebuffer-cube'), dict(environment_resource_path='active')):
    try:
        with_global_sampler_path(definition, **dict(dict(environment_resource_path='absent'), **options))
    except ValueError:
        pass
    else:
        raise AssertionError('Conflicting or unsupported environment accepted')
for options in (dict(dynamic_path='absent', environment_resource_path='absent'),
                dict(environment_resource_path='active')):
    try:
        enumerate_jobs(Path('nonexistent-catalog'), 'ccw', 'rgba16-msaa2', 'active', 1, **options)
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid context reached catalogue')
print(f'{checks} environment bindings, mixed resource profiles and unknown/conflicting context checks passed')

