// Stand-in child for launcher integration checks. No game code or game files.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cwchar>
#include <initializer_list>
#include "../../src/gt5p_restart.h"

int wmain(int argc, wchar_t** argv) {
    FILE* f = nullptr;
    if (_wfopen_s(&f, L"probe.txt", L"w, ccs=UTF-8") || !f) return 2;
    wchar_t cwd[32768];
    GetCurrentDirectoryW(32768, cwd);
    fwprintf(f, L"cwd=%ls\nargc=%d\npid=%lu\n", cwd, argc, GetCurrentProcessId());
    for (int i = 0; i < argc; ++i) fwprintf(f, L"arg%d=%ls\n", i, argv[i]);
    for (const wchar_t* key : {L"GT5P_ROOT", L"PS3_VFS_ROOT", L"PS3_GAMEDATA_ROOT",
                              L"GT5P_SETTINGS", L"GT5P_GAME_DIR", L"PS3_VERBOSE",L"RSX_SHADER_CACHE",L"PS3_TITLE",L"GT5P_LAUNCHER_RESTART"}) {
        wchar_t value[32768]{};
        GetEnvironmentVariableW(key, value, 32768);
        fwprintf(f, L"%ls=%ls\n", key, value);
    }
    fclose(f);
    puts("probe stdout"); fflush(stdout);
    fputs("probe stderr\n", stderr); fflush(stderr);
    wchar_t restarting[8]{};
    if (GetEnvironmentVariableW(L"GT5P_PROBE_RESTART_ONCE",restarting,8)==1 && restarting[0]==L'1') {
        FILE* history=nullptr;
        if (_wfopen_s(&history,L"restart-pids.txt",L"a, ccs=UTF-8") || !history) return 3;
        fwprintf(history,L"%lu\n",GetCurrentProcessId());
        fclose(history);
        if (GetFileAttributesW(L"restart-once.marker")==INVALID_FILE_ATTRIBUTES) {
            FILE* marker=nullptr;
            if (_wfopen_s(&marker,L"restart-once.marker",L"w") || !marker) return 3;
            fclose(marker);
            wchar_t settings[32768]{};
            GetEnvironmentVariableW(L"GT5P_SETTINGS",settings,32768);
            FILE* changed=nullptr;
            if (_wfopen_s(&changed,settings,L"w") || !changed) return 3;
            fputs("[video]\nresolution = \"1440p\"\n",changed); fclose(changed);
            if (!tourline_restart::managed()) return 4;
            tourline_restart::request();
            return 5;
        }
    }
    wchar_t delay[32]{};
    bool preparation=argc>1 && !wcscmp(argv[1],L"--install");
    if ((preparation && GetEnvironmentVariableW(L"GT5P_PROBE_PREPARE_DELAY_MS",delay,32)) || GetEnvironmentVariableW(L"GT5P_PROBE_DELAY_MS", delay, 32)) {
        for (int elapsed=0;elapsed<_wtoi(delay);elapsed+=20) {
            if (preparation && GetFileAttributesW(L"prepare.cancel")!=INVALID_FILE_ATTRIBUTES) return 2;
            Sleep(20);
        }
    }
    return 0;
}
