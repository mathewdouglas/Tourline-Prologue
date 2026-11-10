# Real F1 Feedback layout/action smoke check; private engine/game/settings/cache required.
# Run through run_locked.py. Default disables physical output. -Pulse explicitly sends
# a 250ms body vibration to player one, enables SDL vibration in a NEW private file,
# and checks the real owner-thread API result. Physical feel is a separate acceptance.
param([string]$Engine = "", [string]$GameRoot = "", [string]$OutputDirectory = "", [string]$GameDir = "", [switch]$Pulse)
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System; using System.Runtime.InteropServices; using System.Text;
public class SetUi2 {
 public delegate bool EnumCallback(IntPtr h, IntPtr data);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumCallback callback, IntPtr data);
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h, StringBuilder text, int count);
 [DllImport("user32.dll", CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h, StringBuilder text, int count);
 [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] static extern bool AttachThreadInput(uint a, uint b, bool join);
 [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint f);
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out RECT r);
 [DllImport("user32.dll")] public static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int L,T,R,B; }
 static EnumCallback s_enum;
 static uint s_pid;
 static string s_cls;
 static IntPtr s_found;
 public static IntPtr Owned(uint pid, string cls) {
  s_pid=pid; s_cls=cls; s_found=IntPtr.Zero;
  if (s_enum==null) s_enum=(h, data) => {
   uint owner; GetWindowThreadProcessId(h, out owner);
   if (owner != s_pid) return true;
   var name=new StringBuilder(64); GetClassName(h, name, 64);
   if (name.ToString()==s_cls) { s_found=h; return false; }
   return true;
  };
  EnumWindows(s_enum, IntPtr.Zero);
  return s_found;
 }
 public static bool Activate(IntPtr h) {
  if (h==IntPtr.Zero) return false;
  if (GetForegroundWindow()==h) return true;
  uint unused, current=GetCurrentThreadId();
  uint foreground=GetWindowThreadProcessId(GetForegroundWindow(), out unused);
  bool attached=foreground!=0 && foreground!=current && AttachThreadInput(foreground, current, true);
  try { ShowWindow(h,9); BringWindowToTop(h); SetForegroundWindow(h); }
  finally { if (attached) AttachThreadInput(foreground, current, false); }
  return GetForegroundWindow()==h;
 }
 public static void AltUnlock() {
  keybd_event(0x12, 0, 0, UIntPtr.Zero);
  keybd_event(0x12, 0, 2, UIntPtr.Zero);
 }
 public static string ForegroundLabel() {
  IntPtr fg=GetForegroundWindow(); uint owner; GetWindowThreadProcessId(fg, out owner);
  var text=new StringBuilder(256); GetWindowText(fg, text, 256);
  var cls=new StringBuilder(64); GetClassName(fg, cls, 64);
  return "foreground hwnd=0x"+fg.ToInt64().ToString("X")+" pid="+owner+" class='"+cls+"' title='"+text+"'";
 }
}
'@
$root = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
if (-not $Engine) { $Engine = "$root\build\gt5p.exe" }
if (-not $GameRoot) { $GameRoot = $root }
$dir = if ($OutputDirectory) { $OutputDirectory } else { "$root\scratch\settings_pages" }
New-Item -ItemType Directory -Force $dir | Out-Null
$toml = "$dir\new-settings.toml"
if (Test-Path $toml) { Remove-Item $toml }
if ($Pulse) { Set-Content -Path $toml -Value "[input]`nsdl_rumble = true`n" -Encoding ascii }
$set = @{ GT5P_SETTINGS = $toml; GT5P_SETTINGS_UI = "1"; PS3_VERBOSE = "0"; FS_HIDE = "grim/file/contents"; GT5P_ROOT = $GameRoot;
          PS3_VFS_ROOT = $GameRoot; RSX_SHADER_CACHE = "$dir\cache"; PAD_FEEDBACK_TEST = $(if ($Pulse) { "1" } else { "0" }); PAD_FEEDBACK_TRACE = "1"; PAD_FILE = "$dir\pad.txt"; PAD_HOLD_MERGE = "0" }
if ($GameDir) { $set["GT5P_GAME_DIR"] = $GameDir }
function cap($tag) {
    $h = [SetUi2]::Owned([uint32]$p.Id, "ps3recomp_d3d12")
    if ($h -eq [IntPtr]::Zero) { "no game window ($tag)"; return }
    $r = New-Object SetUi2+RECT; [SetUi2]::GetClientRect($h, [ref]$r) | Out-Null
    $bmp = New-Object System.Drawing.Bitmap ([Math]::Max($r.R,16)), ([Math]::Max($r.B,16))
    $g = [System.Drawing.Graphics]::FromImage($bmp); $dc = $g.GetHdc()
    [SetUi2]::PrintWindow($h, $dc, 2) | Out-Null; $g.ReleaseHdc($dc); $g.Dispose()
    $bmp.Save("$dir\$tag.png"); $bmp.Dispose(); "captured $tag"
}
function key($vk, $n = 1) {
    $h = [SetUi2]::Owned([uint32]$p.Id, "gt5p_settings")
    if ($h -eq [IntPtr]::Zero) { throw "Settings window is not open" }
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
    $uiDeadline = (Get-Date).AddSeconds(15)
    do {
        Start-Sleep -Milliseconds 200
        $err = if (Test-Path "$dir/err.txt") { Get-Content "$dir/err.txt" -Raw } else { '' }
    } until (($err -match '\[settings-ui\] page ready') -or (Get-Date) -gt $uiDeadline)
    if ($err -notmatch '\[settings-ui\] page ready') { throw 'Settings page did not open' }
    Start-Sleep -Seconds 1
    key 0x22 4
    key 0x28 3
    if ($Pulse) {
        # Foreground the settings overlay, not the D3D window. Activating the
        # game window closes F1. The rumble path accepts any foreground window
        # owned by this process.
        $focused=$false
        1..25 | ForEach-Object {
            if (-not $focused) {
                $target = [SetUi2]::Owned([uint32]$p.Id, "gt5p_settings")
                if (-not $focused -and $target -ne [IntPtr]::Zero) { $focused = [SetUi2]::Activate($target) }
                if (-not $focused) { [SetUi2]::AltUnlock(); Start-Sleep -Milliseconds 80 }
            }
        }
        "foreground: $([SetUi2]::ForegroundLabel()) focused=$focused"
        if (-not $focused) { throw "Owned settings window could not receive focus; no pulse requested. $([SetUi2]::ForegroundLabel())" }
    }
    key 0x0D 1
    $logDeadline = (Get-Date).AddSeconds(3)
    do {
        Start-Sleep -Milliseconds 100
        $log = if (Test-Path "$dir/out.txt") { Get-Content "$dir/out.txt" -Raw } else { '' }
    } until ((-not $Pulse) -or ($log -match 'SDL body') -or (Get-Date) -gt $logDeadline)
    cap 'feedback-test-result'
    if ($Pulse) {
        $log=Get-Content "$dir/out.txt" -Raw
        if ($log -notmatch '\[pad-feedback\].*SDL body.*result=0 test=1') { throw 'No accepted SDL pulse in the owner-thread log' }
        if ($log -match 'SDL vibration failed:') { throw 'SDL vibration failed' }
        'PASS: real F1 action queues an accepted 250ms body pulse while ordinary game input is blocked'
    } else { 'PASS: real F1 Feedback layout and test rollback (inspect status in capture)' }
} finally {
    if ($p) { $p.Refresh(); if (-not $p.HasExited) { $p | Stop-Process -Force -ErrorAction SilentlyContinue } }
}
