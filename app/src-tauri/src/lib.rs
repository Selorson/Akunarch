pub mod cowriter_bridge;
pub mod db;
pub mod gpu_queue;
pub mod media_protocol;
pub mod projects;
pub mod selorson_sync;
pub mod vram_win32;
pub mod workbenches;

use cowriter_bridge::{load_manga_episode_pages, load_vault_snapshot, MangaPageItem, VaultSnapshot};
use db::{
    akunarch_db_path, akunarch_projects_root, open_akunarch_db, scan_and_index_local_assets,
    AssetLibraryRow,
};
use gpu_queue::{
    release_comfyui_vram, EnqueueGpuJobInput, GpuJobQueue, GpuJobRow, HardwareStackReport,
    VramReleaseResult,
};
use projects::{
    create_project, export_project_akunbundle, get_project_by_slug, import_external_file,
    list_ai_meshes, list_projects, rescan_projects_from_disk, resolve_project_subfolder_path,
    save_manga_plates, update_project_manifest, upload_asset_bytes, AiMeshEntry,
    CreateProjectInput, MangaPlateExportResult, ProjectManifest, ProjectRecord,
};
use selorson_sync::{
    audit_project_for_sync, fetch_selorson_world_overview, get_selorson_config, list_sync_logs,
    login_to_selorson, push_project_to_selorson, save_selorson_config, QaAuditReport,
    SelorsonConnectionConfig, SyncLogRow,
};
use workbenches::{
    generate_chunk_terrain, load_or_init_vn_episode, pack_chunk_zip, pack_vn_episode_zip,
    save_vn_episode, sculpt_chunk_terrain, stitch_chunk_with_neighbors_in_root, ChunkPackResult,
    ChunkStitchReport, VnEpisodeDocument, VnPackResult, VnSaveResult,
};
use serde::Serialize;
use serde_json::Value;

pub struct AppState {
    pub gpu_queue: GpuJobQueue,
}

#[derive(Debug, Serialize)]
pub struct StudioBootstrapPayload {
    pub db_path: String,
    pub projects_root: String,
    pub projects: Vec<ProjectRecord>,
    pub asset_library: Vec<AssetLibraryRow>,
    pub hardware: HardwareStackReport,
    pub selorson_config: SelorsonConnectionConfig,
    pub sync_logs: Vec<SyncLogRow>,
}

#[tauri::command]
async fn studio_bootstrap(state: tauri::State<'_, AppState>) -> Result<StudioBootstrapPayload, String> {
    let db_path_buf = akunarch_db_path();
    let projects_root_buf = akunarch_projects_root();
    let (projects, asset_library, selorson_config, sync_logs) = tokio::task::spawn_blocking(|| {
        let conn = open_akunarch_db()?;
        let projs = rescan_projects_from_disk(&conn)?;
        let assets = scan_and_index_local_assets(&conn)?;
        let cfg = get_selorson_config(&conn);
        let logs = list_sync_logs(&conn, 25)?;
        Ok::<_, String>((projs, assets, cfg, logs))
    })
    .await
    .map_err(|e| format!("Lỗi tác vụ khởi tạo Studio: {e}"))??;
    let hardware = state.gpu_queue.hardware_report().await;
    Ok(StudioBootstrapPayload {
        db_path: db_path_buf.to_string_lossy().to_string(),
        projects_root: projects_root_buf.to_string_lossy().to_string(),
        projects,
        asset_library,
        hardware,
        selorson_config,
        sync_logs,
    })
}

#[tauri::command]
async fn vault_get_snapshot() -> Result<VaultSnapshot, String> {
    tokio::task::spawn_blocking(load_vault_snapshot)
        .await
        .map_err(|e| format!("Lỗi tác vụ đọc Kho Thánh Tích: {e}"))?
}

#[tauri::command]
async fn vault_get_manga_pages(episode_id: i64) -> Result<Vec<MangaPageItem>, String> {
    tokio::task::spawn_blocking(move || load_manga_episode_pages(episode_id))
        .await
        .map_err(|e| format!("Lỗi tác vụ đọc trang Manga: {e}"))?
}

#[tauri::command]
async fn vault_scan_local_assets() -> Result<Vec<AssetLibraryRow>, String> {
    tokio::task::spawn_blocking(|| {
        let conn = open_akunarch_db()?;
        scan_and_index_local_assets(&conn)
    })
    .await
    .map_err(|e| format!("Lỗi quét kho vật liệu PBR: {e}"))?
}

#[tauri::command]
async fn projects_list() -> Result<Vec<ProjectRecord>, String> {
    tokio::task::spawn_blocking(|| {
        let conn = open_akunarch_db()?;
        list_projects(&conn)
    })
    .await
    .map_err(|e| format!("Lỗi đọc danh sách dự án: {e}"))?
}

#[tauri::command]
async fn projects_rescan() -> Result<Vec<ProjectRecord>, String> {
    tokio::task::spawn_blocking(|| {
        let conn = open_akunarch_db()?;
        rescan_projects_from_disk(&conn)
    })
    .await
    .map_err(|e| format!("Lỗi quét lại thư mục dự án: {e}"))?
}

#[tauri::command]
async fn projects_create(input: CreateProjectInput) -> Result<ProjectRecord, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        create_project(&conn, input)
    })
    .await
    .map_err(|e| format!("Lỗi tạo dự án: {e}"))?
}

#[tauri::command]
async fn projects_update(
    manifest: ProjectManifest,
    original_slug: Option<String>,
) -> Result<ProjectRecord, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        update_project_manifest(&conn, original_slug.as_deref(), manifest)
    })
    .await
    .map_err(|e| format!("Lỗi cập nhật hồ sơ dự án: {e}"))?
}

#[tauri::command]
async fn projects_export_bundle(slug: String) -> Result<String, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        export_project_akunbundle(&conn, &slug)
    })
    .await
    .map_err(|e| format!("Lỗi đóng gói .akunbundle.zip: {e}"))?
}

#[tauri::command]
async fn projects_import_external_file(
    slug: String,
    asset_kind: String,
    source_path: String,
    set_primary: Option<bool>,
) -> Result<ProjectRecord, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        import_external_file(
            &conn,
            &slug,
            &asset_kind,
            &source_path,
            set_primary.unwrap_or(true),
        )
    })
    .await
    .map_err(|e| format!("Lỗi nhập tệp tài nguyên ngoài: {e}"))?
}

#[tauri::command]
async fn projects_upload_asset_bytes(
    slug: String,
    asset_kind: String,
    file_name: String,
    bytes_base64: String,
    set_primary: Option<bool>,
) -> Result<ProjectRecord, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        upload_asset_bytes(
            &conn,
            &slug,
            &asset_kind,
            &file_name,
            &bytes_base64,
            set_primary.unwrap_or(true),
        )
    })
    .await
    .map_err(|e| format!("Lỗi lưu tệp kéo-thả vào dự án: {e}"))?
}

#[tauri::command]
async fn projects_save_manga_plates(
    slug: String,
    label: Option<String>,
    width: u32,
    height: u32,
    beauty_png_base64: String,
    depth_png_base64: String,
) -> Result<MangaPlateExportResult, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        save_manga_plates(
            &conn,
            &slug,
            label.as_deref(),
            width,
            height,
            &beauty_png_base64,
            &depth_png_base64,
        )
    })
    .await
    .map_err(|e| format!("Lỗi xuất phông nền Manga 2K: {e}"))?
}

#[tauri::command]
async fn projects_list_ai_meshes() -> Result<Vec<AiMeshEntry>, String> {
    tokio::task::spawn_blocking(list_ai_meshes)
        .await
        .map_err(|e| format!("Lỗi đọc danh sách 47 mesh điêu khắc: {e}"))?
}

#[tauri::command]
async fn projects_open_folder(slug: String, subfolder: Option<String>) -> Result<String, String> {
    let dir_path = tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        resolve_project_subfolder_path(&conn, &slug, subfolder.as_deref())
    })
    .await
    .map_err(|e| format!("Lỗi mở thư mục dự án: {e}"))??;

    let dir_str = dir_path.to_string_lossy().to_string();
    #[cfg(windows)]
    {
        let _ = std::process::Command::new("explorer.exe")
            .arg(&dir_str)
            .spawn();
    }
    Ok(dir_str)
}

#[tauri::command]
async fn gpu_hardware_report(
    state: tauri::State<'_, AppState>,
) -> Result<HardwareStackReport, String> {
    Ok(state.gpu_queue.hardware_report().await)
}

#[tauri::command]
async fn gpu_list_jobs(
    state: tauri::State<'_, AppState>,
    limit: Option<usize>,
) -> Result<Vec<GpuJobRow>, String> {
    let queue = state.gpu_queue.clone();
    tokio::task::spawn_blocking(move || queue.list_jobs(limit.unwrap_or(40)))
        .await
        .map_err(|e| format!("Lỗi đọc hàng đợi GPU: {e}"))?
}

#[tauri::command]
async fn gpu_enqueue_job(
    state: tauri::State<'_, AppState>,
    input: EnqueueGpuJobInput,
) -> Result<GpuJobRow, String> {
    let queue = state.gpu_queue.clone();
    tokio::task::spawn_blocking(move || queue.enqueue(input))
        .await
        .map_err(|e| format!("Lỗi thêm tác vụ GPU: {e}"))?
}

#[tauri::command]
async fn gpu_cancel_job(
    state: tauri::State<'_, AppState>,
    job_id: i64,
) -> Result<GpuJobRow, String> {
    let queue = state.gpu_queue.clone();
    tokio::task::spawn_blocking(move || queue.cancel_queued(job_id))
        .await
        .map_err(|e| format!("Lỗi hủy tác vụ GPU: {e}"))?
}

/// C2 (trường hợp c): mở dự án → ảnh xem trước thiếu hoặc cũ hơn .glb thì xếp `render_preview_card` chạy nền
/// (không chặn UI, không trùng job đang chờ/chạy). Không bao giờ gọi khi rescan.
#[tauri::command]
async fn projects_ensure_preview_card(
    state: tauri::State<'_, AppState>,
    slug: String,
) -> Result<Option<GpuJobRow>, String> {
    let queue = state.gpu_queue.clone();
    tokio::task::spawn_blocking(move || -> Result<Option<GpuJobRow>, String> {
        let conn = open_akunarch_db()?;
        let Some(proj) = projects::get_project_by_slug(&conn, &slug)? else {
            return Ok(None);
        };
        let Some(glb) = proj.manifest.clockwork.glb_path.clone().filter(|g| !g.trim().is_empty()) else {
            return Ok(None);
        };
        let png = gpu_queue::preview_card_path(&glb);
        if !gpu_queue::preview_card_needed(std::path::Path::new(&glb), &png) {
            return Ok(None);
        }
        let pending = queue.list_jobs(200)?.into_iter().any(|j| {
            (j.status == "queued" || j.status == "running")
                && j.payload.get("project_slug").and_then(Value::as_str) == Some(slug.as_str())
                && matches!(
                    j.payload.get("mode").and_then(Value::as_str),
                    Some("render_preview_card" | "optimize_glb_runtime" | "assemble_glb" | "sculpt_concept")
                )
        });
        if pending {
            return Ok(None);
        }
        queue
            .enqueue(EnqueueGpuJobInput {
                project_id: Some(proj.id),
                worker_kind: "blender".to_string(),
                payload: serde_json::json!({ "mode": "render_preview_card", "project_slug": slug, "glb_path": glb }),
            })
            .map(Some)
    })
    .await
    .map_err(|e| format!("Lỗi kiểm ảnh xem trước: {e}"))?
}

#[tauri::command]
async fn gpu_release_vram(comfyui_url: Option<String>) -> Result<VramReleaseResult, String> {
    Ok(release_comfyui_vram(comfyui_url.as_deref()).await)
}

#[tauri::command]
async fn sync_get_config() -> Result<SelorsonConnectionConfig, String> {
    tokio::task::spawn_blocking(|| {
        let conn = open_akunarch_db()?;
        Ok(get_selorson_config(&conn))
    })
    .await
    .map_err(|e| format!("Lỗi đọc cấu hình Selorson: {e}"))?
}

#[tauri::command]
async fn sync_save_config(
    base_url: String,
    token: Option<String>,
) -> Result<SelorsonConnectionConfig, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        save_selorson_config(&conn, &base_url, token.as_deref())
    })
    .await
    .map_err(|e| format!("Lỗi lưu cấu hình Selorson: {e}"))?
}

#[tauri::command]
async fn sync_login_selorson(
    base_url: String,
    email: String,
    password: String,
) -> Result<Value, String> {
    let db_path = akunarch_db_path();
    login_to_selorson(&db_path, &base_url, &email, &password).await
}

#[tauri::command]
async fn sync_fetch_overview(base_url: Option<String>) -> Result<Value, String> {
    let db_path = akunarch_db_path();
    fetch_selorson_world_overview(&db_path, base_url.as_deref()).await
}

#[tauri::command]
async fn sync_audit_project(
    slug: String,
    force_draft: Option<bool>,
) -> Result<QaAuditReport, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        let proj = get_project_by_slug(&conn, &slug)?
            .ok_or_else(|| format!("Không tìm thấy dự án '{slug}'."))?;
        Ok(audit_project_for_sync(
            &proj.manifest,
            force_draft.unwrap_or(true),
        ))
    })
    .await
    .map_err(|e| format!("Lỗi kiểm định QA dự án: {e}"))?
}

#[tauri::command]
async fn sync_push_project(
    slug: String,
    force_draft: Option<bool>,
    base_url: Option<String>,
) -> Result<Value, String> {
    let db_path = akunarch_db_path();
    push_project_to_selorson(&db_path, &slug, force_draft, base_url.as_deref()).await
}

#[tauri::command]
async fn sync_list_logs(limit: Option<usize>) -> Result<Vec<SyncLogRow>, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        list_sync_logs(&conn, limit.unwrap_or(30))
    })
    .await
    .map_err(|e| format!("Lỗi đọc lịch sử đồng bộ: {e}"))?
}

#[tauri::command]
async fn media_read_data_uri(path: String) -> Result<String, String> {
    tokio::task::spawn_blocking(move || media_protocol::read_media_data_uri(&path))
        .await
        .map_err(|e| format!("Lỗi đọc dữ liệu ảnh cục bộ: {e}"))?
}

#[tauri::command]
async fn chunks_generate_terrain(
    slug: String,
    biome: Option<String>,
    amplitude_scale: Option<f64>,
) -> Result<ChunkStitchReport, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        generate_chunk_terrain(&conn, &slug, biome.as_deref(), amplitude_scale)
    })
    .await
    .map_err(|e| format!("Lỗi khởi tạo địa hình Chunk: {e}"))?
}

#[tauri::command]
async fn chunks_sculpt_terrain(
    slug: String,
    local_x: f64,
    local_z: f64,
    radius_m: f64,
    strength_or_target: f32,
    brush_mode: String,
) -> Result<ChunkStitchReport, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        sculpt_chunk_terrain(
            &conn,
            &slug,
            local_x,
            local_z,
            radius_m,
            strength_or_target,
            &brush_mode,
        )
    })
    .await
    .map_err(|e| format!("Lỗi điêu khắc địa hình Chunk: {e}"))?
}

#[tauri::command]
async fn chunks_stitch_neighbors(slug: String) -> Result<ChunkStitchReport, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        stitch_chunk_with_neighbors_in_root(&conn, &akunarch_projects_root(), &slug)
    })
    .await
    .map_err(|e| format!("Lỗi khâu biên liền mạch Chunk: {e}"))?
}

#[tauri::command]
async fn chunks_pack_zip(slug: String) -> Result<ChunkPackResult, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        pack_chunk_zip(&conn, &slug)
    })
    .await
    .map_err(|e| format!("Lỗi đóng gói chunk_<planet>_<x>_<z>.zip: {e}"))?
}

#[tauri::command]
async fn vn_load_episode(slug: String) -> Result<VnEpisodeDocument, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        load_or_init_vn_episode(&conn, &slug)
    })
    .await
    .map_err(|e| format!("Lỗi đọc kịch bản Visual Novel: {e}"))?
}

#[tauri::command]
async fn vn_save_episode(
    slug: String,
    episode: VnEpisodeDocument,
) -> Result<VnSaveResult, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        save_vn_episode(&conn, &slug, episode)
    })
    .await
    .map_err(|e| format!("Lỗi lưu kịch bản Visual Novel: {e}"))?
}

#[tauri::command]
async fn vn_pack_episode(slug: String) -> Result<VnPackResult, String> {
    tokio::task::spawn_blocking(move || {
        let conn = open_akunarch_db()?;
        pack_vn_episode_zip(&conn, &slug)
    })
    .await
    .map_err(|e| format!("Lỗi đóng gói vn_episode_<slug>.zip: {e}"))?
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    // Initialize akunarch.db and projects directory early
    if let Ok(conn) = open_akunarch_db() {
        let _ = rescan_projects_from_disk(&conn);
    }

    let gpu_queue = GpuJobQueue::default_live();
    let gpu_queue_for_setup = gpu_queue.clone();

    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .register_uri_scheme_protocol("akunmedia", |_ctx, request| {
            media_protocol::handle_akunmedia_request(request)
        })
        .manage(AppState { gpu_queue })
        .setup(move |app| {
            // B2: hàng đợi GPU phát `akunarch://gpu-job-starting` để UI nhường VRAM WebGL trước job nặng
            let handle = app.handle().clone();
            gpu_queue_for_setup.set_job_start_notifier(Box::new(move |payload| {
                use tauri::Emitter;
                handle.emit("akunarch://gpu-job-starting", payload).is_ok()
            }));
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            studio_bootstrap,
            vault_get_snapshot,
            vault_get_manga_pages,
            vault_scan_local_assets,
            projects_list,
            projects_rescan,
            projects_create,
            projects_update,
            projects_export_bundle,
            projects_import_external_file,
            projects_upload_asset_bytes,
            projects_save_manga_plates,
            projects_list_ai_meshes,
            projects_open_folder,
            gpu_hardware_report,
            gpu_list_jobs,
            gpu_enqueue_job,
            gpu_cancel_job,
            gpu_release_vram,
            projects_ensure_preview_card,
            sync_get_config,
            sync_save_config,
            sync_login_selorson,
            sync_fetch_overview,
            sync_audit_project,
            sync_push_project,
            sync_list_logs,
            media_read_data_uri,
            chunks_generate_terrain,
            chunks_sculpt_terrain,
            chunks_stitch_neighbors,
            chunks_pack_zip,
            vn_load_episode,
            vn_save_episode,
            vn_pack_episode,
        ])
        .run(tauri::generate_context!())
        .expect("Lỗi khởi chạy Akunarch Studio");
}
