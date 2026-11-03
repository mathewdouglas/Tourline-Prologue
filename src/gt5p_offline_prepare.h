#pragma once
#include <cstring>

// Offline batches create and persist their requested pipelines before returning.
// Replaying those recipes immediately before exit adds no persistent readiness.
// Normal play always retains its existing startup warmup policy.
inline bool gt5p_replay_prepared_pipelines(const char* offline, const char* replay)
{
    return !offline || std::strcmp(offline, "1") != 0 ||
           (replay && std::strcmp(replay, "1") == 0);
}
