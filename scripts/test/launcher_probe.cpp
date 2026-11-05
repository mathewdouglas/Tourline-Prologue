// Stand-in child for launcher integration checks. No game code or game files.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include <cstdlib>
#include <cwchar>
#include <initializer_list>
#include <string>
#include "../../src/gt5p_restart.h"

int wmain(int argc, wchar_t** argv) {
    if (argc>1 && !wcscmp(argv[1],L"--check-selected")) {
        // The launcher's read-only "is the current preparation selected" question.
        // Leaves its own record and never probe.txt, which marks a game start.
        FILE* record=nullptr;
        if (!_wfopen_s(&record,L"check.txt",L"a, ccs=UTF-8") && record) { fwprintf(record,L"argc=%d\n",argc); fclose(record); }
        wchar_t selected[16]{};
        GetEnvironmentVariableW(L"GT5P_PROBE_SELECTED",selected,16);
        return !wcscmp(selected,L"1") ? 0 : !wcscmp(selected,L"error") ? 1 : 3;
    }
    if (argc>1 && (!wcscmp(argv[1],L"--collect-contribution") || !wcscmp(argv[1],L"--verify-contribution"))) {
        const wchar_t* storage=nullptr;
        for (int i=2;i+1<argc;i++) if (!wcscmp(argv[i],L"--storage")) storage=argv[i+1];
        if (!storage) return 10;
        std::wstring lock=std::wstring(storage)+L"/launcher.lock";
        HANDLE lease=CreateFileW(lock.c_str(),GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,0,nullptr);
        if (lease==INVALID_HANDLE_VALUE) return 11;
        CloseHandle(lease);
        wchar_t home[32768]{};
        if (GetEnvironmentVariableW(L"GT5P_LAUNCHER_HOME",home,32768)) {
            lock=std::wstring(home)+L"/storage.lock";
            lease=CreateFileW(lock.c_str(),GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,0,nullptr);
            if (lease==INVALID_HANDLE_VALUE) return 12;
            CloseHandle(lease);
        }
        FILE* result=nullptr;
        if (_wfopen_s(&result,(std::wstring(storage)+L"/tool-result.txt").c_str(),L"w, ccs=UTF-8") || !result) return 13;
        fwprintf(result,L"mode=%ls\nleases=released\n",argv[1]);fclose(result);
        wchar_t cancelled[8]{};
        return GetEnvironmentVariableW(L"GT5P_PROBE_TOOL_CANCEL",cancelled,8) ? 2 : 0;
    }
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
    wchar_t action[32]{};
    if (GetEnvironmentVariableW(L"GT5P_PROBE_PIPELINE_ACTION",action,32) && tourline_restart::tools_available() &&
            (argc<2 || wcscmp(argv[1],L"--install"))) {
        tourline_restart::request(!wcscmp(action,L"collect") ? tourline_restart::Action::Collect :
            !wcscmp(action,L"verify") ? tourline_restart::Action::Verify : tourline_restart::Action::Prepare);
        return 14;
    }
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
    if (preparation && !wcscmp(action,L"prepare")) {
        HANDLE lease=CreateFileW(L"launcher.lock",GENERIC_WRITE,0,nullptr,OPEN_ALWAYS,0,nullptr);
        if (lease!=INVALID_HANDLE_VALUE) { CloseHandle(lease);return 15; }
        FILE* result=nullptr;
        if (_wfopen_s(&result,L"tool-result.txt",L"w") || !result) return 16;
        fputs("mode=prepare\nlease=held\n",result);fclose(result);
        wchar_t cancelled[8]{};
        if (GetEnvironmentVariableW(L"GT5P_PROBE_TOOL_CANCEL",cancelled,8)) return 2;
    }
    wchar_t failure[8]{};
    if (preparation && GetEnvironmentVariableW(L"GT5P_PROBE_PREPARE_EXIT",failure,8)) return _wtoi(failure);
    if ((preparation && GetEnvironmentVariableW(L"GT5P_PROBE_PREPARE_DELAY_MS",delay,32)) || GetEnvironmentVariableW(L"GT5P_PROBE_DELAY_MS", delay, 32)) {
        for (int elapsed=0;elapsed<_wtoi(delay);elapsed+=20) {
            if (preparation && GetFileAttributesW(L"prepare.cancel")!=INVALID_FILE_ATTRIBUTES) return 2;
            Sleep(20);
        }
    }
    return 0;
}
