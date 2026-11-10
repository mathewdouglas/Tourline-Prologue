#pragma once
#include <windows.h>
#include <string>

// Launcher-owned, click-through status. No engine change or render-thread I/O.
namespace background_preparation_ui {
enum class Work { Preparing, Paused, Complete, Incomplete };
enum class View { Hidden, Preparing, Paused, CompleteNotice, Ready, Incomplete };

struct Notice {
    ULONGLONG visible_ms=0, last_tick=0;
    bool counting=false;
    View update(Work work, bool racing, bool visible, ULONGLONG now) {
        const bool eligible=work==Work::Complete && !racing && visible;
        if (eligible && counting && now>=last_tick) visible_ms+=now-last_tick;
        counting=eligible;last_tick=now;
        if (!visible) return View::Hidden;
        if (work==Work::Complete) return racing?View::Hidden:visible_ms<8000?View::CompleteNotice:View::Ready;
        if (work==Work::Incomplete) return racing?View::Hidden:View::Incomplete;
        return work==Work::Paused?View::Paused:View::Preparing;
    }
};

inline const wchar_t* label(View view) {
    switch(view) {
    case View::Preparing:return L"Preparing shaders in background";
    case View::Paused:return L"Shader preparation paused during race";
    case View::CompleteNotice:return L"Shader preparation complete";
    case View::Ready:return L"Shaders ready for next launch";
    case View::Incomplete:return L"Background preparation incomplete";
    default:return L"";
    }
}
inline const char* name(View view) {
    switch(view) {
    case View::Preparing:return "preparing";
    case View::Paused:return "paused";
    case View::CompleteNotice:return "complete-notice";
    case View::Ready:return "ready";
    case View::Incomplete:return "incomplete";
    default:return "hidden";
    }
}

class Overlay {
    HWND game_=nullptr, window_=nullptr;
    DWORD pid_=0;
    HFONT font_=nullptr, small_=nullptr;
    UINT dpi_=0;
    int width_=0,height_=0;
    Notice notice_;
    View view_=View::Hidden;

    static BOOL CALLBACK find(HWND window, LPARAM arg) {
        auto& self=*reinterpret_cast<Overlay*>(arg);
        DWORD pid=0;GetWindowThreadProcessId(window,&pid);
        if (pid!=self.pid_ || !IsWindowVisible(window) || GetWindow(window,GW_OWNER)) return TRUE;
        wchar_t cls[64]{};GetClassNameW(window,cls,64);
        if (!wcscmp(cls,L"ConsoleWindowClass") || !wcscmp(cls,L"PseudoConsoleWindow") || !wcsncmp(cls,L"gt5p_",5)) return TRUE;
        self.game_=window;return FALSE;
    }
    static LRESULT CALLBACK proc(HWND window, UINT message, WPARAM w, LPARAM l) {
        if (message==WM_NCCREATE) {
            auto* cs=reinterpret_cast<CREATESTRUCTW*>(l);
            SetWindowLongPtrW(window,GWLP_USERDATA,reinterpret_cast<LONG_PTR>(cs->lpCreateParams));
        }
        auto* self=reinterpret_cast<Overlay*>(GetWindowLongPtrW(window,GWLP_USERDATA));
        if (message==WM_NCHITTEST) return HTTRANSPARENT;
        if (message==WM_MOUSEACTIVATE) return MA_NOACTIVATE;
        if (message==WM_ERASEBKGND) return 1;
        if (message==WM_PAINT && self) {
            PAINTSTRUCT ps{};HDC dc=BeginPaint(window,&ps);
            HDC mem=CreateCompatibleDC(dc);
            HBITMAP bitmap=CreateCompatibleBitmap(dc,self->width_,self->height_);
            auto old=SelectObject(mem,bitmap);self->paint(mem);
            BitBlt(dc,0,0,self->width_,self->height_,mem,0,0,SRCCOPY);
            SelectObject(mem,old);DeleteObject(bitmap);DeleteDC(mem);EndPaint(window,&ps);return 0;
        }
        return DefWindowProcW(window,message,w,l);
    }
    int px(int value) const {return MulDiv(value,static_cast<int>(dpi_),96);}
    void paint(HDC dc) {
        RECT all{0,0,width_,height_};FillRect(dc,&all,static_cast<HBRUSH>(GetStockObject(BLACK_BRUSH)));
        HBRUSH fill=CreateSolidBrush(RGB(22,25,31));HPEN edge=CreatePen(PS_SOLID,1,RGB(65,78,93));
        auto ob=SelectObject(dc,fill),op=SelectObject(dc,edge);
        RoundRect(dc,0,0,width_,height_,px(16),px(16));
        SelectObject(dc,ob);SelectObject(dc,op);DeleteObject(fill);DeleteObject(edge);
        COLORREF colour=view_==View::Paused?RGB(156,165,178):
            view_==View::CompleteNotice || view_==View::Ready?RGB(105,205,150):
            view_==View::Incomplete?RGB(221,181,110):RGB(110,170,230);
        HBRUSH dot=CreateSolidBrush(colour);ob=SelectObject(dc,dot);op=SelectObject(dc,GetStockObject(NULL_PEN));
        Ellipse(dc,px(12),px(13),px(19),px(20));
        SelectObject(dc,ob);SelectObject(dc,op);DeleteObject(dot);
        SetBkMode(dc,TRANSPARENT);SetTextColor(dc,RGB(220,225,234));
        auto of=SelectObject(dc,font_);RECT text{px(29),px(7),width_-px(12),px(28)};
        DrawTextW(dc,label(view_),-1,&text,DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
        if (view_==View::CompleteNotice || view_==View::Incomplete) {
            SelectObject(dc,small_);SetTextColor(dc,RGB(172,184,201));
            RECT detail{px(29),px(29),width_-px(12),height_-px(6)};
            DrawTextW(dc,view_==View::CompleteNotice?L"Ready for your next launch":L"You can keep playing",-1,&detail,
                DT_SINGLELINE|DT_END_ELLIPSIS|DT_NOPREFIX);
        }
        SelectObject(dc,of);
    }
    void destroy() {if (IsWindow(window_)) DestroyWindow(window_);window_=nullptr;}
public:
    ~Overlay() {destroy();if (font_) DeleteObject(font_);if (small_) DeleteObject(small_);}
    Overlay()=default;
    Overlay(const Overlay&)=delete;
    Overlay& operator=(const Overlay&)=delete;
    View view() const {return view_;}
    void tick(DWORD pid, Work work, bool racing, ULONGLONG now) {
        if (pid!=pid_ || !IsWindow(game_)) {destroy();game_=nullptr;pid_=pid;}
        if (pid_ && !game_) EnumWindows(find,reinterpret_cast<LPARAM>(this));
        const bool visible=game_ && IsWindowVisible(game_) && !IsIconic(game_) && GetForegroundWindow()==game_;
        const auto view=notice_.update(work,racing,visible,now);
        if (view==View::Hidden) {
            if (view_!=view && IsWindow(window_)) ShowWindow(window_,SW_HIDE);
            view_=view;return;
        }
        UINT dpi=GetDpiForWindow(game_);if (!dpi) dpi=96;
        if (dpi!=dpi_) {
            dpi_=dpi;if (font_) DeleteObject(font_);if (small_) DeleteObject(small_);
            font_=CreateFontW(-px(13),0,0,0,FW_SEMIBOLD,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
            small_=CreateFontW(-px(12),0,0,0,FW_NORMAL,FALSE,FALSE,FALSE,DEFAULT_CHARSET,0,0,CLEARTYPE_QUALITY,0,L"Segoe UI");
        }
        RECT rc{};GetClientRect(game_,&rc);
        int width=px(360);if (width>rc.right-px(32)) width=rc.right-px(32);
        const int height=px(view==View::CompleteNotice || view==View::Incomplete?54:34);
        if (width<px(100) || rc.bottom<height+px(32)) return;
        bool changed=view_!=view || width_!=width || height_!=height;
        view_=view;width_=width;height_=height;
        if (!IsWindow(window_)) {
            HINSTANCE instance=GetModuleHandleW(nullptr);
            WNDCLASSW cls{};cls.lpfnWndProc=proc;cls.hInstance=instance;cls.lpszClassName=L"tourline_background_prepare";
            RegisterClassW(&cls);
            window_=CreateWindowExW(WS_EX_LAYERED|WS_EX_TRANSPARENT|WS_EX_NOACTIVATE|WS_EX_TOOLWINDOW,
                cls.lpszClassName,label(view),WS_POPUP,0,0,width,height,game_,nullptr,instance,this);
            if (!window_) return;
            SetLayeredWindowAttributes(window_,RGB(0,0,0),220,LWA_COLORKEY|LWA_ALPHA);changed=true;
        }
        POINT position{px(16),rc.bottom-height-px(16)};ClientToScreen(game_,&position);
        SetWindowPos(window_,HWND_TOP,position.x,position.y,width,height,SWP_NOACTIVATE|SWP_SHOWWINDOW);
        if (changed) {SetWindowTextW(window_,label(view));InvalidateRect(window_,nullptr,FALSE);}
    }
};
} // namespace background_preparation_ui
