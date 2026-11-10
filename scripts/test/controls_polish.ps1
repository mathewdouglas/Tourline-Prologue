param([string]$Runtime, [string]$Sdl, [switch]$Hardware)
$ErrorActionPreference = 'Stop'
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$dir = "$root/scratch/controls/native"
New-Item -ItemType Directory -Force $dir | Out-Null
Copy-Item -LiteralPath $Sdl -Destination "$dir/SDL2.dll" -Force
@"
@echo off
set "PATH=C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
"C:\Program Files\LLVM\bin\clang-cl.exe" /nologo /O2 /Gy /MD /std:c17 /D_CRT_SECURE_NO_WARNINGS /I"$Runtime" /I"$Runtime/include" /Fo"$dir/controls.obj" /Fe"$dir/controls.exe" "$PSScriptRoot/controls_polish.c" /link /OPT:REF user32.lib
"@ | Set-Content "$dir/build.cmd"
& cmd /c "$dir/build.cmd"
if ($LASTEXITCODE) { throw 'Compile failed' }
$env:PAD_MODERN_CONTROLS='1'; $env:PAD_ADAPTIVE_TRIGGERS='1'; $env:PAD_TRIGGER_RUMBLE='1'; $env:PAD_SDL_RUMBLE='1'
$compileMap = @"
@echo off
set "PATH=C:\Program Files (x86)\Microsoft Visual Studio\Installer;%PATH%"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
"C:\Program Files\LLVM\bin\clang-cl.exe" /nologo /O2 /MD /EHsc /std:c++20 /D_CRT_SECURE_NO_WARNINGS /I"$Runtime/include" /I"$Runtime/runtime/ppu" /Fo"$dir/mapping.obj" /Fe"$dir/mapping.exe" "$PSScriptRoot/controls_mapping.cpp"
"@
$compileMap | Set-Content "$dir/build-map.cmd"
& cmd /c "$dir/build-map.cmd"
if ($LASTEXITCODE) { throw 'Mapping compile failed' }
& "$dir/mapping.exe"
if ($LASTEXITCODE) { throw 'Native mapping test failed' }
foreach($mode in $(if ($Hardware) { @('hardware') } else { @('shapes','packets','effects','capability-size','feedback-hints','guest-feedback','devices','ports','worker') })) {
 & "$dir/controls.exe" $mode
 if ($LASTEXITCODE) { throw "Failed $mode" }
}

$env:PAD_CONTROLS_POLISH='0'
& "$dir/controls.exe" rollback
if ($LASTEXITCODE) { throw 'Failed rollback' }
$env:PAD_NO_SDL='1'
& "$dir/controls.exe" fallback
if ($LASTEXITCODE) { throw 'Failed fallback' }
