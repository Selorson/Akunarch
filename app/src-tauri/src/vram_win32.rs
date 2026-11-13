//! Kế hoạch VRAM v2 · Đợt B · B1 — VRAM của riêng cây tiến trình Akunarch (PDH, lọc theo LUID GPU rời).
//!
//! - `\GPU Process Memory(*)\Local Usage` theo từng `pid_<PID>_luid_<LUID>_phys_<n>`; chỉ cộng các mẫu
//!   trên LUID có `\GPU Adapter Memory(*)\Dedicated Usage` lớn nhất (RTX 4080) và `phys_0`
//!   (một PID có thể xuất hiện trên 2 LUID — iGPU + dGPU).
//! - Hậu duệ của `std::process::id()` dựng từ MỘT snapshot Toolhelp (tránh lẫn PID tái sử dụng),
//!   chia nhóm `webview` / `worker` / `host`. Cùng logic với `bin\scripts\measure_vram.ps1`.
//! - Không phải Windows: trả về `available = false`, toàn số 0.

use serde::{Deserialize, Serialize};
use std::collections::{HashMap, HashSet};

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum ProcGroup {
    Webview,
    Worker,
    Host,
}

#[derive(Debug, Clone, Default, PartialEq, Serialize, Deserialize)]
pub struct AppVramSample {
    pub available: bool,
    pub app_mb: i64,
    pub webview_mb: i64,
    pub worker_mb: i64,
    pub host_mb: i64,
}

const WORKER_EXES: &[&str] = &[
    "python.exe",
    "blender.exe",
    "materialcraft-cli.exe",
    "effectcraft-cli.exe",
    "filmcraft-cli.exe",
    "akunarch-audio-cli.exe",
    "ffmpeg.exe",
];

pub fn classify_exe(exe: &str) -> ProcGroup {
    let lower = exe.to_ascii_lowercase();
    if lower == "msedgewebview2.exe" {
        ProcGroup::Webview
    } else if WORKER_EXES.contains(&lower.as_str()) || lower.ends_with("-cli.exe") {
        ProcGroup::Worker
    } else {
        ProcGroup::Host
    }
}

/// `pid_1234_luid_0x00000000_0x00010AF9_phys_0` → `(1234, "luid_0x00000000_0x00010af9", 0)`.
pub fn parse_process_instance(name: &str) -> Option<(u32, String, u32)> {
    let lower = name.trim().to_ascii_lowercase();
    let rest = lower.strip_prefix("pid_")?;
    let (pid_s, rest) = rest.split_once('_')?;
    let pid = pid_s.parse::<u32>().ok()?;
    let luid = parse_adapter_luid(rest)?;
    let phys_s = rest.strip_prefix(&luid)?.strip_prefix("_phys_")?;
    let phys = phys_s.parse::<u32>().ok()?;
    Some((pid, luid, phys))
}

/// `luid_0x00000000_0x00010AF9_phys_0` (hoặc chuỗi bắt đầu bằng nó) → `luid_0x00000000_0x00010af9`.
pub fn parse_adapter_luid(name: &str) -> Option<String> {
    let lower = name.trim().to_ascii_lowercase();
    let rest = lower.strip_prefix("luid_")?;
    let mut parts = rest.splitn(3, '_');
    let hi = parts.next()?;
    let lo = parts.next()?;
    let is_hex = |s: &str| {
        s.len() > 2 && s.starts_with("0x") && s[2..].chars().all(|c| c.is_ascii_hexdigit())
    };
    if !is_hex(hi) || !is_hex(lo) {
        return None;
    }
    Some(format!("luid_{hi}_{lo}"))
}

/// LUID có tổng `Dedicated Usage` lớn nhất (GPU rời). Cộng dồn nếu một LUID có nhiều `phys_n`.
pub fn pick_dedicated_luid(adapters: &[(String, f64)]) -> Option<String> {
    let mut totals: HashMap<String, f64> = HashMap::new();
    for (name, bytes) in adapters {
        if let Some(luid) = parse_adapter_luid(name) {
            *totals.entry(luid).or_insert(0.0) += bytes.max(0.0);
        }
    }
    totals
        .into_iter()
        .filter(|(_, b)| *b > 0.0)
        .max_by(|a, b| a.1.partial_cmp(&b.1).unwrap_or(std::cmp::Ordering::Equal))
        .map(|(l, _)| l)
}

/// Tập `root` + mọi hậu duệ từ danh sách `(pid, ppid)` của một snapshot. Chịu được vòng lặp PID
/// (PID tái sử dụng) và PID mồ côi. `root` không có trong snapshot → tập rỗng.
pub fn descendants(root: u32, procs: &[(u32, u32)]) -> HashSet<u32> {
    let mut out = HashSet::new();
    if !procs.iter().any(|(p, _)| *p == root) {
        return out;
    }
    let mut children: HashMap<u32, Vec<u32>> = HashMap::new();
    for (pid, ppid) in procs {
        if pid != ppid {
            children.entry(*ppid).or_default().push(*pid);
        }
    }
    let mut stack = vec![root];
    while let Some(cur) = stack.pop() {
        if !out.insert(cur) {
            continue;
        }
        if let Some(kids) = children.get(&cur) {
            stack.extend(kids.iter().copied().filter(|k| !out.contains(k)));
        }
    }
    out
}

/// Cộng `Local Usage` (byte) của cây tiến trình `root` trên đúng `luid`, `phys_0`, chia nhóm.
pub fn aggregate(
    root: u32,
    procs: &[(u32, u32, String)],
    luid: &str,
    samples: &[(String, f64)],
) -> AppVramSample {
    let pairs: Vec<(u32, u32)> = procs.iter().map(|(p, pp, _)| (*p, *pp)).collect();
    let tree = descendants(root, &pairs);
    let exe_of: HashMap<u32, &str> = procs.iter().map(|(p, _, e)| (*p, e.as_str())).collect();
    let (mut web, mut work, mut host) = (0.0f64, 0.0f64, 0.0f64);
    for (name, bytes) in samples {
        let Some((pid, l, phys)) = parse_process_instance(name) else {
            continue;
        };
        if phys != 0 || l != luid || !tree.contains(&pid) {
            continue;
        }
        match classify_exe(exe_of.get(&pid).copied().unwrap_or("")) {
            ProcGroup::Webview => web += bytes,
            ProcGroup::Worker => work += bytes,
            ProcGroup::Host => host += bytes,
        }
    }
    let mb = |b: f64| (b / 1_048_576.0).round() as i64;
    AppVramSample {
        available: true,
        app_mb: mb(web + work + host),
        webview_mb: mb(web),
        worker_mb: mb(work),
        host_mb: mb(host),
    }
}

/// Đọc VRAM của cây tiến trình app hiện tại. Chạy trên `spawn_blocking`, timeout 1500 ms;
/// lỗi/timeout → `available = false` (không làm hỏng IPC).
pub async fn sample_app_vram_async() -> AppVramSample {
    let task = tokio::task::spawn_blocking(sample_app_vram_blocking);
    match tokio::time::timeout(std::time::Duration::from_millis(1500), task).await {
        Ok(Ok(s)) => s,
        _ => AppVramSample::default(),
    }
}

#[cfg(not(windows))]
pub fn sample_app_vram_blocking() -> AppVramSample {
    AppVramSample::default()
}

#[cfg(windows)]
pub fn sample_app_vram_blocking() -> AppVramSample {
    sys::sample(std::process::id())
}

#[cfg(windows)]
mod sys {
    use super::{aggregate, pick_dedicated_luid, AppVramSample};
    use std::sync::Mutex;
    use windows_sys::Win32::Foundation::{CloseHandle, INVALID_HANDLE_VALUE};
    use windows_sys::Win32::System::Diagnostics::ToolHelp::{
        CreateToolhelp32Snapshot, Process32FirstW, Process32NextW, PROCESSENTRY32W,
        TH32CS_SNAPPROCESS,
    };
    use windows_sys::Win32::System::Performance::{
        PdhAddEnglishCounterW, PdhCollectQueryData, PdhGetFormattedCounterArrayW, PdhOpenQueryW,
        PDH_CSTATUS_NEW_DATA, PDH_CSTATUS_VALID_DATA, PDH_FMT_COUNTERVALUE_ITEM_W, PDH_FMT_DOUBLE,
        PDH_HCOUNTER, PDH_HQUERY, PDH_MORE_DATA,
    };

    struct Pdh {
        query: PDH_HQUERY,
        proc_mem: PDH_HCOUNTER,
        adapter_mem: PDH_HCOUNTER,
    }
    // Handle PDH chỉ dùng sau Mutex, một luồng tại một thời điểm.
    unsafe impl Send for Pdh {}

    static PDH: Mutex<Option<Pdh>> = Mutex::new(None);

    fn wide(s: &str) -> Vec<u16> {
        s.encode_utf16().chain(std::iter::once(0)).collect()
    }

    unsafe fn wstr(p: *const u16) -> String {
        if p.is_null() {
            return String::new();
        }
        let mut n = 0usize;
        while *p.add(n) != 0 {
            n += 1;
        }
        String::from_utf16_lossy(std::slice::from_raw_parts(p, n))
    }

    fn open() -> Option<Pdh> {
        unsafe {
            let mut query: PDH_HQUERY = std::ptr::null_mut();
            if PdhOpenQueryW(std::ptr::null(), 0, &mut query) != 0 {
                return None;
            }
            let mut proc_mem: PDH_HCOUNTER = std::ptr::null_mut();
            let mut adapter_mem: PDH_HCOUNTER = std::ptr::null_mut();
            let p1 = wide(r"\GPU Process Memory(*)\Local Usage");
            let p2 = wide(r"\GPU Adapter Memory(*)\Dedicated Usage");
            if PdhAddEnglishCounterW(query, p1.as_ptr(), 0, &mut proc_mem) != 0
                || PdhAddEnglishCounterW(query, p2.as_ptr(), 0, &mut adapter_mem) != 0
            {
                return None;
            }
            Some(Pdh {
                query,
                proc_mem,
                adapter_mem,
            })
        }
    }

    /// Gọi 2 lần kiểu `PDH_MORE_DATA`; bỏ mẫu có `CStatus` khác VALID/NEW_DATA.
    fn read_array(counter: PDH_HCOUNTER) -> Option<Vec<(String, f64)>> {
        unsafe {
            let mut size: u32 = 0;
            let mut count: u32 = 0;
            let st = PdhGetFormattedCounterArrayW(
                counter,
                PDH_FMT_DOUBLE,
                &mut size,
                &mut count,
                std::ptr::null_mut(),
            );
            if st != PDH_MORE_DATA || size == 0 {
                return if st == 0 { Some(Vec::new()) } else { None };
            }
            // Bộ đệm căn 8 byte (item chứa f64)
            let mut buf: Vec<u64> = vec![0; (size as usize).div_ceil(8) + 1];
            let items = buf.as_mut_ptr() as *mut PDH_FMT_COUNTERVALUE_ITEM_W;
            let st = PdhGetFormattedCounterArrayW(counter, PDH_FMT_DOUBLE, &mut size, &mut count, items);
            if st != 0 {
                return None;
            }
            let mut out = Vec::with_capacity(count as usize);
            for i in 0..count as usize {
                let it = &*items.add(i);
                let cs = it.FmtValue.CStatus;
                if cs != PDH_CSTATUS_VALID_DATA && cs != PDH_CSTATUS_NEW_DATA {
                    continue;
                }
                out.push((wstr(it.szName), it.FmtValue.Anonymous.doubleValue));
            }
            Some(out)
        }
    }

    fn snapshot_processes() -> Vec<(u32, u32, String)> {
        let mut out = Vec::new();
        unsafe {
            let snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
            if snap == INVALID_HANDLE_VALUE || snap.is_null() {
                return out;
            }
            let mut pe: PROCESSENTRY32W = std::mem::zeroed();
            pe.dwSize = std::mem::size_of::<PROCESSENTRY32W>() as u32;
            if Process32FirstW(snap, &mut pe) != 0 {
                loop {
                    let n = pe.szExeFile.iter().position(|&c| c == 0).unwrap_or(pe.szExeFile.len());
                    out.push((
                        pe.th32ProcessID,
                        pe.th32ParentProcessID,
                        String::from_utf16_lossy(&pe.szExeFile[..n]),
                    ));
                    if Process32NextW(snap, &mut pe) == 0 {
                        break;
                    }
                }
            }
            CloseHandle(snap);
        }
        out
    }

    fn collect_once(pdh: &Pdh) -> Option<(Vec<(String, f64)>, Vec<(String, f64)>)> {
        unsafe {
            if PdhCollectQueryData(pdh.query) != 0 {
                return None;
            }
        }
        let procs = read_array(pdh.proc_mem)?;
        let adapters = read_array(pdh.adapter_mem)?;
        if procs.is_empty() || adapters.is_empty() {
            return None;
        }
        Some((procs, adapters))
    }

    pub fn sample(root: u32) -> AppVramSample {
        let Ok(mut guard) = PDH.lock() else {
            return AppVramSample::default();
        };
        if guard.is_none() {
            *guard = open();
        }
        let Some(pdh) = guard.as_ref() else {
            return AppVramSample::default();
        };
        // Lần đọc đầu có thể lỗi "sample not valid" → thử lại 1 lần
        let data = collect_once(pdh).or_else(|| {
            std::thread::sleep(std::time::Duration::from_millis(150));
            collect_once(pdh)
        });
        let Some((procs_mem, adapters)) = data else {
            return AppVramSample::default();
        };
        let Some(luid) = pick_dedicated_luid(&adapters) else {
            return AppVramSample::default();
        };
        let procs = snapshot_processes();
        aggregate(root, &procs, &luid, &procs_mem)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_valid_and_rejects_invalid_instance_names() {
        assert_eq!(
            parse_process_instance("pid_27680_luid_0x00000000_0x00010AF9_phys_0"),
            Some((27680, "luid_0x00000000_0x00010af9".to_string(), 0))
        );
        assert_eq!(
            parse_process_instance("pid_7_luid_0x00000000_0x00011c8d_phys_1"),
            Some((7, "luid_0x00000000_0x00011c8d".to_string(), 1))
        );
        for bad in [
            "",
            "pid__luid_0x0_0x1_phys_0",
            "pid_12_luid_0x00000000_phys_0",
            "pid_12_luid_00000000_0x00010af9_phys_0",
            "pid_12_luid_0x00000000_0x00010af9",
            "pid_12_luid_0x00000000_0x00010af9_phys_x",
            "luid_0x00000000_0x00010af9_phys_0",
            "pid_-3_luid_0x00000000_0x00010af9_phys_0",
        ] {
            assert_eq!(parse_process_instance(bad), None, "{bad}");
        }
        assert_eq!(
            parse_adapter_luid("luid_0x00000000_0x00010AF9_phys_0"),
            Some("luid_0x00000000_0x00010af9".to_string())
        );
    }

    #[test]
    fn descendants_handles_cycles_orphans_and_missing_root() {
        // 100 → 200 → 300 ; 200 → 400 ; 500 mồ côi (cha 999 không tồn tại) ; vòng 600 ↔ 700
        let procs = [(100, 1), (200, 100), (300, 200), (400, 200), (500, 999), (600, 700), (700, 600)];
        let d = descendants(100, &procs);
        assert_eq!(d, HashSet::from([100, 200, 300, 400]));
        assert_eq!(descendants(600, &procs), HashSet::from([600, 700]));
        assert!(descendants(42, &procs).is_empty());
        // PID tự làm cha của chính nó không gây lặp vô hạn
        assert_eq!(descendants(8, &[(8, 8)]), HashSet::from([8]));
    }

    #[test]
    fn picks_luid_with_largest_dedicated_usage() {
        let adapters = vec![
            ("luid_0x00000000_0x00011c8d_phys_0".to_string(), 300.0 * 1048576.0),
            ("luid_0x00000000_0x00010af9_phys_0".to_string(), 1900.0 * 1048576.0),
            ("garbage".to_string(), 9e12),
        ];
        assert_eq!(pick_dedicated_luid(&adapters).as_deref(), Some("luid_0x00000000_0x00010af9"));
        assert_eq!(pick_dedicated_luid(&[]), None);
    }

    #[test]
    fn aggregate_filters_luid_phys_tree_and_groups() {
        let mb = 1_048_576.0;
        let procs = vec![
            (10, 1, "akunarch.exe".to_string()),
            (11, 10, "msedgewebview2.exe".to_string()),
            (12, 11, "msedgewebview2.exe".to_string()),
            (13, 10, "python.exe".to_string()),
            (14, 10, "materialcraft-cli.exe".to_string()),
            (99, 1, "chrome.exe".to_string()),
        ];
        let l = "luid_0x00000000_0x00010af9";
        let samples = vec![
            (format!("pid_12_{l}_phys_0"), 400.0 * mb),
            (format!("pid_12_luid_0x00000000_0x00011c8d_phys_0"), 999.0 * mb), // iGPU → bỏ
            (format!("pid_11_{l}_phys_1"), 999.0 * mb),                        // phys_1 → bỏ
            (format!("pid_13_{l}_phys_0"), 2000.0 * mb),
            (format!("pid_14_{l}_phys_0"), 50.0 * mb),
            (format!("pid_10_{l}_phys_0"), 3.0 * mb),
            (format!("pid_99_{l}_phys_0"), 777.0 * mb), // ngoài cây → bỏ
        ];
        let s = aggregate(10, &procs, l, &samples);
        assert_eq!(
            s,
            AppVramSample {
                available: true,
                app_mb: 2453,
                webview_mb: 400,
                worker_mb: 2050,
                host_mb: 3
            }
        );
        assert_eq!(classify_exe("MsEdgeWebView2.exe"), ProcGroup::Webview);
        assert_eq!(classify_exe("Blender.exe"), ProcGroup::Worker);
        assert_eq!(classify_exe("akunarch.exe"), ProcGroup::Host);
    }

    #[cfg(windows)]
    #[test]
    fn live_sample_reads_pdh_on_this_machine() {
        // Tiến trình test không dùng GPU → app_mb thường = 0, nhưng PDH phải đọc được trên máy có GPU.
        let s = sample_app_vram_blocking();
        assert!(s.available, "PDH phải đọc được GPU Process Memory + chọn được LUID GPU rời");
        assert!(s.app_mb >= 0);
    }
}
