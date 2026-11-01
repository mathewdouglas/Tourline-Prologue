# Dot-source from a run script: waits on what the title has reached instead of
# fixed sleeps. The exe prints "[milestone] <name> at <ms> ms" to stdout the
# first time the title reads each screen's .gpb (cellPad.c, pad_milestone_seen).
#   . "$PSScriptRoot\milestone.ps1"
#   $tail = New-LogTail "$dir\run1.out"
#   Wait-Milestone $p $tail "DealerTopRoot" 150     # -> $true when seen

# The save boots to the main menu; these presses reach the Car Dealer page.
# Each counts from the milestone named, so a slow boot does not miss them.
# Measured 2026-10-16: Cross 8 s after the menu template opens the manufacturer
# list, Cross 5 s after that list opens the Car Dealer page (about 29 s in all,
# against 47 s with the old fixed times 28/34/46 s). Each has two retries,
# skipped once the screen it opens has been read ("!<milestone>"): the first
# boot after a build can be slow enough for the menu to miss the +8 s press.
#
# Since a car was bought (2026-10-17) the menu opens on News under a
# "Confirmation" popup (shown every boot). Tabs, left to right: News TV Online
# Rankings Arcade 2P-Battle Events Garage Dealerships Replay Options Manual
# Save; the strip does not wrap. Held Right repeats about every 110 ms, too
# fast to let go on Dealerships by time, so: Circle closes the popup, Right
# held 2 s parks on Save, four Left taps reach Dealerships, Cross enters.
# The whole run is tried again 9 s later unless the manufacturer list opened.
function Get-ToDealers([int]$At) {
    $s = @(); $u = ""
    foreach ($try in 0, 1) {
        $t = $At + 9000 * $try
        if ($try) { $u = "!DealerSelectRoot" }
        $s += "@TopMenuTemplate+$t-$($t+300)$($u):CIRCLE"
        $s += "@TopMenuTemplate+$($t+1000)-$($t+3000)$($u):RIGHT"
        foreach ($k in 0..3) { $l = $t + 3300 + 350 * $k; $s += "@TopMenuTemplate+$l-$($l+100)$($u):LEFT" }
        $s += "@TopMenuTemplate+$($t+5000)-$($t+5300)$($u):CROSS"
    }
    $s -join ","
}
$ToDealers = Get-ToDealers 6000

$DealerHold = "$ToDealers,@DealerSelectRoot+5000-5300:CROSS," +
    "@DealerSelectRoot+11000-11300!DealerTopTransition:CROSS,@DealerSelectRoot+17000-17300!DealerTopTransition:CROSS"

# Reads a file that another process is still writing, returning only the text
# added since the last call.
function New-LogTail([string]$Path) { [pscustomobject]@{ Path = $Path; Pos = [int64]0; Text = "" } }
function Read-LogTail($t) {
    if (-not (Test-Path $t.Path)) { return "" }
    try {
        $fs = [IO.File]::Open($t.Path, 'Open', 'Read', 'ReadWrite')
        try {
            if ($fs.Length -le $t.Pos) { return "" }
            $fs.Seek($t.Pos, 'Begin') | Out-Null
            $buf = New-Object byte[] ($fs.Length - $t.Pos)
            $n = $fs.Read($buf, 0, $buf.Length)
            $t.Pos += $n
            $s = [Text.Encoding]::ASCII.GetString($buf, 0, $n)
            $t.Text += $s
            return $s
        } finally { $fs.Close() }
    } catch { return "" }
}

# Polls until the milestone line appears, the process exits or $TimeoutSec
# passes. Returns the seconds it took, or -1.
function Wait-Milestone($Proc, $Tail, [string]$Name, [int]$TimeoutSec = 150) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        Read-LogTail $Tail | Out-Null
        if ($Tail.Text -match "\[milestone\] $Name at") { return [Math]::Round($sw.Elapsed.TotalSeconds, 1) }
        $Proc.Refresh(); if ($Proc.HasExited) { return -1 }
        Start-Sleep -Milliseconds 500
    }
    return -1
}

# Polls the window title until "draws: N" is at least $MinDraws.
function Wait-Draws($Proc, [int]$MinDraws, [int]$TimeoutSec = 60) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $TimeoutSec) {
        $Proc.Refresh(); if ($Proc.HasExited) { return -1 }
        if ($Proc.MainWindowTitle -match 'draws: (\d+)' -and [int]$Matches[1] -ge $MinDraws) {
            return [Math]::Round($sw.Elapsed.TotalSeconds, 1)
        }
        Start-Sleep -Milliseconds 500
    }
    return -1
}

# Before a launch: no other instance may run, or two games share the CPU and
# every number from the run is wrong. Kills leftovers (a killed run can take a
# few seconds to exit) and waits until they are gone.
function Stop-Stragglers {
    $left = @(Get-Process gt5p -ErrorAction SilentlyContinue)
    if ($left.Count) {
        "note: stopping $($left.Count) gt5p.exe still running (pid $(($left | ForEach-Object { $_.Id }) -join ', '))"
        $left | Stop-Process -Force -ErrorAction SilentlyContinue
        $sw = [Diagnostics.Stopwatch]::StartNew()
        while (@(Get-Process gt5p -ErrorAction SilentlyContinue).Count -and $sw.Elapsed.TotalSeconds -lt 20) { Start-Sleep -Milliseconds 250 }
    }
}

# Arcade (tab 5, four Right taps from News) opens Track Select; Right picks
# Daytona, Cross opens its Race Mode page (PitSceneRoot), Cross there opens
# Driving Options, Cross on OK loads the starting grid (Phase 66).
#   $DaytonaHold                       -> Race Mode page
#   "$DaytonaHold,$DaytonaRaceHold"    -> starting grid and race load
# Get-ToDaytona <ms>: the same, starting <ms> after the menu template opens
# (6000 by default). Under RenderDoc the menu compiles its shaders again and
# stops for seconds, and presses at +6 s are lost: use about 16000 there.
function Get-ToDaytona([int]$At = 6000) {
    $s = @("@TopMenuTemplate+$At-$($At+300):CIRCLE")
    foreach ($k in 0..3) { $t = $At + 1000 + 350 * $k; $s += "@TopMenuTemplate+$t-$($t+100):RIGHT" }
    $s += "@TopMenuTemplate+$($At+3100)-$($At+3400):CROSS"
    $s += "@CourseSelectRoot+3000-3100:RIGHT,@CourseSelectRoot+4500-4800:CROSS"
    $s -join ","
}
$DaytonaHold = Get-ToDaytona 6000

# Course slot is the number of discrete RIGHT taps from the initial Course
# Select cursor. Measured: slot 0 is High Speed Ring (no tap) and slot 1 is
# Daytona (one tap at +3000-3100); slot 2 is Fuji Speedway F (verified on its
# Race Mode page in Phase 180). The volume listing has 10 distinct
# piece/course_logo_S assets, so slots 3..9 are an experimental ordinal ceiling.
# That count is not a verified menu length and it does not name those slots.
$CourseSlotExperimentalMax = 9

function Get-CourseSelectPresses([int]$Slot) {
    if ($Slot -lt 0 -or $Slot -gt $CourseSlotExperimentalMax) {
        throw "Course slot $Slot is outside the experimental range 0..$CourseSlotExperimentalMax. Measured slots are 0 (HighSpeedRing), 1 (Daytona), 2 (FujiSpeedwayF)."
    }
    $s = New-Object System.Collections.Generic.List[string]
    for ($k = 0; $k -lt $Slot; $k++) {
        $t = 3000 + 400 * $k
        $s.Add("@CourseSelectRoot+$t-$($t+100):RIGHT")
    }
    # Slots 0 and 1 keep the Daytona confirm at +4500. Slot 2 matches the
    # collected extra tap at +3400 and the same confirm. A later tap keeps the
    # 1400 ms confirm gap used by slot 1 once it would otherwise land on the tap.
    $cross = 4500
    if ($Slot -ge 1) {
        $lastEnd = 3100 + 400 * ($Slot - 1)
        if ($lastEnd + 1000 -gt 4500) { $cross = $lastEnd + 1400 }
    }
    $s.Add("@CourseSelectRoot+$cross-$($cross+300):CROSS")
    $s -join ","
}

# Same menu timing as Get-ToDaytona. Slot 1 reproduces that function's course
# presses; slot 0 reproduces them with the single Daytona RIGHT removed.
function Get-ToCourse([int]$At = 6000, [int]$Slot = 1) {
    $s = @("@TopMenuTemplate+$At-$($At+300):CIRCLE")
    foreach ($k in 0..3) { $t = $At + 1000 + 350 * $k; $s += "@TopMenuTemplate+$t-$($t+100):RIGHT" }
    $s += "@TopMenuTemplate+$($At+3100)-$($At+3400):CROSS"
    $s += (Get-CourseSelectPresses $Slot)
    $s -join ","
}
$DaytonaRaceHold = "@PitSceneRoot+10000-10300:CROSS,@DrivingOptionRoot+3000-3300:CROSS"
# On the starting grid the cursor rests on Start; Cross begins the race.
# "$DaytonaHold,$DaytonaRaceHold,$DaytonaStartHold" -> driving the race.
$DaytonaStartHold = "@QuickArcadeRoot+5000-5300:CROSS"

# The Ferrari page (Phase 60): row 2, fifth column of the manufacturer list.
# Scripted directions are D-pad only, one column a press.
$FerrariHold = "$ToDealers,@DealerSelectRoot+5000-5100:DOWN," +
    "@DealerSelectRoot+6500-6600:RIGHT,@DealerSelectRoot+8000-8100:RIGHT,@DealerSelectRoot+9500-9600:RIGHT," +
    "@DealerSelectRoot+11000-11100:RIGHT,@DealerSelectRoot+13000-13300:CROSS"
