/* "Compiling shaders" and "Loading shaders" indicators over the game window.
 *
 * The D3D12 backend compiles a guest program's shaders, and builds its
 * pipeline, on the thread that replays frames, so the picture stops while it
 * does: about 9 s the first time the showroom is entered without a shader
 * cache, and short stalls whenever a new screen needs new pipelines. This
 * shows a small badge in the corner of the game window while that happens,
 * from a thread and window of its own (like the F3 profiler), so it keeps
 * animating while the game's own frame is frozen.
 *
 * Two badges, one place. "Compiling shaders" is demand work: a draw is
 * waiting for a shader or a pipeline. "Loading shaders" is the quieter badge
 * (smaller, dimmer) for preload work the player is not waiting on: the
 * background startup warmup, race loading preparation, and anything else made
 * for a recorded recipe rather than for a draw. The backend counts the two
 * apart (g_rsx_shader_busy / g_rsx_shader_demand_total and
 * g_rsx_shader_preload_busy / g_rsx_shader_preload_total, rsx_d3d12_backend.c).
 * If both would show, only "Compiling shaders" does.
 *
 * A badge appears once its work has gone on for a moment, so a single quick
 * pipeline does not flash it, and stays until 0.7 s after the last item, so a
 * burst reads as one. It counts the shaders and pipelines of the burst.
 *
 * [video] shader_indicator in gt5p_settings.toml, the F1 page, or
 * GT5P_SHADER_INDICATOR=0 turn "Compiling shaders" off. [video]
 * preload_indicator, the F1 page, or GT5P_PRELOAD_INDICATOR=1 turn "Loading
 * shaders" on (off by default). RSX_SHADER_INDICATOR_LEGACY=1 makes the
 * backend count preload work as demand work again, as before the split.
 *
 * The race loading gate blocks the guest on LoadingRoot, so the GT logo stays
 * the last presented frame and this thread is what can still draw. A thin bar
 * under that mark tracks pipelines finished in the race set
 * (g_rsx_race_load_done / g_rsx_race_load_total while g_rsx_race_load_waiting).
 * GT5P_RACE_LOAD_BAR=0 leaves it off. It is not an F1 row.
 */
#include <windows.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <string>

extern "C" {
extern volatile LONG g_rsx_shader_busy;            /* rsx_d3d12_backend.c */
extern volatile LONG g_rsx_shader_demand_total;
extern volatile LONG g_rsx_shader_preload_busy;
extern volatile LONG g_rsx_shader_preload_total;
extern volatile LONG g_rsx_race_load_done;
extern volatile LONG g_rsx_race_load_total;
extern volatile LONG g_rsx_race_load_waiting;
}

namespace {

const int kMargin = 16;

/* One badge: a layered window of its own and the burst state that drives it. */
struct Badge {
    const wchar_t* cls;       /* window class */
    const wchar_t* label;
    const char* tag;          /* for the log line */
    int w, h, font, dot, ring;   /* size, font height, spinner dot radius, spinner ring radius */
    COLORREF fill, edge, text, hue;   /* hue: spinner colour at full strength */
    BYTE alpha;
    ULONGLONG delay_ms;       /* sustained activity before it shows */
    volatile LONG* enabled;
    HWND wnd;
    bool shown;
    LONG burst;               /* shaders + pipelines since the burst began */
    int phase;                /* spinner step */
    LONG last_total, burst_base;
    ULONGLONG act_start, last_act, shown_at, last_spin;
    POINT last_pos;
    HFONT hfont;
};

HWND s_game;
volatile LONG s_enabled = 1;           /* "Compiling shaders" */
volatile LONG s_preload_enabled = 0;   /* "Loading shaders" */
volatile LONG s_bar_enabled = 1;       /* race-load bar under the GT logo */

/* The guest's GT mark sits in the middle of the frozen loading frame. */
const double kRaceBarTop = 0.62;
const int kRaceBarH = 6;
const ULONGLONG kRaceBarDelayMs = 200;

Badge s_main = { L"gt5p_shaderbusy", L"Compiling shaders", "shader-badge", 236, 38, -15, 2, 8,
                 RGB(20, 23, 30), RGB(52, 120, 220), RGB(230, 233, 240), RGB(52, 140, 255), 235, 200,
                 &s_enabled };
Badge s_pre  = { L"gt5p_shaderpreload", L"Loading shaders", "preload-badge", 196, 30, -13, 2, 7,
                 RGB(24, 26, 30), RGB(70, 78, 92), RGB(168, 174, 186), RGB(150, 175, 215), 170, 400,
                 &s_preload_enabled };

BOOL CALLBACK find_game(HWND h, LPARAM)
{
    DWORD pid = 0;
    GetWindowThreadProcessId(h, &pid);
    if (pid != GetCurrentProcessId() || !IsWindowVisible(h) || GetWindow(h, GW_OWNER) != NULL)
        return TRUE;
    wchar_t cls[64] = L"";
    GetClassNameW(h, cls, 64);
    if (!wcscmp(cls, L"ConsoleWindowClass") || !wcscmp(cls, L"PseudoConsoleWindow") ||
        !wcsncmp(cls, L"gt5p_", 5))
        return TRUE;
    s_game = h;
    return FALSE;
}

void paint(Badge& b, HDC dc)
{
    if (!b.hfont)
        b.hfont = CreateFontW(b.font, 0, 0, 0, FW_SEMIBOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0,
                              CLEARTYPE_QUALITY, 0, L"Segoe UI");
    RECT all = { 0, 0, b.w, b.h };
    HBRUSH bg = CreateSolidBrush(RGB(0, 0, 0)); FillRect(dc, &all, bg); DeleteObject(bg);
    /* The pill: everything black outside it is keyed out (LWA_COLORKEY). */
    HBRUSH pb = CreateSolidBrush(b.fill); HPEN pp = CreatePen(PS_SOLID, 1, b.edge);
    HGDIOBJ ob = SelectObject(dc, pb), op = SelectObject(dc, pp);
    RoundRect(dc, 0, 0, b.w, b.h, b.h, b.h);
    SelectObject(dc, ob); SelectObject(dc, op); DeleteObject(pb); DeleteObject(pp);

    /* Spinner: eight dots round a circle, the lit one moving. */
    const int cx = b.h / 2 + 3, cy = b.h / 2, r = b.ring;
    const int hr = GetRValue(b.hue), hg = GetGValue(b.hue), hb = GetBValue(b.hue);
    for (int i = 0; i < 8; i++) {
        const double a = i * 3.14159265 / 4;
        const int x = cx + (int)lround(r * cos(a)), y = cy + (int)lround(r * sin(a));
        const int age = (b.phase - i + 8) % 8;
        const int v = age == 0 ? 255 : age == 1 ? 170 : age == 2 ? 110 : 60;
        HBRUSH d = CreateSolidBrush(RGB(hr * v / 255 + 10, hg * v / 255 + 10, hb * v / 255 + 10));
        HPEN np = (HPEN)GetStockObject(NULL_PEN);
        HGDIOBJ o1 = SelectObject(dc, d), o2 = SelectObject(dc, np);
        Ellipse(dc, x - b.dot, y - b.dot, x + b.dot + 1, y + b.dot + 1);
        SelectObject(dc, o1); SelectObject(dc, o2); DeleteObject(d);
    }

    SetBkMode(dc, TRANSPARENT);
    HGDIOBJ of = SelectObject(dc, b.hfont);
    SetTextColor(dc, b.text);
    std::wstring s = b.label;
    if (b.burst > 1) s += L"  (" + std::to_wstring(b.burst) + L")";
    TextOutW(dc, b.h + 4, (b.h - (-b.font + 3)) / 2, s.c_str(), (int)s.size());
    SelectObject(dc, of);
}

LRESULT CALLBACK wndproc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (m == WM_PAINT) {
        Badge& b = GetWindowLongPtrW(h, GWLP_USERDATA) == (LONG_PTR)&s_pre ? s_pre : s_main;
        PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps);
        HDC mem = CreateCompatibleDC(dc);
        HBITMAP bm = CreateCompatibleBitmap(dc, b.w, b.h);
        HGDIOBJ o = SelectObject(mem, bm);
        paint(b, mem);
        BitBlt(dc, 0, 0, b.w, b.h, mem, 0, 0, SRCCOPY);
        SelectObject(mem, o); DeleteObject(bm); DeleteDC(mem);
        EndPaint(h, &ps);
        return 0;
    }
    if (m == WM_NCHITTEST) return HTTRANSPARENT;
    if (m == WM_ERASEBKGND) return 1;
    return DefWindowProcW(h, m, w, l);
}

/* Bottom-right of the game's client area. Asynchronous and only on a change:
 * the game window's thread is the very one that is busy compiling. */
void place(Badge& b, UINT show_flag)
{
    RECT rc; GetClientRect(s_game, &rc);
    POINT p = { rc.right - b.w - kMargin, rc.bottom - b.h - kMargin };
    ClientToScreen(s_game, &p);
    if (!show_flag && p.x == b.last_pos.x && p.y == b.last_pos.y) return;
    b.last_pos = p;
    SetWindowPos(b.wnd, NULL, p.x, p.y, 0, 0,
                 SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS | show_flag);
}

void create(Badge& b, HINSTANCE inst)
{
    WNDCLASSW wc = {};
    wc.lpfnWndProc = wndproc; wc.hInstance = inst;
    wc.lpszClassName = b.cls; wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    RegisterClassW(&wc);
    b.wnd = CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
                            b.cls, L"GT5P shaders", WS_POPUP, 0, 0, b.w, b.h, s_game, NULL, inst, NULL);
    SetWindowLongPtrW(b.wnd, GWLP_USERDATA, (LONG_PTR)&b);
    SetLayeredWindowAttributes(b.wnd, RGB(0, 0, 0), b.alpha, LWA_COLORKEY | LWA_ALPHA);
    b.last_pos = { -100000, -100000 };
}

/* Is there work of this kind now, tracked as a burst. `total` counts what
 * the backend has finished, `busy` is > 0 while a piece is running. */
bool track(Badge& b, ULONGLONG now, LONG busy, LONG total, bool allowed)
{
    const bool act = busy > 0 || total != b.last_total;
    b.last_total = total;
    if (act) {
        if (!b.act_start) { b.act_start = now; b.burst_base = total - (busy > 0 ? 0 : 1); }
        b.last_act = now;
    } else if (b.act_start && now - b.last_act > 700) {
        b.act_start = 0;
    }
    b.burst = total - b.burst_base;
    return *b.enabled && allowed && b.act_start && now - b.act_start >= b.delay_ms;
}

void update(Badge& b, bool want, ULONGLONG now)
{
    if (want != b.shown) {
        b.shown = want;
        place(b, want ? SWP_SHOWWINDOW : SWP_HIDEWINDOW);
        if (want) b.shown_at = now;
        else fprintf(stderr, "[%s] shown %.1f s: %ld shaders and pipelines\n", b.tag,
                     (now - b.shown_at) / 1000.0, (long)b.burst);
    }
    if (b.shown) {
        place(b, 0);
        if (now - b.last_spin >= 90) { b.last_spin = now; b.phase = (b.phase + 1) % 8; }
        InvalidateRect(b.wnd, NULL, FALSE);
    }
}

/* Track and fill only. The window is the bar, so layered alpha is enough. */
struct RaceBar {
    HWND wnd;
    bool shown;
    int w, h;
    POINT last_pos;
    ULONGLONG wait_since, shown_at;
};

RaceBar s_bar = {};

void paint_bar(HDC dc, int w, int h)
{
    RECT all = { 0, 0, w, h };
    HBRUSH track = CreateSolidBrush(RGB(58, 62, 70));
    FillRect(dc, &all, track);
    DeleteObject(track);
    LONG total = g_rsx_race_load_total;
    LONG done = g_rsx_race_load_done;
    if (w <= 0 || h <= 0 || total < 1) return;
    if (done < 0) done = 0;
    if (done > total) done = total;
    int fw = (int)((long long)done * w / total);
    if (done > 0 && fw < 2) fw = 2;
    if (fw > w) fw = w;
    if (fw <= 0) return;
    RECT fill = { 0, 0, fw, h };
    HBRUSH ink = CreateSolidBrush(RGB(240, 242, 246));
    FillRect(dc, &fill, ink);
    DeleteObject(ink);
}

LRESULT CALLBACK barproc(HWND h, UINT m, WPARAM w, LPARAM l)
{
    if (m == WM_PAINT) {
        PAINTSTRUCT ps; HDC dc = BeginPaint(h, &ps);
        RECT cr; GetClientRect(h, &cr);
        const int bw = cr.right > 0 ? cr.right : 1, bh = cr.bottom > 0 ? cr.bottom : 1;
        HDC mem = CreateCompatibleDC(dc);
        HBITMAP bm = CreateCompatibleBitmap(dc, bw, bh);
        HGDIOBJ o = SelectObject(mem, bm);
        paint_bar(mem, cr.right, cr.bottom);
        BitBlt(dc, 0, 0, bw, bh, mem, 0, 0, SRCCOPY);
        SelectObject(mem, o); DeleteObject(bm); DeleteDC(mem);
        EndPaint(h, &ps);
        return 0;
    }
    if (m == WM_NCHITTEST) return HTTRANSPARENT;
    if (m == WM_ERASEBKGND) return 1;
    return DefWindowProcW(h, m, w, l);
}

void place_bar(UINT show_flag)
{
    if (show_flag == SWP_HIDEWINDOW) {
        SetWindowPos(s_bar.wnd, NULL, 0, 0, 0, 0,
                     SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS | SWP_HIDEWINDOW);
        return;
    }
    RECT rc; GetClientRect(s_game, &rc);
    const int cw = rc.right - rc.left, ch = rc.bottom - rc.top;
    if (cw < 80 || ch < 80) return;
    int w = (int)(cw * 0.22);
    if (w < 220) w = 220;
    if (w > 480) w = 480;
    if (w > cw - 32) w = cw - 32;
    POINT p = { (cw - w) / 2, (int)(ch * kRaceBarTop) };
    ClientToScreen(s_game, &p);
    const bool resized = w != s_bar.w || kRaceBarH != s_bar.h;
    const bool moved = p.x != s_bar.last_pos.x || p.y != s_bar.last_pos.y;
    if (!show_flag && !resized && !moved) return;
    s_bar.w = w; s_bar.h = kRaceBarH; s_bar.last_pos = p;
    SetWindowPos(s_bar.wnd, NULL, p.x, p.y, w, kRaceBarH,
                 (resized ? 0 : SWP_NOSIZE) | SWP_NOZORDER | SWP_NOACTIVATE | SWP_ASYNCWINDOWPOS | show_flag);
}

void create_bar(HINSTANCE inst)
{
    WNDCLASSW wc = {};
    wc.lpfnWndProc = barproc; wc.hInstance = inst;
    wc.lpszClassName = L"gt5p_raceload"; wc.hCursor = LoadCursor(NULL, IDC_ARROW);
    RegisterClassW(&wc);
    s_bar.wnd = CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
                                L"gt5p_raceload", L"GT5P race load", WS_POPUP,
                                0, 0, 320, kRaceBarH, s_game, NULL, inst, NULL);
    if (!s_bar.wnd) return;
    SetLayeredWindowAttributes(s_bar.wnd, 0, 255, LWA_ALPHA);
    s_bar.w = 320; s_bar.h = kRaceBarH;
    s_bar.last_pos = { -100000, -100000 };
}

void update_bar(ULONGLONG now)
{
    if (!s_bar_enabled || !s_bar.wnd) return;
    const LONG waiting = g_rsx_race_load_waiting;
    if (waiting > 0) { if (!s_bar.wait_since) s_bar.wait_since = now; }
    else s_bar.wait_since = 0;
    const LONG total = g_rsx_race_load_total;
    const bool want = waiting > 0 && total > 0 && s_bar.wait_since && now - s_bar.wait_since >= kRaceBarDelayMs;
    if (want != s_bar.shown) {
        s_bar.shown = want;
        place_bar(want ? SWP_SHOWWINDOW : SWP_HIDEWINDOW);
        if (want) s_bar.shown_at = now;
        else fprintf(stderr, "[race-load-bar] shown %.1f s: %ld / %ld pipelines\n",
                     (now - s_bar.shown_at) / 1000.0, (long)g_rsx_race_load_done, (long)total);
    }
    if (s_bar.shown) { place_bar(0); InvalidateRect(s_bar.wnd, NULL, FALSE); }
}

DWORD WINAPI badge_thread(LPVOID)
{
    while (!s_game) { Sleep(500); EnumWindows(find_game, 0); }
    HINSTANCE inst = GetModuleHandleW(NULL);
    create(s_main, inst);
    create(s_pre, inst);
    if (s_bar_enabled) create_bar(inst);

    s_main.last_total = s_main.burst_base = g_rsx_shader_demand_total;
    s_pre.last_total = s_pre.burst_base = g_rsx_shader_preload_total;
    for (;;) {
        MSG msg;
        while (PeekMessageW(&msg, NULL, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
        if (!IsWindow(s_game)) return 0;

        const ULONGLONG now = GetTickCount64();
        const bool want_main = track(s_main, now, g_rsx_shader_busy, g_rsx_shader_demand_total, true);
        /* "Compiling shaders" wins when both would show. */
        const bool want_pre = track(s_pre, now, g_rsx_shader_preload_busy, g_rsx_shader_preload_total, !want_main);
        update(s_main, want_main, now);
        update(s_pre, want_pre, now);
        update_bar(now);
        Sleep(30);
    }
}

}  // namespace

/* The settings page switches them while running. */
extern "C" void gt5p_shader_indicator_enable(int on) { s_enabled = on ? 1 : 0; }
extern "C" void gt5p_preload_indicator_enable(int on) { s_preload_enabled = on ? 1 : 0; }

/* Start the badges' thread (they stay hidden until there is work), unless
 * there is no window. GT5P_SHADER_INDICATOR=0 starts "Compiling shaders"
 * disabled; GT5P_PRELOAD_INDICATOR=1 starts "Loading shaders" enabled.
 * GT5P_RACE_LOAD_BAR=0 leaves the race-load bar off. */
extern "C" void gt5p_start_shader_indicator(void)
{
    if (getenv("PS3_HEADLESS")) return;
    const char* e = getenv("GT5P_SHADER_INDICATOR");
    s_enabled = !(e && e[0] == '0');
    const char* p = getenv("GT5P_PRELOAD_INDICATOR");
    s_preload_enabled = p && p[0] == '1';
    const char* b = getenv("GT5P_RACE_LOAD_BAR");
    s_bar_enabled = !(b && b[0] == '0');
    HANDLE h = CreateThread(NULL, 128 * 1024, badge_thread, NULL, 0, NULL);
    if (h) CloseHandle(h);
}
