use crate::db::akunarch_projects_root;
use base64::Engine;
use chrono::Utc;
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::io::Write;
use std::path::{Path, PathBuf};
use zip::write::SimpleFileOptions;

pub const PROJECT_SUBDIRS: &[&str] = &[
    "concepts",
    "audio",
    "clockwork",
    "manga_plates",
    "chunks",
    "stage_vn",
    "cinema",
    "dist",
];

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MangaPlateCapture {
    pub id: String,
    pub label: String,
    pub beauty_path: String,
    pub depth_path: String,
    pub width: u32,
    pub height: u32,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AiMeshEntry {
    pub file_name: String,
    pub stem: String,
    pub glb_path: String,
    pub size_bytes: u64,
    pub concept_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MangaPlateExportResult {
    pub plate: MangaPlateCapture,
    pub beauty_plate_path: String,
    pub depth_map_path: String,
    pub project: ProjectRecord,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ClockworkConfig {
    #[serde(default)]
    pub parts: Vec<Value>,
    pub glb_path: Option<String>,
    pub intro_video_path: Option<String>,
    #[serde(default = "default_version")]
    pub pack_version: String,
    /// Kế hoạch VRAM v2 · C2: ảnh xem trước 1920×1080 render bằng Blender cho thẻ Chờ 2D.
    #[serde(default)]
    pub preview_render_path: Option<String>,
    /// P0: bản CƠ KHÍ (sa bàn đồng hồ, có animation `assemble` / `idle`) — `glb_path` vẫn là bản thật.
    #[serde(default)]
    pub mechanism_glb_path: Option<String>,
}

impl Default for ClockworkConfig {
    fn default() -> Self {
        Self {
            parts: Vec::new(),
            glb_path: None,
            intro_video_path: None,
            pack_version: default_version(),
            preview_render_path: None,
            mechanism_glb_path: None,
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkPlacementItem {
    pub id: String,
    #[serde(default, alias = "title")]
    pub label: String,
    #[serde(default, alias = "slug")]
    pub slug_ref: Option<String>,
    pub glb_path: String,
    #[serde(default)]
    pub x: f64,
    #[serde(default)]
    pub y: f64,
    #[serde(default)]
    pub z: f64,
    #[serde(default)]
    pub rot_y_deg: f64,
    #[serde(default = "default_unit_scale")]
    pub scale: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AmbientAudioZone {
    pub id: String,
    pub label: String,
    pub audio_path: String,
    #[serde(default)]
    pub x: f64,
    #[serde(default)]
    pub z: f64,
    #[serde(default = "default_audio_zone_radius")]
    pub radius: f64,
    #[serde(default = "default_audio_zone_volume")]
    pub volume: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChunkConfig {
    pub pack_zip_path: Option<String>,
    pub heightmap_path: Option<String>,
    #[serde(default)]
    pub splat_path: Option<String>,
    #[serde(default = "default_water_level")]
    pub water_level: f64,
    #[serde(default = "default_foliage_density")]
    pub foliage_density: f64,
    #[serde(default = "default_chunk_grid_res")]
    pub grid_resolution: usize,
    #[serde(default)]
    pub heightmap_values: Vec<f32>,
    #[serde(default)]
    pub placements: Vec<ChunkPlacementItem>,
    #[serde(default)]
    pub audio_zones: Vec<AmbientAudioZone>,
    #[serde(default = "default_version")]
    pub pack_version: String,
    #[serde(default)]
    pub spawn_points: Vec<Value>,
    #[serde(default)]
    pub vn_triggers: Vec<Value>,
}

impl Default for ChunkConfig {
    fn default() -> Self {
        Self {
            pack_zip_path: None,
            heightmap_path: None,
            splat_path: None,
            water_level: default_water_level(),
            foliage_density: default_foliage_density(),
            grid_resolution: default_chunk_grid_res(),
            heightmap_values: Vec::new(),
            placements: Vec::new(),
            audio_zones: Vec::new(),
            pack_version: default_version(),
            spawn_points: Vec::new(),
            vn_triggers: Vec::new(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StageVnConfig {
    pub episode_zip_path: Option<String>,
    pub episode_title: Option<String>,
    #[serde(default)]
    pub episode_json_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CinemaCameraKeyframe {
    #[serde(default)]
    pub id: String,
    pub time_sec: f64,
    pub pos: [f64; 3],
    pub target: [f64; 3],
    #[serde(default = "default_cinema_fov")]
    pub fov_deg: f64,
    #[serde(default)]
    pub explode_pct: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CinemaSubtitleCue {
    pub id: String,
    pub start_sec: f64,
    pub end_sec: f64,
    #[serde(default)]
    pub text_vi: String,
    #[serde(default)]
    pub text_en: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CinemaConfig {
    pub video_path: Option<String>,
    pub thumbnail_path: Option<String>,
    #[serde(default = "default_video_type")]
    pub video_type: String,
    pub episode_number: Option<i32>,
    #[serde(default = "default_cinema_duration")]
    pub duration_sec: f64,
    #[serde(default = "default_cinema_fps")]
    pub fps: u32,
    #[serde(default = "default_vfx_preset")]
    pub vfx_preset: String,
    #[serde(default)]
    pub vfx_overlay_path: Option<String>,
    #[serde(default)]
    pub comfyui_enabled: bool,
    #[serde(default)]
    pub comfyui_prompt: String,
    #[serde(default)]
    pub source_glb_path: Option<String>,
    #[serde(default)]
    pub voice_track_path: Option<String>,
    #[serde(default)]
    pub bgm_track_path: Option<String>,
    #[serde(default)]
    pub mastered_audio_path: Option<String>,
    #[serde(default)]
    pub mastered_lufs: Option<f32>,
    #[serde(default)]
    pub mastered_true_peak_dbtp: Option<f32>,
    #[serde(default)]
    pub keyframes: Vec<CinemaCameraKeyframe>,
    #[serde(default)]
    pub subtitles: Vec<CinemaSubtitleCue>,
}

impl Default for CinemaConfig {
    fn default() -> Self {
        Self {
            video_path: None,
            thumbnail_path: None,
            video_type: default_video_type(),
            episode_number: None,
            duration_sec: default_cinema_duration(),
            fps: default_cinema_fps(),
            vfx_preset: default_vfx_preset(),
            vfx_overlay_path: None,
            comfyui_enabled: false,
            comfyui_prompt: String::new(),
            source_glb_path: None,
            voice_track_path: None,
            bgm_track_path: None,
            mastered_audio_path: None,
            mastered_lufs: None,
            mastered_true_peak_dbtp: None,
            keyframes: Vec::new(),
            subtitles: Vec::new(),
        }
    }
}

fn default_unit_scale() -> f64 {
    1.0
}
fn default_audio_zone_radius() -> f64 {
    45.0
}
fn default_audio_zone_volume() -> f64 {
    0.85
}
fn default_water_level() -> f64 {
    1.6
}
fn default_foliage_density() -> f64 {
    0.65
}
fn default_chunk_grid_res() -> usize {
    65
}
fn default_cinema_fov() -> f64 {
    38.0
}
fn default_cinema_duration() -> f64 {
    8.0
}
fn default_cinema_fps() -> u32 {
    24
}
fn default_vfx_preset() -> String {
    "arcane_embers".to_string()
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncPolicyConfig {
    #[serde(default = "default_source_app")]
    pub source_app: String,
    #[serde(default = "default_true")]
    pub force_draft: bool,
}

impl Default for SyncPolicyConfig {
    fn default() -> Self {
        Self {
            source_app: default_source_app(),
            force_draft: true,
        }
    }
}

fn default_schema_version() -> String {
    "1.0".to_string()
}
fn default_version() -> String {
    "0.1.0".to_string()
}
fn default_video_type() -> String {
    "intro".to_string()
}
fn default_source_app() -> String {
    "Akunarch".to_string()
}
fn default_true() -> bool {
    true
}
fn default_world_size() -> f64 {
    256.0
}
fn default_planet() -> String {
    "akunalia".to_string()
}
fn default_kind() -> String {
    "clockwork".to_string()
}
fn default_biome() -> String {
    "temperate".to_string()
}
fn default_unlock_chapter() -> i32 {
    1
}

/// Canonical `project.akun.json` stored on disk in `E:\Akunarch\projects\<slug>\project.akun.json`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectManifest {
    #[serde(default = "default_schema_version")]
    pub schema_version: String,
    pub slug: String,
    pub title: String,
    #[serde(default)]
    pub title_en: String,
    #[serde(default = "default_kind")]
    pub kind: String,
    #[serde(default = "default_planet")]
    pub planet: String,
    #[serde(default)]
    pub region_slug: String,
    #[serde(default)]
    pub era: String,
    pub era_year: Option<i64>,
    pub lat: Option<f64>,
    pub lng: Option<f64>,
    #[serde(default = "default_biome")]
    pub biome: String,
    #[serde(default)]
    pub chunk_x: i32,
    #[serde(default)]
    pub chunk_z: i32,
    #[serde(default = "default_world_size")]
    pub world_size: f64,
    pub cowriter_entity_id: Option<i64>,
    #[serde(default)]
    pub cowriter_key: String,
    #[serde(default = "default_unlock_chapter")]
    pub unlock_chapter: i32,
    #[serde(default)]
    pub description_vi: String,
    #[serde(default)]
    pub description_en: String,
    pub local_image_path: Option<String>,
    #[serde(default)]
    pub concept_paths: Vec<String>,
    #[serde(default)]
    pub bgm_audio_path: Option<String>,
    #[serde(default)]
    pub audio_paths: Vec<String>,
    #[serde(default)]
    pub manga_plates: Vec<MangaPlateCapture>,
    #[serde(default)]
    pub clockwork: ClockworkConfig,
    #[serde(default)]
    pub chunks: ChunkConfig,
    #[serde(default)]
    pub stage_vn: StageVnConfig,
    #[serde(default)]
    pub cinema: CinemaConfig,
    #[serde(default)]
    pub sync_policy: SyncPolicyConfig,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectRecord {
    pub id: i64,
    pub slug: String,
    pub title: String,
    pub kind: String,
    pub planet: String,
    pub region_slug: String,
    pub cowriter_entity_id: Option<i64>,
    pub chapter_no: Option<i32>,
    pub folder_path: String,
    pub manifest_path: String,
    pub status: String,
    pub last_synced_at: Option<String>,
    pub created_at: String,
    pub updated_at: String,
    pub manifest: ProjectManifest,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CreateProjectInput {
    pub slug: String,
    pub title: String,
    #[serde(default)]
    pub title_en: String,
    #[serde(default = "default_kind")]
    pub kind: String,
    #[serde(default = "default_planet")]
    pub planet: String,
    #[serde(default)]
    pub region_slug: String,
    #[serde(default)]
    pub era: String,
    pub era_year: Option<i64>,
    pub lat: Option<f64>,
    pub lng: Option<f64>,
    #[serde(default = "default_biome")]
    pub biome: String,
    #[serde(default)]
    pub chunk_x: i32,
    #[serde(default)]
    pub chunk_z: i32,
    pub cowriter_entity_id: Option<i64>,
    #[serde(default)]
    pub cowriter_key: String,
    pub unlock_chapter: Option<i32>,
    #[serde(default)]
    pub description_vi: String,
    #[serde(default)]
    pub description_en: String,
    pub local_image_path: Option<String>,
    #[serde(default)]
    pub concept_paths: Vec<String>,
    #[serde(default)]
    pub bgm_audio_path: Option<String>,
    #[serde(default)]
    pub glb_path: Option<String>,
}

fn fold_char_to_ascii(ch: char) -> Option<char> {
    if ch.is_ascii_alphanumeric() {
        return Some(ch.to_ascii_lowercase());
    }
    let mapped = match ch {
        'à' | 'á' | 'ạ' | 'ả' | 'ã' | 'â' | 'ầ' | 'ấ' | 'ậ' | 'ẩ' | 'ẫ' | 'ă' | 'ằ' | 'ắ'
        | 'ặ' | 'ẳ' | 'ẵ' | 'À' | 'Á' | 'Ạ' | 'Ả' | 'Ã' | 'Â' | 'Ầ' | 'Ấ' | 'Ậ' | 'Ẩ' | 'Ẫ'
        | 'Ă' | 'Ằ' | 'Ắ' | 'Ặ' | 'Ẳ' | 'Ẵ' | 'ä' | 'Ä' | 'å' | 'Å' => 'a',
        'è' | 'é' | 'ẹ' | 'ẻ' | 'ẽ' | 'ê' | 'ề' | 'ế' | 'ệ' | 'ể' | 'ễ' | 'È' | 'É' | 'Ẹ'
        | 'Ẻ' | 'Ẽ' | 'Ê' | 'Ề' | 'Ế' | 'Ệ' | 'Ể' | 'Ễ' | 'ë' | 'Ë' => 'e',
        'ì' | 'í' | 'ị' | 'ỉ' | 'ĩ' | 'Ì' | 'Í' | 'Ị' | 'Ỉ' | 'Ĩ' | 'î' | 'ï' | 'Î' | 'Ï' => 'i',
        'ò' | 'ó' | 'ọ' | 'ỏ' | 'õ' | 'ô' | 'ồ' | 'ố' | 'ộ' | 'ổ' | 'ỗ' | 'ơ' | 'ờ' | 'ớ'
        | 'ợ' | 'ở' | 'ỡ' | 'Ò' | 'Ó' | 'Ọ' | 'Ỏ' | 'Õ' | 'Ô' | 'Ồ' | 'Ố' | 'Ộ' | 'Ổ' | 'Ỗ'
        | 'Ơ' | 'Ờ' | 'Ớ' | 'Ợ' | 'Ở' | 'Ỡ' | 'ö' | 'Ö' => 'o',
        'ù' | 'ú' | 'ụ' | 'ủ' | 'ũ' | 'ư' | 'ừ' | 'ứ' | 'ự' | 'ử' | 'ữ' | 'Ù' | 'Ú' | 'Ụ'
        | 'Ủ' | 'Ũ' | 'Ư' | 'Ừ' | 'Ứ' | 'Ự' | 'Ử' | 'Ữ' | 'ü' | 'Ü' | 'û' | 'Û' => 'u',
        'ỳ' | 'ý' | 'ỵ' | 'ỷ' | 'ỹ' | 'Ỳ' | 'Ý' | 'Ỵ' | 'Ỷ' | 'Ỹ' => 'y',
        'đ' | 'Đ' => 'd',
        'ç' | 'Ç' => 'c',
        'ñ' | 'Ñ' => 'n',
        _ => return None,
    };
    Some(mapped)
}

/// Sanitizes and validates a project slug (`[a-z0-9-]+`), folding Vietnamese/Latin diacritics,
/// blocking empty slugs, path traversal, and Windows reserved device names (`CON`, `PRN`, `AUX`, `NUL`, `COM1..9`, `LPT1..9`).
pub fn sanitize_project_slug(raw: &str) -> Result<String, String> {
    let mut out = String::with_capacity(raw.len());
    let mut prev_dash = false;
    for ch in raw.trim().chars() {
        if let Some(ascii) = fold_char_to_ascii(ch) {
            out.push(ascii);
            prev_dash = false;
        } else if matches!(ch, '-' | '_' | ' ' | '.' | '/' | '\\' | ':')
            && !out.is_empty()
            && !prev_dash
        {
            out.push('-');
            prev_dash = true;
        }
    }
    while out.ends_with('-') {
        out.pop();
    }
    if out.len() < 2 {
        return Err("Slug dự án phải dài tối thiểu 2 ký tự chữ/số ASCII (ví dụ: temple-of-zyberon).".to_string());
    }
    if out.len() > 80 {
        out.truncate(80);
        while out.ends_with('-') {
            out.pop();
        }
    }
    let upper = out.to_ascii_uppercase();
    const RESERVED: &[&str] = &[
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8",
        "COM9", "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    ];
    if RESERVED.contains(&upper.as_str()) {
        return Err(format!("Slug '{out}' trùng tên thiết bị hệ thống Windows bị cấm."));
    }
    Ok(out)
}

pub fn validate_kind(kind: &str) -> Result<String, String> {
    let k = kind.trim().to_ascii_lowercase();
    if matches!(k.as_str(), "clockwork" | "open_world" | "vn_episode" | "cinema") {
        Ok(k)
    } else {
        Err(format!(
            "Loại dự án '{kind}' không hợp lệ (chỉ nhận clockwork | open_world | vn_episode | cinema)."
        ))
    }
}

pub fn validate_planet(planet: &str) -> Result<String, String> {
    let p = planet.trim().to_ascii_lowercase();
    if matches!(p.as_str(), "akunalia" | "earth") {
        Ok(p)
    } else {
        Err(format!(
            "Hành tinh '{planet}' không hợp lệ (chỉ nhận akunalia | earth)."
        ))
    }
}

pub fn ensure_project_folder_tree(projects_root: &Path, slug: &str) -> Result<PathBuf, String> {
    std::fs::create_dir_all(projects_root)
        .map_err(|e| format!("Không tạo được thư mục gốc projects {}: {e}", projects_root.display()))?;
    let folder = projects_root.join(slug);
    std::fs::create_dir_all(&folder)
        .map_err(|e| format!("Không tạo được thư mục dự án {}: {e}", folder.display()))?;
    for sub in PROJECT_SUBDIRS {
        std::fs::create_dir_all(folder.join(sub))
            .map_err(|e| format!("Không tạo được thư mục con {sub}: {e}"))?;
    }
    Ok(folder)
}

pub fn create_project(conn: &Connection, input: CreateProjectInput) -> Result<ProjectRecord, String> {
    create_project_in_root(conn, &akunarch_projects_root(), input)
}

pub fn create_project_in_root(
    conn: &Connection,
    projects_root: &Path,
    input: CreateProjectInput,
) -> Result<ProjectRecord, String> {
    let slug = sanitize_project_slug(&input.slug)?;
    let title = input.title.trim().to_string();
    if title.is_empty() {
        return Err("Tên dự án không được để trống.".to_string());
    }
    let kind = validate_kind(&input.kind)?;
    let planet = validate_planet(&input.planet)?;

    let existing: Option<i64> = conn
        .query_row(
            "SELECT id FROM projects WHERE slug = ?1",
            params![slug],
            |r| r.get(0),
        )
        .optional()
        .map_err(|e| e.to_string())?;
    if existing.is_some() {
        return Err(format!("Dự án có slug '{slug}' đã tồn tại trong Akunarch."));
    }

    let folder = ensure_project_folder_tree(projects_root, &slug)?;
    let unlock_chapter = input.unlock_chapter.unwrap_or(1).max(1);

    let manifest = ProjectManifest {
        schema_version: "2.0".to_string(),
        slug: slug.clone(),
        title: title.clone(),
        title_en: input.title_en.trim().to_string(),
        kind: kind.clone(),
        planet: planet.clone(),
        region_slug: input.region_slug.trim().to_string(),
        era: input.era.trim().to_string(),
        era_year: input.era_year,
        lat: input.lat,
        lng: input.lng,
        biome: if input.biome.trim().is_empty() {
            "temperate".to_string()
        } else {
            input.biome.trim().to_string()
        },
        chunk_x: input.chunk_x,
        chunk_z: input.chunk_z,
        world_size: 256.0,
        cowriter_entity_id: input.cowriter_entity_id,
        cowriter_key: input.cowriter_key.trim().to_string(),
        unlock_chapter,
        description_vi: input.description_vi.trim().to_string(),
        description_en: input.description_en.trim().to_string(),
        local_image_path: input
            .local_image_path
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(String::from),
        concept_paths: input.concept_paths,
        bgm_audio_path: input
            .bgm_audio_path
            .as_deref()
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(String::from),
        audio_paths: Vec::new(),
        manga_plates: Vec::new(),
        clockwork: ClockworkConfig {
            glb_path: input
                .glb_path
                .as_deref()
                .map(str::trim)
                .filter(|s| !s.is_empty())
                .map(String::from),
            ..ClockworkConfig::default()
        },
        chunks: ChunkConfig::default(),
        stage_vn: StageVnConfig::default(),
        cinema: CinemaConfig::default(),
        sync_policy: SyncPolicyConfig {
            source_app: "Akunarch".to_string(),
            force_draft: true,
        },
    };

    write_manifest_file(&folder, &manifest)?;
    upsert_project_row_from_manifest(conn, &folder, &manifest, true)?;
    get_project_by_slug(conn, &slug)?.ok_or_else(|| "Không đọc lại được dự án vừa tạo.".to_string())
}

pub fn update_project_manifest(
    conn: &Connection,
    original_slug: Option<&str>,
    mut manifest: ProjectManifest,
) -> Result<ProjectRecord, String> {
    update_project_manifest_in_root(
        conn,
        &akunarch_projects_root(),
        original_slug,
        &mut manifest,
    )
}

fn relocate_single_path(p: &mut String, old_folder: &Path, new_folder: &Path) -> bool {
    let cur = Path::new(p.trim());
    if let Ok(rel) = cur.strip_prefix(old_folder) {
        *p = new_folder.join(rel).to_string_lossy().to_string();
        return true;
    }
    false
}

fn relocate_opt_path(opt: &mut Option<String>, old_folder: &Path, new_folder: &Path) -> bool {
    if let Some(ref mut s) = opt {
        return relocate_single_path(s, old_folder, new_folder);
    }
    false
}

fn relocate_manifest_paths(
    manifest: &mut ProjectManifest,
    old_folder: &Path,
    new_folder: &Path,
) -> bool {
    if old_folder == new_folder {
        return false;
    }
    let mut changed = false;
    changed |= relocate_opt_path(&mut manifest.local_image_path, old_folder, new_folder);
    for cp in &mut manifest.concept_paths {
        changed |= relocate_single_path(cp, old_folder, new_folder);
    }
    changed |= relocate_opt_path(&mut manifest.bgm_audio_path, old_folder, new_folder);
    for ap in &mut manifest.audio_paths {
        changed |= relocate_single_path(ap, old_folder, new_folder);
    }
    for mp in &mut manifest.manga_plates {
        changed |= relocate_single_path(&mut mp.beauty_path, old_folder, new_folder);
        changed |= relocate_single_path(&mut mp.depth_path, old_folder, new_folder);
    }
    changed |= relocate_opt_path(&mut manifest.clockwork.glb_path, old_folder, new_folder);
    changed |= relocate_opt_path(
        &mut manifest.clockwork.intro_video_path,
        old_folder,
        new_folder,
    );
    changed |= relocate_opt_path(&mut manifest.chunks.pack_zip_path, old_folder, new_folder);
    changed |= relocate_opt_path(&mut manifest.chunks.heightmap_path, old_folder, new_folder);
    changed |= relocate_opt_path(&mut manifest.chunks.splat_path, old_folder, new_folder);
    for pl in &mut manifest.chunks.placements {
        changed |= relocate_single_path(&mut pl.glb_path, old_folder, new_folder);
    }
    for az in &mut manifest.chunks.audio_zones {
        changed |= relocate_single_path(&mut az.audio_path, old_folder, new_folder);
    }
    changed |= relocate_opt_path(
        &mut manifest.stage_vn.episode_zip_path,
        old_folder,
        new_folder,
    );
    changed |= relocate_opt_path(
        &mut manifest.stage_vn.episode_json_path,
        old_folder,
        new_folder,
    );
    changed |= relocate_opt_path(&mut manifest.cinema.video_path, old_folder, new_folder);
    changed |= relocate_opt_path(&mut manifest.cinema.thumbnail_path, old_folder, new_folder);
    changed |= relocate_opt_path(&mut manifest.cinema.vfx_overlay_path, old_folder, new_folder);
    changed |= relocate_opt_path(&mut manifest.cinema.source_glb_path, old_folder, new_folder);
    changed |= relocate_opt_path(&mut manifest.cinema.voice_track_path, old_folder, new_folder);
    changed |= relocate_opt_path(&mut manifest.cinema.bgm_track_path, old_folder, new_folder);
    changed |= relocate_opt_path(
        &mut manifest.cinema.mastered_audio_path,
        old_folder,
        new_folder,
    );
    changed
}

pub fn update_project_manifest_in_root(
    conn: &Connection,
    projects_root: &Path,
    original_slug: Option<&str>,
    manifest: &mut ProjectManifest,
) -> Result<ProjectRecord, String> {
    let new_slug = sanitize_project_slug(&manifest.slug)?;
    manifest.slug = new_slug.clone();
    if manifest.title.trim().is_empty() {
        return Err("Tên dự án không được để trống.".to_string());
    }
    manifest.title = manifest.title.trim().to_string();
    manifest.kind = validate_kind(&manifest.kind)?;
    manifest.planet = validate_planet(&manifest.planet)?;
    manifest.unlock_chapter = manifest.unlock_chapter.max(1);
    if manifest.sync_policy.source_app.trim().is_empty() {
        manifest.sync_policy.source_app = "Akunarch".to_string();
    }

    let lookup_slug = original_slug
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .and_then(|s| sanitize_project_slug(s).ok())
        .unwrap_or_else(|| new_slug.clone());

    let prev_record = get_project_by_slug(conn, &lookup_slug)?;

    if lookup_slug != new_slug {
        if get_project_by_slug(conn, &new_slug)?.is_some() {
            return Err(format!(
                "Không thể đổi sang slug '{new_slug}' vì dự án khác đã sử dụng slug này."
            ));
        }
        let target_folder = projects_root.join(&new_slug);
        if !lookup_slug.eq_ignore_ascii_case(&new_slug) && target_folder.exists() {
            return Err(format!(
                "Thư mục dự án '{}' đã tồn tại trên ổ đĩa.",
                target_folder.display()
            ));
        }
        let old_folder = prev_record
            .as_ref()
            .map(|r| PathBuf::from(&r.folder_path))
            .unwrap_or_else(|| projects_root.join(&lookup_slug));
        if old_folder.exists() && !lookup_slug.eq_ignore_ascii_case(&new_slug) {
            std::fs::rename(&old_folder, &target_folder).map_err(|e| {
                format!(
                    "Không đổi tên được thư mục dự án sang {}: {e}",
                    target_folder.display()
                )
            })?;
        }
        relocate_manifest_paths(manifest, &old_folder, &target_folder);
        conn.execute(
            "UPDATE projects SET slug = ?2, folder_path = ?3 WHERE slug = ?1",
            params![
                lookup_slug,
                new_slug,
                target_folder.to_string_lossy().to_string()
            ],
        )
        .map_err(|e| format!("Lỗi cập nhật slug dự án trong akunarch.db: {e}"))?;
    }

    let folder = ensure_project_folder_tree(projects_root, &manifest.slug)?;
    write_manifest_file(&folder, manifest)?;
    upsert_project_row_from_manifest(conn, &folder, manifest, true)?;

    if let Some(prev) = prev_record {
        if prev.manifest.kind == "open_world"
            && (manifest.kind != "open_world"
                || manifest.planet != prev.manifest.planet
                || manifest.chunk_x != prev.manifest.chunk_x
                || manifest.chunk_z != prev.manifest.chunk_z)
        {
            let still_owned = list_projects(conn)?.iter().any(|other| {
                other.slug != new_slug
                    && other.manifest.kind == "open_world"
                    && other.manifest.planet == prev.manifest.planet
                    && other.manifest.chunk_x == prev.manifest.chunk_x
                    && other.manifest.chunk_z == prev.manifest.chunk_z
            });
            if !still_owned {
                let _ = conn.execute(
                    "DELETE FROM world_chunks WHERE planet = ?1 AND chunk_x = ?2 AND chunk_z = ?3",
                    params![
                        prev.manifest.planet,
                        prev.manifest.chunk_x,
                        prev.manifest.chunk_z
                    ],
                );
            }
        }
    }

    get_project_by_slug(conn, &manifest.slug)?
        .ok_or_else(|| "Không tìm thấy dự án sau khi cập nhật.".to_string())
}

fn write_manifest_file(folder: &Path, manifest: &ProjectManifest) -> Result<PathBuf, String> {
    let manifest_path = folder.join("project.akun.json");
    let pretty = serde_json::to_string_pretty(manifest)
        .map_err(|e| format!("Lỗi tuần tự hóa project.akun.json: {e}"))?;
    std::fs::write(&manifest_path, format!("{pretty}\n"))
        .map_err(|e| format!("Không ghi được {}: {e}", manifest_path.display()))?;
    Ok(manifest_path)
}

fn upsert_project_row_from_manifest(
    conn: &Connection,
    folder: &Path,
    manifest: &ProjectManifest,
    touch_updated_at: bool,
) -> Result<(), String> {
    let now = Utc::now().to_rfc3339();
    let folder_str = folder.to_string_lossy().to_string();
    let touch_flag: i32 = if touch_updated_at { 1 } else { 0 };

    conn.execute(
        "INSERT INTO projects (
            slug, title, kind, planet, region_slug, cowriter_entity_id, chapter_no,
            folder_path, status, created_at, updated_at
         )
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 'draft', ?9, ?9)
         ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            kind = excluded.kind,
            planet = excluded.planet,
            region_slug = excluded.region_slug,
            cowriter_entity_id = excluded.cowriter_entity_id,
            chapter_no = excluded.chapter_no,
            folder_path = excluded.folder_path,
            updated_at = CASE WHEN ?10 = 1 THEN excluded.updated_at ELSE projects.updated_at END",
        params![
            manifest.slug,
            manifest.title,
            manifest.kind,
            manifest.planet,
            manifest.region_slug,
            manifest.cowriter_entity_id,
            manifest.unlock_chapter,
            folder_str,
            now,
            touch_flag
        ],
    )
    .map_err(|e| format!("Không lưu được dự án vào akunarch.db: {e}"))?;

    if manifest.kind == "open_world" {
        let sp_json = serde_json::to_string(&manifest.chunks.spawn_points).unwrap_or_else(|_| "[]".into());
        let vt_json = serde_json::to_string(&manifest.chunks.vn_triggers).unwrap_or_else(|_| "[]".into());
        let pl_json = serde_json::to_string(&manifest.chunks.placements).unwrap_or_else(|_| "[]".into());
        let az_json = serde_json::to_string(&manifest.chunks.audio_zones).unwrap_or_else(|_| "[]".into());
        let hm_json = serde_json::to_string(&manifest.chunks.heightmap_values).unwrap_or_else(|_| "[]".into());
        conn.execute(
            "INSERT INTO world_chunks (
                planet, chunk_x, chunk_z, world_size, region_slug, biome, unlock_chapter,
                heightmap_path, pack_zip_path, pack_version, spawn_points_json, vn_triggers_json,
                splat_path, water_level, foliage_density, placements_json, audio_zones_json, heightmap_grid_json
             )
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18)
             ON CONFLICT(planet, chunk_x, chunk_z) DO UPDATE SET
                world_size = excluded.world_size,
                region_slug = excluded.region_slug,
                biome = excluded.biome,
                unlock_chapter = excluded.unlock_chapter,
                heightmap_path = excluded.heightmap_path,
                pack_zip_path = excluded.pack_zip_path,
                pack_version = excluded.pack_version,
                spawn_points_json = excluded.spawn_points_json,
                vn_triggers_json = excluded.vn_triggers_json,
                splat_path = excluded.splat_path,
                water_level = excluded.water_level,
                foliage_density = excluded.foliage_density,
                placements_json = excluded.placements_json,
                audio_zones_json = excluded.audio_zones_json,
                heightmap_grid_json = excluded.heightmap_grid_json",
            params![
                manifest.planet,
                manifest.chunk_x,
                manifest.chunk_z,
                manifest.world_size,
                manifest.region_slug,
                manifest.biome,
                manifest.unlock_chapter,
                manifest.chunks.heightmap_path.clone().unwrap_or_default(),
                manifest.chunks.pack_zip_path.clone().unwrap_or_default(),
                manifest.chunks.pack_version,
                sp_json,
                vt_json,
                manifest.chunks.splat_path.clone().unwrap_or_default(),
                manifest.chunks.water_level,
                manifest.chunks.foliage_density,
                pl_json,
                az_json,
                hm_json,
            ],
        )
        .map_err(|e| format!("Không đồng bộ được ô world_chunks: {e}"))?;
    }

    Ok(())
}

/// Scans `E:\Akunarch\projects\*\project.akun.json` so edits made directly on disk via Vibecode
/// are immediately synchronized into `akunarch.db`.
pub fn rescan_projects_from_disk(conn: &Connection) -> Result<Vec<ProjectRecord>, String> {
    rescan_projects_in_root(conn, &akunarch_projects_root())
}

pub fn rescan_projects_in_root(
    conn: &Connection,
    projects_root: &Path,
) -> Result<Vec<ProjectRecord>, String> {
    std::fs::create_dir_all(projects_root)
        .map_err(|e| format!("Không mở được thư mục projects {}: {e}", projects_root.display()))?;

    let mut discovered_slugs = std::collections::HashSet::new();

    if let Ok(entries) = std::fs::read_dir(projects_root) {
        let mut folders: Vec<PathBuf> = entries
            .flatten()
            .map(|e| e.path())
            .filter(|p| p.is_dir())
            .collect();
        folders.sort();

        for folder in folders {
            let manifest_file = folder.join("project.akun.json");
            if !manifest_file.is_file() {
                continue;
            }
            let Ok(raw) = std::fs::read_to_string(&manifest_file) else {
                continue;
            };
            let Ok(mut manifest) = serde_json::from_str::<ProjectManifest>(&raw) else {
                continue;
            };

            let folder_name = folder
                .file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("")
                .to_string();
            let raw_slug_candidate = if manifest.slug.trim().is_empty() {
                folder_name.as_str()
            } else {
                manifest.slug.as_str()
            };
            let Ok(mut clean_slug) = sanitize_project_slug(raw_slug_candidate) else {
                continue;
            };
            let Ok(clean_kind) = validate_kind(&manifest.kind) else {
                continue;
            };
            let Ok(clean_planet) = validate_planet(&manifest.planet) else {
                continue;
            };
            if manifest.title.trim().is_empty() {
                manifest.title = clean_slug.clone();
            } else {
                manifest.title = manifest.title.trim().to_string();
            }
            manifest.kind = clean_kind;
            manifest.planet = clean_planet;
            manifest.unlock_chapter = manifest.unlock_chapter.max(1);
            if manifest.sync_policy.source_app.trim().is_empty() {
                manifest.sync_policy.source_app = "Akunarch".to_string();
            }

            // Reconcile folder name <-> manifest.slug when edited on disk via Vibecode
            let old_folder_str = folder.to_string_lossy().to_string();
            let mut active_folder = folder.clone();
            if !folder_name.eq_ignore_ascii_case(&clean_slug) {
                let target_folder = projects_root.join(&clean_slug);
                if !target_folder.exists() && !discovered_slugs.contains(&clean_slug) {
                    if std::fs::rename(&folder, &target_folder).is_ok() {
                        active_folder = target_folder;
                    } else if let Ok(fallback_slug) = sanitize_project_slug(&folder_name) {
                        clean_slug = fallback_slug;
                    }
                } else if let Ok(fallback_slug) = sanitize_project_slug(&folder_name) {
                    // Another folder already owns `clean_slug`; preserve both projects safely using folder name
                    if !discovered_slugs.contains(&fallback_slug) {
                        clean_slug = fallback_slug;
                    } else {
                        continue;
                    }
                } else {
                    continue;
                }
            } else if folder_name != clean_slug {
                // Case-only normalization on Windows
                active_folder = projects_root.join(&clean_slug);
            }

            let relocated = relocate_manifest_paths(&mut manifest, &folder, &active_folder);
            let needs_manifest_rewrite =
                manifest.slug != clean_slug || active_folder != folder || relocated;
            manifest.slug = clean_slug.clone();

            let _ = ensure_project_folder_tree(projects_root, &clean_slug);
            if needs_manifest_rewrite {
                let _ = write_manifest_file(&active_folder, &manifest);
            }

            // If this folder previously existed in DB under a different slug, update that row in-place
            // so project `id` (and foreign keys in gpu_jobs / sync_logs) stay intact!
            if let Ok(Some((existing_id, existing_slug))) = conn
                .query_row(
                    "SELECT id, slug FROM projects WHERE folder_path = ?1",
                    params![old_folder_str],
                    |r| Ok((r.get::<_, i64>(0)?, r.get::<_, String>(1)?)),
                )
                .optional()
            {
                if existing_slug != clean_slug {
                    let slug_taken: Option<i64> = conn
                        .query_row(
                            "SELECT id FROM projects WHERE slug = ?1",
                            params![clean_slug],
                            |r| r.get(0),
                        )
                        .optional()
                        .ok()
                        .flatten();
                    if slug_taken.is_none() {
                        let _ = conn.execute(
                            "UPDATE projects SET slug = ?2, folder_path = ?3 WHERE id = ?1",
                            params![
                                existing_id,
                                clean_slug,
                                active_folder.to_string_lossy().to_string()
                            ],
                        );
                    }
                }
            }

            if upsert_project_row_from_manifest(conn, &active_folder, &manifest, needs_manifest_rewrite).is_ok() {
                discovered_slugs.insert(clean_slug);
            }
        }
    }

    // Prune ghost rows whose project.akun.json was deleted from disk under projects_root
    let mut stale_ids: Vec<i64> = Vec::new();
    if let Ok(mut stmt) = conn.prepare("SELECT id, slug, folder_path FROM projects") {
        if let Ok(rows) = stmt.query_map([], |r| {
            Ok((
                r.get::<_, i64>(0)?,
                r.get::<_, String>(1)?,
                r.get::<_, String>(2)?,
            ))
        }) {
            for row in rows.flatten() {
                let (pid, pslug, fpath) = row;
                let fp = Path::new(&fpath);
                let in_this_root = fp.starts_with(projects_root);
                let manifest_exists = fp.join("project.akun.json").is_file();
                if (in_this_root && !discovered_slugs.contains(&pslug)) || !manifest_exists {
                    stale_ids.push(pid);
                }
            }
        }
    }
    for pid in stale_ids {
        let _ = conn.execute(
            "UPDATE gpu_jobs SET project_id = NULL WHERE project_id = ?1",
            params![pid],
        );
        let _ = conn.execute(
            "UPDATE sync_logs SET project_id = NULL WHERE project_id = ?1",
            params![pid],
        );
        let _ = conn.execute("DELETE FROM projects WHERE id = ?1", params![pid]);
    }

    list_projects(conn)
}

pub fn list_projects(conn: &Connection) -> Result<Vec<ProjectRecord>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT id, slug, title, kind, planet, region_slug, cowriter_entity_id, chapter_no,
                    folder_path, status, last_synced_at, created_at, updated_at
             FROM projects
             ORDER BY updated_at DESC, id DESC",
        )
        .map_err(|e| format!("Lỗi đọc danh sách dự án: {e}"))?;

    let rows = stmt
        .query_map([], |r| {
            let slug: String = r.get(1)?;
            let title: String = r.get(2)?;
            let kind: String = r.get(3)?;
            let planet: String = r.get(4)?;
            let region_slug: String = r.get(5)?;
            let cowriter_entity_id: Option<i64> = r.get(6)?;
            let chapter_no: Option<i32> = r.get(7)?;
            let folder_path: String = r.get(8)?;
            let manifest_path_buf = Path::new(&folder_path).join("project.akun.json");
            let manifest = std::fs::read_to_string(&manifest_path_buf)
                .ok()
                .and_then(|raw| serde_json::from_str::<ProjectManifest>(&raw).ok())
                .unwrap_or_else(|| ProjectManifest {
                    schema_version: "1.0".to_string(),
                    slug: slug.clone(),
                    title: title.clone(),
                    title_en: String::new(),
                    kind: kind.clone(),
                    planet: planet.clone(),
                    region_slug: region_slug.clone(),
                    era: String::new(),
                    era_year: None,
                    lat: None,
                    lng: None,
                    biome: "temperate".to_string(),
                    chunk_x: 0,
                    chunk_z: 0,
                    world_size: 256.0,
                    cowriter_entity_id,
                    cowriter_key: String::new(),
                    unlock_chapter: chapter_no.unwrap_or(1),
                    description_vi: String::new(),
                    description_en: String::new(),
                    local_image_path: None,
                    concept_paths: Vec::new(),
                    bgm_audio_path: None,
                    audio_paths: Vec::new(),
                    manga_plates: Vec::new(),
                    clockwork: ClockworkConfig::default(),
                    chunks: ChunkConfig::default(),
                    stage_vn: StageVnConfig::default(),
                    cinema: CinemaConfig::default(),
                    sync_policy: SyncPolicyConfig::default(),
                });

            Ok(ProjectRecord {
                id: r.get(0)?,
                slug,
                title,
                kind,
                planet,
                region_slug,
                cowriter_entity_id,
                chapter_no,
                folder_path,
                manifest_path: manifest_path_buf.to_string_lossy().to_string(),
                status: r.get(9)?,
                last_synced_at: r.get(10)?,
                created_at: r.get(11)?,
                updated_at: r.get(12)?,
                manifest,
            })
        })
        .map_err(|e| format!("Lỗi duyệt danh sách dự án: {e}"))?;

    let mut out = Vec::new();
    for row in rows {
        out.push(row.map_err(|e| e.to_string())?);
    }
    Ok(out)
}

pub fn get_project_by_slug(conn: &Connection, slug: &str) -> Result<Option<ProjectRecord>, String> {
    let all = list_projects(conn)?;
    Ok(all.into_iter().find(|p| p.slug == slug))
}

pub fn export_project_akunbundle(conn: &Connection, slug: &str) -> Result<String, String> {
    let project = get_project_by_slug(conn, slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{slug}' để đóng gói."))?;
    let dist_dir = Path::new(&project.folder_path).join("dist");
    std::fs::create_dir_all(&dist_dir)
        .map_err(|e| format!("Không tạo được thư mục dist: {e}"))?;
    let out_zip = dist_dir.join(format!("{slug}.akunbundle.zip"));
    let file = std::fs::File::create(&out_zip)
        .map_err(|e| format!("Không tạo được gói {}: {e}", out_zip.display()))?;
    let mut zip = zip::ZipWriter::new(file);
    let opts = SimpleFileOptions::default().compression_method(zip::CompressionMethod::Deflated);

    // 1. project.akun.json
    let manifest_bytes = serde_json::to_vec_pretty(&project.manifest)
        .map_err(|e| format!("Lỗi đóng gói manifest: {e}"))?;
    zip.start_file("project.akun.json", opts)
        .map_err(|e| e.to_string())?;
    zip.write_all(&manifest_bytes).map_err(|e| e.to_string())?;

    // 2. Sync payload JSON preview ready for Selorson
    let payload = crate::selorson_sync::build_sync_payload_for_project(
        &project.manifest,
        project.manifest.sync_policy.force_draft,
    );
    let payload_bytes = serde_json::to_vec_pretty(&payload).unwrap_or_default();
    zip.start_file("selorson_sync_payload.json", opts)
        .map_err(|e| e.to_string())?;
    zip.write_all(&payload_bytes).map_err(|e| e.to_string())?;

    // 3. Optional primary image if exists on disk
    if let Some(img_path) = project.manifest.local_image_path.as_deref() {
        let p = Path::new(img_path.trim());
        if p.is_file() {
            if let Ok(bytes) = std::fs::read(p) {
                let fname = p
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("preview.jpg");
                let _ = zip.start_file(format!("media/{fname}"), opts);
                let _ = zip.write_all(&bytes);
            }
        }
    }

    // 4. Bundle provenance stamp
    let stamp = json!({
        "bundle_format": "akunbundle/1.0",
        "exported_at": Utc::now().to_rfc3339(),
        "slug": project.slug,
        "draft_first_enforced": project.manifest.sync_policy.force_draft,
    });
    zip.start_file("bundle_meta.json", opts)
        .map_err(|e| e.to_string())?;
    zip.write_all(serde_json::to_string_pretty(&stamp).unwrap_or_default().as_bytes())
        .map_err(|e| e.to_string())?;

    zip.finish()
        .map_err(|e| format!("Lỗi hoàn tất nén .akunbundle.zip: {e}"))?;

    Ok(out_zip.to_string_lossy().to_string())
}

fn asset_kind_subdir_and_exts(asset_kind: &str) -> Result<(&'static str, &'static [&'static str]), String> {
    match asset_kind.trim().to_ascii_lowercase().as_str() {
        "concept" | "image" => Ok(("concepts", &["png", "jpg", "jpeg", "webp"])),
        "glb" | "model" | "clockwork" => Ok(("clockwork", &["glb", "gltf", "spz", "ply"])),
        "mechanism" | "mechanism_glb" => Ok(("clockwork", &["glb"])),
        "splat" | "chunk_splat" => Ok(("chunks", &["ply", "spz", "splat"])),
        "audio" | "bgm" => Ok(("audio", &["mp3", "wav", "ogg", "flac", "m4a"])),
        "voice" | "tts" => Ok(("stage_vn", &["wav", "mp3", "ogg", "flac", "m4a"])),
        "video" | "intro" => Ok(("cinema", &["mp4", "webm"])),
        other => Err(format!(
            "Loại tài nguyên '{other}' không hợp lệ (chỉ hỗ trợ concept | glb | splat | audio | voice | video)."
        )),
    }
}

/// P0: bản cơ khí nằm cùng thư mục `clockwork/` nhưng ghi vào `clockwork.mechanism_glb_path`, không đè bản thật.
fn is_mechanism_kind(asset_kind: &str) -> bool {
    matches!(asset_kind.trim().to_ascii_lowercase().as_str(), "mechanism" | "mechanism_glb")
}

fn sanitize_asset_filename(raw_name: &str, allowed_exts: &[&str]) -> Result<String, String> {
    let p = Path::new(raw_name.trim());
    let ext = p
        .extension()
        .and_then(|e| e.to_str())
        .map(|s| s.to_ascii_lowercase())
        .ok_or_else(|| format!("Tệp '{raw_name}' thiếu phần mở rộng định dạng."))?;
    if !allowed_exts.iter().any(|a| *a == ext) {
        return Err(format!(
            "Định dạng '.{ext}' không hợp lệ cho phân xưởng này (chỉ nhận: {}).",
            allowed_exts.join(", ")
        ));
    }
    let raw_stem = p
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("asset");
    let mut clean_stem = String::with_capacity(raw_stem.len());
    let mut prev_sep = false;
    for ch in raw_stem.chars() {
        if let Some(ascii) = fold_char_to_ascii(ch) {
            clean_stem.push(ascii);
            prev_sep = false;
        } else if matches!(ch, '-' | '_' | ' ' | '.') && !clean_stem.is_empty() && !prev_sep {
            clean_stem.push('_');
            prev_sep = true;
        }
    }
    while clean_stem.ends_with('_') {
        clean_stem.pop();
    }
    if clean_stem.is_empty() {
        clean_stem = "asset".to_string();
    }
    if clean_stem.len() > 64 {
        clean_stem.truncate(64);
    }
    Ok(format!("{clean_stem}.{ext}"))
}

fn push_unique_path(vec: &mut Vec<String>, path_str: &str) {
    if !vec.iter().any(|existing| existing.eq_ignore_ascii_case(path_str)) {
        vec.push(path_str.to_string());
    }
}

fn apply_imported_asset_to_manifest(
    manifest: &mut ProjectManifest,
    subdir: &str,
    dest_path: &Path,
    source_hint: Option<&Path>,
    set_primary: bool,
) {
    let dest_str = dest_path.to_string_lossy().to_string();
    match subdir {
        "concepts" => {
            push_unique_path(&mut manifest.concept_paths, &dest_str);
            if set_primary
                || manifest
                    .local_image_path
                    .as_deref()
                    .map(str::trim)
                    .unwrap_or("")
                    .is_empty()
            {
                manifest.local_image_path = Some(dest_str);
            }
        }
        "clockwork" => {
            let prev_glb = manifest.clockwork.glb_path.clone().unwrap_or_default();
            let changed_file = !prev_glb.eq_ignore_ascii_case(&dest_str);
            manifest.clockwork.glb_path = Some(dest_str);

            // Load sidecar `<stem>.parts.json` if present next to source or destination
            let sidecar_candidates = [
                source_hint.map(|s| s.with_extension("parts.json")),
                Some(dest_path.with_extension("parts.json")),
            ];
            let mut loaded_sidecar = false;
            for cand in sidecar_candidates.into_iter().flatten() {
                if cand.is_file() {
                    if let Ok(raw) = std::fs::read_to_string(&cand) {
                        if let Ok(parts_val) = serde_json::from_str::<Vec<Value>>(&raw) {
                            manifest.clockwork.parts = parts_val;
                            loaded_sidecar = true;
                            break;
                        }
                    }
                }
            }
            if changed_file && !loaded_sidecar && !prev_glb.is_empty() {
                // Reset parts metadata so RealPbrStageViewport auto-discovers actual nodes from the new .glb
                manifest.clockwork.parts.clear();
            }
        }
        "audio" => {
            push_unique_path(&mut manifest.audio_paths, &dest_str);
            if set_primary
                || manifest
                    .bgm_audio_path
                    .as_deref()
                    .map(str::trim)
                    .unwrap_or("")
                    .is_empty()
            {
                manifest.bgm_audio_path = Some(dest_str);
            }
        }
        "cinema" => {
            if manifest.kind == "cinema" {
                manifest.cinema.video_path = Some(dest_str);
            } else {
                manifest.clockwork.intro_video_path = Some(dest_str);
            }
        }
        "chunks" => {
            manifest.chunks.splat_path = Some(dest_str);
        }
        "stage_vn" => {
            push_unique_path(&mut manifest.audio_paths, &dest_str);
        }
        _ => {}
    }
}

pub fn import_external_file(
    conn: &Connection,
    slug: &str,
    asset_kind: &str,
    source_path: &str,
    set_primary: bool,
) -> Result<ProjectRecord, String> {
    import_external_file_in_root(
        conn,
        &akunarch_projects_root(),
        slug,
        asset_kind,
        source_path,
        set_primary,
    )
}

pub fn import_external_file_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
    asset_kind: &str,
    source_path: &str,
    set_primary: bool,
) -> Result<ProjectRecord, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let mut project = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let (subdir, allowed_exts) = asset_kind_subdir_and_exts(asset_kind)?;

    let src = Path::new(source_path.trim());
    if !src.is_file() {
        return Err(format!("Tệp nguồn không tồn tại trên ổ đĩa: {}", src.display()));
    }
    let raw_fname = src
        .file_name()
        .and_then(|n| n.to_str())
        .ok_or_else(|| "Tên tệp nguồn không hợp lệ.".to_string())?;
    let safe_fname = sanitize_asset_filename(raw_fname, allowed_exts)?;

    let folder = ensure_project_folder_tree(projects_root, &clean_slug)?;
    let target_dir = folder.join(subdir);
    // Đầu ra của job GPU đã nằm sẵn trong thư mục con của dự án → giữ nguyên tên (không sinh bản sao `_` thứ hai)
    let already_inside = src
        .parent()
        .and_then(|p| std::fs::canonicalize(p).ok())
        .zip(std::fs::canonicalize(&target_dir).ok())
        .is_some_and(|(a, b)| a == b);
    let dest_path = if already_inside { src.to_path_buf() } else { target_dir.join(&safe_fname) };

    let same_file = std::fs::canonicalize(src)
        .ok()
        .zip(std::fs::canonicalize(&dest_path).ok())
        .is_some_and(|(a, b)| a == b);
    if !same_file {
        std::fs::copy(src, &dest_path).map_err(|e| {
            format!(
                "Không sao chép được '{}' vào '{}': {e}",
                src.display(),
                dest_path.display()
            )
        })?;
    }

    if is_mechanism_kind(asset_kind) {
        project.manifest.clockwork.mechanism_glb_path = Some(dest_path.to_string_lossy().to_string());
    } else {
        apply_imported_asset_to_manifest(
            &mut project.manifest,
            subdir,
            &dest_path,
            Some(src),
            set_primary,
        );
    }
    update_project_manifest_in_root(conn, projects_root, Some(&clean_slug), &mut project.manifest)
}

pub fn upload_asset_bytes(
    conn: &Connection,
    slug: &str,
    asset_kind: &str,
    file_name: &str,
    bytes_base64: &str,
    set_primary: bool,
) -> Result<ProjectRecord, String> {
    upload_asset_bytes_in_root(
        conn,
        &akunarch_projects_root(),
        slug,
        asset_kind,
        file_name,
        bytes_base64,
        set_primary,
    )
}

pub fn upload_asset_bytes_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
    asset_kind: &str,
    file_name: &str,
    bytes_base64: &str,
    set_primary: bool,
) -> Result<ProjectRecord, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let mut project = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let (subdir, allowed_exts) = asset_kind_subdir_and_exts(asset_kind)?;
    let safe_fname = sanitize_asset_filename(file_name, allowed_exts)?;

    let raw_b64 = bytes_base64
        .trim()
        .split_once(',')
        .map(|(_, payload)| payload)
        .unwrap_or_else(|| bytes_base64.trim());
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(raw_b64)
        .map_err(|e| format!("Dữ liệu tệp tải lên không đúng chuẩn Base64: {e}"))?;
    if decoded.is_empty() {
        return Err("Tệp tải lên rỗng (0 bytes).".to_string());
    }

    let folder = ensure_project_folder_tree(projects_root, &clean_slug)?;
    let dest_path = folder.join(subdir).join(&safe_fname);
    std::fs::write(&dest_path, &decoded)
        .map_err(|e| format!("Không ghi được tệp {}: {e}", dest_path.display()))?;

    if is_mechanism_kind(asset_kind) {
        project.manifest.clockwork.mechanism_glb_path = Some(dest_path.to_string_lossy().to_string());
    } else {
        apply_imported_asset_to_manifest(&mut project.manifest, subdir, &dest_path, None, set_primary);
    }
    update_project_manifest_in_root(conn, projects_root, Some(&clean_slug), &mut project.manifest)
}

fn decode_png_payload(raw: &str, label: &str) -> Result<Vec<u8>, String> {
    let trimmed = raw.trim();
    let payload = trimmed
        .split_once(',')
        .map(|(_, p)| p)
        .unwrap_or(trimmed);
    let bytes = base64::engine::general_purpose::STANDARD
        .decode(payload)
        .map_err(|e| format!("Lỗi giải mã PNG '{label}': {e}"))?;
    if bytes.len() < 8 || &bytes[..8] != b"\x89PNG\r\n\x1a\n" {
        return Err(format!("Dữ liệu '{label}' không có chữ ký tệp PNG hợp lệ."));
    }
    Ok(bytes)
}

pub fn save_manga_plates(
    conn: &Connection,
    slug: &str,
    label: Option<&str>,
    width: u32,
    height: u32,
    beauty_png_base64: &str,
    depth_png_base64: &str,
) -> Result<MangaPlateExportResult, String> {
    save_manga_plates_in_root(
        conn,
        &akunarch_projects_root(),
        slug,
        label,
        width,
        height,
        beauty_png_base64,
        depth_png_base64,
    )
}

pub fn save_manga_plates_in_root(
    conn: &Connection,
    projects_root: &Path,
    slug: &str,
    label: Option<&str>,
    width: u32,
    height: u32,
    beauty_png_base64: &str,
    depth_png_base64: &str,
) -> Result<MangaPlateExportResult, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let mut project = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let beauty_bytes = decode_png_payload(beauty_png_base64, "beauty_plate.png")?;
    let depth_bytes = decode_png_payload(depth_png_base64, "depth_map.png")?;

    let folder = ensure_project_folder_tree(projects_root, &clean_slug)?;
    let plates_dir = folder.join("manga_plates");
    std::fs::create_dir_all(&plates_dir)
        .map_err(|e| format!("Không tạo được thư mục manga_plates: {e}"))?;

    // 1. Canonical latest plate pair (`beauty_plate.png` + `depth_map.png`)
    let canonical_beauty = plates_dir.join("beauty_plate.png");
    let canonical_depth = plates_dir.join("depth_map.png");
    std::fs::write(&canonical_beauty, &beauty_bytes)
        .map_err(|e| format!("Không ghi được {}: {e}", canonical_beauty.display()))?;
    std::fs::write(&canonical_depth, &depth_bytes)
        .map_err(|e| format!("Không ghi được {}: {e}", canonical_depth.display()))?;

    // 2. Timestamped archive copies so multiple camera angles are preserved
    let now = Utc::now();
    let stamp = now.format("%Y%m%d_%H%M%S").to_string();
    let idx = project.manifest.manga_plates.len() + 1;
    let plate_id = format!("plate_{idx:02}_{stamp}");
    let arch_beauty = plates_dir.join(format!("{plate_id}_beauty.png"));
    let arch_depth = plates_dir.join(format!("{plate_id}_depth.png"));
    let _ = std::fs::write(&arch_beauty, &beauty_bytes);
    let _ = std::fs::write(&arch_depth, &depth_bytes);

    let capture = MangaPlateCapture {
        id: plate_id,
        label: label
            .map(str::trim)
            .filter(|s| !s.is_empty())
            .map(String::from)
            .unwrap_or_else(|| format!("Góc quay Manga #{idx} ({width}×{height})")),
        beauty_path: arch_beauty.to_string_lossy().to_string(),
        depth_path: arch_depth.to_string_lossy().to_string(),
        width,
        height,
        created_at: now.to_rfc3339(),
    };
    project.manifest.manga_plates.insert(0, capture.clone());
    if project.manifest.manga_plates.len() > 24 {
        project.manifest.manga_plates.truncate(24);
    }

    let updated = update_project_manifest_in_root(
        conn,
        projects_root,
        Some(&clean_slug),
        &mut project.manifest,
    )?;

    Ok(MangaPlateExportResult {
        plate: capture,
        beauty_plate_path: canonical_beauty.to_string_lossy().to_string(),
        depth_map_path: canonical_depth.to_string_lossy().to_string(),
        project: updated,
    })
}

pub fn list_ai_meshes() -> Result<Vec<AiMeshEntry>, String> {
    let meshes_dir = std::env::var("AKUNARCH_AI_MESHES_DIR")
        .map(PathBuf::from)
        .unwrap_or_else(|_| PathBuf::from(r"E:\Tools-3D\ai_meshes"));
    let concepts_root = crate::cowriter_bridge::concepts_dir();
    if !meshes_dir.is_dir() {
        return Ok(Vec::new());
    }

    let mut items = Vec::new();
    let entries = std::fs::read_dir(&meshes_dir)
        .map_err(|e| format!("Không đọc được kho mesh {}: {e}", meshes_dir.display()))?;
    for entry in entries.flatten() {
        let p = entry.path();
        if !p.is_file() {
            continue;
        }
        let is_glb = p
            .extension()
            .and_then(|e| e.to_str())
            .is_some_and(|e| e.eq_ignore_ascii_case("glb"));
        if !is_glb {
            continue;
        }
        let file_name = p
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();
        let stem = p
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string();
        let size_bytes = entry.metadata().map(|m| m.len()).unwrap_or(0);

        let mut concept_path = None;
        for ext in ["jpg", "png", "webp"] {
            let cand = concepts_root.join(format!("concept_{stem}.{ext}"));
            if cand.is_file() {
                concept_path = Some(cand.to_string_lossy().to_string());
                break;
            }
        }

        items.push(AiMeshEntry {
            file_name,
            stem,
            glb_path: p.to_string_lossy().to_string(),
            size_bytes,
            concept_path,
        });
    }
    items.sort_by(|a, b| a.stem.cmp(&b.stem));
    Ok(items)
}

pub fn resolve_project_subfolder_path(
    conn: &Connection,
    slug: &str,
    subfolder: Option<&str>,
) -> Result<PathBuf, String> {
    let clean_slug = sanitize_project_slug(slug)?;
    let proj = get_project_by_slug(conn, &clean_slug)?
        .ok_or_else(|| format!("Không tìm thấy dự án '{clean_slug}'."))?;
    let base = PathBuf::from(&proj.folder_path);
    let target = match subfolder.map(str::trim).filter(|s| !s.is_empty()) {
        Some(sub) if PROJECT_SUBDIRS.contains(&sub) => base.join(sub),
        Some(other) => {
            return Err(format!("Thư mục con '{other}' không thuộc cấu trúc dự án chuẩn."));
        }
        None => base,
    };
    std::fs::create_dir_all(&target)
        .map_err(|e| format!("Không mở được thư mục {}: {e}", target.display()))?;
    Ok(target)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::init_schema;

    #[test]
    fn manifest_without_mechanism_field_still_loads() {
        let m: ProjectManifest = serde_json::from_value(json!({
            "slug": "a-b", "title": "A",
            "clockwork": { "parts": [], "glb_path": "x.glb", "intro_video_path": null }
        }))
        .unwrap();
        assert_eq!(m.clockwork.mechanism_glb_path, None);
        assert_eq!(m.clockwork.glb_path.as_deref(), Some("x.glb"));
    }

    #[test]
    fn import_mechanism_glb_sets_mechanism_path_not_main_glb() {
        let conn = Connection::open_in_memory().unwrap();
        init_schema(&conn).unwrap();
        let root = std::env::temp_dir().join(format!("akun_mech_{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&root);
        create_project_in_root(
            &conn,
            &root,
            CreateProjectInput {
                slug: "mech-demo".into(),
                title: "Tháp thử".into(),
                title_en: String::new(),
                kind: "clockwork".into(),
                planet: "earth".into(),
                region_slug: String::new(),
                era: String::new(),
                era_year: None,
                lat: None,
                lng: None,
                biome: String::new(),
                chunk_x: 0,
                chunk_z: 0,
                cowriter_entity_id: None,
                cowriter_key: String::new(),
                unlock_chapter: None,
                description_vi: String::new(),
                description_en: String::new(),
                local_image_path: None,
                concept_paths: vec![],
                bgm_audio_path: None,
                glb_path: None,
            },
        )
        .unwrap();
        let src_dir = root.join("_src");
        std::fs::create_dir_all(&src_dir).unwrap();
        std::fs::write(src_dir.join("mech-demo.glb"), b"real").unwrap();
        std::fs::write(src_dir.join("mech-demo_mechanism.glb"), b"mech").unwrap();
        let real = import_external_file_in_root(&conn, &root, "mech-demo", "glb",
            &src_dir.join("mech-demo.glb").to_string_lossy(), true).unwrap();
        let real_path = real.manifest.clockwork.glb_path.clone();
        let rec = import_external_file_in_root(&conn, &root, "mech-demo", "mechanism",
            &src_dir.join("mech-demo_mechanism.glb").to_string_lossy(), true).unwrap();
        assert_eq!(rec.manifest.clockwork.glb_path, real_path, "bản thật giữ nguyên");
        let mech = rec.manifest.clockwork.mechanism_glb_path.expect("phải có mechanism_glb_path");
        assert!(mech.ends_with("_mechanism.glb"), "{mech}");
        assert!(Path::new(&mech).is_file());

        // Đầu ra job (đã nằm sẵn trong clockwork/ của dự án) → dùng nguyên đường dẫn, KHÔNG chép thành bản `_` thứ hai
        let clock = root.join("mech-demo").join("clockwork");
        let job_out = clock.join("mech-demo.glb");
        std::fs::write(&job_out, b"job").unwrap();
        let before = std::fs::read_dir(&clock).unwrap().count();
        let rec = import_external_file_in_root(&conn, &root, "mech-demo", "glb", &job_out.to_string_lossy(), true).unwrap();
        assert_eq!(rec.manifest.clockwork.glb_path.as_deref(), Some(job_out.to_string_lossy().as_ref()));
        assert_eq!(std::fs::read_dir(&clock).unwrap().count(), before, "không sinh bản sao");
        assert!(import_external_file_in_root(&conn, &root, "mech-demo", "mechanism",
            &src_dir.join("x.png").to_string_lossy(), true).is_err());
        let _ = std::fs::remove_dir_all(&root);
    }

    #[test]
    fn slug_sanitizer_blocks_traversal_reserved_and_empty_inputs() {
        assert_eq!(
            sanitize_project_slug("  Singularity: Ganges & Meru v5! ").unwrap(),
            "singularity-ganges-meru-v5"
        );
        assert_eq!(
            sanitize_project_slug("Đền Ngũ Giác Zyberon").unwrap(),
            "den-ngu-giac-zyberon"
        );
        assert_eq!(
            sanitize_project_slug("Pháo Đài Dún Scáith").unwrap(),
            "phao-dai-dun-scaith"
        );
        assert_eq!(
            sanitize_project_slug("../../../Windows/System32").unwrap(),
            "windows-system32"
        );
        assert_eq!(
            sanitize_project_slug(r"..\..\secret\vault").unwrap(),
            "secret-vault"
        );
        let overlong = "a".repeat(95);
        assert_eq!(sanitize_project_slug(&overlong).unwrap().len(), 80);
        assert!(sanitize_project_slug("   ").is_err());
        assert!(sanitize_project_slug("a").is_err());
        assert!(sanitize_project_slug("CON").is_err());
        assert!(sanitize_project_slug("nul").is_err());
    }

    #[test]
    fn open_project_lifecycle_creates_subfolders_vibecode_rescans_and_exports_zip() {
        let conn = Connection::open_in_memory().unwrap();
        init_schema(&conn).unwrap();

        let tmp_root = std::env::temp_dir().join(format!(
            "akunarch_proj_test_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(1)
        ));
        let created = create_project_in_root(
            &conn,
            &tmp_root,
            CreateProjectInput {
                slug: "singularity-ganges-kalyan".into(),
                title: "Xưởng Rèn Sông Hằng & Đỉnh Tuyết Sơn Meru".into(),
                title_en: "Ganges Wootz Forge & Mount Meru".into(),
                kind: "clockwork".into(),
                planet: "earth".into(),
                region_slug: "south-asia-ancient".into(),
                era: "292 TCN".into(),
                era_year: Some(-292),
                lat: Some(25.3176),
                lng: Some(82.9739),
                biome: "river-valley".into(),
                chunk_x: 0,
                chunk_z: 0,
                cowriter_entity_id: Some(4),
                cowriter_key: "char:dona-heracles".into(),
                unlock_chapter: Some(5),
                description_vi: "Lò rèn thép nồi nấu bên bậc thềm sông Hằng.".into(),
                description_en: "Crucible Wootz forge by the Ganges ghats.".into(),
                local_image_path: None,
                concept_paths: vec![],
                bgm_audio_path: None,
                glb_path: None,
            },
        )
        .expect("create project");

        let proj_dir = Path::new(&created.folder_path);
        assert!(proj_dir.join("project.akun.json").is_file());
        for sub in PROJECT_SUBDIRS {
            assert!(proj_dir.join(sub).is_dir(), "missing subdir {sub}");
        }
        assert!(created.manifest.sync_policy.force_draft);

        // Simulate external AI Vibecode edit on disk + rescan into fresh DB
        let conn2 = Connection::open_in_memory().unwrap();
        init_schema(&conn2).unwrap();
        let rescanned = rescan_projects_in_root(&conn2, &tmp_root).expect("rescan from disk");
        assert_eq!(rescanned.len(), 1);
        assert_eq!(rescanned[0].slug, "singularity-ganges-kalyan");
        assert_eq!(rescanned[0].chapter_no, Some(5));

        let bundle_path = export_project_akunbundle(&conn2, "singularity-ganges-kalyan")
            .expect("export bundle zip");
        assert!(Path::new(&bundle_path).is_file());

        // Simulate Vibecode renaming `manifest.slug` inside `project.akun.json` (with Vietnamese diacritics!)
        // while an asset already sits inside `clockwork/gear.glb`.
        let asset_file = proj_dir.join("clockwork").join("gear.glb");
        std::fs::write(&asset_file, b"glb-bytes").unwrap();
        let mut edited_manifest = rescanned[0].manifest.clone();
        edited_manifest.slug = "Đỉnh Tuyết Sơn Meru v2!".to_string();
        write_manifest_file(proj_dir, &edited_manifest).unwrap();

        let after_rename = rescan_projects_in_root(&conn, &tmp_root).expect("rescan after rename");
        assert_eq!(
            after_rename.len(),
            1,
            "must NOT leave duplicate stale row in projects table"
        );
        assert_eq!(after_rename[0].slug, "dinh-tuyet-son-meru-v2");
        assert_eq!(after_rename[0].id, created.id, "project ID must be preserved");
        let new_dir = tmp_root.join("dinh-tuyet-son-meru-v2");
        assert!(new_dir.join("project.akun.json").is_file());
        assert!(
            new_dir.join("clockwork").join("gear.glb").is_file(),
            "existing assets must move atomically with renamed folder"
        );
        assert!(
            !tmp_root.join("Đỉnh Tuyết Sơn Meru v2!").exists(),
            "must never create raw unsanitized ghost folder"
        );

        // Simulate deleting project folder on disk -> rescan must prune ghost DB row cleanly
        std::fs::remove_dir_all(&new_dir).unwrap();
        let after_delete = rescan_projects_in_root(&conn, &tmp_root).expect("rescan after delete");
        assert!(
            after_delete.is_empty(),
            "deleted project folder must be pruned from DB on rescan"
        );

        let _ = std::fs::remove_dir_all(&tmp_root);
    }

    #[test]
    fn update_manifest_handles_ui_slug_rename_collision_and_open_world_chunk_cleanup() {
        let conn = Connection::open_in_memory().unwrap();
        init_schema(&conn).unwrap();
        let tmp_root = std::env::temp_dir().join(format!(
            "akunarch_proj_update_test_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(2)
        ));

        let p1 = create_project_in_root(
            &conn,
            &tmp_root,
            CreateProjectInput {
                slug: "chunk-alpha".into(),
                title: "Ô Đại Lục Alpha".into(),
                title_en: "Alpha Chunk".into(),
                kind: "open_world".into(),
                planet: "akunalia".into(),
                region_slug: "eldarin".into(),
                era: "".into(),
                era_year: None,
                lat: None,
                lng: None,
                biome: "forest".into(),
                chunk_x: 2,
                chunk_z: -3,
                cowriter_entity_id: None,
                cowriter_key: "".into(),
                unlock_chapter: Some(1),
                description_vi: "".into(),
                description_en: "".into(),
                local_image_path: None,
                concept_paths: vec![],
                bgm_audio_path: None,
                glb_path: None,
            },
        )
        .unwrap();

        let _p2 = create_project_in_root(
            &conn,
            &tmp_root,
            CreateProjectInput {
                slug: "taken-slug".into(),
                title: "Dự Án Đã Chiếm Slug".into(),
                title_en: "".into(),
                kind: "clockwork".into(),
                planet: "earth".into(),
                region_slug: "".into(),
                era: "".into(),
                era_year: None,
                lat: None,
                lng: None,
                biome: "temperate".into(),
                chunk_x: 0,
                chunk_z: 0,
                cowriter_entity_id: None,
                cowriter_key: "".into(),
                unlock_chapter: Some(1),
                description_vi: "".into(),
                description_en: "".into(),
                local_image_path: None,
                concept_paths: vec![],
                bgm_audio_path: None,
                glb_path: None,
            },
        )
        .unwrap();

        // Place an asset inside p1's chunks/ directory
        std::fs::write(
            Path::new(&p1.folder_path).join("chunks").join("terrain.bin"),
            b"heightmap",
        )
        .unwrap();

        // Collision with existing project slug must fail without touching either project
        let mut colliding = p1.manifest.clone();
        colliding.slug = "taken-slug".into();
        let err = update_project_manifest_in_root(&conn, &tmp_root, Some("chunk-alpha"), &mut colliding)
            .expect_err("must reject slug collision");
        assert!(err.contains("dự án khác"));

        // Valid UI JSON rename + coordinate update moves folder atomically, preserves id, and cleans old world_chunks row
        let mut renamed = p1.manifest.clone();
        renamed.slug = "Ô Đại Lục Beta!".into();
        renamed.chunk_x = 5;
        renamed.chunk_z = 7;
        let updated = update_project_manifest_in_root(
            &conn,
            &tmp_root,
            Some("chunk-alpha"),
            &mut renamed,
        )
        .expect("rename via update_project_manifest_in_root");
        assert_eq!(updated.id, p1.id);
        assert_eq!(updated.slug, "o-dai-luc-beta");
        assert!(!tmp_root.join("chunk-alpha").exists());
        assert!(tmp_root
            .join("o-dai-luc-beta")
            .join("chunks")
            .join("terrain.bin")
            .is_file());
        assert_eq!(list_projects(&conn).unwrap().len(), 2);

        let chunk_count_old: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM world_chunks WHERE planet='akunalia' AND chunk_x=2 AND chunk_z=-3",
                [],
                |r| r.get(0),
            )
            .unwrap();
        let chunk_count_new: i64 = conn
            .query_row(
                "SELECT COUNT(*) FROM world_chunks WHERE planet='akunalia' AND chunk_x=5 AND chunk_z=7",
                [],
                |r| r.get(0),
            )
            .unwrap();
        assert_eq!(chunk_count_old, 0, "stale chunk coordinates must be cleaned up");
        assert_eq!(chunk_count_new, 1, "new chunk coordinates must be persisted");

        let _ = std::fs::remove_dir_all(&tmp_root);
    }

    #[test]
    fn byoa_import_upload_and_manga_2k_plate_export_work_standalone_without_cowriter_key() {
        let conn = Connection::open_in_memory().unwrap();
        init_schema(&conn).unwrap();
        let tmp_root = std::env::temp_dir().join(format!(
            "akunarch_byoa_test_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(3)
        ));
        let ext_src_dir = tmp_root.join("_external_sources");
        std::fs::create_dir_all(&ext_src_dir).unwrap();

        // 1. Standalone World-First project (empty cowriter_key)
        let proj = create_project_in_root(
            &conn,
            &tmp_root,
            CreateProjectInput {
                slug: "world-first-citadel".into(),
                title: "Thành Cổ Độc Lập Đi Trước".into(),
                title_en: "Standalone World-First Citadel".into(),
                kind: "clockwork".into(),
                planet: "akunalia".into(),
                region_slug: "northern-rift".into(),
                era: "Kỷ Nguyên Khởi Thủy".into(),
                era_year: None,
                lat: None,
                lng: None,
                biome: "highland".into(),
                chunk_x: 0,
                chunk_z: 0,
                cowriter_entity_id: None,
                cowriter_key: "".into(),
                unlock_chapter: Some(1),
                description_vi: "Kỳ quan xây độc lập trước khi gắn vào chương truyện.".into(),
                description_en: "Monument built ahead of manuscript chapters.".into(),
                local_image_path: None,
                concept_paths: vec![],
                bgm_audio_path: None,
                glb_path: None,
            },
        )
        .expect("standalone project creation");
        assert_eq!(proj.manifest.cowriter_key, "");
        assert!(proj.manifest.clockwork.glb_path.is_none());

        // 2. Import external .glb + automatic .parts.json sidecar pickup
        let ext_glb = ext_src_dir.join("Hero Monument v1.glb");
        let ext_parts = ext_src_dir.join("Hero Monument v1.parts.json");
        std::fs::write(&ext_glb, b"glTF\x02\x00\x00\x00").unwrap();
        std::fs::write(
            &ext_parts,
            r#"[{"id":"base_plinth","name_vi":"Đế Đá","name_en":"Stone Plinth","dir":[0,0,0]}]"#,
        )
        .unwrap();
        let after_glb = import_external_file_in_root(
            &conn,
            &tmp_root,
            "world-first-citadel",
            "glb",
            &ext_glb.to_string_lossy(),
            true,
        )
        .expect("import external glb");
        let imported_glb_path = after_glb.manifest.clockwork.glb_path.clone().unwrap();
        assert!(Path::new(&imported_glb_path).is_file());
        assert!(imported_glb_path.ends_with(r"clockwork\hero_monument_v1.glb"));
        assert_eq!(after_glb.manifest.clockwork.parts.len(), 1);

        // 3. Upload external FL Studio .flac BGM via Base64 drag-drop
        let flac_b64 = base64::engine::general_purpose::STANDARD.encode(b"fLaC\x00\x00\x00\x22");
        let after_bgm = upload_asset_bytes_in_root(
            &conn,
            &tmp_root,
            "world-first-citadel",
            "audio",
            "FL Studio Theme Master.flac",
            &flac_b64,
            true,
        )
        .expect("upload flac bgm");
        let bgm_path = after_bgm.manifest.bgm_audio_path.clone().unwrap();
        assert!(Path::new(&bgm_path).is_file());
        assert!(bgm_path.ends_with(r"audio\fl_studio_theme_master.flac"));

        // 4. Export 2K Manga Beauty + Depth plates
        let minimal_png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR";
        let png_b64 = format!(
            "data:image/png;base64,{}",
            base64::engine::general_purpose::STANDARD.encode(minimal_png)
        );
        let manga_res = save_manga_plates_in_root(
            &conn,
            &tmp_root,
            "world-first-citadel",
            Some("Góc Cổng Đông 2K"),
            2048,
            1152,
            &png_b64,
            &png_b64,
        )
        .expect("save manga plates");
        assert!(Path::new(&manga_res.beauty_plate_path).is_file());
        assert!(Path::new(&manga_res.depth_map_path).is_file());
        assert!(manga_res.beauty_plate_path.ends_with(r"manga_plates\beauty_plate.png"));
        assert!(manga_res.depth_map_path.ends_with(r"manga_plates\depth_map.png"));
        assert_eq!(manga_res.project.manifest.manga_plates.len(), 1);

        let _ = std::fs::remove_dir_all(&tmp_root);
    }
}
