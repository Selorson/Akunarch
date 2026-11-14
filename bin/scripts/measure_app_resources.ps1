<#
.SYNOPSIS
  Đo RAM + VRAM của một app (cả cây tiến trình) và tìm tiến trình còn sót sau khi tắt.

.DESCRIPTION
  Nhận diện tiến trình của app theo đường dẫn exe / dòng lệnh (kể cả WebView2 theo thư mục dữ liệu của app),
  cộng thêm toàn bộ tiến trình con. Mỗi giây lấy mẫu:
    - RAM: Private Bytes và Working Set (Get-Process),
    - VRAM: PDH `\GPU Process Memory(*)\Local Usage` trên GPU rời,
  rồi ghi 1 dòng vào measurements.csv và in JSON tóm tắt (kèm danh sách tiến trình).
  Chỉ ĐỌC số liệu, không mở/tắt/gửi gì vào app (an toàn với app đang chạy như NeuroForge).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File measure_app_resources.ps1 -App cowriter -Label idle -Seconds 10
  powershell -ExecutionPolicy Bypass -File measure_app_resources.ps1 -App all -Label snapshot -Seconds 3
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('selorson', 'akunarch', 'cowriter', 'toneforge', 'comfyui', 'comfyui-rieng', 'neuroforge', 'all')]
    [string]$App,
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$Seconds = 10,
    [string]$OutDir = 'E:\Akunarch\docs\toi-uu-tai-nguyen'
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Dấu hiệu nhận diện: regex trên ExecutablePath hoặc CommandLine (không phân biệt hoa thường).
# WebView2 của app Tauri nằm ở %LOCALAPPDATA%\<identifier>\EBWebView → bắt theo identifier trong dòng lệnh.
$Signatures = [ordered]@{
    'selorson'      = @('\\Selorson Admin\\app\.exe', 'com\.selorson\.app')
    'akunarch'      = @('\\Akunarch\\akunarch\.exe', 'vn\.selorson\.akunarch')
    'cowriter'      = @('\\Co-Writer\\', 'vn\.selorson\.cowriter', 'sd-server\.exe')
    'toneforge'     = @('\\toneforge\\', 'com\.toneforge\.studio')
    'comfyui'       = @('Akunarch\\repos\\ComfyUI', 'Git-repo\\ComfyUI')
    'comfyui-rieng' = @('ComfyUI-Rieng')
    'neuroforge'    = @('\\NeuroForge RTX\\', 'com\.neuroforge\.app')
}
$targets = if ($App -eq 'all') { @($Signatures.Keys) } else { @($App) }

function Get-Median([double[]]$xs) {
    if (-not $xs -or $xs.Count -eq 0) { return 0 }
    $s = $xs | Sort-Object; $n = $s.Count
    if ($n % 2 -eq 1) { return [double]$s[[int](($n - 1) / 2)] }
    return ([double]$s[$n / 2 - 1] + [double]$s[$n / 2]) / 2
}

# ---------- Cây tiến trình theo từng app ----------
$all = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine)
$childrenOf = @{}
foreach ($p in $all) {
    $pp = [int]$p.ParentProcessId
    if (-not $childrenOf.ContainsKey($pp)) { $childrenOf[$pp] = New-Object System.Collections.ArrayList }
    [void]$childrenOf[$pp].Add([int]$p.ProcessId)
}
$byPid = @{}; foreach ($p in $all) { $byPid[[int]$p.ProcessId] = $p }

$trees = @{}
foreach ($t in $targets) {
    $seed = @($all | Where-Object {
            $txt = "$($_.ExecutablePath) $($_.CommandLine)"
            $hit = $false
            foreach ($rx in $Signatures[$t]) { if ($txt -match $rx) { $hit = $true; break } }
            $hit -and [int]$_.ProcessId -ne $PID
        } | ForEach-Object { [int]$_.ProcessId })
    $set = @{}
    $q = New-Object System.Collections.Queue
    foreach ($s in $seed) { $q.Enqueue($s) }
    while ($q.Count -gt 0) {
        $cur = [int]$q.Dequeue()
        if ($set.ContainsKey($cur) -or -not $byPid.ContainsKey($cur)) { continue }
        $set[$cur] = $byPid[$cur].Name
        if ($childrenOf.ContainsKey($cur)) { foreach ($c in $childrenOf[$cur]) { $q.Enqueue([int]$c) } }
    }
    $trees[$t] = $set
}

# ---------- LUID GPU rời ----------
$luid = $null
try {
    $ad = Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -ErrorAction SilentlyContinue
    $best = $ad.CounterSamples | Where-Object { $_.Status -eq 0 } | Sort-Object CookedValue -Descending | Select-Object -First 1
    if ($best -and $best.InstanceName -match '(luid_0x[0-9a-f]+_0x[0-9a-f]+)') { $luid = $Matches[1] }
} catch { }

# ---------- Lấy mẫu mỗi giây ----------
$acc = @{}
foreach ($t in $targets) { $acc[$t] = @{ priv = @(); ws = @(); vram = @() } }
$n = [math]::Max(1, $Seconds)
for ($i = 0; $i -lt $n; $i++) {
    $vramByPid = @{}
    if ($luid) {
        try {
            $set = Get-Counter -Counter '\GPU Process Memory(*)\Local Usage' -ErrorAction SilentlyContinue
            foreach ($s in $set.CounterSamples) {
                if ($s.Status -ne 0 -or $s.InstanceName -notmatch '^pid_(\d+)_(luid_0x[0-9a-f]+_0x[0-9a-f]+)_phys_0') { continue }
                if ($Matches[2] -ne $luid) { continue }
                $vramByPid[[int]$Matches[1]] = [double]$s.CookedValue
            }
        } catch { }
    }
    $procs = @{}; foreach ($gp in Get-Process) { $procs[$gp.Id] = $gp }
    foreach ($t in $targets) {
        $priv = 0.0; $ws = 0.0; $vr = 0.0
        foreach ($procId in $trees[$t].Keys) {
            if ($procs.ContainsKey($procId)) { $priv += $procs[$procId].PrivateMemorySize64; $ws += $procs[$procId].WorkingSet64 }
            if ($vramByPid.ContainsKey($procId)) { $vr += $vramByPid[$procId] }
        }
        $acc[$t].priv += $priv / 1MB; $acc[$t].ws += $ws / 1MB; $acc[$t].vram += $vr / 1MB
    }
    if ($i -lt $n - 1) { Start-Sleep -Milliseconds 700 }
}

# ---------- Kết quả ----------
$smi = (& nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
$csv = Join-Path $OutDir 'measurements.csv'
$out = @()
foreach ($t in $targets) {
    $names = $trees[$t].Values | Group-Object | Sort-Object Count -Descending | ForEach-Object { "$($_.Name)x$($_.Count)" }
    $row = [ordered]@{
        timestamp       = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
        app             = $t
        label           = $Label
        process_count   = $trees[$t].Count
        ram_private_mb  = [math]::Round((Get-Median $acc[$t].priv), 1)
        ram_ws_mb       = [math]::Round((Get-Median $acc[$t].ws), 1)
        vram_mb_median  = [math]::Round((Get-Median $acc[$t].vram), 1)
        vram_mb_max     = [math]::Round((($acc[$t].vram | Measure-Object -Maximum).Maximum), 1)
        gpu_used_mb_all = $smi
        processes       = ($names -join ' ')
    }
    [pscustomobject]$row | Export-Csv -Path $csv -Append -NoTypeInformation -Encoding UTF8
    $out += [pscustomobject]$row
}
$out | ConvertTo-Json -Compress
