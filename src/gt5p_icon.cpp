/* The runtime registers its game window without an icon. Explorer uses the
 * icon resource in this executable. The title bar and taskbar use the window
 * icon, so apply the same resource once that window exists and again if a
 * mode change creates a replacement. */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <string.h>

namespace {

bool game_window(HWND hwnd)
{
    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != GetCurrentProcessId()) return false;
    char name[64];
    if (!GetClassNameA(hwnd, name, sizeof name)) return false;
    return !strcmp(name, "ps3recomp_d3d12") || !strcmp(name, "ps3recomp_null") || !strcmp(name, "SDL_app");
}

BOOL CALLBACK find_game(HWND hwnd, LPARAM param)
{
    if (!game_window(hwnd)) return TRUE;
    *reinterpret_cast<HWND*>(param) = hwnd;
    return FALSE;
}

void apply(HWND hwnd, HICON big, HICON small)
{
    SendMessageW(hwnd, WM_SETICON, ICON_BIG, reinterpret_cast<LPARAM>(big));
    SendMessageW(hwnd, WM_SETICON, ICON_SMALL, reinterpret_cast<LPARAM>(small));
    SetClassLongPtrW(hwnd, GCLP_HICON, reinterpret_cast<LONG_PTR>(big));
    SetClassLongPtrW(hwnd, GCLP_HICONSM, reinterpret_cast<LONG_PTR>(small));
}

DWORD WINAPI watch(LPVOID)
{
    HMODULE module = GetModuleHandleW(nullptr);
    HICON big = reinterpret_cast<HICON>(LoadImageW(module, MAKEINTRESOURCEW(1), IMAGE_ICON,
        GetSystemMetrics(SM_CXICON), GetSystemMetrics(SM_CYICON), 0));
    HICON small = reinterpret_cast<HICON>(LoadImageW(module, MAKEINTRESOURCEW(1), IMAGE_ICON,
        GetSystemMetrics(SM_CXSMICON), GetSystemMetrics(SM_CYSMICON), 0));
    if (!big && !small) return 0;
    if (!big) big = small;
    if (!small) small = big;
    HWND last = nullptr;
    for (;;) {
        HWND hwnd = nullptr;
        EnumWindows(find_game, reinterpret_cast<LPARAM>(&hwnd));
        if (hwnd && hwnd != last) {
            apply(hwnd, big, small);
            last = hwnd;
        }
        Sleep(hwnd ? 1000 : 100);
    }
}

}

extern "C" void gt5p_install_window_icon(void)
{
    HANDLE thread = CreateThread(nullptr, 0, watch, nullptr, 0, nullptr);
    if (thread) CloseHandle(thread);
}
