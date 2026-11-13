<#
.SYNOPSIS
  Ghép 2 ảnh cạnh nhau cùng chiều cao (concept ↔ ảnh chụp/render 3D) để tự kiểm Luật #7.
.EXAMPLE
  powershell -File compose_compare.ps1 -Left concept.jpg -Right render.png -Out CMP_real.png -Height 900
#>
param(
    [Parameter(Mandatory = $true)][string]$Left,
    [Parameter(Mandatory = $true)][string]$Right,
    [Parameter(Mandatory = $true)][string]$Out,
    [int]$Height = 900,
    [string]$LeftLabel = 'CONCEPT',
    [string]$RightLabel = '3D'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$a = [Drawing.Image]::FromFile((Resolve-Path $Left).Path)
$b = [Drawing.Image]::FromFile((Resolve-Path $Right).Path)
try {
    $wa = [int]($a.Width * $Height / $a.Height)
    $wb = [int]($b.Width * $Height / $b.Height)
    $gap = 16
    $bmp = New-Object Drawing.Bitmap ($wa + $gap + $wb), $Height
    $g = [Drawing.Graphics]::FromImage($bmp)
    $g.Clear([Drawing.Color]::FromArgb(9, 13, 22))
    $g.InterpolationMode = 'HighQualityBicubic'
    $g.DrawImage($a, 0, 0, $wa, $Height)
    $g.DrawImage($b, $wa + $gap, 0, $wb, $Height)
    $font = New-Object Drawing.Font 'Segoe UI', 18, ([Drawing.FontStyle]::Bold)
    $brush = New-Object Drawing.SolidBrush ([Drawing.Color]::FromArgb(231, 210, 158))
    $g.DrawString($LeftLabel, $font, $brush, 12, 10)
    $g.DrawString($RightLabel, $font, $brush, $wa + $gap + 12, 10)
    $g.Dispose()
    New-Item -ItemType Directory -Force (Split-Path $Out) | Out-Null
    $bmp.Save($Out, [Drawing.Imaging.ImageFormat]::Png)
    $bmp.Dispose()
    Write-Output $Out
} finally {
    $a.Dispose(); $b.Dispose()
}
