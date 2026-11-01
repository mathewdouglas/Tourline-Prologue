// Standalone shader-preparation window, styled after the in-game PC settings panel.
// Header-only so the launcher build stays one translation unit.
//
// Status contract (prepare-status.txt), matching scripts/player_prepare.py:
//   one UTF-8 text, at most 32768 bytes; invalid UTF-8 is ignored;
//   phase words, then an optional trailing " <completed>/<total>" when the helper
//   passed a "completed" count. Python writes phase.replace('-',' ').capitalize(),
//   so "reading-game-assets" arrives as "Reading game assets 3/10".
//   Counted phases today: "Reading game assets", "Checking game archive" (bytes
//   hashed/archive size), "Reusing cache", "Vertex".
//   Uncounted phases stay indeterminate: "Checking cache", "Lookup", "Fragment",
//   "Native", "Verifying cache", a bare "Reusing cache", "Complete",
//   "Starting preparation...", and the final
//   "Complete. Normal demand compilation handles uncovered pipelines."
//   No overall percentage is derived. A missing, huge, or inverted fraction is not a count.
//   The progress control's range is the real count when both values fit in signed
//   32-bit. Larger counts keep that exact text and use a 0..1000000 fraction only
//   as the control value, so accessibility can follow the bar. No percent is drawn.
#pragma once

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <commctrl.h>

#include <algorithm>
#include <cmath>
#include <cstdint>
#include <exception>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <memory>
#include <string>

namespace preparation_ui {

enum class Result { Finished, Unavailable, Failed };

struct Parsed {
    std::wstring phase;
    std::wstring detail;
    std::wstring count;
    bool has_count = false;
    std::uint64_t completed = 0;
    std::uint64_t total = 0;
};

inline std::wstring trim_copy(const std::wstring& text) {
    size_t begin = 0;
    while (begin < text.size() && (text[begin] == L' ' || text[begin] == L'\t')) ++begin;
    size_t end = text.size();
    while (end > begin && (text[end - 1] == L' ' || text[end - 1] == L'\t')) --end;
    return text.substr(begin, end - begin);
}

inline wchar_t ascii_lower(wchar_t c) {
    return (c >= L'A' && c <= L'Z') ? static_cast<wchar_t>(c - L'A' + L'a') : c;
}

inline std::wstring ascii_lower_str(std::wstring text) {
    for (wchar_t& c : text) c = ascii_lower(c);
    return text;
}

inline std::wstring bound_text(std::wstring text, size_t max_chars) {
    if (text.size() <= max_chars) return text;
    if (max_chars == 0) return {};
    text.resize(max_chars - (max_chars > 1u ? 1u : 0u));
    if (!text.empty() && text.back() >= 0xD800 && text.back() <= 0xDBFF) text.pop_back();
    if (max_chars > 1u) text.push_back(L'\u2026');
    return text;
}

inline std::wstring group_digits(std::uint64_t value) {
    std::wstring digits = std::to_wstring(value);
    std::wstring out;
    out.reserve(digits.size() + digits.size() / 3);
    int grouped = 0;
    for (size_t i = digits.size(); i-- > 0;) {
        if (grouped == 3) { out.push_back(L','); grouped = 0; }
        out.push_back(digits[i]);
        ++grouped;
    }
    std::reverse(out.begin(), out.end());
    return out;
}

inline bool parse_u64(const std::wstring& text, size_t begin, size_t end, std::uint64_t& value) {
    if (end <= begin || end - begin > 18u) return false;
    std::uint64_t parsed = 0;
    for (size_t i = begin; i < end; ++i) {
        if (text[i] < L'0' || text[i] > L'9') return false;
        parsed = parsed * 10u + static_cast<std::uint64_t>(text[i] - L'0');
    }
    value = parsed;
    return true;
}

// Trailing " <completed>/<total>" only. Both sides are 1..18 digits, total > 0,
// and completed <= total. Anything else leaves the line uncounted.
inline bool split_count(const std::wstring& line, std::wstring& phase, std::uint64_t& completed, std::uint64_t& total) {
    auto digit = [](wchar_t c) { return c >= L'0' && c <= L'9'; };
    size_t end = line.size();
    size_t total_begin = end;
    while (total_begin > 0 && digit(line[total_begin - 1])) --total_begin;
    if (total_begin == end || total_begin == 0 || line[total_begin - 1] != L'/') return false;
    size_t completed_end = total_begin - 1;
    size_t completed_begin = completed_end;
    while (completed_begin > 0 && digit(line[completed_begin - 1])) --completed_begin;
    if (completed_begin == completed_end || completed_begin == 0) return false;
    wchar_t separator = line[completed_begin - 1];
    if (separator != L' ' && separator != L'\t') return false;
    std::uint64_t got_completed = 0, got_total = 0;
    if (!parse_u64(line, completed_begin, completed_end, got_completed)) return false;
    if (!parse_u64(line, total_begin, end, got_total)) return false;
    if (got_total == 0 || got_completed > got_total) return false;
    phase = trim_copy(line.substr(0, completed_begin));
    completed = got_completed;
    total = got_total;
    return true;
}

inline const wchar_t* known_detail(const std::wstring& phase) {
    if (phase == L"starting") return L"Starting the preparation helper.";
    if (phase == L"reading game assets") return L"Reading the selected game files.";
    if (phase == L"checking game archive") return L"Checking the selected game archive.";
    if (phase == L"checking cache") return L"Checking the preparation checkpoint.";
    if (phase == L"reusing cache") return L"Reusing verified results from the previous cache.";
    if (phase == L"lookup") return L"Locating programs in the selected game files.";
    if (phase == L"vertex") return L"Preparing vertex shaders for this step.";
    if (phase == L"fragment") return L"Preparing fragment shaders for this step.";
    if (phase == L"native") return L"Creating native pipelines for this step.";
    if (phase == L"verifying cache") return L"Checking saved native pipeline files.";
    if (phase == L"complete") return L"Uncovered pipelines and different settings use normal demand compilation.";
    return nullptr;
}

inline std::wstring count_text(const Parsed& parsed) {
    if (!parsed.has_count) return L"Not counted for this step";
    std::wstring text = group_digits(parsed.completed) + L" / " + group_digits(parsed.total);
    // Archive progress is a byte count. Leaving it unitless would look like a pipeline total.
    if (ascii_lower_str(parsed.phase) == L"checking game archive") text += L" bytes for this step";
    else text += L" for this step";
    return text;
}

inline std::wstring first_status_line(const std::wstring& text) {
    size_t index = 0;
    if (!text.empty() && text[0] == 0xFEFF) index = 1;
    while (index < text.size()) {
        size_t end = text.find_first_of(L"\r\n", index);
        if (end == std::wstring::npos) end = text.size();
        std::wstring line;
        line.reserve(end - index);
        for (size_t i = index; i < end; ++i) {
            wchar_t c = text[i];
            if (c == L'\t' || c >= 32) line.push_back(c);
        }
        line = trim_copy(line);
        if (!line.empty()) return line;
        index = end;
        while (index < text.size() && (text[index] == L'\r' || text[index] == L'\n')) ++index;
    }
    return {};
}

inline Parsed parse_status(const std::wstring& text) {
    Parsed parsed;
    const std::wstring line = first_status_line(text);
    if (line.empty()) {
        parsed.phase = L"Preparing";
        parsed.detail = L"Waiting for preparation status.";
        parsed.count = count_text(parsed);
        return parsed;
    }
    std::wstring phase;
    std::uint64_t completed = 0, total = 0;
    const bool has_count = split_count(line, phase, completed, total);
    if (!has_count) phase = line;
    if (phase.empty()) phase = L"Preparing";
    std::wstring detail;
    if (!has_count) {
        const std::wstring low = ascii_lower_str(phase);
        if (low == L"starting preparation..." || low == L"starting preparation") phase = L"Starting";
        else if (low.size() >= 8u && low.compare(0, 8u, L"complete") == 0 &&
                 (low.size() == 8u || low[8] == L'.' || low[8] == L' ' || low[8] == L'\t')) {
            std::wstring rest = trim_copy(phase.substr(8u));
            if (!rest.empty() && rest[0] == L'.') rest = trim_copy(rest.substr(1));
            phase = L"Complete";
            if (!rest.empty()) detail = rest;
        }
    }
    if (detail.empty()) {
        // Unknown text stays visible. Known phases replace the raw line with a factual step sentence.
        if (const wchar_t* known = known_detail(ascii_lower_str(phase))) detail = known;
        else detail = line;
    }
    parsed.phase = bound_text(phase, 180);
    parsed.detail = bound_text(detail, 360);
    parsed.has_count = has_count;
    parsed.completed = completed;
    parsed.total = total;
    parsed.count = count_text(parsed);
    return parsed;
}

inline std::wstring read_status_file(const std::filesystem::path& path) {
    try {
        if (!std::filesystem::is_regular_file(path) || std::filesystem::file_size(path) > 32768u) return {};
        std::ifstream in(path, std::ios::binary);
        if (!in) return {};
        // Bound the read itself: the helper can replace/grow the file after file_size().
        std::string bytes(32769u, '\0');
        in.read(bytes.data(), static_cast<std::streamsize>(bytes.size()));
        bytes.resize(static_cast<size_t>(in.gcount()));
        if (in.bad()) return {};
        if (bytes.empty() || bytes.size() > 32768u) return {};
        const int bytes_n = static_cast<int>(bytes.size());
        const int wide_n = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, bytes.data(), bytes_n, nullptr, 0);
        if (wide_n <= 0) return {};
        std::wstring text(static_cast<size_t>(wide_n), L'\0');
        if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, bytes.data(), bytes_n, text.data(), wide_n) != wide_n)
            return {};
        return text;
    } catch (const std::exception&) {
        return {};
    }
}

struct Layout {
    int client_w = 0;
    int client_h = 0;
    RECT title{};
    int rule1 = 0;
    int rule2 = 0;
    int dot1 = 0;
    int dot2 = 0;
    RECT phase_label{};
    RECT phase_field{};
    RECT phase_value{};
    RECT detail_label{};
    RECT detail_field{};
    RECT detail_value{};
    RECT step_label{};
    RECT step_field{};
    RECT step_value{};
    RECT bar{};
    RECT help{};
    RECT button{};
    RECT note{};
};

struct State {
    HWND hwnd = nullptr;
    HWND title = nullptr;
    HWND phase_label = nullptr;
    HWND phase_value = nullptr;
    HWND detail_label = nullptr;
    HWND detail_value = nullptr;
    HWND step_label = nullptr;
    HWND step_value = nullptr;
    HWND help = nullptr;
    HWND note = nullptr;
    HWND progress = nullptr;
    HWND cancel = nullptr;
    HFONT font_title = nullptr;
    HFONT font_row = nullptr;
    HFONT font_help = nullptr;
    HFONT font_note = nullptr;
    HFONT font_button = nullptr;
    HBRUSH panel = nullptr;
    HBRUSH field = nullptr;
    HICON icon = nullptr;
    bool bar_sub = false;
    bool cancelled = false;
    bool have_status = false;
    bool in_layout = false;
    int dpi = 96;
    double fit = 1;
    unsigned march = 0;
    ULONGLONG last_read = 0;
    ULONGLONG last_anim = 0;
    std::filesystem::path status_path;
    std::filesystem::path cancel_path;
    Parsed parsed;
    std::wstring phase_slot;
    std::wstring detail_slot;
    std::wstring step_slot;
    std::wstring bar_slot;
    std::wstring note_slot;
    Layout lay;
};

constexpr DWORD kStyle = WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU;
constexpr DWORD kExStyle = WS_EX_APPWINDOW;
constexpr wchar_t kClass[] = L"TourlinePrepareProgress";
constexpr wchar_t kCaption[] = L"Tourline Prologue";
constexpr wchar_t kHeading[] = L"Preparing known shaders and pipelines";
constexpr wchar_t kHelp[] =
    L"Preparing known shaders and pipelines from your game files. "
    L"Additional pipelines may be compiled as you play.";
constexpr wchar_t kNote[] = L"Cancel, Esc, or the window close button keeps completed files for resume.";
constexpr wchar_t kCancelling[] = L"Cancelling preparation. Completed files will be kept for resume...";
constexpr int kTitleId = 100;
constexpr int kPhaseLabelId = 101;
constexpr int kPhaseValueId = 102;
constexpr int kDetailLabelId = 103;
constexpr int kDetailValueId = 104;
constexpr int kStepLabelId = 105;
constexpr int kStepValueId = 106;
constexpr int kHelpId = 107;
constexpr int kNoteId = 108;
constexpr int kProgressId = 120;
constexpr DWORD kPollMs = 200;
static_assert(IDCANCEL == 2, "launcher_native.py cancels with button id 2");

inline int scaled(const State* state, int px) {
    if (px <= 0) return 0;
    double value = static_cast<double>(px) * (static_cast<double>(state->dpi) / 96.0) * state->fit;
    if (value > 8000) value = 8000;
    int n = static_cast<int>(value + 0.5);
    if (n < 1) n = 1;
    return n;
}

inline COLORREF grey(int value) { return RGB(value, value, value); }

inline void fill_rect(HDC dc, int x0, int y0, int x1, int y1, COLORREF color) {
    if (x1 <= x0 || y1 <= y0) return;
    RECT rect{x0, y0, x1, y1};
    HBRUSH brush = CreateSolidBrush(color);
    if (brush) {
        FillRect(dc, &rect, brush);
        DeleteObject(brush);
    }
}

inline int lerp_channel(int from, int to, double t) {
    if (t < 0) t = 0;
    if (t > 1) t = 1;
    return static_cast<int>(from + (to - from) * t);
}

inline int fill_px(int width, std::uint64_t completed, std::uint64_t total) {
    if (width <= 0 || total == 0 || completed == 0) return 0;
    if (completed >= total) return width;
    const double fraction = static_cast<double>(completed) / static_cast<double>(total);
    int pixels = static_cast<int>(fraction * static_cast<double>(width) + 0.5);
    if (pixels < 0) return 0;
    if (pixels > width) return width;
    return pixels;
}

inline void draw_bar(const State* state, HDC dc, const RECT& rect) {
    const int x0 = rect.left, y0 = rect.top, x1 = rect.right, y1 = rect.bottom;
    fill_rect(dc, x0, y0, x1, y1, RGB(0, 4, 0));
    int inset = scaled(state, 2);
    const int ix0 = x0 + inset, iy0 = y0 + inset, ix1 = x1 - inset, iy1 = y1 - inset;
    if (ix1 > ix0 && iy1 > iy0) {
        const int inner = ix1 - ix0;
        if (state->parsed.has_count) {
            const int width = fill_px(inner, state->parsed.completed, state->parsed.total);
            if (width > 0) fill_rect(dc, ix0, iy0, ix0 + width, iy1, state->cancelled ? grey(140) : grey(204));
        } else {
            int block = inner / 5;
            const int min_block = scaled(state, 18);
            if (block < min_block) block = min_block;
            if (block > inner) block = inner;
            const unsigned span = static_cast<unsigned>(inner + block);
            const int shift = span ? static_cast<int>(state->march % span) : 0;
            const int block_left = ix0 + shift - block;
            const int draw_left = block_left > ix0 ? block_left : ix0;
            const int block_right = block_left + block;
            const int draw_right = block_right < ix1 ? block_right : ix1;
            if (draw_right > draw_left) fill_rect(dc, draw_left, iy0, draw_right, iy1, grey(204));
        }
    }
    const int underline = y1 - scaled(state, 1);
    fill_rect(dc, x0, underline, x1, y1, RGB(99, 101, 107));
}

template <class Color>
void vertical_gradient(HDC dc, int x0, int y0, int x1, int y1, Color color) {
    if (x1 <= x0 || y1 <= y0) return;
    const double span = static_cast<double>(y1 - y0);
    for (int y = y0; y < y1; ++y) {
        const double t = (static_cast<double>(y - y0) + 0.5) / span;
        fill_rect(dc, x0, y, x1, y + 1, color(t));
    }
}

template <class Color>
void stadium(HDC dc, int x0, int y0, int x1, int y1, Color color) {
    if (x1 <= x0 || y1 <= y0) return;
    const double radius = static_cast<double>(y1 - y0) / 2.0;
    const double cy = static_cast<double>(y0) + radius;
    double mid0 = static_cast<double>(x0) + radius;
    double mid1 = static_cast<double>(x1) - radius;
    if (mid1 < mid0) mid0 = mid1 = (static_cast<double>(x0) + x1) / 2.0;
    for (int y = y0; y < y1; ++y) {
        const double yc = y + 0.5;
        const double dy = yc - cy;
        if (dy * dy > radius * radius) continue;
        const double half = std::sqrt(radius * radius - dy * dy);
        int left = static_cast<int>(mid0 - half + 0.5);
        int right = static_cast<int>(mid1 + half + 0.5);
        if (right < left) { const int swap = left; left = right; right = swap; }
        const double t = (yc - y0) / static_cast<double>(y1 - y0);
        fill_rect(dc, left, y, right, y + 1, color(t));
    }
}

inline void draw_pill(const State* state, HDC dc, const RECT& rect, bool focused) {
    const int x0 = rect.left, y0 = rect.top, x1 = rect.right, y1 = rect.bottom;
    fill_rect(dc, x0, y0, x1, y1, grey(28));
    stadium(dc, x0, y0, x1, y1, [](double) { return grey(46); });
    const int ring = scaled(state, 1);
    const int glass = scaled(state, 3);
    stadium(dc, x0 + ring, y0 + ring, x1 - ring, y1 - ring, [focused](double) {
        return focused ? RGB(168, 0, 0) : grey(0);
    });
    stadium(dc, x0 + glass, y0 + glass, x1 - glass, y1 - glass, [](double t) {
        if (t < 0.5) {
            const double u = t / 0.5;
            return RGB(lerp_channel(123, 57, u), lerp_channel(125, 56, u), lerp_channel(140, 57, u));
        }
        const double u = (t - 0.5) / 0.5;
        const int v = u < 0.6 ? lerp_channel(19, 3, u / 0.6) : lerp_channel(3, 60, (u - 0.6) / 0.4);
        return grey(v);
    });
    HFONT font = state->font_button ? state->font_button : static_cast<HFONT>(GetStockObject(DEFAULT_GUI_FONT));
    HGDIOBJ old = SelectObject(dc, font);
    SetBkMode(dc, TRANSPARENT);
    SetTextColor(dc, grey(232));
    RECT text = rect;
    DrawTextW(dc, L"Cancel", -1, &text, DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX);
    SelectObject(dc, old);
}

inline void set_control_text(HWND hwnd, std::wstring& slot, const std::wstring& text) {
    if (!hwnd || slot == text) return;
    slot = text;
    SetWindowTextW(hwnd, text.c_str());
    NotifyWinEvent(EVENT_OBJECT_NAMECHANGE, hwnd, OBJID_CLIENT, CHILDID_SELF);
}

inline void request_cancel(State* state) {
    if (!state || state->cancelled) return;
    state->cancelled = true;
    bool wrote = false;
    try {
        // Text mode matches the previous TaskDialog writer. The helper only checks that the file exists.
        std::ofstream out(state->cancel_path, std::ios::trunc);
        out << "cancel\n";
        out.flush();
        wrote = static_cast<bool>(out);
    } catch (const std::exception&) {
        wrote = false;
    }
    try {
        const wchar_t* message = wrote ? kCancelling
            : L"Could not write the cancellation request. Waiting for preparation to finish...";
        set_control_text(state->detail_value, state->detail_slot, message);
        set_control_text(state->note, state->note_slot, message);
        if (state->progress) InvalidateRect(state->progress, nullptr, FALSE);
    } catch (const std::exception&) {
        // The cancel file is already requested. A text update must not abandon the wait.
    }
}

inline void apply_parsed(State* state, const Parsed& parsed) {
    if (!state || state->cancelled) return;
    const bool count_changed = !state->have_status || state->parsed.has_count != parsed.has_count ||
        state->parsed.completed != parsed.completed || state->parsed.total != parsed.total;
    state->parsed = parsed;
    state->have_status = true;
    set_control_text(state->phase_value, state->phase_slot, parsed.phase);
    set_control_text(state->detail_value, state->detail_slot, parsed.detail);
    set_control_text(state->step_value, state->step_slot, parsed.count);
    if (state->progress) {
        set_control_text(state->progress, state->bar_slot, parsed.count);
        if (count_changed) {
            if (parsed.has_count && parsed.total <= 0x7fffffffULL && parsed.completed <= 0x7fffffffULL) {
                const int range = static_cast<int>(parsed.total);
                const int position = static_cast<int>(parsed.completed);
                SendMessageW(state->progress, PBM_SETRANGE32, 0, static_cast<LPARAM>(range));
                SendMessageW(state->progress, PBM_SETPOS, static_cast<WPARAM>(position), 0);
            } else if (parsed.has_count && parsed.total > 0) {
                // Archive byte totals can exceed signed 32-bit. The painted bar still uses the full values.
                const double fraction = static_cast<double>(parsed.completed) / static_cast<double>(parsed.total);
                int position = static_cast<int>(fraction * 1000000.0 + 0.5);
                if (position < 0) position = 0;
                if (position > 1000000) position = 1000000;
                SendMessageW(state->progress, PBM_SETRANGE32, 0, static_cast<LPARAM>(1000000));
                SendMessageW(state->progress, PBM_SETPOS, static_cast<WPARAM>(position), 0);
            } else {
                SendMessageW(state->progress, PBM_SETRANGE32, 0, static_cast<LPARAM>(1));
                SendMessageW(state->progress, PBM_SETPOS, 0, 0);
            }
            InvalidateRect(state->progress, nullptr, FALSE);
        }
    }
}

inline void refresh_status(State* state) {
    if (!state || state->cancelled) return;
    try {
        const std::wstring text = read_status_file(state->status_path);
        if (text.empty()) {
            if (!state->have_status) apply_parsed(state, parse_status(L""));
            return;
        }
        apply_parsed(state, parse_status(text));
    } catch (const std::exception&) {
        // Keep the helper running. A bad status read must not look like a finished preparation.
    }
}

inline void tick_status(State* state) {
    if (!state) return;
    const ULONGLONG now = GetTickCount64();
    if (!state->cancelled && (!state->have_status || now - state->last_read >= 100ull)) {
        state->last_read = now;
        refresh_status(state);
    }
    if (!state->parsed.has_count && now - state->last_anim >= 100ull) {
        state->last_anim = now;
        state->march += static_cast<unsigned>(scaled(state, 48));
        if (state->progress) InvalidateRect(state->progress, nullptr, FALSE);
        else InvalidateRect(state->hwnd, &state->lay.bar, FALSE);
    }
}

inline void compute_layout(State* state) {
    const auto S = [state](int px) { return scaled(state, px); };
    Layout lay{};
    lay.client_w = S(740);
    const int x0 = S(28);
    const int x1 = lay.client_w - S(28);
    const int label_right = S(196);
    const int field_left = S(210);
    int y = 0;
    lay.title = RECT{0, 0, lay.client_w, S(36)};
    y = lay.title.bottom + S(8);
    lay.rule1 = y;
    y += S(1) + S(18);
    auto row = [&](RECT& label, RECT& field, RECT& value, int height) {
        label = RECT{x0, y, label_right, y + height};
        field = RECT{field_left, y, x1, y + height};
        value = RECT{field.left + S(12), field.top + S(3), field.right - S(10), field.bottom - S(4)};
        y += height;
    };
    row(lay.phase_label, lay.phase_field, lay.phase_value, S(34));
    y += S(8);
    lay.dot1 = y;
    y += S(12);
    row(lay.detail_label, lay.detail_field, lay.detail_value, S(84));
    y += S(8);
    lay.dot2 = y;
    y += S(12);
    row(lay.step_label, lay.step_field, lay.step_value, S(34));
    y += S(12);
    lay.bar = RECT{field_left, y, x1, y + S(16)};
    y += S(16) + S(14);
    lay.help = RECT{S(36), y, lay.client_w - S(36), y + S(72)};
    y += S(72) + S(10);
    lay.rule2 = y;
    y += S(1) + S(16);
    const int button_w = S(168);
    const int button_h = S(40);
    const int button_x = (lay.client_w - button_w) / 2;
    lay.button = RECT{button_x, y, button_x + button_w, y + button_h};
    y += button_h + S(8);
    lay.note = RECT{S(24), y, lay.client_w - S(24), y + S(40)};
    y += S(40) + S(16);
    lay.client_h = y;
    state->lay = lay;
}

inline RECT monitor_work(HWND hwnd) {
    RECT work{};
    HMONITOR monitor = hwnd ? MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
                            : MonitorFromPoint(POINT{0, 0}, MONITOR_DEFAULTTOPRIMARY);
    MONITORINFO info{};
    info.cbSize = sizeof info;
    if (monitor && GetMonitorInfoW(monitor, &info)) return info.rcWork;
    SystemParametersInfoW(SPI_GETWORKAREA, 0, &work, 0);
    return work;
}

inline void place_control(HWND hwnd, const RECT& rect) {
    if (!hwnd) return;
    int width = rect.right - rect.left;
    int height = rect.bottom - rect.top;
    if (width < 0) width = 0;
    if (height < 0) height = 0;
    SetWindowPos(hwnd, nullptr, rect.left, rect.top, width, height, SWP_NOZORDER | SWP_NOACTIVATE);
}

inline void position_children(State* state) {
    place_control(state->title, state->lay.title);
    place_control(state->phase_label, state->lay.phase_label);
    place_control(state->phase_value, state->lay.phase_value);
    place_control(state->detail_label, state->lay.detail_label);
    place_control(state->detail_value, state->lay.detail_value);
    place_control(state->step_label, state->lay.step_label);
    place_control(state->step_value, state->lay.step_value);
    place_control(state->progress, state->lay.bar);
    place_control(state->help, state->lay.help);
    place_control(state->cancel, state->lay.button);
    place_control(state->note, state->lay.note);
}

inline void place_window(State* state) {
    if (!state || !state->hwnd || state->in_layout) return;
    // SetWindowPos can deliver WM_DPICHANGED. That handler only stores the DPI while
    // this is running, and a changed DPI starts another fit pass.
    struct Hold {
        bool& flag;
        explicit Hold(bool& flag) : flag(flag) { flag = true; }
        ~Hold() { flag = false; }
    };
    [[maybe_unused]] Hold hold{state->in_layout};
    int laid_out_at = state->dpi;
    for (int attempt = 0; attempt < 3; ++attempt) {
        const int dpi_seen = state->dpi;
        laid_out_at = dpi_seen;
        state->fit = 1;
        compute_layout(state);
        const RECT work = monitor_work(state->hwnd);
        const int work_w = work.right - work.left;
        const int work_h = work.bottom - work.top;
        const int margin = scaled(state, 8);
        int avail_w = work_w - margin * 2;
        int avail_h = work_h - margin * 2;
        if (avail_w < 1) avail_w = 1;
        if (avail_h < 1) avail_h = 1;
        auto outer_size = [&](int& width, int& height) {
            RECT outer{0, 0, state->lay.client_w, state->lay.client_h};
            const UINT dpi = static_cast<UINT>(state->dpi);
            if (!AdjustWindowRectExForDpi(&outer, kStyle, FALSE, kExStyle, dpi)) {
                outer = RECT{0, 0, state->lay.client_w, state->lay.client_h};
                if (!AdjustWindowRectEx(&outer, kStyle, FALSE, kExStyle)) {
                    width = state->lay.client_w;
                    height = state->lay.client_h;
                    return;
                }
            }
            width = outer.right - outer.left;
            height = outer.bottom - outer.top;
            if (width < 1) width = 1;
            if (height < 1) height = 1;
        };
        int width = 0, height = 0;
        outer_size(width, height);
        if (width > avail_w || height > avail_h) {
            // The caption does not shrink with the client, so the fit uses the client budget.
            const int chrome_w = width > state->lay.client_w ? width - state->lay.client_w : 0;
            const int chrome_h = height > state->lay.client_h ? height - state->lay.client_h : 0;
            const int client_w = state->lay.client_w > 0 ? state->lay.client_w : 1;
            const int client_h = state->lay.client_h > 0 ? state->lay.client_h : 1;
            int budget_w = avail_w - chrome_w;
            int budget_h = avail_h - chrome_h;
            if (budget_w < 1) budget_w = 1;
            if (budget_h < 1) budget_h = 1;
            const double fx = static_cast<double>(budget_w) / static_cast<double>(client_w);
            const double fy = static_cast<double>(budget_h) / static_cast<double>(client_h);
            state->fit = fx < fy ? fx : fy;
            if (state->fit > 1) state->fit = 1;
            if (state->fit < 0.01) state->fit = 0.01;
            compute_layout(state);
            outer_size(width, height);
            if ((width > avail_w || height > avail_h) && width > 0 && height > 0) {
                const double sx = static_cast<double>(avail_w) / static_cast<double>(width);
                const double sy = static_cast<double>(avail_h) / static_cast<double>(height);
                state->fit *= sx < sy ? sx : sy;
                if (state->fit < 0.01) state->fit = 0.01;
                compute_layout(state);
                outer_size(width, height);
            }
        }
        int x = work.left;
        int y = work.top;
        if (work_w > width) x = work.left + (work_w - width) / 2;
        if (height > work_h) y = work.bottom - height; // keep Cancel on screen when the work area is short
        else if (work_h > height) y = work.top + (work_h - height) / 2;
        SetWindowPos(state->hwnd, nullptr, x, y, width, height, SWP_NOZORDER | SWP_NOACTIVATE);
        if (state->dpi == dpi_seen) break;
    }
    if (state->dpi != laid_out_at) compute_layout(state);
    position_children(state);
}

inline HFONT make_font(const State* state, int px, int weight) {
    return CreateFontW(-scaled(state, px), 0, 0, 0, weight, FALSE, FALSE, FALSE, DEFAULT_CHARSET,
        OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, ANTIALIASED_QUALITY, DEFAULT_PITCH | FF_DONTCARE, L"Segoe UI");
}

inline void set_font(HWND hwnd, HFONT font) {
    if (hwnd && font) SendMessageW(hwnd, WM_SETFONT, reinterpret_cast<WPARAM>(font), TRUE);
}

inline void take_font(HFONT& slot, HFONT next) {
    HFONT old = slot;
    slot = next;
    if (old) DeleteObject(old);
}

inline void rebuild_fonts(State* state) {
    HFONT title = make_font(state, 22, FW_NORMAL);
    set_font(state->title, title);
    take_font(state->font_title, title);
    HFONT row = make_font(state, 19, FW_NORMAL);
    set_font(state->phase_label, row);
    set_font(state->phase_value, row);
    set_font(state->detail_label, row);
    set_font(state->detail_value, row);
    set_font(state->step_label, row);
    set_font(state->step_value, row);
    take_font(state->font_row, row);
    HFONT help = make_font(state, 15, FW_NORMAL);
    set_font(state->help, help);
    take_font(state->font_help, help);
    HFONT note = make_font(state, 13, FW_NORMAL);
    set_font(state->note, note);
    take_font(state->font_note, note);
    take_font(state->font_button, make_font(state, 21, FW_NORMAL));
    if (state->cancel) InvalidateRect(state->cancel, nullptr, TRUE);
}

inline void release_gdi(State* state) {
    HFONT* fonts[] = {&state->font_title, &state->font_row, &state->font_help, &state->font_note, &state->font_button};
    for (HFONT* font : fonts) {
        if (*font) { DeleteObject(*font); *font = nullptr; }
    }
    if (state->panel) { DeleteObject(state->panel); state->panel = nullptr; }
    if (state->field) { DeleteObject(state->field); state->field = nullptr; }
}

inline void paint_window(State* state, HDC dc, const RECT& client) {
    fill_rect(dc, 0, 0, client.right, client.bottom, grey(28));
    vertical_gradient(dc, state->lay.title.left, state->lay.title.top, state->lay.title.right, state->lay.title.bottom,
        [](double t) {
            if (t < 0.04) return RGB(45, 45, 48);
            if (t < 0.1) return grey(27);
            if (t < 0.3) return grey(lerp_channel(9, 4, (t - 0.1) / 0.2));
            return grey(lerp_channel(4, 28, (t - 0.3) / 0.7));
        });
    const int rule_h = scaled(state, 1);
    fill_rect(dc, 0, state->lay.rule1, client.right, state->lay.rule1 + rule_h, grey(76));
    fill_rect(dc, 0, state->lay.rule2, client.right, state->lay.rule2 + rule_h, grey(76));
    const int dot = scaled(state, 2);
    const int step = scaled(state, 7);
    auto dots = [&](int y) {
        for (int x = scaled(state, 26); x < client.right - scaled(state, 26); x += step)
            fill_rect(dc, x, y, x + dot, y + rule_h, grey(96));
    };
    dots(state->lay.dot1);
    dots(state->lay.dot2);
    auto field = [&](const RECT& rect) {
        fill_rect(dc, rect.left, rect.top, rect.right, rect.bottom, RGB(0, 4, 0));
        fill_rect(dc, rect.left, rect.bottom - rule_h, rect.right, rect.bottom, RGB(99, 101, 107));
    };
    field(state->lay.phase_field);
    field(state->lay.detail_field);
    field(state->lay.step_field);
    if (!state->progress) draw_bar(state, dc, state->lay.bar);
}

inline LRESULT CALLBACK bar_proc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp, UINT_PTR, DWORD_PTR context) {
    auto* state = reinterpret_cast<State*>(context);
    if (msg == WM_ERASEBKGND) return 1;
    if (msg == WM_PRINTCLIENT && state) {
        RECT rect{};
        GetClientRect(hwnd, &rect);
        draw_bar(state, reinterpret_cast<HDC>(wp), rect);
        return 0;
    }
    if (msg == WM_PAINT && state) {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(hwnd, &ps);
        RECT rect{};
        GetClientRect(hwnd, &rect);
        draw_bar(state, dc, rect);
        EndPaint(hwnd, &ps);
        return 0;
    }
    return DefSubclassProc(hwnd, msg, wp, lp);
}

inline HWND make_control(HWND parent, const wchar_t* klass, const wchar_t* text, DWORD style, int id) {
    return CreateWindowExW(0, klass, text, WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | style,
        0, 0, 0, 0, parent, reinterpret_cast<HMENU>(static_cast<INT_PTR>(id)), GetModuleHandleW(nullptr), nullptr);
}

inline LRESULT CALLBACK wndproc(HWND hwnd, UINT msg, WPARAM wp, LPARAM lp) {
    if (msg == WM_NCCREATE) {
        auto* created = reinterpret_cast<CREATESTRUCTW*>(lp);
        auto* state = reinterpret_cast<State*>(created->lpCreateParams);
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(state));
        if (state) state->hwnd = hwnd;
        return DefWindowProcW(hwnd, msg, wp, lp);
    }
    auto* state = reinterpret_cast<State*>(GetWindowLongPtrW(hwnd, GWLP_USERDATA));
    if (!state) return DefWindowProcW(hwnd, msg, wp, lp);
    switch (msg) {
    case WM_CREATE: {
        state->dpi = static_cast<int>(GetDpiForWindow(hwnd));
        if (state->dpi < 96) state->dpi = 96;
        state->panel = CreateSolidBrush(grey(28));
        state->field = CreateSolidBrush(RGB(0, 4, 0));
        if (!state->panel || !state->field) return -1;
        const DWORD label = SS_RIGHT | SS_CENTERIMAGE | SS_NOPREFIX;
        const DWORD value = SS_LEFT | SS_CENTERIMAGE | SS_ENDELLIPSIS | SS_NOPREFIX;
        // Transparent so the header gradient shows through the real title text.
        state->title = CreateWindowExW(WS_EX_TRANSPARENT, L"STATIC", kHeading,
            WS_CHILD | WS_VISIBLE | WS_CLIPSIBLINGS | SS_CENTER | SS_CENTERIMAGE | SS_NOPREFIX,
            0, 0, 0, 0, hwnd, reinterpret_cast<HMENU>(static_cast<INT_PTR>(kTitleId)), GetModuleHandleW(nullptr), nullptr);
        state->phase_label = make_control(hwnd, L"STATIC", L"Phase", label, kPhaseLabelId);
        state->phase_value = make_control(hwnd, L"STATIC", L"", value, kPhaseValueId);
        state->detail_label = make_control(hwnd, L"STATIC", L"Detail", label, kDetailLabelId);
        state->detail_value = make_control(hwnd, L"STATIC", L"", SS_LEFT | SS_EDITCONTROL | SS_NOPREFIX, kDetailValueId);
        state->step_label = make_control(hwnd, L"STATIC", L"This step", label, kStepLabelId);
        state->step_value = make_control(hwnd, L"STATIC", L"", value, kStepValueId);
        state->help = make_control(hwnd, L"STATIC", kHelp, SS_CENTER | SS_EDITCONTROL | SS_NOPREFIX, kHelpId);
        state->note = make_control(hwnd, L"STATIC", kNote, SS_CENTER | SS_EDITCONTROL | SS_NOPREFIX, kNoteId);
        state->note_slot = kNote;
        state->progress = make_control(hwnd, PROGRESS_CLASSW, L"Not counted for this step", 0, kProgressId);
        state->cancel = make_control(hwnd, L"BUTTON", L"Cancel", WS_TABSTOP | BS_OWNERDRAW | BS_DEFPUSHBUTTON, IDCANCEL);
        if (!state->title || !state->cancel || !state->phase_value || !state->detail_value || !state->step_value) return -1;
        if (state->progress && SetWindowSubclass(state->progress, bar_proc, 1, reinterpret_cast<DWORD_PTR>(state)))
            state->bar_sub = true;
        else if (state->progress) {
            DestroyWindow(state->progress);
            state->progress = nullptr;
        }
        if (state->icon) {
            SendMessageW(hwnd, WM_SETICON, ICON_BIG, reinterpret_cast<LPARAM>(state->icon));
            SendMessageW(hwnd, WM_SETICON, ICON_SMALL, reinterpret_cast<LPARAM>(state->icon));
        }
        place_window(state);
        rebuild_fonts(state);
        refresh_status(state);
        return 0;
    }
    case WM_DPICHANGED:
        state->dpi = static_cast<int>(HIWORD(wp));
        if (state->dpi < 96) state->dpi = 96;
        if (!state->in_layout) {
            place_window(state);
            rebuild_fonts(state);
            InvalidateRect(hwnd, nullptr, TRUE);
        }
        return 0;
    case WM_ERASEBKGND:
        if (state->panel) {
            RECT rect{};
            GetClientRect(hwnd, &rect);
            FillRect(reinterpret_cast<HDC>(wp), &rect, state->panel);
            return 1;
        }
        break;
    case WM_PAINT: {
        PAINTSTRUCT ps;
        HDC dc = BeginPaint(hwnd, &ps);
        RECT rect{};
        GetClientRect(hwnd, &rect);
        HDC memory = CreateCompatibleDC(dc);
        HBITMAP bitmap = nullptr;
        if (memory && rect.right > 0 && rect.bottom > 0)
            bitmap = CreateCompatibleBitmap(dc, rect.right, rect.bottom);
        if (memory && bitmap) {
            HGDIOBJ old = SelectObject(memory, bitmap);
            paint_window(state, memory, rect);
            BitBlt(dc, 0, 0, rect.right, rect.bottom, memory, 0, 0, SRCCOPY);
            SelectObject(memory, old);
        } else {
            paint_window(state, dc, rect);
        }
        if (bitmap) DeleteObject(bitmap);
        if (memory) DeleteDC(memory);
        EndPaint(hwnd, &ps);
        return 0;
    }
    case WM_PRINTCLIENT: {
        RECT rect{};
        GetClientRect(hwnd, &rect);
        paint_window(state, reinterpret_cast<HDC>(wp), rect);
        return 0;
    }
    case WM_DRAWITEM: {
        const auto* item = reinterpret_cast<DRAWITEMSTRUCT*>(lp);
        if (item && item->CtlID == static_cast<UINT>(IDCANCEL)) {
            draw_pill(state, item->hDC, item->rcItem, (item->itemState & (ODS_FOCUS | ODS_SELECTED)) != 0);
            return TRUE;
        }
        break;
    }
    case WM_CTLCOLORSTATIC: {
        HDC dc = reinterpret_cast<HDC>(wp);
        const int id = GetDlgCtrlID(reinterpret_cast<HWND>(lp));
        if (id == kTitleId) {
            SetBkMode(dc, TRANSPARENT);
            SetTextColor(dc, grey(178));
            return reinterpret_cast<LRESULT>(GetStockObject(HOLLOW_BRUSH));
        }
        SetBkMode(dc, OPAQUE);
        if (id == kPhaseValueId || id == kDetailValueId || id == kStepValueId) {
            SetBkColor(dc, RGB(0, 4, 0));
            SetTextColor(dc, grey(204));
            return reinterpret_cast<LRESULT>(state->field);
        }
        SetBkColor(dc, grey(28));
        COLORREF color = grey(190);
        if (id == kHelpId) color = grey(150);
        else if (id == kNoteId) color = grey(130);
        SetTextColor(dc, color);
        return reinterpret_cast<LRESULT>(state->panel);
    }
    case WM_COMMAND:
        if (LOWORD(wp) == static_cast<WORD>(IDCANCEL)) { request_cancel(state); return 0; }
        break;
    case WM_CLOSE:
        // Close stays on screen until the helper exits. Destroying here would hide that wait.
        request_cancel(state);
        return 0;
    case TDM_CLICK_BUTTON:
        // launcher_native.py sends this to the top-level preparation window with IDCANCEL (2).
        if (wp == static_cast<WPARAM>(IDCANCEL)) request_cancel(state);
        return 0;
    case DM_GETDEFID:
        return MAKELRESULT(IDCANCEL, DC_HASDEFID);
    case WM_ACTIVATE:
        if (LOWORD(wp) != WA_INACTIVE && state->cancel) SetFocus(state->cancel);
        return 0;
    case WM_DESTROY:
        if (state->bar_sub && state->progress) {
            RemoveWindowSubclass(state->progress, bar_proc, 1);
            state->bar_sub = false;
        }
        return 0;
    case WM_NCDESTROY:
        // Children are already gone. Deleting fonts in WM_DESTROY could run during a child paint.
        release_gdi(state);
        state->hwnd = nullptr;
        SetWindowLongPtrW(hwnd, GWLP_USERDATA, 0);
        break;
    default:
        break;
    }
    return DefWindowProcW(hwnd, msg, wp, lp);
}

inline bool ensure_class(HICON icon) {
    WNDCLASSW existing{};
    HINSTANCE instance = GetModuleHandleW(nullptr);
    if (GetClassInfoW(instance, kClass, &existing)) return existing.lpfnWndProc == wndproc;
    WNDCLASSW wc{};
    wc.style = CS_HREDRAW | CS_VREDRAW;
    wc.lpfnWndProc = wndproc;
    wc.hInstance = instance;
    wc.hCursor = LoadCursorW(nullptr, IDC_ARROW);
    wc.hIcon = icon;
    wc.lpszClassName = kClass;
    return RegisterClassW(&wc) != 0;
}

inline Result show(HANDLE process, const std::filesystem::path& status_path, const std::filesystem::path& cancel_path, HICON icon) {
    if (!process) return Result::Failed;
    INITCOMMONCONTROLSEX controls{sizeof controls, ICC_PROGRESS_CLASS};
    InitCommonControlsEx(&controls);
    if (!ensure_class(icon)) return Result::Unavailable;
    auto state = std::make_unique<State>();
    state->status_path = status_path;
    state->cancel_path = cancel_path;
    state->icon = icon;
    struct Window {
        HWND hwnd = nullptr;
        ~Window() { if (hwnd && IsWindow(hwnd)) DestroyWindow(hwnd); }
    } window;
    try {
        window.hwnd = CreateWindowExW(kExStyle, kClass, kCaption, kStyle,
            CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT, CW_USEDEFAULT,
            nullptr, nullptr, GetModuleHandleW(nullptr), state.get());
        if (!window.hwnd) return Result::Unavailable;
        if (WaitForSingleObject(process, 0) == WAIT_OBJECT_0) return Result::Finished;
        ShowWindow(window.hwnd, SW_SHOWNORMAL);
        UpdateWindow(window.hwnd);
        SetForegroundWindow(window.hwnd);
        if (state->cancel) SetFocus(state->cancel);
        for (;;) {
            if (!IsWindow(window.hwnd)) return Result::Failed;
            const DWORD wait = MsgWaitForMultipleObjects(1, &process, FALSE, kPollMs, QS_ALLINPUT);
            if (wait == WAIT_FAILED) return Result::Failed;
            MSG message;
            while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
                // This launcher does not stop on WM_QUIT. Requeueing it would dismiss the later error box.
                if (message.message == WM_QUIT) continue;
                const bool ours = message.hwnd == window.hwnd || IsChild(window.hwnd, message.hwnd);
                if (ours && message.message == WM_KEYDOWN &&
                    (message.wParam == static_cast<WPARAM>(VK_ESCAPE) ||
                     message.wParam == static_cast<WPARAM>(VK_CANCEL) ||
                     message.wParam == static_cast<WPARAM>(VK_RETURN))) {
                    request_cancel(state.get());
                    continue;
                }
                if (IsWindow(window.hwnd) && IsDialogMessageW(window.hwnd, &message)) continue;
                TranslateMessage(&message);
                DispatchMessageW(&message);
            }
            if (IsWindow(window.hwnd)) tick_status(state.get());
            if (WaitForSingleObject(process, 0) == WAIT_OBJECT_0) return Result::Finished;
        }
    } catch (const std::exception&) {
        window.hwnd = nullptr;
        if (state->hwnd && IsWindow(state->hwnd)) DestroyWindow(state->hwnd);
        return Result::Failed;
    }
}

} // namespace preparation_ui
