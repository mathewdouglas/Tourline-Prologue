# Fit launcher/tourline-prologue.png into a multi-size Windows icon.
# The source is a square logo on black with a wide margin. Icon sizes crop to
# the mark so the wordmark stays readable at 16 px. Rebuilds the ICO in place.
param(
    [string]$Source = (Join-Path $PSScriptRoot '..\..\launcher\tourline-prologue.png'),
    [string]$Destination = (Join-Path $PSScriptRoot '..\..\launcher\tourline-prologue.ico')
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing

function New-FittedBitmap([System.Drawing.Bitmap]$source) {
    $width = $source.Width
    $height = $source.Height
    $rect = New-Object System.Drawing.Rectangle 0, 0, $width, $height
    $data = $source.LockBits($rect, [System.Drawing.Imaging.ImageLockMode]::ReadOnly, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $minX = $width
    $minY = $height
    $maxX = -1
    $maxY = -1
    $stride = $data.Stride
    $bytes = New-Object byte[] ($stride * $height)
    [System.Runtime.InteropServices.Marshal]::Copy($data.Scan0, $bytes, 0, $bytes.Length)
    $source.UnlockBits($data)
    for ($y = 0; $y -lt $height; $y++) {
        $row = $y * $stride
        for ($x = 0; $x -lt $width; $x++) {
            $i = $row + ($x * 4)
            if ($bytes[$i] -gt 12 -or $bytes[$i + 1] -gt 12 -or $bytes[$i + 2] -gt 12) {
                if ($x -lt $minX) { $minX = $x }
                if ($y -lt $minY) { $minY = $y }
                if ($x -gt $maxX) { $maxX = $x }
                if ($y -gt $maxY) { $maxY = $y }
            }
        }
    }
    if ($maxX -lt $minX) { throw "Logo has no visible pixels: $Source" }
    $contentW = $maxX - $minX + 1
    $contentH = $maxY - $minY + 1
    $margin = [Math]::Max(2, [int](0.06 * [Math]::Max($contentW, $contentH)))
    $side = [Math]::Max($contentW, $contentH) + (2 * $margin)
    $centerX = ($minX + $maxX) / 2.0
    $centerY = ($minY + $maxY) / 2.0
    $fitted = New-Object System.Drawing.Bitmap $side, $side
    $graphics = [System.Drawing.Graphics]::FromImage($fitted)
    $graphics.Clear([System.Drawing.Color]::Black)
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $destRect = New-Object System.Drawing.RectangleF ([single]($side / 2.0 - $centerX)), ([single]($side / 2.0 - $centerY)), $width, $height
    $graphics.DrawImage($source, $destRect)
    $graphics.Dispose()
    Write-Host "content ${contentW}x${contentH} fitted to ${side}px"
    return $fitted
}

function Get-PngBytes([System.Drawing.Bitmap]$fitted, [int]$size) {
    $image = New-Object System.Drawing.Bitmap $size, $size
    $graphics = [System.Drawing.Graphics]::FromImage($image)
    $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
    $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
    $graphics.Clear([System.Drawing.Color]::Black)
    $graphics.DrawImage($fitted, 0, 0, $size, $size)
    $graphics.Dispose()
    $stream = New-Object System.IO.MemoryStream
    $image.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $image.Dispose()
    return ,$stream.ToArray()
}

$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$loaded = [System.Drawing.Bitmap]::FromFile($sourcePath)
$bitmap = New-Object System.Drawing.Bitmap $loaded.Width, $loaded.Height, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
$copy = [System.Drawing.Graphics]::FromImage($bitmap)
$copy.DrawImage($loaded, 0, 0, $loaded.Width, $loaded.Height)
$copy.Dispose()
$loaded.Dispose()
$fitted = New-FittedBitmap $bitmap
$bitmap.Dispose()

$sizes = @(16, 24, 32, 48, 64, 128, 256)
$images = foreach ($size in $sizes) { Get-PngBytes $fitted $size }
$fitted.Dispose()

$stream = New-Object System.IO.MemoryStream
$writer = New-Object System.IO.BinaryWriter $stream
$writer.Write([uint16]0)
$writer.Write([uint16]1)
$writer.Write([uint16]$images.Count)
$offset = 6 + (16 * $images.Count)
for ($n = 0; $n -lt $images.Count; $n++) {
    $size = $sizes[$n]
    $dimension = if ($size -ge 256) { [byte]0 } else { [byte]$size }
    $writer.Write($dimension)
    $writer.Write($dimension)
    $writer.Write([byte]0)
    $writer.Write([byte]0)
    $writer.Write([uint16]1)
    $writer.Write([uint16]32)
    $writer.Write([uint32]$images[$n].Length)
    $writer.Write([uint32]$offset)
    $offset += $images[$n].Length
}
foreach ($image in $images) { $writer.Write($image) }
$writer.Flush()
$destinationPath = [System.IO.Path]::GetFullPath($Destination)
[System.IO.File]::WriteAllBytes($destinationPath, $stream.ToArray())
Write-Host ("wrote {0} ({1} bytes)" -f $destinationPath, $stream.Length)
