use crate::db::{akunarch_db_path, open_akunarch_db_at};
use chrono::Utc;
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::path::{Path, PathBuf};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Arc;
use tokio::sync::{Mutex, Notify};

pub const VALID_WORKER_KINDS: &[&str] = &[
    "blender",
    "comfyui",
    "worldgen",
    "hunyuan3d",
    "tts",
    "materialcraft",
    "effectcraft",
    "filmcraft",
    "toneforge",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VramTelemetry {
    pub gpu_available: bool,
    pub gpu_name: String,
    pub total_mb: i64,
    pub used_mb: i64,
    pub free_mb: i64,
    pub utilization_pct: i64,
    pub temperature_c: i64,
    pub vram_budget_mb: i64,
    pub within_16gb_budget: bool,
    /// Kế hoạch VRAM v2 · B2: VRAM của riêng cây tiến trình Akunarch (PDH, LUID GPU rời).
    #[serde(default)]
    pub app_used_mb: i64,
    #[serde(default)]
    pub webview_used_mb: i64,
    #[serde(default)]
    pub worker_used_mb: i64,
    /// `used_mb - app_used_mb` (Windows + app khác), không âm.
    #[serde(default)]
    pub other_system_mb: i64,
    #[serde(default)]
    pub app_vram_available: bool,
}

/// Gắn số đo PDH của app vào số đo `nvidia-smi` toàn máy.
pub fn merge_app_vram(mut t: VramTelemetry, s: &crate::vram_win32::AppVramSample) -> VramTelemetry {
    t.app_vram_available = s.available;
    t.app_used_mb = if s.available { s.app_mb } else { 0 };
    t.webview_used_mb = if s.available { s.webview_mb } else { 0 };
    t.worker_used_mb = if s.available { s.worker_mb } else { 0 };
    t.other_system_mb = (t.used_mb - t.app_used_mb).max(0);
    t
}

/// `nvidia-smi` toàn máy + PDH riêng app, đọc song song.
pub async fn probe_vram_with_app() -> VramTelemetry {
    let (t, s) = tokio::join!(probe_nvidia_vram_async(), crate::vram_win32::sample_app_vram_async());
    merge_app_vram(t, &s)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ToolProbeItem {
    pub id: String,
    pub label: String,
    pub path_or_url: String,
    pub available: bool,
    pub stage_note: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct HardwareStackReport {
    pub vram: VramTelemetry,
    pub tools: Vec<ToolProbeItem>,
    pub active_mutex_locked: bool,
    pub queued_count: i64,
    pub running_count: i64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GpuJobRow {
    pub id: i64,
    pub project_id: Option<i64>,
    pub worker_kind: String,
    pub payload: Value,
    pub status: String,
    pub progress_pct: f64,
    pub vram_peak_mb: i64,
    pub output_path: String,
    pub error_log: String,
    pub created_at: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EnqueueGpuJobInput {
    pub project_id: Option<i64>,
    pub worker_kind: String,
    #[serde(default)]
    pub payload: Value,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VramReleaseResult {
    pub comfyui_reachable: bool,
    pub unloaded_models: bool,
    pub message: String,
    pub vram_after: VramTelemetry,
}

/// Trả `true` nếu đã báo được cho UI.
pub type JobStartNotifier = Box<dyn Fn(Value) -> bool + Send + Sync>;

/// Đỉnh VRAM trong lúc job chạy: toàn máy (`nvidia-smi`) và nhóm worker của app (PDH).
pub struct VramPeak {
    machine: std::sync::atomic::AtomicI64,
    worker: std::sync::atomic::AtomicI64,
}

impl VramPeak {
    pub fn new(machine_mb: i64, worker_mb: i64) -> Self {
        Self {
            machine: std::sync::atomic::AtomicI64::new(machine_mb),
            worker: std::sync::atomic::AtomicI64::new(worker_mb),
        }
    }
    pub fn observe(&self, t: &VramTelemetry) {
        if t.gpu_available {
            self.machine.fetch_max(t.used_mb, Ordering::SeqCst);
        }
        if t.app_vram_available {
            self.worker.fetch_max(t.worker_used_mb, Ordering::SeqCst);
        }
    }
    pub fn machine_mb(&self) -> i64 {
        self.machine.load(Ordering::SeqCst)
    }
    pub fn worker_mb(&self) -> i64 {
        self.worker.load(Ordering::SeqCst)
    }
}

/// Single-Mutex GPU Supervisor (`Zero-OOM Architecture` for `RTX 4080 16GB VRAM`).
/// Guarantees at most ONE heavy GPU job runs at any given moment across the entire Studio,
/// automatically flushing ComfyUI VRAM (`POST /free`) when switching heavy GPU workers.
#[derive(Clone)]
pub struct GpuJobQueue {
    db_path: PathBuf,
    gpu_mutex: Arc<Mutex<Option<String>>>,
    wakeup: Arc<Notify>,
    active_jobs_counter: Arc<AtomicUsize>,
    /// B2: báo UI (lib.rs gắn `emit("akunarch://gpu-job-starting")`) nhường VRAM WebGL trước job GPU nặng.
    /// Callback thuần thay vì `tauri::AppHandle` để exe test không kéo DLL giao diện của tauri.
    job_start_notifier: Arc<std::sync::OnceLock<JobStartNotifier>>,
}

impl GpuJobQueue {
    pub fn new(db_path: PathBuf) -> Self {
        // Recover any orphaned 'running' jobs from a previous crash back to 'failed' cleanly
        if let Ok(conn) = open_akunarch_db_at(&db_path) {
            let now = Utc::now().to_rfc3339();
            let _ = conn.execute(
                "UPDATE gpu_jobs
                 SET status = 'failed',
                     error_log = 'Tiến trình trước dừng đột ngột; đã thu hồi khóa GPU an toàn.',
                     updated_at = ?1
                 WHERE status = 'running'",
                params![now],
            );
        }

        let queue = Self {
            db_path,
            gpu_mutex: Arc::new(Mutex::new(None)),
            wakeup: Arc::new(Notify::new()),
            active_jobs_counter: Arc::new(AtomicUsize::new(0)),
            job_start_notifier: Arc::new(std::sync::OnceLock::new()),
        };
        queue.spawn_worker_loop();
        queue
    }

    pub fn default_live() -> Self {
        Self::new(akunarch_db_path())
    }

    pub fn set_job_start_notifier(&self, notify: JobStartNotifier) {
        let _ = self.job_start_notifier.set(notify);
    }

    pub fn active_concurrent_count(&self) -> usize {
        self.active_jobs_counter.load(Ordering::SeqCst)
    }

    fn spawn_worker_loop(&self) {
        let this = self.clone();
        tauri::async_runtime::spawn(async move {
            loop {
                let processed_one = this.try_process_next_queued_job().await;
                if !processed_one {
                    this.wakeup.notified().await;
                }
            }
        });
    }

    pub fn enqueue(&self, input: EnqueueGpuJobInput) -> Result<GpuJobRow, String> {
        let worker_kind = input.worker_kind.trim().to_ascii_lowercase();
        if !VALID_WORKER_KINDS.contains(&worker_kind.as_str()) {
            return Err(format!(
                "Worker '{}' không hợp lệ. Chỉ chấp nhận: {}",
                input.worker_kind,
                VALID_WORKER_KINDS.join(", ")
            ));
        }
        let conn = open_akunarch_db_at(&self.db_path)?;
        let now = Utc::now().to_rfc3339();
        let payload_str = serde_json::to_string(&input.payload).unwrap_or_else(|_| "{}".to_string());

        conn.execute(
            "INSERT INTO gpu_jobs (
                project_id, worker_kind, payload_json, status, progress_pct,
                vram_peak_mb, output_path, error_log, created_at, updated_at
             )
             VALUES (?1, ?2, ?3, 'queued', 0.0, 0, '', '', ?4, ?4)",
            params![input.project_id, worker_kind, payload_str, now],
        )
        .map_err(|e| format!("Không thêm được tác vụ vào hàng đợi gpu_jobs: {e}"))?;

        let job_id = conn.last_insert_rowid();
        let row = get_gpu_job_by_id(&conn, job_id)?;
        self.wakeup.notify_one();
        Ok(row)
    }

    pub fn cancel_queued(&self, job_id: i64) -> Result<GpuJobRow, String> {
        let conn = open_akunarch_db_at(&self.db_path)?;
        let now = Utc::now().to_rfc3339();
        let changed = conn
            .execute(
                "UPDATE gpu_jobs
                 SET status = 'cancelled', updated_at = ?2
                 WHERE id = ?1 AND status = 'queued'",
                params![job_id, now],
            )
            .map_err(|e| format!("Lỗi hủy tác vụ #{job_id}: {e}"))?;
        if changed == 0 {
            return Err(format!(
                "Tác vụ #{job_id} không còn ở trạng thái 'queued' nên không thể hủy."
            ));
        }
        get_gpu_job_by_id(&conn, job_id)
    }

    pub fn list_jobs(&self, limit: usize) -> Result<Vec<GpuJobRow>, String> {
        let conn = open_akunarch_db_at(&self.db_path)?;
        list_gpu_jobs(&conn, limit)
    }

    /// Acquires the single GPU supervisor mutex, guarantees exclusive execution,
    /// switches VRAM cleanly when changing heavy worker families, and updates `gpu_jobs`.
    pub async fn try_process_next_queued_job(&self) -> bool {
        let mut last_worker_guard = self.gpu_mutex.lock().await;

        let next_job = {
            let Ok(conn) = open_akunarch_db_at(&self.db_path) else {
                return false;
            };
            let Ok(mut stmt) = conn.prepare(
                "SELECT id, project_id, worker_kind, payload_json
                 FROM gpu_jobs
                 WHERE status = 'queued'
                 ORDER BY id ASC
                 LIMIT 1",
            ) else {
                return false;
            };
            stmt.query_row([], |r| {
                let id: i64 = r.get(0)?;
                let project_id: Option<i64> = r.get(1)?;
                let worker_kind: String = r.get(2)?;
                let payload_str: String = r.get(3)?;
                let payload: Value = serde_json::from_str(&payload_str).unwrap_or_else(|_| json!({}));
                Ok((id, project_id, worker_kind, payload))
            })
            .ok()
        };

        let Some((job_id, project_id, worker_kind, mut payload)) = next_job else {
            return false;
        };

        // Automatically resolve `project_id` -> `project_slug` when UI dispatches via project_id
        if let Some(pid) = project_id {
            let needs_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .is_empty();
            if needs_slug {
                if let Ok(conn) = open_akunarch_db_at(&self.db_path) {
                    if let Ok(slug) = conn.query_row(
                        "SELECT slug FROM projects WHERE id = ?1",
                        params![pid],
                        |r| r.get::<_, String>(0),
                    ) {
                        if let Some(obj) = payload.as_object_mut() {
                            obj.insert("project_slug".to_string(), Value::String(slug));
                        }
                    }
                }
            }
        }

        // Mark running while still holding the exclusive GPU mutex
        if let Ok(conn) = open_akunarch_db_at(&self.db_path) {
            let now = Utc::now().to_rfc3339();
            let _ = conn.execute(
                "UPDATE gpu_jobs SET status = 'running', progress_pct = 15.0, updated_at = ?2 WHERE id = ?1",
                params![job_id, now],
            );
        }

        let prev_active = self.active_jobs_counter.fetch_add(1, Ordering::SeqCst);
        debug_assert_eq!(prev_active, 0, "Single-Mutex GPU Supervisor violated!");

        // Automatic VRAM flush before switching between heavy GPU models
        let is_heavy_gpu = matches!(
            worker_kind.as_str(),
            "comfyui" | "worldgen" | "hunyuan3d" | "blender" | "tts"
        );
        if is_heavy_gpu {
            if let Some(prev) = last_worker_guard.as_deref() {
                if prev != worker_kind {
                    let _ = release_comfyui_vram_inner("http://127.0.0.1:8188").await;
                }
            }
            *last_worker_guard = Some(worker_kind.clone());
            // B2: báo UI tháo sân khấu WebGL (nhường VRAM) rồi chờ một nhịp trước khi nạp model nặng
            if let Some(notify) = self.job_start_notifier.get() {
                if notify(json!({ "kind": worker_kind, "job_id": job_id })) {
                    tokio::time::sleep(std::time::Duration::from_millis(500)).await;
                }
            }
        }

        // B2 (sửa P2-2): lấy mẫu VRAM mỗi 1 s TRONG lúc job chạy → đỉnh thật của toàn máy và của nhóm worker
        let vram_before = probe_vram_with_app().await;
        let peak = VramPeak::new(vram_before.used_mb, vram_before.worker_used_mb);
        let sampler = async {
            loop {
                tokio::time::sleep(std::time::Duration::from_secs(1)).await;
                peak.observe(&probe_vram_with_app().await);
            }
        };
        let exec_result = tokio::select! {
            r = execute_worker_step(&self.db_path, &worker_kind, &payload) => r,
            _ = sampler => unreachable!(),
        };

        peak.observe(&probe_vram_with_app().await);
        let peak_mb = peak.machine_mb();
        if let Some(obj) = payload.as_object_mut() {
            obj.insert("worker_vram_peak_mb".to_string(), json!(peak.worker_mb()));
        }

        // Release VRAM after heavy step if requested or on completion of ComfyUI step
        if worker_kind == "comfyui"
            || payload
                .get("release_vram_after")
                .and_then(Value::as_bool)
                .unwrap_or(false)
        {
            let _ = release_comfyui_vram_inner("http://127.0.0.1:8188").await;
        }

        self.active_jobs_counter.fetch_sub(1, Ordering::SeqCst);

        if let Ok(output_path) = &exec_result {
            let mode = payload.get("mode").and_then(Value::as_str).unwrap_or("");
            let slug = payload.get("project_slug").and_then(Value::as_str).unwrap_or("");
            for (kind, next_payload) in follow_up_jobs(mode, output_path, slug) {
                let _ = self.enqueue(EnqueueGpuJobInput {
                    project_id,
                    worker_kind: kind,
                    payload: next_payload,
                });
            }
        }

        if let Ok(conn) = open_akunarch_db_at(&self.db_path) {
            let now = Utc::now().to_rfc3339();
            match exec_result {
                Ok(output_path) => {
                    let _ = conn.execute(
                        "UPDATE gpu_jobs
                         SET status = 'completed', progress_pct = 100.0, vram_peak_mb = ?2,
                             output_path = ?3, error_log = '', updated_at = ?4, payload_json = ?5
                         WHERE id = ?1",
                        params![job_id, peak_mb, output_path, now, payload.to_string()],
                    );
                }
                Err(err_msg) => {
                    let _ = conn.execute(
                        "UPDATE gpu_jobs
                         SET status = 'failed', vram_peak_mb = ?2, error_log = ?3, updated_at = ?4,
                             payload_json = ?5
                         WHERE id = ?1",
                        params![job_id, peak_mb, err_msg, now, payload.to_string()],
                    );
                }
            }
        }

        true
    }

    pub async fn hardware_report(&self) -> HardwareStackReport {
        let vram = probe_vram_with_app().await;
        let active_mutex_locked = self.gpu_mutex.try_lock().is_err();
        let db_path = self.db_path.clone();

        let (queued_count, running_count, tools) = tokio::task::spawn_blocking(move || {
            let (q_cnt, r_cnt) = open_akunarch_db_at(&db_path)
                .ok()
                .map(|conn| {
                    let q: i64 = conn
                        .query_row(
                            "SELECT COUNT(*) FROM gpu_jobs WHERE status = 'queued'",
                            [],
                            |r| r.get(0),
                        )
                        .unwrap_or(0);
                    let r: i64 = conn
                        .query_row(
                            "SELECT COUNT(*) FROM gpu_jobs WHERE status = 'running'",
                            [],
                            |r| r.get(0),
                        )
                        .unwrap_or(0);
                    (q, r)
                })
                .unwrap_or((0, 0));

            let tool_list = vec![
                probe_file_tool(
                    "python_cuda",
                    "Python 3.11 + PyTorch CUDA (.venv)",
                    r"E:\Tools-3D\.venv\Scripts\python.exe",
                    "Sẵn sàng cho Hunyuan3D-2 fp16 & WorldGen",
                ),
                probe_file_tool(
                    "blender_52",
                    "Blender 5.2 Headless Cycles OptiX",
                    r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
                    "Sẵn sàng lắp ráp & nướng AO .glb Draco",
                ),
                probe_file_tool(
                    "ffmpeg",
                    "FFmpeg Render Pipeline",
                    r"C:\Users\Admin\.local\bin\ffmpeg.exe",
                    "Sẵn sàng mã hóa Video Intro & Phim .mp4",
                ),
                probe_file_tool(
                    "cowriter_ro",
                    "Kho Thánh Tích Co-Writer (SQLITE_OPEN_READ_ONLY)",
                    crate::cowriter_bridge::cowriter_db_path()
                        .to_string_lossy()
                        .as_ref(),
                    "Khóa chỉ đọc 100% — bảo vệ tuyệt đối Co-Writer",
                ),
                probe_file_tool(
                    "tts_vieneu",
                    "VieNeu-TTS v3 Turbo (.venv + D:\\hf-cache)",
                    r"E:\Akunarch\repos\VieNeu-TTS\.venv\Scripts\python.exe",
                    "Sẵn sàng lồng tiếng Việt phương ngữ Nam Bộ offline",
                ),
                probe_file_tool(
                    "tts_omnivoice",
                    "OmniVoice Multilingual fp16 (.venv + D:\\hf-cache)",
                    r"E:\Akunarch\repos\OmniVoice\.venv\Scripts\python.exe",
                    "Sẵn sàng lồng tiếng Anh & đa ngôn ngữ 24kHz offline",
                ),
                probe_file_tool(
                    "sidecar_materialcraft",
                    "Sidecar: materialcraft-cli.exe (Zero-OOM)",
                    r"E:\Akunarch\bin\materialcraft-cli.exe",
                    "Sẵn sàng (CPU SIMD PBR 16-bit · materialcraft-cli)",
                ),
                probe_file_tool(
                    "sidecar_effectcraft",
                    "Sidecar: effectcraft-cli.exe (Zero-OOM)",
                    r"E:\Akunarch\bin\effectcraft-cli.exe",
                    "Sẵn sàng (Cổ ngữ SVG / VFX RGBA · effectcraft-cli 0.23)",
                ),
                probe_file_tool(
                    "sidecar_filmcraft",
                    "Sidecar: filmcraft-cli.exe (Zero-OOM)",
                    r"E:\Akunarch\bin\filmcraft-cli.exe",
                    "Sẵn sàng (Timeline đa lớp & Probe .mp4 · filmcraft-cli 0.17)",
                ),
                probe_file_tool(
                    "sidecar_audio",
                    "Sidecar: akunarch-audio-cli.exe (ToneForge DSP)",
                    r"E:\Akunarch\bin\akunarch-audio-cli.exe",
                    "Sẵn sàng (ToneForge DSP EQ + Limiter -14.0 LUFS)",
                ),
            ];
            (q_cnt, r_cnt, tool_list)
        })
        .await
        .unwrap_or((0, 0, Vec::new()));

        HardwareStackReport {
            vram,
            tools,
            active_mutex_locked,
            queued_count,
            running_count,
        }
    }
}

fn probe_file_tool(id: &str, label: &str, path: &str, note: &str) -> ToolProbeItem {
    ToolProbeItem {
        id: id.to_string(),
        label: label.to_string(),
        path_or_url: path.to_string(),
        available: Path::new(path).is_file(),
        stage_note: note.to_string(),
    }
}

async fn run_hidden_command(
    bin: &str,
    args: &[String],
    timeout_secs: u64,
    label: &str,
) -> Result<(String, String), String> {
    if !Path::new(bin).is_file() {
        return Err(format!("Không tìm thấy công cụ thực thi '{label}' tại '{bin}'."));
    }
    use tokio::io::AsyncReadExt;
    let mut cmd = tokio::process::Command::new(bin);
    cmd.args(args);
    cmd.kill_on_drop(true);
    cmd.stdout(std::process::Stdio::piped());
    cmd.stderr(std::process::Stdio::piped());
    #[cfg(windows)]
    {
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    let mut child = cmd.spawn().map_err(|e| format!("Lỗi khởi chạy {label}: {e}"))?;
    let pid = child.id();
    let mut so = child.stdout.take();
    let mut se = child.stderr.take();
    let rd_out = tokio::spawn(async move {
        let mut b = Vec::new();
        if let Some(s) = so.as_mut() {
            let _ = s.read_to_end(&mut b).await;
        }
        b
    });
    let rd_err = tokio::spawn(async move {
        let mut b = Vec::new();
        if let Some(s) = se.as_mut() {
            let _ = s.read_to_end(&mut b).await;
        }
        b
    });
    let status = tokio::select! {
        s = child.wait() => s.map_err(|e| format!("Lỗi chờ {label}: {e}"))?,
        _ = tokio::time::sleep(std::time::Duration::from_secs(timeout_secs)) => {
            // Giết CẢ CÂY trước (ktx.exe / node con cháu), rồi mới tới tiến trình con trực tiếp
            if let Some(p) = pid {
                kill_process_tree(p);
            }
            let _ = child.kill().await;
            rd_out.abort();
            rd_err.abort();
            return Err(format!("Quá thời gian {timeout_secs}s khi chạy {label}"));
        }
    };
    let stdout = String::from_utf8_lossy(&rd_out.await.unwrap_or_default()).to_string();
    let stderr = String::from_utf8_lossy(&rd_err.await.unwrap_or_default()).to_string();
    if !status.success() {
        let tail: Vec<&str> = stderr
            .lines()
            .chain(stdout.lines())
            .filter(|l| !l.trim().is_empty())
            .rev()
            .take(8)
            .collect();
        let summary = tail.into_iter().rev().collect::<Vec<_>>().join(" | ");
        return Err(format!(
            "{label} kết thúc với mã lỗi {:?}: {}",
            status.code(),
            if summary.is_empty() { "không có log chi tiết" } else { &summary }
        ));
    }
    Ok((stdout, stderr))
}

/// Giết cả cây tiến trình (con + cháu) — `kill_on_drop` của tokio chỉ giết con trực tiếp.
fn kill_process_tree(pid: u32) {
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        let _ = std::process::Command::new(r"C:\Windows\System32\taskkill.exe")
            .args(["/PID", &pid.to_string(), "/T", "/F"])
            .creation_flags(CREATE_NO_WINDOW)
            .output();
    }
    #[cfg(not(windows))]
    let _ = pid;
}

/// `run_hidden_command` kiểm `Path::is_file()` nên phải là đường dẫn tuyệt đối (tên trần "powershell" luôn trượt).
pub const POWERSHELL_EXE: &str = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe";

pub const COMFY_PYTHON: &str = r"E:\Akunarch\repos\ComfyUI\.venv\Scripts\python.exe";
const COMFY_RUNNER: &str = r"E:\Akunarch\bin\scripts\comfy_run_workflow.py";

/// Tham số cho `comfy_run_workflow.py` từ payload job `comfy_workflow`
/// (`workflow` bắt buộc; `image`, `image_node`, `set[]`, `prefix`, `timeout_sec`, `out_dir` tuỳ chọn).
pub fn comfy_workflow_args(payload: &Value, default_out_dir: &Path) -> Result<Vec<String>, String> {
    let s = |k: &str| payload.get(k).and_then(Value::as_str).map(str::trim).filter(|v| !v.is_empty());
    let workflow = s("workflow").ok_or("Job comfy_workflow thiếu 'workflow' (file .api.json).")?;
    let out_dir = s("out_dir").map(PathBuf::from).unwrap_or_else(|| default_out_dir.to_path_buf());
    let mut args = vec![
        COMFY_RUNNER.to_string(),
        "--workflow".to_string(),
        workflow.to_string(),
        "--out-dir".to_string(),
        out_dir.to_string_lossy().to_string(),
        "--timeout".to_string(),
        payload.get("timeout_sec").and_then(Value::as_u64).unwrap_or(1800).to_string(),
    ];
    if let Some(img) = s("image") {
        args.extend(["--image".to_string(), img.to_string()]);
        args.extend(["--image-node".to_string(), s("image_node").unwrap_or("122").to_string()]);
    }
    if let Some(prefix) = s("prefix") {
        args.extend(["--prefix".to_string(), prefix.to_string()]);
    }
    for item in payload.get("set").and_then(Value::as_array).into_iter().flatten() {
        if let Some(v) = item.as_str() {
            args.extend(["--set".to_string(), v.to_string()]);
        }
    }
    Ok(args)
}

/// P0: script và đầu ra video intro theo biến thể (`mechanism` = sa bàn cơ khí, mặc định = turntable bản thật).
pub fn intro_render_plan(variant: Option<&str>, project_folder: &Path, slug: &str) -> (String, PathBuf) {
    let cinema = project_folder.join("cinema");
    match variant.map(str::trim) {
        Some("mechanism") => (
            r"E:\Akunarch\bin\scripts\clockwork\render_mechanism_intro.py".to_string(),
            cinema.join(format!("{slug}_mechanism_intro.mp4")),
        ),
        _ => (
            r"E:\Akunarch\bin\scripts\render_clockwork_intro.py".to_string(),
            cinema.join(format!("{slug}_intro.mp4")),
        ),
    }
}

/// B3: bản runtime `<slug>.glb` dùng texture KTX2 (Blender không đọc được) → Blender dùng bản gốc JPEG
/// ở `clockwork/_master/<slug>.glb` nếu có.
pub fn blender_source_glb(glb_path: &str) -> String {
    let p = Path::new(glb_path);
    if let (Some(dir), Some(name)) = (p.parent(), p.file_name()) {
        let master = dir.join("_master").join(name);
        if master.is_file() {
            return master.to_string_lossy().to_string();
        }
    }
    glb_path.to_string()
}

/// C2: đường dẫn ảnh xem trước cạnh bản runtime: `clockwork/<stem>_preview_1080p.png`.
pub fn preview_card_path(runtime_glb: &str) -> PathBuf {
    let p = Path::new(runtime_glb);
    let stem = p.file_stem().and_then(|s| s.to_str()).unwrap_or("model");
    p.parent()
        .unwrap_or_else(|| Path::new("."))
        .join(format!("{stem}_preview_1080p.png"))
}

/// C2 (trường hợp c): ảnh thiếu, hoặc `.glb` mới hơn ảnh → cần render lại.
pub fn preview_card_needed(runtime_glb: &Path, preview_png: &Path) -> bool {
    let Ok(glb_meta) = std::fs::metadata(runtime_glb) else {
        return false;
    };
    let Ok(png_meta) = std::fs::metadata(preview_png) else {
        return true;
    };
    match (glb_meta.modified(), png_meta.modified()) {
        (Ok(g), Ok(p)) => g > p,
        _ => false,
    }
}

/// B3/C2: job tự xếp sau khi một job thành công — `.glb` mới xuất → nén KTX2 → ảnh xem trước 2D.
/// Không bao giờ tự gọi khi `rescan_projects` (chỉ theo kết quả job).
pub fn follow_up_jobs(mode: &str, output_path: &str, project_slug: &str) -> Vec<(String, Value)> {
    let slug = project_slug.trim();
    let is_glb = output_path.to_ascii_lowercase().ends_with(".glb");
    if slug.is_empty() || !is_glb {
        return Vec::new();
    }
    let is_mechanism = output_path.to_ascii_lowercase().ends_with("_mechanism.glb");
    // Anh chốt 2026-11-13: KTX2 (~40 phút CPU, mức 4) KHÔNG tự chạy sau mỗi lần dựng — chạy tay
    // (`gpu_enqueue {mode: optimize_glb_runtime}`) khi chốt bản cuối; trong lúc chỉnh chỉ render ảnh xem trước.
    let next_mode = match mode {
        "sculpt_concept" | "assemble_glb" => "render_preview_card",
        // ảnh xem trước 2D luôn là của bản thật — bản cơ khí không thay ảnh xem trước
        "optimize_glb_runtime" if !is_mechanism => "render_preview_card",
        _ => return Vec::new(),
    };
    vec![(
        "blender".to_string(),
        json!({ "mode": next_mode, "project_slug": slug, "glb_path": output_path, "auto_follow_up": true }),
    )]
}

fn bind_output_to_project(
    db_path: &Path,
    project_slug: &str,
    asset_kind: &str,
    output_path: &Path,
) {
    let Ok(conn) = open_akunarch_db_at(db_path) else {
        return;
    };
    let _ = crate::projects::import_external_file(
        &conn,
        project_slug,
        asset_kind,
        &output_path.to_string_lossy(),
        true,
    );
}

/// `glb_path` trong payload, hoặc `clockwork.glb_path` của `project_slug`; phải là file có thật.
fn resolve_project_glb(db_path: &Path, payload: &Value) -> Result<String, String> {
    let mut glb_path = payload
        .get("glb_path")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("")
        .to_string();
    let project_slug = payload
        .get("project_slug")
        .and_then(Value::as_str)
        .map(str::trim)
        .unwrap_or("");
    if glb_path.is_empty() && !project_slug.is_empty() {
        if let Ok(conn) = open_akunarch_db_at(db_path) {
            if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug) {
                glb_path = proj.manifest.clockwork.glb_path.unwrap_or_default();
            }
        }
    }
    if glb_path.is_empty() || !Path::new(&glb_path).is_file() {
        return Err(format!("Không tìm thấy tệp .glb thật: '{glb_path}'."));
    }
    Ok(glb_path)
}

async fn execute_worker_step(
    db_path: &Path,
    worker_kind: &str,
    payload: &Value,
) -> Result<String, String> {
    let mode = payload
        .get("mode")
        .and_then(Value::as_str)
        .unwrap_or("probe");

    if let Some(sim_ms) = payload.get("simulate_ms").and_then(Value::as_u64) {
        tokio::time::sleep(std::time::Duration::from_millis(sim_ms.min(5000))).await;
    }

    match mode {
        "probe" | "vram_check" => {
            let vram = probe_nvidia_vram_async().await;
            if !vram.within_16gb_budget {
                return Err(format!(
                    "Cảnh báo VRAM đang vượt ngưỡng an toàn: {} / {} MB",
                    vram.used_mb, vram.total_mb
                ));
            }
            Ok(format!(
                "verified://{worker_kind}?gpu={}&free_mb={}",
                vram.gpu_name.replace(' ', "_"),
                vram.free_mb
            ))
        }
        "sidecar_version" => {
            let bin = match worker_kind {
                "materialcraft" => r"E:\Akunarch\bin\materialcraft-cli.exe",
                "effectcraft" => r"E:\Akunarch\bin\effectcraft-cli.exe",
                "filmcraft" => r"E:\Akunarch\bin\filmcraft-cli.exe",
                "toneforge" => r"E:\Akunarch\bin\akunarch-audio-cli.exe",
                "blender" => r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
                _ => "",
            };
            if bin.is_empty() || !Path::new(bin).is_file() {
                return Err(format!(
                    "Binary cho worker '{worker_kind}' chưa có mặt tại '{bin}'."
                ));
            }
            let (stdout, _) =
                run_hidden_command(bin, &["--version".to_string()], 10, worker_kind).await?;
            let first_line = stdout.lines().next().unwrap_or("ok").trim().to_string();
            Ok(first_line)
        }
        "sculpt_concept" => {
            let py_bin = r"E:\Tools-3D\.venv\Scripts\python.exe";
            let script = r"E:\Akunarch\bin\scripts\sculpt_concept_to_glb.py";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");

            let mut concept_path = payload
                .get("concept_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut out_glb_path = payload
                .get("out_glb_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();

            if (!project_slug.is_empty()) && (concept_path.is_empty() || out_glb_path.is_empty()) {
                if let Ok(conn) = open_akunarch_db_at(db_path) {
                    if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug)
                    {
                        if concept_path.is_empty() {
                            concept_path = proj
                                .manifest
                                .local_image_path
                                .clone()
                                .or_else(|| proj.manifest.concept_paths.first().cloned())
                                .unwrap_or_default();
                        }
                        if out_glb_path.is_empty() {
                            out_glb_path = Path::new(&proj.folder_path)
                                .join("clockwork")
                                .join(format!("{}_sculpt.glb", proj.slug))
                                .to_string_lossy()
                                .to_string();
                        }
                    }
                }
            }
            if concept_path.is_empty() || !Path::new(&concept_path).is_file() {
                return Err(format!(
                    "Không tìm thấy ảnh Concept đầu vào để đúc 3D: '{concept_path}'. Hãy nhập ảnh Concept trước!"
                ));
            }
            if out_glb_path.is_empty() {
                return Err("Thiếu đường dẫn xuất out_glb_path cho Hunyuan3D-2.".to_string());
            }

            let octree_res = payload
                .get("octree_res")
                .and_then(Value::as_u64)
                .unwrap_or(288)
                .to_string();
            let steps = payload
                .get("steps")
                .and_then(Value::as_u64)
                .unwrap_or(35)
                .to_string();

            let args = vec![
                script.to_string(),
                "--concept".to_string(),
                concept_path,
                "--out".to_string(),
                out_glb_path.clone(),
                "--octree-res".to_string(),
                octree_res,
                "--steps".to_string(),
                steps,
            ];
            run_hidden_command(py_bin, &args, 900, "Hunyuan3D-2 Sculpt").await?;

            if !project_slug.is_empty() {
                let auto_assemble = payload
                    .get("auto_assemble")
                    .and_then(Value::as_bool)
                    .unwrap_or(false);
                if auto_assemble {
                    let blender_bin = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe";
                    let asm_script = r"E:\Akunarch\bin\scripts\assemble_clockwork_glb.py";
                    let final_glb = Path::new(&out_glb_path)
                        .parent()
                        .unwrap_or_else(|| Path::new("."))
                        .join(format!("{project_slug}.glb"))
                        .to_string_lossy()
                        .to_string();
                    let asm_args = vec![
                        "--background".to_string(),
                        "--python-exit-code".to_string(),
                        "1".to_string(),
                        "--python".to_string(),
                        asm_script.to_string(),
                        "--".to_string(),
                        "--slug".to_string(),
                        project_slug.to_string(),
                        "--hero-glb".to_string(),
                        out_glb_path.clone(),
                        "--out".to_string(),
                        final_glb.clone(),
                    ];
                    if run_hidden_command(blender_bin, &asm_args, 900, "Blender Auto-Assemble")
                        .await
                        .is_ok()
                    {
                        let db_clone = db_path.to_path_buf();
                        let slug_owned = project_slug.to_string();
                        let out_buf = PathBuf::from(&final_glb);
                        let _ = tokio::task::spawn_blocking(move || {
                            bind_output_to_project(&db_clone, &slug_owned, "glb", &out_buf);
                        })
                        .await;
                        return Ok(final_glb);
                    }
                }

                let db_clone = db_path.to_path_buf();
                let slug_owned = project_slug.to_string();
                let out_buf = PathBuf::from(&out_glb_path);
                let _ = tokio::task::spawn_blocking(move || {
                    bind_output_to_project(&db_clone, &slug_owned, "glb", &out_buf);
                })
                .await;
            }
            Ok(out_glb_path)
        }
        "sculpt_hero_parts" => {
            let py_bin = r"E:\Tools-3D\.venv\Scripts\python.exe";
            let hero_script = r"E:\Tools-3D\scripts\sculpt_hero_parts_gpu.py";
            if !Path::new(hero_script).is_file() {
                return Err(format!("Không tìm thấy {hero_script}"));
            }
            let mut args = vec![hero_script.to_string()];
            if let Some(filter) = payload
                .get("filter")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
            {
                args.push(filter.to_string());
            }
            run_hidden_command(py_bin, &args, 1800, "Hunyuan3D-2 sculpt_hero_parts_gpu.py").await?;
            Ok(r"E:\Tools-3D\ai_meshes".to_string())
        }
        "assemble_glb" => {
            let blender_bin = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe";
            let script = r"E:\Akunarch\bin\scripts\assemble_clockwork_glb.py";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");
            if project_slug.is_empty() {
                return Err("Thiếu project_slug để lắp ráp & nướng AO .glb.".to_string());
            }

            let mut hero_glb = payload
                .get("hero_glb_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut concept_path = payload
                .get("concept_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut out_glb = payload
                .get("out_glb_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();

            if let Ok(conn) = open_akunarch_db_at(db_path) {
                if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug) {
                    if concept_path.is_empty() {
                        concept_path = proj
                            .manifest
                            .local_image_path
                            .clone()
                            .or_else(|| proj.manifest.concept_paths.first().cloned())
                            .unwrap_or_default();
                    }
                    if out_glb.is_empty() {
                        out_glb = Path::new(&proj.folder_path)
                            .join("clockwork")
                            .join(format!("{}.glb", proj.slug))
                            .to_string_lossy()
                            .to_string();
                    }
                    if hero_glb.is_empty() {
                        let existing = proj.manifest.clockwork.glb_path.unwrap_or_default();
                        if !existing.is_empty() && !existing.eq_ignore_ascii_case(&out_glb) {
                            hero_glb = blender_source_glb(&existing);
                        }
                    }
                }
            }
            if out_glb.is_empty() {
                return Err("Không xác định được đường dẫn xuất .glb cho dự án.".to_string());
            }

            let mut args = vec![
                "--background".to_string(),
                "--python-exit-code".to_string(),
                "1".to_string(),
                "--python".to_string(),
                script.to_string(),
                "--".to_string(),
                "--slug".to_string(),
                project_slug.to_string(),
                "--out".to_string(),
                out_glb.clone(),
            ];
            if !hero_glb.is_empty() {
                args.push("--hero-glb".to_string());
                args.push(hero_glb);
            }
            if !concept_path.is_empty() {
                args.push("--concept".to_string());
                args.push(concept_path);
            }

            run_hidden_command(blender_bin, &args, 900, "Blender 5.2 Cycles OptiX Assemble").await?;

            let db_clone = db_path.to_path_buf();
            let slug_owned = project_slug.to_string();
            let out_buf = PathBuf::from(&out_glb);
            let _ = tokio::task::spawn_blocking(move || {
                bind_output_to_project(&db_clone, &slug_owned, "glb", &out_buf);
            })
            .await;

            Ok(out_glb)
        }
        "assemble_mechanism_glb" => {
            // P0: bản CƠ KHÍ — Blender đọc `<slug>.mechanism.json`, dựng bánh răng/khớp và gắn clip assemble/idle.
            let blender_bin = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe";
            let script = r"E:\Akunarch\bin\scripts\clockwork\assemble_mechanism_glb.py";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");
            if project_slug.is_empty() {
                return Err("Thiếu project_slug để dựng bản cơ khí.".to_string());
            }
            let conn = open_akunarch_db_at(db_path)?;
            let proj = crate::projects::get_project_by_slug(&conn, project_slug)?
                .ok_or_else(|| format!("Không có dự án '{project_slug}'."))?;
            drop(conn);
            let clock_dir = Path::new(&proj.folder_path).join("clockwork");
            let mech_path = payload
                .get("mech_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(PathBuf::from)
                .unwrap_or_else(|| clock_dir.join(format!("{}.mechanism.json", proj.slug)));
            if !mech_path.is_file() {
                return Err(format!("Không tìm thấy đặc tả cơ cấu: {}", mech_path.display()));
            }
            let out_glb = clock_dir.join(format!("{}_mechanism.glb", proj.slug));
            let args = vec![
                "--background".to_string(),
                "--python-exit-code".to_string(),
                "1".to_string(),
                "--python".to_string(),
                script.to_string(),
                "--".to_string(),
                "--slug".to_string(),
                proj.slug.clone(),
                "--mech".to_string(),
                mech_path.to_string_lossy().to_string(),
                "--out".to_string(),
                out_glb.to_string_lossy().to_string(),
            ];
            run_hidden_command(blender_bin, &args, 1200, "Blender 5.2 Clockwork Mechanism").await?;
            let db_clone = db_path.to_path_buf();
            let slug_owned = proj.slug.clone();
            let out_buf = out_glb.clone();
            let _ = tokio::task::spawn_blocking(move || {
                bind_output_to_project(&db_clone, &slug_owned, "mechanism", &out_buf);
            })
            .await;
            Ok(out_glb.to_string_lossy().to_string())
        }
        "comfy_workflow" => {
            // Workflow ComfyUI dạng API (FLUX, TRELLIS.2, H3…): runner tự bật máy chủ, chạy, chép đầu ra, xả VRAM rồi tắt.
            let project_slug = payload.get("project_slug").and_then(Value::as_str).map(str::trim).unwrap_or("");
            let mut default_out = PathBuf::from(r"E:\Akunarch\_archive\comfy");
            if !project_slug.is_empty() {
                let conn = open_akunarch_db_at(db_path)?;
                if let Some(proj) = crate::projects::get_project_by_slug(&conn, project_slug)? {
                    default_out = Path::new(&proj.folder_path).join("comfy");
                }
            }
            let args = comfy_workflow_args(payload, &default_out)?;
            let timeout = payload.get("timeout_sec").and_then(Value::as_u64).unwrap_or(1800) + 300;
            let (stdout, _) = run_hidden_command(COMFY_PYTHON, &args, timeout, "ComfyUI workflow").await?;
            stdout
                .lines()
                .rev()
                .find_map(|l| l.trim().strip_prefix("OUTPUT=").map(str::to_string))
                .ok_or_else(|| format!("ComfyUI chạy xong nhưng không báo file đầu ra:\n{stdout}"))
        }
        "render_intro_mp4" => {
            let blender_bin = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe";
            let variant = payload.get("variant").and_then(Value::as_str);
            let is_mechanism = variant.map(str::trim) == Some("mechanism");
            let mut script = intro_render_plan(variant, Path::new("."), "x").0;
            let mut bgm_path = String::new();
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");

            let mut glb_path = payload
                .get("glb_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut out_mp4 = payload
                .get("out_mp4_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();

            if !project_slug.is_empty() {
                if let Ok(conn) = open_akunarch_db_at(db_path) {
                    if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug)
                    {
                        let (plan_script, plan_out) =
                            intro_render_plan(variant, Path::new(&proj.folder_path), &proj.slug);
                        script = plan_script;
                        bgm_path = proj.manifest.bgm_audio_path.clone().unwrap_or_default();
                        if glb_path.is_empty() {
                            glb_path = if is_mechanism {
                                proj.manifest.clockwork.mechanism_glb_path.clone().unwrap_or_default()
                            } else {
                                proj.manifest.clockwork.glb_path.clone().unwrap_or_default()
                            };
                        }
                        if out_mp4.is_empty() {
                            out_mp4 = plan_out.to_string_lossy().to_string();
                        }
                    }
                }
            }
            if glb_path.is_empty() || !Path::new(&glb_path).is_file() {
                return Err(format!(
                    "Không tìm thấy tệp mô hình .glb thật để render Video Intro: '{glb_path}'."
                ));
            }
            if out_mp4.is_empty() {
                return Err("Thiếu đường dẫn xuất out_mp4_path.".to_string());
            }

            let frames = payload
                .get("frames")
                .and_then(Value::as_u64)
                .unwrap_or(36)
                .to_string();
            let width = payload
                .get("width")
                .and_then(Value::as_u64)
                .unwrap_or(1280)
                .to_string();
            let height = payload
                .get("height")
                .and_then(Value::as_u64)
                .unwrap_or(720)
                .to_string();

            let mut args = vec![
                "--background".to_string(),
                "--python-exit-code".to_string(),
                "1".to_string(),
                "--python".to_string(),
                script.to_string(),
                "--".to_string(),
                "--glb".to_string(),
                blender_source_glb(&glb_path),
                "--out".to_string(),
                out_mp4.clone(),
                "--frames".to_string(),
                frames,
                "--width".to_string(),
                width,
                "--height".to_string(),
                height,
            ];
            if is_mechanism && Path::new(&bgm_path).is_file() {
                args.push("--audio".to_string());
                args.push(bgm_path.clone());
            }
            let timeout = if is_mechanism { 3600 } else { 900 };
            run_hidden_command(blender_bin, &args, timeout, "Blender + FFmpeg Intro Render").await?;

            if !project_slug.is_empty() {
                let db_clone = db_path.to_path_buf();
                let slug_owned = project_slug.to_string();
                let out_buf = PathBuf::from(&out_mp4);
                let _ = tokio::task::spawn_blocking(move || {
                    bind_output_to_project(&db_clone, &slug_owned, "video", &out_buf);
                })
                .await;
            }
            Ok(out_mp4)
        }
        "optimize_glb_runtime" => {
            let glb_path = resolve_project_glb(db_path, payload)?;
            let script = r"E:\Akunarch\bin\scripts\optimize_glb_runtime.ps1";
            let args = vec![
                "-NoProfile".to_string(),
                "-ExecutionPolicy".to_string(),
                "Bypass".to_string(),
                "-File".to_string(),
                script.to_string(),
                "-Glb".to_string(),
                glb_path.clone(),
            ];
            // UASTC mức 4 với ~50 texture mất ~40 phút ở 2 job × 2 luồng (giới hạn nhiệt CPU) → hạn 90 phút
            run_hidden_command(POWERSHELL_EXE, &args, 5400, "KTX2 optimize_glb_runtime").await?;
            Ok(glb_path)
        }
        "render_preview_card" => {
            let glb_path = resolve_project_glb(db_path, payload)?;
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let out_png = preview_card_path(&glb_path);
            let blender_bin = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe";
            let script = r"E:\Akunarch\bin\scripts\render_glb_preview_card.py";
            let args = vec![
                "--background".to_string(),
                "--python-exit-code".to_string(),
                "1".to_string(),
                "--python".to_string(),
                script.to_string(),
                "--".to_string(),
                "--glb".to_string(),
                blender_source_glb(&glb_path),
                "--out".to_string(),
                out_png.to_string_lossy().to_string(),
            ];
            run_hidden_command(blender_bin, &args, 600, "Blender 5.2 Preview Card 1080p").await?;
            if !out_png.is_file() {
                return Err(format!("Blender không xuất được ảnh xem trước {}", out_png.display()));
            }
            if !project_slug.is_empty() {
                let db_clone = db_path.to_path_buf();
                let png = out_png.to_string_lossy().to_string();
                tokio::task::spawn_blocking(move || -> Result<(), String> {
                    let conn = open_akunarch_db_at(&db_clone)?;
                    let proj = crate::projects::get_project_by_slug(&conn, &project_slug)?
                        .ok_or_else(|| format!("Không tìm thấy dự án '{project_slug}'."))?;
                    let mut manifest = proj.manifest;
                    manifest.clockwork.preview_render_path = Some(png);
                    crate::projects::update_project_manifest(&conn, Some(&project_slug), manifest)?;
                    Ok(())
                })
                .await
                .map_err(|e| format!("Lỗi ghi preview_render_path: {e}"))??;
            }
            Ok(out_png.to_string_lossy().to_string())
        }
        "pbr_pack" => {
            let bin = r"E:\Akunarch\bin\materialcraft-cli.exe";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");
            let input_pkg = payload
                .get("input")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .unwrap_or("sample");
            let size = payload
                .get("size")
                .and_then(Value::as_u64)
                .unwrap_or(1024)
                .to_string();
            let depth = payload
                .get("depth")
                .and_then(Value::as_u64)
                .unwrap_or(16)
                .to_string();

            let out_dir = if !project_slug.is_empty() {
                if let Ok(conn) = open_akunarch_db_at(db_path) {
                    if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug)
                    {
                        Path::new(&proj.folder_path).join("clockwork").join("pbr_maps")
                    } else {
                        crate::db::akunarch_projects_root()
                            .join(project_slug)
                            .join("clockwork")
                            .join("pbr_maps")
                    }
                } else {
                    std::env::temp_dir().join("akunarch_materialcraft_out")
                }
            } else {
                std::env::temp_dir().join("akunarch_materialcraft_out")
            };
            std::fs::create_dir_all(&out_dir)
                .map_err(|e| format!("Không tạo được thư mục xuất PBR: {e}"))?;

            let out_dir_str = out_dir.to_string_lossy().to_string();
            let args = vec![
                "export".to_string(),
                input_pkg.to_string(),
                out_dir_str.clone(),
                "--format".to_string(),
                "png".to_string(),
                "--depth".to_string(),
                depth,
                "--size".to_string(),
                size,
            ];
            run_hidden_command(bin, &args, 180, "materialcraft-cli export").await?;
            Ok(out_dir_str)
        }
        "image_to_splat" => {
            let py_bin = r"E:\Tools-3D\.venv\Scripts\python.exe";
            let script = r"E:\Akunarch\bin\scripts\convert_image_to_splat_ply.py";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");

            let mut input_img = payload
                .get("input_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut out_ply = payload
                .get("out_ply_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut depth_png = String::new();

            if !project_slug.is_empty() {
                if let Ok(conn) = open_akunarch_db_at(db_path) {
                    if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug)
                    {
                        if input_img.is_empty() {
                            input_img = proj
                                .manifest
                                .local_image_path
                                .clone()
                                .or_else(|| proj.manifest.concept_paths.first().cloned())
                                .unwrap_or_default();
                        }
                        let chunks_dir = Path::new(&proj.folder_path).join("chunks");
                        let _ = std::fs::create_dir_all(&chunks_dir);
                        if out_ply.is_empty() {
                            out_ply = chunks_dir
                                .join(format!("{}_splat.ply", proj.slug))
                                .to_string_lossy()
                                .to_string();
                        }
                        depth_png = chunks_dir
                            .join(format!("{}_splat_depth.png", proj.slug))
                            .to_string_lossy()
                            .to_string();
                    }
                }
            }

            if input_img.is_empty() || !Path::new(&input_img).is_file() {
                return Err(format!(
                    "Không tìm thấy ảnh phong cảnh đầu vào để dựng Gaussian Splat: '{input_img}'."
                ));
            }
            if out_ply.is_empty() {
                return Err("Thiếu đường dẫn xuất out_ply_path cho Gaussian Splat.".to_string());
            }

            let max_splats = payload
                .get("max_splats")
                .and_then(Value::as_u64)
                .unwrap_or(140_000)
                .to_string();
            let world_span = payload
                .get("world_span")
                .and_then(Value::as_f64)
                .unwrap_or(96.0)
                .to_string();
            let relief_scale = payload
                .get("relief_scale")
                .and_then(Value::as_f64)
                .unwrap_or(26.0)
                .to_string();

            let mut args = vec![
                script.to_string(),
                "--input".to_string(),
                input_img,
                "--output".to_string(),
                out_ply.clone(),
                "--max-splats".to_string(),
                max_splats,
                "--world-span".to_string(),
                world_span,
                "--relief-scale".to_string(),
                relief_scale,
            ];
            if !depth_png.is_empty() {
                args.push("--depth-png".to_string());
                args.push(depth_png);
            }

            run_hidden_command(py_bin, &args, 300, "GPU Image-to-Gaussian-Splat (.ply)").await?;

            if !project_slug.is_empty() {
                let db_clone = db_path.to_path_buf();
                let slug_owned = project_slug.to_string();
                let ply_owned = out_ply.clone();
                let _ = tokio::task::spawn_blocking(move || {
                    if let Ok(conn) = open_akunarch_db_at(&db_clone) {
                        if let Ok(Some(mut proj)) =
                            crate::projects::get_project_by_slug(&conn, &slug_owned)
                        {
                            proj.manifest.chunks.splat_path = Some(ply_owned);
                            let _ = crate::projects::update_project_manifest(
                                &conn,
                                Some(&slug_owned),
                                proj.manifest,
                            );
                        }
                    }
                })
                .await;
            }
            Ok(out_ply)
        }
        "tts_synthesize" => {
            let py_bin = r"E:\Tools-3D\.venv\Scripts\python.exe";
            let script = r"E:\Akunarch\bin\scripts\synthesize_local_tts.py";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");
            let single_text = payload
                .get("text")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");
            let batch_episode = payload
                .get("batch_episode")
                .and_then(Value::as_bool)
                .unwrap_or(single_text.is_empty());

            if batch_episode {
                if project_slug.is_empty() {
                    return Err(
                        "Thiếu project_slug để lồng tiếng hàng loạt cho kịch bản Visual Novel."
                            .to_string(),
                    );
                }
                let db_clone = db_path.to_path_buf();
                let slug_owned = project_slug.to_string();
                let (episode, voices_dir) = tokio::task::spawn_blocking(move || {
                    let conn = open_akunarch_db_at(&db_clone)?;
                    let proj = crate::projects::get_project_by_slug(&conn, &slug_owned)?
                        .ok_or_else(|| format!("Không tìm thấy dự án '{slug_owned}'."))?;
                    let ep = crate::workbenches::load_or_init_vn_episode(&conn, &slug_owned)?;
                    let vdir = Path::new(&proj.folder_path).join("stage_vn").join("voices");
                    std::fs::create_dir_all(&vdir).map_err(|e| e.to_string())?;
                    Ok::<_, String>((ep, vdir))
                })
                .await
                .map_err(|e| e.to_string())??;

                let mut batch_items = Vec::new();
                for node in &episode.nodes {
                    let cast_entry = episode.cast.iter().find(|c| c.id == node.speaker_id);
                    let voice_vi = cast_entry
                        .map(|c| c.voice_vi.as_str())
                        .unwrap_or("Thùy Dung");
                    let voice_en = cast_entry.map(|c| c.voice_en.as_str()).unwrap_or("female");

                    if !node.text_vi.trim().is_empty() {
                        let out_vi = voices_dir.join(format!("{}_vi.wav", node.id));
                        batch_items.push(json!({
                            "id": format!("{}:vi", node.id),
                            "lang": "vi",
                            "text": node.text_vi.trim(),
                            "voice": voice_vi,
                            "out_path": out_vi.to_string_lossy().to_string(),
                        }));
                    }
                    if !node.text_en.trim().is_empty() {
                        let out_en = voices_dir.join(format!("{}_en.wav", node.id));
                        batch_items.push(json!({
                            "id": format!("{}:en", node.id),
                            "lang": "en",
                            "text": node.text_en.trim(),
                            "voice": voice_en,
                            "out_path": out_en.to_string_lossy().to_string(),
                        }));
                    }
                }

                if batch_items.is_empty() {
                    return Err("Kịch bản VN chưa có lời thoại nào để lồng tiếng.".to_string());
                }

                let tmp_batch = voices_dir.join("_tts_batch_job.json");
                let tmp_report = voices_dir.join("_tts_batch_report.json");
                std::fs::write(
                    &tmp_batch,
                    serde_json::to_string_pretty(&batch_items).unwrap_or_else(|_| "[]".into()),
                )
                .map_err(|e| e.to_string())?;

                let args = vec![
                    script.to_string(),
                    "--batch-json".to_string(),
                    tmp_batch.to_string_lossy().to_string(),
                    "--report-json".to_string(),
                    tmp_report.to_string_lossy().to_string(),
                ];
                let res = run_hidden_command(
                    py_bin,
                    &args,
                    900,
                    "VieNeu-TTS + OmniVoice Batch Synthesis",
                )
                .await;
                let _ = std::fs::remove_file(&tmp_batch);
                let _ = std::fs::remove_file(&tmp_report);
                res?;

                let db_save = db_path.to_path_buf();
                let slug_save = project_slug.to_string();
                let vdir_save = voices_dir.clone();
                let _ = tokio::task::spawn_blocking(move || {
                    if let Ok(conn) = open_akunarch_db_at(&db_save) {
                        if let Ok(mut ep) =
                            crate::workbenches::load_or_init_vn_episode(&conn, &slug_save)
                        {
                            for node in &mut ep.nodes {
                                let p_vi = vdir_save.join(format!("{}_vi.wav", node.id));
                                if p_vi.is_file() {
                                    node.voice_vi_path = Some(p_vi.to_string_lossy().to_string());
                                }
                                let p_en = vdir_save.join(format!("{}_en.wav", node.id));
                                if p_en.is_file() {
                                    node.voice_en_path = Some(p_en.to_string_lossy().to_string());
                                }
                            }
                            let _ = crate::workbenches::save_vn_episode(&conn, &slug_save, ep);
                        }
                    }
                })
                .await;

                Ok(voices_dir.to_string_lossy().to_string())
            } else {
                let lang = payload
                    .get("lang")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|s| *s == "en" || *s == "vi")
                    .unwrap_or("vi");
                let node_id = payload
                    .get("node_id")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .filter(|s| !s.is_empty())
                    .unwrap_or("line");
                let voice = payload
                    .get("voice")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .unwrap_or("");
                let ref_audio = payload
                    .get("ref_audio")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .unwrap_or("");

                let mut out_wav = payload
                    .get("out_wav_path")
                    .and_then(Value::as_str)
                    .map(str::trim)
                    .unwrap_or("")
                    .to_string();

                if out_wav.is_empty() && !project_slug.is_empty() {
                    if let Ok(conn) = open_akunarch_db_at(db_path) {
                        if let Ok(Some(proj)) =
                            crate::projects::get_project_by_slug(&conn, project_slug)
                        {
                            let vdir = Path::new(&proj.folder_path).join("stage_vn").join("voices");
                            let _ = std::fs::create_dir_all(&vdir);
                            out_wav = vdir
                                .join(format!("{node_id}_{lang}.wav"))
                                .to_string_lossy()
                                .to_string();
                        }
                    }
                }
                if out_wav.is_empty() {
                    out_wav = std::env::temp_dir()
                        .join(format!("akunarch_tts_{node_id}_{lang}.wav"))
                        .to_string_lossy()
                        .to_string();
                }

                let mut args = vec![
                    script.to_string(),
                    "--lang".to_string(),
                    lang.to_string(),
                    "--text".to_string(),
                    single_text.to_string(),
                    "--out".to_string(),
                    out_wav.clone(),
                ];
                if !voice.is_empty() {
                    args.push("--voice".to_string());
                    args.push(voice.to_string());
                }
                if !ref_audio.is_empty() {
                    args.push("--ref-audio".to_string());
                    args.push(ref_audio.to_string());
                }

                run_hidden_command(py_bin, &args, 300, "Local TTS Single Line").await?;

                if !project_slug.is_empty() {
                    let db_save = db_path.to_path_buf();
                    let slug_save = project_slug.to_string();
                    let nid_owned = node_id.to_string();
                    let lang_owned = lang.to_string();
                    let wav_owned = out_wav.clone();
                    let _ = tokio::task::spawn_blocking(move || {
                        if let Ok(conn) = open_akunarch_db_at(&db_save) {
                            if let Ok(mut ep) =
                                crate::workbenches::load_or_init_vn_episode(&conn, &slug_save)
                            {
                                if let Some(node) = ep.nodes.iter_mut().find(|n| n.id == nid_owned)
                                {
                                    if lang_owned == "en" {
                                        node.voice_en_path = Some(wav_owned);
                                    } else {
                                        node.voice_vi_path = Some(wav_owned);
                                    }
                                    let _ =
                                        crate::workbenches::save_vn_episode(&conn, &slug_save, ep);
                                }
                            }
                        }
                    })
                    .await;
                }

                Ok(out_wav)
            }
        }
        "effectcraft_overlay" => {
            let bin = r"E:\Akunarch\bin\effectcraft-cli.exe";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");
            let time_sec = payload
                .get("time_sec")
                .and_then(Value::as_f64)
                .unwrap_or(1.2)
                .to_string();

            let out_png = if !project_slug.is_empty() {
                if let Ok(conn) = open_akunarch_db_at(db_path) {
                    if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug)
                    {
                        let dir = Path::new(&proj.folder_path).join("cinema");
                        let _ = std::fs::create_dir_all(&dir);
                        dir.join(format!("{}_vfx_overlay.png", proj.slug))
                    } else {
                        std::env::temp_dir().join("akunarch_vfx_overlay.png")
                    }
                } else {
                    std::env::temp_dir().join("akunarch_vfx_overlay.png")
                }
            } else {
                std::env::temp_dir().join("akunarch_vfx_overlay.png")
            };
            let out_png_str = out_png.to_string_lossy().to_string();
            let args = vec![
                "--demo".to_string(),
                "render-frame".to_string(),
                "--time".to_string(),
                time_sec,
                "--transparent".to_string(),
                "--out".to_string(),
                out_png_str.clone(),
                "--json".to_string(),
            ];
            run_hidden_command(bin, &args, 120, "effectcraft-cli render-frame").await?;

            if !project_slug.is_empty() {
                let db_save = db_path.to_path_buf();
                let slug_save = project_slug.to_string();
                let out_owned = out_png_str.clone();
                let _ = tokio::task::spawn_blocking(move || {
                    if let Ok(conn) = open_akunarch_db_at(&db_save) {
                        if let Ok(Some(mut proj)) =
                            crate::projects::get_project_by_slug(&conn, &slug_save)
                        {
                            proj.manifest.cinema.vfx_overlay_path = Some(out_owned);
                            let _ = crate::projects::update_project_manifest(
                                &conn,
                                Some(&slug_save),
                                proj.manifest,
                            );
                        }
                    }
                })
                .await;
            }
            Ok(out_png_str)
        }
        "toneforge_master" => {
            let bin = r"E:\Akunarch\bin\akunarch-audio-cli.exe";
            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");

            let mut in_audio = payload
                .get("in_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut bgm_audio = payload
                .get("bgm_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut out_wav = payload
                .get("out_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("")
                .to_string();
            let mut duration_opt = payload.get("duration_sec").and_then(Value::as_f64);

            if !project_slug.is_empty() {
                if let Ok(conn) = open_akunarch_db_at(db_path) {
                    if let Ok(Some(proj)) = crate::projects::get_project_by_slug(&conn, project_slug)
                    {
                        let cdir = Path::new(&proj.folder_path).join("cinema");
                        let _ = std::fs::create_dir_all(&cdir);
                        if in_audio.is_empty() {
                            in_audio = proj
                                .manifest
                                .cinema
                                .voice_track_path
                                .clone()
                                .or_else(|| proj.manifest.cinema.bgm_track_path.clone())
                                .or_else(|| proj.manifest.bgm_audio_path.clone())
                                .unwrap_or_default();
                        }
                        if bgm_audio.is_empty() {
                            let cand = proj
                                .manifest
                                .cinema
                                .bgm_track_path
                                .clone()
                                .or_else(|| proj.manifest.bgm_audio_path.clone())
                                .unwrap_or_default();
                            if !cand.is_empty() && !cand.eq_ignore_ascii_case(&in_audio) {
                                bgm_audio = cand;
                            }
                        }
                        if out_wav.is_empty() {
                            out_wav = cdir
                                .join(format!("{}_master_14lufs.wav", proj.slug))
                                .to_string_lossy()
                                .to_string();
                        }
                        if duration_opt.is_none() {
                            duration_opt = Some(proj.manifest.cinema.duration_sec);
                        }
                        if in_audio.is_empty() || !Path::new(&in_audio).is_file() {
                            let synth_pad = cdir.join("_harmonic_pad_seed.wav");
                            synthesize_warm_ambient_pad_wav(
                                &synth_pad,
                                duration_opt.unwrap_or(6.0).max(2.5),
                            )?;
                            in_audio = synth_pad.to_string_lossy().to_string();
                        }
                    }
                }
            }

            if in_audio.is_empty() || !Path::new(&in_audio).is_file() {
                return Err(format!(
                    "Không tìm thấy tệp âm thanh đầu vào cho ToneForge Mastering: '{in_audio}'."
                ));
            }
            if out_wav.is_empty() {
                out_wav = std::env::temp_dir()
                    .join("akunarch_master_14lufs.wav")
                    .to_string_lossy()
                    .to_string();
            }

            let mut args = vec![
                "master".to_string(),
                "--in".to_string(),
                in_audio,
                "--out".to_string(),
                out_wav.clone(),
                "--target-lufs".to_string(),
                "-14.0".to_string(),
                "--ceiling-dbtp".to_string(),
                "-1.0".to_string(),
                "--json".to_string(),
            ];
            if !bgm_audio.is_empty() && Path::new(&bgm_audio).is_file() {
                args.push("--bgm".to_string());
                args.push(bgm_audio);
            }
            if let Some(d) = duration_opt.filter(|v| *v >= 1.0) {
                args.push("--duration-sec".to_string());
                args.push(format!("{d:.2}"));
            }

            let (stdout, _) =
                run_hidden_command(bin, &args, 180, "akunarch-audio-cli -14 LUFS Master").await?;
            let parsed_json: Value =
                serde_json::from_str(stdout.trim()).unwrap_or_else(|_| json!({}));
            let lufs = parsed_json
                .get("output_integrated_lufs")
                .and_then(Value::as_f64)
                .unwrap_or(-14.0);
            let dbtp = parsed_json
                .get("output_true_peak_dbtp")
                .and_then(Value::as_f64)
                .unwrap_or(-1.2);

            if !project_slug.is_empty() {
                let db_save = db_path.to_path_buf();
                let slug_save = project_slug.to_string();
                let out_owned = out_wav.clone();
                let _ = tokio::task::spawn_blocking(move || {
                    if let Ok(conn) = open_akunarch_db_at(&db_save) {
                        if let Ok(Some(mut proj)) =
                            crate::projects::get_project_by_slug(&conn, &slug_save)
                        {
                            proj.manifest.cinema.mastered_audio_path = Some(out_owned);
                            proj.manifest.cinema.mastered_lufs = Some(lufs as f32);
                            proj.manifest.cinema.mastered_true_peak_dbtp = Some(dbtp as f32);
                            let _ = crate::projects::update_project_manifest(
                                &conn,
                                Some(&slug_save),
                                proj.manifest,
                            );
                        }
                    }
                })
                .await;
            }
            Ok(out_wav)
        }
        "cinema_render_pipeline" => {
            let blender_bin = r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe";
            let seq_script = r"E:\Akunarch\bin\scripts\render_cinema_sequence.py";
            let effect_bin = r"E:\Akunarch\bin\effectcraft-cli.exe";
            let audio_bin = r"E:\Akunarch\bin\akunarch-audio-cli.exe";
            let film_bin = r"E:\Akunarch\bin\filmcraft-cli.exe";
            let ffmpeg_bin = r"C:\Users\Admin\.local\bin\ffmpeg.exe";

            let project_slug = payload
                .get("project_slug")
                .and_then(Value::as_str)
                .map(str::trim)
                .unwrap_or("");
            if project_slug.is_empty() {
                return Err("Thiếu project_slug cho dây chuyền dựng phim Điện Ảnh VFX.".to_string());
            }

            let db_load = db_path.to_path_buf();
            let slug_load = project_slug.to_string();
            let proj = tokio::task::spawn_blocking(move || {
                let conn = open_akunarch_db_at(&db_load)?;
                crate::projects::get_project_by_slug(&conn, &slug_load)?
                    .ok_or_else(|| format!("Không tìm thấy dự án '{slug_load}'."))
            })
            .await
            .map_err(|e| e.to_string())??;

            let cinema_dir = Path::new(&proj.folder_path).join("cinema");
            std::fs::create_dir_all(&cinema_dir).map_err(|e| e.to_string())?;

            let duration_sec = payload
                .get("duration_sec")
                .and_then(Value::as_f64)
                .unwrap_or(proj.manifest.cinema.duration_sec)
                .clamp(2.0, 24.0);
            let fps = payload
                .get("fps")
                .and_then(Value::as_u64)
                .unwrap_or(proj.manifest.cinema.fps as u64)
                .clamp(12, 60);
            let width = payload.get("width").and_then(Value::as_u64).unwrap_or(1280);
            let height = payload.get("height").and_then(Value::as_u64).unwrap_or(720);
            let mood = payload
                .get("mood")
                .and_then(Value::as_str)
                .unwrap_or("golden_hour");

            let glb_source = payload
                .get("glb_path")
                .and_then(Value::as_str)
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(str::to_string)
                .or_else(|| proj.manifest.cinema.source_glb_path.clone())
                .or_else(|| proj.manifest.clockwork.glb_path.clone())
                .map(|p| blender_source_glb(&p))
                .unwrap_or_default();

            let plate_source = proj
                .manifest
                .manga_plates
                .first()
                .map(|p| p.beauty_path.clone())
                .or_else(|| proj.manifest.local_image_path.clone())
                .or_else(|| proj.manifest.concept_paths.first().cloned())
                .unwrap_or_default();

            let raw_mp4 = cinema_dir.join(format!("{}_raw.mp4", proj.slug));
            let thumb_jpg = cinema_dir.join(format!("{}_thumb.jpg", proj.slug));
            let depth_png = cinema_dir.join(format!("{}_depth.png", proj.slug));
            let kf_json = cinema_dir.join("keyframes.json");
            let _ = std::fs::write(
                &kf_json,
                serde_json::to_string_pretty(&proj.manifest.cinema.keyframes)
                    .unwrap_or_else(|_| "[]".into()),
            );

            // Step 1: Sequential Blender 5.2 Cycles OptiX Beauty + Depth Render (exits -> 0 MB VRAM)
            let mut b_args = vec![
                "--background".to_string(),
                "--python-exit-code".to_string(),
                "1".to_string(),
                "--python".to_string(),
                seq_script.to_string(),
                "--".to_string(),
                "--out-raw-mp4".to_string(),
                raw_mp4.to_string_lossy().to_string(),
                "--out-thumb".to_string(),
                thumb_jpg.to_string_lossy().to_string(),
                "--out-depth".to_string(),
                depth_png.to_string_lossy().to_string(),
                "--keyframes-json".to_string(),
                kf_json.to_string_lossy().to_string(),
                "--duration".to_string(),
                format!("{duration_sec:.2}"),
                "--fps".to_string(),
                fps.to_string(),
                "--width".to_string(),
                width.to_string(),
                "--height".to_string(),
                height.to_string(),
                "--mood".to_string(),
                mood.to_string(),
            ];
            if !glb_source.is_empty() && Path::new(&glb_source).is_file() {
                b_args.push("--glb".to_string());
                b_args.push(glb_source);
            } else if !plate_source.is_empty() && Path::new(&plate_source).is_file() {
                b_args.push("--plate".to_string());
                b_args.push(plate_source);
            } else {
                return Err(
                    "Dự án Điện ảnh cần gắn mô hình .glb hoặc ảnh Concept/Manga 2K làm bối cảnh quay."
                        .to_string(),
                );
            }
            run_hidden_command(
                blender_bin,
                &b_args,
                900,
                "Cinema Step 1: Blender Cycles OptiX Beauty+Depth",
            )
            .await?;

            // Step 2: Optional ComfyUI pass + mandatory POST /free VRAM release
            if proj.manifest.cinema.comfyui_enabled
                || payload
                    .get("comfyui_enabled")
                    .and_then(Value::as_bool)
                    .unwrap_or(false)
            {
                let _ = release_comfyui_vram_inner("http://127.0.0.1:8188").await;
            }

            // Step 3: effectcraft-cli transparent VFX / Rune overlay
            let vfx_overlay = cinema_dir.join(format!("{}_vfx_overlay.png", proj.slug));
            let use_vfx = !proj
                .manifest
                .cinema
                .vfx_preset
                .trim()
                .eq_ignore_ascii_case("none");
            if use_vfx && Path::new(effect_bin).is_file() {
                let e_args = vec![
                    "--demo".to_string(),
                    "render-frame".to_string(),
                    "--time".to_string(),
                    "1.25".to_string(),
                    "--transparent".to_string(),
                    "--out".to_string(),
                    vfx_overlay.to_string_lossy().to_string(),
                    "--json".to_string(),
                ];
                let _ =
                    run_hidden_command(effect_bin, &e_args, 120, "Cinema Step 3: effectcraft-cli")
                        .await;
            }

            // Step 4: ToneForge / akunarch-audio-cli -14.0 LUFS Mastering
            let mut primary_audio = proj
                .manifest
                .cinema
                .voice_track_path
                .clone()
                .filter(|p| Path::new(p).is_file())
                .or_else(|| {
                    proj.manifest
                        .cinema
                        .bgm_track_path
                        .clone()
                        .filter(|p| Path::new(p).is_file())
                })
                .or_else(|| {
                    proj.manifest
                        .bgm_audio_path
                        .clone()
                        .filter(|p| Path::new(p).is_file())
                })
                .unwrap_or_default();

            if primary_audio.is_empty() {
                let synth_pad = cinema_dir.join("_cinema_harmonic_bed.wav");
                synthesize_warm_ambient_pad_wav(&synth_pad, duration_sec)?;
                primary_audio = synth_pad.to_string_lossy().to_string();
            }

            let secondary_bgm = proj
                .manifest
                .cinema
                .bgm_track_path
                .clone()
                .or_else(|| proj.manifest.bgm_audio_path.clone())
                .filter(|p| Path::new(p).is_file() && !p.eq_ignore_ascii_case(&primary_audio))
                .unwrap_or_default();

            let master_wav = cinema_dir.join(format!("{}_master_14lufs.wav", proj.slug));
            let mut a_args = vec![
                "master".to_string(),
                "--in".to_string(),
                primary_audio,
                "--out".to_string(),
                master_wav.to_string_lossy().to_string(),
                "--target-lufs".to_string(),
                "-14.0".to_string(),
                "--ceiling-dbtp".to_string(),
                "-1.0".to_string(),
                "--duration-sec".to_string(),
                format!("{duration_sec:.2}"),
                "--json".to_string(),
            ];
            if !secondary_bgm.is_empty() {
                a_args.push("--bgm".to_string());
                a_args.push(secondary_bgm);
            }
            let (audio_stdout, _) = run_hidden_command(
                audio_bin,
                &a_args,
                180,
                "Cinema Step 4: ToneForge -14 LUFS Master",
            )
            .await?;
            let audio_meta: Value =
                serde_json::from_str(audio_stdout.trim()).unwrap_or_else(|_| json!({}));
            let mastered_lufs = audio_meta
                .get("output_integrated_lufs")
                .and_then(Value::as_f64)
                .unwrap_or(-14.0);
            let mastered_dbtp = audio_meta
                .get("output_true_peak_dbtp")
                .and_then(Value::as_f64)
                .unwrap_or(-1.2);

            // Step 5: Write Bilingual Subtitles (.vi.vtt, .en.vtt, .srt) + FFmpeg Composite + filmcraft probe
            write_cinema_subtitle_files(&cinema_dir, &proj.slug, &proj.manifest.cinema.subtitles)?;

            let final_mp4 = cinema_dir.join(format!("{}.mp4", proj.slug));
            let final_mp4_str = final_mp4.to_string_lossy().to_string();

            let mux_args = if use_vfx && vfx_overlay.is_file() {
                vec![
                    "-y".to_string(),
                    "-i".to_string(),
                    raw_mp4.to_string_lossy().to_string(),
                    "-loop".to_string(),
                    "1".to_string(),
                    "-i".to_string(),
                    vfx_overlay.to_string_lossy().to_string(),
                    "-i".to_string(),
                    master_wav.to_string_lossy().to_string(),
                    "-filter_complex".to_string(),
                    format!(
                        "[1:v]scale={width}:{height},format=rgba,colorchannelmixer=aa=0.34[vfx];[0:v][vfx]overlay=0:0:shortest=1[vout]"
                    ),
                    "-map".to_string(),
                    "[vout]".to_string(),
                    "-map".to_string(),
                    "2:a:0".to_string(),
                    "-c:v".to_string(),
                    "libx264".to_string(),
                    "-pix_fmt".to_string(),
                    "yuv420p".to_string(),
                    "-crf".to_string(),
                    "18".to_string(),
                    "-c:a".to_string(),
                    "aac".to_string(),
                    "-b:a".to_string(),
                    "192k".to_string(),
                    "-shortest".to_string(),
                    "-movflags".to_string(),
                    "+faststart".to_string(),
                    final_mp4_str.clone(),
                ]
            } else {
                vec![
                    "-y".to_string(),
                    "-i".to_string(),
                    raw_mp4.to_string_lossy().to_string(),
                    "-i".to_string(),
                    master_wav.to_string_lossy().to_string(),
                    "-map".to_string(),
                    "0:v:0".to_string(),
                    "-map".to_string(),
                    "1:a:0".to_string(),
                    "-c:v".to_string(),
                    "copy".to_string(),
                    "-c:a".to_string(),
                    "aac".to_string(),
                    "-b:a".to_string(),
                    "192k".to_string(),
                    "-shortest".to_string(),
                    "-movflags".to_string(),
                    "+faststart".to_string(),
                    final_mp4_str.clone(),
                ]
            };
            run_hidden_command(ffmpeg_bin, &mux_args, 300, "Cinema Step 5: FFmpeg H.264+AAC Mux")
                .await?;
            let _ = std::fs::remove_file(&raw_mp4);

            if Path::new(film_bin).is_file() {
                let _ = run_hidden_command(
                    film_bin,
                    &["probe".to_string(), final_mp4_str.clone()],
                    30,
                    "filmcraft-cli probe",
                )
                .await;
            }

            let db_save = db_path.to_path_buf();
            let slug_save = project_slug.to_string();
            let mp4_save = final_mp4_str.clone();
            let thumb_save = thumb_jpg.to_string_lossy().to_string();
            let vfx_save = vfx_overlay.is_file().then(|| vfx_overlay.to_string_lossy().to_string());
            let wav_save = master_wav.to_string_lossy().to_string();

            let _ = tokio::task::spawn_blocking(move || {
                if let Ok(conn) = open_akunarch_db_at(&db_save) {
                    if let Ok(Some(mut p)) =
                        crate::projects::get_project_by_slug(&conn, &slug_save)
                    {
                        p.manifest.cinema.video_path = Some(mp4_save);
                        if Path::new(&thumb_save).is_file() {
                            p.manifest.cinema.thumbnail_path = Some(thumb_save.clone());
                            if p.manifest.local_image_path.is_none() {
                                p.manifest.local_image_path = Some(thumb_save);
                            }
                        }
                        if let Some(vp) = vfx_save {
                            p.manifest.cinema.vfx_overlay_path = Some(vp);
                        }
                        p.manifest.cinema.mastered_audio_path = Some(wav_save);
                        p.manifest.cinema.mastered_lufs = Some(mastered_lufs as f32);
                        p.manifest.cinema.mastered_true_peak_dbtp = Some(mastered_dbtp as f32);
                        p.manifest.cinema.duration_sec = duration_sec;
                        p.manifest.cinema.fps = fps as u32;
                        let _ = crate::projects::update_project_manifest(
                            &conn,
                            Some(&slug_save),
                            p.manifest,
                        );
                    }
                }
            })
            .await;

            Ok(final_mp4_str)
        }
        other => Err(format!(
            "Chế độ thực thi '{other}' cho worker '{worker_kind}' sẽ được kích hoạt ở phân xưởng chuyên biệt tiếp theo."
        )),
    }
}

fn format_vtt_timestamp(sec: f64) -> String {
    let total_ms = (sec.max(0.0) * 1000.0).round() as u64;
    let hours = total_ms / 3_600_000;
    let mins = (total_ms % 3_600_000) / 60_000;
    let secs = (total_ms % 60_000) / 1000;
    let ms = total_ms % 1000;
    format!("{hours:02}:{mins:02}:{secs:02}.{ms:03}")
}

fn format_srt_timestamp(sec: f64) -> String {
    format_vtt_timestamp(sec).replace('.', ",")
}

pub fn write_cinema_subtitle_files(
    cinema_dir: &Path,
    slug: &str,
    cues: &[crate::projects::CinemaSubtitleCue],
) -> Result<(), String> {
    std::fs::create_dir_all(cinema_dir).map_err(|e| e.to_string())?;
    let mut vi_vtt = String::from("WEBVTT\n\n");
    let mut en_vtt = String::from("WEBVTT\n\n");
    let mut bi_srt = String::new();

    for (idx, cue) in cues.iter().enumerate() {
        let start_vtt = format_vtt_timestamp(cue.start_sec);
        let end_vtt = format_vtt_timestamp(cue.end_sec.max(cue.start_sec + 0.4));
        let start_srt = format_srt_timestamp(cue.start_sec);
        let end_srt = format_srt_timestamp(cue.end_sec.max(cue.start_sec + 0.4));

        if !cue.text_vi.trim().is_empty() {
            vi_vtt.push_str(&format!(
                "{}\n{} --> {}\n{}\n\n",
                idx + 1,
                start_vtt,
                end_vtt,
                cue.text_vi.trim()
            ));
        }
        if !cue.text_en.trim().is_empty() {
            en_vtt.push_str(&format!(
                "{}\n{} --> {}\n{}\n\n",
                idx + 1,
                start_vtt,
                end_vtt,
                cue.text_en.trim()
            ));
        }
        let combined = match (cue.text_vi.trim().is_empty(), cue.text_en.trim().is_empty()) {
            (false, false) => format!("{}\n{}", cue.text_vi.trim(), cue.text_en.trim()),
            (false, true) => cue.text_vi.trim().to_string(),
            (true, false) => cue.text_en.trim().to_string(),
            (true, true) => continue,
        };
        bi_srt.push_str(&format!(
            "{}\n{} --> {}\n{}\n\n",
            idx + 1,
            start_srt,
            end_srt,
            combined
        ));
    }

    std::fs::write(cinema_dir.join(format!("{slug}.vi.vtt")), vi_vtt).map_err(|e| e.to_string())?;
    std::fs::write(cinema_dir.join(format!("{slug}.en.vtt")), en_vtt).map_err(|e| e.to_string())?;
    std::fs::write(cinema_dir.join(format!("{slug}.srt")), bi_srt).map_err(|e| e.to_string())?;
    Ok(())
}

/// Synthesizes a clean stereo 48kHz 16-bit warm acoustic pad (D-minor fifths + bronze bell overtones)
/// when a Cinema project has no external FL Studio BGM or TTS WAV attached yet, so ToneForge DSP
/// always has rich musical content to master to `-14.0 LUFS`.
pub fn synthesize_warm_ambient_pad_wav(out_path: &Path, duration_sec: f64) -> Result<(), String> {
    if let Some(parent) = out_path.parent() {
        std::fs::create_dir_all(parent).map_err(|e| e.to_string())?;
    }
    let sr: u32 = 48_000;
    let channels: u16 = 2;
    let frames = ((duration_sec.clamp(1.5, 60.0)) * (sr as f64)).round() as usize;
    let data_bytes = (frames * (channels as usize) * 2) as u32;

    let mut buf = Vec::with_capacity(44 + data_bytes as usize);
    buf.extend_from_slice(b"RIFF");
    buf.extend_from_slice(&(36u32 + data_bytes).to_le_bytes());
    buf.extend_from_slice(b"WAVEfmt ");
    buf.extend_from_slice(&16u32.to_le_bytes());
    buf.extend_from_slice(&1u16.to_le_bytes()); // PCM
    buf.extend_from_slice(&channels.to_le_bytes());
    buf.extend_from_slice(&sr.to_le_bytes());
    buf.extend_from_slice(&(sr * (channels as u32) * 2).to_le_bytes());
    buf.extend_from_slice(&(channels * 2).to_le_bytes());
    buf.extend_from_slice(&16u16.to_le_bytes());
    buf.extend_from_slice(b"data");
    buf.extend_from_slice(&data_bytes.to_le_bytes());

    let dur = frames as f64 / (sr as f64);
    for i in 0..frames {
        let t = (i as f64) / (sr as f64);
        let fade_in = (t / 0.45).clamp(0.0, 1.0);
        let fade_out = ((dur - t) / 0.65).clamp(0.0, 1.0);
        let env = fade_in * fade_out;

        let slow_lfo = 0.85 + 0.15 * (2.0 * std::f64::consts::PI * 0.22 * t).sin();
        // Warm D2 (73.42 Hz) + A2 (110.0 Hz) + D3 (146.83 Hz) + F3 (174.61 Hz) + A3 (220.0 Hz)
        let l = env
            * slow_lfo
            * (0.28 * (2.0 * std::f64::consts::PI * 73.42 * t).sin()
                + 0.22 * (2.0 * std::f64::consts::PI * 110.00 * t + 0.18).sin()
                + 0.17 * (2.0 * std::f64::consts::PI * 146.83 * t).sin()
                + 0.11 * (2.0 * std::f64::consts::PI * 220.05 * t + 0.4).sin()
                + 0.06 * (-t * 0.65).exp() * (2.0 * std::f64::consts::PI * 440.0 * t).sin());
        let r = env
            * slow_lfo
            * (0.28 * (2.0 * std::f64::consts::PI * 73.42 * t).sin()
                + 0.22 * (2.0 * std::f64::consts::PI * 110.08 * t - 0.18).sin()
                + 0.17 * (2.0 * std::f64::consts::PI * 174.61 * t + 0.25).sin()
                + 0.11 * (2.0 * std::f64::consts::PI * 219.95 * t - 0.3).sin()
                + 0.06 * (-t * 0.65).exp() * (2.0 * std::f64::consts::PI * 587.33 * t).sin());

        let sl = (l.clamp(-0.95, 0.95) * 32767.0).round() as i16;
        let sr_sample = (r.clamp(-0.95, 0.95) * 32767.0).round() as i16;
        buf.extend_from_slice(&sl.to_le_bytes());
        buf.extend_from_slice(&sr_sample.to_le_bytes());
    }

    std::fs::write(out_path, buf).map_err(|e| format!("Không ghi được WAV nền: {e}"))
}

fn offline_vram_telemetry() -> VramTelemetry {
    VramTelemetry {
        gpu_available: false,
        gpu_name: "GPU Offline / Không đọc được nvidia-smi".to_string(),
        total_mb: 16384,
        used_mb: 0,
        free_mb: 16384,
        utilization_pct: 0,
        temperature_c: 0,
        vram_budget_mb: 16384,
        within_16gb_budget: true,
        app_used_mb: 0,
        webview_used_mb: 0,
        worker_used_mb: 0,
        other_system_mb: 0,
        app_vram_available: false,
    }
}

fn parse_nvidia_smi_csv(text: &str) -> Option<VramTelemetry> {
    let line = text.lines().next()?;
    let parts: Vec<&str> = line.split(',').map(str::trim).collect();
    if parts.len() < 6 {
        return None;
    }
    let gpu_name = parts[0].to_string();
    let total_mb = parts[1].parse::<i64>().unwrap_or(16384);
    let used_mb = parts[2].parse::<i64>().unwrap_or(0);
    let free_mb = parts[3].parse::<i64>().unwrap_or(total_mb - used_mb);
    let utilization_pct = parts[4].parse::<i64>().unwrap_or(0);
    let temperature_c = parts[5].parse::<i64>().unwrap_or(0);
    let budget = 16384i64.min(total_mb);
    Some(VramTelemetry {
        gpu_available: true,
        gpu_name,
        total_mb,
        used_mb,
        free_mb,
        utilization_pct,
        temperature_c,
        vram_budget_mb: budget,
        within_16gb_budget: used_mb <= (budget - 512),
        app_used_mb: 0,
        webview_used_mb: 0,
        worker_used_mb: 0,
        other_system_mb: used_mb,
        app_vram_available: false,
    })
}

/// Asynchronous bounded VRAM probe (`2000ms` timeout + `kill_on_drop`) so a hung GPU display driver
/// can never stall Tauri IPC or `GpuJobQueue`.
pub async fn probe_nvidia_vram_async() -> VramTelemetry {
    let mut cmd = tokio::process::Command::new("nvidia-smi");
    cmd.args([
        "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
        "--format=csv,noheader,nounits",
    ]);
    cmd.kill_on_drop(true);
    #[cfg(windows)]
    {
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }

    if let Ok(Ok(out)) =
        tokio::time::timeout(std::time::Duration::from_millis(2000), cmd.output()).await
    {
        if out.status.success() {
            let text = String::from_utf8_lossy(&out.stdout);
            if let Some(parsed) = parse_nvidia_smi_csv(&text) {
                return parsed;
            }
        }
    }
    offline_vram_telemetry()
}

pub async fn release_comfyui_vram(comfyui_base_url: Option<&str>) -> VramReleaseResult {
    let url = comfyui_base_url
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .unwrap_or("http://127.0.0.1:8188");
    release_comfyui_vram_inner(url).await
}

async fn release_comfyui_vram_inner(base_url: &str) -> VramReleaseResult {
    let endpoint = format!("{}/free", base_url.trim_end_matches('/'));
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_millis(1800))
        .build()
        .unwrap_or_default();

    let resp = client
        .post(&endpoint)
        .json(&json!({
            "unload_models": true,
            "free_memory": true
        }))
        .send()
        .await;

    let vram_after = probe_vram_with_app().await;

    match resp {
        Ok(r) if r.status().is_success() => VramReleaseResult {
            comfyui_reachable: true,
            unloaded_models: true,
            message: format!(
                "Đã giải phóng mô hình ComfyUI thành công. VRAM trống hiện tại: {} MB.",
                vram_after.free_mb
            ),
            vram_after,
        },
        Ok(r) => VramReleaseResult {
            comfyui_reachable: true,
            unloaded_models: false,
            message: format!(
                "ComfyUI phản hồi HTTP {} khi gọi /free. VRAM trống: {} MB.",
                r.status(),
                vram_after.free_mb
            ),
            vram_after,
        },
        Err(_) => VramReleaseResult {
            comfyui_reachable: false,
            unloaded_models: false,
            message: format!(
                "ComfyUI (127.0.0.1:8188) hiện đang tắt (0 MB chiếm dụng bởi ComfyUI). VRAM trống sẵn sàng: {} MB.",
                vram_after.free_mb
            ),
            vram_after,
        },
    }
}

pub fn get_gpu_job_by_id(conn: &Connection, job_id: i64) -> Result<GpuJobRow, String> {
    conn.query_row(
        "SELECT id, project_id, worker_kind, payload_json, status, progress_pct,
                vram_peak_mb, output_path, error_log, created_at, updated_at
         FROM gpu_jobs
         WHERE id = ?1",
        params![job_id],
        map_gpu_job_row,
    )
    .map_err(|e| format!("Không tìm thấy gpu_job #{job_id}: {e}"))
}

pub fn list_gpu_jobs(conn: &Connection, limit: usize) -> Result<Vec<GpuJobRow>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT id, project_id, worker_kind, payload_json, status, progress_pct,
                    vram_peak_mb, output_path, error_log, created_at, updated_at
             FROM gpu_jobs
             ORDER BY id DESC
             LIMIT ?1",
        )
        .map_err(|e| format!("Lỗi đọc danh sách gpu_jobs: {e}"))?;
    let rows = stmt
        .query_map(params![limit.max(1) as i64], map_gpu_job_row)
        .map_err(|e| format!("Lỗi duyệt gpu_jobs: {e}"))?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(|e| e.to_string())?);
    }
    Ok(out)
}

fn map_gpu_job_row(r: &rusqlite::Row<'_>) -> rusqlite::Result<GpuJobRow> {
    let payload_raw: String = r.get(3)?;
    let payload: Value = serde_json::from_str(&payload_raw).unwrap_or_else(|_| json!({}));
    Ok(GpuJobRow {
        id: r.get(0)?,
        project_id: r.get(1)?,
        worker_kind: r.get(2)?,
        payload,
        status: r.get(4)?,
        progress_pct: r.get(5)?,
        vram_peak_mb: r.get(6)?,
        output_path: r.get(7)?,
        error_log: r.get(8)?,
        created_at: r.get(9)?,
        updated_at: r.get(10)?,
    })
}

#[cfg(test)]
mod tests {
    #[test]
    fn preview_card_needed_when_missing_or_older_than_glb() {
        let dir = std::env::temp_dir().join(format!("akun_preview_{}", std::process::id()));
        std::fs::create_dir_all(&dir).unwrap();
        let glb = dir.join("demo.glb");
        std::fs::write(&glb, b"glb").unwrap();
        let png = preview_card_path(&glb.to_string_lossy());
        assert_eq!(png, dir.join("demo_preview_1080p.png"));
        assert!(preview_card_needed(&glb, &png), "thiếu ảnh → cần render");
        std::fs::write(&png, b"png").unwrap();
        let t0 = std::time::SystemTime::now();
        let old = t0 - std::time::Duration::from_secs(3600);
        std::fs::File::options().write(true).open(&glb).unwrap().set_modified(old).unwrap();
        std::fs::File::options().write(true).open(&png).unwrap().set_modified(t0).unwrap();
        assert!(!preview_card_needed(&glb, &png), "ảnh mới hơn .glb → không render lại");
        std::fs::File::options().write(true).open(&glb).unwrap()
            .set_modified(t0 + std::time::Duration::from_secs(60)).unwrap();
        assert!(preview_card_needed(&glb, &png), ".glb mới hơn ảnh (vd. vừa nén KTX2) → render lại");
        assert!(!preview_card_needed(&dir.join("none.glb"), &png), "không có .glb → không làm gì");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn blender_source_glb_prefers_master_copy() {
        let dir = std::env::temp_dir().join(format!("akun_master_{}", std::process::id()));
        let clock = dir.join("clockwork");
        std::fs::create_dir_all(clock.join("_master")).unwrap();
        let runtime = clock.join("demo.glb");
        std::fs::write(&runtime, b"ktx2").unwrap();
        let rt = runtime.to_string_lossy().to_string();
        assert_eq!(blender_source_glb(&rt), rt, "chưa có _master → giữ nguyên");
        std::fs::write(clock.join("_master").join("demo.glb"), b"jpeg").unwrap();
        assert_eq!(
            blender_source_glb(&rt),
            clock.join("_master").join("demo.glb").to_string_lossy().to_string()
        );
        assert_eq!(blender_source_glb(""), "");
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn follow_up_chain_assemble_then_preview_ktx2_only_when_finalized() {
        // Anh chốt 2026-11-13: KTX2 (~40 phút CPU) KHÔNG tự chạy sau mỗi lần dựng — chỉ chạy khi chốt bản cuối
        let glb = r"E:\Akunarch\projects\demo\clockwork\demo.glb";
        for mode in ["sculpt_concept", "assemble_glb"] {
            let next = follow_up_jobs(mode, glb, "demo");
            assert_eq!(next.len(), 1);
            assert_eq!(next[0].0, "blender");
            assert_eq!(next[0].1["mode"], "render_preview_card");
            assert_eq!(next[0].1["glb_path"], glb);
        }
        let next = follow_up_jobs("optimize_glb_runtime", glb, "demo");
        assert_eq!(next[0].1["mode"], "render_preview_card");
        // Không chuỗi tiếp sau ảnh xem trước, không chạy khi thiếu slug hoặc đầu ra không phải .glb
        assert!(follow_up_jobs("render_preview_card", glb, "demo").is_empty());
        assert!(follow_up_jobs("assemble_glb", glb, "").is_empty());
        assert!(follow_up_jobs("assemble_glb", r"E:\x\intro.mp4", "demo").is_empty());
        assert!(follow_up_jobs("render_intro_mp4", glb, "demo").is_empty());
    }

    #[test]
    fn follow_up_chain_mechanism_none_and_no_preview_after_its_optimize() {
        let mech = r"E:\Akunarch\projects\demo\clockwork\demo_mechanism.glb";
        assert!(follow_up_jobs("assemble_mechanism_glb", mech, "demo").is_empty(), "KTX2 chỉ khi chốt bản cuối");
        assert!(
            follow_up_jobs("optimize_glb_runtime", mech, "demo").is_empty(),
            "bản cơ khí không được thay ảnh xem trước của bản thật"
        );
    }

    #[cfg(windows)]
    #[tokio::test]
    async fn timeout_kills_whole_process_tree_not_only_direct_child() {
        // Lỗi cũ: kill_on_drop chỉ giết powershell → ktx.exe (cháu) chạy mồ côi, đốt CPU sau khi job đã "quá hạn"
        let marker = format!("127.0.0.{}", 50 + std::process::id() % 150);
        let script = format!(
            "Start-Process -NoNewWindow -FilePath ping.exe -ArgumentList '-n 40 {marker}'; Start-Sleep -Seconds 40"
        );
        let args = vec!["-NoProfile".to_string(), "-Command".to_string(), script];
        let err = run_hidden_command(POWERSHELL_EXE, &args, 3, "test cây tiến trình").await.unwrap_err();
        assert!(err.contains("Quá thời gian"), "{err}");
        tokio::time::sleep(std::time::Duration::from_millis(1500)).await;
        let probe = std::process::Command::new(POWERSHELL_EXE)
            .args([
                "-NoProfile",
                "-Command",
                &format!("@(Get-CimInstance Win32_Process | Where-Object {{ $_.CommandLine -match '{marker}' -and $_.Name -eq 'PING.EXE' }}).Count"),
            ])
            .output()
            .unwrap();
        let left = String::from_utf8_lossy(&probe.stdout).trim().to_string();
        assert_eq!(left, "0", "tiến trình cháu còn sống: {left}");
    }

    #[test]
    fn powershell_is_called_by_absolute_existing_path() {
        // Lỗi cũ: run_hidden_command("powershell") kiểm Path::new("powershell").is_file() → luôn sai → KTX2 tự động luôn hỏng
        assert!(std::path::Path::new(POWERSHELL_EXE).is_absolute());
        assert!(std::path::Path::new(POWERSHELL_EXE).is_file());
    }

    #[test]
    fn comfy_workflow_args_maps_payload_to_runner_flags() {
        let p = json!({
            "workflow": r"E:\Akunarch\bin\comfy_workflows\trellis2_image_to_glb.api.json",
            "image": r"E:\a b\ảnh.png",
            "image_node": "122",
            "set": ["316.value=true", "288.value=2048"],
            "prefix": "tracery",
            "timeout_sec": 900
        });
        let args = comfy_workflow_args(&p, std::path::Path::new(r"E:\p\demo\comfy")).unwrap();
        assert!(args[0].ends_with(r"bin\scripts\comfy_run_workflow.py"), "{}", args[0]);
        let pos = |flag: &str| args.iter().position(|a| a == flag).unwrap();
        assert_eq!(args[pos("--out-dir") + 1], r"E:\p\demo\comfy");
        assert_eq!(args[pos("--image") + 1], r"E:\a b\ảnh.png");
        assert_eq!(args[pos("--prefix") + 1], "tracery");
        assert_eq!(args[pos("--timeout") + 1], "900");
        assert_eq!(args.iter().filter(|a| *a == "--set").count(), 2);
        // thiếu workflow → lỗi rõ
        assert!(comfy_workflow_args(&json!({}), std::path::Path::new("x")).unwrap_err().contains("workflow"));
    }

    #[test]
    fn intro_render_plan_picks_script_and_output_by_variant() {
        let folder = std::path::Path::new(r"E:\p\demo");
        let (script, out) = intro_render_plan(Some("mechanism"), folder, "demo");
        assert!(script.ends_with(r"clockwork\render_mechanism_intro.py"), "{script}");
        assert_eq!(out, folder.join("cinema").join("demo_mechanism_intro.mp4"));
        let (script, out) = intro_render_plan(None, folder, "demo");
        assert!(script.ends_with("render_clockwork_intro.py"), "{script}");
        assert_eq!(out, folder.join("cinema").join("demo_intro.mp4"));
    }

    #[test]
    fn merge_app_vram_splits_app_and_other_system() {
        let smi = parse_nvidia_smi_csv("NVIDIA GeForce RTX 4080, 16376, 2300, 14076, 7, 41").unwrap();
        assert_eq!(smi.other_system_mb, 2300);
        let s = crate::vram_win32::AppVramSample {
            available: true,
            app_mb: 450,
            webview_mb: 440,
            worker_mb: 0,
            host_mb: 10,
        };
        let t = merge_app_vram(smi.clone(), &s);
        assert!(t.app_vram_available);
        assert_eq!((t.app_used_mb, t.webview_used_mb, t.worker_used_mb, t.other_system_mb), (450, 440, 0, 1850));
        // PDH lỗi → app = 0, phần "khác" = toàn máy
        let off = merge_app_vram(smi.clone(), &crate::vram_win32::AppVramSample::default());
        assert!(!off.app_vram_available);
        assert_eq!((off.app_used_mb, off.other_system_mb), (0, 2300));
        // Không bao giờ âm (PDH và nvidia-smi lệch thời điểm)
        let big = crate::vram_win32::AppVramSample { app_mb: 9999, ..s };
        assert_eq!(merge_app_vram(smi, &big).other_system_mb, 0);
    }

    #[test]
    fn vram_peak_tracks_max_of_machine_and_worker_ignoring_offline_samples() {
        let p = VramPeak::new(2000, 0);
        let mut t = parse_nvidia_smi_csv("RTX 4080, 16376, 9000, 7376, 99, 70").unwrap();
        t.app_vram_available = true;
        t.worker_used_mb = 6500;
        p.observe(&t);
        let mut later = parse_nvidia_smi_csv("RTX 4080, 16376, 2100, 14276, 3, 50").unwrap();
        later.app_vram_available = true;
        later.worker_used_mb = 0;
        p.observe(&later);
        p.observe(&offline_vram_telemetry());
        assert_eq!((p.machine_mb(), p.worker_mb()), (9000, 6500));
    }

    use super::*;

    #[tokio::test]
    async fn single_mutex_gpu_queue_serializes_concurrent_heavy_jobs() {
        let tmp_db = std::env::temp_dir().join(format!(
            "akunarch_gpu_test_{}.db",
            Utc::now().timestamp_nanos_opt().unwrap_or(2)
        ));
        let _ = open_akunarch_db_at(&tmp_db).unwrap();

        let queue = GpuJobQueue {
            db_path: tmp_db.clone(),
            gpu_mutex: Arc::new(Mutex::new(None)),
            wakeup: Arc::new(Notify::new()),
            active_jobs_counter: Arc::new(AtomicUsize::new(0)),
            job_start_notifier: Arc::new(std::sync::OnceLock::new()),
        };

        // Enqueue 3 jobs back-to-back
        for wk in ["hunyuan3d", "blender", "tts"] {
            queue
                .enqueue(EnqueueGpuJobInput {
                    project_id: None,
                    worker_kind: wk.to_string(),
                    payload: json!({ "mode": "probe", "simulate_ms": 40 }),
                })
                .expect("enqueue job");
        }

        // Fire 3 concurrent tasks trying to process simultaneously; mutex must serialize them 1-by-1
        let q1 = queue.clone();
        let q2 = queue.clone();
        let q3 = queue.clone();
        let (r1, r2, r3) = tokio::join!(
            q1.try_process_next_queued_job(),
            q2.try_process_next_queued_job(),
            q3.try_process_next_queued_job()
        );
        assert!(r1 && r2 && r3);
        assert_eq!(queue.active_concurrent_count(), 0);

        let jobs = queue.list_jobs(10).unwrap();
        assert_eq!(jobs.len(), 3);
        assert!(jobs.iter().all(|j| j.status == "completed"));

        let _ = std::fs::remove_file(&tmp_db);
    }
}
