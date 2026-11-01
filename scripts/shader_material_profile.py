"""Conditional asset profiles for 2D uploads, built-ins and initialized LV shadows.

This is a conditional material profile, not proof of actual draw/pass ownership.
Unknown sampled bindings fail closed, including globals with only shape known.
"""
from shader_material_textures import complete_sampler_key
from shader_texture_shapes import texture_fields, texture_shape
from shader_pass_state import object_pass_fields, native_target_fields


def ordinary_profile(definition, material, control, object_path, target_path):
    return _profile(definition, material, control, object_path, target_path, False)


def shadow_lv_profile(definition, material, control, object_path, target_path):
    """Initialized LV depth resource; successful default local depth aliases.

    Unlisted/stale units must not supply an earlier different depth comparison.
    This explicit resource context does not prove a live draw's ownership.
    """
    return _profile(definition, material, control, object_path, target_path, True)


def _profile(definition, material, control, object_path, target_path, shadow):
    if material['stencil_enable']:
        raise ValueError('ordinary profile excludes stencil')
    sampler = complete_sampler_key(definition)
    fields = texture_fields(definition, sampling=True)
    if sampler is None or fields['unresolved_units']:
        raise ValueError('unresolved sampled texture or sampler facts')
    low = 0
    depth_units = 0
    global_units = {g['unit'] for g in definition.get('globals', ())}
    for binding in definition['bindings']:
        unit = binding['unit']
        if not definition['used'] & (1 << unit) or unit in global_units:
            continue
        if 'format' in binding:
            shape = texture_shape(binding)
            texel = bool(binding['format'] & 0x4000)
        else:
            facts = binding.get('texture_facts') or {}
            shape, texel = facts.get('shape'), facts.get('unnormalized')
            if facts.get('depth_compare') is not None:
                if (not shadow or binding.get('global_path') != 'shadow-lv-depth' or
                        (binding.get('name'), binding.get('kind'), binding.get('identifier')) != ('realTimeShadowMap', 0x601, 87) or
                        facts != dict(shape='2d', gamma=False, unnormalized=False, depth_compare=6) or
                        binding.get('address') != 0x60030404 or binding.get('filtering') != 0x02022000):
                    raise ValueError('depth alias requires the explicit initialized LV context')
                depth_units |= 1 << unit
        fallback_cube = ('format' not in binding and binding.get('global_path') == 'absent'
                         and shape == 'cube' and texel is False)
        if (shape != '2d' and not fallback_cube) or texel is None:
            raise ValueError('ordinary profile requires known 2D coordinate facts')
        if unit < 4 and texel:
            low |= 1 << unit
    if depth_units:
        first = (depth_units & -depth_units).bit_length() - 1
        # Production takes the comparison from the first depth-format binding,
        # even if its program does not sample that unit. Check all declarations.
        if any(g['unit'] < first for g in definition.get('globals', ())):
            raise ValueError('unresolved earlier global depth comparison')
        if any(b['unit'] < first for b in definition.get('unresolved', ())):
            raise ValueError('unresolved earlier local depth comparison')
        for b in definition['bindings']:
            if b['unit'] < first and 'format' in b and 0x90 <= (b['format'] >> 8) & 0x9f <= 0x93:
                if (b['address'] >> 28) & 7 != 6:
                    raise ValueError('earlier depth binding changes the comparison')
    wrapper = object_pass_fields(object_path, material)
    target = native_target_fields(target_path)
    return dict(exp32=int(bool(control & 0x40)),
                cube=fields['values']['cube'] | wrapper['cube_value'] | target['cube_value'],
                ghi=fields['values']['ghi'], unhi=fields['values']['unhi'],
                unnorm=(0x100 | low) if low else 0, shd=(depth_units | (6 << 16)) if depth_units else 0,
                samplers=f'{sampler:016x}', blend=material['blend'], cmask=material['cmask'],
                stencil=material['depth_bits'], cull=wrapper['cull'], rtfmt=target['rtfmt'], nrt=1)


def profile_matches(profile, state):
    return all(state.get(name) == value for name, value in profile.items())


ASSUMPTIONS = [
    'successfully uploaded supported 2D textures; no target/depth-copy/mip alias redirects',
    'explicit global callback candidates; unknown sampled facts rejected',
    'prepared material, compact fragment binding and explicit object/target candidate',
    'no later binding/control/pass overrides; default renderer translation switches',
]

SHADOW_ASSUMPTIONS = [
    'ordinary local 2D uploads; only explicit initialized shadow depth aliases; no other target/depth-copy/mip redirects',
    *ASSUMPTIONS[1:],
    'fresh enum-0x40 2D depth framebuffer initialization then enabled LV pass; no later descriptor overrides',
    'local shadow aliases enabled and allocated successfully; no unlisted earlier depth binding with a different comparison',
]
