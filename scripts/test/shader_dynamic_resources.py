"""Conditional dynamic fallback bindings; active/unknown resources stay unknown."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parents[1]))
from shader_material_textures import with_global_sampler_path, complete_sampler_key
from shader_texture_shapes import texture_fields
from shader_material_profile import ordinary_profile
from shader_material_variants import contexts, expand_job
from prepare_material_shaders import check_dynamic_game
import tempfile

material = dict(stencil_enable=0, cull_enable=1, blend=0, cmask=15, depth_bits=0x30000000)
signatures = [('envMapSampler', 0x901, 71, True), ('realTimeShadowMap', 0x601, 87, False),
              ('realTimeShadowMapColor', 0x601, 96, False), ('mirrorMapSampler', 0x601, 115, True)]
checks = 0
for name, kind, identifier, cube in signatures:
    for unit in range(16):
        g = dict(name=name, kind=kind, identifier=identifier, unit=unit)
        d = dict(used=1 << unit, bindings=[], globals=[g])
        assert with_global_sampler_path(d) is d
        assert complete_sampler_key(d) is None
        r = with_global_sampler_path(d, dynamic_path='absent')
        assert d['globals'] == [g] and not d['bindings']
        assert not r['globals'] and complete_sampler_key(r) == 8 << (unit * 4)
        f = texture_fields(r, True)
        assert not f['unresolved_units'] and not f['rejected']
        p = ordinary_profile(r, material, 0, 'ccw', 'rgba16-msaa2')
        assert p['cube'] == 0x21000 | ((1 << (unit if unit < 4 else unit + 16)) if cube else 0)
        assert (p['ghi'], p['unhi'], p['unnorm'], p['shd']) == (0, 0, 0, 0)
        for context in contexts('supported'):
            seed = dict(vertex_sha256='v', fragment_sha256='f', state=p)
            assert expand_job(seed, context)['state'] == ordinary_profile(
                r, material, 0, context['object_path'], context['target_path'])
        for change in (dict(name='unknown'), dict(kind=0x602), dict(identifier=999)):
            bad = dict(d, globals=[dict(g, **change)])
            assert complete_sampler_key(with_global_sampler_path(bad, dynamic_path='absent')) is None
        for bad in (dict(d, globals=[g, g]), dict(d, bindings=[dict(unit=unit, sampler=9)]),
                    dict(d, unresolved=[dict(unit=unit, reason='missing scalar alias binding')])):
            rbad = with_global_sampler_path(bad, dynamic_path='absent')
            assert rbad['globals'] and complete_sampler_key(rbad) is None
        checks += 1

# Absence of a dynamic resource is independent of the dither feature gate.
g = dict(name='envMapSampler', kind=0x901, identifier=71, unit=14)
d = dict(used=0xc000, bindings=[], globals=[g, dict(name='ditherMap', kind=0x801, identifier=103, unit=15)])
for path, sampler, unhi in [('active', 4, 0x8000), ('fallback', 8, 0)]:
    r = with_global_sampler_path(d, path, dynamic_path='absent')
    p = ordinary_profile(r, material, 0, 'ccw', 'rgba16-msaa2')
    assert p['samplers'] == f'{(8 << 56) | (sampler << 60):016x}' and p['unhi'] == unhi

for kwargs in (dict(dynamic_path='present'), dict(dynamic_path='absent', shadow_path='shadow-lv'),
               dict(dynamic_path='absent', environment_path='framebuffer-single'),
               dict(dynamic_path='absent', mirror_path='scene-copy')):
    try:
        with_global_sampler_path(d, **kwargs)
    except ValueError:
        pass
    else:
        raise AssertionError('Unsupported/conflicting resource path accepted')
with tempfile.TemporaryDirectory() as folder:
    root = Path(folder); (root / 'input').mkdir()
    (root / 'input/EMAIN.ELF').write_bytes(b'wrong game')
    try:
        check_dynamic_game(root)
    except ValueError:
        pass
    else:
        raise AssertionError('Wrong game accepted for build-specific fallback rules')
print(f'{checks} dynamic fallback signatures/lanes and all explicit target/face variants passed; unknowns rejected')
