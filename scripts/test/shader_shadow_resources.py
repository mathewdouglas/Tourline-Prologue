"""Initialized LV shadow context and rejection of unresolved comparison inputs."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from shader_material_textures import with_global_sampler_path, complete_sampler_key
from shader_material_profile import ordinary_profile, shadow_lv_profile
from shader_material_variants import contexts, expand_job

material = dict(stencil_enable=0, cull_enable=1, blend=0, cmask=15, depth_bits=0x30000000)
checks = 0
for name, identifier in [('realTimeShadowMap', 87), ('realTimeShadowMapColor', 96)]:
    for unit in range(16):
        g = dict(name=name, kind=0x601, identifier=identifier, unit=unit)
        d = dict(used=1 << unit, bindings=[], globals=[g])
        r = with_global_sampler_path(d, shadow_path='shadow-lv-depth')
        assert complete_sampler_key(r) == 9 << (unit * 4)
        assert r['bindings'][0]['address'] == 0x60030404
        assert r['bindings'][0]['filtering'] == 0x02022000
        p = shadow_lv_profile(r, material, 0, 'ccw', 'rgba16-msaa2')
        assert p['shd'] == ((6 << 16) | (1 << unit) if identifier == 87 else 0)
        assert (p['cube'], p['ghi'], p['unhi'], p['unnorm']) == (0x21000, 0, 0, 0)
        for context in contexts('supported'):
            seed = dict(vertex_sha256='v', fragment_sha256='f', state=p)
            assert expand_job(seed, context)['state'] == shadow_lv_profile(
                r, material, 0, context['object_path'], context['target_path'])
        if identifier == 87:
            try:
                ordinary_profile(r, material, 0, 'ccw', 'rgba16-msaa2')
            except ValueError:
                pass
            else:
                raise AssertionError('Ordinary profile silently discarded shadow comparison')
        for change in (dict(name='unknown'), dict(identifier=999), dict(kind=0x801)):
            bad = dict(d, globals=[dict(g, **change)])
            assert complete_sampler_key(with_global_sampler_path(bad, shadow_path='shadow-lv-depth')) is None
        checks += 1

d = dict(used=0xb000, bindings=[], globals=[
    dict(name='realTimeShadowMap', kind=0x601, identifier=87, unit=13),
    dict(name='realTimeShadowMapColor', kind=0x601, identifier=96, unit=12),
    dict(name='ditherMap', kind=0x801, identifier=103, unit=15)])
selected = with_global_sampler_path(d, 'active', shadow_path='shadow-lv-depth')
p = shadow_lv_profile(selected, material, 0, 'ccw', 'rgba16-msaa2')
assert p['shd'] == 0x62000 and p['unhi'] == 0x8000
bad_cases = [dict(selected, globals=[dict(unit=0)]),
             dict(selected, unresolved=[dict(unit=0)]),
             dict(selected, bindings=selected['bindings'] + [dict(unit=0, format=0x19029, address=3 << 28)])]
bad_binding = dict(selected['bindings'][0], texture_facts=dict(shape='2d', gamma=False, unnormalized=False, depth_compare=3))
bad_cases.append(dict(selected, bindings=[bad_binding] + selected['bindings'][1:]))
for change in (dict(address=3 << 28), dict(filtering=0x01012000)):
    bad_cases.append(dict(selected, bindings=[dict(selected['bindings'][0], **change)] + selected['bindings'][1:]))
for bad in bad_cases:
    try:
        shadow_lv_profile(bad, material, 0, 'ccw', 'rgba16-msaa2')
    except ValueError:
        pass
    else:
        raise AssertionError('Unresolved/conflicting comparison accepted')
same = dict(selected, bindings=selected['bindings'] + [dict(unit=0, format=0x19029, address=6 << 28)])
assert shadow_lv_profile(same, material, 0, 'ccw', 'rgba16-msaa2')['shd'] == 0x62000
try:
    with_global_sampler_path(d, shadow_path='shadow-lv-depth', dynamic_path='absent')
except ValueError:
    pass
else:
    raise AssertionError('Absent and active resources accepted together')
print(f'{checks} initialized shadow bindings, explicit variants and comparison/ownership rejection checks passed')
