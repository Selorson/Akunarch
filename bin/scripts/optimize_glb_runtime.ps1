<#
.SYNOPSIS
  Nén texture của một .glb kỳ quan sang KTX2 (Basis Universal) cho sân khấu WebGL — Kế hoạch VRAM v2 · B3.

.DESCRIPTION
  - Bản gốc (JPEG) nằm ở clockwork\_master\<slug>.glb (Q3). KHÔNG BAO GIỜ ghi đè _master:
      * runtime chưa phải KTX2 và _master chưa có  → chép runtime vào _master rồi nén.
      * runtime chưa phải KTX2 và _master đã có    → (bản xuất mới) chuyển _master cũ sang _master\history\
                                                      (đổi tên, không ghi đè), chép runtime mới vào _master.
      * runtime đã là KTX2                          → nén lại từ _master (dùng khi đổi chế độ màu).
  - dedup + prune; MỌI texture mã hóa UASTC (toktx, gán OETF sRGB cho slot màu) rồi giải mã sẵn sang
    KTX2 BC7 + zstd (ktx2_to_bc7.mjs). Lý do: transcoder Basis của three cần 'unsafe-eval' (embind
    `new Function`) mà CSP Akunarch không cho; BC7 thì KTX2Loader nạp thẳng không cần transcoder.
    BC7 = 1 byte/px (JPEG giải nén RGBA8 = 4 byte/px). Mesh giữ Draco.
  - Bản KTX2 giữ đúng tên <slug>.glb (mọi manifest không phải sửa). Ghi qua file tạm rồi thay thế nguyên tử.
  - Công cụ cục bộ: E:\Akunarch\bin\tools\gltf-transform (npm) + E:\Akunarch\bin\tools\ktx-software\bin (toktx).
  - In ra 1 dòng JSON tóm tắt (ok, master, bytes trước/sau, số ảnh, mime).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File optimize_glb_runtime.ps1 -Glb E:\Akunarch\projects\temple-of-zyberon\clockwork\temple-of-zyberon.glb
#>
param(
    [Parameter(Mandatory = $true)][string]$Glb,
    [string]$ToolsDir = 'E:\Akunarch\bin\tools'
)

$ErrorActionPreference = 'Stop'
$cli = Join-Path $ToolsDir 'gltf-transform\node_modules\@gltf-transform\cli\bin\cli.js'
$ktxBin = Join-Path $ToolsDir 'ktx-software\bin'
if (-not (Test-Path $cli)) { throw "Thiếu gltf-transform: $cli" }
if (-not (Test-Path (Join-Path $ktxBin 'toktx.exe'))) { throw "Thiếu toktx: $ktxBin" }
$env:PATH = "$ktxBin;$env:PATH"

$Glb = (Resolve-Path $Glb).Path
$dir = Split-Path $Glb -Parent
$name = Split-Path $Glb -Leaf
$masterDir = Join-Path $dir '_master'
$master = Join-Path $masterDir $name

function Invoke-Gltf([string[]]$argv) {
    $out = & node $cli @argv 2>&1
    if ($LASTEXITCODE -ne 0) { throw "gltf-transform $($argv[0]) lỗi:`n$($out | Out-String)" }
    return $out
}

function Get-ImageMimes([string]$path) {
    $json = Invoke-Gltf @('inspect', $path, '--format', 'csv')
    # Không cần parse CSV: đếm theo mime xuất hiện trong bảng TEXTURES
    $text = $json | Out-String
    return @{
        jpeg = ([regex]::Matches($text, 'image/jpeg')).Count
        png  = ([regex]::Matches($text, 'image/png')).Count
        ktx2 = ([regex]::Matches($text, 'image/ktx2')).Count
    }
}

function Test-IsKtx2Glb([string]$path) {
    # Đọc chunk JSON của GLB: extensionsUsed có KHR_texture_basisu?
    $fs = [System.IO.File]::OpenRead($path)
    try {
        $br = New-Object System.IO.BinaryReader($fs)
        [void]$br.ReadBytes(12)
        $len = $br.ReadUInt32()
        [void]$br.ReadUInt32()
        $jsonText = [System.Text.Encoding]::UTF8.GetString($br.ReadBytes([int]$len))
        return $jsonText -match '"KHR_texture_basisu"'
    } finally { $fs.Dispose() }
}

$bytesBefore = (Get-Item $Glb).Length
$isKtx = Test-IsKtx2Glb $Glb
New-Item -ItemType Directory -Force -Path $masterDir | Out-Null
$archivedMaster = $null
if (-not $isKtx) {
    # _master đã có và trùng từng byte với runtime (lần chạy trước bị ngắt giữa chừng) → dùng lại, không lưu lịch sử thừa
    $sameAsMaster = (Test-Path $master) -and ((Get-FileHash $master).Hash -eq (Get-FileHash $Glb).Hash)
    if ($sameAsMaster) {
        # giữ nguyên _master
    } elseif (Test-Path $master) {
        $hist = Join-Path $masterDir 'history'
        New-Item -ItemType Directory -Force -Path $hist | Out-Null
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $archivedMaster = Join-Path $hist ("{0}.{1}.glb" -f [IO.Path]::GetFileNameWithoutExtension($name), $stamp)
        Move-Item -LiteralPath $master -Destination $archivedMaster
    }
    if (-not $sameAsMaster) {
        Copy-Item -LiteralPath $Glb -Destination $master
        if ((Get-FileHash $master).Hash -ne (Get-FileHash $Glb).Hash) { throw "Chép bản gốc vào _master lệch SHA-256" }
    }
} elseif (-not (Test-Path $master)) {
    throw "Runtime đã là KTX2 nhưng không có bản gốc $master — không thể nén lại."
}

$tmp = Join-Path ([IO.Path]::GetTempPath()) ("akun_ktx2_{0}" -f ([guid]::NewGuid().ToString('N')))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
try {
    $t1 = Join-Path $tmp '1_dedup.glb'
    $t2 = Join-Path $tmp '2_prune.glb'
    $t3 = Join-Path $tmp '3_uastc.glb'
    $final = Join-Path $tmp '4_bc7.glb'
    Invoke-Gltf @('dedup', $master, $t1) | Out-Null
    Invoke-Gltf @('prune', $t1, $t2) | Out-Null
    # UASTC mức 4 (chất lượng cao nhất) — không zstd ở bước này vì bước BC7 tự siêu nén lại
    Invoke-Gltf @('uastc', $t2, $t3, '--level', '4', '--jobs', '2') | Out-Null
    $bc7 = & node (Join-Path $PSScriptRoot 'ktx2_to_bc7.mjs') $t3 $final 2>&1
    if ($LASTEXITCODE -ne 0) { throw "ktx2_to_bc7 lỗi:`n$($bc7 | Out-String)" }

    $mimes = Get-ImageMimes $final
    if ($mimes.jpeg -gt 0 -or $mimes.png -gt 0) { throw "Còn ảnh chưa nén KTX2: $($mimes | ConvertTo-Json -Compress)" }
    if (-not (Test-IsKtx2Glb $final)) { throw 'Bản xuất không có KHR_texture_basisu' }

    # Thay thế nguyên tử bản runtime (bản gốc đã an toàn trong _master)
    $staged = "$Glb.ktx2.tmp"
    Copy-Item -LiteralPath $final -Destination $staged -Force
    Move-Item -LiteralPath $staged -Destination $Glb -Force
    $srcMimes = Get-ImageMimes $master
    [pscustomobject]@{
        ok              = $true
        glb             = $Glb
        master          = $master
        archived_master = $archivedMaster
        texture_format  = 'KTX2 BC7 + zstd (từ UASTC L4)'
        bytes_master    = (Get-Item $master).Length
        bytes_before    = $bytesBefore
        bytes_after     = (Get-Item $Glb).Length
        images_master   = $srcMimes.jpeg + $srcMimes.png + $srcMimes.ktx2
        images_after    = $mimes.ktx2
    } | ConvertTo-Json -Compress
} finally {
    Remove-Item -LiteralPath $tmp -Recurse -Force -ErrorAction SilentlyContinue
}
