#include "gt5p_settings.h"
#include <cstdio>
#include <cstdlib>
extern "C" void pad_keyboard_set_vk(unsigned,int) { std::abort(); }
void gt5p_glyphs_keys_changed() { std::abort(); }
int main(int argc,char** argv) {
 gt5p_settings_load(); const auto& s=gt5p_settings();
 printf("CONTROLS %d %d %d %d %d %d %d\n",s.trigger_deadzone,s.trigger_curve,s.modern_controls,s.adaptive_triggers,s.trigger_rumble,s.sdl_rumble,gt5p_settings_overridden("PAD_TRIGGER_CURVE"));
 if(argc>1 && !gt5p_settings_save(gt5p_settings_file(),argv[1])) return 1;
 return 0;
}
