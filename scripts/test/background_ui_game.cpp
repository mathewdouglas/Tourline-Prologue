// Synthetic visible game for launcher overlay integration. No game code/data.
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <cstdio>
#include "../../src/gt5p_restart.h"
LRESULT CALLBACK proc(HWND h,UINT m,WPARAM w,LPARAM l) {
    if (m==WM_DESTROY) {PostQuitMessage(0);return 0;}
    if (m==WM_PAINT) {
        PAINTSTRUCT ps{};HDC dc=BeginPaint(h,&ps);RECT rc{};GetClientRect(h,&rc);
        HBRUSH brush=CreateSolidBrush(RGB(35,42,55));FillRect(dc,&rc,brush);DeleteObject(brush);
        SetBkMode(dc,TRANSPARENT);SetTextColor(dc,RGB(225,230,240));
        DrawTextW(dc,L"Background preparation UI fixture",-1,&rc,DT_CENTER|DT_VCENTER|DT_SINGLELINE);
        EndPaint(h,&ps);return 0;
    }
    return DefWindowProcW(h,m,w,l);
}
int wmain() {
    HINSTANCE instance=GetModuleHandleW(nullptr);WNDCLASSW cls{};
    cls.hInstance=instance;cls.lpfnWndProc=proc;cls.lpszClassName=L"tourline_ui_fixture";RegisterClassW(&cls);
    HWND window=CreateWindowExW(0,cls.lpszClassName,L"Tourline preparation fixture",WS_OVERLAPPEDWINDOW,
        CW_USEDEFAULT,CW_USEDEFAULT,960,600,nullptr,nullptr,instance,nullptr);
    if (!window) return 1;ShowWindow(window,SW_SHOW);SetForegroundWindow(window);
    FILE* file=nullptr;wchar_t event[256]{};GetEnvironmentVariableW(L"GT5P_RACE_EVENT",event,256);
    if (_wfopen_s(&file,L"ui-game.txt",L"w, ccs=UTF-8") || !file) return 2;
    fwprintf(file,L"pid=%lu\nevent=%ls\n",GetCurrentProcessId(),event);fclose(file);
    for (;;) {
        MSG msg;
        while (PeekMessageW(&msg,nullptr,0,0,PM_REMOVE)) {
            if (msg.message==WM_QUIT) return 0;TranslateMessage(&msg);DispatchMessageW(&msg);
        }
        if (GetFileAttributesW(L"ui-stop")!=INVALID_FILE_ATTRIBUTES) return 0;
        if (GetFileAttributesW(L"ui-restart")!=INVALID_FILE_ATTRIBUTES) {
            MoveFileExW(L"ui-restart",L"ui-restarted",MOVEFILE_REPLACE_EXISTING);
            if (!tourline_restart::managed()) return 3;tourline_restart::request();return 4;
        }
        Sleep(20);
    }
}
