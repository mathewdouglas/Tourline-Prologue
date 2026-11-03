#include "../../src/gt5p_offline_prepare.h"
#include <cassert>

int main()
{
    const char* live_values[] = {nullptr, "", "0", "true", "01"};
    const char* replay_values[] = {nullptr, "", "0", "1", "other"};
    for (const char* live : live_values)
        for (const char* replay : replay_values)
            assert(gt5p_replay_prepared_pipelines(live, replay));
    assert(!gt5p_replay_prepared_pipelines("1", nullptr));
    assert(!gt5p_replay_prepared_pipelines("1", "0"));
    assert(!gt5p_replay_prepared_pipelines("1", "other"));
    assert(gt5p_replay_prepared_pipelines("1", "1"));
}
