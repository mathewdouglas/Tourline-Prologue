# Isolated three-dealership timing route. Invoke through run_locked.py.
[CmdletBinding(PositionalBinding=$false)]
param([string]$Engine,[string]$GameRoot,[string]$OutputDirectory,[string]$Tag,
      [Parameter(ValueFromRemainingArguments=$true)]$Vars)
. "$PSScriptRoot/milestone.ps1"
Add-Type -AssemblyName System.Drawing
if (-not ("RaceWindowShot" -as [type])) {
    Add-Type @'
using System; using System.Runtime.InteropServices;
public class RaceWindowShot {
 public delegate bool EnumCallback(IntPtr h,IntPtr data);
 [DllImport("user32.dll")] public static extern bool EnumWindows(EnumCallback callback,IntPtr data);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint pid);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetWindowText(IntPtr h,System.Text.StringBuilder text,int count);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int how);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] static extern bool BringWindowToTop(IntPtr h);
 [DllImport("user32.dll")] static extern bool AttachThreadInput(uint one,uint two,bool attach);
 [DllImport("kernel32.dll")] static extern uint GetCurrentThreadId();
 [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
 public static bool ActivateOwnedWindow(IntPtr h) {
  if(h==IntPtr.Zero)return false;
  if(GetForegroundWindow()==h)return true;
  uint unused, current=GetCurrentThreadId();
  uint foreground=GetWindowThreadProcessId(GetForegroundWindow(),out unused);
  bool a=foreground!=0 && foreground!=current && AttachThreadInput(foreground,current,true);
  try { ShowWindow(h,9); BringWindowToTop(h); SetForegroundWindow(h); }
  finally { if(a)AttachThreadInput(foreground,current,false); }
  return GetForegroundWindow()==h;
 }
 public static string ForegroundLabel() {
  IntPtr fg=GetForegroundWindow(); uint owner; GetWindowThreadProcessId(fg,out owner);
  var text=new System.Text.StringBuilder(512); GetWindowText(fg,text,512);
  return "foreground hwnd=0x"+fg.ToInt64().ToString("X")+" pid="+owner+" title='"+text.ToString()+"'";
 }
 public static IntPtr GameWindow(int pid) {
  IntPtr result=IntPtr.Zero;
  EnumWindows((h,data)=>{uint owner;GetWindowThreadProcessId(h,out owner);
   var text=new System.Text.StringBuilder(512);GetWindowText(h,text,512);
   if(owner==pid && (text.ToString().Contains("Gran Turismo") || text.ToString().Contains("Project Tourline Prologue"))){result=h;return false;}return true;},IntPtr.Zero);
  return result;
 }
 [DllImport("user32.dll")] public static extern bool PrintWindow(IntPtr h, IntPtr dc, uint flags);
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h, out Rect r);
 [DllImport("kernel32.dll")] public static extern bool GetExitCodeProcess(IntPtr process, out uint code);
 [StructLayout(LayoutKind.Sequential)] public struct Rect { public int Left,Top,Right,Bottom; }
}
'@
}

$ErrorActionPreference='Stop'
$dir=$OutputDirectory
$shotTimes=[Collections.Generic.List[object]]::new()
$hold=$ToDealers
$t=6000
foreach($visit in 1..3) {
 $hold+=",@DealerSelectRoot+$t-$($t+300):CROSS"
 $a=$t+16000
 $hold+=",@DealerSelectRoot+$a-$($a+150):RIGHT,@DealerSelectRoot+$($a+1500)-$($a+1650):LEFT,@DealerSelectRoot+$($a+3500)-$($a+5500):CIRCLE,@DealerSelectRoot+$($a+10000)-$($a+10150):RIGHT"
 $t=$a+12000
}
$set=@{GT5P_NO_SETTINGS='1';PS3_VERBOSE='0';FS_HIDE='grim/file/contents';PAD_HOLD=$hold;GT5P_ROOT=$GameRoot;GT5P_PROFVIEW='0'}
foreach($v in $Vars){$k,$val="$v" -split '=',2;$set[$k]=$val}
$p=$null
try {
 if(@(Get-Process gt5p -ErrorAction SilentlyContinue).Count){throw 'Another game is running'}
 foreach($k in $set.Keys){Set-Item "Env:$k" $set[$k]}
 $launchMs=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
 $p=Start-Process -FilePath $Engine -WorkingDirectory $GameRoot -PassThru -WindowStyle Hidden -RedirectStandardOutput "$dir/$Tag.out" -RedirectStandardError "$dir/$Tag.err"
 foreach($k in $set.Keys){Remove-Item "Env:$k" -ErrorAction SilentlyContinue}
 $tail=New-LogTail "$dir/$Tag.out"
 if((Wait-Milestone $p $tail 'DealerSelectRoot' 180) -lt 0){throw 'Dealer list not reached'}
 $w=[RaceWindowShot]::GameWindow($p.Id)
 if(-not [RaceWindowShot]::ActivateOwnedWindow($w)){throw 'Foreground activation rejected'}
 $gridMs=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
 for($sec=0;$sec -lt 88;$sec++) {
  $p.Refresh();if($p.HasExited){throw 'Game exited'}
  if([RaceWindowShot]::GetForegroundWindow() -ne $w){throw 'Foreground lost'}
  if($sec -in @(10,20,40,50,68,78)) {
   $begin=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()
   $r=New-Object RaceWindowShot+Rect
   [RaceWindowShot]::GetClientRect($w,[ref]$r)|Out-Null
   $bmp=New-Object System.Drawing.Bitmap ($r.Right),($r.Bottom)
   $g=[Drawing.Graphics]::FromImage($bmp);$dc=$g.GetHdc()
   try{[RaceWindowShot]::PrintWindow($w,$dc,3)|Out-Null}finally{$g.ReleaseHdc($dc);$g.Dispose()}
   $file="$Tag.car$sec.png"
   try{$bmp.Save((Join-Path $dir $file))}finally{$bmp.Dispose()}
   $shotTimes.Add(@{file=$file;start_ms=$begin;end_ms=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds()})
  }
  Start-Sleep -Seconds 1
 }
 @{launch_ms=$launchMs;grid_observed_ms=$gridMs;sample_start_ms=$gridMs;sample_end_ms=[DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds();pid=$p.Id}|ConvertTo-Json|Set-Content "$dir/$Tag.window.json"
 Start-Sleep -Seconds 5 # Flush a complete timing-window prefix before owned cleanup.
} finally {
 ConvertTo-Json -InputObject @($shotTimes.ToArray())|Set-Content "$dir/$Tag.shots.json"
 if($p){$p.Refresh();if(-not $p.HasExited){$p.Kill();$p.WaitForExit(10000)|Out-Null}}
}
