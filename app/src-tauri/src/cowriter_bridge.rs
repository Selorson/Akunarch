use rusqlite::{params, Connection, OpenFlags};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::collections::HashMap;
use std::path::{Path, PathBuf};

/// Resolves `%LOCALAPPDATA%\Co-Writer` (or `COWRITER_DATA_DIR` override in tests).
pub fn cowriter_data_dir() -> PathBuf {
    if let Ok(custom) = std::env::var("COWRITER_DATA_DIR") {
        let trimmed = custom.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
        if !local_app_data.trim().is_empty() {
            return PathBuf::from(local_app_data).join("Co-Writer");
        }
    }
    PathBuf::from(r"C:\Users\Admin\AppData\Local\Co-Writer")
}

pub fn cowriter_db_path() -> PathBuf {
    cowriter_data_dir().join("co_writer.db")
}

pub fn concepts_dir() -> PathBuf {
    if let Ok(custom) = std::env::var("AKUNARCH_CONCEPTS_DIR") {
        let trimmed = custom.trim();
        if !trimmed.is_empty() {
            return PathBuf::from(trimmed);
        }
    }
    PathBuf::from(r"E:\Tools-3D\concepts")
}

/// Opens `co_writer.db` strictly in `SQLITE_OPEN_READ_ONLY` + `URI(?mode=ro)` + `PRAGMA query_only = ON`.
/// Never writes, creates, or mutates any file in Co-Writer!
pub fn open_cowriter_readonly() -> Result<Connection, String> {
    open_cowriter_readonly_at(&cowriter_db_path())
}

pub fn open_cowriter_readonly_at(db_path: &Path) -> Result<Connection, String> {
    if !db_path.is_file() {
        return Err(format!(
            "Không tìm thấy cơ sở dữ liệu Co-Writer tại {}",
            db_path.display()
        ));
    }
    let normalized = db_path.to_string_lossy().replace('\\', "/");
    let uri = format!("file:{normalized}?mode=ro");
    let flags = OpenFlags::SQLITE_OPEN_READ_ONLY
        | OpenFlags::SQLITE_OPEN_URI
        | OpenFlags::SQLITE_OPEN_NO_MUTEX;
    let conn = Connection::open_with_flags(&uri, flags)
        .or_else(|_| {
            Connection::open_with_flags(
                db_path,
                OpenFlags::SQLITE_OPEN_READ_ONLY | OpenFlags::SQLITE_OPEN_NO_MUTEX,
            )
        })
        .map_err(|e| format!("Không mở được co_writer.db ở chế độ chỉ đọc: {e}"))?;

    conn.execute_batch("PRAGMA query_only = ON; PRAGMA busy_timeout = 3000;")
        .map_err(|e| format!("Lỗi khóa PRAGMA query_only cho co_writer.db: {e}"))?;

    Ok(conn)
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultSummary {
    pub db_path: String,
    pub readonly_verified: bool,
    pub entities_count: i64,
    pub arcs_count: i64,
    pub chapters_count: i64,
    pub sketches_count: i64,
    pub manga_episodes_count: i64,
    pub manga_pages_count: i64,
    pub concepts_canon_15_count: usize,
    pub concepts_canon_extended_count: usize,
    pub concepts_total_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoryEntityItem {
    pub id: i64,
    pub subject_key: String,
    pub kind: String,
    pub name: String,
    pub role: String,
    pub summary: String,
    pub confirmed: bool,
    pub mention_count: i64,
    pub voice_profile: String,
    pub visual_anchor: String,
    pub primary_sketch_path: Option<String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct StoryArcItem {
    pub id: i64,
    pub arc_key: String,
    pub title: String,
    pub ordinal: i64,
    pub summary: String,
    pub goal: String,
    pub stakes: String,
    pub turn: String,
    pub chapter_start: Option<i64>,
    pub chapter_end: Option<i64>,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ChapterPlanItem {
    pub id: i64,
    pub chapter_no: i64,
    pub arc_id: Option<i64>,
    pub title: String,
    pub intent: String,
    pub beats: Vec<Value>,
    pub pov_entity_id: Option<i64>,
    pub pov_name: Option<String>,
    pub setting: String,
    pub status: String,
    pub era_label: String,
    pub time_span: String,
    pub opening_lens: String,
    pub emotional_turn: String,
    pub note: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SketchItem {
    pub id: i64,
    pub entity_id: Option<i64>,
    pub subject: String,
    pub kind: String,
    pub prompt: String,
    pub rel_path: String,
    pub full_path: String,
    pub exists_on_disk: bool,
    pub width: i64,
    pub height: i64,
    pub bytes: i64,
    pub note: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MangaEpisodeItem {
    pub id: i64,
    pub title: String,
    pub chapter_no: Option<i64>,
    pub mode: String,
    pub style: String,
    pub aspect_ratio: String,
    pub status: String,
    pub page_count: i64,
    pub done_pages: i64,
    pub actual_pages_in_db: i64,
    pub cover_full_path: Option<String>,
    pub note: String,
    pub updated_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MangaPageItem {
    pub id: i64,
    pub episode_id: i64,
    pub page_no: i64,
    pub title: String,
    pub layout_style: String,
    pub pacing_note: String,
    pub rel_path: String,
    pub full_path: String,
    pub exists_on_disk: bool,
    pub width: i64,
    pub height: i64,
    pub byte_size: i64,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ConceptBlueprintItem {
    pub filename: String,
    pub stem: String,
    pub full_path: String,
    pub byte_size: i64,
    pub location_slug: String,
    pub location_title_vi: String,
    pub planet: String,
    pub era: String,
    pub is_canon_15: bool,
    pub is_canon_extended: bool,
    pub spoiler_locked: bool,
    pub spoiler_note: String,
    pub architectural_note: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct VaultSnapshot {
    pub summary: VaultSummary,
    pub entities: Vec<StoryEntityItem>,
    pub arcs: Vec<StoryArcItem>,
    pub chapters: Vec<ChapterPlanItem>,
    pub sketches: Vec<SketchItem>,
    pub manga_episodes: Vec<MangaEpisodeItem>,
    pub concepts: Vec<ConceptBlueprintItem>,
}

struct CanonConceptMeta {
    filename: &'static str,
    location_slug: &'static str,
    location_title_vi: &'static str,
    planet: &'static str,
    era: &'static str,
    is_canon_15: bool,
    spoiler_locked: bool,
    note: &'static str,
}

/// Locked Architectural Concept Manifest from `AKUNARCH_MASTER_PLAN.md` & `SELORSON_WORLD_3D_VN_ROADMAP.md` §4.3 #10.
/// Exact 15 primary `v2–v6` approved architectural hero concepts (`is_canon_15 = true`),
/// plus Eldarin companion concepts (`is_canon_extended = true`) and the Zero-Spoiler lock on `black_crystal_seal_v5`.
const CANON_CONCEPT_MANIFEST: &[CanonConceptMeta] = &[
    // 1. Eldarin Hollow (Akunalia)
    CanonConceptMeta {
        filename: "concept_eldarin_lifestream_tree.jpg",
        location_slug: "eldarin-hollow",
        location_title_vi: "Thung Lũng Thánh Địa Eldarin",
        planet: "akunalia",
        era: "Kỷ Nguyên Khởi Nguyên",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Đại thụ Lifestream tán lá phát quang màu lam ngọc & bộ rễ ôm hồ nước.",
    },
    CanonConceptMeta {
        filename: "concept_eldarin_prayer_shrine.jpg",
        location_slug: "eldarin-hollow",
        location_title_vi: "Thung Lũng Thánh Địa Eldarin",
        planet: "akunalia",
        era: "Kỷ Nguyên Khởi Nguyên",
        is_canon_15: false,
        spoiler_locked: false,
        note: "Miếu đá rêu phong mái vòm cuốn cổ kính & lồng đèn treo tại Eldarin.",
    },
    CanonConceptMeta {
        filename: "concept_eldarin_cottage_roof.jpg",
        location_slug: "eldarin-hollow",
        location_title_vi: "Thung Lũng Thánh Địa Eldarin",
        planet: "akunalia",
        era: "Kỷ Nguyên Khởi Nguyên",
        is_canon_15: false,
        spoiler_locked: false,
        note: "Mái nhà gỗ rêu phong làng cổ Eldarin.",
    },
    // 2. Ganges & Meru (~300 BCE - Dona Heracles)
    CanonConceptMeta {
        filename: "concept_wootz_crucible_furnace_v5.jpg",
        location_slug: "singularity-ganges-kalyan",
        location_title_vi: "Xưởng Rèn Sông Hằng & Đỉnh Tuyết Sơn Meru",
        planet: "earth",
        era: "292 TCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Bầu lò nung vòm đất sét trộn trấu 1400°C, nồi đất số 7 lộ phôi thép Wootz vàng kim mật ong & ống bễ da.",
    },
    CanonConceptMeta {
        filename: "concept_kalyan_tamarind_anvil_v5.jpg",
        location_slug: "singularity-ganges-kalyan",
        location_title_vi: "Xưởng Rèn Sông Hằng & Đỉnh Tuyết Sơn Meru",
        planet: "earth",
        era: "292 TCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Đe sắt trăm cân trên gốc me cổ thụ, hốc rễ giấu hộp sắt chứa mảnh thiên thạch vàng sẫm, búa tạ 8 cân & thau đất.",
    },
    CanonConceptMeta {
        filename: "concept_meru_himalayan_sanctuary_v3.jpg",
        location_slug: "singularity-ganges-kalyan",
        location_title_vi: "Xưởng Rèn Sông Hằng & Đỉnh Tuyết Sơn Meru",
        planet: "earth",
        era: "292 TCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Quần phong Tuyết Sơn Meru & Cung điện Vệ Đà với tháp vàng Shikhara trên đỉnh núi tuyết.",
    },
    // 3. Kyoto Sanctuary (1850-1868 - Miyamoto Okita)
    CanonConceptMeta {
        filename: "concept_kyoto_red_shard_katana_stand_v5.jpg",
        location_slug: "singularity-kyoto-sanctuary",
        location_title_vi: "Tịnh Am Kiếm Đạo Kyoto",
        planet: "earth",
        era: "1850 SCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Bệ thờ thần kiếm Shinto gỗ Bách 2 tầng đặt Katana đỏ-đen & Bokuto, tảng Đá Thiên Thạch Đỏ Sẫm trên khay gỗ daiza.",
    },
    CanonConceptMeta {
        filename: "concept_kyoto_irimoya_roof_v3.jpg",
        location_slug: "singularity-kyoto-sanctuary",
        location_title_vi: "Tịnh Am Kiếm Đạo Kyoto",
        planet: "earth",
        era: "1850 SCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Mái ngói cổ truyền Irimoya-zukuri đầu hồi tam giác chuẩn Kyoto và đầu đao Shibi đồng xanh.",
    },
    CanonConceptMeta {
        filename: "concept_kyoto_ancient_momiji_v2.jpg",
        location_slug: "singularity-kyoto-sanctuary",
        location_title_vi: "Tịnh Am Kiếm Đạo Kyoto",
        planet: "earth",
        era: "1850 SCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Đại thụ Phong Đỏ Momiji 500 năm rễ bám nền đá tảng rêu phong sân vườn, tách biệt khỏi mái đền.",
    },
    // 4. Samos & Olympus (~800 BCE - Olivia Fiora)
    CanonConceptMeta {
        filename: "concept_olympus_mountain_pantheon_v4.jpg",
        location_slug: "singularity-samos-olympus",
        location_title_vi: "Học Viện Đảo Samos & Đỉnh Thần Điện Olympus",
        planet: "earth",
        era: "800 TCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Đại quần thể 2 tầng: đỉnh Đại Điện Pantheon mái vòm vàng cột Corinth kép & tầng dưới Học Viện Samos Peristyle Stoa + Tholos.",
    },
    CanonConceptMeta {
        filename: "concept_olympus_eagle_altar_v4.jpg",
        location_slug: "singularity-samos-olympus",
        location_title_vi: "Học Viện Đảo Samos & Đỉnh Thần Điện Olympus",
        planet: "earth",
        era: "800 TCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Bệ cẩm thạch trắng Pentelic bát giác 4 Đại Bàng đồng & cẩm thạch đỡ chậu thánh đựng mảnh thiên thạch tím tự nhiên.",
    },
    // 5. Dun Scaith (~1000 BCE - Feliscael Tom)
    CanonConceptMeta {
        filename: "concept_dun_scaith_fortress_bridge_v4.jpg",
        location_slug: "singularity-dun-scaith",
        location_title_vi: "Pháo Đài Bóng Tối Dún Scáith",
        planet: "earth",
        era: "1000 TCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Pháo đài đá đen Celtic trên đảo đá biển khơi nối vách đá đất liền bằng cầu vòm đá hẹp & cầu kéo.",
    },
    CanonConceptMeta {
        filename: "concept_dun_scaith_indigo_weapon_rack_v6.jpg",
        location_slug: "singularity-dun-scaith",
        location_title_vi: "Pháo Đài Bóng Tối Dún Scáith",
        planet: "earth",
        era: "1000 TCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Đài đá xanh Celtic khắc Ogham & Triskele: Hồng Thương dựng thẳng trục giữa, Tù và sừng bò bọc đồng cánh trái, bệ đồng 4 chấu đỡ Đá Chàm 420nm.",
    },
    // Zero-Spoiler Guardrail Reference
    CanonConceptMeta {
        filename: "concept_dun_scaith_black_crystal_seal_v5.jpg",
        location_slug: "singularity-dun-scaith",
        location_title_vi: "Tư Liệu Tham Khảo Cốt Truyện Dún Scáith (Khóa Zero-Spoiler)",
        planet: "earth",
        era: "1000 TCN",
        is_canon_15: false,
        spoiler_locked: true,
        note: "KHÓA ZERO-SPOILER: Chỉ dùng làm tư liệu tham khảo cảnh Visual Novel / Cốt truyện về sau. Cấm đưa vào mô hình Sa bàn địa danh /world.",
    },
    // 6. Stonehenge & Avalon (~500 CE - Nguyen Arya)
    CanonConceptMeta {
        filename: "concept_stonehenge_megalith_village_v4.jpg",
        location_slug: "singularity-stonehenge-avalon",
        location_title_vi: "Vòng Cự Thạch Stonehenge & Thánh Địa Avalon",
        planet: "earth",
        era: "497 SCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Vòng Cự Thạch Stonehenge cổng đôi Trilithon trên đồi xanh kết hợp làng cổ thế kỷ V nhà tròn đá thấp mái rơm Celtic roundhouses.",
    },
    CanonConceptMeta {
        filename: "concept_avalon_mage_sanctum_reliquary_v4.jpg",
        location_slug: "singularity-stonehenge-avalon",
        location_title_vi: "Vòng Cự Thạch Stonehenge & Thánh Địa Avalon",
        planet: "earth",
        era: "497 SCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Bệ đá bát giác rễ Sồi Cổ Thụ Avalon lá lam phát sáng, trận đồ Ogham, 4 trụ rune, bệ Grimoire & rương đá chứa Đá Lam 450nm.",
    },
    // 7. Grey Ash Buffer Zone 9 (2485-2515 CE - Unikey Chirovan)
    CanonConceptMeta {
        filename: "concept_fff_sonic_core_glove_rig_v3.jpg",
        location_slug: "singularity-grey-ash-buffer",
        location_title_vi: "Phòng Thí Nghiệm Khu 9 & Trạm Lõi Âm Thanh FFF",
        planet: "earth",
        era: "2485 SCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Trạm chiếu tia laser neon xanh tích hợp Lõi Âm Thanh Cam 600nm vào găng tay tác chiến Unikey trên bàn có đúng 2 đồng hồ đo.",
    },
    CanonConceptMeta {
        filename: "concept_khu9_futuristic_laser_lab_v3.jpg",
        location_slug: "singularity-grey-ash-buffer",
        location_title_vi: "Phòng Thí Nghiệm Khu 9 & Trạm Lõi Âm Thanh FFF",
        planet: "earth",
        era: "2485 SCN",
        is_canon_15: true,
        spoiler_locked: false,
        note: "Tổ hợp Phòng thí nghiệm Khoa học Tương lai Hậu tận thế Khu 9 với mạng lưới laser neon xanh giao hội buồng cộng hưởng.",
    },
];

pub fn load_concepts_manifest(dir: &Path) -> Vec<ConceptBlueprintItem> {
    let mut by_filename: HashMap<&str, &CanonConceptMeta> = HashMap::new();
    for m in CANON_CONCEPT_MANIFEST {
        by_filename.insert(m.filename, m);
    }

    let mut out = Vec::new();
    let Ok(entries) = std::fs::read_dir(dir) else {
        return out;
    };

    let mut files: Vec<PathBuf> = entries
        .flatten()
        .map(|e| e.path())
        .filter(|p| {
            p.is_file()
                && p.extension()
                    .and_then(|e| e.to_str())
                    .is_some_and(|ext| {
                        matches!(
                            ext.to_ascii_lowercase().as_str(),
                            "jpg" | "jpeg" | "png" | "webp"
                        )
                    })
        })
        .collect();
    files.sort();

    for path in files {
        let filename = path
            .file_name()
            .and_then(|n| n.to_str())
            .unwrap_or("")
            .to_string();
        let stem = path
            .file_stem()
            .and_then(|s| s.to_str())
            .unwrap_or("")
            .to_string();
        let byte_size = path.metadata().map(|m| m.len() as i64).unwrap_or(0);
        let full_path = path.to_string_lossy().to_string();

        if let Some(meta) = by_filename.get(filename.as_str()) {
            out.push(ConceptBlueprintItem {
                filename,
                stem,
                full_path,
                byte_size,
                location_slug: meta.location_slug.to_string(),
                location_title_vi: meta.location_title_vi.to_string(),
                planet: meta.planet.to_string(),
                era: meta.era.to_string(),
                is_canon_15: meta.is_canon_15,
                is_canon_extended: !meta.spoiler_locked,
                spoiler_locked: meta.spoiler_locked,
                spoiler_note: if meta.spoiler_locked {
                    meta.note.to_string()
                } else {
                    String::new()
                },
                architectural_note: meta.note.to_string(),
            });
        } else {
            let spoiler_locked = stem.contains("black_crystal_seal");
            let (planet, loc_slug, loc_title) = infer_concept_origin(&stem);
            out.push(ConceptBlueprintItem {
                filename,
                stem,
                full_path,
                byte_size,
                location_slug: loc_slug,
                location_title_vi: loc_title,
                planet,
                era: String::new(),
                is_canon_15: false,
                is_canon_extended: false,
                spoiler_locked,
                spoiler_note: if spoiler_locked {
                    "KHÓA ZERO-SPOILER: Không đưa chi tiết phong ấn nhân vật vào mô hình địa danh /world."
                        .to_string()
                } else {
                    String::new()
                },
                architectural_note: "Bản vẽ Concept lưu trữ trong kho Tools-3D\\concepts.".to_string(),
            });
        }
    }

    // Sort Canon 15 first, then Extended Canon, then alphabetical
    out.sort_by(|a, b| {
        b.is_canon_15
            .cmp(&a.is_canon_15)
            .then_with(|| b.is_canon_extended.cmp(&a.is_canon_extended))
            .then_with(|| a.filename.cmp(&b.filename))
    });
    out
}

fn infer_concept_origin(stem: &str) -> (String, String, String) {
    if stem.contains("nambo") {
        (
            "earth".into(),
            "singularity-nam-bo-forest".into(),
            "Dị Điểm Rừng Dầu Rái Nam Bộ".into(),
        )
    } else if stem.contains("eryndor") {
        (
            "earth".into(),
            "singularity-eryndor-saqqara".into(),
            "Tĩnh Thất Đá Đen Eryndor & Saqqara".into(),
        )
    } else if stem.contains("wootz") || stem.contains("kalyan") || stem.contains("meru") {
        (
            "earth".into(),
            "singularity-ganges-kalyan".into(),
            "Xưởng Rèn Sông Hằng & Đỉnh Meru".into(),
        )
    } else if stem.contains("kyoto") {
        (
            "earth".into(),
            "singularity-kyoto-sanctuary".into(),
            "Tịnh Am Kiếm Đạo Kyoto".into(),
        )
    } else if stem.contains("olympus") || stem.contains("samos") {
        (
            "earth".into(),
            "singularity-samos-olympus".into(),
            "Học Viện Đảo Samos & Olympus".into(),
        )
    } else if stem.contains("dun_scaith") {
        (
            "earth".into(),
            "singularity-dun-scaith".into(),
            "Pháo Đài Bóng Tối Dún Scáith".into(),
        )
    } else if stem.contains("stonehenge") || stem.contains("avalon") {
        (
            "earth".into(),
            "singularity-stonehenge-avalon".into(),
            "Stonehenge & Thánh Địa Avalon".into(),
        )
    } else if stem.contains("khu9") || stem.contains("fff") || stem.contains("ash_buffer") {
        (
            "earth".into(),
            "singularity-grey-ash-buffer".into(),
            "Phòng Thí Nghiệm Khu 9 & Tầng Đệm Tro Xám".into(),
        )
    } else if stem.contains("crescent") || stem.contains("abyssal") {
        (
            "akunalia".into(),
            "crescent-ward-altar".into(),
            "Đài Phong Ấn Hồ Bán Nguyệt".into(),
        )
    } else if stem.contains("ferryman") || stem.contains("mist_pavilion") || stem.contains("river_stone") {
        (
            "akunalia".into(),
            "behadona-nilanda".into(),
            "Bến Đò Sương Mù Đại Giang Behadona".into(),
        )
    } else if stem.contains("eldarin") {
        (
            "akunalia".into(),
            "eldarin-hollow".into(),
            "Thung Lũng Thánh Địa Eldarin".into(),
        )
    } else if stem.contains("sky_") {
        (
            "akunalia".into(),
            "sky-sanctum-spire".into(),
            "Đảo Bay Tinh Thể & Tháp Phong Lôi".into(),
        )
    } else {
        (
            "akunalia".into(),
            "temple-of-zyberon".into(),
            "Đại Đền Ngũ Giác Zyberon".into(),
        )
    }
}

pub fn load_vault_snapshot() -> Result<VaultSnapshot, String> {
    let cw_dir = cowriter_data_dir();
    let db_path = cw_dir.join("co_writer.db");
    let conn = open_cowriter_readonly_at(&db_path)?;

    let sketches_dir = cw_dir.join("sketches");
    let manga_dir = cw_dir.join("manga");

    // 1. Sketches first so we can map entity_id -> primary sketch
    let mut sketches = Vec::new();
    let mut entity_sketch_map: HashMap<i64, String> = HashMap::new();
    {
        let mut stmt = conn
            .prepare(
                "SELECT id, entity_id, COALESCE(subject,''), COALESCE(kind,''), COALESCE(prompt,''),
                        COALESCE(path,''), COALESCE(width,0), COALESCE(height,0), COALESCE(bytes,0),
                        COALESCE(note,''), COALESCE(created_at,'')
                 FROM sketches
                 ORDER BY id ASC",
            )
            .map_err(|e| format!("Lỗi đọc bảng sketches: {e}"))?;
        let rows = stmt
            .query_map([], |r| {
                let rel_path: String = r.get(5)?;
                let resolved = resolve_media_path(&sketches_dir, &rel_path);
                let exists = Path::new(&resolved).is_file();
                Ok(SketchItem {
                    id: r.get(0)?,
                    entity_id: r.get(1)?,
                    subject: r.get(2)?,
                    kind: r.get(3)?,
                    prompt: r.get(4)?,
                    rel_path,
                    full_path: resolved,
                    exists_on_disk: exists,
                    width: r.get(6)?,
                    height: r.get(7)?,
                    bytes: r.get(8)?,
                    note: r.get(9)?,
                    created_at: r.get(10)?,
                })
            })
            .map_err(|e| format!("Lỗi duyệt sketches: {e}"))?;
        for row in rows {
            let item = row.map_err(|e| e.to_string())?;
            if let Some(eid) = item.entity_id {
                entity_sketch_map
                    .entry(eid)
                    .or_insert_with(|| item.full_path.clone());
            }
            sketches.push(item);
        }
    }

    // 2. Story Entities (163)
    let mut entities = Vec::new();
    let mut entity_name_by_id: HashMap<i64, String> = HashMap::new();
    {
        let mut stmt = conn
            .prepare(
                "SELECT id, COALESCE(subject_key,''), COALESCE(kind,''), COALESCE(name,''),
                        COALESCE(role,''), COALESCE(summary,''), COALESCE(confirmed,0),
                        COALESCE(mention_count,0), COALESCE(voice_profile,''), COALESCE(visual_anchor,'')
                 FROM story_entities
                 ORDER BY mention_count DESC, id ASC",
            )
            .map_err(|e| format!("Lỗi đọc bảng story_entities: {e}"))?;
        let rows = stmt
            .query_map([], |r| {
                let id: i64 = r.get(0)?;
                let confirmed_raw: i64 = r.get(6)?;
                Ok(StoryEntityItem {
                    id,
                    subject_key: r.get(1)?,
                    kind: r.get(2)?,
                    name: r.get(3)?,
                    role: r.get(4)?,
                    summary: r.get(5)?,
                    confirmed: confirmed_raw != 0,
                    mention_count: r.get(7)?,
                    voice_profile: r.get(8)?,
                    visual_anchor: r.get(9)?,
                    primary_sketch_path: entity_sketch_map.get(&id).cloned(),
                })
            })
            .map_err(|e| format!("Lỗi duyệt story_entities: {e}"))?;
        for row in rows {
            let item = row.map_err(|e| e.to_string())?;
            entity_name_by_id.insert(item.id, item.name.clone());
            entities.push(item);
        }
    }

    // 3. Story Arcs (7)
    let mut arcs = Vec::new();
    {
        let mut stmt = conn
            .prepare(
                "SELECT id, COALESCE(arc_key,''), COALESCE(title,''), COALESCE(ordinal,0),
                        COALESCE(summary,''), COALESCE(goal,''), COALESCE(stakes,''), COALESCE(turn,''),
                        chapter_start, chapter_end, COALESCE(status,'')
                 FROM story_arcs
                 ORDER BY ordinal ASC, id ASC",
            )
            .map_err(|e| format!("Lỗi đọc bảng story_arcs: {e}"))?;
        let rows = stmt
            .query_map([], |r| {
                Ok(StoryArcItem {
                    id: r.get(0)?,
                    arc_key: r.get(1)?,
                    title: r.get(2)?,
                    ordinal: r.get(3)?,
                    summary: r.get(4)?,
                    goal: r.get(5)?,
                    stakes: r.get(6)?,
                    turn: r.get(7)?,
                    chapter_start: r.get(8)?,
                    chapter_end: r.get(9)?,
                    status: r.get(10)?,
                })
            })
            .map_err(|e| format!("Lỗi duyệt story_arcs: {e}"))?;
        for row in rows {
            arcs.push(row.map_err(|e| e.to_string())?);
        }
    }

    // 4. Chapter Plans (12)
    let mut chapters = Vec::new();
    {
        let mut stmt = conn
            .prepare(
                "SELECT id, COALESCE(chapter_no,0), arc_id, COALESCE(title,''), COALESCE(intent,''),
                        COALESCE(beats_json,'[]'), pov_entity_id, COALESCE(setting,''), COALESCE(status,''),
                        COALESCE(era_label,''), COALESCE(time_span,''), COALESCE(opening_lens,''),
                        COALESCE(emotional_turn,''), COALESCE(note,'')
                 FROM chapter_plans
                 ORDER BY chapter_no ASC, id ASC",
            )
            .map_err(|e| format!("Lỗi đọc bảng chapter_plans: {e}"))?;
        let rows = stmt
            .query_map([], |r| {
                let beats_raw: String = r.get(5)?;
                let beats: Vec<Value> = serde_json::from_str(&beats_raw).unwrap_or_default();
                let pov_id: Option<i64> = r.get(6)?;
                let pov_name = pov_id.and_then(|pid| entity_name_by_id.get(&pid).cloned());
                Ok(ChapterPlanItem {
                    id: r.get(0)?,
                    chapter_no: r.get(1)?,
                    arc_id: r.get(2)?,
                    title: r.get(3)?,
                    intent: r.get(4)?,
                    beats,
                    pov_entity_id: pov_id,
                    pov_name,
                    setting: r.get(7)?,
                    status: r.get(8)?,
                    era_label: r.get(9)?,
                    time_span: r.get(10)?,
                    opening_lens: r.get(11)?,
                    emotional_turn: r.get(12)?,
                    note: r.get(13)?,
                })
            })
            .map_err(|e| format!("Lỗi duyệt chapter_plans: {e}"))?;
        for row in rows {
            chapters.push(row.map_err(|e| e.to_string())?);
        }
    }

    // 5. Manga Episodes (13) & total Manga Pages count (273)
    let manga_pages_count: i64 = conn
        .query_row("SELECT COUNT(*) FROM manga_pages", [], |r| r.get(0))
        .unwrap_or(0);

    let mut manga_episodes = Vec::new();
    {
        let mut stmt = conn
            .prepare(
                "SELECT e.id, COALESCE(e.title,''), e.chapter_no, COALESCE(e.mode,''),
                        COALESCE(e.style,''), COALESCE(e.aspect_ratio,''), COALESCE(e.status,''),
                        COALESCE(e.page_count,0), COALESCE(e.done_pages,0), COALESCE(e.note,''),
                        COALESCE(e.updated_at,''),
                        (SELECT COUNT(*) FROM manga_pages mp WHERE mp.episode_id = e.id) AS actual_cnt,
                        (SELECT COALESCE(mp.image_path,'') FROM manga_pages mp WHERE mp.episode_id = e.id AND mp.image_path IS NOT NULL AND mp.image_path != '' ORDER BY mp.page_no ASC LIMIT 1) AS first_img
                 FROM manga_episodes e
                 ORDER BY COALESCE(e.chapter_no, 999) ASC, e.id ASC",
            )
            .map_err(|e| format!("Lỗi đọc bảng manga_episodes: {e}"))?;
        let rows = stmt
            .query_map([], |r| {
                let first_rel: Option<String> = r.get(12)?;
                let cover_full = first_rel
                    .filter(|s| !s.trim().is_empty())
                    .map(|rel| resolve_media_path(&manga_dir, &rel));
                Ok(MangaEpisodeItem {
                    id: r.get(0)?,
                    title: r.get(1)?,
                    chapter_no: r.get(2)?,
                    mode: r.get(3)?,
                    style: r.get(4)?,
                    aspect_ratio: r.get(5)?,
                    status: r.get(6)?,
                    page_count: r.get(7)?,
                    done_pages: r.get(8)?,
                    note: r.get(9)?,
                    updated_at: r.get(10)?,
                    actual_pages_in_db: r.get(11)?,
                    cover_full_path: cover_full,
                })
            })
            .map_err(|e| format!("Lỗi duyệt manga_episodes: {e}"))?;
        for row in rows {
            manga_episodes.push(row.map_err(|e| e.to_string())?);
        }
    }

    // 6. Concepts in E:\Tools-3D\concepts\
    let concepts = load_concepts_manifest(&concepts_dir());
    let concepts_canon_15_count = concepts.iter().filter(|c| c.is_canon_15).count();
    let concepts_canon_extended_count = concepts.iter().filter(|c| c.is_canon_extended).count();
    let concepts_total_count = concepts.len();

    let summary = VaultSummary {
        db_path: db_path.to_string_lossy().to_string(),
        readonly_verified: true,
        entities_count: entities.len() as i64,
        arcs_count: arcs.len() as i64,
        chapters_count: chapters.len() as i64,
        sketches_count: sketches.len() as i64,
        manga_episodes_count: manga_episodes.len() as i64,
        manga_pages_count,
        concepts_canon_15_count,
        concepts_canon_extended_count,
        concepts_total_count,
    };

    Ok(VaultSnapshot {
        summary,
        entities,
        arcs,
        chapters,
        sketches,
        manga_episodes,
        concepts,
    })
}

pub fn load_manga_episode_pages(episode_id: i64) -> Result<Vec<MangaPageItem>, String> {
    let cw_dir = cowriter_data_dir();
    let db_path = cw_dir.join("co_writer.db");
    let conn = open_cowriter_readonly_at(&db_path)?;
    let manga_dir = cw_dir.join("manga");

    let mut stmt = conn
        .prepare(
            "SELECT id, episode_id, COALESCE(page_no,0), COALESCE(title,''), COALESCE(layout_style,''),
                    COALESCE(pacing_note,''), COALESCE(image_path,''), COALESCE(width,0),
                    COALESCE(height,0), COALESCE(byte_size,0), COALESCE(status,'')
             FROM manga_pages
             WHERE episode_id = ?1
             ORDER BY page_no ASC, id ASC",
        )
        .map_err(|e| format!("Lỗi đọc manga_pages cho tập #{episode_id}: {e}"))?;
    let rows = stmt
        .query_map(params![episode_id], |r| {
            let rel: String = r.get(6)?;
            let full = if rel.trim().is_empty() {
                String::new()
            } else {
                resolve_media_path(&manga_dir, &rel)
            };
            let exists = !full.is_empty() && Path::new(&full).is_file();
            Ok(MangaPageItem {
                id: r.get(0)?,
                episode_id: r.get(1)?,
                page_no: r.get(2)?,
                title: r.get(3)?,
                layout_style: r.get(4)?,
                pacing_note: r.get(5)?,
                rel_path: rel,
                full_path: full,
                exists_on_disk: exists,
                width: r.get(7)?,
                height: r.get(8)?,
                byte_size: r.get(9)?,
                status: r.get(10)?,
            })
        })
        .map_err(|e| format!("Lỗi duyệt manga_pages: {e}"))?;
    let mut out = Vec::new();
    for row in rows {
        out.push(row.map_err(|e| e.to_string())?);
    }
    Ok(out)
}

fn resolve_media_path(base_dir: &Path, raw: &str) -> String {
    let trimmed = raw.trim();
    if trimmed.is_empty() {
        return String::new();
    }
    let candidate = Path::new(trimmed);
    if candidate.is_absolute() {
        return candidate.to_string_lossy().to_string();
    }
    base_dir.join(trimmed).to_string_lossy().to_string()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn live_cowriter_bridge_is_strictly_readonly_and_loads_full_canon_counts() {
        let db = cowriter_db_path();
        if !db.is_file() {
            return;
        }
        let conn = open_cowriter_readonly_at(&db).expect("open readonly");

        // Any attempted write MUST fail immediately!
        let write_attempt = conn.execute(
            "CREATE TABLE IF NOT EXISTS _akunarch_forbidden_probe (id INTEGER)",
            [],
        );
        assert!(
            write_attempt.is_err(),
            "Co-Writer connection MUST reject writes (SQLITE_OPEN_READ_ONLY + query_only)!"
        );

        let snap = load_vault_snapshot().expect("load full vault snapshot");
        assert!(snap.summary.entities_count >= 163);
        assert!(snap.summary.arcs_count >= 7);
        assert!(snap.summary.chapters_count >= 12);
        assert!(snap.summary.sketches_count >= 46);
        assert!(snap.summary.manga_episodes_count >= 13);
        assert!(snap.summary.manga_pages_count >= 273);
        assert_eq!(snap.summary.concepts_canon_15_count, 15);
        assert!(snap.summary.concepts_total_count >= 15);

        // Verify Zero-Spoiler lock is enforced on dun_scaith_black_crystal_seal_v5
        let seal = snap
            .concepts
            .iter()
            .find(|c| c.filename == "concept_dun_scaith_black_crystal_seal_v5.jpg");
        assert!(seal.is_some(), "seal concept should be indexed");
        assert!(seal.unwrap().spoiler_locked, "seal concept must be spoiler_locked");
    }
}
