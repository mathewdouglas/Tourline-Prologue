# Drive to the Car Dealer page (milestone.ps1) and record which shader badge is up while
# doing so: "Compiling shaders" (class gt5p_shaderbusy) and "Loading shaders" (class
# gt5p_shaderpreload). Every 100 ms the badge windows are polled; each change of state is
# written to <Tag>.badges.txt with the time since launch, and the first few images of each
# badge are saved from the badge's own window (PrintWindow, no desktop grab). The game
# window is saved once at the end.
#   scripts\test\badge_dealer.ps1 -Tag t -Engine <exe> -GameRoot <private root> -OutputDirectory <dir> [-Settle 25] NAME=VALUE ...
# Run through C:\tmp\gt5p-testlock\run_locked.py. The private root must hold input\EMAIN.ELF and a copy of the save.
[CmdletBinding(PositionalBinding = $false)]
param([string]$Tag = "badge", [int]$Settle = 25, [string]$Engine = "", [string]$GameRoot = "",
      [string]$OutputDirectory = "", [int]$TimeoutSec = 240, [int]$Images = 3,
      [Parameter(ValueFromRemainingArguments = $true)] $Vars)
. "$PSScriptRoot\milestone.ps1"
Add-Type -AssemblyName System.Drawing
if (-not ("BadgeWin" -as [type])) {
Add-Type @'
using System; using System.Runtime.InteropServices;
public class BadgeWin {
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern IntPtr FindWindow(string c, string t);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; } }
'@ }
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $Engine) { $Engine = "$root\build\gt5p.exe" }
if (-not $GameRoot) { $GameRoot = $root }
$dir = if ($OutputDirectory) { $OutputDirectory } else { "$root\scratch\pv" }
New-Item -ItemType Directory -Force $dir | Out-Null
$set = @{ GT5P_NO_SETTINGS = "1"; FS_HIDE = "grim/file/contents"; PS3_VERBOSE = "0"; PAD_HOLD = $DealerHold; GT5P_PROFVIEW = "0"; GT5P_ROOT = $GameRoot }
foreach ($v in $Vars) { if (-not $v) { continue }; $k, $val = "$v" -split "=", 2; $set[$k] = $val }
$classes = [ordered]@{ compiling = @("gt5p_shaderbusy", 236, 38); loading = @("gt5p_shaderpreload", 196, 30) }
$saved = @{ compiling = 0; loading = 0 }
$state = @{ compiling = $false; loading = $false }
$log = New-Object System.Collections.Generic.List[string]
try {
if (@(Get-Process gt5p -ErrorAction SilentlyContinue).Count) { throw "Another gt5p.exe is running; no process was stopped" }
foreach ($k in $set.Keys) { Set-Item "Env:$k" $set[$k] }
$p = Start-Process -FilePath $Engine -WorkingDirectory $GameRoot -PassThru `
    -RedirectStandardOutput "$dir\$Tag.out" -RedirectStandardError "$dir\$Tag.err"
foreach ($k in $set.Keys) { Remove-Item "Env:$k" -ErrorAction SilentlyContinue }
$tl = New-LogTail "$dir\$Tag.out"
$sw = [Diagnostics.Stopwatch]::StartNew()
$reached = $null
$settleEnd = $null
while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
    $p.Refresh(); if ($p.HasExited) { $log.Add("process exited"); break }
    foreach ($name in $classes.Keys) {
        $c = $classes[$name]
        $h = [BadgeWin]::FindWindow($c[0], [NullString]::Value)
        $vis = ($h -ne [IntPtr]::Zero) -and [BadgeWin]::IsWindowVisible($h)
        if ($vis -ne $state[$name]) {
            $state[$name] = $vis
            $log.Add(("{0,7:N1} s  {1} badge {2}" -f $sw.Elapsed.TotalSeconds, $name, $(if ($vis) { "shown" } else { "hidden" })))
        }
        if ($vis -and $saved[$name] -lt $Images) {
            $bmp = New-Object System.Drawing.Bitmap $c[1], $c[2]
            $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
            [BadgeWin]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc); $g.Dispose()
            $bmp.Save("$dir\$Tag.$name$($saved[$name]).png"); $bmp.Dispose(); $saved[$name]++
        }
    }
    Read-LogTail $tl | Out-Null
    if (-not $reached -and $tl.Text -match "\[milestone\] DealerTopRoot at") {
        $reached = $sw.Elapsed.TotalSeconds; $settleEnd = $reached + $Settle
        $log.Add(("{0,7:N1} s  DealerTopRoot reached" -f $reached))
    }
    if ($settleEnd -and $sw.Elapsed.TotalSeconds -ge $settleEnd) { break }
    Start-Sleep -Milliseconds 100
}
if ($reached) {
    $p.Refresh(); $h = $p.MainWindowHandle
    $r = New-Object BadgeWin+RECT; [BadgeWin]::GetClientRect($h, [ref]$r) | Out-Null
    $bmp = New-Object System.Drawing.Bitmap ([Math]::Max($r.R, 16)), ([Math]::Max($r.B, 16))
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
    [BadgeWin]::PrintWindow($h, $dc, 3) | Out-Null; $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save("$dir\$Tag.win.png"); $bmp.Dispose()
    "dealer page at $([Math]::Round($reached,1)) s; title: $($p.MainWindowTitle)"
} else { "dealer page not reached" }
} finally {
    if ($p) { $p.Refresh(); if (-not $p.HasExited) { $p | Stop-Process -Force -ErrorAction SilentlyContinue } }
    $log | Set-Content -Encoding ascii "$dir\$Tag.badges.txt"
    "badge timeline ($($log.Count) events) in $dir\$Tag.badges.txt"
}
