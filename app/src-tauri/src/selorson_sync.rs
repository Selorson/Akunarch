use crate::db::{get_setting, set_setting};
use crate::projects::{get_project_by_slug, ProjectManifest};
use chrono::{Duration, Utc};
use jsonwebtoken::{encode, EncodingKey, Header};
use rusqlite::{params, Connection};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::path::Path;

pub const DEFAULT_SELORSON_BASE_URL: &str = "http://127.0.0.1:8001";

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StudioEntityTranslationPayload {
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub role: Option<String>,
    #[serde(default)]
    pub aliases: Vec<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StudioLocationSyncPayload {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slug: Option<String>,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub kind: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub planet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub region: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub era: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub era_year: Option<i64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lat: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub lng: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unlock_chapter: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_image_path: Option<String>,
    #[serde(default, skip_serializing_if = "Vec::is_empty")]
    pub local_preview_paths: Vec<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_intro_video_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_clockwork_pack_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub clockwork_pack_version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_desktop_pack_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub desktop_pack_version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_vn_episode_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vn_episode_title: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub parts: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub en: Option<StudioEntityTranslationPayload>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StudioChunkSyncPayload {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub source_key: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub slug: Option<String>,
    pub name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub planet: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub region: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub biome: Option<String>,
    pub chunk_x: i32,
    pub chunk_z: i32,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub world_size: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub unlock_chapter: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_image_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_chunk_pack_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub chunk_pack_version: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_splat_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub water_level: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub foliage_density: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub heightmap_grid: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub placements: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub audio_zones: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub spawn_points: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vn_triggers: Option<Value>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub en: Option<StudioEntityTranslationPayload>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StudioVideoTranslationPayload {
    #[serde(skip_serializing_if = "Option::is_none")]
    pub video_name: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
pub struct StudioVideoSyncPayload {
    pub video_name: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_video_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub local_thumbnail_path: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub episode_number: Option<i32>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub video_type: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub description: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub en: Option<StudioVideoTranslationPayload>,
}

/// Exact contract matching `WorldStudioSyncPayload` in `E:\Selorson\backend-v3\src\handlers\admin_sync.rs`.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct WorldStudioSyncPayload {
    pub source_app: String,
    pub force_draft: bool,
    #[serde(default)]
    pub locations: Vec<StudioLocationSyncPayload>,
    #[serde(default)]
    pub chunks: Vec<StudioChunkSyncPayload>,
    #[serde(default)]
    pub videos: Vec<StudioVideoSyncPayload>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QaFinding {
    pub severity: String, // "blocker" | "warning" | "pass"
    pub rule_code: String,
    pub message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct QaAuditReport {
    pub slug: String,
    pub passed: bool,
    pub draft_first_enforced: bool,
    pub findings: Vec<QaFinding>,
    pub payload_preview: WorldStudioSyncPayload,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SyncLogRow {
    pub id: i64,
    pub project_id: Option<i64>,
    pub target_url: String,
    pub payload_summary: Value,
    pub response: Value,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SelorsonConnectionConfig {
    pub base_url: String,
    pub has_token: bool,
    pub token_preview: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct LocalBetaClaims {
    sub: i64,
    role: String,
    token_type: String,
    auth_version: i64,
    remember_me: bool,
    exp: i64,
    iat: i64,
}

pub fn sanitize_bearer_token(raw: &str) -> Result<String, String> {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return Ok(String::new());
    }
    let without_scheme = if trimmed
        .get(..7)
        .is_some_and(|prefix| prefix.eq_ignore_ascii_case("bearer "))
    {
        trimmed[7..].trim()
    } else {
        trimmed
    };
    if without_scheme.is_empty() || !without_scheme.chars().all(|c| c.is_ascii_graphic()) {
        return Err(
            "Bearer Token không hợp lệ (chỉ chấp nhận chuỗi JWT ASCII chuẩn, không khoảng trắng hoặc dấu tiếng Việt)."
                .to_string(),
        );
    }
    Ok(without_scheme.to_string())
}

pub fn get_selorson_config(conn: &Connection) -> SelorsonConnectionConfig {
    let base_url = get_setting(conn, "selorson_base_url")
        .filter(|s| !s.trim().is_empty())
        .unwrap_or_else(|| DEFAULT_SELORSON_BASE_URL.to_string());
    let token = get_setting(conn, "selorson_token").unwrap_or_default();
    let trimmed = token.trim();
    let char_count = trimmed.chars().count();
    let preview = if char_count > 16 {
        let head: String = trimmed.chars().take(10).collect();
        let tail: String = trimmed.chars().skip(char_count - 6).collect();
        format!("{head}…{tail}")
    } else if char_count > 0 {
        "Đã cấu hình token".to_string()
    } else {
        "Chưa có token".to_string()
    };
    SelorsonConnectionConfig {
        base_url,
        has_token: char_count > 0,
        token_preview: preview,
    }
}

pub fn save_selorson_config(
    conn: &Connection,
    base_url: &str,
    token: Option<&str>,
) -> Result<SelorsonConnectionConfig, String> {
    let clean_url = normalize_base_url(base_url)?;
    set_setting(conn, "selorson_base_url", &clean_url)?;
    if let Some(tok) = token {
        let clean_tok = sanitize_bearer_token(tok)?;
        set_setting(conn, "selorson_token", &clean_tok)?;
    }
    Ok(get_selorson_config(conn))
}

pub fn normalize_base_url(raw: &str) -> Result<String, String> {
    let trimmed = raw.trim().trim_end_matches('/');
    if trimmed.is_empty() {
        return Ok(DEFAULT_SELORSON_BASE_URL.to_string());
    }
    if !(trimmed.starts_with("http://") || trimmed.starts_with("https://")) {
        return Err("URL Selorson phải bắt đầu bằng http:// hoặc https://".to_string());
    }
    Ok(trimmed.to_string())
}

/// Builds the exact `WorldStudioSyncPayload` from a `ProjectManifest`.
/// By Rule #5 (`Draft-First`), `force_draft` defaults to `true`.
pub fn build_sync_payload_for_project(
    manifest: &ProjectManifest,
    force_draft: bool,
) -> WorldStudioSyncPayload {
    let en_entity = if !manifest.title_en.trim().is_empty() {
        Some(StudioEntityTranslationPayload {
            name: manifest.title_en.trim().to_string(),
            description: (!manifest.description_en.trim().is_empty())
                .then(|| manifest.description_en.trim().to_string()),
            role: None,
            aliases: Vec::new(),
        })
    } else {
        None
    };

    let mut locations = Vec::new();
    let mut chunks = Vec::new();
    let mut videos = Vec::new();

    match manifest.kind.as_str() {
        "open_world" => {
            let source_key = format!(
                "chunk:{}:{}:{}",
                manifest.planet, manifest.chunk_x, manifest.chunk_z
            );
            let local_img = manifest
                .local_image_path
                .clone()
                .or_else(|| manifest.concept_paths.first().cloned());
            chunks.push(StudioChunkSyncPayload {
                source_key: Some(source_key),
                slug: Some(manifest.slug.clone()),
                name: manifest.title.clone(),
                planet: Some(manifest.planet.clone()),
                region: (!manifest.region_slug.trim().is_empty())
                    .then(|| manifest.region_slug.clone()),
                biome: (!manifest.biome.trim().is_empty()).then(|| manifest.biome.clone()),
                chunk_x: manifest.chunk_x,
                chunk_z: manifest.chunk_z,
                world_size: Some(manifest.world_size),
                unlock_chapter: Some(manifest.unlock_chapter),
                description: (!manifest.description_vi.trim().is_empty())
                    .then(|| manifest.description_vi.clone()),
                local_image_path: local_img,
                local_chunk_pack_path: manifest.chunks.pack_zip_path.clone(),
                chunk_pack_version: Some(manifest.chunks.pack_version.clone()),
                local_splat_path: manifest.chunks.splat_path.clone(),
                water_level: Some(manifest.chunks.water_level),
                foliage_density: Some(manifest.chunks.foliage_density),
                heightmap_grid: (!manifest.chunks.heightmap_values.is_empty()).then(|| {
                    json!({
                        "resolution": manifest.chunks.grid_resolution,
                        "values": manifest.chunks.heightmap_values,
                    })
                }),
                placements: (!manifest.chunks.placements.is_empty()).then(|| {
                    // B3: bản runtime dùng KTX2 BC7 (chỉ Akunarch desktop đọc được) → Selorson nhận bản gốc _master
                    let portable: Vec<_> = manifest
                        .chunks
                        .placements
                        .iter()
                        .cloned()
                        .map(|mut pl| {
                            pl.glb_path = crate::gpu_queue::blender_source_glb(&pl.glb_path);
                            pl
                        })
                        .collect();
                    json!(portable)
                }),
                audio_zones: (!manifest.chunks.audio_zones.is_empty())
                    .then(|| json!(manifest.chunks.audio_zones)),
                spawn_points: (!manifest.chunks.spawn_points.is_empty())
                    .then(|| json!(manifest.chunks.spawn_points)),
                vn_triggers: (!manifest.chunks.vn_triggers.is_empty())
                    .then(|| json!(manifest.chunks.vn_triggers)),
                en: en_entity,
            });
        }
        "cinema" => {
            videos.push(StudioVideoSyncPayload {
                video_name: manifest.title.clone(),
                local_video_path: manifest.cinema.video_path.clone(),
                local_thumbnail_path: manifest
                    .cinema
                    .thumbnail_path
                    .clone()
                    .or_else(|| manifest.local_image_path.clone()),
                episode_number: manifest.cinema.episode_number,
                video_type: Some(manifest.cinema.video_type.clone()),
                description: (!manifest.description_vi.trim().is_empty())
                    .then(|| manifest.description_vi.clone()),
                en: (!manifest.title_en.trim().is_empty()).then(|| StudioVideoTranslationPayload {
                    video_name: Some(manifest.title_en.clone()),
                    description: (!manifest.description_en.trim().is_empty())
                        .then(|| manifest.description_en.clone()),
                }),
            });
        }
        // "clockwork" | "vn_episode"
        _ => {
            let source_key = if !manifest.cowriter_key.trim().is_empty() {
                manifest.cowriter_key.clone()
            } else {
                format!("akunarch:{}", manifest.slug)
            };
            let local_img = manifest
                .local_image_path
                .clone()
                .or_else(|| manifest.concept_paths.first().cloned());
            // B3: gửi bản .glb gốc chuẩn glTF (clockwork\_master) — bản runtime KTX2 BC7 chỉ dành cho Akunarch desktop
            let pack_path = manifest
                .clockwork
                .glb_path
                .as_deref()
                .map(crate::gpu_queue::blender_source_glb);
            // P0: sa bàn cơ khí dùng bản cơ khí (có animation) nếu có; gói desktop vẫn là bản thật
            let clockwork_pack_path = manifest
                .clockwork
                .mechanism_glb_path
                .as_deref()
                .filter(|p| !p.trim().is_empty())
                .map(crate::gpu_queue::blender_source_glb)
                .or_else(|| pack_path.clone());
            locations.push(StudioLocationSyncPayload {
                source_key: Some(source_key),
                slug: Some(manifest.slug.clone()),
                name: manifest.title.clone(),
                kind: Some("poi".to_string()),
                planet: Some(manifest.planet.clone()),
                region: (!manifest.region_slug.trim().is_empty())
                    .then(|| manifest.region_slug.clone()),
                era: (!manifest.era.trim().is_empty()).then(|| manifest.era.clone()),
                era_year: manifest.era_year,
                lat: manifest.lat,
                lng: manifest.lng,
                unlock_chapter: Some(manifest.unlock_chapter),
                description: (!manifest.description_vi.trim().is_empty())
                    .then(|| manifest.description_vi.clone()),
                local_image_path: local_img,
                local_preview_paths: manifest.concept_paths.clone(),
                local_intro_video_path: manifest.clockwork.intro_video_path.clone(),
                local_clockwork_pack_path: clockwork_pack_path,
                clockwork_pack_version: Some(manifest.clockwork.pack_version.clone()),
                local_desktop_pack_path: pack_path,
                desktop_pack_version: Some(manifest.clockwork.pack_version.clone()),
                local_vn_episode_path: manifest.stage_vn.episode_zip_path.clone(),
                vn_episode_title: manifest.stage_vn.episode_title.clone(),
                parts: (!manifest.clockwork.parts.is_empty())
                    .then(|| json!(manifest.clockwork.parts)),
                en: en_entity,
            });
        }
    }

    WorldStudioSyncPayload {
        source_app: "Akunarch".to_string(),
        force_draft,
        locations,
        chunks,
        videos,
    }
}

fn contains_phrase_boundary(haystack_lower: &str, phrase: &str) -> bool {
    let mut search_from = 0;
    while let Some(rel_idx) = haystack_lower[search_from..].find(phrase) {
        let start = search_from + rel_idx;
        let end = start + phrase.len();
        let prev_ok = haystack_lower[..start]
            .chars()
            .next_back()
            .is_none_or(|c| !c.is_alphanumeric());
        let next_ok = haystack_lower[end..]
            .chars()
            .next()
            .is_none_or(|c| !c.is_alphanumeric());
        if prev_ok && next_ok {
            return true;
        }
        search_from = start + phrase.chars().next().map_or(1, char::len_utf8);
    }
    false
}

/// Runs Pre-Flight QA & Canon Audit (`Rule #5`, `Rule #34`, `Rule #36`, `Zero-Spoiler`, file checks).
pub fn audit_project_for_sync(manifest: &ProjectManifest, force_draft: bool) -> QaAuditReport {
    let mut findings = Vec::new();

    // 1. Rule #5 Draft-First
    if force_draft {
        findings.push(QaFinding {
            severity: "pass".into(),
            rule_code: "RULE_5_DRAFT_FIRST".into(),
            message: "Đảm bảo Draft-First: gói đẩy sang Selorson giữ trạng thái Nháp (force_draft = true, is_active = false).".into(),
        });
    } else {
        findings.push(QaFinding {
            severity: "warning".into(),
            rule_code: "RULE_5_DRAFT_FIRST".into(),
            message: "force_draft đang tắt (chỉ dùng khi tác giả chủ động cập nhật địa danh đã duyệt).".into(),
        });
    }

    // 2. Zero-Spoiler Guardrail for Location / Chunk dioramas
    if matches!(manifest.kind.as_str(), "clockwork" | "open_world") {
        let mut all_paths: Vec<&str> = manifest.concept_paths.iter().map(String::as_str).collect();
        if let Some(img) = manifest.local_image_path.as_deref() {
            all_paths.push(img);
        }
        for p in all_paths {
            let lower = p.to_ascii_lowercase();
            if lower.contains("black_crystal_seal") {
                findings.push(QaFinding {
                    severity: "blocker".into(),
                    rule_code: "ZERO_SPOILER_DIORAMA".into(),
                    message: format!(
                        "Vi phạm Zero-Spoiler: tệp '{p}' chứa chi tiết phong ấn nhân vật, cấm đưa vào mô hình địa danh /world!"
                    ),
                });
            }
        }
    }

    // 3. Rule #34 Subtext Only (No external philosopher/author/work names in VI or EN)
    let text_corpus = format!(
        "{}\n{}\n{}\n{}",
        manifest.title, manifest.description_vi, manifest.title_en, manifest.description_en
    );
    let text_lower = text_corpus.to_lowercase();
    for forbidden_name in [
        "trang tử",
        "khổng tử",
        "nietzsche",
        "dostoevsky",
        "kant",
        "kantian",
        "rawls",
        "rawlsian",
        "evagrius ponticus",
        "steins;gate",
    ] {
        if contains_phrase_boundary(&text_lower, forbidden_name) {
            findings.push(QaFinding {
                severity: "blocker".into(),
                rule_code: "RULE_34_SUBTEXT_ONLY".into(),
                message: format!(
                    "Vi phạm Rule #34 (Subtext Only): phát hiện tên riêng ngoại lai '{forbidden_name}' trong hồ sơ dự án."
                ),
            });
        }
    }

    // 4. Rule #36 Southern Dialect Check
    let vi_lower = format!("{} {}", manifest.title, manifest.description_vi).to_lowercase();
    for northern_term in [
        "bát cháo",
        "cái bát",
        "bát nước",
        "cái thìa",
        "cái cốc",
        "cái ô",
        "quả trứng",
        "cái đĩa",
        "cái chăn",
        "cái đệm",
        "chậu rửa",
        "lúc nãy",
    ] {
        if contains_phrase_boundary(&vi_lower, northern_term) {
            findings.push(QaFinding {
                severity: "warning".into(),
                rule_code: "RULE_36_SOUTHERN_LEXICON".into(),
                message: format!(
                    "Nhắc nhở Rule #36 (Phương ngữ Nam Bộ): nên thay '{northern_term}' bằng từ chuẩn Nam Bộ (chén/tô, muỗng, ly/tách, cây dù, hột gà/cái trứng, cái dĩa, cái mền, cái nệm, bồn rửa, hồi nãy)."
                ),
            });
        }
    }

    // 5. File path existence verification
    for (idx, cp) in manifest.concept_paths.iter().enumerate() {
        let trimmed_cp = cp.trim();
        if !trimmed_cp.is_empty() && !Path::new(trimmed_cp).is_file() {
            findings.push(QaFinding {
                severity: "blocker".into(),
                rule_code: "MISSING_LOCAL_FILE".into(),
                message: format!(
                    "Tệp khai báo tại concept_paths[{idx}] không tồn tại trên ổ đĩa: {trimmed_cp}"
                ),
            });
        }
    }
    for (field_label, opt_path) in [
        ("local_image_path", manifest.local_image_path.as_deref()),
        ("bgm_audio_path", manifest.bgm_audio_path.as_deref()),
        ("clockwork.glb_path", manifest.clockwork.glb_path.as_deref()),
        (
            "clockwork.intro_video_path",
            manifest.clockwork.intro_video_path.as_deref(),
        ),
        (
            "chunks.pack_zip_path",
            manifest.chunks.pack_zip_path.as_deref(),
        ),
        (
            "chunks.heightmap_path",
            manifest.chunks.heightmap_path.as_deref(),
        ),
        (
            "chunks.splat_path",
            manifest.chunks.splat_path.as_deref(),
        ),
        (
            "stage_vn.episode_zip_path",
            manifest.stage_vn.episode_zip_path.as_deref(),
        ),
        ("cinema.video_path", manifest.cinema.video_path.as_deref()),
        (
            "cinema.thumbnail_path",
            manifest.cinema.thumbnail_path.as_deref(),
        ),
    ] {
        if let Some(raw_p) = opt_path.map(str::trim).filter(|s| !s.is_empty()) {
            if !Path::new(raw_p).is_file() {
                findings.push(QaFinding {
                    severity: "blocker".into(),
                    rule_code: "MISSING_LOCAL_FILE".into(),
                    message: format!("Tệp khai báo tại {field_label} không tồn tại trên ổ đĩa: {raw_p}"),
                });
            }
        }
    }

    // 5b. Deep VN Episode & Cinema Subtitle Prose Audit (Rule #36 + Rule #34)
    if let Some(ep_json_path) = manifest
        .stage_vn
        .episode_json_path
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
    {
        if Path::new(ep_json_path).is_file() {
            if let Ok(raw_ep) = std::fs::read_to_string(ep_json_path) {
                if let Ok(ep_doc) =
                    serde_json::from_str::<crate::workbenches::VnEpisodeDocument>(&raw_ep)
                {
                    for issue in crate::workbenches::lint_vn_episode_prose(&ep_doc) {
                        findings.push(QaFinding {
                            severity: issue.severity,
                            rule_code: issue.rule_code,
                            message: format!("[VN {}] {}", issue.location, issue.message),
                        });
                    }
                }
            }
        }
    }

    for cue in &manifest.cinema.subtitles {
        if cue.text_vi.contains('—') {
            findings.push(QaFinding {
                severity: "blocker".into(),
                rule_code: "RULE_36_NO_EM_DASH".into(),
                message: format!(
                    "Phụ đề cinema cue '{}' chứa dấu gạch ngang dài '—' bị cấm theo Rule #36.",
                    cue.id
                ),
            });
        }
        if contains_phrase_boundary(&cue.text_vi.to_lowercase(), "ạ") {
            findings.push(QaFinding {
                severity: "blocker".into(),
                rule_code: "RULE_36_NO_PARTICLE_A".into(),
                message: format!(
                    "Phụ đề cinema cue '{}' dùng trợ từ 'ạ' trái phương ngữ Nam Bộ (Rule #36).",
                    cue.id
                ),
            });
        }
    }

    // Cinema sync requires an actual video file on disk so Selorson ingests it
    if manifest.kind == "cinema"
        && manifest
            .cinema
            .video_path
            .as_deref()
            .map(str::trim)
            .unwrap_or("")
            .is_empty()
    {
        findings.push(QaFinding {
            severity: "warning".into(),
            rule_code: "CINEMA_VIDEO_PENDING".into(),
            message: "Dự án loại 'cinema' chưa gắn cinema.video_path (.mp4); Selorson sẽ bỏ qua mục video trống.".into(),
        });
    }

    let has_blocker = findings.iter().any(|f| f.severity == "blocker");
    if !has_blocker {
        findings.push(QaFinding {
            severity: "pass".into(),
            rule_code: "CANON_QA_READY".into(),
            message: "Hồ sơ dự án đạt chuẩn kiểm định Canon & Hợp đồng WorldStudioSyncPayload.".into(),
        });
    }

    let payload_preview = build_sync_payload_for_project(manifest, force_draft);

    QaAuditReport {
        slug: manifest.slug.clone(),
        passed: !has_blocker,
        draft_first_enforced: force_draft,
        findings,
        payload_preview,
    }
}

/// Logs in via `POST /api/v1/auth/login` on Selorson and saves the returned JWT token.
pub async fn login_to_selorson(
    conn_db_path: &Path,
    base_url: &str,
    email: &str,
    password: &str,
) -> Result<Value, String> {
    let clean_url = normalize_base_url(base_url)?;
    let endpoint = format!("{clean_url}/api/v1/auth/login");
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
        .map_err(|e| e.to_string())?;

    let resp = client
        .post(&endpoint)
        .json(&json!({
            "email": email.trim(),
            "password": password,
            "remember_me": true
        }))
        .send()
        .await
        .map_err(|e| format!("Không kết nối được tới Selorson ({endpoint}): {e}"))?;

    let status = resp.status();
    let body: Value = resp
        .json()
        .await
        .map_err(|e| format!("Phản hồi đăng nhập không hợp lệ (HTTP {status}): {e}"))?;

    if !body.get("success").and_then(Value::as_bool).unwrap_or(false) {
        let msg = body
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("Đăng nhập thất bại");
        return Err(format!("Selorson từ chối đăng nhập: {msg}"));
    }

    let token = body
        .get("data")
        .and_then(|d| d.get("token"))
        .and_then(Value::as_str)
        .ok_or_else(|| "Đăng nhập thành công nhưng không nhận được access token (có thể tài khoản bật 2FA — hãy dán Bearer Token trực tiếp).".to_string())?;

    let conn = crate::db::open_akunarch_db_at(conn_db_path)?;
    save_selorson_config(&conn, &clean_url, Some(token))?;

    Ok(body)
}

fn read_jwt_secret_from_env_file(env_path: &Path) -> Option<String> {
    let raw = std::fs::read_to_string(env_path).ok()?;
    for line in raw.lines() {
        let trimmed = line.trim();
        if let Some(rest) = trimmed.strip_prefix("JWT_SECRET=") {
            let val = rest.trim().trim_matches('"').trim_matches('\'');
            if !val.is_empty() {
                return Some(val.to_string());
            }
        }
    }
    None
}

/// Attempts 1-click Local Beta Admin authentication when `Selorson Beta` is running on loopback (`127.0.0.1` / `localhost` / `[::1]`).
/// Reads `JWT_SECRET` (read-only) from `%APPDATA%\com.selorson.app\backend.env` (release `Selorson Admin\app.exe`)
/// and `E:\Selorson\backend-v3\.env` (standalone `backend-v3`), testing both `::desktop-local` and standalone secrets.
pub fn mint_local_selorson_beta_candidates() -> Vec<String> {
    let mut env_paths: Vec<std::path::PathBuf> = Vec::new();
    if let Some(appdata) = std::env::var_os("APPDATA") {
        env_paths.push(
            std::path::PathBuf::from(appdata)
                .join("com.selorson.app")
                .join("backend.env"),
        );
    }
    env_paths.push(std::path::PathBuf::from(r"E:\Selorson\backend-v3\.env"));

    let mut base_secrets: Vec<String> = Vec::new();
    for p in &env_paths {
        if let Some(sec) = read_jwt_secret_from_env_file(p) {
            if !base_secrets.contains(&sec) {
                base_secrets.push(sec);
            }
        }
    }
    if base_secrets.is_empty() {
        return Vec::new();
    }

    let now = Utc::now();
    let exp = (now + Duration::hours(12)).timestamp();
    let iat = now.timestamp();

    let mut out = Vec::new();
    for secret in base_secrets {
        for candidate_secret in [format!("{secret}::desktop-local"), secret] {
            for auth_ver in 0..=5i64 {
                let claims = LocalBetaClaims {
                    sub: 1,
                    role: "admin".to_string(),
                    token_type: "access".to_string(),
                    auth_version: auth_ver,
                    remember_me: false,
                    exp,
                    iat,
                };
                if let Ok(tok) = encode(
                    &Header::default(),
                    &claims,
                    &EncodingKey::from_secret(candidate_secret.as_bytes()),
                ) {
                    out.push(tok);
                }
            }
        }
    }
    out
}

pub fn is_loopback_url(url: &str) -> bool {
    let trimmed = url.trim();
    let Some(rest) = trimmed
        .strip_prefix("http://")
        .or_else(|| trimmed.strip_prefix("https://"))
    else {
        return false;
    };
    let authority = rest.split(['/', '?', '#']).next().unwrap_or("");
    if authority.is_empty() || authority.contains('@') {
        return false;
    }
    let host = if let Some(bracketed) = authority.strip_prefix('[') {
        let Some((ipv6, after)) = bracketed.split_once(']') else {
            return false;
        };
        if !after.is_empty() && !after.starts_with(':') {
            return false;
        }
        ipv6
    } else {
        authority.split_once(':').map_or(authority, |(h, _port)| h)
    };
    host.eq_ignore_ascii_case("localhost") || host == "127.0.0.1" || host == "::1"
}

async fn resolve_initial_token(
    conn_db_path: &Path,
    clean_url: &str,
    client: &reqwest::Client,
) -> Result<String, String> {
    let saved_token = crate::db::open_akunarch_db_at(conn_db_path)
        .ok()
        .and_then(|c| get_setting(&c, "selorson_token"))
        .unwrap_or_default();

    if let Ok(clean_tok) = sanitize_bearer_token(&saved_token) {
        if !clean_tok.is_empty() {
            return Ok(clean_tok);
        }
    }

    try_mint_loopback_token(conn_db_path, clean_url, client).await
}

async fn try_mint_loopback_token(
    conn_db_path: &Path,
    clean_url: &str,
    client: &reqwest::Client,
) -> Result<String, String> {
    if is_loopback_url(clean_url) {
        let overview_url = format!("{clean_url}/api/v1/admin/world/overview");
        for candidate in mint_local_selorson_beta_candidates() {
            match client.get(&overview_url).bearer_auth(&candidate).send().await {
                Ok(resp) if resp.status().is_success() => {
                    if let Ok(conn) = crate::db::open_akunarch_db_at(conn_db_path) {
                        let _ = set_setting(&conn, "selorson_token", &candidate);
                    }
                    return Ok(candidate);
                }
                Err(e) => {
                    return Err(format!(
                        "Selorson Beta tại {clean_url} hiện chưa bật (hãy mở Selorson Admin hoặc backend-v3): {e}"
                    ));
                }
                _ => continue,
            }
        }
    }

    Err(
        "Chưa có phiên đăng nhập Admin hợp lệ với Selorson. Hãy đăng nhập hoặc dán Bearer Token."
            .to_string(),
    )
}

/// Inbound check & world catalog overview (`GET /api/v1/admin/world/overview`).
pub async fn fetch_selorson_world_overview(
    conn_db_path: &Path,
    override_base_url: Option<&str>,
) -> Result<Value, String> {
    let configured_url = {
        let conn = crate::db::open_akunarch_db_at(conn_db_path)?;
        if let Some(u) = override_base_url.filter(|s| !s.trim().is_empty()) {
            let clean = normalize_base_url(u)?;
            set_setting(&conn, "selorson_base_url", &clean)?;
            clean
        } else {
            get_selorson_config(&conn).base_url
        }
    };

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(8))
        .build()
        .map_err(|e| e.to_string())?;

    let mut token = resolve_initial_token(conn_db_path, &configured_url, &client).await?;
    let endpoint = format!("{configured_url}/api/v1/admin/world/overview");

    let mut resp = client
        .get(&endpoint)
        .bearer_auth(&token)
        .send()
        .await
        .map_err(|e| format!("Không gọi được {endpoint}: {e}"))?;

    if resp.status() == reqwest::StatusCode::UNAUTHORIZED && is_loopback_url(&configured_url) {
        if let Ok(fresh) = try_mint_loopback_token(conn_db_path, &configured_url, &client).await {
            token = fresh;
            resp = client
                .get(&endpoint)
                .bearer_auth(&token)
                .send()
                .await
                .map_err(|e| format!("Không gọi được {endpoint}: {e}"))?;
        }
    }

    let status = resp.status();
    let body: Value = resp
        .json()
        .await
        .map_err(|e| format!("Phản hồi JSON từ {endpoint} lỗi (HTTP {status}): {e}"))?;

    if !status.is_success() || !body.get("success").and_then(Value::as_bool).unwrap_or(false) {
        let msg = body
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("Không đọc được tổng quan /admin/world/overview");
        return Err(format!("Selorson trả lỗi (HTTP {status}): {msg}"));
    }

    Ok(body)
}

/// Outbound push (`POST /api/v1/admin/sync/world-studio`) with mandatory QA audit & `sync_logs` persistence.
pub async fn push_project_to_selorson(
    conn_db_path: &Path,
    slug: &str,
    force_draft: Option<bool>,
    override_base_url: Option<&str>,
) -> Result<Value, String> {
    let draft_flag = force_draft.unwrap_or(true);
    let (project_id, manifest, base_url) = {
        let conn = crate::db::open_akunarch_db_at(conn_db_path)?;
        let proj = get_project_by_slug(&conn, slug)?
            .ok_or_else(|| format!("Không tìm thấy dự án '{slug}' trong Akunarch."))?;
        let url = if let Some(u) = override_base_url.filter(|s| !s.trim().is_empty()) {
            let clean = normalize_base_url(u)?;
            set_setting(&conn, "selorson_base_url", &clean)?;
            clean
        } else {
            get_selorson_config(&conn).base_url
        };
        (proj.id, proj.manifest, url)
    };

    let audit = audit_project_for_sync(&manifest, draft_flag);
    if !audit.passed {
        let blockers: Vec<String> = audit
            .findings
            .iter()
            .filter(|f| f.severity == "blocker")
            .map(|f| format!("[{}] {}", f.rule_code, f.message))
            .collect();
        return Err(format!(
            "Chặn đồng bộ do vi phạm kiểm định QA:\n{}",
            blockers.join("\n")
        ));
    }

    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(30))
        .build()
        .map_err(|e| e.to_string())?;

    let mut token = resolve_initial_token(conn_db_path, &base_url, &client).await?;
    let endpoint = format!("{base_url}/api/v1/admin/sync/world-studio");

    let payload = audit.payload_preview;
    let payload_summary = json!({
        "slug": manifest.slug,
        "kind": manifest.kind,
        "force_draft": payload.force_draft,
        "locations_count": payload.locations.len(),
        "chunks_count": payload.chunks.len(),
        "videos_count": payload.videos.len(),
    });

    let mut resp = client
        .post(&endpoint)
        .bearer_auth(&token)
        .json(&payload)
        .send()
        .await
        .map_err(|e| format!("Lỗi gửi POST tới {endpoint}: {e}"))?;

    if resp.status() == reqwest::StatusCode::UNAUTHORIZED && is_loopback_url(&base_url) {
        if let Ok(fresh) = try_mint_loopback_token(conn_db_path, &base_url, &client).await {
            token = fresh;
            resp = client
                .post(&endpoint)
                .bearer_auth(&token)
                .json(&payload)
                .send()
                .await
                .map_err(|e| format!("Lỗi gửi POST tới {endpoint}: {e}"))?;
        }
    }

    let status = resp.status();
    let resp_json: Value = resp
        .json()
        .await
        .unwrap_or_else(|e| json!({ "success": false, "http_status": status.as_u16(), "parse_error": e.to_string() }));

    // Record in sync_logs regardless of outcome for full auditability
    {
        let conn = crate::db::open_akunarch_db_at(conn_db_path)?;
        let now = Utc::now().to_rfc3339();
        let _ = conn.execute(
            "INSERT INTO sync_logs (project_id, target_url, payload_summary_json, response_json, created_at)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                project_id,
                endpoint,
                serde_json::to_string(&payload_summary).unwrap_or_default(),
                serde_json::to_string(&resp_json).unwrap_or_default(),
                now
            ],
        );

        if status.is_success() && resp_json.get("success").and_then(Value::as_bool).unwrap_or(false)
        {
            let new_status = if draft_flag { "synced_draft" } else { "synced" };
            let _ = conn.execute(
                "UPDATE projects SET status = ?2, last_synced_at = ?3, updated_at = ?3 WHERE id = ?1",
                params![project_id, new_status, now],
            );
        }
    }

    if !status.is_success() || !resp_json.get("success").and_then(Value::as_bool).unwrap_or(false) {
        let msg = resp_json
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("Đồng bộ thất bại");
        return Err(format!("Selorson trả lỗi (HTTP {status}): {msg}"));
    }

    Ok(resp_json)
}

pub fn list_sync_logs(conn: &Connection, limit: usize) -> Result<Vec<SyncLogRow>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT id, project_id, target_url, payload_summary_json, response_json, created_at
             FROM sync_logs
             ORDER BY id DESC
             LIMIT ?1",
        )
        .map_err(|e| format!("Lỗi đọc bảng sync_logs: {e}"))?;
    let rows = stmt
        .query_map(params![limit.max(1) as i64], |r| {
            let sum_raw: String = r.get(3)?;
            let resp_raw: String = r.get(4)?;
            Ok(SyncLogRow {
                id: r.get(0)?,
                project_id: r.get(1)?,
                target_url: r.get(2)?,
                payload_summary: serde_json::from_str(&sum_raw).unwrap_or_else(|_| json!({})),
                response: serde_json::from_str(&resp_raw).unwrap_or_else(|_| json!({})),
                created_at: r.get(5)?,
            })
        })
        .map_err(|e| format!("Lỗi duyệt sync_logs: {e}"))?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(|e| e.to_string())?);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::db::open_akunarch_db_at;
    use crate::projects::{create_project_in_root, CreateProjectInput};
    use tokio::io::{AsyncReadExt, AsyncWriteExt};
    use tokio::net::TcpListener;

    #[test]
    fn sync_payload_sends_portable_master_glb_not_ktx2_runtime() {
        let conn = Connection::open_in_memory().unwrap();
        crate::db::init_schema(&conn).unwrap();
        let tmp_root = std::env::temp_dir().join(format!(
            "akunarch_sync_master_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(5)
        ));
        let proj = create_project_in_root(
            &conn,
            &tmp_root,
            CreateProjectInput {
                slug: "ktx-demo".into(),
                title: "Đền Thử".into(),
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
        let clock = tmp_root.join("ktx-demo").join("clockwork");
        std::fs::create_dir_all(clock.join("_master")).unwrap();
        std::fs::write(clock.join("ktx-demo.glb"), b"bc7").unwrap();
        std::fs::write(clock.join("_master").join("ktx-demo.glb"), b"jpeg").unwrap();
        let runtime = clock.join("ktx-demo.glb").to_string_lossy().to_string();
        let master = clock.join("_master").join("ktx-demo.glb").to_string_lossy().to_string();

        let mut m = proj.manifest.clone();
        m.clockwork.glb_path = Some(runtime.clone());
        let v = serde_json::to_value(build_sync_payload_for_project(&m, true)).unwrap();
        let loc = &v["locations"][0];
        assert_eq!(loc["local_clockwork_pack_path"], json!(master));
        assert_eq!(loc["local_desktop_pack_path"], json!(master));

        let mut c = proj.manifest.clone();
        c.kind = "open_world".into();
        c.chunks.placements = serde_json::from_value(json!([
            { "id": "p1", "label": "Đền", "glb_path": runtime, "x": 1.0 }
        ]))
        .unwrap();
        let cv = serde_json::to_value(build_sync_payload_for_project(&c, true)).unwrap();
        let pl = cv
            .pointer("/chunks/0/placements/0/glb_path")
            .unwrap_or_else(|| panic!("không thấy placements trong payload: {cv}"));
        assert_eq!(pl, &json!(master));

        // P0: có bản cơ khí → gói sa bàn (clockwork pack) là bản cơ khí _master, gói desktop vẫn là bản thật
        std::fs::write(clock.join("ktx-demo_mechanism.glb"), b"bc7").unwrap();
        std::fs::write(clock.join("_master").join("ktx-demo_mechanism.glb"), b"jpeg").unwrap();
        let mut mm = proj.manifest.clone();
        mm.clockwork.glb_path = Some(runtime.clone());
        mm.clockwork.mechanism_glb_path = Some(clock.join("ktx-demo_mechanism.glb").to_string_lossy().to_string());
        let mv = serde_json::to_value(build_sync_payload_for_project(&mm, true)).unwrap();
        let mloc = &mv["locations"][0];
        let mech_master = clock.join("_master").join("ktx-demo_mechanism.glb").to_string_lossy().to_string();
        assert_eq!(mloc["local_clockwork_pack_path"], json!(mech_master));
        assert_eq!(mloc["local_desktop_pack_path"], json!(master));

        let _ = std::fs::remove_dir_all(&tmp_root);
    }

    #[test]
    fn qa_audit_catches_spoiler_seal_and_subtext_violations_and_enforces_draft_first() {
        let conn = Connection::open_in_memory().unwrap();
        crate::db::init_schema(&conn).unwrap();
        let tmp_root = std::env::temp_dir().join(format!(
            "akunarch_qa_test_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(3)
        ));
        let proj = create_project_in_root(
            &conn,
            &tmp_root,
            CreateProjectInput {
                slug: "dun-scaith-test".into(),
                title: "Pháo Đài Dún Scáith".into(),
                title_en: "Dun Scaith Fortress".into(),
                kind: "clockwork".into(),
                planet: "earth".into(),
                region_slug: "alba".into(),
                era: "1000 TCN".into(),
                era_year: Some(-1000),
                lat: Some(57.2),
                lng: Some(-6.2),
                biome: "coastal-cliff".into(),
                chunk_x: 0,
                chunk_z: 0,
                cowriter_entity_id: None,
                cowriter_key: String::new(),
                unlock_chapter: Some(8),
                description_vi: "Lấy cảm hứng từ Nietzsche và bát cháo nóng.".into(),
                description_en: String::new(),
                local_image_path: None,
                concept_paths: vec![
                    r"E:\Tools-3D\concepts\concept_dun_scaith_black_crystal_seal_v5.jpg".into(),
                ],
                bgm_audio_path: None,
                glb_path: None,
            },
        )
        .unwrap();

        let report = audit_project_for_sync(&proj.manifest, true);
        assert!(!report.passed, "spoiler + subtext violation must block sync");
        assert!(report
            .findings
            .iter()
            .any(|f| f.rule_code == "ZERO_SPOILER_DIORAMA" && f.severity == "blocker"));
        assert!(report
            .findings
            .iter()
            .any(|f| f.rule_code == "RULE_34_SUBTEXT_ONLY" && f.severity == "blocker"));
        assert!(report
            .findings
            .iter()
            .any(|f| f.rule_code == "RULE_36_SOUTHERN_LEXICON" && f.severity == "warning"));

        assert!(contains_phrase_boundary("trời mưa cầm cái ô.", "cái ô"));
        assert!(!contains_phrase_boundary("cái ông lão bên đồi", "cái ô"));

        // Verify Rule #34 also catches English description_en violations ("Kant" / "Rawls")
        let mut en_manifest = proj.manifest.clone();
        en_manifest.description_vi = "Pháo đài cổ bên bờ đá đen.".into();
        en_manifest.concept_paths.clear();
        en_manifest.description_en = "Inspired by Kant and Rawlsian ethics.".into();
        let en_report = audit_project_for_sync(&en_manifest, true);
        assert!(!en_report.passed, "Rule #34 in description_en must block sync");

        let _ = std::fs::remove_dir_all(&tmp_root);
    }

    #[test]
    fn token_sanitization_and_loopback_host_parsing_are_utf8_and_spoof_safe() {
        let conn = Connection::open_in_memory().unwrap();
        crate::db::init_schema(&conn).unwrap();

        // Even if non-ASCII UTF-8 bytes exist in studio_settings, get_selorson_config must never panic on char boundary
        set_setting(
            &conn,
            "selorson_token",
            "Đền_Thờ_Ngũ_Giác_Chuỗi_Unicode_Dài_Hơn_16_Ký_Tự",
        )
        .unwrap();
        let cfg_unicode = get_selorson_config(&conn);
        assert!(cfg_unicode.has_token);
        assert!(cfg_unicode.token_preview.contains('…'));

        // Saving non-ASCII token via save_selorson_config returns clean Err instead of storing bad header bytes
        let err = save_selorson_config(&conn, "http://127.0.0.1:8001", Some("Đền Thờ Token"))
            .expect_err("must reject non-ASCII token");
        assert!(err.contains("Bearer Token không hợp lệ"));

        // Saving "Bearer eyJhbGci..." strips scheme cleanly
        let cfg_bearer = save_selorson_config(
            &conn,
            "http://127.0.0.1:8001/",
            Some("  Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig  "),
        )
        .unwrap();
        assert_eq!(cfg_bearer.base_url, "http://127.0.0.1:8001");
        assert_eq!(
            get_setting(&conn, "selorson_token").unwrap(),
            "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test.sig"
        );

        // Clearing token with "" works
        let cfg_cleared = save_selorson_config(&conn, "http://127.0.0.1:8001", Some("   ")).unwrap();
        assert!(!cfg_cleared.has_token);

        // Loopback host parser blocks domain spoofing
        assert!(is_loopback_url("http://127.0.0.1:8001"));
        assert!(is_loopback_url("http://localhost:8001/api/v1"));
        assert!(is_loopback_url("http://[::1]:8001"));
        assert!(!is_loopback_url("http://localhost.evil.com:8001"));
        assert!(!is_loopback_url("http://127.0.0.1.nip.io:8001"));
        assert!(!is_loopback_url("http://localhost@evil.com:8001"));
    }

    #[test]
    fn local_selorson_beta_jwt_candidates_match_backend_v3_claims() {
        let env_path = Path::new(r"E:\Selorson\backend-v3\.env");
        if !env_path.is_file() {
            return;
        }
        let candidates = mint_local_selorson_beta_candidates();
        assert!(
            candidates.len() >= 12,
            "expected at least 12 JWT candidates (desktop-local + standalone across auth_versions 0..=5), got {}",
            candidates.len()
        );

        let appdata_env = std::env::var_os("APPDATA")
            .map(|p| std::path::PathBuf::from(p).join("com.selorson.app").join("backend.env"))
            .filter(|p| p.is_file());
        let primary_env = appdata_env.as_deref().unwrap_or(env_path);
        let secret = read_jwt_secret_from_env_file(primary_env).unwrap();
        let desktop_key =
            jsonwebtoken::DecodingKey::from_secret(format!("{secret}::desktop-local").as_bytes());
        let decoded = jsonwebtoken::decode::<LocalBetaClaims>(
            &candidates[0],
            &desktop_key,
            &jsonwebtoken::Validation::default(),
        )
        .expect("decode ::desktop-local admin JWT");
        assert_eq!(decoded.claims.sub, 1);
        assert_eq!(decoded.claims.role, "admin");
        assert_eq!(decoded.claims.token_type, "access");
    }

    async fn read_full_http_request(stream: &mut tokio::net::TcpStream) -> String {
        let mut buf = Vec::with_capacity(8192);
        let mut chunk = [0u8; 4096];
        let mut header_end = None;
        let mut content_length = 0usize;

        loop {
            let n = stream.read(&mut chunk).await.unwrap();
            if n == 0 {
                break;
            }
            buf.extend_from_slice(&chunk[..n]);
            if header_end.is_none() {
                if let Some(pos) = buf.windows(4).position(|w| w == b"\r\n\r\n") {
                    let h_end = pos + 4;
                    header_end = Some(h_end);
                    let headers_str = String::from_utf8_lossy(&buf[..h_end]);
                    for line in headers_str.lines() {
                        if let Some((k, v)) = line.split_once(':') {
                            if k.trim().eq_ignore_ascii_case("content-length") {
                                content_length = v.trim().parse::<usize>().unwrap_or(0);
                            }
                        }
                    }
                }
            }
            if let Some(h_end) = header_end {
                if buf.len() >= h_end + content_length {
                    break;
                }
            }
        }
        String::from_utf8_lossy(&buf).to_string()
    }

    #[tokio::test]
    async fn bidirectional_selorson_gateway_fetches_overview_and_pushes_draft_payload() {
        let listener = TcpListener::bind("127.0.0.1:0").await.unwrap();
        let port = listener.local_addr().unwrap().port();
        let base_url = format!("http://127.0.0.1:{port}");

        // Spawn lightweight HTTP server verifying GET /admin/world/overview & POST /admin/sync/world-studio
        let server_handle = tokio::spawn(async move {
            for _ in 0..2 {
                let (mut stream, _) = listener.accept().await.unwrap();
                let req = read_full_http_request(&mut stream).await;

                assert!(
                    req.to_ascii_lowercase()
                        .contains("authorization: bearer test-admin-jwt"),
                    "missing Bearer header in request: {req}"
                );

                let resp_body = if req.starts_with("GET /api/v1/admin/world/overview") {
                    json!({
                        "success": true,
                        "data": {
                            "summary": {
                                "total_places": 13,
                                "published_places": 13,
                                "pending_places": 0,
                                "total_chunks": 0,
                                "published_chunks": 0,
                                "pending_chunks": 0,
                                "with_intro_video": 2,
                                "with_desktop_pack": 13,
                                "with_vn_episode": 0,
                                "total_videos": 4
                            },
                            "storage_mode": "local",
                            "items": []
                        }
                    })
                } else if req.starts_with("POST /api/v1/admin/sync/world-studio") {
                    // Verify body contains source_app="Akunarch" & force_draft=true
                    let body_part = req.split("\r\n\r\n").nth(1).unwrap_or("{}");
                    let parsed: Value = serde_json::from_str(body_part).unwrap();
                    assert_eq!(parsed["source_app"], "Akunarch");
                    assert_eq!(parsed["force_draft"], true);
                    assert_eq!(parsed["locations"][0]["slug"], "eldarin-hollow");

                    json!({
                        "success": true,
                        "message": "Đã nhận tài nguyên từ World Studio vào hàng chờ kiểm duyệt (Nháp)!",
                        "data": {
                            "source_app": "Akunarch",
                            "created_locations": 1,
                            "updated_locations": 0,
                            "created_chunks": 0,
                            "updated_chunks": 0,
                            "synced_videos": 0,
                            "synced_translations": 1
                        }
                    })
                } else {
                    json!({ "success": false, "message": "Unexpected route" })
                };

                let body_str = serde_json::to_string(&resp_body).unwrap();
                let http_resp = format!(
                    "HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: {}\r\nConnection: close\r\n\r\n{}",
                    body_str.len(),
                    body_str
                );
                stream.write_all(http_resp.as_bytes()).await.unwrap();
            }
        });

        let tmp_dir = std::env::temp_dir().join(format!(
            "akunarch_sync_test_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(4)
        ));
        std::fs::create_dir_all(&tmp_dir).unwrap();
        let db_path = tmp_dir.join("akunarch.db");
        let proj_root = tmp_dir.join("projects");

        {
            let conn = open_akunarch_db_at(&db_path).unwrap();
            save_selorson_config(&conn, &base_url, Some("test-admin-jwt")).unwrap();
            create_project_in_root(
                &conn,
                &proj_root,
                CreateProjectInput {
                    slug: "eldarin-hollow".into(),
                    title: "Thung Lũng Thánh Địa Eldarin".into(),
                    title_en: "Sacred Hollow of Eldarin".into(),
                    kind: "clockwork".into(),
                    planet: "akunalia".into(),
                    region_slug: "eldarin-highlands".into(),
                    era: "Kỷ Nguyên Khởi Nguyên".into(),
                    era_year: None,
                    lat: Some(14.5),
                    lng: Some(42.8),
                    biome: "crystal-forest".into(),
                    chunk_x: 0,
                    chunk_z: 0,
                    cowriter_entity_id: None,
                    cowriter_key: "loc:eldarin-hollow".into(),
                    unlock_chapter: Some(1),
                    description_vi: "Thung lũng cổ thụ mạch thần năng đón nắng sớm.".into(),
                    description_en: "Valley of the ancient Lifestream tree.".into(),
                    local_image_path: None,
                    concept_paths: vec![],
                    bgm_audio_path: None,
                    glb_path: None,
                },
            )
            .unwrap();
        }

        let overview = fetch_selorson_world_overview(&db_path, None)
            .await
            .expect("fetch overview");
        assert_eq!(overview["data"]["summary"]["total_places"], 13);

        let sync_res = push_project_to_selorson(&db_path, "eldarin-hollow", Some(true), Some(&base_url))
            .await
            .expect("push draft project");
        assert_eq!(sync_res["data"]["created_locations"], 1);

        server_handle.await.unwrap();

        let conn = open_akunarch_db_at(&db_path).unwrap();
        let logs = list_sync_logs(&conn, 10).unwrap();
        assert_eq!(logs.len(), 1);
        let updated_proj = get_project_by_slug(&conn, "eldarin-hollow").unwrap().unwrap();
        assert_eq!(updated_proj.status, "synced_draft");
        assert!(updated_proj.last_synced_at.is_some());

        let _ = std::fs::remove_dir_all(&tmp_dir);
    }

    #[tokio::test]
    #[ignore = "Requires live Selorson Admin / backend-v3 listening on 127.0.0.1:8001"]
    async fn live_selorson_admin_roundtrip() {
        let tmp_dir = std::env::temp_dir().join(format!(
            "akunarch_live_selorson_{}",
            Utc::now().timestamp_nanos_opt().unwrap_or(9)
        ));
        std::fs::create_dir_all(&tmp_dir).unwrap();
        let db_path = tmp_dir.join("akunarch.db");
        let proj_root = tmp_dir.join("projects");

        {
            let conn = open_akunarch_db_at(&db_path).unwrap();
            // Intentionally save NO token so 1-click ::desktop-local JWT minting is exercised live!
            save_selorson_config(&conn, "http://127.0.0.1:8001", None).unwrap();
            create_project_in_root(
                &conn,
                &proj_root,
                CreateProjectInput {
                    slug: "akunarch-live-probe-temp".into(),
                    title: "Tháp Thử Nghiệm Đồng Bộ Akunarch".into(),
                    title_en: "Akunarch Live Sync Probe Spire".into(),
                    kind: "clockwork".into(),
                    planet: "akunalia".into(),
                    region_slug: "zyberon".into(),
                    era: "Kỷ Nguyên Thứ Nhất".into(),
                    era_year: None,
                    lat: Some(12.34),
                    lng: Some(56.78),
                    biome: "crystal".into(),
                    chunk_x: 0,
                    chunk_z: 0,
                    cowriter_entity_id: None,
                    cowriter_key: "akunarch:live-probe-temp".into(),
                    unlock_chapter: Some(1),
                    description_vi: "Mẫu kiểm thử đồng bộ 2 chiều thực tế ở trạng thái Nháp.".into(),
                    description_en: "Live bidirectional draft-first sync probe.".into(),
                    local_image_path: None,
                    concept_paths: vec![],
                    bgm_audio_path: None,
                    glb_path: None,
                },
            )
            .unwrap();
        }

        let overview_before =
            fetch_selorson_world_overview(&db_path, Some("http://127.0.0.1:8001"))
                .await
                .expect("live GET /api/v1/admin/world/overview via auto-minted ::desktop-local JWT");
        assert_eq!(overview_before["success"], true);

        let push_res = push_project_to_selorson(
            &db_path,
            "akunarch-live-probe-temp",
            Some(true),
            Some("http://127.0.0.1:8001"),
        )
        .await
        .expect("live POST /api/v1/admin/sync/world-studio");
        assert_eq!(push_res["success"], true);
        assert_eq!(push_res["data"]["source_app"], "Akunarch");
        assert_eq!(push_res["data"]["created_locations"], 1);
        assert_eq!(push_res["data"]["synced_translations"], 1);

        let overview_after = fetch_selorson_world_overview(&db_path, Some("http://127.0.0.1:8001"))
            .await
            .expect("live GET /api/v1/admin/world/overview after push");
        let items = overview_after["data"]["items"].as_array().unwrap();
        let found = items
            .iter()
            .find(|it| it["slug"] == "akunarch-live-probe-temp")
            .expect("pushed draft item must appear in live Selorson overview");
        assert_eq!(
            found["is_active"], false,
            "Rule #5 Draft-First: live Selorson row must have is_active = false"
        );

        let _ = std::fs::remove_dir_all(&tmp_dir);
    }
}
