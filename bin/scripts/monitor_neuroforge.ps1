# Theo dõi NeuroForge TỪ BÊN NGOÀI (chỉ đọc danh sách tiến trình + bộ đếm hiệu năng). Không mở/tắt/gửi gì vào app,
# không đọc DB của app. Chạy ưu tiên thấp. Ghi:
#   <Out>\nf_samples.csv : mỗi mẫu — RAM/VRAM/CPU cả cây NeuroForge + GPU toàn máy
#   <Out>\nf_events.log  : tiến trình con xuất hiện / kết thúc (tên + dòng lệnh rút gọn, đã che khoá bí mật)
param(
    [string]$Out = 'E:\Akunarch\_archive\toi-uu\neuroforge',
    [int]$IntervalSec = 10,
    [int]$MaxMinutes = 240
)
$ErrorActionPreference = 'Continue'
try { (Get-Process -Id $PID).PriorityClass = 'BelowNormal' } catch { }
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$csv = Join-Path $Out 'nf_samples.csv'
$log = Join-Path $Out 'nf_events.log'

function Mask([string]$s) {
    if (-not $s) { return '' }
    $s = $s -replace '(?i)(api[_-]?key|token|secret|password|passwd|authorization|bearer|cookie|session)([=:\s"]+)[^\s"&]+', '$1$2***'
    $s = $s -replace '\b(sk-[A-Za-z0-9_-]{6})[A-Za-z0-9_-]+', '$1***'
    $s = $s -replace '\b(AIza[0-9A-Za-z_-]{4})[0-9A-Za-z_-]+', '$1***'
    if ($s.Length -gt 260) { $s = $s.Substring(0, 260) + '…' }
    return $s
}
function Log([string]$m) { "$(Get-Date -Format 'HH:mm:ss')  $m" | Out-File -FilePath $log -Append -Encoding utf8 }

$luid = $null
try {
    $ad = Get-Counter -Counter '\GPU Adapter Memory(*)\Dedicated Usage' -ErrorAction SilentlyContinue
    $best = $ad.CounterSamples | Where-Object { $_.Status -eq 0 } | Sort-Object CookedValue -Descending | Select-Object -First 1
    if ($best -and $best.InstanceName -match '(luid_0x[0-9a-f]+_0x[0-9a-f]+)') { $luid = $Matches[1] }
} catch { }

$known = @{}      # pid -> "name | cmd"
$prevCpu = @{}    # pid -> TotalProcessorTime (giây)
$prevT = Get-Date
$cores = [Environment]::ProcessorCount
$deadline = (Get-Date).AddMinutes($MaxMinutes)
Log "=== BẮT ĐẦU theo dõi (mỗi $IntervalSec s, tối đa $MaxMinutes phút)"

while ((Get-Date) -lt $deadline) {
    $all = @(Get-CimInstance Win32_Process | Select-Object ProcessId, ParentProcessId, Name, ExecutablePath, CommandLine)
    $roots = @($all | Where-Object { "$($_.ExecutablePath)" -match '\\NeuroForge RTX\\neuroforge\.exe$' } | ForEach-Object { [int]$_.ProcessId })
    if ($roots.Count -eq 0) { Log '=== neuroforge.exe không còn chạy — kết thúc theo dõi'; break }

    $childrenOf = @{}; $byPid = @{}
    foreach ($p in $all) {
        $byPid[[int]$p.ProcessId] = $p
        $pp = [int]$p.ParentProcessId
        if (-not $childrenOf.ContainsKey($pp)) { $childrenOf[$pp] = New-Object System.Collections.ArrayList }
        [void]$childrenOf[$pp].Add([int]$p.ProcessId)
    }
    $tree = @{}; $q = New-Object System.Collections.Queue
    foreach ($r in $roots) { $q.Enqueue($r) }
    while ($q.Count -gt 0) {
        $c = [int]$q.Dequeue()
        if ($tree.ContainsKey($c) -or -not $byPid.ContainsKey($c)) { continue }
        $tree[$c] = $byPid[$c]
        if ($childrenOf.ContainsKey($c)) { foreach ($k in $childrenOf[$c]) { $q.Enqueue([int]$k) } }
    }

    # Sự kiện: tiến trình con mới / đã kết thúc (bỏ qua msedgewebview2 cho đỡ nhiễu)
    foreach ($procId in $tree.Keys) {
        if (-not $known.ContainsKey($procId)) {
            $p = $tree[$procId]
            $desc = "$($p.Name) | $(Mask $p.CommandLine)"
            $known[$procId] = $desc
            if ($p.Name -ne 'msedgewebview2.exe') { Log "+ [$procId←$($p.ParentProcessId)] $desc" }
        }
    }
    foreach ($procId in @($known.Keys)) {
        if (-not $tree.ContainsKey($procId)) {
            if ($known[$procId] -notlike 'msedgewebview2.exe*') { Log "- [$procId] $($known[$procId].Split('|')[0].Trim())" }
            $known.Remove($procId); $prevCpu.Remove($procId)
        }
    }

    # RAM + CPU
    $now = Get-Date; $dt = ($now - $prevT).TotalSeconds; $prevT = $now
    $priv = 0.0; $ws = 0.0; $cpuSec = 0.0; $top = @{}
    foreach ($procId in $tree.Keys) {
        $gp = Get-Process -Id $procId -ErrorAction SilentlyContinue
        if (-not $gp) { continue }
        $priv += $gp.PrivateMemorySize64; $ws += $gp.WorkingSet64
        $t = 0.0; try { $t = $gp.TotalProcessorTime.TotalSeconds } catch { }
        if ($prevCpu.ContainsKey($procId)) { $d = [math]::Max(0, $t - $prevCpu[$procId]); $cpuSec += $d; $top[$gp.ProcessName] = [double]$top[$gp.ProcessName] + $d }
        $prevCpu[$procId] = $t
    }
    $cpuPct = if ($dt -gt 0) { [math]::Round(100 * $cpuSec / ($dt * $cores), 1) } else { 0 }
    $topCpu = ($top.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 3 | ForEach-Object { "$($_.Key):$([math]::Round(100*$_.Value/($dt*$cores),1))" }) -join ' '

    # VRAM của cây NeuroForge
    $vram = 0.0
    if ($luid) {
        try {
            $set = Get-Counter -Counter '\GPU Process Memory(*)\Local Usage' -ErrorAction SilentlyContinue
            foreach ($s in $set.CounterSamples) {
                if ($s.Status -eq 0 -and $s.InstanceName -match '^pid_(\d+)_(luid_0x[0-9a-f]+_0x[0-9a-f]+)_phys_0' -and $Matches[2] -eq $luid -and $tree.ContainsKey([int]$Matches[1])) {
                    $vram += $s.CookedValue
                }
            }
        } catch { }
    }
    $smi = (& nvidia-smi --query-gpu=memory.used,utilization.gpu --format=csv,noheader,nounits 2>$null | Select-Object -First 1)
    $gpuMem = ''; $gpuUtil = ''
    if ($smi) { $parts = $smi.Split(',') | ForEach-Object { $_.Trim() }; $gpuMem = $parts[0]; $gpuUtil = $parts[1] }
    $os = Get-CimInstance Win32_OperatingSystem
    [pscustomobject][ordered]@{
        time          = $now.ToString('HH:mm:ss')
        procs         = $tree.Count
        nonweb_procs  = @($tree.Values | Where-Object { $_.Name -ne 'msedgewebview2.exe' }).Count
        ram_private_mb = [math]::Round($priv / 1MB)
        ram_ws_mb     = [math]::Round($ws / 1MB)
        vram_nf_mb    = [math]::Round($vram / 1MB)
        cpu_nf_pct    = $cpuPct
        cpu_top       = $topCpu
        gpu_used_mb   = $gpuMem
        gpu_util_pct  = $gpuUtil
        sys_ram_used_gb = [math]::Round(($os.TotalVisibleMemorySize - $os.FreePhysicalMemory) / 1MB, 1)
    } | Export-Csv -Path $csv -Append -NoTypeInformation -Encoding UTF8

    Start-Sleep -Seconds $IntervalSec
}
Log '=== KẾT THÚC'
