// Links the production settings parser, never the game or renderer.
#include "gt5p_settings.h"
#include <cstdio>
#include <cstdlib>
// Parsing formats the key map but must never apply inputs or refresh glyphs.
extern "C" void pad_keyboard_set_vk(unsigned,int) { std::abort(); }
void gt5p_glyphs_keys_changed() { std::abort(); }
int main() {
    gt5p_settings_load();
    const auto& s=gt5p_settings();
    std::printf("PREPARE_SETTINGS %d %d %d %d\n",s.resolution,s.ultrawide?1:0,s.anisotropy,s.smooth_colour?1:0);
    return 0;
}
