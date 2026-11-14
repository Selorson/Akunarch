# Mở ComfyUI riêng của anh (D:\ComfyUI-Rieng, cổng 8189, model chung D:\AI-Models).
# Đóng cửa sổ này = tắt ComfyUI riêng. Trong lúc nó bật, hàng đợi GPU của Akunarch tự giữ job lại.
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = 'ComfyUI riêng (8189) - đóng cửa sổ này để tắt'

$Dir = 'D:\ComfyUI-Rieng'
$Url = 'http://127.0.0.1:8189'

function Test-Port([int]$Port) {
    try {
        Invoke-WebRequest "http://127.0.0.1:$Port/system_stats" -UseBasicParsing -TimeoutSec 2 | Out-Null
        return $true
    } catch { return $false }
}

if (Test-Port 8189) {
    Write-Host 'ComfyUI riêng đang bật sẵn, mở trình duyệt.'
    Start-Process $Url
    exit
}

# Akunarch đang dùng card? (job ComfyUI của Akunarch chạy ở cổng 8188; job Blender chạy blender.exe)
function Get-AkunarchBusy {
    $why = @()
    if (Test-Port 8188) { $why += 'ComfyUI của Akunarch (cổng 8188)' }
    if (Get-Process blender -ErrorAction SilentlyContinue) { $why += 'Blender' }
    return $why
}
$busy = Get-AkunarchBusy
if ($busy) {
    Write-Host ("Card đồ hoạ đang bận: " + ($busy -join ', ') + '.') -ForegroundColor Yellow
    Write-Host 'Mở chồng lên có thể tràn VRAM (16 GB). Em sẽ đợi việc đó xong rồi tự mở.'
    Write-Host 'Muốn mở luôn thì bấm phím M.'
    while ($busy) {
        Start-Sleep -Seconds 5
        if ([Console]::KeyAvailable -and [Console]::ReadKey($true).Key -eq 'M') { break }
        $busy = Get-AkunarchBusy
    }
}

Write-Host 'Đang bật ComfyUI riêng... (lần đầu mất khoảng 30 giây, trình duyệt tự mở)'
Set-Location $Dir
& "$Dir\.venv\Scripts\python.exe" main.py --port 8189 --enable-manager --auto-launch
