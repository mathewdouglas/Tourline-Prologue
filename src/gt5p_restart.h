#pragma once
#include <windows.h>
#include <cstdio>

// A managed game exits with this code instead of spawning a child which would
// be killed when the launcher's old kill-on-close job is retired.
namespace tourline_restart {
constexpr DWORD exit_code = 0x47543552UL;
enum class Action : DWORD { Restart = exit_code, Collect = 0x47543543UL, Verify = 0x47543556UL, Prepare = 0x47543550UL };
inline bool pipeline_action(DWORD code) {
    return code == static_cast<DWORD>(Action::Collect) || code == static_cast<DWORD>(Action::Verify) ||
        code == static_cast<DWORD>(Action::Prepare);
}
inline bool managed() {
    wchar_t value[8]{};
    return GetEnvironmentVariableW(L"GT5P_LAUNCHER_RESTART", value, 8) == 1 && value[0] == L'1';
}
inline bool tools_available() {
    wchar_t value[8]{};
    return managed() && GetEnvironmentVariableW(L"GT5P_PIPELINE_TOOLS", value, 8) == 1 && value[0] == L'1'
        && GetEnvironmentVariableW(L"RSX_PSO_PROVENANCE", nullptr, 0) == 0;
}
inline bool request(Action action = Action::Restart) {
    std::fflush(stdout);
    std::fflush(stderr);
    return TerminateProcess(GetCurrentProcess(), static_cast<DWORD>(action)) != FALSE;
}
}
