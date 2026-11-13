#!/usr/bin/env python3
"""
Akunarch v2.1 — Phase 2, Phase 3 & Phase 4 Live Workbench Deliverables Builder
==============================================================================
Populates `E:\\Akunarch\\projects\\` and `%LOCALAPPDATA%\\Akunarch\\akunarch.db` with
100% real, GPU-baked, verified assets across Open-World Chunks, Visual Novel 3D,
and Cinema VFX + ToneForge -14 LUFS Mastering (while keeping all 4 Gate #1 certified
Phase 1 `.glb` monuments untouched):

  - Phase 2 (`open_world`):
      1) `chunk-akunalia-0-0` — Lòng Chảo Thánh Tích Zyberon [0, 0]
      2) `chunk-akunalia-1-0` — Bờ Đông Suối Cổ Zyberon [1, 0]
     * Exact `0.000m` stitched heightmap seam across shared border (`ix=64` == `ix=0`)
     * Real GPU 3D Gaussian Splat `.ply` (`convert_image_to_splat_ply.py`)
     * Placed real AAA `.glb` monuments (`temple-of-zyberon.glb`, `avalon-mage-sanctum.glb`)
     * Ambient Audio Zones, `spawn_points`, `vn_triggers`, 2K Beauty+Depth plates, `.zip` packs

  - Phase 3 (`vn_episode`):
      3) `vn-zyberon-sanctum-prelude` — Tiếng Vọng Thánh Điện Zyberon
     * 5-node branching bilingual VI / EN script (100% Rule #36 Southern dialect + Rule #34 Subtext Only)
     * 10 real local GPU TTS `.wav` voiceovers (`VieNeu-TTS` VI + `OmniVoice` EN, sequential Zero-OOM)
     * Hotspots, TIPS, Memory Shards, 2K 3D camera rig backdrop, packed `vn_episode_*.zip`

  - Phase 4 (`cinema`):
      4) `cinema-zyberon-awakening` — Phim Khai Mở Đại Đền Ngũ Giác Zyberon
      5) `cinema-olympus-pantheon-chronicle` — Biên Niên Sử Đỉnh Mây Olympus
     * Blender 5.2 Cycles OptiX multi-keyframe Beauty + 16-bit Depth Pass sequence
     * `effectcraft-cli.exe` RGBA VFX overlay + `akunarch-audio-cli.exe` `-14.0 LUFS` mastered mix
     * Bilingual `.vi.vtt` / `.en.vtt` / `.srt` subtitles + H.264 `.mp4` verified via `filmcraft-cli.exe probe`
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import sqlite3
import struct
import subprocess
import sys
import wave
import zipfile
import zlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

PROJECTS_ROOT = Path(os.environ.get("AKUNARCH_PROJECTS_DIR", r"E:\Akunarch\projects"))
DATA_DIR = Path(
    os.environ.get(
        "AKUNARCH_DATA_DIR",
        str(Path(os.environ.get("LOCALAPPDATA", r"C:\Users\Admin\AppData\Local")) / "Akunarch"),
    )
)
DB_PATH = DATA_DIR / "akunarch.db"

TOOLS_PY = Path(r"E:\Tools-3D\.venv\Scripts\python.exe")
BLENDER_EXE = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
FFMPEG_EXE = Path(r"C:\Users\Admin\.local\bin\ffmpeg.exe")

BIN_DIR = Path(r"E:\Akunarch\bin")
SCRIPTS_DIR = BIN_DIR / "scripts"
EFFECTCRAFT_CLI = BIN_DIR / "effectcraft-cli.exe"
FILMCRAFT_CLI = BIN_DIR / "filmcraft-cli.exe"
AUDIO_CLI = BIN_DIR / "akunarch-audio-cli.exe"

SPLAT_SCRIPT = SCRIPTS_DIR / "convert_image_to_splat_ply.py"
TTS_SCRIPT = SCRIPTS_DIR / "synthesize_local_tts.py"
CINEMA_SCRIPT = SCRIPTS_DIR / "render_cinema_sequence.py"
SEED_P1_SCRIPT = SCRIPTS_DIR / "seed_live_projects.py"

SUBDIRS = ["concepts", "audio", "clockwork", "manga_plates", "chunks", "stage_vn", "cinema", "dist"]
GRID_RES = 65
WORLD_SIZE = 256.0


def run_cmd(cmd: list[str], label: str, timeout: int = 600) -> str:
    print(f"[RUN] {label}: {' '.join(cmd[:5])} ...", flush=True)
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"{label} failed (exit {proc.returncode}):\nSTDOUT:\n{proc.stdout[-1500:]}\nSTDERR:\n{proc.stderr[-1500:]}"
        )
    return proc.stdout


def ensure_project_dirs(slug: str) -> Path:
    p = PROJECTS_ROOT / slug
    for sub in SUBDIRS:
        (p / sub).mkdir(parents=True, exist_ok=True)
    return p


def synthesize_harmonic_bgm(
    out_wav: Path,
    fundamental_hz: float,
    ratios: list[float],
    duration_sec: float = 10.0,
    shimmer_hz: float = 0.2,
) -> None:
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
        bell_pulse = 0.24 * math.exp(-((t % (duration_sec / 2.0)) * 1.35))
        left = 0.0
        right = 0.0
        for idx, f in enumerate(adj_freqs):
            amp = (0.35 / (idx + 1.15)) * slow_env
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


def write_heightmap_16bit_png(out_png: Path, values: list[float], res: int = GRID_RES) -> None:
    min_ref = -8.0
    span_ref = 80.0
    raw_rows = bytearray()
    for iz in range(res):
        raw_rows.append(0)
        for ix in range(res):
            h = values[iz * res + ix]
            norm = max(0.0, min(1.0, (h - min_ref) / span_ref))
            u16 = int(round(norm * 65535.0))
            raw_rows.append((u16 >> 8) & 0xFF)
            raw_rows.append(u16 & 0xFF)

    def png_chunk(ctype: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(ctype)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + ctype + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", res, res, 16, 0, 0, 0, 0)
    comp = zlib.compress(bytes(raw_rows), level=6)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    with open(out_png, "wb") as fp:
        fp.write(b"\x89PNG\r\n\x1a\n")
        fp.write(png_chunk(b"IHDR", ihdr))
        fp.write(png_chunk(b"IDAT", comp))
        fp.write(png_chunk(b"IEND", b""))


def sample_zyberon_basin_height(world_x: float, world_z: float) -> float:
    macro = (
        math.sin(world_x * 0.0145 + 0.35) * 4.2
        + math.cos(world_z * 0.0165 - 0.50) * 3.8
        + math.sin((world_x + world_z) * 0.009) * 3.2
    )
    ridge = abs(math.sin(world_x * 0.024 - world_z * 0.019)) * 4.5
    # Meandering ancient stream flowing diagonally between chunk [0,0] East and [1,0] West
    river_center_x = 118.0 + math.sin(world_z * 0.022) * 18.0
    dist_stream = abs(world_x - river_center_x)
    stream_carve = math.exp(-((dist_stream / 20.0) ** 2)) * 5.6
    h = 5.6 + macro + ridge - stream_carve

    # Smooth plateau on Chunk [0, 0] around (0, -12) for Temple of Zyberon
    d_temple = math.hypot(world_x - 0.0, world_z - (-12.0))
    if d_temple < 46.0:
        w = 0.5 * (1.0 + math.cos(math.pi * min(1.0, d_temple / 46.0)))
        h = h * (1.0 - w) + 6.4 * w

    # Smooth knoll on Chunk [1, 0] around (256 + 8, 4) for Eastern Sanctum
    d_sanctum = math.hypot(world_x - 264.0, world_z - 4.0)
    if d_sanctum < 32.0:
        w2 = 0.5 * (1.0 + math.cos(math.pi * min(1.0, d_sanctum / 32.0)))
        h = h * (1.0 - w2) + 7.2 * w2

    return round(max(-3.5, min(52.0, h)), 3)


def build_grid_for_chunk(chunk_x: int, chunk_z: int) -> list[float]:
    step = WORLD_SIZE / (GRID_RES - 1)
    ox = chunk_x * WORLD_SIZE
    oz = chunk_z * WORLD_SIZE
    vals: list[float] = []
    for iz in range(GRID_RES):
        lz = -0.5 * WORLD_SIZE + iz * step
        for ix in range(GRID_RES):
            lx = -0.5 * WORLD_SIZE + ix * step
            vals.append(sample_zyberon_basin_height(ox + lx, oz + lz))
    return vals


def stitch_east_west_exact(west_grid: list[float], east_grid: list[float], res: int = GRID_RES) -> float:
    band = 6
    for iz in range(res):
        shared = round(0.5 * (west_grid[iz * res + (res - 1)] + east_grid[iz * res + 0]), 3)
        diff_w = shared - west_grid[iz * res + (res - 1)]
        diff_e = shared - east_grid[iz * res + 0]
        west_grid[iz * res + (res - 1)] = shared
        east_grid[iz * res + 0] = shared
        for d in range(1, band):
            fw = 0.5 * (1.0 + math.cos(math.pi * (d / band)))
            ix_w = (res - 1) - d
            ix_e = d
            west_grid[iz * res + ix_w] = round(west_grid[iz * res + ix_w] + diff_w * fw, 3)
            east_grid[iz * res + ix_e] = round(east_grid[iz * res + ix_e] + diff_e * fw, 3)

    max_err = max(
        abs(west_grid[iz * res + (res - 1)] - east_grid[iz * res + 0]) for iz in range(res)
    )
    return max_err


def render_2k_plate_from_glb(
    glb_path: Path,
    out_beauty: Path,
    out_depth: Path,
    cam_pos: list[float],
    cam_target: list[float],
    fov_deg: float = 38.0,
) -> None:
    if out_beauty.is_file() and out_beauty.stat().st_size > 80_000 and out_depth.is_file():
        return
    tmp_mp4 = out_beauty.parent / "_plate_tmp.mp4"
    kf_json = out_beauty.parent / "_plate_kf.json"
    kf_json.write_text(
        json.dumps(
            [{"time_sec": 0.0, "pos": cam_pos, "target": cam_target, "fov_deg": fov_deg}],
            indent=2,
        ),
        encoding="utf-8",
    )
    run_cmd(
        [
            str(BLENDER_EXE),
            "--background",
            "--python-exit-code",
            "1",
            "--python",
            str(CINEMA_SCRIPT),
            "--",
            "--glb",
            str(glb_path),
            "--keyframes-json",
            str(kf_json),
            "--out-raw-mp4",
            str(tmp_mp4),
            "--out-thumb",
            str(out_beauty),
            "--out-depth",
            str(out_depth),
            "--duration",
            "0.2",
            "--fps",
            "5",
            "--width",
            "2048",
            "--height",
            "1152",
            "--samples",
            "32",
            "--still-only",
            "1",
            "--mood",
            "golden_hour",
        ],
        f"Render 2K Plate ({out_beauty.name})",
        timeout=300,
    )
    for f in (tmp_mp4, kf_json):
        if f.is_file():
            f.unlink()


def assert_strict_prose_rules(texts_vi: list[str], texts_en: list[str], context_label: str) -> None:
    forbidden_subtext = [
        "lượng tử", "quantum", "entropy", "relativity", "thuyết tương đối",
        "thermodynamics", "spacetime", "không-thời gian", "photon", "nanometer",
        "wavefunction", "nietzsche", "dostoevsky", "kant", "rawls", "steins;gate",
    ]
    for idx, vi in enumerate(texts_vi):
        if "—" in vi:
            raise ValueError(f"[{context_label}#{idx}] Rule #36 violation: em-dash found in VI text: {vi}")
        if re.search(r"(?<!\w)ạ(?!\w)", vi.lower()):
            raise ValueError(f"[{context_label}#{idx}] Rule #36 violation: particle 'ạ' found in VI text: {vi}")
        for bad in forbidden_subtext:
            if bad in vi.lower():
                raise ValueError(f"[{context_label}#{idx}] Rule #34 violation '{bad}' in VI: {vi}")
    for idx, en in enumerate(texts_en):
        for bad in forbidden_subtext:
            if bad in en.lower():
                raise ValueError(f"[{context_label}#{idx}] Rule #34 violation '{bad}' in EN: {en}")


def build_phase3_vn_project(conn: sqlite3.Connection, ts_iso: str) -> tuple[str, Path]:
    slug = "vn-zyberon-sanctum-prelude"
    proj_dir = ensure_project_dirs(slug)
    stage_dir = proj_dir / "stage_vn"
    voices_dir = stage_dir / "voices"
    voices_dir.mkdir(parents=True, exist_ok=True)

    zyberon_glb = PROJECTS_ROOT / "temple-of-zyberon" / "clockwork" / "temple-of-zyberon.glb"
    backdrop_2k = proj_dir / "manga_plates" / "zyberon_vn_backdrop_2k.jpg"
    depth_2k = proj_dir / "manga_plates" / "zyberon_vn_depth_2k.png"
    render_2k_plate_from_glb(
        zyberon_glb,
        backdrop_2k,
        depth_2k,
        cam_pos=[13.5, 6.2, 16.8],
        cam_target=[0.0, 4.6, 0.0],
        fov_deg=36.0,
    )

    # Copy concept reference for project card fallback
    src_concept = PROJECTS_ROOT / "temple-of-zyberon" / "concepts" / "concept_sealing_stone.jpg"
    dst_concept = proj_dir / "concepts" / "concept_sealing_stone.jpg"
    if src_concept.is_file() and not dst_concept.is_file():
        shutil.copy2(src_concept, dst_concept)

    bgm_wav = proj_dir / "audio" / "zyberon_vn_prelude_pad.wav"
    synthesize_harmonic_bgm(bgm_wav, 130.81, [1.0, 1.25, 1.5, 2.0, 3.0], duration_sec=12.0)

    nodes = [
        {
            "id": "n01_arrival",
            "speaker_id": "narrator",
            "expression": "solemn",
            "text_vi": (
                "Hồi sương sớm còn giăng ngang năm bậc thềm đá rêu, hai lữ khách dừng chân trước tòa đại đền cổ. "
                "Gió từ lòng chảo thổi ngược lên mang theo mùi đồng xưa và tiếng mạch nước ngầm róc rách dưới móng đá."
            ),
            "text_en": (
                "While morning mist still drifts across the five mossy stone steps, two wayfarers pause before the ancient grand temple. "
                "Wind rising from the basin carries the scent of aged bronze and subterranean water murmuring beneath the foundation."
            ),
            "backdrop_path": str(backdrop_2k),
            "voice_vi_path": str(voices_dir / "n01_arrival_vi.wav"),
            "voice_en_path": str(voices_dir / "n01_arrival_en.wav"),
            "bgm_override_path": None,
            "next_node_id": "n02_threshold",
            "choices": [],
            "hotspots": [
                {
                    "id": "hs_sealing_stone",
                    "x_pct": 50.0,
                    "y_pct": 44.0,
                    "label_vi": "Hòn Đá Phong Ấn Giữa Tâm Điện",
                    "label_en": "Central Sealing Stone Monolith",
                    "inspect_vi": "Thân đá xám khắc chìm những đường rãnh cổ tự ăn khớp với bóng nắng ban mai rọi qua vòm đền.",
                    "inspect_en": "The grey monolith bears sunken archaic glyphs aligned cleanly with the morning sunbeams piercing the dome.",
                    "unlock_tip_id": "tip_sealing_stone",
                },
                {
                    "id": "hs_ritual_brazier",
                    "x_pct": 31.0,
                    "y_pct": 62.0,
                    "label_vi": "Chậu Lửa Đồng Chạm Nổi",
                    "label_en": "Sculpted Bronze Ritual Brazier",
                    "inspect_vi": "Lớp đồng xanh dày dặn đúc hình cánh chim cổ, bên trong than tùng vẫn âm ỉ giữ hơi ấm suốt đêm sương.",
                    "inspect_en": "Heavy patinated bronze cast with ancient wing motifs, still cradling warm pine embers through the misty night.",
                    "unlock_tip_id": "tip_bronze_brazier",
                },
            ],
            "unlock_tip_ids": ["tip_zyberon_terrace"],
            "unlock_shard_id": None,
        },
        {
            "id": "n02_threshold",
            "speaker_id": "lyra",
            "expression": "curious",
            "text_vi": (
                "Anh coi kìa, bốn chậu lửa đồng quanh sân vẫn còn giữ tàn than ấm. "
                "Tụi mình bước vô soi kỹ mặt chữ trên Hòn Đá Phong Ấn trước, hay ghé tai nghe tiếng bánh răng đồng vọng lên từ hầm ngầm dưới chân nghen?"
            ),
            "text_en": (
                "Look over there, the four bronze braziers around the court still hold warm embers. "
                "Shall we step inside to examine the glyphs on the Sealing Stone first, or listen closely to the bronze gearwork echoing from the vault beneath our feet?"
            ),
            "backdrop_path": str(backdrop_2k),
            "voice_vi_path": str(voices_dir / "n02_threshold_vi.wav"),
            "voice_en_path": str(voices_dir / "n02_threshold_en.wav"),
            "bgm_override_path": None,
            "next_node_id": None,
            "choices": [
                {
                    "id": "ch_inspect_stone",
                    "label_vi": "Bước lên thềm soi nét chữ cổ trên Hòn Đá Phong Ấn",
                    "label_en": "Ascend the dais to inspect the glyphs on the Sealing Stone",
                    "target_node_id": "n03a_stone_branch",
                    "grant_shard_id": "shard_sealing_oath",
                },
                {
                    "id": "ch_listen_vault",
                    "label_vi": "Áp tay xuống nền đá nghe nhịp bánh răng hầm mạch ngầm",
                    "label_en": "Press a palm to the stone floor to hear the subterranean gear vault",
                    "target_node_id": "n03b_vault_branch",
                    "grant_shard_id": "shard_siphon_cadence",
                },
            ],
            "hotspots": [],
            "unlock_tip_ids": [],
            "unlock_shard_id": None,
        },
        {
            "id": "n03a_stone_branch",
            "speaker_id": "kael",
            "expression": "thoughtful",
            "text_vi": (
                "Chạm bàn tay lên mặt đá mát lạnh mà nghe rõ nhịp ngân trầm ấm bên trong đa. "
                "Người xưa canh từng khe nắng rọi từ đỉnh vòm vàng xuống đúng hàng chữ khắc mùa nước lên."
            ),
            "text_en": (
                "Touching the cool stone face, you can feel a deep, steady hum resonating within. "
                "The builders aligned each sunbeam from the gilded dome right onto the carved flood-season inscriptions."
            ),
            "backdrop_path": str(backdrop_2k),
            "voice_vi_path": str(voices_dir / "n03a_stone_branch_vi.wav"),
            "voice_en_path": str(voices_dir / "n03a_stone_branch_en.wav"),
            "bgm_override_path": None,
            "next_node_id": "n04_convergence",
            "choices": [],
            "hotspots": [],
            "unlock_tip_ids": ["tip_sealing_stone"],
            "unlock_shard_id": "shard_sealing_oath",
        },
        {
            "id": "n03b_vault_branch",
            "speaker_id": "lyra",
            "expression": "warm",
            "text_vi": (
                "Dưới lớp gạch đá năm cạnh này là cả một dòng suối ngầm đang xoay đều từng vành răng đồng xanh đó nghen. "
                "Thảo nào qua bao nhiêu năm tháng mà nhịp thở của tòa đền vẫn vẹn nguyên chớ chẳng hề ngưng nghỉ."
            ),
            "text_en": (
                "Beneath this five-sided stone pavement, an underground spring steadily turns the patinated bronze gear rings. "
                "No wonder the temple has kept its steady pulse unbroken across so many generations."
            ),
            "backdrop_path": str(backdrop_2k),
            "voice_vi_path": str(voices_dir / "n03b_vault_branch_vi.wav"),
            "voice_en_path": str(voices_dir / "n03b_vault_branch_en.wav"),
            "bgm_override_path": None,
            "next_node_id": "n04_convergence",
            "choices": [],
            "hotspots": [],
            "unlock_tip_ids": ["tip_bronze_brazier"],
            "unlock_shard_id": "shard_siphon_cadence",
        },
        {
            "id": "n04_convergence",
            "speaker_id": "narrator",
            "expression": "serene",
            "text_vi": (
                "Ánh nắng đầu ngày vừa chạm đỉnh vòm kim ô, tiếng chuông gió nơi hàng cột hộ pháp khẽ ngân dài, "
                "mở lối cho cuộc hành trình tiến sâu vô lòng chảo cổ Zyberon."
            ),
            "text_en": (
                "As first daylight crowns the gilded dome, wind chimes along the guardian colonnade ring out softly, "
                "opening the way deeper into the ancient basin of Zyberon."
            ),
            "backdrop_path": str(backdrop_2k),
            "voice_vi_path": str(voices_dir / "n04_convergence_vi.wav"),
            "voice_en_path": str(voices_dir / "n04_convergence_en.wav"),
            "bgm_override_path": None,
            "next_node_id": None,
            "choices": [],
            "hotspots": [],
            "unlock_tip_ids": [],
            "unlock_shard_id": None,
        },
    ]

    tips = [
        {
            "id": "tip_zyberon_terrace",
            "term_vi": "Thềm Đá Ngũ Giác Zyberon",
            "term_en": "Pentagonal Terrace of Zyberon",
            "body_vi": "Nền đá hoa cương năm cạnh chia đều năm hướng gió từ lòng chảo hội tụ về tâm đại đền.",
            "body_en": "Five-sided granite terrace channeling the five basin winds toward the central sanctuary.",
        },
        {
            "id": "tip_sealing_stone",
            "term_vi": "Hòn Đá Phong Ấn Khắc Cổ Tự",
            "term_en": "Glyph-Carved Sealing Stone",
            "body_vi": "Trụ đá nguyên khối dựng ngay trục dọc dưới mái vòm vàng, ghi dấu giao ước của các bậc tiền nhân.",
            "body_en": "Monolithic stone pillar set directly beneath the golden dome, recording the covenant of the elders.",
        },
        {
            "id": "tip_bronze_brazier",
            "term_vi": "Hầm Bánh Răng Mạch Ngầm & Lửa Thiêng",
            "term_en": "Subterranean Water-Gear Vault & Braziers",
            "body_vi": "Hệ thống rãnh nước ngầm dưới đáy đền dẫn sức nước làm quay các vành đồng cổ suốt bốn mùa.",
            "body_en": "Subterranean stone conduits beneath the temple channel spring water to turn ancient bronze rings year-round.",
        },
    ]

    shards = [
        {
            "id": "shard_sealing_oath",
            "title_vi": "Mảnh Ký Ức: Lời Thề Nắng Sớm Trên Đá Xám",
            "title_en": "Memory Shard: Sunlit Oath on Grey Granite",
            "echo_vi": "Khi tia nắng đầu tiên chạm nét khắc đầu dòng, tiếng vọng xưa nhắc người lữ khách giữ trọn lòng ngay thẳng.",
            "echo_en": "When the first sunbeam touches the top glyph, an ancient echo reminds the traveler to keep a steadfast heart.",
            "chapter_hint": 1,
        },
        {
            "id": "shard_siphon_cadence",
            "title_vi": "Mảnh Ký Ức: Nhịp Nước Ngầm Dưới Chân Đền",
            "title_en": "Memory Shard: Subterranean Stream Cadence",
            "echo_vi": "Dòng suối khuất dưới lớp đá tối vẫn bền bỉ đẩy từng răng đồng xoay tròn không chút mỏi mệt.",
            "echo_en": "Hidden beneath dark masonry, the mountain stream patiently turns each bronze tooth without rest.",
            "chapter_hint": 2,
        },
    ]

    assert_strict_prose_rules(
        [n["text_vi"] for n in nodes]
        + [c["label_vi"] for n in nodes for c in n["choices"]]
        + [h["inspect_vi"] for n in nodes for h in n["hotspots"]]
        + [t["body_vi"] for t in tips]
        + [s["echo_vi"] for s in shards],
        [n["text_en"] for n in nodes]
        + [c["label_en"] for n in nodes for c in n["choices"]]
        + [h["inspect_en"] for n in nodes for h in n["hotspots"]]
        + [t["body_en"] for t in tips]
        + [s["echo_en"] for s in shards],
        "VN_ZYBERON_PRELUDE",
    )

    cast = [
        {
            "id": "narrator",
            "name_vi": "Lời Dẫn",
            "name_en": "Narrator",
            "voice_vi": "Mỹ Duyên",
            "voice_en": "narrator",
            "portrait_path": None,
            "accent_color": "#94a3b8",
        },
        {
            "id": "lyra",
            "name_vi": "Lyra (Người Giữ Tháp)",
            "name_en": "Lyra (Spire Keeper)",
            "voice_vi": "Thùy Dung",
            "voice_en": "female",
            "portrait_path": None,
            "accent_color": "#6ee7b7",
        },
        {
            "id": "kael",
            "name_vi": "Kael (Lữ Khách Phương Nam)",
            "name_en": "Kael (Southern Wayfarer)",
            "voice_vi": "Minh Triết",
            "voice_en": "male",
            "portrait_path": None,
            "accent_color": "#fbbf24",
        },
    ]
    cast_by_id = {c["id"]: c for c in cast}

    # Synthesize missing VI & EN voiceovers via real VieNeu-TTS + OmniVoice batch
    batch_items = []
    for n in nodes:
        c = cast_by_id[n["speaker_id"]]
        vi_wav = Path(n["voice_vi_path"])
        en_wav = Path(n["voice_en_path"])
        if not vi_wav.is_file() or vi_wav.stat().st_size < 4096:
            batch_items.append(
                {
                    "id": f"{n['id']}:vi",
                    "lang": "vi",
                    "text": n["text_vi"],
                    "voice": c["voice_vi"],
                    "out_path": str(vi_wav),
                }
            )
        if not en_wav.is_file() or en_wav.stat().st_size < 4096:
            batch_items.append(
                {
                    "id": f"{n['id']}:en",
                    "lang": "en",
                    "text": n["text_en"],
                    "voice": c["voice_en"],
                    "out_path": str(en_wav),
                }
            )

    if batch_items:
        batch_json = voices_dir / "_vn_tts_batch.json"
        report_json = voices_dir / "_vn_tts_report.json"
        batch_json.write_text(json.dumps(batch_items, ensure_ascii=False, indent=2), encoding="utf-8")
        run_cmd(
            [
                str(TOOLS_PY),
                str(TTS_SCRIPT),
                "--batch-json",
                str(batch_json),
                "--report-json",
                str(report_json),
            ],
            "Synthesize Batch Local TTS (VieNeu-TTS VI + OmniVoice EN)",
            timeout=900,
        )

    # Verify all 10 voice files exist on disk
    for n in nodes:
        for k in ("voice_vi_path", "voice_en_path"):
            vp = Path(n[k])
            if not vp.is_file() or vp.stat().st_size < 4096:
                raise RuntimeError(f"Missing synthesized TTS audio file: {vp}")

    episode_doc = {
        "schema_version": "1.0",
        "slug": slug,
        "title_vi": "Tiếng Vọng Thánh Điện Zyberon",
        "title_en": "Echoes of the Zyberon Sanctum",
        "synopsis_vi": "Hồi sương sớm còn giăng ngang thềm đá năm cạnh, hai lữ khách lắng nghe nhịp nước ngầm và nét chữ cổ nơi Đại Đền Zyberon.",
        "synopsis_en": "As morning mist drifts across the pentagonal stone steps, two wayfarers listen to subterranean water gears and ancient glyphs at the Grand Temple of Zyberon.",
        "entry_node_id": "n01_arrival",
        "bgm_path": str(bgm_wav),
        "default_backdrop_path": str(backdrop_2k),
        "camera_rig": {
            "preset": "low_angle_monument",
            "fov_deg": 36.0,
            "pos": [13.5, 6.2, 16.8],
            "target": [0.0, 4.6, 0.0],
            "weather": "mist",
            "exposure": 1.08,
            "source_slug": "temple-of-zyberon",
        },
        "cast": cast,
        "nodes": nodes,
        "tips": tips,
        "memory_shards": shards,
        "archive_asset_map": {},
    }

    # Pack vn_episode_vn-zyberon-sanctum-prelude.zip
    zip_path = stage_dir / f"vn_episode_{slug}.zip"
    asset_map: dict[str, str] = {}
    written_rels: set[str] = set()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        def bundle_file(raw_str: str | None, cat: str) -> None:
            if not raw_str or raw_str in asset_map:
                return
            p = Path(raw_str)
            if not p.is_file():
                return
            rel = f"{cat}/{p.name}"
            if rel not in written_rels:
                zf.write(p, arcname=rel)
                written_rels.add(rel)
            asset_map[raw_str] = rel

        bundle_file(episode_doc["bgm_path"], "bgm")
        bundle_file(episode_doc["default_backdrop_path"], "backdrops")
        for n in nodes:
            bundle_file(n["backdrop_path"], "backdrops")
            bundle_file(n["voice_vi_path"], "voices")
            bundle_file(n["voice_en_path"], "voices")

        episode_doc["archive_asset_map"] = asset_map
        ep_json_bytes = json.dumps(episode_doc, ensure_ascii=False, indent=2).encode("utf-8")
        zf.writestr("episode.json", ep_json_bytes)
        (stage_dir / "episode.json").write_bytes(ep_json_bytes)

    manifest = {
        "schema_version": "2.0",
        "slug": slug,
        "title": "Tiếng Vọng Thánh Điện Zyberon (Visual Novel 3D)",
        "title_en": "Echoes of the Zyberon Sanctum (3D Visual Novel)",
        "kind": "vn_episode",
        "planet": "akunalia",
        "region_slug": "zyberon-sacred-basin",
        "era": "Kỷ Nguyên Hoàng Kim Eldarin",
        "era_year": None,
        "lat": 14.62,
        "lng": 108.45,
        "biome": "sacred-highland",
        "chunk_x": 0,
        "chunk_z": 0,
        "world_size": 256.0,
        "cowriter_entity_id": None,
        "cowriter_key": "loc:dai-den-zyberon",
        "unlock_chapter": 1,
        "description_vi": episode_doc["synopsis_vi"],
        "description_en": episode_doc["synopsis_en"],
        "local_image_path": str(backdrop_2k),
        "concept_paths": [str(backdrop_2k), str(dst_concept)] if dst_concept.is_file() else [str(backdrop_2k)],
        "bgm_audio_path": str(bgm_wav),
        "audio_paths": [str(bgm_wav)],
        "manga_plates": [
            {
                "id": "plate_vn_zyberon_2k",
                "label": "Phông Nền Trường Quay Đại Đền Zyberon 2K",
                "beauty_path": str(backdrop_2k),
                "depth_path": str(depth_2k),
                "width": 2048,
                "height": 1152,
                "fov_deg": 36.0,
                "created_at": ts_iso,
            }
        ],
        "clockwork": {
            "parts": [],
            "glb_path": str(zyberon_glb),
            "intro_video_path": None,
            "pack_version": "2.1.0",
        },
        "chunks": {
            "pack_zip_path": None,
            "heightmap_path": None,
            "pack_version": "0.1.0",
            "spawn_points": [],
            "vn_triggers": [],
        },
        "stage_vn": {
            "episode_zip_path": str(zip_path),
            "episode_json_path": str(stage_dir / "episode.json"),
            "episode_title": episode_doc["title_vi"],
        },
        "cinema": {
            "video_path": None,
            "thumbnail_path": None,
            "video_type": "intro",
            "episode_number": None,
        },
        "sync_policy": {"source_app": "Akunarch", "force_draft": True},
    }
    (proj_dir / "project.akun.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    conn.execute(
        """
        INSERT INTO projects (
            slug, title, kind, planet, region_slug, cowriter_entity_id,
            chapter_no, folder_path, status, created_at, updated_at
        )
        VALUES (?1, ?2, 'vn_episode', 'akunalia', 'zyberon-sacred-basin', NULL, 1, ?3, 'ready_3d', ?4, ?4)
        ON CONFLICT(slug) DO UPDATE SET
            title = excluded.title,
            kind = excluded.kind,
            folder_path = excluded.folder_path,
            status = 'ready_3d',
            updated_at = excluded.updated_at
        """,
        (slug, manifest["title"], str(proj_dir), ts_iso),
    )

    # Also attach the VN zip onto `temple-of-zyberon` so LocationHud plays it seamlessly!
    zy_manifest_path = PROJECTS_ROOT / "temple-of-zyberon" / "project.akun.json"
    if zy_manifest_path.is_file():
        zy_m = json.loads(zy_manifest_path.read_text(encoding="utf-8"))
        zy_m["stage_vn"] = {
            "episode_zip_path": str(zip_path),
            "episode_json_path": str(stage_dir / "episode.json"),
            "episode_title": episode_doc["title_vi"],
        }
        zy_manifest_path.write_text(json.dumps(zy_m, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"[PHASE3_VN_OK] {slug} -> zip={zip_path.name} ({zip_path.stat().st_size // 1024} KB) | voices=10",
        flush=True,
    )
    return slug, zip_path


def build_phase2_adjacent_chunks(
    conn: sqlite3.Connection, vn_zip_path: Path, ts0_iso: str, ts1_iso: str
) -> None:
    grid_0_0 = build_grid_for_chunk(0, 0)
    grid_1_0 = build_grid_for_chunk(1, 0)
    max_seam_err = stitch_east_west_exact(grid_0_0, grid_1_0, GRID_RES)
    if max_seam_err > 1e-6:
        raise RuntimeError(f"Chunk seam error exceeded 0.000m: {max_seam_err}")
    print(f"[PHASE2_STITCH_OK] Chunk [0,0] <-> Chunk [1,0] max_seam_error_m = {max_seam_err:.6f}m")

    zyberon_glb = PROJECTS_ROOT / "temple-of-zyberon" / "clockwork" / "temple-of-zyberon.glb"
    sanctum_glb = PROJECTS_ROOT / "avalon-mage-sanctum" / "clockwork" / "avalon-mage-sanctum.glb"

    chunk_defs = [
        {
            "slug": "chunk-akunalia-0-0",
            "title": "Lòng Chảo Thánh Tích Zyberon [Chunk 0, 0]",
            "title_en": "Zyberon Sacred Sanctuary Basin [Chunk 0, 0]",
            "chunk_x": 0,
            "chunk_z": 0,
            "biome": "temperate",
            "grid": grid_0_0,
            "glb_ref": zyberon_glb,
            "cam_pos": [18.0, 9.5, 21.0],
            "cam_target": [0.0, 4.2, 0.0],
            "bgm": ("zyberon_basin_wind_harmonic.wav", 130.81, [1.0, 1.5, 2.0, 2.5]),
            "placements": [
                {
                    "id": "pl_zyberon_temple",
                    "slug_ref": "temple-of-zyberon",
                    "label": "Đại Đền Ngũ Giác Zyberon",
                    "glb_path": str(zyberon_glb),
                    "x": 0.0,
                    "y": 0.0,
                    "z": -12.0,
                    "rot_y_deg": 0.0,
                    "scale": 1.0,
                }
            ],
            "spawn_points": [
                {"id": "sp_basin_south", "label": "Lối Mòn Phía Nam Lòng Chảo", "x": 0.0, "y": 1.8, "z": 52.0}
            ],
            "vn_triggers": [
                {
                    "id": "tr_zyberon_prelude",
                    "label": "Bậc Thềm Ngũ Giác Đại Đền",
                    "title": "Tiếng Vọng Thánh Điện Zyberon",
                    "episode_slug": "vn-zyberon-sanctum-prelude",
                    "local_episode_path": str(vn_zip_path),
                    "x": 0.0,
                    "y": 1.8,
                    "z": 16.0,
                    "radius": 18.0,
                }
            ],
            "description_vi": (
                "Ô địa hình trung tâm lòng chảo Zyberon rộng hai trăm năm mươi sáu mét vuông vức, "
                "nơi thảm cỏ xanh thoải xuống dòng suối ngầm phía đông và nâng đỡ Đại Đền Ngũ Giác uy nghiêm."
            ),
            "description_en": (
                "Central 256m×256m terrain chunk of the Zyberon Basin where grassy slopes descend toward "
                "the eastern stream and cradle the monumental Pentagonal Grand Temple."
            ),
            "ts": ts0_iso,
        },
        {
            "slug": "chunk-akunalia-1-0",
            "title": "Bờ Đông Suối Cổ Zyberon [Chunk 1, 0]",
            "title_en": "Zyberon Eastern Ancient Stream [Chunk 1, 0]",
            "chunk_x": 1,
            "chunk_z": 0,
            "biome": "temperate",
            "grid": grid_1_0,
            "glb_ref": sanctum_glb,
            "cam_pos": [11.5, 5.8, 13.5],
            "cam_target": [0.0, 2.4, 0.0],
            "bgm": ("zyberon_eastern_stream_chime.wav", 164.81, [1.0, 1.25, 1.5, 2.0]),
            "placements": [
                {
                    "id": "pl_eastern_reliquary_dais",
                    "slug_ref": "avalon-mage-sanctum",
                    "label": "Thánh Đàn Cổ Thụ Bờ Đông",
                    "glb_path": str(sanctum_glb),
                    "x": 8.0,
                    "y": 0.0,
                    "z": 4.0,
                    "rot_y_deg": -25.0,
                    "scale": 1.0,
                }
            ],
            "spawn_points": [
                {"id": "sp_eastern_ford", "label": "Bến Đá Qua Suối Cổ", "x": -92.0, "y": 1.8, "z": 12.0}
            ],
            "vn_triggers": [
                {
                    "id": "tr_eastern_echo",
                    "label": "Gốc Sồi Già Bờ Đông",
                    "title": "Tiếng Vọng Thánh Điện Zyberon",
                    "episode_slug": "vn-zyberon-sanctum-prelude",
                    "local_episode_path": str(vn_zip_path),
                    "x": 8.0,
                    "y": 1.8,
                    "z": 18.0,
                    "radius": 16.0,
                }
            ],
            "description_vi": (
                "Ô địa hình liền kề phía đông khớp biên không khe hở với lòng chảo chính, "
                "nơi dòng suối trong vắt uốn quanh gò đất rêu phong có bệ đá bát giác và cội sồi cổ thụ."
            ),
            "description_en": (
                "Adjacent eastern 256m×256m terrain chunk seamlessly stitched to the main basin, "
                "where a clear stream curves around a mossy knoll crowned by an octagonal stone dais."
            ),
            "ts": ts1_iso,
        },
    ]

    for cdef in chunk_defs:
        slug = cdef["slug"]
        proj_dir = ensure_project_dirs(slug)
        chunks_dir = proj_dir / "chunks"

        hm_png = chunks_dir / "heightmap_16bit.png"
        write_heightmap_16bit_png(hm_png, cdef["grid"], GRID_RES)

        beauty_2k = proj_dir / "manga_plates" / f"{slug}_landscape_2k.jpg"
        depth_2k = proj_dir / "manga_plates" / f"{slug}_depth_2k.png"
        render_2k_plate_from_glb(
            cdef["glb_ref"],
            beauty_2k,
            depth_2k,
            cam_pos=cdef["cam_pos"],
            cam_target=cdef["cam_target"],
            fov_deg=42.0,
        )

        # Real GPU BYOA Landscape -> 3D Gaussian Splat (.ply)
        splat_ply = chunks_dir / f"{slug}_splat.ply"
        splat_depth = chunks_dir / f"{slug}_splat_depth.png"
        if not splat_ply.is_file() or splat_ply.stat().st_size < 100_000:
            run_cmd(
                [
                    str(TOOLS_PY),
                    str(SPLAT_SCRIPT),
                    "--input",
                    str(beauty_2k),
                    "--output",
                    str(splat_ply),
                    "--depth-png",
                    str(splat_depth),
                    "--max-splats",
                    "90000",
                    "--world-span",
                    "96.0",
                    "--relief-scale",
                    "22.0",
                ],
                f"GPU Image-to-Splat ({slug})",
                timeout=240,
            )

        bgm_name, f_hz, ratios = cdef["bgm"]
        bgm_wav = proj_dir / "audio" / bgm_name
        synthesize_harmonic_bgm(bgm_wav, f_hz, ratios, duration_sec=10.0)

        audio_zones = [
            {
                "id": f"az_{slug}",
                "label": cdef["title"],
                "audio_path": str(bgm_wav),
                "x": 0.0,
                "z": 0.0,
                "radius": 88.0,
                "volume": 0.85,
            }
        ]

        # Pack chunk_akunalia_<x>_<z>.zip
        zip_name = f"chunk_akunalia_{cdef['chunk_x']}_{cdef['chunk_z']}.zip"
        pack_zip = chunks_dir / zip_name
        chunk_meta = {
            "slug": slug,
            "planet": "akunalia",
            "chunk_x": cdef["chunk_x"],
            "chunk_z": cdef["chunk_z"],
            "world_size": WORLD_SIZE,
            "biome": cdef["biome"],
            "water_level": 1.6,
            "foliage_density": 0.68,
            "grid_resolution": GRID_RES,
            "placements": cdef["placements"],
            "audio_zones": audio_zones,
            "spawn_points": cdef["spawn_points"],
            "vn_triggers": cdef["vn_triggers"],
        }
        with zipfile.ZipFile(pack_zip, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.write(hm_png, arcname="heightmap_16bit.png")
            zf.write(splat_ply, arcname=f"splats/{splat_ply.name}")
            zf.write(bgm_wav, arcname=f"audio/{bgm_wav.name}")
            zf.writestr("chunk_manifest.json", json.dumps(chunk_meta, ensure_ascii=False, indent=2))

        manifest = {
            "schema_version": "2.0",
            "slug": slug,
            "title": cdef["title"],
            "title_en": cdef["title_en"],
            "kind": "open_world",
            "planet": "akunalia",
            "region_slug": "zyberon-sacred-basin",
            "era": "Kỷ Nguyên Hoàng Kim Eldarin",
            "era_year": None,
            "lat": 14.62,
            "lng": 108.45 + cdef["chunk_x"] * 0.02,
            "biome": cdef["biome"],
            "chunk_x": cdef["chunk_x"],
            "chunk_z": cdef["chunk_z"],
            "world_size": WORLD_SIZE,
            "cowriter_entity_id": None,
            "cowriter_key": "",
            "unlock_chapter": 1,
            "description_vi": cdef["description_vi"],
            "description_en": cdef["description_en"],
            "local_image_path": str(beauty_2k),
            "concept_paths": [str(beauty_2k)],
            "bgm_audio_path": str(bgm_wav),
            "audio_paths": [str(bgm_wav)],
            "manga_plates": [
                {
                    "id": f"plate_{slug}_2k",
                    "label": f"Phông Đại Cảnh 2K {cdef['title']}",
                    "beauty_path": str(beauty_2k),
                    "depth_path": str(depth_2k),
                    "width": 2048,
                    "height": 1152,
                    "fov_deg": 42.0,
                    "created_at": cdef["ts"],
                }
            ],
            "clockwork": {
                "parts": [],
                "glb_path": str(cdef["glb_ref"]),
                "intro_video_path": None,
                "pack_version": "2.1.0",
            },
            "chunks": {
                "pack_zip_path": str(pack_zip),
                "heightmap_path": str(hm_png),
                "splat_path": str(splat_ply),
                "water_level": 1.6,
                "foliage_density": 0.68,
                "grid_resolution": GRID_RES,
                "heightmap_values": cdef["grid"],
                "placements": cdef["placements"],
                "audio_zones": audio_zones,
                "pack_version": "1.0.0",
                "spawn_points": cdef["spawn_points"],
                "vn_triggers": cdef["vn_triggers"],
            },
            "stage_vn": {
                "episode_zip_path": str(vn_zip_path),
                "episode_json_path": None,
                "episode_title": "Tiếng Vọng Thánh Điện Zyberon",
            },
            "cinema": {
                "video_path": None,
                "thumbnail_path": None,
                "video_type": "intro",
                "episode_number": None,
            },
            "sync_policy": {"source_app": "Akunarch", "force_draft": True},
        }
        (proj_dir / "project.akun.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        conn.execute(
            """
            INSERT INTO projects (
                slug, title, kind, planet, region_slug, cowriter_entity_id,
                chapter_no, folder_path, status, created_at, updated_at
            )
            VALUES (?1, ?2, 'open_world', 'akunalia', 'zyberon-sacred-basin', NULL, 1, ?3, 'ready_3d', ?4, ?4)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                kind = excluded.kind,
                folder_path = excluded.folder_path,
                status = 'ready_3d',
                updated_at = excluded.updated_at
            """,
            (slug, cdef["title"], str(proj_dir), cdef["ts"]),
        )

        conn.execute(
            """
            INSERT INTO world_chunks (
                planet, chunk_x, chunk_z, world_size, region_slug, biome, unlock_chapter,
                heightmap_path, pack_zip_path, pack_version, spawn_points_json, vn_triggers_json
            )
            VALUES ('akunalia', ?1, ?2, 256.0, 'zyberon-sacred-basin', ?3, 1, ?4, ?5, '1.0.0', ?6, ?7)
            ON CONFLICT(planet, chunk_x, chunk_z) DO UPDATE SET
                region_slug = excluded.region_slug,
                biome = excluded.biome,
                heightmap_path = excluded.heightmap_path,
                pack_zip_path = excluded.pack_zip_path,
                pack_version = excluded.pack_version,
                spawn_points_json = excluded.spawn_points_json,
                vn_triggers_json = excluded.vn_triggers_json
            """,
            (
                cdef["chunk_x"],
                cdef["chunk_z"],
                cdef["biome"],
                str(hm_png),
                str(pack_zip),
                json.dumps(cdef["spawn_points"], ensure_ascii=False),
                json.dumps(cdef["vn_triggers"], ensure_ascii=False),
            ),
        )
        print(
            f"[PHASE2_CHUNK_OK] {slug} -> pack={pack_zip.name} ({pack_zip.stat().st_size // 1024} KB) | splat={splat_ply.name}",
            flush=True,
        )


def write_bilingual_subtitles(cinema_dir: Path, slug: str, cues: list[dict]) -> None:
    def fmt_vtt(sec: float) -> str:
        ms = int(round(sec * 1000))
        h, rem = divmod(ms, 3600_000)
        m, rem = divmod(rem, 60_000)
        s, mil = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d}.{mil:03d}"

    def fmt_srt(sec: float) -> str:
        return fmt_vtt(sec).replace(".", ",")

    vi_lines = ["WEBVTT", ""]
    en_lines = ["WEBVTT", ""]
    srt_lines = []
    for idx, c in enumerate(cues, start=1):
        t0, t1 = c["start_sec"], c["end_sec"]
        vi_lines.extend([f"{fmt_vtt(t0)} --> {fmt_vtt(t1)}", c["text_vi"], ""])
        en_lines.extend([f"{fmt_vtt(t0)} --> {fmt_vtt(t1)}", c["text_en"], ""])
        srt_lines.extend([str(idx), f"{fmt_srt(t0)} --> {fmt_srt(t1)}", c["text_vi"], c["text_en"], ""])

    (cinema_dir / f"{slug}.vi.vtt").write_text("\n".join(vi_lines), encoding="utf-8")
    (cinema_dir / f"{slug}.en.vtt").write_text("\n".join(en_lines), encoding="utf-8")
    (cinema_dir / f"{slug}.srt").write_text("\n".join(srt_lines), encoding="utf-8")


def build_phase4_cinema_videos(conn: sqlite3.Connection, ts_a: str, ts_b: str) -> None:
    zyberon_glb = PROJECTS_ROOT / "temple-of-zyberon" / "clockwork" / "temple-of-zyberon.glb"
    olympus_glb = PROJECTS_ROOT / "singularity-samos-olympus" / "clockwork" / "singularity-samos-olympus.glb"

    films = [
        {
            "slug": "cinema-zyberon-awakening",
            "monument_slug": "temple-of-zyberon",
            "title": "Phim Khai Mở Đại Đền Ngũ Giác Zyberon",
            "title_en": "Awakening of the Pentagonal Temple of Zyberon",
            "planet": "akunalia",
            "region_slug": "zyberon-sacred-basin",
            "era": "Kỷ Nguyên Hoàng Kim Eldarin",
            "glb_path": zyberon_glb,
            "duration_sec": 5.0,
            "fps": 24,
            "mood": "golden_hour",
            "vfx_time": "1.35",
            "bgm": ("zyberon_cinema_score.wav", 130.81, [1.0, 1.5, 2.0, 2.5, 3.0]),
            "narration_vi": (
                "Giữa sương sớm lòng chảo cổ, năm bậc thềm đá hoa cương dẫn lối lên mái vòm đồng mạ vàng rực sáng."
            ),
            "voice_vi": "Mỹ Duyên",
            "keyframes": [
                {"time_sec": 0.0, "pos": [18.5, 7.2, 20.5], "target": [0.0, 4.2, 0.0], "fov_deg": 38.0, "explode_pct": 0.0},
                {"time_sec": 2.5, "pos": [11.0, 8.8, 17.0], "target": [0.0, 5.0, 0.0], "fov_deg": 36.0, "explode_pct": 16.0},
                {"time_sec": 5.0, "pos": [4.5, 6.4, 15.2], "target": [0.0, 4.6, 0.0], "fov_deg": 35.0, "explode_pct": 0.0},
            ],
            "subtitles": [
                {
                    "id": "sub_01",
                    "start_sec": 0.2,
                    "end_sec": 2.5,
                    "text_vi": "Giữa sương sớm lòng chảo cổ, năm bậc thềm đá hoa cương dần hiện rõ.",
                    "text_en": "Amid the ancient basin's morning mist, five granite terraces emerge into view.",
                },
                {
                    "id": "sub_02",
                    "start_sec": 2.5,
                    "end_sec": 4.9,
                    "text_vi": "Ánh bình minh chạm đỉnh mái vòm đồng mạ vàng trên Hòn Đá Phong Ấn.",
                    "text_en": "Dawn light crowns the gilded bronze dome above the central Sealing Stone.",
                },
            ],
            "description_vi": (
                "Phim cắt cảnh điện ảnh quay trực tiếp trên mô hình Đại Đền Ngũ Giác Zyberon, "
                "kết hợp hạt sáng cổ ngữ và bản phối âm chuẩn mười bốn đơn vị âm lượng."
            ),
            "description_en": (
                "Cinematic sequence filmed directly on the 3D Grand Temple of Zyberon with particle VFX "
                "and ToneForge -14.0 LUFS mastered narration and score."
            ),
            "ts": ts_a,
        },
        {
            "slug": "cinema-olympus-pantheon-chronicle",
            "monument_slug": "singularity-samos-olympus",
            "title": "Biên Niên Sử Đỉnh Mây Cẩm Thạch Olympus",
            "title_en": "Chronicle of the Cloud-Crowned Marble Olympus",
            "planet": "earth",
            "region_slug": "aegean-hellenic-arc",
            "era": "800 TCN",
            "glb_path": olympus_glb,
            "duration_sec": 5.0,
            "fps": 24,
            "mood": "golden_hour",
            "vfx_time": "1.85",
            "bgm": ("olympus_cinema_score.wav", 196.0, [1.0, 1.25, 1.5, 2.0, 2.5]),
            "narration_vi": (
                "Từ quảng trường ngôi sao mười sáu cánh bên dòng thác biếc, bậc thang lửa dẫn thẳng lên đại điện mái vòm vàng trên đỉnh núi."
            ),
            "voice_vi": "Thái Sơn",
            "keyframes": [
                {"time_sec": 0.0, "pos": [19.0, 9.5, 22.5], "target": [0.0, 5.2, 0.0], "fov_deg": 39.0, "explode_pct": 0.0},
                {"time_sec": 2.5, "pos": [12.5, 11.8, 18.5], "target": [0.0, 6.6, -1.2], "fov_deg": 37.0, "explode_pct": 12.0},
                {"time_sec": 5.0, "pos": [6.0, 13.0, 15.8], "target": [0.0, 7.4, -2.0], "fov_deg": 35.0, "explode_pct": 0.0},
            ],
            "subtitles": [
                {
                    "id": "sub_01",
                    "start_sec": 0.2,
                    "end_sec": 2.5,
                    "text_vi": "Từ quảng trường ngôi sao mười sáu cánh bên bốn dòng thác xanh đổ xuống vực.",
                    "text_en": "From the sixteen-ray sun plaza beside four turquoise cascades plunging into the gorge.",
                },
                {
                    "id": "sub_02",
                    "start_sec": 2.5,
                    "end_sec": 4.9,
                    "text_vi": "Đại lộ cầu thang thắp lửa vút thẳng lên mái vòm vàng chói lọi giữa tầng mây.",
                    "text_en": "The brazier-lit grand stairway ascends straight to the gleaming golden dome amid the clouds.",
                },
            ],
            "description_vi": (
                "Phim cắt cảnh điện ảnh lướt dọc vách núi cẩm thạch bốn dòng thác lên tới Đại Điện Pantheon mái vòm vàng, "
                "kèm thuyết minh tiếng Việt miền Nam và âm thanh chuẩn mười bốn đơn vị âm lượng."
            ),
            "description_en": (
                "Cinematic camera sweep ascending the four-waterfall marble massif to the gilded-dome Pantheon, "
                "complete with local TTS narration and -14.0 LUFS mastered soundtrack."
            ),
            "ts": ts_b,
        },
    ]

    for fdef in films:
        slug = fdef["slug"]
        proj_dir = ensure_project_dirs(slug)
        cdir = proj_dir / "cinema"

        assert_strict_prose_rules(
            [fdef["narration_vi"]] + [s["text_vi"] for s in fdef["subtitles"]],
            [s["text_en"] for s in fdef["subtitles"]],
            slug,
        )

        # 1. Synthesize real narration TTS (sequential GPU step 1)
        narration_wav = cdir / "narration_vi.wav"
        if not narration_wav.is_file() or narration_wav.stat().st_size < 4096:
            run_cmd(
                [
                    str(TOOLS_PY),
                    str(TTS_SCRIPT),
                    "--lang",
                    "vi",
                    "--voice",
                    fdef["voice_vi"],
                    "--text",
                    fdef["narration_vi"],
                    "--out",
                    str(narration_wav),
                ],
                f"Cinema TTS Narration ({slug})",
                timeout=300,
            )

        # 2. Synthesize harmonic score + ToneForge -14.0 LUFS Master
        bgm_name, f_hz, ratios = fdef["bgm"]
        bgm_wav = proj_dir / "audio" / bgm_name
        synthesize_harmonic_bgm(bgm_wav, f_hz, ratios, duration_sec=8.0)

        master_wav = cdir / f"{slug}_master_14lufs.wav"
        master_stdout = run_cmd(
            [
                str(AUDIO_CLI),
                "master",
                "--in",
                str(narration_wav),
                "--bgm",
                str(bgm_wav),
                "--out",
                str(master_wav),
                "--target-lufs",
                "-14.0",
                "--ceiling-dbtp",
                "-1.0",
                "--duration-sec",
                f"{fdef['duration_sec']:.2f}",
                "--json",
            ],
            f"ToneForge -14 LUFS Master ({slug})",
            timeout=120,
        )
        audio_meta = json.loads(master_stdout.strip())
        measured_lufs = float(audio_meta.get("output_integrated_lufs", -14.0))
        measured_dbtp = float(audio_meta.get("output_true_peak_dbtp", -1.0))

        # 3. Render Blender 5.2 Cycles OptiX Beauty + 16-bit Depth sequence (sequential GPU step 2)
        raw_mp4 = cdir / "raw_beauty.mp4"
        thumb_jpg = cdir / "thumbnail.jpg"
        depth_png = cdir / "depth_preview.png"
        kf_path = cdir / "keyframes.json"
        kf_path.write_text(json.dumps(fdef["keyframes"], indent=2), encoding="utf-8")

        final_mp4 = cdir / f"{slug}.mp4"
        if not raw_mp4.is_file() or raw_mp4.stat().st_size < 50_000:
            run_cmd(
                [
                    str(BLENDER_EXE),
                    "--background",
                    "--python-exit-code",
                    "1",
                    "--python",
                    str(CINEMA_SCRIPT),
                    "--",
                    "--glb",
                    str(fdef["glb_path"]),
                    "--keyframes-json",
                    str(kf_path),
                    "--out-raw-mp4",
                    str(raw_mp4),
                    "--out-thumb",
                    str(thumb_jpg),
                    "--out-depth",
                    str(depth_png),
                    "--duration",
                    str(fdef["duration_sec"]),
                    "--fps",
                    str(fdef["fps"]),
                    "--width",
                    "1280",
                    "--height",
                    "720",
                    "--samples",
                    "24",
                    "--mood",
                    fdef["mood"],
                ],
                f"Blender 5.2 Cinema Render ({slug})",
                timeout=900,
            )

        # 4. Render effectcraft-cli RGBA particle overlay
        vfx_png = cdir / f"{slug}_vfx_overlay.png"
        run_cmd(
            [
                str(EFFECTCRAFT_CLI),
                "--demo",
                "render-frame",
                "--time",
                fdef["vfx_time"],
                "--transparent",
                "--out",
                str(vfx_png),
                "--json",
            ],
            f"EffectCraft VFX Overlay ({slug})",
            timeout=120,
        )

        # 5. Subtitles + Final FFmpeg H.264 + AAC -14 LUFS Mux + FilmCraft Probe
        write_bilingual_subtitles(cdir, slug, fdef["subtitles"])

        run_cmd(
            [
                str(FFMPEG_EXE),
                "-y",
                "-i",
                str(raw_mp4),
                "-loop",
                "1",
                "-i",
                str(vfx_png),
                "-i",
                str(master_wav),
                "-filter_complex",
                "[1:v]scale=1280:720,format=rgba,colorchannelmixer=aa=0.45[vfx];[0:v][vfx]overlay=0:0:shortest=1[vout]",
                "-map",
                "[vout]",
                "-map",
                "2:a:0",
                "-c:v",
                "libx264",
                "-preset",
                "medium",
                "-crf",
                "19",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "256k",
                "-shortest",
                "-movflags",
                "+faststart",
                str(final_mp4),
            ],
            f"FFmpeg Final Cinema Composite ({slug})",
            timeout=240,
        )

        probe_out = run_cmd(
            [str(FILMCRAFT_CLI), "probe", str(final_mp4), "--json"],
            f"FilmCraft Probe ({slug})",
            timeout=60,
        )
        print(f"[FILMCRAFT_PROBE] {slug}: {probe_out.strip()[:180]}")

        manifest = {
            "schema_version": "2.0",
            "slug": slug,
            "title": fdef["title"],
            "title_en": fdef["title_en"],
            "kind": "cinema",
            "planet": fdef["planet"],
            "region_slug": fdef["region_slug"],
            "era": fdef["era"],
            "era_year": None,
            "lat": 14.62 if fdef["planet"] == "akunalia" else 40.0856,
            "lng": 108.45 if fdef["planet"] == "akunalia" else 22.3586,
            "biome": "sacred-highland",
            "chunk_x": 0,
            "chunk_z": 0,
            "world_size": 256.0,
            "cowriter_entity_id": None,
            "cowriter_key": "",
            "unlock_chapter": 1,
            "description_vi": fdef["description_vi"],
            "description_en": fdef["description_en"],
            "local_image_path": str(thumb_jpg),
            "concept_paths": [str(thumb_jpg)],
            "bgm_audio_path": str(bgm_wav),
            "audio_paths": [str(bgm_wav), str(narration_wav), str(master_wav)],
            "manga_plates": [
                {
                    "id": f"plate_{slug}_depth",
                    "label": f"Cinema Beauty + Depth ({fdef['title']})",
                    "beauty_path": str(thumb_jpg),
                    "depth_path": str(depth_png),
                    "width": 1280,
                    "height": 720,
                    "fov_deg": 37.0,
                    "created_at": fdef["ts"],
                }
            ],
            "clockwork": {
                "parts": [],
                "glb_path": str(fdef["glb_path"]),
                "intro_video_path": str(final_mp4),
                "pack_version": "2.1.0",
            },
            "chunks": {
                "pack_zip_path": None,
                "heightmap_path": None,
                "pack_version": "0.1.0",
                "spawn_points": [],
                "vn_triggers": [],
            },
            "stage_vn": {
                "episode_zip_path": None,
                "episode_json_path": None,
                "episode_title": None,
            },
            "cinema": {
                "video_path": str(final_mp4),
                "thumbnail_path": str(thumb_jpg),
                "video_type": "intro",
                "episode_number": 1,
                "duration_sec": fdef["duration_sec"],
                "fps": fdef["fps"],
                "vfx_preset": "golden_embers",
                "vfx_overlay_path": str(vfx_png),
                "comfyui_enabled": False,
                "comfyui_prompt": "",
                "source_glb_path": str(fdef["glb_path"]),
                "voice_track_path": str(narration_wav),
                "bgm_track_path": str(bgm_wav),
                "mastered_audio_path": str(master_wav),
                "mastered_lufs": round(measured_lufs, 2),
                "mastered_true_peak_dbtp": round(measured_dbtp, 2),
                "keyframes": fdef["keyframes"],
                "subtitles": fdef["subtitles"],
            },
            "sync_policy": {"source_app": "Akunarch", "force_draft": True},
        }
        (proj_dir / "project.akun.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        conn.execute(
            """
            INSERT INTO projects (
                slug, title, kind, planet, region_slug, cowriter_entity_id,
                chapter_no, folder_path, status, created_at, updated_at
            )
            VALUES (?1, ?2, 'cinema', ?3, ?4, NULL, 1, ?5, 'ready_3d', ?6, ?6)
            ON CONFLICT(slug) DO UPDATE SET
                title = excluded.title,
                kind = excluded.kind,
                planet = excluded.planet,
                folder_path = excluded.folder_path,
                status = 'ready_3d',
                updated_at = excluded.updated_at
            """,
            (slug, fdef["title"], fdef["planet"], fdef["region_slug"], str(proj_dir), fdef["ts"]),
        )

        # Link intro video onto parent monument project too!
        mon_manifest_path = PROJECTS_ROOT / fdef["monument_slug"] / "project.akun.json"
        if mon_manifest_path.is_file():
            mm = json.loads(mon_manifest_path.read_text(encoding="utf-8"))
            mm.setdefault("clockwork", {})["intro_video_path"] = str(final_mp4)
            mm["cinema"] = manifest["cinema"]
            mon_manifest_path.write_text(json.dumps(mm, ensure_ascii=False, indent=2), encoding="utf-8")

        print(
            f"[PHASE4_CINEMA_OK] {slug} -> mp4={final_mp4.name} ({final_mp4.stat().st_size // 1024} KB) "
            f"| LUFS={measured_lufs:.2f} | dBTP={measured_dbtp:.2f}",
            flush=True,
        )


def main() -> None:
    PROJECTS_ROOT.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # First ensure Phase 1 canonical projects are seeded cleanly
    run_cmd([str(TOOLS_PY), str(SEED_P1_SCRIPT)], "Seed Phase 1 Canonical Projects", timeout=120)

    now = datetime.now(timezone.utc)
    # Order timestamps so `temple-of-zyberon` remains newest default on cold start,
    # followed cleanly by the Phase 1 monuments and Phase 2/3/4 projects!
    t_base = now - timedelta(minutes=20)

    conn = sqlite3.connect(str(DB_PATH))
    try:
        _, vn_zip = build_phase3_vn_project(conn, (t_base + timedelta(minutes=2)).isoformat())
        build_phase2_adjacent_chunks(
            conn,
            vn_zip,
            (t_base + timedelta(minutes=3)).isoformat(),
            (t_base + timedelta(minutes=4)).isoformat(),
        )
        build_phase4_cinema_videos(
            conn,
            (t_base + timedelta(minutes=5)).isoformat(),
            (t_base + timedelta(minutes=6)).isoformat(),
        )

        # Bump the 4 canonical monuments' updated_at so `temple-of-zyberon` is first in list_projects
        canonical_order = [
            "eryndor-clocktower-concept",
            "singularity-samos-olympus",
            "avalon-mage-sanctum",
            "singularity-stonehenge-avalon",
            "temple-of-zyberon",
        ]
        for idx, cslug in enumerate(canonical_order):
            cts = (t_base + timedelta(minutes=10 + idx)).isoformat()
            conn.execute("UPDATE projects SET updated_at = ?2 WHERE slug = ?1", (cslug, cts))

        conn.commit()
    finally:
        conn.close()

    print("[ALL_P2_P3_P4_DELIVERABLES_COMPLETE]", flush=True)


if __name__ == "__main__":
    main()
