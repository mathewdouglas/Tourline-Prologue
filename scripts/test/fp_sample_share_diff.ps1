# Compare two PrintWindow shots. Prints dimensions and how far the pixels are.
param([Parameter(Mandatory = $true)][string]$Left,
      [Parameter(Mandatory = $true)][string]$Right)
Add-Type -AssemblyName System.Drawing
$a = [System.Drawing.Bitmap]::FromFile((Resolve-Path $Left))
$b = [System.Drawing.Bitmap]::FromFile((Resolve-Path $Right))
try {
    if ($a.Width -ne $b.Width -or $a.Height -ne $b.Height) {
        "size $($a.Width)x$($a.Height) vs $($b.Width)x$($b.Height)"
        exit 2
    }
    $rect = New-Object System.Drawing.Rectangle 0, 0, $a.Width, $a.Height
    $da = $a.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $db = $b.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    try {
        $bytes = $da.Stride * $a.Height
        $ba = New-Object byte[] $bytes
        $bb = New-Object byte[] $bytes
        [System.Runtime.InteropServices.Marshal]::Copy($da.Scan0, $ba, 0, $bytes)
        [System.Runtime.InteropServices.Marshal]::Copy($db.Scan0, $bb, 0, $bytes)
    } finally {
        $a.UnlockBits($da); $b.UnlockBits($db)
    }
    $n = 0; $diff = 0; $sum = [int64]0; $max = 0
    for ($y = 0; $y -lt $a.Height; $y++) {
        $row = $y * $da.Stride
        for ($x = 0; $x -lt $a.Width; $x++) {
            $i = $row + $x * 4
            $d = [Math]::Abs($ba[$i] - $bb[$i]) + [Math]::Abs($ba[$i+1] - $bb[$i+1]) + [Math]::Abs($ba[$i+2] - $bb[$i+2])
            $n++
            if ($d -gt 0) { $diff++ }
            $sum += $d
            if ($d -gt $max) { $max = $d }
        }
    }
    "pixels=$n changed=$diff maxAbs=$max meanAbs=$([Math]::Round($sum / [double]$n, 4)) size=$($a.Width)x$($a.Height)"
} finally {
    $a.Dispose(); $b.Dispose()
}
