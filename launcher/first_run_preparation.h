#pragma once
#include <windows.h>
#include <commctrl.h>
#include <string>

namespace first_run_preparation {

// Which launch asks: right after setup completes, or the first launch of an
// updated version whose earlier preparation is no longer used.
enum class Kind { AfterSetup, Update, DxcUpdate };

// The broad time window, from the measured full preparation (docs/release-v0.2.4.md).
// The helper runs four compiler workers on 8 or more logical processors and two
// otherwise, so the window follows that and says it depends on the PC.
inline std::wstring estimate(DWORD logical_processors) {
    return logical_processors >= 8
        ? L"about 10 to 20 minutes on a PC with 8 or more logical processors"
        : L"about 20 to 40 minutes on a PC with fewer than 8 logical processors";
}

inline bool offer(HICON icon, Kind kind, const std::wstring& window) {
    TASKDIALOG_BUTTON buttons[] = {{100, L"Prepare now"}, {101, L"Skip and play"}};
    TASKDIALOGCONFIG td{};
    td.cbSize = sizeof td;
    td.dwFlags = static_cast<TASKDIALOG_FLAGS>(TDF_USE_COMMAND_LINKS | TDF_ALLOW_DIALOG_CANCELLATION);
    td.pszWindowTitle = L"Tourline Prologue";
    std::wstring content;
    if (kind == Kind::DxcUpdate) {
        td.pszMainInstruction = L"Prepare shaders for the updated shader compiler?";
        content = L"This version uses DXC to build shaders. Shaders prepared with the previous FXC compiler cannot be used by DXC. "
                  L"Your older caches are kept for rollback. After preparation succeeds, you can choose to remove them to free space.\n\n"
                  L"Preparing now can reduce compilation stutter. You can skip and play; shaders will compile as needed.\n\n";
    } else if (kind == Kind::Update) {
        td.pszMainInstruction = L"Prepare shaders for this version?";
        content = L"This update changed how shaders are built, so shaders prepared by an earlier version are no longer used. "
                  L"The game works without preparing, but compiling shaders while you play can cause stutter.\n\n";
    } else {
        td.pszMainInstruction = L"Prepare known shaders before playing?";
        content = L"Setup is complete. Preparing shaders now is optional and can reduce stutter while you play.\n\n";
    }
    content += L"Preparation builds the game's known shaders and pipelines from your selected game files. "
               L"Expect " + window + L"; it depends on your PC. You can cancel and start playing, then run "
               L"Prepare shaders.cmd (or F1 > Debug > Prepare shaders) at any time to resume.\n\n"
               L"You will only be asked once for this version.";
    td.pszContent = content.c_str();
    td.cButtons = 2;
    td.pButtons = buttons;
    td.nDefaultButton = 101;
    if (icon) {
        td.dwFlags |= TDF_USE_HICON_MAIN;
        td.hMainIcon = icon;
    }
    int selected = IDCANCEL;
    return SUCCEEDED(TaskDialogIndirect(&td, &selected, nullptr, nullptr)) && selected == 100;
}
}
