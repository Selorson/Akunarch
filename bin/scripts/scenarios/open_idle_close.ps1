# Kịch bản đo chung: mở app → chờ ổn định → đo → (tuỳ chọn) chờ rảnh → đóng như bấm X → đo tiến trình còn sót.
# CHỈ chạy khi anh cho phép (mở/đóng app thật). Không dùng cho NeuroForge.
param(
    [Parameter(Mandatory = $true)][ValidateSet('selorson', 'akunarch', 'toneforge', 'comfyui-rieng')][string]$App,
    [string]$Tag = 'baseline',
    [int]$SettleSeconds = 20,
    [int]$IdleSeconds = 0
)
$ErrorActionPreference = 'Stop'
$measure = 'E:\Akunarch\bin\scripts\measure_app_resources.ps1'
function M([string]$label, [int]$sec = 10) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File $measure -App $App -Label "$Tag`_$label" -Seconds $sec
}
$cfg = @{
    'selorson'      = @{ exe = "$env:LOCALAPPDATA\Selorson Admin\app.exe"; proc = 'app' }
    'akunarch'      = @{ exe = "$env:LOCALAPPDATA\Akunarch\akunarch.exe"; proc = 'akunarch' }
    'toneforge'     = @{ exe = 'F:\FL studio\toneforge\ToneForge_Studio.exe'; proc = 'ToneForge_Studio' }
    'comfyui-rieng' = @{ exe = 'powershell.exe'; args = '-NoProfile -ExecutionPolicy Bypass -File "E:\Akunarch\bin\scripts\comfyui_rieng.ps1"'; proc = 'powershell'; port = 8189 }
}[$App]

$before = & powershell -NoProfile -ExecutionPolicy Bypass -File $measure -App $App -Label "$Tag`_before" -Seconds 2 | ConvertFrom-Json
if ($before.process_count -gt 0) { throw "$App đang chạy sẵn ($($before.process_count) tiến trình) — anh đang dùng? Dừng kịch bản." }

$p = if ($cfg.args) { Start-Process $cfg.exe -ArgumentList $cfg.args -PassThru -WindowStyle Minimized } else { Start-Process $cfg.exe -PassThru }
if ($cfg.port) {
    for ($i = 0; $i -lt 90; $i++) { try { Invoke-WebRequest "http://127.0.0.1:$($cfg.port)/system_stats" -UseBasicParsing -TimeoutSec 2 | Out-Null; break } catch { Start-Sleep 1 } }
}
Start-Sleep $SettleSeconds
M 'open'
if ($IdleSeconds -gt 0) { Start-Sleep $IdleSeconds; M "idle_${IdleSeconds}s" }

# Đóng như người dùng: CloseMainWindow (bấm X). ComfyUI riêng: đóng cửa sổ console = dừng tiến trình powershell của lối tắt.
if ($App -eq 'comfyui-rieng') {
    [void](Get-Process -Id $p.Id).CloseMainWindow()   # đóng cửa sổ console như anh bấm X
} else {
    Get-Process $cfg.proc -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $cfg.exe } | ForEach-Object { [void]$_.CloseMainWindow() }
}
Start-Sleep 8
M 'after_close' 3
