# Open the F1 page on a NEW settings file (so the written defaults are visible), capture every page,
# turn the "Shader preload indicator" on from the Game page and show what reached the file.
#   scripts\test\rc024_settings_pages.ps1 -Engine <exe> -GameRoot <private root> -OutputDirectory <dir>
# Run through C:\tmp\gt5p-testlock\run_locked.py. Shots are of the game window (PrintWindow).
param([string]$Engine = "", [string]$GameRoot = "", [string]$OutputDirectory = "", [string]$GameDir = "")
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
          PS3_VFS_ROOT = $GameRoot; RSX_SHADER_CACHE = "$dir\cache" }
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
    if (@(Get-Process gt5p -ErrorAction SilentlyContinue).Count) { throw "Another gt5p.exe is running; no process was stopped" }
    foreach ($k in $set.Keys) { Set-Item "Env:$k" $set[$k] }
    Remove-Item Env:GT5P_NO_SETTINGS, Env:PS3_HEADLESS -ErrorAction SilentlyContinue
    $p = Start-Process -FilePath $Engine -WorkingDirectory $GameRoot -PassThru -RedirectStandardOutput "$dir\out.txt" -RedirectStandardError "$dir\err.txt"
    foreach ($k in $set.Keys) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 18
    cap "page0"
    "--- defaults the new file got:"
    Get-Content $toml | Select-String "^(shader_indicator|preload_indicator|shader_warmup|pipeline_async|race_preload) ="
    for ($page = 1; $page -le 8; $page++) { key 0x22; Start-Sleep -Milliseconds 500; cap "page$page" }
    # Back to the Game page from the Debug page; its fifth row is the preload indicator.
    "--- toggling the Shader preload indicator (Game page, fifth row)"
    key 0x21 8                   # Page Up to the first page
    key 0x22 6                   # Video, Shaders, Input, Controls, Feedback, Keyboard, Game (page order, from the shots above)
    key 0x28 4; key 0x27         # fifth row, right: on
    Start-Sleep -Milliseconds 500; cap "game_toggled"
    Get-Content $toml | Select-String "^(shader_indicator|preload_indicator|shader_warmup) ="
} finally {
    if ($p) { $p.Refresh(); if (-not $p.HasExited) { $p | Stop-Process -Force -ErrorAction SilentlyContinue } }
}
