# Static course-slot checks. Dot-sources the milestone library and compares hold
# strings. It does not launch the game, stop processes, or call Stop-Stragglers.
$ErrorActionPreference = 'Stop'
. "$PSScriptRoot\milestone.ps1"

$daytona6000 = '@TopMenuTemplate+6000-6300:CIRCLE,@TopMenuTemplate+7000-7100:RIGHT,@TopMenuTemplate+7350-7450:RIGHT,@TopMenuTemplate+7700-7800:RIGHT,@TopMenuTemplate+8050-8150:RIGHT,@TopMenuTemplate+9100-9400:CROSS,@CourseSelectRoot+3000-3100:RIGHT,@CourseSelectRoot+4500-4800:CROSS'
$daytona10000 = '@TopMenuTemplate+10000-10300:CIRCLE,@TopMenuTemplate+11000-11100:RIGHT,@TopMenuTemplate+11350-11450:RIGHT,@TopMenuTemplate+11700-11800:RIGHT,@TopMenuTemplate+12050-12150:RIGHT,@TopMenuTemplate+13100-13400:CROSS,@CourseSelectRoot+3000-3100:RIGHT,@CourseSelectRoot+4500-4800:CROSS'
if ((Get-ToDaytona 6000) -ne $daytona6000) { throw 'Get-ToDaytona 6000 changed' }
if ((Get-ToDaytona) -ne $daytona6000) { throw 'Get-ToDaytona default changed' }
if ((Get-ToDaytona 10000) -ne $daytona10000) { throw 'Get-ToDaytona 10000 changed' }
if ((Get-ToCourse 6000) -ne (Get-ToDaytona 6000)) { throw 'Default Get-ToCourse diverges from Daytona' }
if ((Get-ToCourse 10000 1) -ne (Get-ToDaytona 10000)) { throw 'Course slot 1 diverges from Daytona' }
$hsr = (Get-ToDaytona 10000).Replace('@CourseSelectRoot+3000-3100:RIGHT,', '')
if ((Get-ToCourse 10000 0) -ne $hsr) { throw 'Course slot 0 diverges from High Speed Ring' }
$slot2 = '@CourseSelectRoot+3000-3100:RIGHT,@CourseSelectRoot+3400-3500:RIGHT,@CourseSelectRoot+4500-4800:CROSS'
if ((Get-CourseSelectPresses 2) -ne $slot2) { throw 'Course slot 2 no longer matches the measured extra tap at +3400 and confirm at +4500' }
$slot3 = '@CourseSelectRoot+3000-3100:RIGHT,@CourseSelectRoot+3400-3500:RIGHT,@CourseSelectRoot+3800-3900:RIGHT,@CourseSelectRoot+5300-5600:CROSS'
if ((Get-CourseSelectPresses 3) -ne $slot3) { throw 'Course slot 3 confirm no longer keeps the 1400 ms gap' }
$slot9 = @((Get-CourseSelectPresses 9) -split ',')
if ($slot9.Count -ne 10) { throw 'Course slot 9 does not have nine RIGHT taps and one confirm' }
if ($slot9[0] -ne '@CourseSelectRoot+3000-3100:RIGHT' -or $slot9[-1] -notmatch ':CROSS$') {
    throw 'Course slot 9 taps are not ordered from the initial cursor'
}
$rejected = $false
try { Get-CourseSelectPresses 10 | Out-Null } catch { $rejected = $true }
if (-not $rejected) { throw 'Course slot 10 was accepted' }
if ($CourseSlotExperimentalMax -ne 9) { throw 'Experimental course-slot ceiling changed' }

foreach ($path in @("$PSScriptRoot\race.ps1", "$PSScriptRoot\..\train_pipeline_cache.py")) {
    $text = Get-Content -Raw -LiteralPath $path
    if ($text -match 'Stop-Stragglers' -or $text -match 'dealer\.ps1') {
        throw "$path references a global game terminator"
    }
}
'course slot strings match measured High Speed Ring slot 0 and Daytona slot 1'
