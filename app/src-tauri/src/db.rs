use chrono::Utc;
use rusqlite::{params, Connection, OptionalExtension};
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// Resolves the live data directory for Akunarch (`%LOCALAPPDATA%\Akunarch` by default,
/// or `AKUNARCH_DATA_DIR` when overridden for isolated tests).
pub fn akunarch_data_dir() -> PathBuf {
    if let Ok(custom) = std::env::var("AKUNARCH_DATA_DIR") {
        let trimmed = custom.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        if !local_app_data.trim().is_empty() {
            return PathBuf::from(local_app_data).join("Akunarch");
        }
    }
    PathBuf::from(r"E:\Akunarch\.localdata")
}

pub fn akunarch_db_path() -> PathBuf {
    akunarch_data_dir().join("akunarch.db")
}

pub fn akunarch_projects_root() -> PathBuf {
    if let Ok(custom) = std::env::var("AKUNARCH_PROJECTS_DIR") {
        let trimmed = custom.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    PathBuf::from(r"E:\Akunarch\projects")
}

pub fn open_akunarch_db() -> Result<Connection, String> {
    open_akunarch_db_at(&akunarch_db_path())
}

pub fn open_akunarch_db_at(path: &Path) -> Result<Connection, String> {
    if let Some(parent) = path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| format!("Không tạo được thư mục dữ liệu {}: {e}", parent.display()))?;
    }
    let conn = Connection::open(path)
        .map_err(|e| format!("Không mở được akunarch.db tại {}: {e}", path.display()))?;
    conn.execute_batch(
        "PRAGMA journal_mode = WAL;
         PRAGMA synchronous = NORMAL;
         PRAGMA foreign_keys = ON;
         PRAGMA busy_timeout = 5000;",
    )
    .map_err(|e| format!("Lỗi cấu hình PRAGMA cho akunarch.db: {e}"))?;

    init_schema(&conn)?;
    Ok(conn)
}

pub fn init_schema(conn: &Connection) -> Result<(), String> {
    conn.execute_batch(
        r#"
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            title TEXT NOT NULL,
            kind TEXT NOT NULL CHECK(kind IN ('clockwork', 'open_world', 'vn_episode', 'cinema')),
            planet TEXT NOT NULL DEFAULT 'akunalia' CHECK(planet IN ('akunalia', 'earth')),
            region_slug TEXT NOT NULL DEFAULT '',
            cowriter_entity_id INTEGER,
            chapter_no INTEGER,
            folder_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            last_synced_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS asset_library (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL CHECK(category IN (
                'gear', 'architecture', 'foliage', 'rock', 'prop',
                'character_rig', 'splat', 'pbr_material', 'hdr_env'
            )),
            file_path TEXT NOT NULL,
            thumb_path TEXT NOT NULL DEFAULT '',
            poly_count INTEGER NOT NULL DEFAULT 0,
            byte_size INTEGER NOT NULL DEFAULT 0,
            tags_json TEXT NOT NULL DEFAULT '[]',
            license_clean INTEGER NOT NULL DEFAULT 1
        );

        CREATE TABLE IF NOT EXISTS world_chunks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            planet TEXT NOT NULL DEFAULT 'akunalia' CHECK(planet IN ('akunalia', 'earth')),
            chunk_x INTEGER NOT NULL,
            chunk_z INTEGER NOT NULL,
            world_size REAL NOT NULL DEFAULT 256.0,
            region_slug TEXT NOT NULL DEFAULT '',
            biome TEXT NOT NULL DEFAULT 'temperate',
            unlock_chapter INTEGER NOT NULL DEFAULT 1,
            heightmap_path TEXT NOT NULL DEFAULT '',
            pack_zip_path TEXT NOT NULL DEFAULT '',
            pack_version TEXT NOT NULL DEFAULT '0.1.0',
            spawn_points_json TEXT NOT NULL DEFAULT '[]',
            vn_triggers_json TEXT NOT NULL DEFAULT '[]',
            UNIQUE(planet, chunk_x, chunk_z)
        );

        CREATE TABLE IF NOT EXISTS gpu_jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            worker_kind TEXT NOT NULL CHECK(worker_kind IN (
                'blender', 'comfyui', 'worldgen', 'hunyuan3d', 'tts',
                'materialcraft', 'effectcraft', 'filmcraft', 'toneforge'
            )),
            payload_json TEXT NOT NULL DEFAULT '{}',
            status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN (
                'queued', 'running', 'completed', 'failed', 'cancelled'
            )),
            progress_pct REAL NOT NULL DEFAULT 0.0,
            vram_peak_mb INTEGER NOT NULL DEFAULT 0,
            output_path TEXT NOT NULL DEFAULT '',
            error_log TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS sync_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            target_url TEXT NOT NULL,
            payload_summary_json TEXT NOT NULL DEFAULT '{}',
            response_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS studio_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        "#,
    )
    .map_err(|e| format!("Không khởi tạo được schema akunarch.db: {e}"))?;

    // Idempotent Phase 2 Open-World Chunk columns migration
    for alter_sql in [
        "ALTER TABLE world_chunks ADD COLUMN splat_path TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE world_chunks ADD COLUMN water_level REAL NOT NULL DEFAULT 1.6",
        "ALTER TABLE world_chunks ADD COLUMN foliage_density REAL NOT NULL DEFAULT 0.65",
        "ALTER TABLE world_chunks ADD COLUMN placements_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE world_chunks ADD COLUMN audio_zones_json TEXT NOT NULL DEFAULT '[]'",
        "ALTER TABLE world_chunks ADD COLUMN heightmap_grid_json TEXT NOT NULL DEFAULT '[]'",
    ] {
        let _ = conn.execute(alter_sql, []);
    }

    Ok(())
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssetLibraryRow {
    pub id: i64,
    pub slug: String,
    pub category: String,
    pub file_path: String,
    pub thumb_path: String,
    pub poly_count: i64,
    pub byte_size: i64,
    pub tags: Vec<String>,
    pub license_clean: bool,
}

pub fn get_setting(conn: &Connection, key: &str) -> Option<String> {
    conn.query_row(
        "SELECT value FROM studio_settings WHERE key = ?1",
        params![key],
        |row| row.get::<_, String>(0),
    )
    .optional()
    .ok()
    .flatten()
}

pub fn set_setting(conn: &Connection, key: &str, value: &str) -> Result<(), String> {
    let now = Utc::now().to_rfc3339();
    conn.execute(
        "INSERT INTO studio_settings (key, value, updated_at) VALUES (?1, ?2, ?3)
         ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
        params![key, value, now],
    )
    .map_err(|e| format!("Không lưu được cấu hình {key}: {e}"))?;
    Ok(())
}

pub fn scan_and_index_local_assets(conn: &Connection) -> Result<Vec<AssetLibraryRow>, String> {
    let polyhaven_root = Path::new(r"E:\Tools-3D\polyhaven");
    if polyhaven_root.is_dir() {
        index_polyhaven_dir(conn, polyhaven_root)?;
    }
    let ai_meshes_root = Path::new(r"E:\Tools-3D\ai_meshes");
    if ai_meshes_root.is_dir() {
        if let Ok(entries) = std::fs::read_dir(ai_meshes_root) {
            for entry in entries.flatten() {
                let p = entry.path();
                if p.is_file()
                    && p.extension()
                        .and_then(|e| e.to_str())
                        .is_some_and(|ext| ext.eq_ignore_ascii_case("glb"))
                {
                    let stem = p
                        .file_stem()
                        .and_then(|s| s.to_str())
                        .unwrap_or("mesh")
                        .to_lowercase()
                        .replace('_', "-");
                    let slug = format!("kitbash-{stem}");
                    let byte_size = p.metadata().map(|m| m.len() as i64).unwrap_or(0);
                    let tags = serde_json::json!(["kitbash", "ai_mesh", "tools-3d"]).to_string();
                    let _ = conn.execute(
                        "INSERT INTO asset_library (slug, category, file_path, thumb_path, poly_count, byte_size, tags_json, license_clean)
                         VALUES (?1, 'architecture', ?2, '', 0, ?3, ?4, 1)
                         ON CONFLICT(slug) DO UPDATE SET file_path = excluded.file_path, byte_size = excluded.byte_size",
                        params![slug, p.to_string_lossy().to_string(), byte_size, tags],
                    );
                }
            }
        }
    }
    list_asset_library(conn)
}

fn index_polyhaven_dir(conn: &Connection, root: &Path) -> Result<(), String> {
    let Ok(level1) = std::fs::read_dir(root) else {
        return Ok(());
    };
    for entry in level1.flatten() {
        let p = entry.path();
        if !p.is_dir() {
            continue;
        }
        let folder_name = p
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_lowercase();
        // Either `polyhaven/<asset_slug>` or `polyhaven/textures/<asset_slug>`, `polyhaven/hdris/...`, `polyhaven/models/...`
        if matches!(folder_name.as_str(), "textures" | "hdris" | "models") {
            if let Ok(sub_entries) = std::fs::read_dir(&p) {
                for sub in sub_entries.flatten() {
                    let sp = sub.path();
                    if sp.is_dir() {
                        upsert_polyhaven_folder(conn, &sp, &folder_name);
                    } else if sp.is_file() {
                        upsert_polyhaven_file(conn, &sp, &folder_name);
                    }
                }
            }
        } else {
            upsert_polyhaven_folder(conn, &p, "textures");
        }
    }
    Ok(())
}

fn upsert_polyhaven_folder(conn: &Connection, dir: &Path, kind_hint: &str) {
    let raw_name = dir
        .file_name()
        .and_then(|n| n.to_str())
        .unwrap_or("pbr")
        .to_lowercase();
    let slug = format!("ph-{}", raw_name.replace('_', "-"));
    let category = match kind_hint {
        "hdris" => "hdr_env",
        "models" => {
            if raw_name.contains("rock") || raw_name.contains("boulder") || raw_name.contains("cliff") {
                "rock"
            } else if raw_name.contains("tree") || raw_name.contains("fern") || raw_name.contains("bush") {
                "foliage"
            } else {
                "prop"
            }
        }
        _ => "pbr_material",
    };

    let mut total_bytes = 0i64;
    let mut thumb_path = String::new();
    if let Ok(files) = std::fs::read_dir(dir) {
        for f in files.flatten() {
            let fp = f.path();
            if fp.is_file() {
                total_bytes += fp.metadata().map(|m| m.len() as i64).unwrap_or(0);
                let fname = fp
                    .file_name()
                    .and_then(|n| n.to_str())
                    .unwrap_or("")
                    .to_lowercase();
                if thumb_path.is_empty()
                    && (fname.ends_with(".jpg") || fname.ends_with(".png"))
                    && (fname.contains("diff")
                        || fname.contains("col")
                        || fname.contains("albedo")
                        || fname.contains("thumb")
                        || fname.contains("preview"))
                {
                    thumb_path = fp.to_string_lossy().to_string();
                }
            }
        }
    }
    let tags = serde_json::json!(["polyhaven", "cc0", kind_hint]).to_string();
    let _ = conn.execute(
        "INSERT INTO asset_library (slug, category, file_path, thumb_path, poly_count, byte_size, tags_json, license_clean)
         VALUES (?1, ?2, ?3, ?4, 0, ?5, ?6, 1)
         ON CONFLICT(slug) DO UPDATE SET
            file_path = excluded.file_path,
            thumb_path = CASE WHEN excluded.thumb_path != '' THEN excluded.thumb_path ELSE asset_library.thumb_path END,
            byte_size = excluded.byte_size",
        params![
            slug,
            category,
            dir.to_string_lossy().to_string(),
            thumb_path,
            total_bytes,
            tags
        ],
    );
}

fn upsert_polyhaven_file(conn: &Connection, file: &Path, kind_hint: &str) {
    let stem = file
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("asset")
        .to_lowercase();
    let slug = format!("ph-{}", stem.replace('_', "-"));
    let category = if kind_hint == "hdris"
        || file
            .extension()
            .and_then(|e| e.to_str())
            .is_some_and(|e| e.eq_ignore_ascii_case("hdr") || e.eq_ignore_ascii_case("exr"))
    {
        "hdr_env"
    } else {
        "pbr_material"
    };
    let byte_size = file.metadata().map(|m| m.len() as i64).unwrap_or(0);
    let tags = serde_json::json!(["polyhaven", "cc0", kind_hint]).to_string();
    let _ = conn.execute(
        "INSERT INTO asset_library (slug, category, file_path, thumb_path, poly_count, byte_size, tags_json, license_clean)
         VALUES (?1, ?2, ?3, '', 0, ?4, ?5, 1)
         ON CONFLICT(slug) DO UPDATE SET file_path = excluded.file_path, byte_size = excluded.byte_size",
        params![slug, category, file.to_string_lossy().to_string(), byte_size, tags],
    );
}

pub fn list_asset_library(conn: &Connection) -> Result<Vec<AssetLibraryRow>, String> {
    let mut stmt = conn
        .prepare(
            "SELECT id, slug, category, file_path, thumb_path, poly_count, byte_size, tags_json, license_clean
             FROM asset_library
             ORDER BY category ASC, slug ASC",
        )
        .map_err(|e| format!("Lỗi truy vấn asset_library: {e}"))?;
    let rows = stmt
        .query_map([], |row| {
            let tags_raw: String = row.get(7)?;
            let tags: Vec<String> = serde_json::from_str(&tags_raw).unwrap_or_default();
            let clean_int: i64 = row.get(8)?;
            Ok(AssetLibraryRow {
                id: row.get(0)?,
                slug: row.get(1)?,
                category: row.get(2)?,
                file_path: row.get(3)?,
                thumb_path: row.get(4)?,
                poly_count: row.get(5)?,
                byte_size: row.get(6)?,
                tags,
                license_clean: clean_int != 0,
            })
        })
        .map_err(|e| format!("Lỗi đọc asset_library: {e}"))?;
    let mut out = Vec::new();
    for r in rows {
        out.push(r.map_err(|e| e.to_string())?);
    }
    Ok(out)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schema_creates_all_five_master_plan_tables_and_enforces_checks() {
        let conn = Connection::open_in_memory().expect("open in memory");
        init_schema(&conn).expect("init schema");

        for expected_table in [
            "projects",
            "asset_library",
            "world_chunks",
            "gpu_jobs",
            "sync_logs",
            "studio_settings",
        ] {
            let exists: i64 = conn
                .query_row(
                    "SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name=?1",
                    params![expected_table],
                    |r| r.get(0),
                )
                .unwrap();
            assert_eq!(exists, 1, "missing table {expected_table}");
        }

        // Invalid project kind must be rejected by CHECK constraint
        let bad_kind = conn.execute(
            "INSERT INTO projects (slug, title, kind, planet, folder_path, created_at, updated_at)
             VALUES ('test-bad', 'Bad', 'invalid_kind', 'akunalia', 'E:/tmp', '2026-01-01', '2026-01-01')",
            [],
        );
        assert!(bad_kind.is_err(), "invalid project kind should fail CHECK");

        // Invalid gpu_job worker_kind must be rejected
        let bad_worker = conn.execute(
            "INSERT INTO gpu_jobs (worker_kind) VALUES ('fal_cloud_paid')",
            [],
        );
        assert!(bad_worker.is_err(), "invalid worker_kind should fail CHECK");

        set_setting(&conn, "selorson_base_url", "http://127.0.0.1:8001").unwrap();
        assert_eq!(
            get_setting(&conn, "selorson_base_url").as_deref(),
            Some("http://127.0.0.1:8001")
        );
    }
}
