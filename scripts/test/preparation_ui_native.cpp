// Tests the production preparation window with a waitable stand-in, never a game.
// Build with /std:c++17 /EHsc /MT /DUNICODE /D_UNICODE /D_WIN32_WINNT=0x0A00
// and user32.lib gdi32.lib comctl32.lib. Parent serializes executable tests.
#include "../../launcher/preparation_ui.h"
#include <iostream>
#include <stdexcept>
#include <thread>

static void require(bool valid, const char* message) {
    if (!valid) throw std::runtime_error(message);
}

static void selftest(const std::filesystem::path& root) {
    using namespace preparation_ui;
    auto zero = parse_status(L"Vertex 0/10");
    require(zero.has_count && zero.completed == 0 && zero.total == 10, "zero count");
    auto archive = parse_status(L"Checking game archive 2147483648/4294967296");
    require(archive.has_count && archive.count == L"2,147,483,648 / 4,294,967,296 bytes for this step", "64-bit byte count");
    for (const auto* text : {L"Vertex 5/0", L"Vertex 11/10", L"Vertex -1/10",
                            L"Vertex 1/1000000000000000000", L"Vertex 1/a", L"Fragment"})
        require(!parse_status(text).has_count, "invalid or uncounted status");
    require(parse_status(L"\xFEFF\r\n\tVertex 2/10\r\nignored 5/7").completed == 2, "BOM/first line");
    require(parse_status(L"New phase 5/7").detail == L"New phase 5/7", "unknown phase retained");
    auto complete = parse_status(L"Complete. Remaining work stays on demand.");
    require(complete.phase == L"Complete" && complete.detail == L"Remaining work stays on demand.", "completion detail");
    require(parse_status(std::wstring(1000, L'x')).phase.size() <= 180, "phase bound");
    require(parse_status(std::wstring(1000, L'x')).detail.size() <= 360, "detail bound");
    require(bound_text(std::wstring(178, L'x') + L"\xD83D\xDE00yy", 180).back() == L'\x2026', "surrogate bound");
    const auto status = root / L"reader.txt";
    auto write = [&](const std::string& bytes) { std::ofstream(status, std::ios::binary) << bytes; };
    write("Vertex 3/10");
    require(read_status_file(status) == L"Vertex 3/10", "valid UTF8");
    write(std::string(32768, 'a'));
    require(read_status_file(status).size() == 32768, "maximum read");
    write(std::string(32769, 'a'));
    require(read_status_file(status).empty(), "oversized read");
    write("\xFF\xFE");
    require(read_status_file(status).empty(), "invalid UTF8");
    require(read_status_file(root / L"absent").empty(), "missing status");
    HANDLE event = CreateEventW(nullptr, TRUE, TRUE, nullptr);
    require(event != nullptr, "event");
    DWORD before = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    for (int i = 0; i < 6; ++i)
        require(show(event, status, root / L"cancel", nullptr) == Result::Finished, "signalled completion");
    DWORD after = GetGuiResources(GetCurrentProcess(), GR_GDIOBJECTS);
    require(after <= before + 5, "GDI resources retained across windows");
    CloseHandle(event);
    require(show(INVALID_HANDLE_VALUE, status, root / L"cancel", nullptr) == Result::Failed, "invalid wait fails");
    std::cout << "Status bounds, counts, reader, completion, wait failure and GDI cleanup: passed\n";
}

int wmain(int argc, wchar_t** argv) {
    if (argc != 3) return 64;
    try {
        std::filesystem::path root = argv[2];
        std::filesystem::create_directories(root);
        if (!wcscmp(argv[1], L"--selftest")) { selftest(root); return 0; }
        if (wcscmp(argv[1], L"--window")) return 64;
        HANDLE event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        if (!event) return 1;
        std::thread finisher([&] {
            // The controller checks cancellation does not hide the window or end this wait.
            for (int i = 0; i < 300; ++i) {
                if (std::filesystem::exists(root / L"finish")) break;
                Sleep(100);
            }
            SetEvent(event);
        });
        const auto result = preparation_ui::show(event, root / L"status.txt", root / L"cancel", nullptr);
        finisher.join();
        CloseHandle(event);
        return result == preparation_ui::Result::Finished ? 0 : 1;
    } catch (const std::exception& e) {
        std::cerr << e.what() << '\n';
        return 1;
    }
}
