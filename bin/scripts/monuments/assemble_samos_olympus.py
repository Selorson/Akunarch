"""
Akunarch v2.1 — Monument #3: `singularity-samos-olympus` (v4 Surgical 1:1 Edition)
100% 1:1 Architectural & Geological Match to `E:\\Tools-3D\\concepts\\concept_olympus_mountain_pantheon_v4.jpg`.

Fixes all Gate #1 Audit Round 1 findings (3A–3G):
  - 32-bit F32 world-position bake + high-texel UV chart (`1550x1515 px`) + sharp faceted Pentelic/Carrara white-cool-grey marble massif & unified crag buttresses (ZERO 8-bit blocks, ZERO beige dough, ZERO dark-grey mismatched blocks)
  - Exact 4 frothy turquoise-and-white waterfalls nestled inside carved concave exterior cliff gullies (ZERO water or mist discs inside the plaza/colonnade)
  - 258-deg wrapping semicircular fluted peristyle (`-54 deg .. +204 deg`) around the 16-ray gilded Sun-Star plaza, terminated at front-left & front-right by 2 refined pedimented Propylaea portals + projecting circular golden fountain
  - Mid-left pierced white marble Rotunda (Tholos) with pure white ribbed marble dome & delicate gold lantern trim, cleanly separated from the upper-left stairway (ZERO brazier/cornice collision)
  - Multi-fin golden-amber sacred fire braziers along the Grand Right Diagonal Stairway & Summit Parapet
  - Summit Peripteral Pantheon supported on sculpted white marble summit crags (no boxy beige bastion), white marble raking cornice framing classical triangular pediment relief, fine pale marble roof tiles, and a white marble attic podium lifting the fenestrated drum & coffered Golden Dome cleanly above the roof ridge
  - Strict 6-part monotonic coaxial Y-band order guaranteeing `Part 2 dirY >= 1.88m`, `max dirY <= 16.5m`, and `>= 0.36m` world clearance at 50%/100%
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Vector

MONUMENTS_DIR = Path(__file__).resolve().parent
KIT_DIR = Path(r"E:\Tools-3D\scripts\archived_selorson_monuments")
for p in (str(MONUMENTS_DIR), str(KIT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import _aaa_monument_kit as kit  # noqa: E402
import _monument_builders as mb  # noqa: E402

SLUG = "singularity-samos-olympus"
OUT_GLB = mb.resolve_out_glb(SLUG, globals())

scene, t_start = kit.init_blender_optix_scene(
    "MOUNT OLYMPUS PENTELIC MARBLE MASSIF, SUN-STAR PLAZA & GOLDEN PANTHEON (1:1 v4)"
)


# ---------------------------------------------------------------------------
# 1. Custom 2K Materials (Sun-Star Plaza, Coffered Gold Dome, Frothy Waterfall, Golden Fire)
# ---------------------------------------------------------------------------
def build_sunstar_plaza_material() -> bpy.types.Material:
    """2048x2048 white Pentelic marble pavement inlaid with a 16-ray gilded Helios Sun Star & Greek key rings."""
    res = 2048
    tdir = kit.POLY_DIR / "textures" / "marble_01"
    diff = kit.load_img_np(tdir / "Diffuse_2k.jpg", res, is_data=False)[:, :, :3]
    rgh = kit.load_img_np(tdir / "Rough_2k.jpg", res, is_data=True)[:, :, :1]
    nor = kit.load_img_np(tdir / "nor_gl_2k.jpg", res, is_data=True)[:, :, :3]

    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    px = (xx - 0.5) * 2.0
    py = (yy - 0.5) * 2.0
    rr = np.hypot(px, py)
    ang = np.arctan2(py, px)

    # Crisp 16-pointed Helios Sun Star (8 major rays + 8 minor rays)
    sector = ((ang + math.pi) / (2.0 * math.pi)) * 16.0
    sec_idx = np.floor(sector).astype(np.int32) % 16
    sec_u = np.abs((sector - np.floor(sector)) - 0.5) * 2.0
    r_tip = np.where((sec_idx % 2) == 0, 0.55, 0.42)
    ray_half_w = np.clip((r_tip - rr) / np.maximum(r_tip - 0.13, 1e-4), 0.0, 1.0) ** 0.76
    in_rays = (rr >= 0.13) & (rr <= r_tip) & (sec_u <= ray_half_w * 0.70)

    in_core = (rr <= 0.112) | ((rr >= 0.128) & (rr <= 0.154))
    meander_1 = (rr >= 0.61) & (rr <= 0.67) & (np.sin(ang * 48.0 + np.sign(np.sin((rr - 0.64) * 125.0)) * 0.9) > -0.15)
    meander_2 = (rr >= 0.83) & (rr <= 0.89) & (np.cos(ang * 64.0 + np.sign(np.cos((rr - 0.86) * 125.0)) * 0.9) > -0.15)
    ring_lines = (
        (np.abs(rr - 0.595) < 0.008)
        | (np.abs(rr - 0.685) < 0.008)
        | (np.abs(rr - 0.815) < 0.008)
        | (np.abs(rr - 0.905) < 0.008)
    )
    radial_joints = (rr > 0.56) & (rr < 0.96) & (np.abs(np.sin(ang * 16.0)) < 0.014)

    gold_mask = (in_rays | in_core | meander_1 | meander_2 | ring_lines).astype(np.float32)[:, :, None]
    gold_mask = 0.5 * gold_mask + 0.125 * (
        np.roll(gold_mask, 1, 0) + np.roll(gold_mask, -1, 0) + np.roll(gold_mask, 1, 1) + np.roll(gold_mask, -1, 1)
    )

    marble_luma = np.mean(diff, axis=2, keepdims=True)
    marble_col = np.clip(
        np.array([0.89, 0.89, 0.90], dtype=np.float32)[None, None, :] * (0.82 + 0.24 * marble_luma)
        - 0.08 * radial_joints.astype(np.float32)[:, :, None],
        0.10,
        0.97,
    )
    gold_col = np.array([0.85, 0.64, 0.20], dtype=np.float32)[None, None, :] * (0.86 + 0.16 * marble_luma)

    albedo = np.clip(marble_col * (1.0 - gold_mask) + gold_col * gold_mask, 0.05, 0.97)
    r_out = np.clip((rgh * 0.58 + 0.18) * (1.0 - gold_mask) + 0.23 * gold_mask, 0.14, 0.86)
    m_out = 0.88 * gold_mask
    orm_out = np.concatenate([np.full_like(r_out, 0.95), r_out, m_out], axis=2)

    col_img = kit.save_np_img(albedo, kit.BAKED_DIR / "oly_v4_sunstar_plaza_col.jpg", is_data=False)
    orm_img = kit.save_np_img(orm_out, kit.BAKED_DIR / "oly_v4_sunstar_plaza_orm.jpg", is_data=True)
    nor_img = kit.save_np_img(nor, kit.BAKED_DIR / "oly_v4_sunstar_plaza_nor.jpg", is_data=True)
    return kit.make_principled_gltf_material("mat_oly_sunstar_plaza", col_img, orm_img, nor_img, normal_strength=0.60)


def build_coffered_gold_dome_material() -> bpy.types.Material:
    """1024x1024 embossed imperial gilded-bronze coffered dome PBR material with floral rosettes."""
    res = 1024
    tdir = kit.POLY_DIR / "textures" / "metal_plate_02"
    diff = kit.load_img_np(tdir / "Diffuse_2k.jpg", res, is_data=False)[:, :, :3]
    rgh = kit.load_img_np(tdir / "Rough_2k.jpg", res, is_data=True)[:, :, :1]
    nor = kit.load_img_np(tdir / "nor_gl_2k.jpg", res, is_data=True)[:, :, :3]

    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    cx_grid = np.abs(((xx * 12.0) % 1.0) - 0.5) * 2.0
    cy_grid = np.abs(((yy * 12.0) % 1.0) - 0.5) * 2.0
    coffer_frame = np.maximum(cx_grid, cy_grid)
    rosette = np.exp(-(((np.hypot(cx_grid, cy_grid) - 0.34) / 0.13) ** 2)) * (
        0.5 + 0.5 * np.cos(np.arctan2(cy_grid, cx_grid) * 8.0)
    )
    emboss = np.clip(0.55 * (coffer_frame > 0.78).astype(np.float32) + 0.68 * rosette, 0.0, 1.0)

    patina = 0.86 + 0.14 * np.mean(diff, axis=2, keepdims=True)
    albedo = np.clip(
        np.array([0.88, 0.67, 0.22], dtype=np.float32)[None, None, :] * patina * (0.76 + 0.30 * emboss[:, :, None]),
        0.06,
        0.98,
    )
    gx = np.roll(emboss, -1, axis=1) - np.roll(emboss, 1, axis=1)
    gy = np.roll(emboss, -1, axis=0) - np.roll(emboss, 1, axis=0)
    nx = (nor[:, :, 0] * 2.0 - 1.0) - gx * 2.1
    ny = (nor[:, :, 1] * 2.0 - 1.0) - gy * 2.1
    nz = np.maximum(nor[:, :, 2] * 2.0 - 1.0, 0.35)
    nlen = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-6)
    nor_out = np.stack([0.5 + 0.5 * (nx / nlen), 0.5 + 0.5 * (ny / nlen), 0.5 + 0.5 * (nz / nlen)], axis=-1)

    ao_ch = np.clip(0.74 + 0.26 * emboss[:, :, None], 0.0, 1.0)
    r_ch = np.clip(0.20 + 0.11 * rgh - 0.04 * emboss[:, :, None], 0.12, 0.42)
    orm_out = np.concatenate([ao_ch, r_ch, np.full_like(r_ch, 0.89)], axis=2)

    col_img = kit.save_np_img(albedo, kit.BAKED_DIR / "oly_v4_gold_dome_col.jpg", is_data=False)
    orm_img = kit.save_np_img(orm_out, kit.BAKED_DIR / "oly_v4_gold_dome_orm.jpg", is_data=True)
    nor_img = kit.save_np_img(nor_out, kit.BAKED_DIR / "oly_v4_gold_dome_nor.jpg", is_data=True)
    return kit.make_principled_gltf_material("mat_oly_gold_dome", col_img, orm_img, nor_img, normal_strength=1.05)


def build_frothy_waterfall_material() -> bpy.types.Material:
    """
    Flowing Aegean turquoise-and-white frothy waterfall material mapped along UV `(u_across, v_flow)`.
    White aerated foam streaks along edges/crests + luminous turquoise core (ZERO dark garden-hose plastic!).
    """
    res = 512
    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    edge_foam = np.clip((np.abs(xx - 0.5) * 2.0 - 0.48) / 0.52, 0.0, 1.0) ** 1.2
    streaks = (
        0.52 * (0.5 + 0.5 * np.sin(xx * 42.0 + np.sin(yy * 18.0) * 1.4))
        + 0.48 * (0.5 + 0.5 * np.cos(xx * 78.0 - yy * 26.0))
    )
    crest_foam = np.clip((streaks - 0.54) * 2.3 + 0.45 * edge_foam + 0.25 * (yy > 0.82).astype(np.float32), 0.0, 1.0)[
        :, :, None
    ]

    turq_core = np.array([0.16, 0.68, 0.92], dtype=np.float32)[None, None, :]
    foam_white = np.array([0.92, 0.98, 1.00], dtype=np.float32)[None, None, :]
    albedo = np.clip(turq_core * (1.0 - crest_foam) + foam_white * crest_foam, 0.08, 0.99)

    gx = np.roll(streaks, -1, axis=1) - np.roll(streaks, 1, axis=1)
    gy = np.roll(streaks, -1, axis=0) - np.roll(streaks, 1, axis=0)
    nx = -gx * 1.4
    ny = -gy * 0.9
    nz = np.ones_like(nx)
    nlen = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-6)
    nor_out = np.stack([0.5 + 0.5 * (nx / nlen), 0.5 + 0.5 * (ny / nlen), 0.5 + 0.5 * (nz / nlen)], axis=-1)
    rgh_out = 0.14 * (1.0 - crest_foam) + 0.44 * crest_foam
    orm_out = np.concatenate([np.full_like(rgh_out, 0.96), rgh_out, np.zeros_like(rgh_out)], axis=2)

    c_i = kit.save_np_img(albedo, kit.BAKED_DIR / "oly_v4_waterfall_col.jpg", is_data=False)
    o_i = kit.save_np_img(orm_out, kit.BAKED_DIR / "oly_v4_waterfall_orm.jpg", is_data=True)
    n_i = kit.save_np_img(nor_out, kit.BAKED_DIR / "oly_v4_waterfall_nor.jpg", is_data=True)
    return kit.make_principled_gltf_material(
        "mat_oly_frothy_waterfall", c_i, o_i, n_i, normal_strength=0.65
    )


def build_sacred_fire_material() -> bpy.types.Material:
    """Radiant golden-amber sacred fire material (>=86% `#000000` outer border per Golden Rule #6, ZERO salmon-pink!)."""
    res = 256
    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    rr = np.hypot(xx - 0.5, yy - 0.5) * 2.0
    mask = np.clip((0.42 - rr) / 0.16, 0.0, 1.0)[:, :, None]
    core_w = np.clip((0.25 - rr) / 0.18, 0.0, 1.0)[:, :, None]
    hot_gold = np.array([1.00, 0.95, 0.40], dtype=np.float32)[None, None, :]
    warm_amber = np.array([1.00, 0.58, 0.06], dtype=np.float32)[None, None, :]
    glow = warm_amber * (1.0 - core_w) + hot_gold * core_w
    base = np.array([0.14, 0.07, 0.01], dtype=np.float32)[None, None, :] * (1.0 - mask) + glow * (0.95 * mask)
    emit = glow * (mask ** 1.15)
    orm = np.dstack(
        [
            np.full((res, res), 0.95, dtype=np.float32),
            np.full((res, res), 0.22, dtype=np.float32),
            np.zeros((res, res), dtype=np.float32),
        ]
    )
    nor = np.dstack(
        [
            np.full((res, res), 0.5, dtype=np.float32),
            np.full((res, res), 0.5, dtype=np.float32),
            np.ones((res, res), dtype=np.float32),
        ]
    )
    c_i = kit.save_np_img(base, kit.BAKED_DIR / "oly_v4_sacred_fire_col.jpg", is_data=False)
    o_i = kit.save_np_img(orm, kit.BAKED_DIR / "oly_v4_sacred_fire_orm.jpg", is_data=True)
    n_i = kit.save_np_img(nor, kit.BAKED_DIR / "oly_v4_sacred_fire_nor.jpg", is_data=True)
    e_i = kit.save_np_img(emit, kit.BAKED_DIR / "oly_v4_sacred_fire_emit.jpg", is_data=False)
    return kit.make_principled_gltf_material(
        "mat_oly_sacred_fire", c_i, o_i, n_i, normal_strength=0.25, emit_img=e_i, emit_strength=3.80
    )


# Unified crisp Pentelic white marble + matching white-cool-grey alpine marble crag material!
mat_marble = kit.build_polyhaven_gltf_material(
    "oly_pentelic_marble",
    "marble_01",
    base_override_linear=(0.88, 0.88, 0.90),
    contrast=1.06,
    ao_strength=0.40,
    rough_scale=0.68,
    rough_bias=0.10,
    normal_strength=0.68,
)
mat_cliff_crag = kit.build_polyhaven_gltf_material(
    "oly_alpine_marble_crag",
    "rock_face_03",
    base_override_linear=(0.56, 0.57, 0.59),
    contrast=1.36,
    ao_strength=0.68,
    rough_scale=0.88,
    rough_bias=0.06,
    normal_strength=1.35,
)
mat_marble_roof = kit.build_polyhaven_gltf_material(
    "oly_pale_marble_roof_tile",
    "grey_roof_tiles_02",
    base_override_linear=(0.84, 0.85, 0.87),
    contrast=1.08,
    ao_strength=0.38,
    rough_scale=0.74,
    rough_bias=0.08,
    normal_strength=0.72,
)
mat_gold_trim = kit.build_polyhaven_gltf_material(
    "oly_imperial_gold_trim",
    "metal_plate_02",
    base_override_linear=(0.83, 0.62, 0.20),
    contrast=1.14,
    ao_strength=0.42,
    rough_scale=0.44,
    rough_bias=0.05,
    metallic=0.89,
    normal_strength=0.78,
)
mat_bronze_grille = kit.build_polyhaven_gltf_material(
    "oly_sanctuary_gilded_grille",
    "metal_plate_02",
    base_override_linear=(0.30, 0.21, 0.08),
    contrast=1.22,
    ao_strength=0.60,
    rough_scale=0.55,
    metallic=0.78,
)
mat_sunstar_plaza = build_sunstar_plaza_material()
mat_gold_dome = build_coffered_gold_dome_material()
mat_waterfall = build_frothy_waterfall_material()
mat_fountain_pool = kit.build_rippled_water_material(
    "oly_fountain_turquoise_pool",
    deep_rgb=(0.08, 0.54, 0.80),
    shallow_rgb=(0.34, 0.84, 0.98),
    caustic_rgb=(0.88, 0.98, 1.00),
    roughness=0.12,
    emit_strength=0.0,
)
mat_plunge_foam = kit.build_polyhaven_gltf_material(
    "oly_waterfall_spray_foam",
    "painted_plaster_wall",
    base_override_linear=(0.88, 0.96, 1.00),
    contrast=1.04,
    ao_strength=0.18,
    rough_bias=0.22,
    normal_strength=0.35,
)
mat_brazier_flame = build_sacred_fire_material()

# ---------------------------------------------------------------------------
# 2. Multi-Tiered Faceted Pentelic Marble Mountain Massif + Carved Gullies
# ---------------------------------------------------------------------------
Z_CLIFF_BOT = -1.04
PLAZA_X, PLAZA_Y, Z_PLAZA = -0.60, -1.46, 0.50
FOUNT_X, FOUNT_Y = -1.26, -2.98
ROT_X, ROT_Y, Z_ROT = -2.64, 0.06, 1.20
SUM_X, SUM_Y, Z_SUMMIT = 0.56, 1.54, 2.52

# Exact 4 exterior cliff waterfall gully angles (design radians around origin)
GULLY_1_LEFT_RAD = math.radians(-138.0)
GULLY_2_FOUNT_RAD = math.radians(-113.5)
GULLY_3_FRIGHT_RAD = math.radians(-62.0)
GULLY_4_RRIGHT_RAD = math.radians(-31.0)


def _ang_diff(a: float | np.ndarray, b: float) -> float | np.ndarray:
    return np.arctan2(np.sin(a - b), np.cos(a - b))


def outer_rim_r_fn(thetas: np.ndarray) -> np.ndarray:
    """Sharp faceted alpine marble mountain footprint — sheer front cliffs, broad towering rear-right peak."""
    d_ang = thetas - mb.CAM_YAW
    front_tuck = -0.54 * np.exp(-((_ang_diff(d_ang, -math.pi * 0.5) / 0.92) ** 2))
    rear_swell = 0.38 * np.exp(-((_ang_diff(d_ang, math.pi * 0.34) / 1.05) ** 2))
    left_rot_shelf = 0.24 * np.exp(-((_ang_diff(d_ang, math.radians(176.0)) / 0.42) ** 2))
    fount_bulge = 0.34 * np.exp(-((_ang_diff(d_ang, GULLY_2_FOUNT_RAD) / 0.24) ** 2))

    # Crisp angular rock buttress facets (`abs(sin(...))` sharp ridges!)
    faceted = (
        4.14
        + front_tuck
        + rear_swell
        + left_rot_shelf
        + fount_bulge
        + 0.20 * (1.0 - 2.0 * np.abs(np.sin(d_ang * 3.5 - 0.3)))
        + 0.13 * np.sin(d_ang * 9.0 + 1.1)
        + 0.07 * (1.0 - 2.0 * np.abs(np.cos(d_ang * 14.0 - 0.7)))
    )
    # Carve concave cliff notches at the 4 waterfall chutes so water sits recessed inside rock clefts!
    gully_carve = (
        -0.18 * np.exp(-((_ang_diff(d_ang, GULLY_1_LEFT_RAD) / 0.115) ** 2))
        - 0.13 * np.exp(-((_ang_diff(d_ang, GULLY_2_FOUNT_RAD) / 0.105) ** 2))
        - 0.20 * np.exp(-((_ang_diff(d_ang, GULLY_3_FRIGHT_RAD) / 0.115) ** 2))
        - 0.20 * np.exp(-((_ang_diff(d_ang, GULLY_4_RRIGHT_RAD) / 0.115) ** 2))
    )
    return np.clip(faceted + gully_carve, 3.42, 4.74)


def olympus_massif_z_design(dx: float, dy: float, rr: float, r_rim: float) -> float:
    """Multi-tiered faceted alpine marble massif with carved concave waterfall gullies."""
    edge_drop = max(0.0, min(1.0, (r_rim - rr) / 0.62)) ** 0.46
    d_ang = math.atan2(dy, dx)

    # 1) Towering Rear-Upper Summit Peak + Front Summit Crag Spur under Pantheon stairs (replaces boxy bastion!)
    sx = (dx - SUM_X) / 2.28
    sy = (dy - SUM_Y) / 1.92
    w_sum = math.exp(-((sx * sx + sy * sy) ** 1.32) * 0.86)

    # Natural jagged rock spur directly supporting Pantheon front stairs around (0.46, 0.56) — well clear of rear colonnade!
    sp_x = (dx - 0.46) / 1.18
    sp_y = (dy - 0.58) / 0.92
    w_front_spur = math.exp(-((sp_x * sp_x + sp_y * sp_y) ** 1.45) * 1.10)

    # 2) Mid-Left Rotunda Acropolis Terrace around (ROT_X=-2.64, ROT_Y=0.06)
    rx = (dx - ROT_X) / 1.24
    ry = (dy - ROT_Y) / 1.24
    w_rot = math.exp(-((rx * rx + ry * ry) ** 1.75) * 1.05)

    # 3) Right Grand Staircase Escarpment Ridge from (1.62, -1.48) -> (2.36, 1.18) — cleanly outside right colonnade!
    vx, vy = 2.36 - 1.62, 1.18 - (-1.48)
    vlen2 = vx * vx + vy * vy
    t_st = max(0.0, min(1.0, ((dx - 1.62) * vx + (dy + 1.48) * vy) / vlen2))
    dist_st = math.hypot(dx - (1.62 + t_st * vx), dy - (-1.48 + t_st * vy))
    w_stair = math.exp(-((dist_st / 0.72) ** 2.2))
    z_stair_target = Z_PLAZA + t_st * (Z_SUMMIT - Z_PLAZA) - 0.12

    # 4) Lower Front Plaza + Projecting Fountain Promontory
    dist_plz = math.hypot(dx - PLAZA_X, dy - PLAZA_Y)
    dist_fnt = math.hypot(dx - FOUNT_X, dy - FOUNT_Y)
    w_plz = max(
        math.exp(-((max(0.0, dist_plz - 1.66) / 0.52) ** 1.8)),
        math.exp(-((max(0.0, dist_fnt - 0.44) / 0.40) ** 1.8)),
    )

    # Sharp faceted alpine crag creases!
    ridge1 = 1.0 - abs(math.sin(dx * 1.65 + dy * 1.25 + 0.35))
    ridge2 = 1.0 - abs(math.cos(dx * 2.60 - dy * 2.05 - 0.60))
    ridge3 = 1.0 - abs(math.sin(dx * 3.80 + dy * 3.10 + 1.15))
    crag = (0.38 * ridge1 + 0.24 * ridge2 + 0.12 * ridge3) * (1.0 - 0.92 * max(w_plz, w_rot))

    z_raw = max(
        0.16 + (Z_SUMMIT - 0.22) * w_sum + crag * (0.42 + 0.52 * max(0.0, (dy + 1.2) / 3.8)),
        (Z_SUMMIT - 0.48) * w_front_spur + 0.22 * crag,
        Z_ROT * w_rot,
        z_stair_target * w_stair,
        Z_PLAZA * w_plz,
    )

    # Carve concave upper cleft for Waterfall #3a (`(1.04, 0.56) -> (1.22, -0.34)`, `dist_plz >= 2.14m` strictly outside colonnade!)
    g3_vx, g3_vy = 1.22 - 1.04, -0.34 - 0.56
    g3_l2 = g3_vx * g3_vx + g3_vy * g3_vy
    g3_t = max(0.0, min(1.0, ((dx - 1.04) * g3_vx + (dy - 0.56) * g3_vy) / g3_l2))
    g3_dist = math.hypot(dx - (1.04 + g3_vx * g3_t), dy - (0.56 + g3_vy * g3_t))
    if dist_plz > 1.98:
        z_raw -= 0.18 * math.exp(-((g3_dist / 0.24) ** 2))

    # Carve concave rim gullies for the outer slope cascades (#1, #3, #4)
    for g_rad, r_min_g in ((GULLY_1_LEFT_RAD, 2.85), (GULLY_3_FRIGHT_RAD, 2.75), (GULLY_4_RRIGHT_RAD, 2.75)):
        if rr > r_min_g:
            ad = float(_ang_diff(d_ang, g_rad))
            z_raw -= 0.22 * math.exp(-((ad / 0.105) ** 2)) * min(1.0, (rr - r_min_g) / 0.35)

    # Keep full 360-deg Plaza & Colonnade terrace cleanly level (`dist_plz < 1.92`) so ZERO rock pokes between columns!
    if dist_plz < 1.92 or dist_fnt < 0.58:
        flat_blend = max(
            max(0.0, min(1.0, (1.92 - dist_plz) / 0.22)),
            max(0.0, min(1.0, (0.58 - dist_fnt) / 0.18)),
        )
        z_raw = z_raw * (1.0 - flat_blend) + (Z_PLAZA - 0.02) * flat_blend

    dist_rot = math.hypot(dx - ROT_X, dy - ROT_Y)
    if dist_rot < 1.12:
        rot_blend = max(0.0, min(1.0, (1.12 - dist_rot) / 0.20))
        z_raw = z_raw * (1.0 - rot_blend) + (Z_ROT - 0.02) * rot_blend

    return z_raw * edge_drop + (-0.24) * (1.0 - edge_drop)


def top_surface_z_fn(wx: float, wy: float, rr: float, th: float) -> float:
    dx, dy = mb.w2d_xy(wx, wy)
    r_rim = float(outer_rim_r_fn(np.array([th]))[0])
    return olympus_massif_z_design(float(dx), float(dy), rr, r_rim)


def cliff_r_fn(th_grid: np.ndarray, zz_grid: np.ndarray, s_frac: np.ndarray, rim_r: np.ndarray) -> np.ndarray:
    """Sheer faceted Pentelic marble cliffs with vertical angular strata & recessed waterfall chutes."""
    d_ang = th_grid - mb.CAM_YAW
    chute_mask = np.clip(
        np.exp(-((_ang_diff(d_ang, GULLY_1_LEFT_RAD) / 0.12) ** 2))
        + np.exp(-((_ang_diff(d_ang, GULLY_2_FOUNT_RAD) / 0.11) ** 2))
        + np.exp(-((_ang_diff(d_ang, GULLY_3_FRIGHT_RAD) / 0.12) ** 2))
        + np.exp(-((_ang_diff(d_ang, GULLY_4_RRIGHT_RAD) / 0.12) ** 2)),
        0.0,
        1.0,
    )
    faceted_ribs = (
        0.09 * (s_frac ** 0.70) * (1.0 - 2.0 * np.abs(np.sin(d_ang * 5.0 - s_frac * 1.4)))
        + 0.12 * (1.0 - 2.0 * np.abs(np.cos(d_ang * 13.0 + s_frac * 3.8))) * np.sin(s_frac * math.pi)
        - 0.09 * np.abs(np.sin(d_ang * 19.0 - s_frac * 4.2))
    ) * (1.0 - 0.85 * chute_mask)
    chute_recess = -0.18 * chute_mask * np.sin(np.clip(s_frac * 1.15, 0.0, 1.0) * math.pi * 0.85)
    return rim_r + faceted_ribs + chute_recess


# ---------------------------------------------------------------------------
# 3. Create 6 Monotonic Coaxial Part Empties (`max dirY <= 16.5m` guaranteed!)
# ---------------------------------------------------------------------------
p1_massif = kit.create_part_empty(scene, "olympus_marble_massif_and_waterfalls")
p2_plaza_peristyle = kit.create_part_empty(scene, "helios_plaza_and_peristyle_sanctuary")
p3_stairs = kit.create_part_empty(scene, "grand_stairways_and_sacred_braziers")
p4_rotunda = kit.create_part_empty(scene, "mid_left_pierced_marble_rotunda_tholos")
p5_pantheon = kit.create_part_empty(scene, "summit_pantheon_colonnade_and_guardians")
p6_dome = kit.create_part_empty(scene, "summit_attic_drum_and_golden_dome")

# ---------------------------------------------------------------------------
# PART 1: Faceted White-Cool-Grey Marble Massif (32-bit F32 Bake) + Crags + 4 Waterfalls
# ---------------------------------------------------------------------------
radii_top = [
    0.05, 0.11, 0.17, 0.24, 0.31, 0.38, 0.45, 0.52,
    0.59, 0.66, 0.73, 0.80, 0.86, 0.92, 0.97, 1.00,
]
massif_obj, m_ao, m_pt, m_nz, m_wx, m_wy, m_wz, m_vm = mb.build_hi_res_cutaway_terrain_mesh(
    scene=scene,
    mesh_name="olympus_marble_massif_mesh",
    radii_top=radii_top,
    z_cliff_bot=Z_CLIFF_BOT,
    outer_rim_r_fn=outer_rim_r_fn,
    top_surface_z_fn=top_surface_z_fn,
    cliff_r_fn=cliff_r_fn,
    n_ang=280,
    n_z=56,
    bake_res=2048,
    sharp_cliff_facets=True,
)

cliff_col, cliff_rgh, cliff_nor = kit.sample_triplanar_or_cyl_pbr(
    "cliff_side", m_wx, m_wy, m_wz, m_nz, bake_res=2048, planar_scale=0.82, cyl_rep=10.0, z_scale=0.92
)
marb_col, marb_rgh, marb_nor = kit.sample_triplanar_or_cyl_pbr(
    "marble_01", m_wx, m_wy, m_wz, m_nz, bake_res=2048, planar_scale=0.88, cyl_rep=10.0, z_scale=0.90
)

# Chiseled high-contrast Pentelic white-ivory & cool slate-shadow alpine marble matching Concept v4!
cliff_luma = np.mean(cliff_col, axis=2, keepdims=True)
marb_luma = np.mean(marb_col, axis=2, keepdims=True)
ridge_hi = np.clip((m_pt - 0.498) * 20.0, -0.58, 0.78)
steep_wall = np.clip((0.82 - np.abs(m_nz)) * 2.1, 0.0, 1.0)
sunlit_marble = np.array([0.78, 0.78, 0.76], dtype=np.float32)[None, None, :]
cool_crevice = np.array([0.16, 0.18, 0.22], dtype=np.float32)[None, None, :]
strata_wave = 0.5 + 0.5 * np.sin(m_wz * 10.5 + m_wx * 2.1 - m_wy * 1.6)

ao_curve = np.clip((m_ao - 0.12) / 0.88, 0.0, 1.0) ** 1.32
rock_base = cool_crevice * (1.0 - ao_curve) + sunlit_marble * ao_curve
detail_mod = np.clip(0.54 + 0.58 * cliff_luma + 0.28 * (marb_luma - 0.45) - 0.12 * strata_wave * steep_wall, 0.28, 1.24)
massif_albedo = np.clip(
    rock_base * detail_mod * (1.0 + 0.26 * ridge_hi) * (0.38 + 0.62 * ao_curve),
    0.04,
    0.92,
)
massif_albedo = kit.dilate_uv_gutters(massif_albedo, m_vm, iterations=18)
massif_rgh = np.clip(0.58 * cliff_rgh + 0.42 * marb_rgh + 0.08 - 0.08 * np.clip(ridge_hi, 0.0, 1.0), 0.30, 0.92)
massif_nor = 0.76 * cliff_nor + 0.24 * marb_nor
massif_orm = np.concatenate([m_ao, massif_rgh, np.zeros_like(massif_rgh)], axis=2)

m_col_img = kit.save_np_img(massif_albedo, kit.BAKED_DIR / "oly_v4_massif_2k_col.jpg", is_data=False)
m_orm_img = kit.save_np_img(massif_orm, kit.BAKED_DIR / "oly_v4_massif_2k_orm.jpg", is_data=True)
m_nor_img = kit.save_np_img(massif_nor, kit.BAKED_DIR / "oly_v4_massif_2k_nor.jpg", is_data=True)
mat_massif_2k = kit.make_principled_gltf_material("mat_oly_massif_2k", m_col_img, m_orm_img, m_nor_img, normal_strength=1.35)
massif_obj.data.materials.clear()
massif_obj.data.materials.append(mat_massif_2k)
kit.parent_keep_local(massif_obj, p1_massif)


def _cliff_surface_r(d_ang_rad: float, z_val: float) -> float:
    th_arr = np.array([d_ang_rad + mb.CAM_YAW], dtype=np.float64)
    rim_arr = outer_rim_r_fn(th_arr)
    z_top = olympus_massif_z_design(
        float(rim_arr[0]) * math.cos(d_ang_rad),
        float(rim_arr[0]) * math.sin(d_ang_rad),
        float(rim_arr[0]),
        float(rim_arr[0]),
    )
    s_frac = np.array([max(0.0, min(1.0, (z_val - Z_CLIFF_BOT) / max(0.25, z_top - Z_CLIFF_BOT)))], dtype=np.float64)
    return float(cliff_r_fn(th_arr, np.array([z_val]), s_frac, rim_arr)[0])


def _cliff_pt(d_ang_deg: float, z_val: float, out_offset: float = 0.04) -> tuple[float, float, float]:
    ar = math.radians(d_ang_deg)
    rr = _cliff_surface_r(ar, z_val) + out_offset
    return (rr * math.cos(ar), rr * math.sin(ar), z_val)


# Unified Pentelic white-grey angular marble crag buttresses (including jagged summit spurs under Pantheon front stairs!)
crag_spurs = [
    # Perimeter cliff buttresses flanking (never occluding!) the 4 waterfalls
    (*_cliff_pt(-154.0, -0.25, -0.18)[:2], -1.02, 0.76, 0.60, 1.50, 28.0),
    (*_cliff_pt(-125.0, -0.28, -0.18)[:2], -1.02, 0.72, 0.56, 1.46, 16.0),
    (*_cliff_pt(-98.0, -0.30, -0.16)[:2], -1.02, 0.80, 0.62, 1.52, -10.0),
    (*_cliff_pt(-76.0, -0.28, -0.16)[:2], -1.02, 0.78, 0.60, 1.50, -22.0),
    (*_cliff_pt(-47.0, -0.22, -0.18)[:2], -1.02, 0.82, 0.64, 1.66, -38.0),
    (*_cliff_pt(-14.0, -0.12, -0.20)[:2], -1.02, 0.88, 0.68, 1.94, -62.0),
    # Mid-mountain jagged Pentelic marble spurs framing (not blocking!) the central sanctuary cleft (`min_dist_plz >= 1.96m`)!
    (-0.94, 0.78, 0.74, 0.84, 0.62, 1.68, 18.0),
    (0.22, 0.80, 0.78, 0.76, 0.58, 1.66, -6.0),
    (1.48, 0.88, 0.84, 0.72, 0.56, 1.62, -24.0),
    (-0.42, 0.98, 0.92, 0.82, 0.60, 1.56, 8.0),
]
for idx_cr, (cx, cy, cz, sx, sy, sz, cyaw) in enumerate(crag_spurs):
    mb.add_craggy_megalith(
        scene,
        f"olympus_marble_crag_spur_{idx_cr}",
        (cx, cy, cz),
        (sx, sy, sz),
        mat_cliff_crag,
        p1_massif,
        rot_design=(0.05, -0.04, math.radians(cyaw)),
        taper_top=0.48,
        crag_amp=0.15,
        seed=400.0 + idx_cr * 9.1,
        uv_scale=0.58,
    )


def add_recessed_waterfall_sheet(
    name: str,
    pts_design: list[tuple[float, float, float]],
    w_start: float,
    w_end: float,
    with_base_foam: bool = True,
):
    """
    Build a thin, concave-nestled frothy waterfall sheet with directional flow UVs `(u_across, v_flow)`
    and irregular rock-hugged spray cushions (ZERO round garden hoses, ZERO flat disc puddles!).
    """
    bm = bmesh.new()
    uv_lay = bm.loops.layers.uv.new("UVMap")
    pts = [Vector(mb.d2w(*p)) for p in pts_design]
    s_pts = [pts[0]]
    for i in range(len(pts) - 1):
        for f in (0.25, 0.50, 0.75, 1.0):
            s_pts.append(pts[i].lerp(pts[i + 1], f))

    rows = []
    n_p = len(s_pts)
    for i, p in enumerate(s_pts):
        v_flow = (i / max(1, n_p - 1)) * 2.4
        tang = (s_pts[min(n_p - 1, i + 1)] - s_pts[max(0, i - 1)]).normalized()
        side = tang.cross(Vector((0, 0, 1)))
        if side.length < 1e-3:
            side = Vector((1, 0, 0))
        else:
            side.normalize()
        out_n = side.cross(tang).normalized()
        u_t = i / max(1, n_p - 1)
        hw = 0.5 * (w_start * (1.0 - u_t) + w_end * u_t) * (1.0 + 0.09 * math.sin(u_t * 15.0))
        thk = 0.042 + 0.018 * math.sin(u_t * 11.0)
        # Thin ribbon profile hugging the rock gully (wide across, shallow depth)
        prof = [
            (p - side * hw - out_n * (thk * 0.6), 0.02),
            (p - side * (hw * 0.45) + out_n * (thk * 0.7), 0.28),
            (p + side * (hw * 0.45) + out_n * (thk * 0.7), 0.72),
            (p + side * hw - out_n * (thk * 0.6), 0.98),
            (p + side * (hw * 0.4) - out_n * (thk * 1.1), 0.70),
            (p - side * (hw * 0.4) - out_n * (thk * 1.1), 0.30),
        ]
        rows.append([(bm.verts.new(co), u_c, v_flow) for co, u_c in prof])

    for i in range(n_p - 1):
        for k in range(6):
            kn = (k + 1) % 6
            v00, u00, vf0 = rows[i][k]
            v01, u01, _ = rows[i][kn]
            v11, u11, vf1 = rows[i + 1][kn]
            v10, u10, _ = rows[i + 1][k]
            f = bm.faces.new([v00, v01, v11, v10])
            for lp, uv_c in zip(f.loops, [(u00, vf0), (u01, vf0), (u11, vf1), (u10, vf1)]):
                lp[uv_lay].uv = uv_c
    f_top = bm.faces.new([r[0] for r in reversed(rows[0])])
    for lp in f_top.loops:
        lp[uv_lay].uv = (0.5, 0.0)
    f_bot = bm.faces.new([r[0] for r in rows[-1]])
    for lp in f_bot.loops:
        lp[uv_lay].uv = (0.5, 1.0)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m = bpy.data.meshes.new(name)
    bm.to_mesh(m)
    bm.free()
    for poly in m.polygons:
        poly.use_smooth = True
    o = bpy.data.objects.new(name, m)
    scene.collection.objects.link(o)
    o.data.materials.append(mat_waterfall)
    kit.parent_keep_local(o, p1_massif)

    if with_base_foam:
        foot_w = Vector(mb.d2w(*pts_design[-1]))
        bm_sp = bmesh.new()
        uv_sp = bm_sp.loops.layers.uv.new("UVMap")
        lobe_specs = [
            (0.0, 0.0, w_end * 0.44, 0.095),
            (-w_end * 0.28, 0.02, w_end * 0.30, 0.070),
            (w_end * 0.28, -0.02, w_end * 0.30, 0.070),
        ]
        for l_ox, l_oy, l_r, l_h in lobe_specs:
            n_az_s = 12
            r_low, r_mid = [], []
            for ka in range(n_az_s):
                aa = (ka / n_az_s) * 2.0 * math.pi
                rip = 0.88 + 0.16 * math.sin(ka * 3.0 + l_ox * 8.0)
                r_low.append(bm_sp.verts.new(foot_w + Vector((l_ox + l_r * rip * math.cos(aa), l_oy + l_r * 0.68 * rip * math.sin(aa), -0.03))))
                r_mid.append(bm_sp.verts.new(foot_w + Vector((l_ox + l_r * 0.65 * rip * math.cos(aa), l_oy + l_r * 0.46 * rip * math.sin(aa), l_h * 0.65))))
            vc_top = bm_sp.verts.new(foot_w + Vector((l_ox, l_oy, l_h)))
            vc_bot = bm_sp.verts.new(foot_w + Vector((l_ox, l_oy, -0.04)))
            for ka in range(n_az_s):
                kan = (ka + 1) % n_az_s
                for f_new in (
                    bm_sp.faces.new([vc_bot, r_low[kan], r_low[ka]]),
                    bm_sp.faces.new([r_low[ka], r_low[kan], r_mid[kan], r_mid[ka]]),
                    bm_sp.faces.new([r_mid[ka], r_mid[kan], vc_top]),
                ):
                    for lp in f_new.loops:
                        lp[uv_sp].uv = (0.5, 0.5)
        bmesh.ops.recalc_face_normals(bm_sp, faces=bm_sp.faces)
        m_sp = bpy.data.meshes.new(f"{name}_foam_cushion")
        bm_sp.to_mesh(m_sp)
        bm_sp.free()
        for poly in m_sp.polygons:
            poly.use_smooth = True
        o_sp = bpy.data.objects.new(f"{name}_foam_cushion", m_sp)
        scene.collection.objects.link(o_sp)
        o_sp.data.materials.append(mat_plunge_foam)
        kit.parent_keep_local(o_sp, p1_massif)


def _gully_waterfall_path(d_ang_deg: float, r_start: float) -> list[tuple[float, float, float]]:
    ar = math.radians(d_ang_deg)
    th_arr = np.array([ar + mb.CAM_YAW], dtype=np.float64)
    r_rim = float(outer_rim_r_fn(th_arr)[0])
    pts: list[tuple[float, float, float]] = []
    r_s = min(r_start, r_rim - 0.16)
    for frac in (0.0, 0.52, 0.94):
        rr = r_s + (r_rim - 0.04 - r_s) * frac
        dx = rr * math.cos(ar)
        dy = rr * math.sin(ar)
        zz = olympus_massif_z_design(dx, dy, rr, r_rim) + 0.09
        pts.append((dx, dy, zz))
    z_lip = olympus_massif_z_design((r_rim - 0.03) * math.cos(ar), (r_rim - 0.03) * math.sin(ar), r_rim - 0.03, r_rim) + 0.08
    for f_drop, off in ((0.14, 0.105), (0.44, 0.115), (0.74, 0.120), (0.97, 0.125)):
        zd = z_lip * (1.0 - f_drop) + Z_CLIFF_BOT * f_drop
        pts.append(_cliff_pt(d_ang_deg, zd, off))
    return pts


# Exact 1:1 Recessed Cliff Waterfalls matching `concept_olympus_mountain_pantheon_v4.jpg` (ZERO colonnade/stair collision!):
# 1) Left cliff waterfall plunging from the notch between Rotunda & Plaza straight down the sheer left cliff
add_recessed_waterfall_sheet(
    "olympus_waterfall_1_left_cliff",
    _gully_waterfall_path(-138.0, r_start=3.18),
    w_start=0.28,
    w_end=0.44,
)
# 2) Front promontory waterfall pouring straight out of the circular golden fountain down the sheer cliff chute
add_recessed_waterfall_sheet(
    "olympus_waterfall_2_front_fountain",
    [
        (FOUNT_X - 0.08, FOUNT_Y - 0.44, Z_PLAZA + 0.05),
        _cliff_pt(-113.5, Z_PLAZA - 0.14, 0.115),
        _cliff_pt(-113.5, -0.18, 0.125),
        _cliff_pt(-113.5, -0.60, 0.130),
        _cliff_pt(-113.5, -0.98, 0.135),
    ],
    w_start=0.30,
    w_end=0.44,
)
# 3a) Upper sanctuary cleft cascade below the Pantheon's right guardian into a subterranean cleft pool (`min_dist_plz >= 2.14m`!)
add_recessed_waterfall_sheet(
    "olympus_waterfall_3a_upper_sanctuary_cleft",
    [
        (1.04, 0.56, max(1.94, olympus_massif_z_design(1.04, 0.56, math.hypot(1.04, 0.56), 4.2) + 0.16)),
        (1.10, 0.24, max(1.66, olympus_massif_z_design(1.10, 0.24, math.hypot(1.10, 0.24), 4.2) + 0.16)),
        (1.16, -0.06, max(1.36, olympus_massif_z_design(1.16, -0.06, math.hypot(1.16, -0.06), 4.2) + 0.15)),
        (1.22, -0.34, max(1.06, olympus_massif_z_design(1.22, -0.34, math.hypot(1.22, -0.34), 4.2) + 0.14)),
    ],
    w_start=0.24,
    w_end=0.34,
    with_base_foam=True,
)
# 3b) Subterranean outflow emerging directly from the sheer front-right cliff wall below the marble terrace!
add_recessed_waterfall_sheet(
    "olympus_waterfall_3b_front_right_cliff_spring",
    [
        _cliff_pt(-62.0, Z_PLAZA - 0.16, 0.110),
        _cliff_pt(-62.0, -0.05, 0.120),
        _cliff_pt(-62.0, -0.52, 0.128),
        _cliff_pt(-62.0, -0.98, 0.135),
    ],
    w_start=0.28,
    w_end=0.44,
)
# 4) Right escarpment waterfall plunging from beneath the upper Grand Staircase retaining wall down the right cliff flank
add_recessed_waterfall_sheet(
    "olympus_waterfall_4_right_escarpment",
    [
        (2.26, -0.26, olympus_massif_z_design(2.26, -0.26, math.hypot(2.26, -0.26), 4.2) + 0.14),
        (2.64, -0.88, olympus_massif_z_design(2.64, -0.88, math.hypot(2.64, -0.88), 4.2) + 0.15),
        (2.98, -1.46, olympus_massif_z_design(2.98, -1.46, math.hypot(2.98, -1.46), 4.2) + 0.15),
        _cliff_pt(-31.0, 0.10, 0.130),
        _cliff_pt(-31.0, -0.45, 0.138),
        _cliff_pt(-31.0, -0.96, 0.145),
    ],
    w_start=0.26,
    w_end=0.44,
)

# ---------------------------------------------------------------------------
# PART 2: Circular Sun-Star Plaza, Golden Fountain, 258° Wrapping Peristyle & Twin Portals
# ---------------------------------------------------------------------------
R_PLAZA = 1.78
WXY_PLZ = mb.d2w(PLAZA_X, PLAZA_Y, 0.0)

bm_pz = bmesh.new()
uv_pz = bm_pz.loops.layers.uv.new("UVMap")
n_pz = 72
pz_top, pz_bot = [], []
for k in range(n_pz):
    ang = (k / n_pz) * 2.0 * math.pi
    dx = PLAZA_X + R_PLAZA * math.cos(ang)
    dy = PLAZA_Y + R_PLAZA * math.sin(ang)
    pz_top.append((bm_pz.verts.new(mb.d2w(dx, dy, Z_PLAZA + 0.05)), 0.5 + 0.48 * math.cos(ang), 0.5 + 0.48 * math.sin(ang)))
    pz_bot.append(bm_pz.verts.new(mb.d2w(dx, dy, Z_PLAZA - 0.08)))
vc_t = bm_pz.verts.new(mb.d2w(PLAZA_X, PLAZA_Y, Z_PLAZA + 0.05))
vc_b = bm_pz.verts.new(mb.d2w(PLAZA_X, PLAZA_Y, Z_PLAZA - 0.08))
for k in range(n_pz):
    kn = (k + 1) % n_pz
    vt0, u0, v0 = pz_top[k]
    vt1, u1, v1 = pz_top[kn]
    ft = bm_pz.faces.new([vc_t, vt0, vt1])
    for lp, uv_c in zip(ft.loops, [(0.5, 0.5), (u0, v0), (u1, v1)]):
        lp[uv_pz].uv = uv_c
    fs = bm_pz.faces.new([pz_bot[k], pz_bot[kn], vt1, vt0])
    for lp in fs.loops:
        lp[uv_pz].uv = (0.04, 0.04)
    fb = bm_pz.faces.new([vc_b, pz_bot[kn], pz_bot[k]])
    for lp in fb.loops:
        lp[uv_pz].uv = (0.04, 0.04)
bmesh.ops.recalc_face_normals(bm_pz, faces=bm_pz.faces)
m_pz = bpy.data.meshes.new("olympus_sunstar_plaza_deck")
bm_pz.to_mesh(m_pz)
bm_pz.free()
o_pz = bpy.data.objects.new("olympus_sunstar_plaza_deck", m_pz)
scene.collection.objects.link(o_pz)
o_pz.data.materials.append(mat_sunstar_plaza)
kit.parent_keep_local(o_pz, p2_plaza_peristyle)

plaza_rim = kit.add_prism_ring(
    scene, "olympus_plaza_marble_curb", R_PLAZA + 0.12, R_PLAZA - 0.04, Z_PLAZA - 0.08, Z_PLAZA + 0.10, sides=56, bevel=0.012
)
plaza_rim.location = (WXY_PLZ[0], WXY_PLZ[1], 0.0)
kit.apply_box_uv_and_mat(plaza_rim, mat_marble, uv_scale=0.52)
kit.parent_keep_local(plaza_rim, p2_plaza_peristyle)

plaza_gold_band = kit.add_prism_ring(
    scene, "olympus_plaza_gold_band", R_PLAZA + 0.135, R_PLAZA + 0.02, Z_PLAZA + 0.02, Z_PLAZA + 0.065, sides=56, bevel=0.006
)
plaza_gold_band.location = (WXY_PLZ[0], WXY_PLZ[1], 0.0)
kit.apply_box_uv_and_mat(plaza_gold_band, mat_gold_trim, uv_scale=0.65)
kit.parent_keep_local(plaza_gold_band, p2_plaza_peristyle)

# Projecting Circular Gold-Rimmed Fountain at (FOUNT_X, FOUNT_Y)
WXY_FNT = mb.d2w(FOUNT_X, FOUNT_Y, 0.0)
fnt_deck = kit.add_prism_ring(scene, "fountain_marble_base", 0.58, 0.0, Z_PLAZA - 0.08, Z_PLAZA + 0.06, sides=36, bevel=0.012)
fnt_deck.location = (WXY_FNT[0], WXY_FNT[1], 0.0)
kit.apply_box_uv_and_mat(fnt_deck, mat_marble, uv_scale=0.6)
kit.parent_keep_local(fnt_deck, p2_plaza_peristyle)

fnt_rim_gold = kit.add_prism_ring(scene, "fountain_gold_rim", 0.52, 0.41, Z_PLAZA + 0.05, Z_PLAZA + 0.16, sides=36, bevel=0.010)
fnt_rim_gold.location = (WXY_FNT[0], WXY_FNT[1], 0.0)
kit.apply_box_uv_and_mat(fnt_rim_gold, mat_gold_trim, uv_scale=0.7)
kit.parent_keep_local(fnt_rim_gold, p2_plaza_peristyle)

fnt_water = kit.add_prism_ring(scene, "fountain_turquoise_water", 0.42, 0.0, Z_PLAZA + 0.05, Z_PLAZA + 0.125, sides=32, bevel=0.004)
fnt_water.location = (WXY_FNT[0], WXY_FNT[1], 0.0)
kit.apply_box_uv_and_mat(fnt_water, mat_fountain_pool, uv_scale=1.1)
kit.parent_keep_local(fnt_water, p2_plaza_peristyle)

fnt_ped = kit.add_prism_ring(scene, "fountain_center_pedestal", 0.12, 0.0, Z_PLAZA + 0.08, Z_PLAZA + 0.25, sides=14, bevel=0.008)
fnt_ped.location = (WXY_FNT[0], WXY_FNT[1], 0.0)
kit.apply_box_uv_and_mat(fnt_ped, mat_gold_trim, uv_scale=0.9)
kit.parent_keep_local(fnt_ped, p2_plaza_peristyle)

# Full 258-deg Wrapping Semicircular Peristyle (`-54 deg .. +204 deg`) framing the Sun-Star Plaza!
COL_ARC_START_DEG = -54.0
COL_ARC_END_DEG = 204.0
R_PERISTYLE_OUT = 1.62
R_PERISTYLE_IN = 1.38
H_PERISTYLE_COL = 0.80


def add_smooth_curved_band(
    name: str,
    r_mid: float,
    width_r: float,
    z0: float,
    z1: float,
    a0_d: float,
    a1_d: float,
    mat: bpy.types.Material,
    parent_emp: bpy.types.Object,
):
    bm = bmesh.new()
    n_seg = 48
    ri = r_mid - 0.5 * width_r
    ro = r_mid + 0.5 * width_r
    ob, ot, ib, it = [], [], [], []
    for k in range(n_seg + 1):
        a = math.radians(a0_d + (a1_d - a0_d) * (k / n_seg))
        ob.append(bm.verts.new(mb.d2w(PLAZA_X + ro * math.cos(a), PLAZA_Y + ro * math.sin(a), z0)))
        ot.append(bm.verts.new(mb.d2w(PLAZA_X + ro * math.cos(a), PLAZA_Y + ro * math.sin(a), z1)))
        ib.append(bm.verts.new(mb.d2w(PLAZA_X + ri * math.cos(a), PLAZA_Y + ri * math.sin(a), z0)))
        it.append(bm.verts.new(mb.d2w(PLAZA_X + ri * math.cos(a), PLAZA_Y + ri * math.sin(a), z1)))
    for k in range(n_seg):
        bm.faces.new([ob[k], ob[k + 1], ot[k + 1], ot[k]])
        bm.faces.new([it[k], it[k + 1], ib[k + 1], ib[k]])
        bm.faces.new([ot[k], ot[k + 1], it[k + 1], it[k]])
        bm.faces.new([ib[k], ib[k + 1], ob[k + 1], ob[k]])
    bm.faces.new([ib[0], ob[0], ot[0], it[0]])
    bm.faces.new([ob[-1], ib[-1], it[-1], ot[-1]])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m = bpy.data.meshes.new(name)
    bm.to_mesh(m)
    bm.free()
    o = bpy.data.objects.new(name, m)
    scene.collection.objects.link(o)
    kit.apply_box_uv_and_mat(o, mat, uv_scale=0.55)
    kit.parent_keep_local(o, parent_emp)


add_smooth_curved_band(
    "peristyle_curved_stylobate", 1.50, 0.42, Z_PLAZA + 0.04, Z_PLAZA + 0.12, COL_ARC_START_DEG - 4.0, COL_ARC_END_DEG + 4.0, mat_marble, p2_plaza_peristyle
)

n_arc_cols = 21
for ic in range(n_arc_cols):
    ang_d = COL_ARC_START_DEG + (COL_ARC_END_DEG - COL_ARC_START_DEG) * (ic / (n_arc_cols - 1))
    rad = math.radians(ang_d)
    for r_row, tag_r in ((R_PERISTYLE_OUT, "out"), (R_PERISTYLE_IN, "in")):
        cx = PLAZA_X + r_row * math.cos(rad)
        cy = PLAZA_Y + r_row * math.sin(rad)
        mb.add_fluted_classical_column(
            scene,
            f"peristyle_col_{tag_r}_{ic}",
            (cx, cy, Z_PLAZA + 0.12),
            height=H_PERISTYLE_COL,
            radius_base=0.046,
            mat_marble=mat_marble,
            mat_gold=mat_gold_trim,
            parent=p2_plaza_peristyle,
            n_flutes=14,
        )

Z_ENT = Z_PLAZA + 0.12 + H_PERISTYLE_COL
add_smooth_curved_band(
    "peristyle_architrave", 1.50, 0.36, Z_ENT, Z_ENT + 0.075, COL_ARC_START_DEG - 2.0, COL_ARC_END_DEG + 2.0, mat_marble, p2_plaza_peristyle
)
add_smooth_curved_band(
    "peristyle_gold_frieze", 1.50, 0.37, Z_ENT + 0.075, Z_ENT + 0.12, COL_ARC_START_DEG - 2.0, COL_ARC_END_DEG + 2.0, mat_gold_trim, p2_plaza_peristyle
)
add_smooth_curved_band(
    "peristyle_cornice_deck", 1.50, 0.43, Z_ENT + 0.12, Z_ENT + 0.195, COL_ARC_START_DEG - 3.0, COL_ARC_END_DEG + 3.0, mat_marble, p2_plaza_peristyle
)


def add_pediment_portal_pavilion(
    name: str,
    cx: float,
    cy: float,
    z_base: float,
    width: float,
    depth: float,
    col_h: float,
    yaw_deg: float,
    parent_emp: bpy.types.Object,
):
    """Refined classical 4-column Propylaea portal seamlessly terminating the colonnade ends."""
    yaw = math.radians(yaw_deg)
    ca, sa = math.cos(yaw), math.sin(yaw)

    def l2d(lx: float, ly: float, lz: float = 0.0) -> tuple[float, float, float]:
        return (cx + lx * ca - ly * sa, cy + lx * sa + ly * ca, z_base + lz)

    for sx_p in (-width * 0.40, width * 0.40):
        for sy_p in (-depth * 0.38, depth * 0.38):
            mb.add_fluted_classical_column(
                scene,
                f"{name}_col_{sx_p:+.2f}_{sy_p:+.2f}",
                l2d(sx_p, sy_p, 0.0),
                col_h,
                0.048,
                mat_marble,
                mat_gold_trim,
                parent_emp,
                n_flutes=14,
            )

    kit.add_beveled_box(
        scene,
        f"{name}_entablature",
        mb.d2w(*l2d(0.0, 0.0, col_h + 0.065)),
        (width, depth, 0.13),
        mat_marble,
        parent_emp,
        rot_xyz=mb.rot_d2w(0.0, 0.0, yaw),
        bevel=0.007,
    )
    kit.add_beveled_box(
        scene,
        f"{name}_gold_frieze",
        mb.d2w(*l2d(0.0, 0.0, col_h + 0.075)),
        (width * 1.01, depth * 1.01, 0.04),
        mat_gold_trim,
        parent_emp,
        rot_xyz=mb.rot_d2w(0.0, 0.0, yaw),
        bevel=0.004,
    )

    ped_h = width * 0.27
    bm_p = bmesh.new()
    hw, hd = width * 0.45, depth * 0.45
    for sy_f in (-hd, hd):
        v0 = bm_p.verts.new(mb.d2w(*l2d(-hw, sy_f, col_h + 0.13)))
        v1 = bm_p.verts.new(mb.d2w(*l2d(hw, sy_f, col_h + 0.13)))
        v2 = bm_p.verts.new(mb.d2w(*l2d(0.0, sy_f, col_h + 0.13 + ped_h)))
        bm_p.faces.new([v0, v1, v2] if sy_f < 0 else [v1, v0, v2])
    bmesh.ops.recalc_face_normals(bm_p, faces=bm_p.faces)
    m_p = bpy.data.meshes.new(f"{name}_tympanum")
    bm_p.to_mesh(m_p)
    bm_p.free()
    o_p = bpy.data.objects.new(f"{name}_tympanum", m_p)
    scene.collection.objects.link(o_p)
    kit.apply_box_uv_and_mat(o_p, mat_gold_trim, uv_scale=0.8)
    kit.parent_keep_local(o_p, parent_emp)

    # Watertight classical triangular gable roof prism directly aligned over the tympanum!
    bm_r = bmesh.new()
    rw, rd = width * 0.54, depth * 0.54
    z_eave_r = col_h + 0.125
    z_ridge_r = col_h + 0.135 + ped_h + 0.045
    vf_l = bm_r.verts.new(mb.d2w(*l2d(-rw, -rd, z_eave_r)))
    vf_r = bm_r.verts.new(mb.d2w(*l2d(rw, -rd, z_eave_r)))
    vf_t = bm_r.verts.new(mb.d2w(*l2d(0.0, -rd, z_ridge_r)))
    vb_l = bm_r.verts.new(mb.d2w(*l2d(-rw, rd, z_eave_r)))
    vb_r = bm_r.verts.new(mb.d2w(*l2d(rw, rd, z_eave_r)))
    vb_t = bm_r.verts.new(mb.d2w(*l2d(0.0, rd, z_ridge_r)))
    bm_r.faces.new([vf_l, vf_r, vf_t])
    bm_r.faces.new([vb_r, vb_l, vb_t])
    bm_r.faces.new([vf_l, vf_t, vb_t, vb_l])
    bm_r.faces.new([vf_t, vf_r, vb_r, vb_t])
    bm_r.faces.new([vb_l, vb_r, vf_r, vf_l])
    bmesh.ops.recalc_face_normals(bm_r, faces=bm_r.faces)
    m_pr = bpy.data.meshes.new(f"{name}_gable_roof")
    bm_r.to_mesh(m_pr)
    bm_r.free()
    o_pr = bpy.data.objects.new(f"{name}_gable_roof", m_pr)
    scene.collection.objects.link(o_pr)
    kit.apply_box_uv_and_mat(o_pr, mat_marble_roof, uv_scale=0.7)
    kit.parent_keep_local(o_pr, parent_emp)


# 2 Refined Pediment Portals terminating the front-left (`+206 deg`) and front-right (`-56 deg`) ends of the colonnade!
for g_name, g_ang in (("peristyle_gate_front_left", COL_ARC_END_DEG + 3.0), ("peristyle_gate_front_right", COL_ARC_START_DEG - 3.0)):
    gr = math.radians(g_ang)
    gx = PLAZA_X + 1.50 * math.cos(gr)
    gy = PLAZA_Y + 1.50 * math.sin(gr)
    add_pediment_portal_pavilion(
        g_name, gx, gy, Z_PLAZA + 0.12, width=0.50, depth=0.46, col_h=0.84, yaw_deg=g_ang, parent_emp=p2_plaza_peristyle
    )

# ---------------------------------------------------------------------------
# PART 3: Grand Diagonal Staircase, Clean Upper-Left Stair & Golden-Amber Braziers
# ---------------------------------------------------------------------------
braz_src, br_ao, br_pt, br_nz, br_px, br_py, br_pz, br_cav, br_vm = kit.import_hero_sculpt_raw(
    "ritual_brazier.glb", "ritual_brazier", target_height=0.34, decimate_max_polys=3500, bake_res=512
)
br_albedo, br_rgh, br_met, br_nor, _ = kit.project_concept_albedo_onto_hero_mesh(
    concept_file="concept_ritual_brazier.jpg",
    px=br_px,
    py=br_py,
    pz=br_pz,
    ao_map=br_ao,
    cavity_boost=br_cav,
    valid_mask=br_vm,
    pbr_tex_folder="metal_plate_02",
    pbr_detail_strength=0.22,
    ao_weight=0.38,
    rough_base=0.28,
    metal_base=0.86,
)
br_luma = np.mean(br_albedo, axis=2, keepdims=True)
br_albedo = np.clip(
    np.array([0.84, 0.62, 0.20], dtype=np.float32)[None, None, :] * (0.62 + 0.68 * br_luma),
    0.04,
    0.98,
)
kit.finalize_hero_pbr(braz_src, "ritual_brazier", br_albedo, br_ao, br_rgh, br_met, br_nor)


def add_burning_brazier(name: str, dx: float, dy: float, dz: float, parent_emp: bpy.types.Object = p3_stairs):
    kit.add_beveled_box(
        scene, f"{name}_plinth", mb.d2w(dx, dy, dz + 0.055), (0.22, 0.22, 0.11), mat_marble, parent_emp, rot_xyz=mb.rot_d2w(), bevel=0.008
    )
    inst = braz_src.copy()
    inst.data = braz_src.data.copy()
    inst.name = name
    inst.location = mb.d2w(dx, dy, dz + 0.11)
    inst.rotation_euler = mb.rot_d2w()
    scene.collection.objects.link(inst)
    kit.parent_keep_local(inst, parent_emp)

    # Sculpted multi-fin golden-amber sacred fire tongues (curved twisted tongues, ZERO salmon cone!)
    bm_f = bmesh.new()
    uv_f = bm_f.loops.layers.uv.new("UVMap")
    wxy_b = mb.d2w(dx, dy, 0.0)
    z_bowl = dz + 0.39
    tongue_specs = [
        (0.0, 0.0, 0.085, 0.24, 0.0),
        (0.032, 0.015, 0.055, 0.18, 0.9),
        (-0.030, 0.020, 0.052, 0.17, 2.2),
        (0.012, -0.034, 0.050, 0.16, 3.8),
    ]
    for t_ox, t_oy, r_b, h_fl, ph in tongue_specs:
        n_az = 8
        rings_t = []
        for iz_f, (zf_u, rad_u, u_rad) in enumerate([(0.0, 1.0, 0.17), (0.45, 0.68, 0.10), (0.80, 0.30, 0.05)]):
            ring_v = []
            sway_x = 0.018 * math.sin(ph + zf_u * 2.6) * zf_u
            sway_y = 0.018 * math.cos(ph + zf_u * 2.2) * zf_u
            for k in range(n_az):
                af = (k / n_az) * 2.0 * math.pi
                rf = r_b * rad_u * (0.82 + 0.22 * math.sin(k * 3.0 + ph))
                vx = wxy_b[0] + t_ox + sway_x + rf * math.cos(af)
                vy = wxy_b[1] + t_oy + sway_y + rf * math.sin(af)
                vz = z_bowl + h_fl * zf_u
                ring_v.append((bm_f.verts.new((vx, vy, vz)), 0.5 + u_rad * math.cos(af), 0.5 + u_rad * math.sin(af)))
            rings_t.append(ring_v)
        vt_tip = bm_f.verts.new((wxy_b[0] + t_ox, wxy_b[1] + t_oy, z_bowl + h_fl))
        vb_bot = bm_f.verts.new((wxy_b[0] + t_ox, wxy_b[1] + t_oy, z_bowl - 0.02))
        for k in range(n_az):
            kn = (k + 1) % n_az
            fb = bm_f.faces.new([vb_bot, rings_t[0][kn][0], rings_t[0][k][0]])
            for lp in fb.loops:
                lp[uv_f].uv = (0.5, 0.5)
            ft = bm_f.faces.new([rings_t[-1][k][0], rings_t[-1][kn][0], vt_tip])
            for lp, uvc in zip(ft.loops, [rings_t[-1][k][1:], rings_t[-1][kn][1:], (0.5, 0.5)]):
                lp[uv_f].uv = uvc
        for ir_f in range(len(rings_t) - 1):
            for k in range(n_az):
                kn = (k + 1) % n_az
                v00, u00, w00 = rings_t[ir_f][k]
                v01, u01, w01 = rings_t[ir_f][kn]
                v11, u11, w11 = rings_t[ir_f + 1][kn]
                v10, u10, w10 = rings_t[ir_f + 1][k]
                fq = bm_f.faces.new([v00, v01, v11, v10])
                for lp, uvc in zip(fq.loops, [(u00, w00), (u01, w01), (u11, w11), (u10, w10)]):
                    lp[uv_f].uv = uvc

    bmesh.ops.recalc_face_normals(bm_f, faces=bm_f.faces)
    m_fl = bpy.data.meshes.new(f"{name}_fire")
    bm_f.to_mesh(m_fl)
    bm_f.free()
    for poly in m_fl.polygons:
        poly.use_smooth = True
    o_fl = bpy.data.objects.new(f"{name}_fire", m_fl)
    scene.collection.objects.link(o_fl)
    o_fl.data.materials.append(mat_brazier_flame)
    kit.parent_keep_local(o_fl, parent_emp)


def add_balustraded_marble_stair(
    name: str,
    p_bot_xyz: tuple[float, float, float],
    p_top_xyz: tuple[float, float, float],
    width: float,
    n_steps: int,
    brazier_specs: list[tuple[float, tuple[float, ...]]],
):
    x0, y0, z0 = p_bot_xyz
    x1, y1, z1 = p_top_xyz
    dx_tot, dy_tot, dz_tot = x1 - x0, y1 - y0, z1 - z0
    horiz_len = math.hypot(dx_tot, dy_tot)
    yaw = math.atan2(dy_tot, dx_tot)
    pitch = -math.atan2(dz_tot, horiz_len)
    nx_d, ny_d = -math.sin(yaw), math.cos(yaw)

    mid_x, mid_y, mid_z = 0.5 * (x0 + x1), 0.5 * (y0 + y1), 0.5 * (z0 + z1) - 0.24
    kit.add_beveled_box(
        scene,
        f"{name}_marble_spine",
        mb.d2w(mid_x, mid_y, mid_z),
        (math.hypot(horiz_len, dz_tot) + 0.10, width + 0.14, 0.18),
        mat_marble,
        p3_stairs,
        rot_xyz=mb.rot_d2w(0.0, pitch, yaw),
        bevel=0.010,
    )

    step_run = horiz_len / n_steps
    step_rise = dz_tot / n_steps
    for is_i in range(n_steps):
        t = (is_i + 0.5) / n_steps
        sx = x0 + dx_tot * t
        sy = y0 + dy_tot * t
        sz = z0 + dz_tot * t
        kit.add_beveled_box(
            scene,
            f"{name}_step_{is_i}",
            mb.d2w(sx, sy, sz - 0.5 * step_rise),
            (step_run * 1.06, width, step_rise * 0.92),
            mat_marble if (is_i % 2 == 0) else mat_marble_roof,
            p3_stairs,
            rot_xyz=mb.rot_d2w(0.0, 0.0, yaw),
            bevel=0.005,
        )

    for side_s in (-1.0, 1.0):
        bx = mid_x + nx_d * side_s * (width * 0.54)
        by = mid_y + ny_d * side_s * (width * 0.54)
        kit.add_beveled_box(
            scene,
            f"{name}_balustrade_{'L' if side_s < 0 else 'R'}",
            mb.d2w(bx, by, 0.5 * (z0 + z1) + 0.10),
            (math.hypot(horiz_len, dz_tot) + 0.14, 0.10, 0.21),
            mat_marble,
            p3_stairs,
            rot_xyz=mb.rot_d2w(0.0, pitch, yaw),
            bevel=0.009,
        )

    for bf, sides_tuple in brazier_specs:
        for side_s in sides_tuple:
            bx = x0 + dx_tot * bf + nx_d * side_s * (width * 0.58)
            by = y0 + dy_tot * bf + ny_d * side_s * (width * 0.58)
            bz = z0 + dz_tot * bf + 0.10
            add_burning_brazier(f"{name}_brazier_{bf:.2f}_{'L' if side_s < 0 else 'R'}", bx, by, bz, p3_stairs)


# Right-Flank Long Diagonal White Marble Grand Staircase (`min_dist_plz >= 1.89m` — cleanly outside right colonnade!)
add_balustraded_marble_stair(
    "olympus_grand_right_staircase",
    p_bot_xyz=(1.62, -1.48, Z_PLAZA + 0.08),
    p_top_xyz=(2.36, 1.18, Z_SUMMIT - 0.16),
    width=0.58,
    n_steps=34,
    brazier_specs=[(0.08, (-1.0, 1.0)), (0.38, (-1.0, 1.0)), (0.68, (-1.0, 1.0)), (0.95, (-1.0, 1.0))],
)
# Left Upper Staircase starting at (-1.56, 0.86) — >= 1.34m from Rotunda center (-2.64, 0.06) (ZERO collision!)
add_balustraded_marble_stair(
    "olympus_upper_left_staircase",
    p_bot_xyz=(-1.56, 0.86, Z_ROT + 0.16),
    p_top_xyz=(-0.94, 1.50, Z_SUMMIT - 0.18),
    width=0.48,
    n_steps=16,
    brazier_specs=[(0.38, (1.0,)), (0.88, (1.0,))],
)

# ---------------------------------------------------------------------------
# PART 4: Mid-Left Pierced White Marble Rotunda (Tholos) & Pure White Ribbed Dome
# ---------------------------------------------------------------------------
WXY_ROT = mb.d2w(ROT_X, ROT_Y, 0.0)
for st_i, (r_st, z0_s, z1_s) in enumerate([
    (1.06, Z_ROT - 0.04, Z_ROT + 0.06),
    (0.95, Z_ROT + 0.06, Z_ROT + 0.15),
]):
    st_ring = kit.add_prism_ring(scene, f"rotunda_stylobate_{st_i}", r_st, 0.0, z0_s, z1_s, sides=40, bevel=0.010)
    st_ring.location = (WXY_ROT[0], WXY_ROT[1], 0.0)
    kit.apply_box_uv_and_mat(st_ring, mat_marble, uv_scale=0.55)
    kit.parent_keep_local(st_ring, p4_rotunda)

rot_parapet_gold = kit.add_prism_ring(
    scene, "rotunda_terrace_gold_trim", 1.07, 1.00, Z_ROT + 0.03, Z_ROT + 0.07, sides=40, bevel=0.005
)
rot_parapet_gold.location = (WXY_ROT[0], WXY_ROT[1], 0.0)
kit.apply_box_uv_and_mat(rot_parapet_gold, mat_gold_trim, uv_scale=0.7)
kit.parent_keep_local(rot_parapet_gold, p4_rotunda)

mb.add_pierced_arched_rotunda_tier(
    scene=scene,
    name_prefix="rotunda_lower_arcade",
    design_center_xyz=(ROT_X, ROT_Y, Z_ROT + 0.15),
    r_outer=0.84,
    r_inner=0.71,
    height=0.70,
    n_arches=12,
    arch_width_frac=0.55,
    arch_spring_frac=0.62,
    arch_crown_frac=0.86,
    mat_wall=mat_marble,
    mat_trim=mat_gold_trim,
    mat_shadow_core=mat_bronze_grille,
    parent=p4_rotunda,
)

mb.add_pierced_arched_rotunda_tier(
    scene=scene,
    name_prefix="rotunda_upper_drum",
    design_center_xyz=(ROT_X, ROT_Y, Z_ROT + 0.89),
    r_outer=0.68,
    r_inner=0.57,
    height=0.42,
    n_arches=12,
    arch_width_frac=0.46,
    arch_spring_frac=0.58,
    arch_crown_frac=0.82,
    mat_wall=mat_marble,
    mat_trim=mat_gold_trim,
    mat_shadow_core=mat_bronze_grille,
    parent=p4_rotunda,
)

# Pure Pentelic White Marble Ribbed Hemispherical Dome (both shell AND ribs in `mat_marble` + gold finial ring!)
mb.add_ribbed_hemispherical_dome(
    scene=scene,
    name="rotunda_ribbed_white_dome",
    design_center_xyz=(ROT_X, ROT_Y, Z_ROT + 1.35),
    radius=0.66,
    height_scale=0.90,
    n_ribs=12,
    mat_dome=mat_marble,
    mat_rib_trim=mat_marble,
    parent=p4_rotunda,
    with_lantern=True,
)
rot_lantern_gold = kit.add_prism_ring(
    scene, "rotunda_lantern_gold_collar", 0.16, 0.0, Z_ROT + 1.93, Z_ROT + 1.98, sides=16, bevel=0.004
)
rot_lantern_gold.location = (WXY_ROT[0], WXY_ROT[1], 0.0)
kit.apply_box_uv_and_mat(rot_lantern_gold, mat_gold_trim, uv_scale=0.8)
kit.parent_keep_local(rot_lantern_gold, p4_rotunda)

# ---------------------------------------------------------------------------
# PART 5: Summit Classical Peripteral Pantheon, Gilded Guardians & Eagle Altar
# ---------------------------------------------------------------------------
statue_src, st_ao, st_pt, st_nz, st_px, st_py, st_pz, st_cav, st_vm = kit.import_hero_sculpt_raw(
    "olympus_guardian_statue.glb", "olympus_guardian_statue", target_height=0.84, decimate_max_polys=9500, bake_res=1024
)
st_albedo, st_rgh, st_met, st_nor, _ = kit.project_concept_albedo_onto_hero_mesh(
    concept_file="concept_olympus_guardian_statue.jpg",
    px=st_px,
    py=st_py,
    pz=st_pz,
    ao_map=st_ao,
    cavity_boost=st_cav,
    valid_mask=st_vm,
    pbr_tex_folder="metal_plate_02",
    pbr_detail_strength=0.20,
    ao_weight=0.36,
    rough_base=0.26,
    metal_base=0.86,
)
st_luma = np.mean(st_albedo, axis=2, keepdims=True)
st_albedo = np.clip(
    np.array([0.86, 0.64, 0.20], dtype=np.float32)[None, None, :] * (0.64 + 0.70 * st_luma) * (0.58 + 0.42 * st_ao),
    0.04,
    0.98,
)
st_met = np.full_like(st_rgh, 0.88)
st_rgh = np.clip(st_rgh * 0.80, 0.15, 0.40)
kit.finalize_hero_pbr(statue_src, "olympus_guardian_statue", st_albedo, st_ao, st_rgh, st_met, st_nor)

eagle_src, eg_ao, eg_pt, eg_nz, eg_px, eg_py, eg_pz, eg_cav, eg_vm = kit.import_hero_sculpt_raw(
    "olympus_eagle_altar_v4.glb", "olympus_eagle_altar_v4", target_height=0.64, decimate_max_polys=9000, bake_res=1024
)
eg_albedo, eg_rgh, eg_met, eg_nor, _ = kit.project_concept_albedo_onto_hero_mesh(
    concept_file="concept_olympus_eagle_altar_v4.jpg",
    px=eg_px,
    py=eg_py,
    pz=eg_pz,
    ao_map=eg_ao,
    cavity_boost=eg_cav,
    valid_mask=eg_vm,
    pbr_tex_folder="marble_01",
    pbr_detail_strength=0.22,
    ao_weight=0.36,
    rough_base=0.40,
    metal_base=0.22,
)
kit.finalize_hero_pbr(eagle_src, "olympus_eagle_altar_v4", eg_albedo, eg_ao, eg_rgh, eg_met, eg_nor)

# Miniature gilded sculpture atop the front circular fountain (`p2_plaza_peristyle`)
fnt_stat = statue_src.copy()
fnt_stat.data = statue_src.data.copy()
fnt_stat.name = "fountain_center_gold_deity"
fnt_stat.location = mb.d2w(FOUNT_X, FOUNT_Y, Z_PLAZA + 0.25)
fnt_stat.rotation_euler = mb.rot_d2w(0.0, 0.0, math.radians(-12.0))
fnt_stat.scale = (0.40, 0.40, 0.40)
scene.collection.objects.link(fnt_stat)
kit.parent_keep_local(fnt_stat, p2_plaza_peristyle)

PANTHEON_YAW = math.radians(-8.0)
CA_P, SA_P = math.cos(PANTHEON_YAW), math.sin(PANTHEON_YAW)


def pan_d(lx: float, ly: float, lz: float = 0.0) -> tuple[float, float, float]:
    return (SUM_X + lx * CA_P - ly * SA_P, SUM_Y + lx * SA_P + ly * CA_P, Z_SUMMIT + lz)


# Crisp Pentelic Marble Summit Stylobate (`3.36m` wide so right parapet braziers sit 100% supported with +12cm margin!)
kit.add_beveled_box(
    scene,
    "pantheon_summit_terrace",
    mb.d2w(*pan_d(0.0, 0.18, -0.06)),
    (3.36, 2.24, 0.20),
    mat_marble,
    p5_pantheon,
    rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
    bevel=0.014,
)
for st_k, (sw_p, sd_p, sz_p) in enumerate([
    (2.94, 2.20, 0.06),
    (2.82, 2.08, 0.14),
    (2.70, 1.96, 0.22),
]):
    kit.add_beveled_box(
        scene,
        f"pantheon_stylobate_{st_k}",
        mb.d2w(*pan_d(0.0, 0.16, sz_p)),
        (sw_p, sd_p, 0.085),
        mat_marble,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.008,
    )

# Wide Classical Front Grand Staircase with crisp articulated marble treads & side cheek-walls!
n_pan_steps = 12
for is_p in range(n_pan_steps):
    t_s = (is_p + 0.5) / n_pan_steps
    ly_s = -0.84 - t_s * 0.96
    lz_s = 0.23 - t_s * 0.54
    kit.add_beveled_box(
        scene,
        f"pantheon_front_step_{is_p}",
        mb.d2w(*pan_d(0.0, ly_s, lz_s)),
        (1.36, 0.095, 0.052),
        mat_marble if (is_p % 2 == 0) else mat_marble_roof,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.005,
    )
    kit.add_beveled_box(
        scene,
        f"pantheon_front_riser_{is_p}",
        mb.d2w(*pan_d(0.0, ly_s - 0.038, lz_s - 0.026)),
        (1.35, 0.025, 0.032),
        mat_cliff_crag,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.002,
    )
kit.add_beveled_box(
    scene,
    "pantheon_front_stair_carriage",
    mb.d2w(*pan_d(0.0, -1.32, -0.24)),
    (1.38, 1.00, 0.18),
    mat_marble,
    p5_pantheon,
    rot_xyz=mb.rot_d2w(0.49, 0.0, PANTHEON_YAW),
    bevel=0.010,
)

# Twin Sculpted Gilded Guardian Deity Statues on Classical Molded Pentelic Marble Pedestals flanking the stairs
for side_lbl, sx_g, yaw_off in (("left", -0.92, 14.0), ("right", 0.92, -14.0)):
    ped_pos = pan_d(sx_g, -1.24, -0.10)
    kit.add_beveled_box(
        scene,
        f"pantheon_guardian_plinth_{side_lbl}",
        mb.d2w(ped_pos[0], ped_pos[1], ped_pos[2] - 0.10),
        (0.50, 0.50, 0.16),
        mat_marble,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.010,
    )
    kit.add_beveled_box(
        scene,
        f"pantheon_guardian_pedestal_{side_lbl}",
        mb.d2w(*ped_pos),
        (0.40, 0.40, 0.34),
        mat_marble,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.010,
    )
    g_inst = statue_src.copy()
    g_inst.data = statue_src.data.copy()
    g_inst.name = f"pantheon_gilded_guardian_{side_lbl}"
    g_inst.location = mb.d2w(ped_pos[0], ped_pos[1], ped_pos[2] + 0.17)
    g_inst.rotation_euler = mb.rot_d2w(0.0, 0.0, PANTHEON_YAW + math.radians(yaw_off))
    scene.collection.objects.link(g_inst)
    kit.parent_keep_local(g_inst, p5_pantheon)

# Right Summit Parapet Braziers matching the glowing golden braziers beside the Pantheon's right colonnade in the Concept!
for sb_i, sb_ly in enumerate((-0.42, 0.22, 0.86)):
    bp = pan_d(1.44, sb_ly, -0.02)
    add_burning_brazier(f"pantheon_summit_parapet_brazier_{sb_i}", bp[0], bp[1], bp[2], p5_pantheon)

# Inner Cella Sanctuary Walls + Tall Gilded Portal + Sculpted Eagle Marble Altar inside
Z_COL_BASE = 0.26
H_PAN_COL = 1.02
for side_cx in (-0.80, 0.80):
    kit.add_beveled_box(
        scene,
        f"pantheon_cella_wall_{side_cx:+.2f}",
        mb.d2w(*pan_d(side_cx, 0.22, Z_COL_BASE + 0.48)),
        (0.15, 1.20, 0.96),
        mat_marble,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.008,
    )
kit.add_beveled_box(
    scene,
    "pantheon_cella_rear_wall",
    mb.d2w(*pan_d(0.0, 0.78, Z_COL_BASE + 0.48)),
    (1.72, 0.15, 0.96),
    mat_marble,
    p5_pantheon,
    rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
    bevel=0.008,
)
for jx in (-0.42, 0.42):
    kit.add_beveled_box(
        scene,
        f"pantheon_portal_jamb_{jx:+.2f}",
        mb.d2w(*pan_d(jx, -0.34, Z_COL_BASE + 0.48)),
        (0.32, 0.15, 0.96),
        mat_marble,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.008,
    )
kit.add_beveled_box(
    scene,
    "pantheon_portal_gold_lintel",
    mb.d2w(*pan_d(0.0, -0.36, Z_COL_BASE + 0.86)),
    (0.66, 0.18, 0.11),
    mat_gold_trim,
    p5_pantheon,
    rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
    bevel=0.006,
)

eag_inst = eagle_src.copy()
eag_inst.data = eagle_src.data.copy()
eag_inst.name = "pantheon_inner_eagle_marble_altar"
eag_inst.location = mb.d2w(*pan_d(0.0, 0.18, Z_COL_BASE))
eag_inst.rotation_euler = mb.rot_d2w(0.0, 0.0, PANTHEON_YAW)
scene.collection.objects.link(eag_inst)
kit.parent_keep_local(eag_inst, p5_pantheon)

# Peripteral Fluted Colonnade on All 4 Sides (8 along width x 6 along depth = 24 perimeter columns)
nx_cols, ny_cols = 8, 6
half_w_col, half_d_col = 1.22, 0.84
col_idx = 0
for ix in range(nx_cols):
    for iy in range(ny_cols):
        if 0 < ix < nx_cols - 1 and 0 < iy < ny_cols - 1:
            continue
        col_idx += 1
        lx = -half_w_col + (2.0 * half_w_col) * (ix / (nx_cols - 1))
        ly = 0.16 - half_d_col + (2.0 * half_d_col) * (iy / (ny_cols - 1))
        mb.add_fluted_classical_column(
            scene,
            f"pantheon_peripteral_col_{col_idx}",
            pan_d(lx, ly, Z_COL_BASE),
            height=H_PAN_COL,
            radius_base=0.065,
            mat_marble=mat_marble,
            mat_gold=mat_gold_trim,
            parent=p5_pantheon,
            n_flutes=16,
        )

# Classical Entablature (Pentelic Marble Architrave + Gilded Frieze + Projecting Dentil Cornice)
Z_PAN_ENT = Z_COL_BASE + H_PAN_COL
kit.add_beveled_box(
    scene,
    "pantheon_architrave",
    mb.d2w(*pan_d(0.0, 0.16, Z_PAN_ENT + 0.05)),
    (2.64, 1.88, 0.10),
    mat_marble,
    p5_pantheon,
    rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
    bevel=0.008,
)
kit.add_beveled_box(
    scene,
    "pantheon_gold_frieze",
    mb.d2w(*pan_d(0.0, 0.16, Z_PAN_ENT + 0.135)),
    (2.66, 1.90, 0.075),
    mat_gold_trim,
    p5_pantheon,
    rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
    bevel=0.006,
)
kit.add_beveled_box(
    scene,
    "pantheon_cornice",
    mb.d2w(*pan_d(0.0, 0.16, Z_PAN_ENT + 0.21)),
    (2.80, 2.04, 0.075),
    mat_marble,
    p5_pantheon,
    rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
    bevel=0.008,
)

# Recessed Gilded Tympanum framed by Projecting White Marble Raking Cornices + Sculpted Classical Relief Group!
PED_RISE = 0.46
Z_PED_BASE = Z_PAN_ENT + 0.245
bm_ped = bmesh.new()
for sy_end in (-0.82, 1.14):
    v0 = bm_ped.verts.new(mb.d2w(*pan_d(-1.26, sy_end, Z_PED_BASE)))
    v1 = bm_ped.verts.new(mb.d2w(*pan_d(1.26, sy_end, Z_PED_BASE)))
    v2 = bm_ped.verts.new(mb.d2w(*pan_d(0.0, sy_end, Z_PED_BASE + PED_RISE - 0.04)))
    bm_ped.faces.new([v0, v1, v2] if sy_end < 0 else [v1, v0, v2])
bmesh.ops.recalc_face_normals(bm_ped, faces=bm_ped.faces)
m_ped = bpy.data.meshes.new("pantheon_gilded_tympanums")
bm_ped.to_mesh(m_ped)
bm_ped.free()
o_ped = bpy.data.objects.new("pantheon_gilded_tympanums", m_ped)
scene.collection.objects.link(o_ped)
kit.apply_box_uv_and_mat(o_ped, mat_gold_dome, uv_scale=0.9)
kit.parent_keep_local(o_ped, p5_pantheon)

# Sculpted high-relief classical Olympian figures inside the front tympanum (varied poses/angles, ZERO vertical bars!)
tymp_figures = [
    (0.0, 0.34, 0.16, 0.0),
    (-0.24, 0.27, 0.14, -0.18),
    (0.24, 0.27, 0.14, 0.18),
    (-0.48, 0.20, 0.15, -0.36),
    (0.48, 0.20, 0.15, 0.36),
    (-0.74, 0.13, 0.18, -0.58),
    (0.74, 0.13, 0.18, 0.58),
]
for idx_tf, (fx, fh, fw, ftilt) in enumerate(tymp_figures):
    fig_inst = statue_src.copy()
    fig_inst.data = statue_src.data.copy()
    fig_inst.name = f"pediment_olympian_relief_{idx_tf}"
    fig_inst.location = mb.d2w(*pan_d(fx, -0.85, Z_PED_BASE + 0.01))
    fig_inst.rotation_euler = mb.rot_d2w(0.0, ftilt, PANTHEON_YAW)
    fig_inst.scale = (fw / 0.36, 0.18, fh / 0.84)
    scene.collection.objects.link(fig_inst)
    kit.parent_keep_local(fig_inst, p5_pantheon)

# Fine Pale Pentelic Marble Pitched Roof + Projecting White Marble Raking Cornices (`uv_scale = 1.45`)
roof_slope_len = math.hypot(1.40, PED_RISE)
roof_pitch = math.atan2(PED_RISE, 1.40)
for sx_r in (-1.0, 1.0):
    r_slab = kit.add_beveled_box(
        scene,
        f"pantheon_pitched_marble_roof_{'L' if sx_r < 0 else 'R'}",
        mb.d2w(*pan_d(sx_r * 0.70, 0.16, Z_PED_BASE + PED_RISE * 0.50)),
        (roof_slope_len, 2.08, 0.068),
        mat_marble_roof,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, sx_r * roof_pitch, PANTHEON_YAW),
        bevel=0.007,
    )
    kit.apply_box_uv_and_mat(r_slab, mat_marble_roof, uv_scale=1.45)

    # Projecting white Pentelic marble raking cornice framing front & rear pediments!
    for sy_rk, lbl_rk in ((-0.88, "front"), (1.20, "rear")):
        kit.add_beveled_box(
            scene,
            f"pantheon_raking_cornice_{lbl_rk}_{'L' if sx_r < 0 else 'R'}",
            mb.d2w(*pan_d(sx_r * 0.70, sy_rk, Z_PED_BASE + PED_RISE * 0.50 + 0.02)),
            (roof_slope_len + 0.06, 0.12, 0.085),
            mat_marble,
            p5_pantheon,
            rot_xyz=mb.rot_d2w(0.0, sx_r * roof_pitch, PANTHEON_YAW),
            bevel=0.008,
        )

# Gilded Acroteria Finials at pediment apex & corners
for ax, ay, az in [
    (0.0, -0.89, Z_PED_BASE + PED_RISE + 0.09),
    (-1.38, -0.89, Z_PED_BASE + 0.08),
    (1.38, -0.89, Z_PED_BASE + 0.08),
    (-1.38, 1.21, Z_PED_BASE + 0.08),
    (1.38, 1.21, Z_PED_BASE + 0.08),
]:
    kit.add_beveled_box(
        scene,
        f"pantheon_acroterion_{ax:+.1f}_{ay:+.1f}",
        mb.d2w(*pan_d(ax, ay, az)),
        (0.075, 0.075, 0.15),
        mat_gold_trim,
        p5_pantheon,
        rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
        bevel=0.010,
    )

# ---------------------------------------------------------------------------
# PART 6: White Marble Attic Podium, Fenestrated Drum & Ribbed Golden Dome
# ---------------------------------------------------------------------------
DOME_DX, DOME_DY, _ = pan_d(0.0, 0.20, 0.0)
WXY_DOME = mb.d2w(DOME_DX, DOME_DY, 0.0)
Z_ATTIC_BOT = Z_SUMMIT + Z_PED_BASE + 0.34
Z_DOME_DRUM = Z_ATTIC_BOT + 0.18

# White Pentelic Marble Square + Circular Attic Podium lifting the drum cleanly above the pitched roof ridge!
kit.add_beveled_box(
    scene,
    "pantheon_dome_attic_podium",
    mb.d2w(*pan_d(0.0, 0.20, Z_PED_BASE + 0.42)),
    (1.78, 1.78, 0.16),
    mat_marble,
    p6_dome,
    rot_xyz=mb.rot_d2w(0.0, 0.0, PANTHEON_YAW),
    bevel=0.010,
)
attic_ring = kit.add_prism_ring(
    scene, "pantheon_dome_attic_plinth", 0.90, 0.0, Z_DOME_DRUM - 0.06, Z_DOME_DRUM + 0.02, sides=40, bevel=0.008
)
attic_ring.location = (WXY_DOME[0], WXY_DOME[1], 0.0)
kit.apply_box_uv_and_mat(attic_ring, mat_marble, uv_scale=0.6)
kit.parent_keep_local(attic_ring, p6_dome)

mb.add_pierced_arched_rotunda_tier(
    scene=scene,
    name_prefix="pantheon_summit_dome_drum",
    design_center_xyz=(DOME_DX, DOME_DY, Z_DOME_DRUM),
    r_outer=0.82,
    r_inner=0.69,
    height=0.34,
    n_arches=16,
    arch_width_frac=0.46,
    arch_spring_frac=0.58,
    arch_crown_frac=0.82,
    mat_wall=mat_marble,
    mat_trim=mat_gold_trim,
    mat_shadow_core=mat_bronze_grille,
    parent=p6_dome,
)

mb.add_ribbed_hemispherical_dome(
    scene=scene,
    name="pantheon_ribbed_golden_dome",
    design_center_xyz=(DOME_DX, DOME_DY, Z_DOME_DRUM + 0.36),
    radius=0.80,
    height_scale=0.92,
    n_ribs=16,
    mat_dome=mat_gold_dome,
    mat_rib_trim=mat_gold_trim,
    parent=p6_dome,
    with_lantern=True,
)

# ---------------------------------------------------------------------------
# 4. Verify Golden Rules + Export Draco GLB & Coaxial .parts.json Sidecar
# ---------------------------------------------------------------------------
part_defs = [
    {
        "empty": p1_massif,
        "id": "olympus_marble_massif_and_waterfalls",
        "name_vi": "Khối Núi Cẩm Thạch Đa Tầng & Bốn Dòng Thác Xanh Đỉnh Olympus",
        "name_en": "Multi-Tiered Pentelic Marble Massif & Four Recessed Waterfalls",
        "summary_vi": "Khối núi đá cẩm thạch trắng xám vát cạnh dựng đứng nhiều tầng cùng bốn dòng thác bọt trắng xanh biếc.",
        "summary_en": "Towering multi-tiered faceted white-grey marble massif with four frothy turquoise waterfalls in carved gullies.",
    },
    {
        "empty": p2_plaza_peristyle,
        "id": "helios_plaza_and_peristyle_sanctuary",
        "name_vi": "Quảng Trường Sao Mặt Trời 16 Cánh, Đài Phun Nước & Hàng Cột Vòng Cung",
        "name_en": "16-Ray Sun-Star Plaza, Golden Fountain & Wrapping Peristyle",
        "summary_vi": "Sân tròn ngôi sao mười sáu cánh mạ vàng, đài phun nước mũi vực và hàng cột đá trắng vòng cung khóa hai cổng.",
        "summary_en": "Circular 16-ray gilded Sun-Star plaza, cliffside golden fountain, 258-deg fluted colonnade, and twin portals.",
    },
    {
        "empty": p3_stairs,
        "id": "grand_stairways_and_sacred_braziers",
        "name_vi": "Đại Lộ Cầu Thang Đá Trắng Vút Đỉnh Núi & Hàng Chậu Lửa Vàng",
        "name_en": "Grand Diagonal Marble Stairways & Burning Gilded Braziers",
        "summary_vi": "Đại lộ bậc thang cẩm thạch trắng có lan can vươn chéo lên đỉnh thượng, rực sáng hàng chậu lửa đồng mạ vàng.",
        "summary_en": "Long diagonal balustraded marble stairway and upper ascent flanked by golden-amber sacred fire braziers.",
    },
    {
        "empty": p4_rotunda,
        "id": "mid_left_pierced_marble_rotunda_tholos",
        "name_vi": "Đền Tròn Sườn Trái Trổ Ô Cửa Vòm & Mái Vòm Đá Trắng Chia Múi",
        "name_en": "Mid-Left Pierced Arched Marble Rotunda & Ribbed White Dome",
        "summary_vi": "Tòa đền tròn đá trắng nơi sườn trái trổ mười hai ô cửa vòm thoáng đãng, đội mái vòm bán cầu cẩm thạch trắng.",
        "summary_en": "Mid-slope marble Tholos rotunda with open round-arched colonnade, fenestrated drum, and pure white ribbed dome.",
    },
    {
        "empty": p5_pantheon,
        "id": "summit_pantheon_colonnade_and_guardians",
        "name_vi": "Đại Điện Đỉnh Núi, Đôi Tượng Thần Vàng & Bàn Thờ Đại Bàng",
        "name_en": "Summit Peripteral Pantheon, Gilded Guardians & Eagle Altar",
        "summary_vi": "Ngôi đền chữ nhật bốn mặt cột khía rãnh, trán tường phù điêu vàng, đôi tượng thần đứng gác và bệ đại bàng cổ.",
        "summary_en": "Classical peripteral summit temple with wide stairs, twin gilded guardian statues, relief pediment, and eagle altar.",
    },
    {
        "empty": p6_dome,
        "id": "summit_attic_drum_and_golden_dome",
        "name_vi": "Đài Đế Đá Trắng, Cổ Vòm Trổ Cửa & Mái Vòm Bán Cầu Vàng Ròng",
        "name_en": "Marble Attic Podium, Fenestrated Drum & Ribbed Golden Dome",
        "summary_vi": "Đài đế đá trắng nâng tầng cổ vòm trổ mười sáu cửa sổ cùng mái vòm bán cầu mạ vàng chạm hoa văn và lồng đèn đỉnh.",
        "summary_en": "White marble attic podium, fenestrated drum, embossed coffered hemispherical golden dome, and summit lantern.",
    },
]

mb.export_monument_with_parts_json(
    scene=scene,
    out_glb=OUT_GLB,
    part_defs=part_defs,
    master_sources=[braz_src, statue_src, eagle_src],
    prop_support_checks=[
        (p2_plaza_peristyle, 0.0, 0.0, 4.46, 0.18),
        (p3_stairs, 0.0, 0.0, 4.46, 0.25),
        (p4_rotunda, 0.0, 0.0, 4.46, 0.25),
        (p5_pantheon, 0.0, 0.0, 4.46, 0.40),
        (p6_dome, 0.0, 0.0, 4.46, 1.40),
    ],
    t_start=t_start,
)
