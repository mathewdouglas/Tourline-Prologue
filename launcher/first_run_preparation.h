#pragma once
#include <windows.h>
#include <commctrl.h>

namespace first_run_preparation {
inline bool offer(HICON icon) {
    TASKDIALOG_BUTTON buttons[] = {{100, L"Prepare now"}, {101, L"Skip and play"}};
    TASKDIALOGCONFIG td{};
    td.cbSize = sizeof td;
    td.dwFlags = static_cast<TASKDIALOG_FLAGS>(TDF_USE_COMMAND_LINKS | TDF_ALLOW_DIALOG_CANCELLATION);
    td.pszWindowTitle = L"Tourline Prologue";
    td.pszMainInstruction = L"Prepare known shaders before playing?";
    td.pszContent = L"Setup is complete. Optional preparation uses your selected game files and may take several minutes. It covers known shaders and pipelines, with other variants prepared during play.\n\nYou can cancel preparation and start playing, then run Prepare shaders.cmd at any time to resume.";
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
