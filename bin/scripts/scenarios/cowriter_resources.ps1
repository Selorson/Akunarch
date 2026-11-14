# Kịch bản đo RAM/VRAM Co-Writer (đợt tối ưu tài nguyên). CHỈ chạy khi anh cho phép (mở/đóng app thật).
# Các mốc: mở xong → sau 1 lần truy xuất (nạp bộ nhúng CUDA) → rảnh 5 phút → sau khi tắt (tiến trình còn sót).
# Truy xuất chỉ ĐỌC kho (POST /index/retrieve), không ghi gì vào co_writer.db.
param([string]$Tag = 'baseline', [int]$IdleSeconds = 300)
$ErrorActionPreference = 'Stop'
$measure = 'E:\Akunarch\bin\scripts\measure_app_resources.ps1'
function M([string]$label, [int]$sec = 10) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $measure -App cowriter -Label "$Tag`_$label" -Seconds $sec
}

if (Get-Process cowriter -ErrorAction SilentlyContinue) { throw 'Co-Writer đang mở — anh đang dùng? Dừng kịch bản.' }
Start-Process "$env:LOCALAPPDATA\Co-Writer\cowriter.exe"
$ready = $false
for ($i = 0; $i -lt 90; $i++) {
    try { Invoke-WebRequest http://127.0.0.1:8787/health -UseBasicParsing -TimeoutSec 2 | Out-Null; $ready = $true; break } catch { Start-Sleep 1 }
}
if (-not $ready) { throw 'Lõi Co-Writer không lên sau 90 s' }
Start-Sleep 10
M 'open'

$body = @{ query = 'tháp đồng hồ thiên văn Eryndor'; recall = 50; rerank_top = 20; final = 8; token_budget = 4000 } | ConvertTo-Json
$t0 = Get-Date
Invoke-RestMethod http://127.0.0.1:8787/index/retrieve -Method Post -ContentType 'application/json; charset=utf-8' -Body ([Text.Encoding]::UTF8.GetBytes($body)) | Out-Null
"retrieve: {0:N1} s" -f ((Get-Date) - $t0).TotalSeconds
M 'after_retrieve'

Start-Sleep $IdleSeconds
M "idle_${IdleSeconds}s"

# Tắt như người dùng bấm X: đóng cửa sổ chính (CloseMainWindow), không giết cứng.
Get-Process cowriter -ErrorAction SilentlyContinue | ForEach-Object { [void]$_.CloseMainWindow() }
Start-Sleep 8
M 'after_close' 3
