#pragma once
#include <windows.h>
#include <cstdio>

// A managed game exits with this code instead of spawning a child which would
// be killed when the launcher's old kill-on-close job is retired.
namespace tourline_restart {
constexpr DWORD exit_code = 0x47543552UL;
inline bool managed() {
    wchar_t value[8]{};
    return GetEnvironmentVariableW(L"GT5P_LAUNCHER_RESTART", value, 8) == 1 && value[0] == L'1';
}
inline bool request() {
    std::fflush(stdout);
    std::fflush(stderr);
    return TerminateProcess(GetCurrentProcess(), exit_code) != FALSE;
}
}
