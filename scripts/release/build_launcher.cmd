@echo off
rem Builds ONLY the native launcher. Never configures/builds/runs the game.
setlocal
if "%~1"=="" (
  echo Usage: build_launcher.cmd output-directory
  exit /b 1
)
if not defined VSCMD_ARG_TGT_ARCH (
  if not defined VSINSTALLDIR (
    echo Run from an x64 Visual Studio Developer Command Prompt.
    exit /b 1
  )
  call "%VSINSTALLDIR%VC\Auxiliary\Build\vcvars64.bat" || exit /b 1
)
if /I not "%VSCMD_ARG_TGT_ARCH%"=="x64" (
  echo An x64 compiler environment is required.
  exit /b 1
)
if not exist "%~1" mkdir "%~1" || exit /b 1
rc /nologo /fo "%~1\launcher.res" "%~dp0..\..\launcher\tourline.rc" || exit /b 1
cl /nologo /std:c++17 /O2 /W4 /MT /EHsc /DUNICODE /D_UNICODE /D_WIN32_WINNT=0x0A00 /DWINVER=0x0A00 ^
  /Fo"%~1\launcher.obj" /Fe"%~1\tourline-prologue.exe" "%~dp0..\..\launcher\launcher.cpp" "%~1\launcher.res" ^
  /link /SUBSYSTEM:WINDOWS /MANIFEST:EMBED ^
  /MANIFESTINPUT:"%~dp0..\..\launcher\launcher.manifest" ^
  user32.lib gdi32.lib shell32.lib ole32.lib uuid.lib bcrypt.lib comctl32.lib
exit /b %errorlevel%
