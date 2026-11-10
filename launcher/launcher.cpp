// Native first-run launcher. No game code, decryption keys or game data belong here.
#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <commctrl.h>
#include <bcrypt.h>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <vector>
#include <string>
#include <array>
#include <cstdio>
#include <algorithm>
#include <cwctype>
#include "preparation_ui.h"
#include "first_run_preparation.h"
#include "background_preparation_ui.h"
#include "storage_link.h"
#include "../src/gt5p_restart.h"

namespace fs = std::filesystem;
struct Failure { std::wstring message; };
[[noreturn]] static void fail(const std::wstring& s) { throw Failure{s}; }
struct Handle {
    HANDLE h = INVALID_HANDLE_VALUE;
    explicit Handle(HANDLE v) : h(v) {}
    ~Handle() { if (h && h != INVALID_HANDLE_VALUE) CloseHandle(h); }
    Handle(const Handle&) = delete;
};
static fs::path install, data;
static bool quiet = false;
static bool silent_errors = false;
static volatile LONG background_game_pid=0;
static std::wstring profile(const fs::path& file, const wchar_t* section, const wchar_t* key) {
    std::array<wchar_t, 32768> b{};
    const DWORD n = GetPrivateProfileStringW(section, key, L"", b.data(), (DWORD)b.size(), file.c_str());
    if (n == b.size() - 1) fail(L"A configuration path is too long.");
    return b.data();
}
static void setting(const fs::path& file, const wchar_t* key, const fs::path& value) {
    if (!WritePrivateProfileStringW(L"game", key, value.c_str(), file.c_str()))
        fail(L"Could not save setup: " + file.wstring());
}
static std::wstring env(const wchar_t* key) {
    DWORD n = GetEnvironmentVariableW(key, nullptr, 0);
    if (!n) return {};
    std::vector<wchar_t> b(n);
    GetEnvironmentVariableW(key, b.data(), n);
    return b.data();
}
// Keep <home>\selected-storage (read by recomplauncher.json) naming the selected storage.
// Best effort: a failure is logged and never stops the game. GT5P_STORAGE_LINK=0 disables it.
static void link_storage(const fs::path& home, const fs::path& selected) {
    if (env(L"GT5P_STORAGE_LINK") == L"0") return;
    auto problem = storage_link::sync(home, selected);
    if (problem.empty()) return;
    fwprintf(stderr, L"%ls\n", problem.c_str());
    try {
        fs::create_directories(data/L"logs");
        std::wofstream(data/L"logs"/L"storage-link.err", std::ios::app) << problem << L'\n';
    } catch (...) {}
}
static void setenv(const wchar_t* key, const std::wstring& value) {
    if (!SetEnvironmentVariableW(key, value.c_str())) fail(L"Could not set launch environment.");
}
static HICON brand_icon() {
    static HICON icon = reinterpret_cast<HICON>(LoadImageW(GetModuleHandleW(nullptr), MAKEINTRESOURCEW(1),
        IMAGE_ICON, GetSystemMetrics(SM_CXICON), GetSystemMetrics(SM_CYICON), 0));
    return icon;
}
static void brand(TASKDIALOGCONFIG& td) {
    HICON icon = brand_icon();
    if (!icon) return;
    td.dwFlags |= TDF_USE_HICON_MAIN;
    td.hMainIcon = icon;
}
// The current runtime's VFS uses ANSI CRT file paths. Reject lossy conversion
// instead of accepting a path which will silently refer to a different file.
static void runtime_path(const fs::path& p) {
    BOOL lossy = FALSE;
    UINT cp = GetACP();
    int n = WideCharToMultiByte(cp, cp == CP_UTF8 ? WC_ERR_INVALID_CHARS : WC_NO_BEST_FIT_CHARS,
        p.c_str(), -1, nullptr, 0, nullptr, cp == CP_UTF8 ? nullptr : &lossy);
    if (!n || lossy || n >= 480)
        fail(L"The current game runtime cannot use this path. Choose a shorter folder with characters supported by your Windows language:\n\n" + p.wstring());
}
static std::wstring hash(const fs::path& file) {
    std::ifstream in(file, std::ios::binary);
    if (!in) fail(L"Cannot read: " + file.wstring());
    BCRYPT_ALG_HANDLE alg = nullptr;
    BCRYPT_HASH_HANDLE ctx = nullptr;
    if (BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, nullptr, 0) < 0)
        fail(L"Windows SHA-256 is unavailable.");
    DWORD bytes = 0, got = 0;
    NTSTATUS rc = BCryptGetProperty(alg, BCRYPT_OBJECT_LENGTH, (PUCHAR)&bytes, sizeof bytes, &got, 0);
    std::vector<unsigned char> obj(bytes), block(65536);
    std::array<unsigned char, 32> digest{};
    if (rc >= 0) rc = BCryptCreateHash(alg, &ctx, obj.data(), bytes, nullptr, 0, 0);
    while (rc >= 0 && in) {
        in.read((char*)block.data(), block.size());
        if (in.gcount()) rc = BCryptHashData(ctx, block.data(), (ULONG)in.gcount(), 0);
    }
    if (rc >= 0 && !in.bad()) rc = BCryptFinishHash(ctx, digest.data(), (ULONG)digest.size(), 0);
    else rc = (NTSTATUS)0xC0000001L;
    if (ctx) BCryptDestroyHash(ctx);
    BCryptCloseAlgorithmProvider(alg, 0);
    if (rc < 0) fail(L"Could not hash: " + file.wstring());
    std::wstring out;
    for (auto b : digest) { out += L"0123456789abcdef"[b >> 4]; out += L"0123456789abcdef"[b & 15]; }
    return out;
}
static std::vector<unsigned char> read_small(const fs::path& p) {
    if (!fs::is_regular_file(p) || fs::file_size(p) > 65536) fail(L"Missing or invalid PARAM.SFO:\n\n"+p.wstring());
    std::ifstream f(p, std::ios::binary);
    return std::vector<unsigned char>(std::istreambuf_iterator<char>(f), {});
}
static unsigned le(const std::vector<unsigned char>& b, size_t at, size_t n) {
    if (at > b.size() || n > b.size() - at) fail(L"Malformed PARAM.SFO.");
    unsigned v = 0;
    for (size_t i = 0; i < n; ++i) v |= unsigned(b[at+i]) << (8*i);
    return v;
}
static std::string text_at(const std::vector<unsigned char>& b, size_t at, size_t n) {
    if (at > b.size() || n > b.size() - at) fail(L"Malformed PARAM.SFO.");
    std::string s;
    for (size_t i = 0; i < n && b[at+i]; ++i) s += char(b[at+i]);
    return s;
}
static fs::path game_folder(fs::path p) {
    if (!fs::exists(p / L"PARAM.SFO") && fs::exists(p / L"PS3_GAME")) p /= L"PS3_GAME";
    auto b = read_small(p / L"PARAM.SFO");
    if (le(b, 0, 4) != 0x46535000) fail(L"This is not a PS3 game folder.");
    size_t keys = le(b, 8, 4), values = le(b, 12, 4), count = le(b, 16, 4);
    if (count > 256) fail(L"Malformed PARAM.SFO table.");
    std::string id, version;
    for (size_t i = 0; i < count; ++i) {
        size_t at = 20 + i * 16, key = keys + le(b, at, 2);
        if (key >= b.size()) fail(L"Malformed PARAM.SFO key.");
        auto name = text_at(b, key, b.size()-key);
        auto value = text_at(b, values + le(b, at+12, 4), le(b, at+4, 4));
        if (name == "TITLE_ID") id = value;
        if (name == "VERSION") version = value;
    }
    if (id != "BCUS98158" || version != "03.00")
        fail(L"This release supports Gran Turismo 5 Prologue BCUS98158 v03.00 (US disc). Select that extracted game's folder.");
    for (const wchar_t* name : { L"GT.VOL", L"TV.DAT" })
        if (!fs::is_regular_file(p / L"USRDIR" / name) || !fs::file_size(p / L"USRDIR" / name))
            fail(L"The selected dump is missing USRDIR\\" + std::wstring(name) + L". An ISO must be extracted first.");
    p = fs::canonical(p);
    runtime_path(p);
    return p;
}
static fs::path pick(bool folder, const wchar_t* title, const wchar_t* label = L"Decrypted executable", const wchar_t* pattern = L"*.elf") {
    IFileOpenDialog* dialog = nullptr;
    if (FAILED(CoCreateInstance(CLSID_FileOpenDialog, nullptr, CLSCTX_INPROC_SERVER, IID_PPV_ARGS(&dialog))))
        fail(L"Windows file picker could not be opened.");
    DWORD flags = FOS_FORCEFILESYSTEM | FOS_PATHMUSTEXIST | FOS_NOCHANGEDIR;
    dialog->SetOptions(flags | (folder ? FOS_PICKFOLDERS : FOS_FILEMUSTEXIST));
    COMDLG_FILTERSPEC filter{label, pattern};
    if (!folder) dialog->SetFileTypes(1, &filter);
    dialog->SetTitle(title);
    HRESULT hr = dialog->Show(nullptr);
    fs::path result;
    if (SUCCEEDED(hr)) {
        IShellItem* item = nullptr;
        if (SUCCEEDED(dialog->GetResult(&item))) {
            PWSTR path = nullptr;
            if (SUCCEEDED(item->GetDisplayName(SIGDN_FILESYSPATH, &path))) { result = path; CoTaskMemFree(path); }
            item->Release();
        }
    }
    dialog->Release();
    if (hr == HRESULT_FROM_WIN32(ERROR_CANCELLED)) return {};
    if (FAILED(hr) || result.empty()) fail(L"The selected path could not be read.");
    return result;
}
// Windows argv quoting, not shell quoting. No user paths are sent to cmd.exe.
static std::wstring quote(const fs::path& p) {
    std::wstring out = L"\"";
    unsigned slashes = 0;
    for (wchar_t c : p.wstring()) {
        if (c == L'\\') { ++slashes; continue; }
        out.append(slashes * (c == L'"' ? 2 : 1), L'\\'); slashes = 0;
        if (c == L'"') out += L'\\';
        out += c;
    }
    out.append(slashes * 2, L'\\');
    return out + L'"';
}
static std::wstring utf8_file(const fs::path& path) {
    if (!fs::is_regular_file(path) || fs::file_size(path)>32768) return {};
    std::ifstream f(path,std::ios::binary);
    std::string bytes((std::istreambuf_iterator<char>(f)),{});
    int n=MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,bytes.data(),(int)bytes.size(),nullptr,0);
    if (!n) return {};
    std::wstring text(n,L'\0');
    MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,bytes.data(),(int)bytes.size(),text.data(),n);
    return text;
}
struct PrepareDialog { HANDLE process; bool cancelled=false; };
static HRESULT CALLBACK prepare_dialog(HWND window,UINT notification,WPARAM button,LPARAM,LONG_PTR context) {
    auto& state=*reinterpret_cast<PrepareDialog*>(context);
    if (notification==TDN_CREATED) {
        SendMessageW(window,TDM_ENABLE_BUTTON,IDOK,FALSE);
        SendMessageW(window,TDM_SET_PROGRESS_BAR_MARQUEE,TRUE,50);
    }
    if (notification==TDN_TIMER) {
        if (WaitForSingleObject(state.process,0)==WAIT_OBJECT_0) {
            SendMessageW(window,TDM_ENABLE_BUTTON,IDOK,TRUE);
            SendMessageW(window,TDM_CLICK_BUTTON,IDOK,0);
        } else if (!state.cancelled) {
            auto text=utf8_file(data/L"prepare-status.txt");
            if (!text.empty()) SendMessageW(window,TDM_SET_ELEMENT_TEXT,TDE_CONTENT,(LPARAM)text.c_str());
        }
    }
    if (notification==TDN_BUTTON_CLICKED && button==IDOK && WaitForSingleObject(state.process,0)!=WAIT_OBJECT_0) return S_FALSE;
    if (notification==TDN_BUTTON_CLICKED && button==IDCANCEL) {
        state.cancelled=true;
        std::ofstream(data/L"prepare.cancel") << "cancel\n";
        SendMessageW(window,TDM_SET_ELEMENT_TEXT,TDE_CONTENT,(LPARAM)L"Cancelling preparation. Completed files will be kept for resume...");
        return S_FALSE;
    }
    return S_OK;
}
static DWORD run(const fs::path& exe, const std::wstring& args, const fs::path& cwd, const wchar_t* tag, bool preparation=false) {
    fs::create_directories(data / L"logs");
    SECURITY_ATTRIBUTES sa{sizeof sa, nullptr, TRUE};
    Handle out(CreateFileW((data/L"logs"/(std::wstring(tag)+L".out")).c_str(), GENERIC_WRITE,
        FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr));
    Handle err(CreateFileW((data/L"logs"/(std::wstring(tag)+L".err")).c_str(), GENERIC_WRITE,
        FILE_SHARE_READ, &sa, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr));
    Handle input(CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, nullptr));
    if (out.h == INVALID_HANDLE_VALUE || err.h == INVALID_HANDLE_VALUE || input.h == INVALID_HANDLE_VALUE)
        fail(L"Could not open launch logs in " + (data/L"logs").wstring());
    STARTUPINFOW si{}; si.cb = sizeof si; si.dwFlags = STARTF_USESTDHANDLES;
    si.hStdInput = input.h; si.hStdOutput = out.h; si.hStdError = err.h;
    Handle job(CreateJobObjectW(nullptr, nullptr));
    JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
    limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
    if (!job.h || !SetInformationJobObject(job.h, JobObjectExtendedLimitInformation, &limits, sizeof limits))
        fail(L"Could not create the application process group.");
    PROCESS_INFORMATION pi{};
    std::wstring command = quote(exe) + L" " + args;
    if (!CreateProcessW(exe.c_str(), command.data(), nullptr, nullptr, TRUE, CREATE_NO_WINDOW|CREATE_SUSPENDED, nullptr, cwd.c_str(), &si, &pi))
        fail(L"Could not start " + exe.wstring() + L" (Windows error " + std::to_wstring(GetLastError()) + L"). Re-extract the complete release ZIP.");
    Handle process(pi.hProcess), thread(pi.hThread);
    struct Playing { bool active; ~Playing() {if (active) InterlockedExchange(&background_game_pid,0);} } playing{!wcscmp(tag,L"play")};
    if (playing.active) InterlockedExchange(&background_game_pid,static_cast<LONG>(pi.dwProcessId));
    if (!AssignProcessToJobObject(job.h, process.h)) {
        TerminateProcess(process.h, 1); // only the suspended child created above
        fail(L"Could not attach the launched application to its process group.");
    }
    if (ResumeThread(thread.h) == (DWORD)-1) fail(L"Could not resume the launched application.");
    if (preparation) {
        // GT5P_PREPARE_UI=0 keeps the TaskDialog. Unset or any other value uses the preparation window.
        preparation_ui::Result shown = preparation_ui::Result::Unavailable;
        if (env(L"GT5P_PREPARE_UI") != L"0")
            shown = preparation_ui::show(process.h, data/L"prepare-status.txt", data/L"prepare.cancel", brand_icon());
        if (shown == preparation_ui::Result::Failed)
            fail(L"Could not keep the preparation window open.");
        if (shown != preparation_ui::Result::Finished) {
            PrepareDialog state{process.h};
            TASKDIALOGCONFIG td{};td.cbSize=sizeof td;
            td.dwFlags=(TASKDIALOG_FLAGS)(TDF_CALLBACK_TIMER|TDF_SHOW_MARQUEE_PROGRESS_BAR|TDF_ALLOW_DIALOG_CANCELLATION);
            td.pszWindowTitle=L"Tourline Prologue";
            td.pszMainInstruction=L"Preparing known shaders and pipelines";
            td.pszContent=L"Verifying your game and preparation inputs...";
            td.dwCommonButtons=TDCBF_CANCEL_BUTTON|TDCBF_OK_BUTTON;
            td.pfCallback=prepare_dialog;td.lpCallbackData=(LONG_PTR)&state;
            brand(td);
            if (FAILED(TaskDialogIndirect(&td,nullptr,nullptr,nullptr))) fail(L"Could not open preparation progress.");
        }
    }
    // Keep this thread's dialogs responsive while either child is running.
    for (;;) {
        DWORD w = MsgWaitForMultipleObjects(1, &process.h, FALSE, INFINITE, QS_ALLINPUT);
        if (w == WAIT_OBJECT_0) break;
        if (w == WAIT_FAILED) fail(L"Could not wait for the launched application.");
        MSG msg;
        while (PeekMessageW(&msg, nullptr, 0, 0, PM_REMOVE)) { TranslateMessage(&msg); DispatchMessageW(&msg); }
    }
    DWORD code = 1; GetExitCodeProcess(process.h, &code); return code;
}
static fs::path executable_for(const fs::path& disc, const std::wstring& expected) {
    auto candidate = disc / L"USRDIR" / L"EMAIN.ELF";
    if (fs::is_regular_file(candidate) && hash(candidate) == expected) return candidate;
    TASKDIALOG_BUTTON buttons[] = {{100,L"Select my decrypted EMAIN.ELF"}, {101,L"Create it using my installed RPCS3"}};
    TASKDIALOGCONFIG td{}; td.cbSize = sizeof td;
    td.dwFlags = (TASKDIALOG_FLAGS)(TDF_USE_COMMAND_LINKS | TDF_ALLOW_DIALOG_CANCELLATION);
    td.pszWindowTitle = L"Project Tourline Prologue - executable setup"; td.pszMainInstruction = L"One game file needs to be decrypted";
    td.pszContent = L"The download contains no game data or decryption keys. If your dump already has a decrypted EMAIN.ELF, select it. Otherwise select your installed RPCS3; it will decrypt a temporary copy of EMAIN.SELF. Your original dump is left unchanged.";
    td.cButtons = 2; td.pButtons = buttons; td.dwCommonButtons = TDCBF_CANCEL_BUTTON;
    brand(td);
    int choice = IDCANCEL;
    if (FAILED(TaskDialogIndirect(&td, &choice, nullptr, nullptr))) fail(L"Could not open the executable setup dialog.");
    if (choice == IDCANCEL) return {};
    if (choice == 100) return pick(false, L"Select decrypted EMAIN.ELF (BCUS98158 v03.00)");
    auto rpcs3 = pick(false, L"Select your installed RPCS3", L"RPCS3 executable", L"rpcs3.exe");
    if (rpcs3.empty()) return {};
    if (!fs::is_regular_file(disc/L"USRDIR"/L"EMAIN.SELF")) fail(L"The dump is missing USRDIR\\EMAIN.SELF.");
    // Each attempt has its own directory; never overwrite an earlier import.
    fs::path temp = data/L"imports"/(std::to_wstring(GetCurrentProcessId())+L"-"+std::to_wstring(GetTickCount64()));
    fs::create_directories(temp);
    fs::copy_file(disc/L"USRDIR"/L"EMAIN.SELF", temp/L"EMAIN.SELF");
    if (run(rpcs3, L"--decrypt " + quote(temp/L"EMAIN.SELF"), rpcs3.parent_path(), L"decrypt") != 0)
        fail(L"RPCS3 decryption failed. See logs\\decrypt.err in the GT5P user-data folder. You can also use RPCS3's Decrypt PS3 Binaries menu, then select the resulting ELF on the next setup attempt.");
    candidate = temp/L"EMAIN.elf";
    if (!fs::is_regular_file(candidate)) fail(L"RPCS3 did not produce EMAIN.elf. Use its Decrypt PS3 Binaries menu, then select the resulting ELF.");
    return candidate;
}
static std::wstring release_value(const wchar_t* key) {
    return profile(install/L"release.ini", L"release", key);
}
static bool setup(const std::wstring& expected) {
    auto chosen = pick(true, L"Select your GT5P dump folder (or its PS3_GAME folder)");
    if (chosen.empty()) return false;
    fs::path disc = game_folder(chosen), elf = data/L"input"/L"EMAIN.ELF";
    if (!fs::is_regular_file(elf) || hash(elf) != expected) {
        auto source = executable_for(disc, expected);
        if (source.empty()) return false;
        if (hash(source) != expected) fail(L"That executable does not match this GT5P release. Use a decrypted EMAIN.SELF from the supported BCUS98158 v03.00 dump.");
        fs::create_directories(elf.parent_path());
        fs::copy_file(source, elf.wstring()+L".tmp", fs::copy_options::overwrite_existing);
        if (!MoveFileExW((elf.wstring()+L".tmp").c_str(), elf.c_str(), MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH))
            fail(L"Could not save the verified game executable.");
    }
    // Commit a complete configuration atomically; cancel/failure leaves the old one.
    fs::path staged = data/L"setup.new.ini";
    { std::ofstream f(staged, std::ios::binary|std::ios::trunc); f.write("\xff\xfe", 2); }
    setting(staged, L"directory", disc);
    WritePrivateProfileStringW(nullptr, nullptr, nullptr, staged.c_str());
    if (!MoveFileExW(staged.c_str(), (data/L"setup.ini").c_str(), MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
        fail(L"Could not finish saving setup.");
    return true;
}
static void report(const std::wstring& message) {
    try {
        if (!data.empty() && fs::is_directory(data)) {
            fs::create_directories(data/L"logs");
            int n = WideCharToMultiByte(CP_UTF8, 0, message.c_str(), (int)message.size(), nullptr, 0, nullptr, nullptr);
            std::string text(n, '\0');
            WideCharToMultiByte(CP_UTF8, 0, message.c_str(), (int)message.size(), text.data(), n, nullptr, nullptr);
            std::ofstream out(data/L"logs"/L"setup.err"); out << text << '\n';
        }
    } catch (const std::exception&) {}
    fwprintf(stderr, L"%ls\n", message.c_str());
    if (!quiet && !silent_errors) MessageBoxW(nullptr, message.c_str(), L"GT5P setup", MB_OK|MB_ICONERROR);
}
static bool within(const fs::path& a, const fs::path& b) {
    auto x = a.lexically_normal().wstring(), y = b.lexically_normal().wstring();
    std::transform(x.begin(), x.end(), x.begin(), towlower);
    std::transform(y.begin(), y.end(), y.begin(), towlower);
    if (x == y) return true;
    if (!y.empty() && y.back() != L'\\') y += L'\\';
    return x.compare(0, y.size(), y) == 0;
}
// Copy before switching the locator. Keep the old profile as a recovery copy.
static void relocate(const fs::path& chosen, const fs::path& home) {
    fs::path destination = fs::weakly_canonical(fs::absolute(chosen));
    auto source = fs::weakly_canonical(data);
    runtime_path(destination);
    if (within(destination, source) && within(source, destination)) return;
    if (within(destination, source) || within(source, destination) ||
        within(install, destination) || within(home, destination))
        fail(L"Choose a separate storage folder, outside the current data folder and containing neither the launcher nor its configuration folder.");
    if (fs::exists(destination) && (!fs::is_directory(destination) || !fs::is_empty(destination)))
        fail(L"Choose an empty folder for GT5P storage. Existing files will not be overwritten.");
    // Check the entire source before copying; do not follow directory links.
    for (const auto& entry : fs::recursive_directory_iterator(source))
        if (GetFileAttributesW(entry.path().c_str()) & FILE_ATTRIBUTE_REPARSE_POINT)
            fail(L"The existing storage contains a linked file or folder. Relocation stopped; the original storage is unchanged.");
    fs::create_directories(destination);
    Handle lock(CreateFileW((destination/L"launcher.lock").c_str(), GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS, 0, nullptr));
    if (lock.h == INVALID_HANDLE_VALUE) fail(L"The selected storage folder is not writable or is in use.");
    for (const auto& entry : fs::recursive_directory_iterator(source)) {
        auto relative = entry.path().lexically_relative(source);
        if (relative == L"launcher.lock" || relative == L"storage.lock" ||
            relative == L"storage.ini" || relative == L"storage.new.ini") continue;
        auto target = destination/relative;
        if (entry.is_directory()) fs::create_directories(target);
        else if (entry.is_regular_file()) {
            fs::copy_file(entry.path(), target);
            if (hash(entry.path()) != hash(target)) fail(L"Storage copy verification failed. The original storage remains selected.");
        } else fail(L"Unsupported file in storage. The original storage remains selected.");
    }
    auto staged = home/L"storage.new.ini";
    { std::ofstream f(staged, std::ios::binary|std::ios::trunc); f.write("\xff\xfe", 2); }
    setting(staged, L"directory", destination);
    WritePrivateProfileStringW(nullptr, nullptr, nullptr, staged.c_str());
    if (!MoveFileExW(staged.c_str(), (home/L"storage.ini").c_str(), MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH))
        fail(L"Could not remember the storage folder. The original storage remains selected.");
    data = destination;
}
static fs::path storage_picker() {
    TASKDIALOG_BUTTON buttons[] = {{100,L"Keep the current storage folder"}, {101,L"Choose a folder (including an external SSD)"}};
    TASKDIALOGCONFIG td{}; td.cbSize = sizeof td;
    td.dwFlags = (TASKDIALOG_FLAGS)(TDF_USE_COMMAND_LINKS | TDF_ALLOW_DIALOG_CANCELLATION);
    td.pszWindowTitle = L"Project Tourline Prologue - storage location";
    td.pszMainInstruction = L"Where should Project Tourline Prologue store its files?";
    std::wstring content = L"Saves, settings, shader cache and the verified executable will be stored here:\n\n" + data.wstring() +
        L"\n\nYour game dump stays where it is. The launcher stays where you extracted it; you can put that entire folder on your SSD too. Changing storage copies existing data and keeps the original as a backup.";
    td.pszContent = content.c_str(); td.cButtons = 2; td.pButtons = buttons;
    td.dwCommonButtons = TDCBF_CANCEL_BUTTON;
    brand(td);
    int choice = IDCANCEL;
    if (FAILED(TaskDialogIndirect(&td, &choice, nullptr, nullptr))) fail(L"Could not open storage setup.");
    if (choice == IDCANCEL) return {};
    if (choice == 100) return data;
    return pick(true, L"Choose an empty folder for Project Tourline Prologue saves, settings and cache");
}
static void offer_cache_cleanup(const fs::path& disc) {
    if (env(L"GT5P_PREPARE_CLEANUP")==L"0" || !fs::is_regular_file(data/L"prepare-cleanup-pending.txt")) return;
    auto helper=install/L"preparation"/L"GT5P-Prepare.exe";
    if (!fs::is_regular_file(helper) || hash(helper)!=release_value(L"prepare_sha256")) return;
    // No progress dialog: this helper only scans and offers cleanup. Failure must
    // never turn a successful preparation into a failed launch.
    try {
        DWORD result=run(helper,L"--offer-cache-cleanup --install "+quote(install)+L" --storage "+quote(data)+
            L" --game "+quote(disc)+L" --launcher-pid "+std::to_wstring(GetCurrentProcessId()),data,L"prepare-cleanup");
        if (result) MessageBoxW(nullptr,L"Older cache cleanup could not finish. Your selected preparation is kept. "
            L"Normal play is still available; details are in the prepare-cleanup log in your storage folder.",
            L"Tourline Prologue",MB_OK|MB_ICONINFORMATION);
    }
    catch (...) {}
}
static DWORD prepare_cache(const fs::path& disc, const fs::path& prepare_assets, bool continue_to_game, bool notices=true, bool full=false) {
    auto helper=install/L"preparation"/L"GT5P-Prepare.exe";
    if (!fs::is_regular_file(helper) || hash(helper)!=release_value(L"prepare_sha256"))
        fail(L"The preparation helper is missing or does not match this release. Re-extract the full ZIP.");
    bool packed=prepare_assets.empty() && env(L"GT5P_PREPARE_VOLUME")!=L"0";
    if (notices && prepare_assets.empty() && !continue_to_game) MessageBoxW(nullptr,packed?
        L"Experimental preparation covers known menu/HSR/Daytona pipelines, not the whole game.\n\nPreparation reads your already selected game files in place. No separate GT.VOL extraction is needed. It may take several minutes and stores local shader/driver files. No consistent stutter reduction is established. You can cancel and resume, or launch normally without preparation.":
        L"Legacy preparation: choose your already unpacked GT.VOL asset folder. Preparation remains partial and optional.",L"Project Tourline Prologue - optional preparation",MB_OK|MB_ICONINFORMATION);
    auto assets=packed?fs::path{}:prepare_assets.empty()?pick(true,L"Choose your unpacked GT.VOL asset folder"):prepare_assets;
    if (!packed && assets.empty()) return 2;
    fs::remove(data/L"prepare.cancel");
    std::ofstream(data/L"prepare-status.txt") << "Starting preparation...";
    auto source=packed?L" --game "+quote(disc):L" --assets "+quote(assets);
    DWORD result=run(helper,L"--install "+quote(install)+L" --storage "+quote(data)+source+
        (full?L" --full":L"")+L" --launcher-pid "+std::to_wstring(GetCurrentProcessId()),data,L"prepare",true);
    if (result && result!=2) fail(L"Preparation did not finish. Normal play is still available. Logs are in:\n\n"+(data/L"logs").wstring());
    if (!result) offer_cache_cleanup(disc);
    if (notices && !result && prepare_assets.empty() && !continue_to_game) MessageBoxW(nullptr,
        !full && env(L"GT5P_PREPARE_QUICK")!=L"0" ?
        L"Common menu and race pipelines are ready for your settings. Launch tourline-prologue.exe to play. Broader preparation can continue in the background. Other shaders compile as needed.":
        L"Known pipelines prepared. Launch tourline-prologue.exe to play. Uncovered pipelines and different settings use normal demand compilation.",L"Project Tourline Prologue",MB_OK|MB_ICONINFORMATION);
    return result;
}
// One-time offer per port version. A small marker in the launcher's storage records that it was
// answered (yes, no or closed), so it is never shown again for that version.
static bool plain_version(const std::wstring& v) {
    if (v.empty() || v.size() > 16) return false;
    for (wchar_t c : v) if (!((c >= L'0' && c <= L'9') || c == L'.')) return false;
    return true;
}
static fs::path offer_marker(const std::wstring& version) { return data/(L"prepare-offer-"+version+L".done"); }
static void mark_offer(const std::wstring& version) {
    try { std::ofstream(offer_marker(version)) << "answered\n"; } catch (...) {}
}
// 0: a completed preparation of the current identity is selected. 3: it is not. -1: unknown
// (helper missing or failed); the launcher then offers nothing and records nothing.
static int selected_preparation(const fs::path& disc, bool full=false) {
    try {
        auto helper=install/L"preparation"/L"GT5P-Prepare.exe";
        if (!fs::is_regular_file(helper) || hash(helper)!=release_value(L"prepare_sha256")) return -1;
        DWORD code=run(helper,(full?L"--check-full-selected --install ":L"--check-selected --install ")+quote(install)+L" --storage "+quote(data)+L" --game "+quote(disc),
            data,L"prepare-check");
        return code==0 || code==3 ? (int)code : -1;
    } catch (const Failure&) { return -1; } catch (const std::exception&) { return -1; }
}
// Phase 225: background preparation beside the game. Started (idle priority, own kill-on-close job) when no
// completed preparation of this release is selected; it prepares the race pipelines first and copies them into
// the cache the game is using, then runs the full preparation, which the next launch selects. Stopped with the
// game: prepare.cancel at a checkpoint (work kept for resume), then the job closes. GT5P_PREPARE_BACKGROUND=0
// restores the one-time offer instead.
// While a race runs the helper is paused: the game arms GT5P_RACE_EVENT at loading and sets it at grid Start
// until a menu loads. The watcher suspends every process in the helper's job meanwhile (resumed in menus).
// The indicator observes the same event even with the pause rollback off. A helper compiling during racing added
// 3-4 s of hitching to the first race. GT5P_PREPARE_BACKGROUND_PAUSE=0 never pauses.
struct Background {
    HANDLE process=nullptr, job=nullptr, race=nullptr, stop=nullptr, watcher=nullptr;
    bool indicator=false, pause=true;
    volatile LONG pauses=0; volatile LONG64 paused_ms=0;
};
static bool background_enabled() { return env(L"GT5P_PREPARE_BACKGROUND")!=L"0"; }
static DWORD WINAPI background_watch(LPVOID arg) {
    auto& b=*static_cast<Background*>(arg);
    using NtProcess=LONG (NTAPI*)(HANDLE);
    HMODULE ntdll=GetModuleHandleW(L"ntdll.dll");
    auto suspend=ntdll ? reinterpret_cast<NtProcess>(GetProcAddress(ntdll,"NtSuspendProcess")) : nullptr;
    auto resume=ntdll ? reinterpret_cast<NtProcess>(GetProcAddress(ntdll,"NtResumeProcess")) : nullptr;
    const bool can_pause=b.pause && suspend && resume;
    background_preparation_ui::Overlay overlay;
    auto previous=background_preparation_ui::View::Hidden;
    std::vector<HANDLE> held;   // processes this watcher suspended, resumed exactly once
    ULONGLONG since=0;
    auto release=[&] {
        for (HANDLE h : held) { resume(h); CloseHandle(h); }
        held.clear();
        if (since) { InterlockedAdd64(&b.paused_ms,(LONG64)(GetTickCount64()-since)); since=0; }
    };
    while (WaitForSingleObject(b.stop,250)!=WAIT_OBJECT_0) {
        MSG message;
        while (PeekMessageW(&message,nullptr,0,0,PM_REMOVE)) {TranslateMessage(&message);DispatchMessageW(&message);}
        const bool racing=b.race && WaitForSingleObject(b.race,0)==WAIT_OBJECT_0;
        const bool finished=WaitForSingleObject(b.process,0)==WAIT_OBJECT_0;
        if (!can_pause || !racing || finished) release();
        else {
            // Every process in the job, including ones started since the last pass.
            struct { JOBOBJECT_BASIC_PROCESS_ID_LIST list; ULONG_PTR more[511]; } ids{};
            if (QueryInformationJobObject(b.job,JobObjectBasicProcessIdList,&ids,sizeof ids,nullptr))
            for (DWORD i=0;i<ids.list.NumberOfProcessIdsInList;++i) {
                const DWORD pid=(DWORD)ids.list.ProcessIdList[i];
                if (std::any_of(held.begin(),held.end(),[&](HANDLE h){ return GetProcessId(h)==pid; })) continue;
                HANDLE h=OpenProcess(PROCESS_SUSPEND_RESUME|PROCESS_QUERY_LIMITED_INFORMATION,FALSE,pid);
                if (h && suspend(h)>=0) held.push_back(h);
                else if (h) CloseHandle(h);
            }
            if (!held.empty() && !since) {since=GetTickCount64();InterlockedIncrement(&b.pauses);}
        }
        if (b.indicator) {
            DWORD code=1;if (finished) GetExitCodeProcess(b.process,&code);
            using namespace background_preparation_ui;
            const Work work=finished?(code==0?Work::Complete:Work::Incomplete):!held.empty()?Work::Paused:Work::Preparing;
            overlay.tick(static_cast<DWORD>(background_game_pid),work,racing,GetTickCount64());
            if (overlay.view()!=previous) {
                previous=overlay.view();
                try {std::ofstream(data/L"logs"/L"prepare-background-status.txt",std::ios::app)<<name(previous)<<"\n";} catch (...) {}
            }
        }
    }
    release();
    return 0;
}
static void watch_background(Background& b) {
    if (!b.process || (!b.race && !b.indicator)) return;
    b.stop=CreateEventW(nullptr,TRUE,FALSE,nullptr);
    if (b.stop) b.watcher=CreateThread(nullptr,0,background_watch,&b,0,nullptr);
}
static Background start_background(const fs::path& disc, const fs::path& live) {
    Background b;
    try {
        auto helper=install/L"preparation"/L"GT5P-Prepare.exe";
        if (!fs::is_regular_file(helper) || hash(helper)!=release_value(L"prepare_sha256")) return b;
        fs::create_directories(data/L"logs");
        fs::remove(data/L"prepare.cancel");
        SECURITY_ATTRIBUTES sa{sizeof sa, nullptr, TRUE};
        Handle out(CreateFileW((data/L"logs"/L"prepare-background.out").c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa,
            CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr));
        Handle err(CreateFileW((data/L"logs"/L"prepare-background.err").c_str(), GENERIC_WRITE, FILE_SHARE_READ, &sa,
            CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr));
        Handle input(CreateFileW(L"NUL", GENERIC_READ, FILE_SHARE_READ|FILE_SHARE_WRITE, &sa, OPEN_EXISTING, 0, nullptr));
        if (out.h==INVALID_HANDLE_VALUE || err.h==INVALID_HANDLE_VALUE || input.h==INVALID_HANDLE_VALUE) return b;
        STARTUPINFOW si{}; si.cb=sizeof si; si.dwFlags=STARTF_USESTDHANDLES;
        si.hStdInput=input.h; si.hStdOutput=out.h; si.hStdError=err.h;
        HANDLE job=CreateJobObjectW(nullptr, nullptr);
        JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits{};
        limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
        if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation, &limits, sizeof limits)) {
            if (job) CloseHandle(job);
            return b;
        }
        std::wstring command=quote(helper)+L" --install "+quote(install)+L" --storage "+quote(data)+L" --game "+quote(disc)+
            L" --launcher-pid "+std::to_wstring(GetCurrentProcessId())+L" --background --live-cache "+quote(live);
        PROCESS_INFORMATION pi{};
        // Idle priority is inherited by the helper's compiler and offline processes.
        if (!CreateProcessW(helper.c_str(), command.data(), nullptr, nullptr, TRUE,
                CREATE_NO_WINDOW|CREATE_SUSPENDED|IDLE_PRIORITY_CLASS, nullptr, data.c_str(), &si, &pi)) {
            CloseHandle(job);
            return b;
        }
        if (!AssignProcessToJobObject(job, pi.hProcess) || ResumeThread(pi.hThread)==(DWORD)-1) {
            TerminateProcess(pi.hProcess, 1);  // only the suspended child created above
            CloseHandle(pi.hThread); CloseHandle(pi.hProcess); CloseHandle(job);
            return b;
        }
        CloseHandle(pi.hThread);
        b.process=pi.hProcess; b.job=job;
        b.indicator=env(L"GT5P_PREPARE_BACKGROUND_INDICATOR")!=L"0";
        if (b.indicator) std::ofstream(data/L"logs"/L"prepare-background-status.txt",std::ios::trunc);
        b.pause=env(L"GT5P_PREPARE_BACKGROUND_PAUSE")!=L"0";
        if (b.pause || b.indicator) {
            // The game opens it by name; created before the game starts.
            const std::wstring name=L"Local\\TourlinePrologue-Race-"+std::to_wstring(GetCurrentProcessId());
            b.race=CreateEventW(nullptr,TRUE,FALSE,name.c_str());
            if (b.race) setenv(L"GT5P_RACE_EVENT",name);
        }
    } catch (...) {}
    return b;
}
// Cancel at the helper's next checkpoint (it keeps completed work), then close its job.
static void stop_background(Background& b) {
    if (!b.process) return;
    if (b.watcher) {   // resumes anything paused, so the helper can see the cancel request
        SetEvent(b.stop); WaitForSingleObject(b.watcher,INFINITE); CloseHandle(b.watcher); b.watcher=nullptr;
    }
    if (WaitForSingleObject(b.process, 0)!=WAIT_OBJECT_0) {
        try { std::ofstream(data/L"prepare.cancel") << "cancel\n"; } catch (...) {}
        WaitForSingleObject(b.process, 30000);
    }
    try {
        std::ofstream(data/L"logs"/L"prepare-background-pause.txt") << "pauses=" << b.pauses << "\npaused_ms=" << b.paused_ms << "\n";
    } catch (...) {}
    CloseHandle(b.process); CloseHandle(b.job);   // the job kills anything still running
    for (HANDLE* h : {&b.race,&b.stop}) if (*h) { CloseHandle(*h); *h=nullptr; }
    b.process=b.job=nullptr;
    try { fs::remove(data/L"prepare.cancel"); } catch (...) {}
}
// Whether this release's completed preparation is selected. The helper's check costs a few seconds, so a
// positive answer is remembered beside the selection it was given for.
static bool preparation_current(const fs::path& disc) {
    const std::wstring version=release_value(L"port_version");
    const auto pointer=utf8_file(data/L"prepared-cache.txt");
    const fs::path done=data/(L"prepare-full-current-"+version+L".txt");
    const auto settings=data/L"gt5p_settings.toml";
    std::wstring settings_hash;
    try { if (fs::is_regular_file(settings)) settings_hash=hash(settings); }
    catch (...) { return selected_preparation(disc,true)!=3; } // An optional memo must never prevent play.
    const auto identity=pointer+L"\n"+settings_hash+L"\n"+env(L"RSX_SHADER_COMPILER")+L"\n"+
        env(L"RSX_SHADER_INTERP")+L"\n"+env(L"RSX_SHADER_INTERP_VP")+L"\nfull-v1";
    if (plain_version(version) && !pointer.empty() && utf8_file(done)==identity) return true;
    int state=selected_preparation(disc,true);
    if (state==0 && plain_version(version) && !pointer.empty()) {
        try { std::ofstream f(done, std::ios::binary); auto n=WideCharToMultiByte(CP_UTF8,0,identity.c_str(),(int)identity.size(),nullptr,0,nullptr,nullptr);
              std::string t(n,'\0'); WideCharToMultiByte(CP_UTF8,0,identity.c_str(),(int)identity.size(),t.data(),n,nullptr,nullptr); f<<t; } catch (...) {}
    }
    return state!=3;   // unknown (-1) starts nothing
}
// The same offer, preparation and failure handling for both launches.
static void offer_preparation(const fs::path& disc, first_run_preparation::Kind kind, const std::wstring& version) {
    DWORD cpus = GetActiveProcessorCount(ALL_PROCESSOR_GROUPS);
    bool quick=env(L"GT5P_PREPARE_QUICK")!=L"0";
    bool yes = first_run_preparation::offer(brand_icon(), kind,
        quick?L"a few minutes":first_run_preparation::estimate(cpus),quick);
    if (plain_version(version)) mark_offer(version);
    if (!yes) return;
    try { prepare_cache(disc,{},true); }
    catch (const Failure& e) { report(e.message+L"\n\nThe game will now start. You can run Prepare shaders.cmd later."); }
    catch (const std::exception&) { report(L"Optional preparation could not finish. The game will now start. You can run Prepare shaders.cmd later."); }
}
int WINAPI wWinMain(HINSTANCE, HINSTANCE, PWSTR, int) {
    HRESULT com = CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    try {
        int argc = 0; auto argv = CommandLineToArgvW(GetCommandLineW(), &argc);
        if (!argv) fail(L"Could not read launcher options.");
        bool force = false, open = false, unknown = false, choose_storage = false, prepare = false, full_prepare=false, no_prepared = false;
        fs::path storage, prepare_assets;
        for (int i = 1; i < argc; ++i) {
            if (!wcscmp(argv[i], L"--setup")) force = true;
            else if (!wcscmp(argv[i], L"--check")) quiet = true;
            else if (!wcscmp(argv[i], L"--open-data")) open = true;
            else if (!wcscmp(argv[i], L"--choose-storage")) choose_storage = true;
            else if (!wcscmp(argv[i], L"--prepare")) prepare = true;
            else if (!wcscmp(argv[i], L"--prepare-full")) { prepare=true;full_prepare=true; }
            else if (!wcscmp(argv[i], L"--no-prepared")) no_prepared = true;
            else if (!wcscmp(argv[i], L"--prepare-assets") && i+1<argc) { prepare=true;prepare_assets=argv[++i]; }
            else if (!wcscmp(argv[i], L"--set-storage") && i+1 < argc) storage = argv[++i];
            else unknown = true;
        }
        LocalFree(argv);
        silent_errors = !storage.empty() || !prepare_assets.empty();
        if (unknown || (quiet && (choose_storage || !storage.empty() || open || prepare)) || (prepare && (choose_storage || !storage.empty() || open)))
            fail(L"Supported options: --setup, --check, --prepare, --prepare-assets <folder>, --no-prepared, --open-data, --choose-storage, --set-storage <empty folder>. Preparation/storage changes cannot be combined with --check.");
        if (FAILED(com)) fail(L"Windows COM initialization failed.");
        std::array<wchar_t, 32768> module{};
        DWORD n = GetModuleFileNameW(nullptr, module.data(), (DWORD)module.size());
        if (!n || n >= module.size()) fail(L"Could not locate the launcher.");
        install = fs::path(module.data()).parent_path();
        PWSTR local = nullptr;
        if (FAILED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &local))) fail(L"Could not locate Local AppData.");
        auto home = env(L"GT5P_LAUNCHER_HOME").empty() ? fs::path(local)/L"GT5PRecomp" : fs::absolute(env(L"GT5P_LAUNCHER_HOME"));
        CoTaskMemFree(local);
        bool override_data = !env(L"GT5P_USER_DIR").empty();
        data = override_data ? fs::absolute(env(L"GT5P_USER_DIR")) : home;
        bool relocated = false;
        runtime_path(home);
        if (override_data && (choose_storage || !storage.empty())) fail(L"Unset GT5P_USER_DIR before changing the remembered storage location.");
        if (!override_data) {
            auto saved = profile(home/L"storage.ini", L"game", L"directory");
            if (!saved.empty()) {
                data = saved; relocated = true;
                if (!fs::is_directory(data)) {
                    data = home;
                    fail(L"Your selected Project Tourline Prologue storage is unavailable:\n\n" + saved + L"\n\nReconnect the drive and try again. Your saved selection has been kept.");
                }
            }
        }
        runtime_path(data); runtime_path(install);
        fs::create_directories(data);
        if (open) {
            if ((INT_PTR)ShellExecuteW(nullptr, L"open", data.c_str(), nullptr, nullptr, SW_SHOWNORMAL) <= 32)
                fail(L"Explorer could not open the user-data directory.");
            CoUninitialize(); return 0;
        }
        // Serialize locator changes and launches even while data lives elsewhere.
        if (!override_data) fs::create_directories(home);
        Handle home_lock(override_data ? INVALID_HANDLE_VALUE : CreateFileW((home/L"storage.lock").c_str(), GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS, 0, nullptr));
        if (!override_data && home_lock.h == INVALID_HANDLE_VALUE) fail(L"Project Tourline Prologue is already running or storage setup is in use.");
        // Also repairs a link from before this version or after storage.ini was removed.
        if (!override_data) link_storage(home, relocated ? data : fs::path{});
        Handle lock(CreateFileW((data/L"launcher.lock").c_str(), GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS, 0, nullptr));
        if (lock.h == INVALID_HANDLE_VALUE) fail(L"Project Tourline Prologue is already running or this user-data folder is not writable.");
        auto expected = release_value(L"elf_sha256");
        if (release_value(L"schema") != L"1" || release_value(L"target") != L"BCUS98158" ||
            release_value(L"version") != L"03.00" || expected.size() != 64)
            fail(L"Missing or incompatible release.ini. Re-extract the full release ZIP.");
        auto game = install/L"runtime"/L"gt5p.exe";
        if (!fs::is_regular_file(game) || hash(game) != release_value(L"game_sha256")) fail(L"The game executable does not match release.ini. Re-extract the complete ZIP.");
        bool first_storage = !override_data && !fs::exists(data/L"setup.ini") &&
            env(L"GT5P_STORAGE_PICKER") != L"0" && env(L"GT5P_LAUNCHER_SETUP") != L"0" && !quiet && !open;
        if (!override_data && (choose_storage || !storage.empty() || first_storage || (force && !quiet && env(L"GT5P_STORAGE_PICKER") != L"0"))) {
            auto selected = storage.empty() ? storage_picker() : storage;
            if (selected.empty()) { CoUninitialize(); return 0; }
            auto previous = data;
            relocate(selected, home);
            if (data != previous) {
                link_storage(home, data);
                CloseHandle(lock.h);
                lock.h = CreateFileW((data/L"launcher.lock").c_str(), GENERIC_WRITE, 0, nullptr, OPEN_ALWAYS, 0, nullptr);
                if (lock.h == INVALID_HANDLE_VALUE) fail(L"The selected storage folder is in use or not writable.");
            }
            if (choose_storage || !storage.empty()) { CoUninitialize(); return 0; }
        }
        bool valid = false;
        auto disc = fs::path(profile(data/L"setup.ini", L"game", L"directory"));
        if (!force && !disc.empty()) {
            try { disc = game_folder(disc); valid = hash(data/L"input"/L"EMAIN.ELF") == expected; }
            catch (const Failure&) {} catch (const fs::filesystem_error&) {}
        }
        bool completed_setup=false;
        if (!valid) {
            if (quiet || env(L"GT5P_LAUNCHER_SETUP") == L"0") fail(L"Setup is missing or no longer valid. Run tourline-prologue.exe --setup.");
            if (!setup(expected)) { CoUninitialize(); return 0; }
            disc = game_folder(profile(data/L"setup.ini", L"game", L"directory"));
            completed_setup=true;
        }
        if (quiet) { CoUninitialize(); return 0; }
        if (prepare) {
            prepare_cache(disc,prepare_assets,false,true,full_prepare);
            CoUninitialize();return 0;
        }
        // One DXC migration offer, including when background preparation is enabled.
        // A current preparation suppresses it. Interpreter/FXC users keep their existing flow.
        bool dxc_offered=false;
        auto interpreter_on=[](const std::wstring& v) { return !v.empty() && (v[0]==L'1' || v[0]==L'f' || v[0]==L'F'); };
        const auto compiler=env(L"RSX_SHADER_COMPILER");
        const auto dxc_marker=data/L"prepare-offer-dxc-v1.done";
        if (completed_setup) std::ofstream(dxc_marker) << "new-install\n";
        if (!completed_setup && !no_prepared && env(L"GT5P_PREPARE_VOLUME")!=L"0" &&
            env(L"GT5P_PREPARE_OFFER")!=L"0" && env(L"GT5P_PREPARE_DXC_OFFER")!=L"0" &&
            (compiler.empty() || compiler==L"dxc") &&
            !interpreter_on(env(L"RSX_SHADER_INTERP")) && !interpreter_on(env(L"RSX_SHADER_INTERP_VP")) &&
            !fs::exists(dxc_marker)) {
            int state=selected_preparation(disc);
            if (state==0 || state==3) {
                if (state==3) {
                    offer_preparation(disc,first_run_preparation::Kind::DxcUpdate,release_value(L"port_version"));
                    dxc_offered=true;
                }
                else {
                    const auto version=release_value(L"port_version");
                    if (plain_version(version)) mark_offer(version);
                }
                std::ofstream(dxc_marker) << "answered\n";
            }
        }
        offer_cache_cleanup(disc); // a completed background preparation from the previous launch
        // Phase 225: aside from the DXC migration notice above, background preparation starts beside
        // the game below. At most one offer per launch otherwise. GT5P_PREPARE_OFFER=0 disables both.
        bool background=false;
        if (background_enabled() && !no_prepared && env(L"GT5P_PREPARE_VOLUME")!=L"0" && env(L"GT5P_PREPARE_OFFER")!=L"0")
            background=!preparation_current(disc);
        else if (!dxc_offered && env(L"GT5P_PREPARE_OFFER")!=L"0") {
            const std::wstring version=release_value(L"port_version");
            if (completed_setup) {
                offer_preparation(disc,first_run_preparation::Kind::AfterSetup,version);
                std::ofstream(dxc_marker) << "answered\n";
            }
            else if (!no_prepared && env(L"GT5P_PREPARE_VOLUME")!=L"0" && plain_version(version) &&
                     !fs::exists(offer_marker(version))) {
                // First launch of this version: offer unless a completed preparation of the
                // current identity is already selected (shaders of earlier versions do not count).
                int state=selected_preparation(disc);
                if (state==0) mark_offer(version);
                else if (state==3) offer_preparation(disc,first_run_preparation::Kind::Update,version);
            }
        }
        // Keep all mutable state outside the ZIP/install directory. Assets are
        // small, distributable glyph art; this never copies the game dump.
        if (!fs::is_directory(install/L"assets")) fail(L"The release assets folder is missing.");
        fs::copy(install/L"assets", data/L"assets", fs::copy_options::recursive|fs::copy_options::overwrite_existing);
        fs::create_directories(data/L"gamedata"/L"dev_hdd0");
        auto settings = data/L"gt5p_settings.toml";
        if (!fs::exists(settings)) {
            std::ofstream f(settings);
            // Keep in step with config.new in recomplauncher.json, which writes this preset
            // when RecompLauncher starts the game before this launcher has run.
            f << "# First-run preset. Change this in the game's F1 settings.\n[video]\nresolution = \"720p\"\naspect = \"16:9\"\nmsaa = 2\nshader_precompile = true\npipeline_async = true\n\n[meta]\ndefaults_version = 1\n";
            if (!f) fail(L"Could not write initial video settings.");
        }
        setenv(L"PS3_TITLE", L"Project Tourline Prologue");
        setenv(L"GT5P_ROOT", data.wstring());
        setenv(L"PS3_VFS_ROOT", data.wstring());
        setenv(L"PS3_GAMEDATA_ROOT", (data/L"gamedata").wstring());
        setenv(L"GT5P_SETTINGS", settings.wstring());
        setenv(L"GT5P_GAME_DIR", disc.wstring()+L"/");
        auto prepared=utf8_file(data/L"prepared-cache.txt");
        if (no_prepared) setenv(L"RSX_SHADER_CACHE",(data/L"shadercache").wstring());
        else if (!prepared.empty()) {
            auto cache=fs::weakly_canonical(data/fs::path(prepared));
            if (!within(cache,fs::weakly_canonical(data/L"preparation")) || !fs::is_directory(cache))
                fail(L"The prepared cache selection is invalid. Remove prepared-cache.txt to use the ordinary cache; keep the cache directories.");
            setenv(L"RSX_SHADER_CACHE",cache.wstring());
        }
        if (env(L"PS3_VERBOSE").empty()) setenv(L"PS3_VERBOSE", L"0");
        auto restart=env(L"GT5P_LAUNCHER_RESTART");
        if (!restart.empty() && restart!=L"0" && restart!=L"1") fail(L"GT5P_LAUNCHER_RESTART must be 0 or 1.");
        if (restart.empty()) setenv(L"GT5P_LAUNCHER_RESTART",L"1");
        auto tools = install/L"preparation"/L"GT5P-Prepare.exe";
        const bool pipeline_tools = env(L"GT5P_PIPELINE_TOOLS")!=L"0" &&
            fs::is_regular_file(tools) && hash(tools)==release_value(L"prepare_sha256");
        setenv(L"GT5P_PIPELINE_TOOLS", pipeline_tools ? L"1" : L"0");
        Background helper;
        if (background) {
            // The cache this game run uses: the old selection, or the ordinary cache.
            fs::path live = prepared.empty() ? data/L"shadercache" : fs::weakly_canonical(data/fs::path(prepared));
            fs::create_directories(live);
            helper=start_background(disc, live);
            watch_background(helper);
        }
        struct StopHelper { Background& b; ~StopHelper() { stop_background(b); } } stop_helper{helper};
        for (;;) {
            DWORD code = run(game, quote(data/L"input"/L"EMAIN.ELF"), data, L"play");
            // Settings restarts keep the background helper; anything else stops it first.
            if (!(code==tourline_restart::exit_code && tourline_restart::managed())) stop_background(helper);
            // run() has waited for the old process and closed its private job
            // before another instance starts. Keep both storage locks throughout.
            if (code==tourline_restart::exit_code && tourline_restart::managed()) continue;
            if (tourline_restart::pipeline_action(code) && tourline_restart::managed() && pipeline_tools &&
                    env(L"RSX_PSO_PROVENANCE").empty()) {
                if (hash(tools)!=release_value(L"prepare_sha256")) fail(L"The preparation helper changed. Re-extract the complete package.");
                if (code==static_cast<DWORD>(tourline_restart::Action::Prepare)) {
                    // Offline preparation already runs under these leases.
                    prepare_cache(disc,{},false,false);
                    break;
                }
                // The old game's job is retired. Release only our leases before
                // the collector's normal launcher or verifier acquires them.
                // Keep owning the helper's job until every child has exited.
                CloseHandle(lock.h); lock.h=INVALID_HANDLE_VALUE;
                if (home_lock.h!=INVALID_HANDLE_VALUE) { CloseHandle(home_lock.h); home_lock.h=INVALID_HANDLE_VALUE; }
                setenv(L"GT5P_USER_DIR",data.wstring());
                auto mode = code==static_cast<DWORD>(tourline_restart::Action::Collect) ?
                    L"--collect-contribution" : L"--verify-contribution";
                DWORD result=run(tools,std::wstring(mode)+L" --install "+quote(install)+L" --storage "+quote(data),
                    install,L"pipeline-tools");
                if (result!=0 && result!=2)
                    fail(L"Pipeline collection or verification could not finish. Your recorded work is kept. See logs\\pipeline-tools.err, then try the collection or Resume command again.");
                break;
            }
            if (code) fail(L"The game exited with code " + std::to_wstring(code) + L". Logs are in:\n\n" + (data/L"logs").wstring());
            break;
        }
        CoUninitialize(); return 0;
    } catch (const Failure& e) {
        report(e.message);
    } catch (const std::exception&) {
        report(L"A file operation failed. Check free space and folder access, then run tourline-prologue.exe --setup again.");
    }
    if (SUCCEEDED(com)) CoUninitialize();
    return 1;
}
