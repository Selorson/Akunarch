"""
Akunarch v2.1 — Live Projects & `%LOCALAPPDATA%\\Akunarch\\akunarch.db` Seeder (Law #2 & Law #7).

Populates `E:\\Akunarch\\projects\\` and `%LOCALAPPDATA%\\Akunarch\\akunarch.db` with:
  1. `temple-of-zyberon` — Real AAA PBR `.glb` (7 parts, 215k polys, Draco) + 4 Concepts + BGM `.wav` + Intro `.mp4`
  2. `singularity-stonehenge-avalon` — Real 1:1 AAA PBR `.glb` matching `concept_stonehenge_megalith_village_v4.jpg`
  3. `avalon-mage-sanctum` — Standalone 1:1 AAA PBR `.glb` matching `concept_avalon_mage_sanctum_reliquary_v4.jpg`
  4. `singularity-samos-olympus` — Real 1:1 AAA PBR `.glb` matching `concept_olympus_mountain_pantheon_v4.jpg`
  5. `eryndor-clocktower-concept` — Standalone World-First Concept-ready project (`cowriter_key: ""`, `glb_path: null`)

Strictly enforces:
  - Co-Writer DB Read-Only (`?mode=ro` + `PRAGMA query_only = ON`)
  - Rule #34 (Subtext Only — zero modern physics jargon, zero external author names, zero spoiler tokens)
  - Rule #36 (Southern Vietnamese literary fantasy register + natural English translation)
"""

from __future__ import annotations

import json
import math
import os
import shutil
import sqlite3
import struct
import wave
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS_ROOT = Path(os.environ.get("AKUNARCH_PROJECTS_DIR", r"E:\Akunarch\projects"))
DATA_DIR = Path(
    os.environ.get(
        "AKUNARCH_DATA_DIR",
        str(Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Admin\AppData\Local")) / "Akunarch"),
    )
)
CONCEPTS_SRC = Path(r"E:\Tools-3D\concepts")
COWRITER_DB = Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Admin\AppData\Local")) / "Co-Writer" / "co_writer.db"

SUBDIRS = ["concepts", "audio", "clockwork", "manga_plates", "chunks", "stage_vn", "cinema", "dist"]


def lookup_cowriter_entity(keyword: str) -> tuple[int | None, str]:
    if not COWRITER_DB.is_file():
        return None, ""
    uri = f"file:{COWRITER_DB.as_posix()}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    try:
        conn.execute("PRAGMA query_only = ON;")
        cur = conn.execute(
            "SELECT id, subject_key FROM story_entities "
            "WHERE kind IN ('place', 'location') AND (lower(subject_key) LIKE ? OR lower(name) LIKE ?) "
            "ORDER BY mention_count DESC LIMIT 1",
            (f"%{keyword.lower()}%", f"%{keyword.lower()}%"),
        )
        row = cur.fetchone()
        if row:
            return int(row[0]), str(row[1])
    except Exception:
        pass
    finally:
        conn.close()
    return None, ""


def synthesize_harmonic_bgm(
    out_wav: Path,
    fundamental_hz: float,
    ratios: list[float],
    duration_sec: float = 10.0,
    shimmer_hz: float = 0.2,
) -> None:
    """Generates a warm, seamless-looping stereo 44.1kHz 16-bit atmospheric ceremonial motif."""
    if out_wav.is_file() and out_wav.stat().st_size > 64_000:
        return
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    sr = 44100
    n_samples = int(sr * duration_sec)
    two_pi = 2.0 * math.pi

    adj_freqs = [round(fundamental_hz * r * duration_sec) / duration_sec for r in ratios]
    mod_freq = round(shimmer_hz * duration_sec) / duration_sec

    buf = bytearray(n_samples * 4)
    for i in range(n_samples):
        t = i / sr
        slow_env = 0.78 + 0.22 * math.sin(two_pi * mod_freq * t)
        bell_pulse = 0.25 * math.exp(-((t % (duration_sec / 2.0)) * 1.35))
        left = 0.0
        right = 0.0
        for idx, f in enumerate(adj_freqs):
            amp = (0.36 / (idx + 1.15)) * slow_env
            pan = 0.18 * math.sin(two_pi * mod_freq * t + idx * 1.1)
            sig = amp * math.sin(two_pi * f * t + idx * 0.45)
            if idx == len(adj_freqs) - 1:
                sig += bell_pulse * 0.14 * math.sin(two_pi * (f * 2.0) * t)
            left += sig * (1.0 - pan)
            right += sig * (1.0 + pan)

        l_i16 = max(-30000, min(30000, int(left * 22000.0)))
        r_i16 = max(-30000, min(30000, int(right * 22000.0)))
        struct.pack_into("<hh", buf, i * 4, l_i16, r_i16)

    with wave.open(str(out_wav), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(bytes(buf))


def ensure_db_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        PRAGMA journal_mode = WAL;
        PRAGMA foreign_keys = ON;
        CREATE TABLE IF NOT EXISTS projects (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            slug                TEXT NOT NULL UNIQUE,
            title               TEXT NOT NULL,
            kind                TEXT NOT NULL CHECK (kind IN ('clockwork', 'open_world', 'vn_episode', 'cinema')),
            planet              TEXT NOT NULL DEFAULT 'akunalia' CHECK (planet IN ('akunalia', 'earth')),
            region_slug         TEXT NOT NULL DEFAULT '',
            cowriter_entity_id  INTEGER,
            chapter_no          INTEGER,
            folder_path         TEXT NOT NULL,
            status              TEXT NOT NULL DEFAULT 'draft',
            last_synced_at      TEXT,
            created_at          TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS asset_library (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            slug                TEXT NOT NULL UNIQUE,
            category            TEXT NOT NULL,
            file_path           TEXT NOT NULL,
            thumb_path          TEXT NOT NULL DEFAULT '',
            poly_count          INTEGER NOT NULL DEFAULT 0,
            byte_size           INTEGER NOT NULL DEFAULT 0,
            tags_json           TEXT NOT NULL DEFAULT '[]',
            license_clean       INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE IF NOT EXISTS world_chunks (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            planet              TEXT NOT NULL DEFAULT 'akunalia' CHECK (planet IN ('akunalia', 'earth')),
            chunk_x             INTEGER NOT NULL,
            chunk_z             INTEGER NOT NULL,
            world_size          REAL NOT NULL DEFAULT 256.0,
            region_slug         TEXT NOT NULL DEFAULT '',
            biome               TEXT NOT NULL DEFAULT 'temperate',
            unlock_chapter      INTEGER NOT NULL DEFAULT 1,
            heightmap_path      TEXT NOT NULL DEFAULT '',
            pack_zip_path       TEXT NOT NULL DEFAULT '',
            pack_version        TEXT NOT NULL DEFAULT '0.1.0',
            spawn_points_json   TEXT NOT NULL DEFAULT '[]',
            vn_triggers_json    TEXT NOT NULL DEFAULT '[]',
            UNIQUE(planet, chunk_x, chunk_z)
        );
        CREATE TABLE IF NOT EXISTS gpu_jobs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER,
            worker_kind         TEXT NOT NULL,
            payload_json        TEXT NOT NULL DEFAULT '{}',
            status              TEXT NOT NULL DEFAULT 'queued',
            progress_pct        REAL NOT NULL DEFAULT 0.0,
            vram_peak_mb        INTEGER NOT NULL DEFAULT 0,
            output_path         TEXT NOT NULL DEFAULT '',
            error_log           TEXT NOT NULL DEFAULT '',
            created_at          TEXT NOT NULL DEFAULT '',
            updated_at          TEXT NOT NULL DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS sync_logs (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id          INTEGER,
            target_url          TEXT NOT NULL,
            payload_summary_json TEXT NOT NULL DEFAULT '{}',
            response_json       TEXT NOT NULL DEFAULT '{}',
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS studio_settings (
            key                 TEXT PRIMARY KEY,
            value               TEXT NOT NULL,
            updated_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )


def copy_concepts(dest_concepts_dir: Path, filenames: list[str]) -> list[str]:
    copied: list[str] = []
    for fn in filenames:
        src = CONCEPTS_SRC / fn
        if src.is_file():
            dst = dest_concepts_dir / fn
            if not dst.is_file() or dst.stat().st_size != src.stat().st_size:
                shutil.copy2(src, dst)
            copied.append(str(dst))
    return copied


def build_project_specs() -> list[dict]:
    zyberon_id, zyberon_key = lookup_cowriter_entity("zyberon")
    avalon_id, avalon_key = lookup_cowriter_entity("avalon")
    olympus_id, olympus_key = lookup_cowriter_entity("olympus")

    return [
        # 5th (oldest updated_at): Standalone World-First Concept Launchpad
        {
            "slug": "eryndor-clocktower-concept",
            "title": "Tháp Đồng Hồ Tinh Tú Eryndor (Phác Thảo Đi Trước)",
            "title_en": "Eryndor Astral Clocktower (World-First Concept)",
            "kind": "clockwork",
            "planet": "akunalia",
            "region_slug": "eryndor-high-citadel",
            "era": "Kỷ Nguyên Khởi Thủy",
            "era_year": None,
            "lat": 41.28,
            "lng": 19.64,
            "biome": "citadel-highland",
            "unlock_chapter": 1,
            "cowriter_entity_id": None,
            "cowriter_key": "",
            "description_vi": (
                "Dự án xây thế giới độc lập chưa nối khóa thực thể Co-Writer: tháp đồng hồ đá đen Eryndor "
                "dựng sừng sững giữa sương mù cao nguyên, sẵn sàng trên Bàn phóng Concept để đúc khối 3D "
                "hoặc kéo thả mô hình điêu khắc có sẵn."
            ),
            "description_en": (
                "Standalone World-First project ahead of manuscript chapters: the obsidian astral clocktower "
                "of Eryndor poised on the Concept Launchpad for GPU sculpting or direct GLB import."
            ),
            "concepts": [
                "concept_eryndor_astronomical_clocktower.jpg",
                "concept_eryndor_black_shard_pedestal.jpg",
            ],
            "bgm": ("eryndor_pendulum_chime.wav", 146.83, [1.0, 1.5, 2.0, 3.0]),
            "has_glb": False,
            "parts": [],
        },
        # 4th: Mount Olympus Pantheon & Sun-Star Plaza (1:1 v2.1)
        {
            "slug": "singularity-samos-olympus",
            "title": "Đại Điện Đỉnh Núi Olympus & Quảng Trường Sao Mặt Trời",
            "title_en": "Mount Olympus Marble Pantheon & Gilded Sun-Star Acropolis",
            "kind": "clockwork",
            "planet": "earth",
            "region_slug": "aegean-hellenic-arc",
            "era": "800 TCN",
            "era_year": -800,
            "lat": 40.0856,
            "lng": 22.3586,
            "biome": "alpine-marble",
            "unlock_chapter": 3,
            "cowriter_entity_id": olympus_id,
            "cowriter_key": olympus_key or "loc:dinh-may-olympus-samos",
            "description_vi": (
                "Khối núi cẩm thạch trắng xám vách dựng nhiều tầng có bốn dòng thác xanh đổ thẳng xuống chân vực. "
                "Từ quảng trường tròn lát ngôi sao mặt trời mười sáu cánh mạ vàng, đền tròn mái vòm trắng sườn trái "
                "và đại lộ cầu thang thắp lửa bên phải cùng dẫn lối lên đại điện mái vòm vàng chói lọi trên đỉnh núi."
            ),
            "description_en": (
                "Multi-tiered white-grey marble mountain massif pierced by four turquoise cascades, ascending from "
                "the 16-ray gilded Sun-Star plaza, arched white Tholos rotunda, and brazier-lined grand stairway "
                "to the gilded-dome peripteral Pantheon at the summit."
            ),
            "concepts": [
                "concept_olympus_mountain_pantheon_v4.jpg",
                "concept_olympus_eagle_altar_v4.jpg",
                "concept_olympus_guardian_statue.jpg",
            ],
            "bgm": ("olympus_dorian_lyre.wav", 196.0, [1.0, 1.25, 1.5, 2.0, 2.5]),
            "has_glb": True,
            "parts": None,  # Loaded directly from baked <slug>.parts.json sidecar!
        },
        # 3rd: Avalon Mage Sanctum & Azure Reliquary (1:1 standalone v2.1)
        {
            "slug": "avalon-mage-sanctum",
            "title": "Thánh Đàn Pháp Thư Avalon & Rương Thiên Thạch Lam",
            "title_en": "Avalon Arcane Reliquary Dais & Azure Meteorite Chest",
            "kind": "clockwork",
            "planet": "earth",
            "region_slug": "britannia-avalon-sanctum",
            "era": "497–510 SCN",
            "era_year": 502,
            "lat": 51.1458,
            "lng": -2.7145,
            "biome": "arcane-sanctum",
            "unlock_chapter": 4,
            "cowriter_entity_id": None,
            "cowriter_key": "loc:thanh-dan-phap-thu-avalon",
            "description_vi": (
                "Bệ đá cổ bát giác bốn bậc thềm rêu phong khắc chìm trận đồ chữ cổ Ogham sáng ánh lam dịu. "
                "Bốn trụ đá nhọn canh giữ bốn góc quanh gốc sồi già điểm lá lam phát sáng, nơi bộ rễ chằng chịt "
                "ôm chặt chiếc rương đá sáu cạnh mở nắp cùng cuốn pháp thư da thuộc và đôi bình tinh chất trước thềm."
            ),
            "description_en": (
                "Four-stepped mossy octagonal stone dais inscribed with a glowing Celtic and Ogham arcane circle, "
                "guarded by four rune obelisks around a gnarled ancient oak whose roots embrace an open hexagonal "
                "meteorite reliquary behind a parchment grimoire lectern and twin essence phials."
            ),
            "concepts": [
                "concept_avalon_mage_sanctum_reliquary_v4.jpg",
                "concept_avalon_azure_meteorite_reliquary.jpg",
            ],
            "bgm": ("avalon_reliquary_chime.wav", 174.61, [1.0, 1.25, 1.5, 2.0]),
            "has_glb": True,
            "parts": None,
        },
        # 2nd: Salisbury Stonehenge & Celtic Foothill Village (1:1 v2.1)
        {
            "slug": "singularity-stonehenge-avalon",
            "title": "Vòng Cự Thạch Đồi Cỏ Stonehenge & Xóm Làng Cổ Chân Đồi",
            "title_en": "Salisbury Megalithic Circle & Celtic Foothill Thatched Village",
            "kind": "clockwork",
            "planet": "earth",
            "region_slug": "britannia-salisbury-mist",
            "era": "497–510 SCN",
            "era_year": 500,
            "lat": 51.1789,
            "lng": -1.8262,
            "biome": "misty-moorland",
            "unlock_chapter": 4,
            "cowriter_entity_id": avalon_id,
            "cowriter_key": avalon_key or "loc:vong-cu-thach-avalon",
            "description_vi": (
                "Đồi cỏ xanh xứ Salisbury thoải dần từ xóm làng cổ có bờ rào đá xếp khô, bốn nếp nhà tròn mái rơm, "
                "hai ngôi nhà dài phủ rêu, giếng nước đá và lán củi bên đôi cội sồi già lên tới vòng cự thạch xám "
                "cùng năm cổng đá đôi sừng sững trên đỉnh đồi."
            ),
            "description_en": (
                "Natural brown-earth cutaway and grassy Salisbury hill rising smoothly from a dry-stone-walled Celtic "
                "hamlet of four conical-thatched roundhouses, two mossy-roofed longhouses, stone well, and twin ancient oaks "
                "to the outer Sarsen lintel ring and five great Trilithons."
            ),
            "concepts": [
                "concept_stonehenge_megalith_village_v4.jpg",
                "concept_avalon_ancient_oak_patriarch.jpg",
            ],
            "bgm": ("avalon_mist_harp.wav", 164.81, [1.0, 1.2, 1.5, 1.8, 2.4]),
            "has_glb": True,
            "parts": None,
        },
        # 1st (newest updated_at -> default active on launch!): Temple of Zyberon AAA .glb
        {
            "slug": "temple-of-zyberon",
            "title": "Đại Đền Ngũ Giác Zyberon & Hòn Đá Phong Ấn",
            "title_en": "Pentagonal Grand Temple of Zyberon & The Sealing Stone",
            "kind": "clockwork",
            "planet": "akunalia",
            "region_slug": "zyberon-sacred-basin",
            "era": "Kỷ Nguyên Hoàng Kim Eldarin",
            "era_year": None,
            "lat": 14.62,
            "lng": 108.45,
            "biome": "sacred-highland",
            "unlock_chapter": 1,
            "cowriter_entity_id": zyberon_id,
            "cowriter_key": zyberon_key or "loc:dai-den-zyberon",
            "description_vi": (
                "Kỳ quan trung tâm thành bang cổ: tòa đại đền năm cạnh bằng đá hoa cương xám tro và đồng thau mạ vàng "
                "ngự trên hầm rãnh đá ngầm, nơi bốn chậu lửa thiêng và hàng cột hộ pháp vây quanh Hòn Đá Phong Ấn dưới mái vòm kim ô."
            ),
            "description_en": (
                "Architectural centerpiece of the ancient realm: a monumental five-sided granite and gilded-bronze sanctuary "
                "poised above subterranean stone conduits, where guardian pillars and ritual braziers encircle the Sealing Stone beneath the Golden Dome."
            ),
            "concepts": [
                "concept_sealing_stone.jpg",
                "concept_golden_dome.jpg",
                "concept_guardian_pillar.jpg",
                "concept_ritual_brazier.jpg",
            ],
            "bgm": ("zyberon_sanctum_harmonic.wav", 130.81, [1.0, 1.5, 2.0, 2.5, 3.0]),
            "has_glb": True,
            "parts": [
                {
                    "id": "geological_siphon_base",
                    "name_vi": "Đế Địa Tầng Đá Bazan & Mạch Ngầm Cổ Đại",
                    "name_en": "Basalt Geological Cutaway & Subterranean Conduit Base",
                    "summary_vi": "Khối đá nền năm cạnh vát mặt cắt địa chất phơi lộ các rãnh dẫn mạch ngầm sâu dưới móng đền.",
                    "summary_en": "Pentagonal basalt bedrock cutaway revealing carved subterranean channels beneath the foundation.",
                    "dir": [0, 0.0, 0],
                },
                {
                    "id": "subterranean_siphon_vault",
                    "name_vi": "Hầm Vòm Cơ Khí & Bánh Răng Đồng Ngầm Đáy Đền",
                    "name_en": "Subterranean Bronze Vault & Under-Sanctum Gearwork",
                    "summary_vi": "Tầng hầm vòm đá khóa chặt các vành cơ cấu đồng thau cổ kính bên dưới sàn chính điện.",
                    "summary_en": "Vaulted stone undercroft housing heavy bronze ring mechanisms beneath the main sanctuary floor.",
                    "dir": [0, 2.70, 0],
                },
                {
                    "id": "pentagonal_terrace",
                    "name_vi": "Thềm Đá Ngũ Giác Bậc Thang Đại Lễ",
                    "name_en": "Grand Pentagonal Stepped Stone Terrace",
                    "summary_vi": "Năm mặt bậc thang đá hoa cương dẫn lối hành hương hội tụ về tâm điểm tòa đại đền.",
                    "summary_en": "Five-sided monumental granite ceremonial stairway converging toward the inner sanctum.",
                    "dir": [0, 3.80, 0],
                },
                {
                    "id": "ritual_braziers",
                    "name_vi": "Cụm Chậu Lửa Nghi Lễ Đúc Đồng Chạm Nổi",
                    "name_en": "Sculpted Bronze Ritual Braziers",
                    "summary_vi": "Những đài lửa đồng điêu khắc tinh xảo canh giữ các góc thềm ngũ giác suốt ngày đêm.",
                    "summary_en": "Ornate sculpted bronze ritual braziers standing sentinel at the corners of the terrace.",
                    "dir": [0, 5.30, 0],
                },
                {
                    "id": "sealing_stone_core",
                    "name_vi": "Hòn Đá Phong Ấn Khắc Cổ Tự Giữa Tâm Điện",
                    "name_en": "Rune-Bound Sealing Stone Core",
                    "summary_vi": "Khối thạch trụ thiêng chạm khắc văn tự cổ nằm ngay trục thẳng đứng giữa lòng đại đền.",
                    "summary_en": "Sacred monolithic Sealing Stone etched with archaic glyphs along the central axis.",
                    "dir": [0, 7.80, 0],
                },
                {
                    "id": "sanctum_colonnade",
                    "name_vi": "Vòng Cột Đá Hộ Pháp Đỡ Vòm Thượng Điện",
                    "name_en": "Guardian Pillar Sanctum Colonnade",
                    "summary_vi": "Hàng cột đá điêu khắc tượng hộ pháp trầm mặc nâng đỡ toàn bộ kết cấu mái vòm phía trên.",
                    "summary_en": "Ring of carved guardian stone pillars supporting the upper drum of the temple.",
                    "dir": [0, 11.90, 0],
                },
                {
                    "id": "imperial_golden_dome",
                    "name_vi": "Mái Vòm Kim Ô Mạ Vàng Đỉnh Đại Đền Zyberon",
                    "name_en": "Imperial Gilded-Bronze Dome Crown",
                    "summary_vi": "Mái vòm đồng mạ vàng rực rỡ khép lại trục thẳng đứng uy nghiêm của Đại Đền Ngũ Giác.",
                    "summary_en": "Radiant gilded-bronze ribbed dome crowning the vertical axis of the Grand Temple.",
                    "dir": [0, 13.00, 0],
                },
            ],
        },
    ]


def main() -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    db_path = DATA_DIR / "akunarch.db"

    specs = build_project_specs()
    base_time = datetime.now(timezone.utc) - timedelta(minutes=len(specs))

    conn = sqlite3.connect(str(db_path))
    try:
        ensure_db_schema(conn)
        for idx, spec in enumerate(specs):
            slug = spec["slug"]
            proj_dir = PROJECTS_ROOT / slug
            for sub in SUBDIRS:
                (proj_dir / sub).mkdir(parents=True, exist_ok=True)

            concept_paths = copy_concepts(proj_dir / "concepts", spec["concepts"])
            primary_img = concept_paths[0] if concept_paths else None

            bgm_name, fund_hz, ratios = spec["bgm"]
            bgm_file = proj_dir / "audio" / bgm_name
            synthesize_harmonic_bgm(bgm_file, fund_hz, ratios)

            glb_path: str | None = None
            parts_list: list[dict] = []
            if spec["has_glb"]:
                cand_glb = proj_dir / "clockwork" / f"{slug}.glb"
                if not cand_glb.is_file():
                    raise FileNotFoundError(f"Expected baked AAA .glb missing on disk: {cand_glb}")
                glb_path = str(cand_glb)
                sidecar_parts = proj_dir / "clockwork" / f"{slug}.parts.json"
                if spec["parts"] is None:
                    if not sidecar_parts.is_file():
                        raise FileNotFoundError(f"Expected .parts.json sidecar missing: {sidecar_parts}")
                    parts_list = json.loads(sidecar_parts.read_text(encoding="utf-8"))
                else:
                    parts_list = spec["parts"]
                    sidecar_parts.write_text(
                        json.dumps(parts_list, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )

            intro_mp4_cand = proj_dir / "cinema" / f"{slug}_intro.mp4"
            intro_video_path = str(intro_mp4_cand) if intro_mp4_cand.is_file() else None

            # Preserve any existing manga_plates, stage_vn, chunks, or cinema fields if re-running seeder
            existing_plates = []
            existing_chunks = {
                "pack_zip_path": None,
                "heightmap_path": None,
                "pack_version": "0.1.0",
                "spawn_points": [],
                "vn_triggers": [],
            }
            existing_vn = {
                "episode_zip_path": None,
                "episode_title": None,
            }
            existing_cinema = {
                "video_path": None,
                "thumbnail_path": None,
                "video_type": "intro",
                "episode_number": None,
            }
            manifest_file = proj_dir / "project.akun.json"
            if manifest_file.is_file():
                try:
                    prev = json.loads(manifest_file.read_text(encoding="utf-8"))
                    existing_plates = prev.get("manga_plates", existing_plates)
                    existing_chunks = prev.get("chunks", existing_chunks)
                    existing_vn = prev.get("stage_vn", existing_vn)
                    existing_cinema = prev.get("cinema", existing_cinema)
                except Exception:
                    pass

            manifest = {
                "schema_version": "2.0",
                "slug": slug,
                "title": spec["title"],
                "title_en": spec["title_en"],
                "kind": spec["kind"],
                "planet": spec["planet"],
                "region_slug": spec["region_slug"],
                "era": spec["era"],
                "era_year": spec["era_year"],
                "lat": spec["lat"],
                "lng": spec["lng"],
                "biome": spec["biome"],
                "chunk_x": 0,
                "chunk_z": 0,
                "world_size": 256.0,
                "cowriter_entity_id": spec["cowriter_entity_id"],
                "cowriter_key": spec["cowriter_key"],
                "unlock_chapter": spec["unlock_chapter"],
                "description_vi": spec["description_vi"],
                "description_en": spec["description_en"],
                "local_image_path": primary_img,
                "concept_paths": concept_paths,
                "bgm_audio_path": str(bgm_file),
                "audio_paths": [str(bgm_file)],
                "manga_plates": existing_plates,
                "clockwork": {
                    "parts": parts_list,
                    "glb_path": glb_path,
                    "intro_video_path": intro_video_path,
                    "pack_version": "2.1.0",
                },
                "chunks": existing_chunks,
                "stage_vn": existing_vn,
                "cinema": existing_cinema,
                "sync_policy": {
                    "source_app": "Akunarch",
                    "force_draft": True,
                },
            }

            manifest_file.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            ts = (base_time + timedelta(seconds=idx * 30)).isoformat()
            conn.execute(
                """
                INSERT INTO projects (
                    slug, title, kind, planet, region_slug, cowriter_entity_id,
                    chapter_no, folder_path, status, created_at, updated_at
                )
                VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, 'ready_3d', ?9, ?9)
                ON CONFLICT(slug) DO UPDATE SET
                    title = excluded.title,
                    kind = excluded.kind,
                    planet = excluded.planet,
                    region_slug = excluded.region_slug,
                    cowriter_entity_id = excluded.cowriter_entity_id,
                    chapter_no = excluded.chapter_no,
                    folder_path = excluded.folder_path,
                    status = CASE WHEN ?10 = 1 THEN 'ready_3d' ELSE 'concept_ready' END,
                    updated_at = excluded.updated_at
                """,
                (
                    slug,
                    spec["title"],
                    spec["kind"],
                    spec["planet"],
                    spec["region_slug"],
                    spec["cowriter_entity_id"],
                    spec["unlock_chapter"],
                    str(proj_dir),
                    ts,
                    1 if spec["has_glb"] else 0,
                ),
            )
            conn.execute(
                "UPDATE projects SET status = ?2 WHERE slug = ?1",
                (slug, "ready_3d" if spec["has_glb"] else "concept_ready"),
            )
            print(
                f"[SEEDED] {slug} -> glb={'YES' if glb_path else 'CONCEPT_ONLY'} "
                f"| parts={len(parts_list)} | concepts={len(concept_paths)} | bgm={bgm_file.name}"
            )

        conn.commit()
    finally:
        conn.close()

    print(f"[AKUNARCH_SEED_OK] Live DB={db_path} | ProjectsRoot={PROJECTS_ROOT}")


if __name__ == "__main__":
    main()
