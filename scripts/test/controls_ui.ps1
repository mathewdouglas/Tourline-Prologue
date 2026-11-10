# Real-game F1/native mapping acceptance on a private settings/cache/save fixture.
# Run through run_locked.py. -Mapping also edits the game's own button assignment
# dialog, checks F1 follows it, then restores the four defaults from custom No.
param([string]$Engine = "", [string]$GameRoot = "", [string]$OutputDirectory = "", [string]$GameDir = "", [switch]$Mapping)
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices;
public class SetUi2 {
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [DllImport("user32.dll")] public static extern IntPtr FindWindow(string cls, string title);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; } }
'@
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $Engine) { $Engine = "$root\build\gt5p.exe" }
if (-not $GameRoot) { $GameRoot = $root }
$dir = if ($OutputDirectory) { $OutputDirectory } else { "$root\scratch\settings_pages" }
New-Item -ItemType Directory -Force $dir | Out-Null
$toml = "$dir\new-settings.toml"
if (Test-Path $toml) { Remove-Item $toml }
$set = @{ GT5P_SETTINGS = $toml; GT5P_SETTINGS_UI = "1"; PS3_VERBOSE = "0"; FS_HIDE = "grim/file/contents"; GT5P_ROOT = $GameRoot;
          PS3_VFS_ROOT = $GameRoot; RSX_SHADER_CACHE = "$dir\cache"; PAD_FILE = "$dir\pad.txt"; PAD_HOLD_MERGE = "0" }
if ($GameDir) { $set["GT5P_GAME_DIR"] = $GameDir }
function cap($tag) {
    $h = [SetUi2]::FindWindow("ps3recomp_d3d12", [NullString]::Value)
    if ($h -eq [IntPtr]::Zero) { "no game window ($tag)"; return }
    $r = New-Object SetUi2+RECT; [SetUi2]::GetClientRect($h, [ref]$r) | Out-Null
    $bmp = New-Object System.Drawing.Bitmap ([Math]::Max($r.R,16)), ([Math]::Max($r.B,16))
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
    [SetUi2]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save("$dir\$tag.png"); $bmp.Dispose(); "captured $tag"
}
function key($vk, $n = 1) {
    $h = [SetUi2]::FindWindow("gt5p_settings", [NullString]::Value)
    for ($i = 0; $i -lt $n; $i++) { [SetUi2]::PostMessage($h, 0x100, [IntPtr]$vk, [IntPtr]0) | Out-Null; Start-Sleep -Milliseconds 200 }
}
try {
    if (@(Get-Process gt5p -ErrorAction SilentlyContinue).Count) { throw "Another game is running" }
    foreach ($k in $set.Keys) { Set-Item "Env:$k" $set[$k] }
    Remove-Item Env:GT5P_NO_SETTINGS, Env:PS3_HEADLESS -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $Engine -WorkingDirectory $GameRoot -PassThru -RedirectStandardOutput "$dir/out.txt" -RedirectStandardError "$dir/err.txt"
    $deadline = (Get-Date).AddSeconds(65)
    do {
        Start-Sleep -Milliseconds 500
        $p.Refresh()
        if ($p.HasExited) { throw "Game exited: $($p.ExitCode)" }
        $log = if (Test-Path "$dir/out.txt") { Get-Content "$dir/out.txt" -Raw } else { '' }
    } until (($log -match '\[milestone\] TopMenuTemplate') -or (Get-Date) -gt $deadline)
    if ($log -notmatch '\[milestone\] TopMenuTemplate') { throw 'No boot milestone' }
    Start-Sleep -Seconds 3
    key 0x22 3
    Start-Sleep -Seconds 2
    cap 'controls-default'
    key 0x27
    key 0x28; key 0x27
    key 0x28
    if ((Get-Content $toml -Raw) -notmatch 'modern_controls = true') { key 0x27 }
    else { key 0x0D; key 0x0D }
    Start-Sleep -Milliseconds 500
    cap 'controls-changed'
    key 0x25
    Start-Sleep -Milliseconds 500
    cap 'controls-restored'
    if ((Get-Content $toml -Raw) -notmatch 'modern_controls = false') { throw 'Modern No did not follow native defaults' }
    key 0x27
    Start-Sleep -Milliseconds 500
    key 0x22
    Start-Sleep -Milliseconds 500
    cap 'feedback-default'
    $saved = Get-Content $toml -Raw
    if ($saved -notmatch 'trigger_deadzone = 2' -or $saved -notmatch 'trigger_curve = 1' -or $saved -notmatch 'modern_controls = true') { throw 'Control settings did not persist' }
    foreach($name in @('adaptive_triggers','trigger_rumble','sdl_rumble')) {
        if ($saved -notmatch "$name = false") { throw "Unexpected effect default: $name" }
    }
    'PASS: game F1 Controls page, saved dead zone/curve/modern preset; effects remain opt-in'
    key 0x70
    function pad($mask, $reports = 12, $wait = 700) {
        Set-Content -Path "$dir\pad.txt" -Value "$mask $reports" -Encoding ascii
        Start-Sleep -Milliseconds $wait
    }
    Start-Sleep -Seconds 2
    pad 0x2000
    pad 0x20 80 4000
    pad 0x80
    pad 0x80
    pad 0x4000 12 4500
    cap 'game-options'
    if ($Mapping) {
        pad 0x40; pad 0x20; pad 0x4000 12 1800
        cap 'native-modern'
        pad 0x20
        1..3 | ForEach-Object { pad 0x40 }
        cap 'native-cross'
        pad 0x4000; pad 0x40; pad 0x4000
        1..9 | ForEach-Object { pad 0x40 }
        pad 0x4000 12 1500
        if ((Get-Content $toml -Raw) -notmatch 'modern_controls = false') { throw 'In-game edit did not update observed state' }
        key 0x70; key 0x21
        cap 'game-edit-f1-no'
        key 0x28 2
        key 0x0D; key 0x0D
        Start-Sleep -Milliseconds 500
        cap 'explicit-default-no'
        key 0x70
        pad 0x4000 12 1500
        cap 'native-default-restored'
        pad 0x2000
        key 0x70
        key 0x28 2; key 0x27
        Start-Sleep -Milliseconds 500
        cap 'native-modern-again'
        key 0x70
        'PASS: native game mapping, game-side edit detection, explicit default restoration from custom No'
    }

} finally {
    if ($p) { $p.Refresh(); if (-not $p.HasExited) { $p | Stop-Process -Force -ErrorAction SilentlyContinue } }
}
