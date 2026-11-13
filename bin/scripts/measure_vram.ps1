<#
.SYNOPSIS
  Đo VRAM theo cây tiến trình + tải GPU thật trên RTX 4080 (Đợt A — Kế hoạch VRAM v2).

.DESCRIPTION
  - Duyệt toàn bộ hậu duệ của tiến trình gốc (mặc định akunarch.exe), chia nhóm webview / worker / host.
  - Đọc PDH `\GPU Process Memory(*)\Local Usage` và `\GPU Engine(*)\Utilization Percentage`,
    CHỈ trên LUID của GPU rời (LUID có `\GPU Adapter Memory(*)\Dedicated Usage` lớn nhất), bỏ mẫu lỗi.
  - Song song chạy `nvidia-smi -lms 500` để lấy utilization / pstate / công suất toàn máy.
  - Ghi 1 dòng vào docs\vram\measurements.csv và in 1 dòng JSON tóm tắt ra stdout.

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File measure_vram.ps1 -Label baseline_S2 -Seconds 10
#>
param(
    [Parameter(Mandatory = $true)][string]$Label,
    [int]$Seconds = 10,
    [string]$ProcessName = 'akunarch',
    [string]$OutDir = 'E:\Akunarch\docs\vram'
)

$ErrorActionPreference = 'Stop'
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

function Get-Median([double[]]$xs) {
    if (-not $xs -or $xs.Count -eq 0) { return 0 }
    $s = $xs | Sort-Object
    $n = $s.Count
    if ($n % 2 -eq 1) { return [double]$s[[int](($n - 1) / 2)] }
    return ([double]$s[$n / 2 - 1] + [double]$s[$n / 2]) / 2
}

function Get-Percentile([double[]]$xs, [double]$p) {
    if (-not $xs -or $xs.Count -eq 0) { return 0 }
    $s = $xs | Sort-Object
    $idx = [math]::Min($s.Count - 1, [math]::Ceiling($p * $s.Count) - 1)
    return [double]$s[[math]::Max(0, $idx)]
}

# ---------- 1. Cây tiến trình ----------
$all = Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name
$roots = @($all | Where-Object { $_.Name -ieq "$ProcessName.exe" } | ForEach-Object { [int]$_.ProcessId })
$tree = @{}
if ($roots.Count -gt 0) {
    $childrenOf = @{}
    foreach ($p in $all) {
        $pp = [int]$p.ParentProcessId
        if (-not $childrenOf.ContainsKey($pp)) { $childrenOf[$pp] = New-Object System.Collections.ArrayList }
        [void]$childrenOf[$pp].Add($p)
    }
    $queue = New-Object System.Collections.Queue
    foreach ($r in $roots) { $queue.Enqueue($r) }
    while ($queue.Count -gt 0) {
        $cur = [int]$queue.Dequeue()
        if ($tree.ContainsKey($cur)) { continue }
        $name = ($all | Where-Object { [int]$_.ProcessId -eq $cur } | Select-Object -First 1).Name
        $tree[$cur] = $name
        if ($childrenOf.ContainsKey($cur)) {
            foreach ($c in $childrenOf[$cur]) { $queue.Enqueue([int]$c.ProcessId) }
        }
    }
}
$workerNames = @('python.exe', 'blender.exe', 'materialcraft-cli.exe', 'effectcraft-cli.exe', 'filmcraft-cli.exe', 'akunarch-audio-cli.exe', 'ffmpeg.exe')
function Get-Group([int]$procId) {
    $n = [string]$tree[$procId]
    if ($n -ieq 'msedgewebview2.exe') { return 'webview' }
    if ($workerNames -contains $n.ToLower()) { return 'worker' }
    return 'host'
}

# ---------- 2. LUID của GPU rời ----------
function Read-CounterSafe([string[]]$paths) {
    for ($i = 0; $i -lt 2; $i++) {
        try {
            $res = Get-Counter -Counter $paths -ErrorAction SilentlyContinue
            if ($res) { return $res }
        } catch { }
        Start-Sleep -Milliseconds 300
    }
    return $null
}
$adapter = Read-CounterSafe @('\GPU Adapter Memory(*)\Dedicated Usage')
$luid = $null
if ($adapter) {
    $best = $adapter.CounterSamples | Where-Object { $_.Status -eq 0 } | Sort-Object CookedValue -Descending | Select-Object -First 1
    if ($best -and $best.InstanceName -match '(luid_0x[0-9a-f]+_0x[0-9a-f]+)') { $luid = $Matches[1] }
}
if (-not $luid) { throw 'Không xác định được LUID GPU rời từ \GPU Adapter Memory' }

# ---------- 3. nvidia-smi nền ----------
$smiOut = Join-Path $env:TEMP ("akun_smi_{0}.csv" -f ([guid]::NewGuid().ToString('N')))
$smi = Start-Process -FilePath 'nvidia-smi' -ArgumentList @('--query-gpu=utilization.gpu,power.draw,pstate,memory.used', '--format=csv,noheader,nounits', '-lms', '500') `
    -RedirectStandardOutput $smiOut -NoNewWindow -PassThru

# ---------- 4. Lấy mẫu PDH mỗi giây ----------
$memSamples = @{ app = @(); webview = @(); worker = @(); host = @() }
$eng3dSamples = @()
$engAllSamples = @()
$paths = @('\GPU Process Memory(*)\Local Usage', '\GPU Engine(*)\Utilization Percentage')
$sets = $null
try {
    $sets = Get-Counter -Counter $paths -SampleInterval 1 -MaxSamples ([math]::Max(2, $Seconds)) -ErrorAction SilentlyContinue
} catch { }
foreach ($set in @($sets)) {
    if (-not $set) { continue }
    $g = @{ webview = 0.0; worker = 0.0; host = 0.0 }
    $e3d = 0.0; $eAll = 0.0
    foreach ($s in $set.CounterSamples) {
        if ($s.Status -ne 0) { continue }
        if ($s.InstanceName -notmatch '^pid_(\d+)_(luid_0x[0-9a-f]+_0x[0-9a-f]+)_phys_0') { continue }
        $procId = [int]$Matches[1]
        if ($Matches[2] -ne $luid -or -not $tree.ContainsKey($procId)) { continue }
        if ($s.Path -like '*gpu process memory*') {
            $g[(Get-Group $procId)] += $s.CookedValue / 1MB
        } elseif ($s.Path -like '*gpu engine*') {
            $eAll += $s.CookedValue
            if ($s.InstanceName -like '*engtype_3D*') { $e3d += $s.CookedValue }
        }
    }
    $memSamples.webview += $g.webview
    $memSamples.worker += $g.worker
    $memSamples.host += $g.host
    $memSamples.app += ($g.webview + $g.worker + $g.host)
    $eng3dSamples += $e3d
    $engAllSamples += $eAll
}

try { Stop-Process -Id $smi.Id -Force -ErrorAction SilentlyContinue } catch { }
Start-Sleep -Milliseconds 200

# ---------- 5. Đọc nvidia-smi ----------
$util = @(); $power = @(); $pstates = @(); $used = @()
if (Test-Path $smiOut) {
    foreach ($line in Get-Content $smiOut) {
        $parts = $line.Split(',') | ForEach-Object { $_.Trim() }
        if ($parts.Count -lt 4) { continue }
        $u = 0.0; $w = 0.0; $m = 0.0
        if ([double]::TryParse($parts[0], [ref]$u)) { $util += $u }
        if ([double]::TryParse($parts[1], [ref]$w)) { $power += $w }
        $pstates += $parts[2]
        if ([double]::TryParse($parts[3], [ref]$m)) { $used += $m }
    }
    Remove-Item $smiOut -Force -ErrorAction SilentlyContinue
}
$pstateMode = ($pstates | Group-Object | Sort-Object Count -Descending | Select-Object -First 1).Name

$summary = [ordered]@{
    timestamp            = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    label                = $Label
    process              = $ProcessName
    process_count        = $tree.Count
    luid                 = $luid
    samples              = $memSamples.app.Count
    app_vram_mb_median   = [math]::Round((Get-Median $memSamples.app), 1)
    app_vram_mb_max      = [math]::Round((($memSamples.app | Measure-Object -Maximum).Maximum), 1)
    webview_mb_median    = [math]::Round((Get-Median $memSamples.webview), 1)
    worker_mb_median     = [math]::Round((Get-Median $memSamples.worker), 1)
    host_mb_median       = [math]::Round((Get-Median $memSamples.host), 1)
    app_gpu3d_pct_avg    = [math]::Round((($eng3dSamples | Measure-Object -Average).Average), 2)
    app_gpu3d_pct_p95    = [math]::Round((Get-Percentile $eng3dSamples 0.95), 2)
    app_gpu_all_pct_avg  = [math]::Round((($engAllSamples | Measure-Object -Average).Average), 2)
    gpu_util_avg         = [math]::Round((($util | Measure-Object -Average).Average), 2)
    gpu_util_p95         = [math]::Round((Get-Percentile $util 0.95), 2)
    gpu_power_w_avg      = [math]::Round((($power | Measure-Object -Average).Average), 1)
    gpu_pstate_mode      = $pstateMode
    gpu_mem_used_mb_avg  = [math]::Round((($used | Measure-Object -Average).Average), 0)
}

$csv = Join-Path $OutDir 'measurements.csv'
[pscustomobject]$summary | Export-Csv -Path $csv -Append -NoTypeInformation -Encoding UTF8
$summary | ConvertTo-Json -Compress
