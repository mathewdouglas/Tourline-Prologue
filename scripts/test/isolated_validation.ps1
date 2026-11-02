# Serialize validation with other isolated Tourline working threads. The owned
# mutex must cover the command's children and cleanup: commands must join them.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$FilePath,
    [Parameter(ValueFromRemainingArguments=$true)][string[]]$CommandArguments
)
$ErrorActionPreference = 'Stop'
$mutex = [Threading.Mutex]::new($false, 'Local\Tourline-Prologue-Isolated-Validation')
$owned = $false
try {
    try { $owned = $mutex.WaitOne(0) }
    catch [Threading.AbandonedMutexException] { $owned = $true }
    if (-not $owned) { throw 'Another Tourline validation owns the shared mutex; no command started.' }
    $running = @(Get-Process gt5p,GT5P-Prepare,tourline-prologue -ErrorAction SilentlyContinue)
    if ($running.Count) { throw 'A game/preparation/launcher is running; no command started or process stopped.' }
    $global:LASTEXITCODE = 0
    & $FilePath @CommandArguments
    if ($LASTEXITCODE) { throw "Validation command exited with code $LASTEXITCODE" }
} finally {
    if ($owned) { $mutex.ReleaseMutex() }
    $mutex.Dispose()
}
