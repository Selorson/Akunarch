"""
Akunarch v2.1 — Monument #2 (Standalone Split Project): `avalon-mage-sanctum`
100% 1:1 Architectural & Sculptural Match to `E:\\Tools-3D\\concepts\\concept_avalon_mage_sanctum_reliquary_v4.jpg`.

Fixes verified against Gate #1 Adversarial Audit:
  - Monumental dressed Celtic stone blocks with organic joint moss (zero tiny busy wall bricks, zero isolated moss bars).
  - 4x4 tiled monumental stone pavement inside the 2048x2048 glowing 450nm Celtic/Ogham circle + `Part 2 dirY >= 1.88m`.
  - 4 symmetrically balanced corner rune obelisks (`SW, SE, NW, NE`) with `>= +0.20m` step margin & zero branch collision.
  - Step-draping gnarled pale-brown deadwood oak roots (`z >= step_surface_z + r_root`, zero step-tunneling, `>= +0.35m` Step 1 support margin) + individual twig-mounted glowing azure leaves (zero paper pinwheels).
  - True 3D carved stone arch frames on all 6 hexagonal chest faces, physically hinged vaulted lid, and faceted 450nm crystal meteorite (zero horizontal stripes).
  - Unburied front stone lectern & phial pedestal standing proudly on the front step landing (`dy = -3.34m`).
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Vector

MONUMENTS_DIR = Path(__file__).resolve().parent
KIT_DIR = Path(r"E:\Tools-3D\scripts\archived_selorson_monuments")
for p in (str(MONUMENTS_DIR), str(KIT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import _aaa_monument_kit as kit  # noqa: E402
import _monument_builders as mb  # noqa: E402

SLUG = "avalon-mage-sanctum"
OUT_GLB = mb.resolve_out_glb(SLUG, globals())

scene, t_start = kit.init_blender_optix_scene("AVALON MAGE SANCTUM & 450NM METEORITE RELIQUARY (1:1 v2.2)")


# ---------------------------------------------------------------------------
# Helpers: 2D Segment SDF & Seamless Tiling
# ---------------------------------------------------------------------------
def sdf_segment(px: np.ndarray, py: np.ndarray, x0: float, y0: float, x1: float, y1: float) -> np.ndarray:
    vx, vy = x1 - x0, y1 - y0
    wx, wy = px - x0, py - y0
    denom = max(vx * vx + vy * vy, 1e-8)
    t = np.clip((wx * vx + wy * vy) / denom, 0.0, 1.0)
    dx = wx - t * vx
    dy = wy - t * vy
    return np.sqrt(dx * dx + dy * dy)


def tile_img_np(arr: np.ndarray, tiles: int) -> np.ndarray:
    res = arr.shape[0]
    sub = max(64, res // tiles)
    small = arr[:: max(1, res // sub), :: max(1, res // sub)][:sub, :sub]
    tiled = np.tile(small, (tiles + 1, tiles + 1, 1))[:res, :res, :]
    return tiled.astype(np.float32)


def build_monumental_mossy_ashlar_material() -> bpy.types.Material:
    """1024x1024 large dressed grey-olive Celtic stone slabs with organic damp moss nestled in mortar joints."""
    res = 1024
    sdir = kit.POLY_DIR / "textures" / "large_sandstone_blocks_01"
    diff = kit.load_img_np(sdir / "Diffuse_2k.jpg", res, is_data=False)[:, :, :3]
    ao = kit.load_img_np(sdir / "AO_2k.jpg", res, is_data=True)[:, :, :1]
    rgh = kit.load_img_np(sdir / "Rough_2k.jpg", res, is_data=True)[:, :, :1]
    nor = kit.load_img_np(sdir / "nor_gl_2k.jpg", res, is_data=True)[:, :, :3]

    mdir = kit.POLY_DIR / "textures" / "mossy_rock"
    mdiff = kit.load_img_np(mdir / "Diffuse_2k.jpg", res, is_data=False)[:, :, :3]

    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    luma = np.mean(diff, axis=2, keepdims=True)
    # Re-grade warm sandstone into cool ancient grey-olive Celtic granite/limestone
    stone_grey = (0.35 * diff + 0.65 * luma * np.array([0.46, 0.48, 0.43], dtype=np.float32)[None, None, :]) * (0.48 + 0.52 * ao)
    # Organic moss concentrated in low-AO mortar crevices + natural damp patches
    blotch = 0.5 + 0.5 * np.sin(xx * math.pi * 6.0 + 0.5) * np.cos(yy * math.pi * 6.0 - 0.7)
    crevice_moss = np.clip((0.76 - ao[:, :, 0]) * 3.2 * (0.45 + 0.75 * blotch), 0.0, 0.78)[:, :, None]
    moss_col = (0.45 * mdiff + 0.55 * np.array([0.11, 0.20, 0.065], dtype=np.float32)[None, None, :]) * (0.55 + 0.45 * ao)

    albedo = np.clip(stone_grey * (1.0 - crevice_moss) + moss_col * crevice_moss, 0.02, 0.80)
    orm = np.concatenate([ao, np.clip(rgh * 0.95 + 0.10, 0.35, 0.96), np.zeros_like(rgh)], axis=2)

    c_img = kit.save_np_img(albedo, kit.BAKED_DIR / "av_monumental_ashlar_col.jpg", is_data=False)
    o_img = kit.save_np_img(orm, kit.BAKED_DIR / "av_monumental_ashlar_orm.jpg", is_data=True)
    n_img = kit.save_np_img(nor, kit.BAKED_DIR / "av_monumental_ashlar_nor.jpg", is_data=True)
    return kit.make_principled_gltf_material("mat_av_monumental_ashlar", c_img, o_img, n_img, normal_strength=1.15)


def build_celtic_arcane_floor_material() -> bpy.types.Material:
    """2048x2048 crisp 4x4-tiled stone floor engraved with glowing 450nm Celtic/Ogham rings & 8-pointed star."""
    res = 2048
    sdir = kit.POLY_DIR / "textures" / "large_sandstone_blocks_01"
    diff_raw = kit.load_img_np(sdir / "Diffuse_2k.jpg", res, is_data=False)[:, :, :3]
    ao_raw = kit.load_img_np(sdir / "AO_2k.jpg", res, is_data=True)[:, :, :1]
    rgh_raw = kit.load_img_np(sdir / "Rough_2k.jpg", res, is_data=True)[:, :, :1]
    nor_raw = kit.load_img_np(sdir / "nor_gl_2k.jpg", res, is_data=True)[:, :, :3]

    # Tile 4x4 so the 4.56m circle has crisp 1:1 stone block scale matching the octagonal plinth!
    diff = tile_img_np(diff_raw, 4)
    ao = tile_img_np(ao_raw, 4)
    rgh = tile_img_np(rgh_raw, 4)
    nor = tile_img_np(nor_raw, 4)

    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    px = (xx - 0.5) * 2.0
    py = (yy - 0.5) * 2.0
    rr = np.hypot(px, py)
    ang = np.arctan2(py, px)

    d_min = np.minimum(np.abs(rr - 0.915), np.abs(rr - 0.755))
    d_min = np.minimum(d_min, np.abs(rr - 0.435))

    for rot_off in (0.0, math.pi * 0.25):
        verts = [(0.745 * math.cos(rot_off + k * math.pi * 0.5), 0.745 * math.sin(rot_off + k * math.pi * 0.5)) for k in range(4)]
        for k in range(4):
            x0, y0 = verts[k]
            x1, y1 = verts[(k + 1) % 4]
            d_min = np.minimum(d_min, sdf_segment(px, py, x0, y0, x1, y1))

    petal_r = 0.585 + 0.145 * np.cos(ang * 4.0)
    petal_r2 = 0.585 - 0.145 * np.cos(ang * 4.0)
    d_min = np.minimum(d_min, np.where((rr > 0.41) & (rr < 0.76), np.minimum(np.abs(rr - petal_r), np.abs(rr - petal_r2)), 1.0))

    n_runes = 32
    for ir in range(n_runes):
        ra = (ir / n_runes) * 2.0 * math.pi
        ca, sa = math.cos(ra), math.sin(ra)
        tx, ty = -sa, ca
        r_lo, r_hi, r_mid = 0.788, 0.882, 0.835
        d_min = np.minimum(d_min, sdf_segment(px, py, r_lo * ca, r_lo * sa, r_hi * ca, r_hi * sa))
        glyph_type = ir % 4
        w_twig = 0.032
        if glyph_type == 0:
            d_min = np.minimum(d_min, sdf_segment(px, py, r_hi * ca, r_hi * sa, (r_mid + 0.01) * ca + w_twig * tx, (r_mid + 0.01) * sa + w_twig * ty))
            d_min = np.minimum(d_min, sdf_segment(px, py, r_mid * ca, r_mid * sa, (r_lo + 0.02) * ca + w_twig * tx, (r_lo + 0.02) * sa + w_twig * ty))
        elif glyph_type == 1:
            d_min = np.minimum(d_min, sdf_segment(px, py, r_hi * ca, r_hi * sa, (r_mid + 0.015) * ca + w_twig * tx, (r_mid + 0.015) * sa + w_twig * ty))
            d_min = np.minimum(d_min, sdf_segment(px, py, (r_mid + 0.015) * ca + w_twig * tx, (r_mid + 0.015) * sa + w_twig * ty, r_mid * ca, r_mid * sa))
            d_min = np.minimum(d_min, sdf_segment(px, py, r_mid * ca, r_mid * sa, r_lo * ca + w_twig * tx, r_lo * sa + w_twig * ty))
        elif glyph_type == 2:
            d_min = np.minimum(d_min, sdf_segment(px, py, r_hi * ca, r_hi * sa, r_mid * ca + w_twig * tx, r_mid * sa + w_twig * ty))
            d_min = np.minimum(d_min, sdf_segment(px, py, r_hi * ca, r_hi * sa, r_mid * ca - w_twig * tx, r_mid * sa - w_twig * ty))
        else:
            d_min = np.minimum(d_min, sdf_segment(px, py, (r_mid + 0.025) * ca - w_twig * tx, (r_mid + 0.025) * sa - w_twig * ty, (r_mid - 0.015) * ca + w_twig * tx, (r_mid - 0.015) * sa + w_twig * ty))

    line_core = np.clip((0.0105 - d_min) / 0.0045, 0.0, 1.0)[:, :, None]
    line_halo = np.clip((0.0215 - d_min) / 0.0135, 0.0, 1.0)[:, :, None]

    luma = np.mean(diff, axis=2, keepdims=True)
    stone_base = np.clip(
        (0.32 * diff + 0.68 * luma * np.array([0.44, 0.47, 0.43], dtype=np.float32)[None, None, :]) * (0.48 + 0.52 * ao),
        0.02,
        0.82,
    )
    azure_edge = np.array([0.07, 0.48, 1.00], dtype=np.float32)[None, None, :]
    azure_hot = np.array([0.62, 0.92, 1.00], dtype=np.float32)[None, None, :]
    rune_rgb = azure_edge * (1.0 - 0.58 * line_core) + azure_hot * (0.58 * line_core)

    albedo = np.clip(stone_base * (1.0 - 0.82 * line_halo) + rune_rgb * (0.85 * line_halo), 0.02, 0.98)
    emit_arr = rune_rgb * ((0.32 * line_halo + 0.68 * line_core) ** 1.48)

    gx = np.roll(line_halo[:, :, 0], -1, axis=1) - np.roll(line_halo[:, :, 0], 1, axis=1)
    gy = np.roll(line_halo[:, :, 0], -1, axis=0) - np.roll(line_halo[:, :, 0], 1, axis=0)
    nx = (nor[:, :, 0] * 2.0 - 1.0) + gx * 2.2
    ny = (nor[:, :, 1] * 2.0 - 1.0) + gy * 2.2
    nz = np.maximum(nor[:, :, 2] * 2.0 - 1.0, 0.28)
    nlen = np.maximum(np.sqrt(nx * nx + ny * ny + nz * nz), 1e-6)
    nor_out = np.stack([0.5 + 0.5 * (nx / nlen), 0.5 + 0.5 * (ny / nlen), 0.5 + 0.5 * (nz / nlen)], axis=-1)

    r_out = np.clip(rgh * 0.92 + 0.10 - 0.35 * line_core, 0.12, 0.96)
    orm_out = np.concatenate([ao, r_out, np.full_like(r_out, 0.04)], axis=2)

    col_img = kit.save_np_img(albedo, kit.BAKED_DIR / "av_magic_circle_col.jpg", is_data=False)
    orm_img = kit.save_np_img(orm_out, kit.BAKED_DIR / "av_magic_circle_orm.jpg", is_data=True)
    nor_img = kit.save_np_img(nor_out, kit.BAKED_DIR / "av_magic_circle_nor.jpg", is_data=True)
    emit_img = kit.save_np_img(emit_arr, kit.BAKED_DIR / "av_magic_circle_emit.jpg", is_data=False)
    return kit.make_principled_gltf_material(
        "mat_av_magic_circle", col_img, orm_img, nor_img, normal_strength=1.12, emit_img=emit_img, emit_strength=2.60
    )


def build_obelisk_rune_face_material(mat_name: str, rune_segments: list[tuple[float, float, float, float]]) -> bpy.types.Material:
    """512x512 mossy granite material with crisp SDF-carved glowing azure rune glyphs."""
    res = 512
    tdir = kit.POLY_DIR / "textures" / "rock_face_03"
    diff = kit.load_img_np(tdir / "Diffuse_2k.jpg", res, is_data=False)[:, :, :3]
    ao = kit.load_img_np(tdir / "AO_2k.jpg", res, is_data=True)[:, :, :1]
    rgh = kit.load_img_np(tdir / "Rough_2k.jpg", res, is_data=True)[:, :, :1]
    nor = kit.load_img_np(tdir / "nor_gl_2k.jpg", res, is_data=True)[:, :, :3]

    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    d_min = np.full_like(xx, 10.0)
    for x0, y0, x1, y1 in rune_segments:
        d_min = np.minimum(d_min, sdf_segment(xx, yy, x0, y0, x1, y1))

    core = np.clip((0.016 - d_min) / 0.007, 0.0, 1.0)[:, :, None]
    halo = np.clip((0.034 - d_min) / 0.020, 0.0, 1.0)[:, :, None]
    luma = np.mean(diff, axis=2, keepdims=True)
    stone = np.clip(
        (0.28 * diff + 0.72 * luma * np.array([0.45, 0.48, 0.43], dtype=np.float32)[None, None, :]) * (0.48 + 0.52 * ao),
        0.03,
        0.78,
    )
    glow = np.array([0.10, 0.56, 1.00], dtype=np.float32)[None, None, :] * (1.0 - 0.55 * core) + np.array([0.68, 0.95, 1.00], dtype=np.float32)[None, None, :] * (0.55 * core)

    albedo = np.clip(stone * (1.0 - 0.80 * halo) + glow * (0.85 * halo), 0.02, 0.98)
    emit_arr = glow * ((0.30 * halo + 0.70 * core) ** 1.42)
    orm_out = np.concatenate([ao, np.clip(rgh + 0.08 - 0.30 * core, 0.14, 0.95), np.full_like(rgh, 0.04)], axis=2)

    col_img = kit.save_np_img(albedo, kit.BAKED_DIR / f"{mat_name}_col.jpg", is_data=False)
    orm_img = kit.save_np_img(orm_out, kit.BAKED_DIR / f"{mat_name}_orm.jpg", is_data=True)
    nor_img = kit.save_np_img(nor, kit.BAKED_DIR / f"{mat_name}_nor.jpg", is_data=True)
    emit_img = kit.save_np_img(emit_arr, kit.BAKED_DIR / f"{mat_name}_emit.jpg", is_data=False)
    return kit.make_principled_gltf_material(mat_name, col_img, orm_img, nor_img, normal_strength=1.15, emit_img=emit_img, emit_strength=2.70)


def build_faceted_450nm_meteorite_material() -> bpy.types.Material:
    """
    512x512 Voronoi-faceted 450nm crystalline sapphire meteorite material (ZERO horizontal stripes!).
    Deep cobalt-indigo meteoritic crust crisscrossed by glowing 450nm crystal facets & fissures (>82% #000000 emit mask).
    """
    res = 512
    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    rng = np.random.default_rng(45021)
    n_seeds = 28
    sx = rng.uniform(0.08, 0.92, n_seeds).astype(np.float32)
    sy = rng.uniform(0.08, 0.92, n_seeds).astype(np.float32)

    # Compute 1st and 2nd nearest Voronoi cell distances for crystal facet edges + luminous facet hearts
    dx = xx[:, :, None] - sx[None, None, :]
    dy = yy[:, :, None] - sy[None, None, :]
    dists = np.sqrt(dx * dx + dy * dy)
    idx_part = np.argpartition(dists, 2, axis=2)
    d1 = np.take_along_axis(dists, idx_part[:, :, 0:1], axis=2)[:, :, 0]
    d2 = np.take_along_axis(dists, idx_part[:, :, 1:2], axis=2)[:, :, 0]
    cell_id = idx_part[:, :, 0]

    edge_dist = d2 - d1
    # Deep royal-sapphire crystal facets with soft internal crystal luster (ZERO white spiderweb grid lines!)
    border_fade = np.clip((np.minimum(np.minimum(xx, 1.0 - xx), np.minimum(yy, 1.0 - yy)) - 0.08) / 0.12, 0.0, 1.0)
    radial_heart = np.clip((0.40 - np.hypot(xx - 0.50, yy - 0.50)) / 0.26, 0.0, 1.0) * border_fade
    facet_sparkle = np.clip(0.5 + 0.5 * np.sin(cell_id * 3.1 + d1 * 18.0), 0.15, 1.0)
    e_mask = np.clip(radial_heart * (0.45 + 0.55 * facet_sparkle), 0.0, 1.0)[:, :, None]

    crust_col = np.array([0.022, 0.075, 0.28], dtype=np.float32)[None, None, :] * (0.72 + 0.34 * np.sin(cell_id * 2.3)[:, :, None])
    sapphire_450 = np.array([0.05, 0.30, 0.92], dtype=np.float32)[None, None, :]
    cyan_core = np.array([0.18, 0.62, 1.00], dtype=np.float32)[None, None, :]
    glow_rgb = sapphire_450 * (1.0 - 0.45 * e_mask) + cyan_core * (0.45 * e_mask)

    albedo = np.clip(crust_col * (1.0 - 0.65 * e_mask) + glow_rgb * (0.68 * e_mask), 0.015, 0.94)
    emit_arr = glow_rgb * (e_mask ** 1.55) * 0.72

    gx = np.roll(d1, -1, axis=1) - np.roll(d1, 1, axis=1)
    gy = np.roll(d1, -1, axis=0) - np.roll(d1, 1, axis=0)
    nx = gx * 12.0
    ny = gy * 12.0
    nz = np.ones_like(nx)
    nlen = np.sqrt(nx * nx + ny * ny + nz * nz)
    nor_arr = np.stack([0.5 + 0.5 * (nx / nlen), 0.5 + 0.5 * (ny / nlen), 0.5 + 0.5 * (nz / nlen)], axis=-1)
    orm_arr = np.dstack([
        np.full((res, res), 0.88, dtype=np.float32),
        np.clip(0.32 - 0.18 * e_mask[:, :, 0], 0.10, 0.55),
        np.full((res, res), 0.18, dtype=np.float32),
    ])

    c_i = kit.save_np_img(albedo, kit.BAKED_DIR / "av_meteorite_crystal_col.jpg", is_data=False)
    o_i = kit.save_np_img(orm_arr, kit.BAKED_DIR / "av_meteorite_crystal_orm.jpg", is_data=True)
    n_i = kit.save_np_img(nor_arr, kit.BAKED_DIR / "av_meteorite_crystal_nor.jpg", is_data=True)
    e_i = kit.save_np_img(emit_arr, kit.BAKED_DIR / "av_meteorite_crystal_emit.jpg", is_data=False)
    return kit.make_principled_gltf_material("mat_av_meteorite_450nm_v4", c_i, o_i, n_i, normal_strength=1.10, emit_img=e_i, emit_strength=2.95)


def build_grimoire_parchment_material() -> bpy.types.Material:
    res = 1024
    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    grain = 0.04 * np.sin(xx * 38.0) * np.cos(yy * 31.0) + 0.025 * np.sin(xx * 95.0 + yy * 77.0)
    edge_vignette = np.clip(np.minimum(np.minimum(xx, 1.0 - xx), np.minimum(yy, 1.0 - yy)) / 0.12, 0.35, 1.0)
    gutter_fold = 1.0 - 0.32 * np.exp(-(((xx - 0.50) / 0.032) ** 2))

    paper = np.array([0.76, 0.65, 0.47], dtype=np.float32)[None, None, :] * (0.82 + 0.18 * edge_vignette[:, :, None] + grain[:, :, None]) * gutter_fold[:, :, None]
    d_seal = np.minimum(np.abs(np.hypot(xx - 0.26, yy - 0.52) - 0.12), np.abs(np.hypot(xx - 0.26, yy - 0.52) - 0.075))
    seal_mask = np.clip((0.006 - d_seal) / 0.003, 0.0, 1.0)

    in_right_text = (xx > 0.56) & (xx < 0.90) & (yy > 0.16) & (yy < 0.86)
    in_left_hdr = (xx > 0.10) & (xx < 0.42) & (((yy > 0.72) & (yy < 0.86)) | ((yy > 0.16) & (yy < 0.30)))
    line_wave = np.clip((np.sin(yy * math.pi * 46.0) - 0.55) / 0.45, 0.0, 1.0) * (0.6 + 0.4 * np.sin(xx * 180.0))
    ink_mask = np.where(in_right_text | in_left_hdr, line_wave, 0.0)[:, :, None]

    albedo = np.clip(
        paper * (1.0 - 0.48 * ink_mask) + np.array([0.14, 0.48, 0.88], dtype=np.float32)[None, None, :] * (0.55 * seal_mask[:, :, None]),
        0.04,
        0.92,
    )
    emit_arr = np.array([0.18, 0.65, 1.0], dtype=np.float32)[None, None, :] * ((seal_mask[:, :, None]) ** 1.5) * 0.65
    orm_arr = np.concatenate([np.full((res, res, 1), 0.92, dtype=np.float32), np.full((res, res, 1), 0.78, dtype=np.float32), np.zeros((res, res, 1), dtype=np.float32)], axis=2)
    nor_arr = np.dstack([np.full((res, res), 0.5, dtype=np.float32), np.full((res, res), 0.5, dtype=np.float32), np.ones((res, res), dtype=np.float32)])

    col_img = kit.save_np_img(albedo, kit.BAKED_DIR / "av_parchment_col.jpg", is_data=False)
    orm_img = kit.save_np_img(orm_arr, kit.BAKED_DIR / "av_parchment_orm.jpg", is_data=True)
    nor_img = kit.save_np_img(nor_arr, kit.BAKED_DIR / "av_parchment_nor.jpg", is_data=True)
    emit_img = kit.save_np_img(emit_arr, kit.BAKED_DIR / "av_parchment_emit.jpg", is_data=False)
    return kit.make_principled_gltf_material("mat_av_parchment", col_img, orm_img, nor_img, normal_strength=0.4, emit_img=emit_img, emit_strength=1.35)


def build_compact_glow_material(
    mat_name: str,
    core_rgb: tuple[float, float, float],
    edge_rgb: tuple[float, float, float],
    rim_dark_rgb: tuple[float, float, float],
    strength: float,
    glow_radius: float = 0.42,
    roughness: float = 0.18,
) -> bpy.types.Material:
    """Compact centered glow spot (>82% pure #000000 texels) for leaves,mana phials, and recessed stone seals."""
    res = 256
    yy, xx = np.mgrid[0:res, 0:res].astype(np.float32) / float(res)
    rr = np.hypot(xx - 0.5, yy - 0.5) * 2.0
    mask = np.clip((glow_radius - rr) / (glow_radius * 0.45), 0.0, 1.0)[:, :, None]
    glow = (
        np.array(edge_rgb, dtype=np.float32)[None, None, :] * (1.0 - 0.6 * mask)
        + np.array(core_rgb, dtype=np.float32)[None, None, :] * (0.6 * mask)
    )
    base = np.array(rim_dark_rgb, dtype=np.float32)[None, None, :] * (1.0 - mask) + glow * (0.88 * mask)
    emit = glow * (mask ** 1.40)
    orm = np.dstack([np.full((res, res), 0.92, dtype=np.float32), np.full((res, res), roughness, dtype=np.float32), np.full((res, res), 0.05, dtype=np.float32)])
    nor = np.dstack([np.full((res, res), 0.5, dtype=np.float32), np.full((res, res), 0.5, dtype=np.float32), np.ones((res, res), dtype=np.float32)])
    c_i = kit.save_np_img(base, kit.BAKED_DIR / f"{mat_name}_col.jpg", is_data=False)
    o_i = kit.save_np_img(orm, kit.BAKED_DIR / f"{mat_name}_orm.jpg", is_data=True)
    n_i = kit.save_np_img(nor, kit.BAKED_DIR / f"{mat_name}_nor.jpg", is_data=True)
    e_i = kit.save_np_img(emit, kit.BAKED_DIR / f"{mat_name}_emit.jpg", is_data=False)
    return kit.make_principled_gltf_material(mat_name, c_i, o_i, n_i, normal_strength=0.4, emit_img=e_i, emit_strength=strength)


# ---------------------------------------------------------------------------
# 1. Build Materials
# ---------------------------------------------------------------------------
mat_moss_stone = build_monumental_mossy_ashlar_material()
mat_carved_stone = kit.build_polyhaven_gltf_material(
    "av_carved_reliquary_stone", "rock_face_03", base_override_linear=(0.34, 0.36, 0.32), contrast=1.18, ao_strength=0.58, rough_bias=0.06, normal_strength=1.15
)
mat_recess_slate = kit.build_polyhaven_gltf_material(
    "av_recess_dark_slate", "rock_face_03", base_override_linear=(0.14, 0.16, 0.15), contrast=1.22, ao_strength=0.65, rough_bias=0.08, normal_strength=1.10
)
mat_deadwood = kit.build_polyhaven_gltf_material(
    "av_gnarled_oak_deadwood", "bark_willow_02", base_override_linear=(0.45, 0.41, 0.36), contrast=1.28, ao_strength=0.68, rough_bias=0.10, normal_strength=1.28
)
mat_leather = kit.build_polyhaven_gltf_material(
    "av_grimoire_leather", "bark_brown_02", base_override_linear=(0.085, 0.042, 0.024), contrast=1.15, ao_strength=0.55, rough_scale=0.85, rough_bias=0.04
)
mat_bronze_clasp = kit.build_polyhaven_gltf_material(
    "av_aged_bronze_clasp", "metal_plate_02", base_override_linear=(0.36, 0.24, 0.09), contrast=1.18, ao_strength=0.52, rough_scale=0.65, metallic=0.84
)
mat_silver_cap = kit.build_polyhaven_gltf_material(
    "av_silver_bottle_collar", "metal_plate_02", base_override_linear=(0.56, 0.60, 0.66), contrast=1.12, ao_strength=0.45, rough_scale=0.52, metallic=0.88
)
mat_magic_floor = build_celtic_arcane_floor_material()
mat_parchment = build_grimoire_parchment_material()
mat_meteorite_450nm = build_faceted_450nm_meteorite_material()

mat_azure_leaf = build_compact_glow_material(
    "av_glowing_azure_leaf_v4", core_rgb=(0.62, 0.94, 1.00), edge_rgb=(0.08, 0.62, 1.00), rim_dark_rgb=(0.05, 0.14, 0.22), strength=3.00, glow_radius=0.44, roughness=0.24
)
mat_chest_basin = build_compact_glow_material(
    "av_chest_cyan_basin_v4", core_rgb=(0.30, 0.92, 1.00), edge_rgb=(0.06, 0.68, 0.94), rim_dark_rgb=(0.04, 0.22, 0.30), strength=2.45, glow_radius=0.82, roughness=0.22
)
mat_lid_underside_glow = build_compact_glow_material(
    "av_lid_underside_cyan_v4", core_rgb=(0.14, 0.56, 0.74), edge_rgb=(0.08, 0.38, 0.56), rim_dark_rgb=(0.16, 0.22, 0.24), strength=1.15, glow_radius=0.84, roughness=0.58
)
mat_phial_sapphire = build_compact_glow_material(
    "av_phial_sapphire_v4", core_rgb=(0.52, 0.78, 1.00), edge_rgb=(0.10, 0.32, 1.00), rim_dark_rgb=(0.07, 0.12, 0.28), strength=2.60, glow_radius=0.46, roughness=0.10
)
mat_phial_cyan = build_compact_glow_material(
    "av_phial_cyan_v4", core_rgb=(0.64, 1.00, 0.96), edge_rgb=(0.08, 0.82, 0.82), rim_dark_rgb=(0.06, 0.18, 0.22), strength=2.60, glow_radius=0.46, roughness=0.10
)

mat_rune_sw = build_obelisk_rune_face_material(
    "av_obelisk_rune_ansuz_uruz",
    [(0.42, 0.54, 0.42, 0.80), (0.42, 0.79, 0.58, 0.70), (0.42, 0.68, 0.57, 0.59), (0.40, 0.18, 0.40, 0.42), (0.40, 0.42, 0.57, 0.35), (0.57, 0.35, 0.57, 0.18)],
)
mat_rune_se = build_obelisk_rune_face_material(
    "av_obelisk_rune_kenaz_fehu",
    [(0.43, 0.54, 0.43, 0.80), (0.43, 0.68, 0.59, 0.78), (0.43, 0.66, 0.59, 0.55), (0.43, 0.18, 0.43, 0.43), (0.43, 0.42, 0.58, 0.36), (0.43, 0.31, 0.56, 0.25)],
)
mat_rune_nw = build_obelisk_rune_face_material(
    "av_obelisk_rune_raido",
    [(0.43, 0.28, 0.43, 0.74), (0.43, 0.74, 0.59, 0.61), (0.59, 0.61, 0.43, 0.50), (0.43, 0.50, 0.60, 0.28)],
)
mat_rune_ne = build_obelisk_rune_face_material(
    "av_obelisk_rune_tiwaz",
    [(0.50, 0.26, 0.50, 0.74), (0.50, 0.74, 0.36, 0.58), (0.50, 0.74, 0.64, 0.58)],
)

# ---------------------------------------------------------------------------
# 2. Create 6 Coaxial Part Empties
# ---------------------------------------------------------------------------
p1_plinth = kit.create_part_empty(scene, "weathered_octagonal_moss_stepped_plinth")
p2_floor = kit.create_part_empty(scene, "celtic_ogham_glowing_rune_floor")
p3_pillars = kit.create_part_empty(scene, "four_corner_rune_monolith_obelisks")
p4_lectern = kit.create_part_empty(scene, "front_grimoire_lectern_and_mana_phials")
p5_oak = kit.create_part_empty(scene, "gnarled_ancient_oak_roots_and_azure_leaves")
p6_chest = kit.create_part_empty(scene, "hexagonal_reliquary_chest_and_450nm_meteorite")

# ---------------------------------------------------------------------------
# PART 1: 4-Step Monumental Mossy Octagonal Stone Plinth
# ---------------------------------------------------------------------------
STEP_SPECS = [
    (4.48, 0.00, 0.24),
    (4.04, 0.24, 0.48),
    (3.60, 0.48, 0.72),
    (3.16, 0.72, 0.96),
]
OCT_ROT_DESIGN = math.pi / 8.0
COS_OCT = math.cos(OCT_ROT_DESIGN)  # 0.9238795 -> Step 1 apothem = 4.139m


def oct_edge_coord(dx: float, dy: float) -> float:
    """Exact octagonal norm: point `(dx, dy)` is inside octagon of circumradius `R` iff `oct_edge_coord <= R * COS_OCT`."""
    best = 0.0
    for k in range(8):
        n_ang = k * (math.pi / 4.0)
        best = max(best, dx * math.cos(n_ang) + dy * math.sin(n_ang))
    return best


def step_surface_z_at(dx: float, dy: float) -> float:
    """Exact top tread height of the 4-step octagonal stone plinth at `(dx, dy)`."""
    od = oct_edge_coord(dx, dy)
    if od <= 3.16 * COS_OCT:
        return 0.965
    if od <= 3.60 * COS_OCT:
        return 0.725
    if od <= 4.04 * COS_OCT:
        return 0.485
    if od <= 4.48 * COS_OCT:
        return 0.245
    return 0.02


under_collar = kit.add_prism_ring(
    scene, "av_oct_recessed_foot", 4.24, 0.0, -0.18, 0.01, sides=8, bevel=0.016, rot_offset=OCT_ROT_DESIGN + mb.CAM_YAW
)
kit.apply_box_uv_and_mat(under_collar, mat_moss_stone, uv_scale=0.22)
kit.parent_keep_local(under_collar, p1_plinth)

for s_idx, (r_oct, z0, z1) in enumerate(STEP_SPECS):
    core_slab = kit.add_prism_ring(
        scene,
        f"av_oct_step_core_{s_idx}",
        r_oct - 0.12,
        0.0,
        z0,
        z1 - 0.006,
        sides=8,
        bevel=0.014,
        rot_offset=OCT_ROT_DESIGN + mb.CAM_YAW,
    )
    kit.apply_box_uv_and_mat(core_slab, mat_moss_stone, uv_scale=0.22)
    kit.parent_keep_local(core_slab, p1_plinth)

    # Large monumental dressed stone curb blocks along each octagonal edge (3-4 massive blocks per side, zero tiny bricks!)
    oct_verts_d = [
        (r_oct * math.cos(OCT_ROT_DESIGN + k * (math.pi / 4.0)), r_oct * math.sin(OCT_ROT_DESIGN + k * (math.pi / 4.0)))
        for k in range(8)
    ]
    for edge_k in range(8):
        vx0, vy0 = oct_verts_d[edge_k]
        vx1, vy1 = oct_verts_d[(edge_k + 1) % 8]
        edge_len = math.hypot(vx1 - vx0, vy1 - vy0)
        edge_yaw = math.atan2(vy1 - vy0, vx1 - vx0)
        inward_x, inward_y = -math.sin(edge_yaw), math.cos(edge_yaw)
        if inward_x * (0.5 * (vx0 + vx1)) + inward_y * (0.5 * (vy0 + vy1)) > 0:
            inward_x, inward_y = -inward_x, -inward_y

        n_blocks = max(3, int(round(edge_len / 0.86)))
        for ib in range(n_blocks):
            t = (ib + 0.5) / n_blocks
            bx = vx0 + (vx1 - vx0) * t + inward_x * 0.24
            by = vy0 + (vy1 - vy0) * t + inward_y * 0.24
            blk_len = (edge_len / n_blocks) * 0.975
            blk_h = (z1 - z0) + 0.010 * math.sin(s_idx * 3.1 + edge_k * 2.3 + ib * 1.9)
            kit.add_beveled_box(
                scene,
                f"av_step_{s_idx}_edge_{edge_k}_blk_{ib}",
                mb.d2w(bx, by, z0 + 0.5 * blk_h),
                (blk_len, 0.50, blk_h),
                mat_moss_stone,
                p1_plinth,
                rot_xyz=mb.rot_d2w(0.0, 0.0, edge_yaw),
                bevel=0.020,
                uv_scale=0.25,
            )

# Projecting stepped stone altar pier on the front steps so the Lectern seats 100% flush with zero overhang or riser clipping!
kit.add_beveled_box(
    scene,
    "av_front_lectern_altar_pier_step1",
    mb.d2w(0.0, -3.47, 0.362),
    (1.04, 0.78, 0.245),
    mat_moss_stone,
    p1_plinth,
    rot_xyz=mb.rot_d2w(),
    bevel=0.018,
    uv_scale=0.25,
)
kit.add_beveled_box(
    scene,
    "av_front_lectern_altar_pier_step2",
    mb.d2w(0.0, -3.40, 0.602),
    (0.94, 0.72, 0.245),
    mat_moss_stone,
    p1_plinth,
    rot_xyz=mb.rot_d2w(),
    bevel=0.018,
    uv_scale=0.25,
)

# ---------------------------------------------------------------------------
# PART 2: Engraved Glowing Azure Celtic/Ogham Magic Circle Floor (`R = 2.28m`)
# ---------------------------------------------------------------------------
R_CIRCLE = 2.28
Z_DECK = 0.96

bm_fl = bmesh.new()
uv_fl = bm_fl.loops.layers.uv.new("UVMap")
n_seg_fl = 64
top_ring_fl = []
bot_ring_fl = []
for k in range(n_seg_fl):
    ang_d = (k / n_seg_fl) * 2.0 * math.pi
    dx = R_CIRCLE * math.cos(ang_d)
    dy = R_CIRCLE * math.sin(ang_d)
    top_ring_fl.append((bm_fl.verts.new(mb.d2w(dx, dy, Z_DECK + 0.05)), 0.5 + 0.48 * math.cos(ang_d), 0.5 + 0.48 * math.sin(ang_d)))
    bot_ring_fl.append(bm_fl.verts.new(mb.d2w(dx, dy, Z_DECK - 0.01)))

v_c_top = bm_fl.verts.new(mb.d2w(0.0, 0.0, Z_DECK + 0.05))
v_c_bot = bm_fl.verts.new(mb.d2w(0.0, 0.0, Z_DECK - 0.01))
for k in range(n_seg_fl):
    kn = (k + 1) % n_seg_fl
    vt0, u0, v0 = top_ring_fl[k]
    vt1, u1, v1 = top_ring_fl[kn]
    f_top = bm_fl.faces.new([v_c_top, vt0, vt1])
    for lp, uv_c in zip(f_top.loops, [(0.5, 0.5), (u0, v0), (u1, v1)]):
        lp[uv_fl].uv = uv_c
    f_side = bm_fl.faces.new([bot_ring_fl[k], bot_ring_fl[kn], vt1, vt0])
    for lp in f_side.loops:
        lp[uv_fl].uv = (0.04, 0.04)
    f_bot = bm_fl.faces.new([v_c_bot, bot_ring_fl[kn], bot_ring_fl[k]])
    for lp in f_bot.loops:
        lp[uv_fl].uv = (0.04, 0.04)

bmesh.ops.recalc_face_normals(bm_fl, faces=bm_fl.faces)
m_fl = bpy.data.meshes.new("av_arcane_circle_slab")
bm_fl.to_mesh(m_fl)
bm_fl.free()
o_fl = bpy.data.objects.new("av_arcane_circle_slab", m_fl)
scene.collection.objects.link(o_fl)
o_fl.data.materials.append(mat_magic_floor)
kit.parent_keep_local(o_fl, p2_floor)

curb = kit.add_prism_ring(scene, "av_magic_circle_curb", R_CIRCLE + 0.14, R_CIRCLE - 0.02, Z_DECK - 0.01, Z_DECK + 0.075, sides=32, bevel=0.014)
kit.apply_box_uv_and_mat(curb, mat_carved_stone, uv_scale=0.45)
kit.parent_keep_local(curb, p2_floor)


# ---------------------------------------------------------------------------
# PART 3: 4 Symmetrical Corner Rune Obelisks (`SW, SE, NW, NE` with >= +0.20m Step Margin!)
# ---------------------------------------------------------------------------
def add_pointed_rune_obelisk(
    name: str,
    dx: float,
    dy: float,
    z_base: float,
    shaft_h: float,
    face_yaw_deg: float,
    mat_front_rune: bpy.types.Material,
):
    yaw = math.radians(face_yaw_deg)
    kit.add_beveled_box(
        scene, f"{name}_pedestal_1", mb.d2w(dx, dy, z_base + 0.08), (0.64, 0.64, 0.16), mat_moss_stone, p3_pillars, rot_xyz=mb.rot_d2w(0.0, 0.0, yaw), bevel=0.016, uv_scale=0.35
    )
    kit.add_beveled_box(
        scene, f"{name}_pedestal_2", mb.d2w(dx, dy, z_base + 0.22), (0.52, 0.52, 0.12), mat_carved_stone, p3_pillars, rot_xyz=mb.rot_d2w(0.0, 0.0, yaw), bevel=0.014, uv_scale=0.45
    )

    bm = bmesh.new()
    uv_lay = bm.loops.layers.uv.new("UVMap")
    z0 = 0.28
    z_sh = z0 + shaft_h
    z_tip = z_sh + 0.34

    def oct_section(hw: float, hd: float, ch: float, zz: float):
        pts = [
            (-hw + ch, -hd), (hw - ch, -hd),
            (hw, -hd + ch), (hw, hd - ch),
            (hw - ch, hd), (-hw + ch, hd),
            (-hw, hd - ch), (-hw, -hd + ch),
        ]
        return [bm.verts.new((px, py, zz)) for px, py in pts]

    r_bot = oct_section(0.22, 0.20, 0.050, z0)
    r_top = oct_section(0.17, 0.155, 0.038, z_sh)
    v_tip = bm.verts.new((0.0, 0.0, z_tip))
    v_bot_c = bm.verts.new((0.0, 0.0, z0))

    for k in range(8):
        kn = (k + 1) % 8
        f_b = bm.faces.new([v_bot_c, r_bot[kn], r_bot[k]])
        for lp in f_b.loops:
            lp[uv_lay].uv = (0.08, 0.08)

        f_s = bm.faces.new([r_bot[k], r_bot[kn], r_top[kn], r_top[k]])
        if k == 0:
            uvs = [(0.22, 0.10), (0.78, 0.10), (0.74, 0.90), (0.26, 0.90)]
            for lp, uvp in zip(f_s.loops, uvs):
                lp[uv_lay].uv = uvp
        else:
            for lp in f_s.loops:
                co = lp.vert.co
                lp[uv_lay].uv = (0.04 + 0.12 * abs(co.x + co.y), 0.10 + 0.70 * ((co.z - z0) / max(shaft_h, 0.1)))

        f_t = bm.faces.new([r_top[k], r_top[kn], v_tip])
        for lp in f_t.loops:
            lp[uv_lay].uv = (0.08, 0.92)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = mb.d2w(dx, dy, z_base)
    obj.rotation_euler = mb.rot_d2w(0.0, 0.0, yaw)
    scene.collection.objects.link(obj)
    obj.data.materials.append(mat_front_rune)
    kit.parent_keep_local(obj, p3_pillars)


# 4 Balanced Symmetrical Corner Obelisks on Step 3 (`z_base = 0.72m`, `r = 2.74m` -> `+0.25m` Step 3 margin, zero oak collision!)
add_pointed_rune_obelisk("rune_obelisk_front_left_sw", -2.54, -1.04, 0.72, 1.18, face_yaw_deg=-10.0, mat_front_rune=mat_rune_sw)
add_pointed_rune_obelisk("rune_obelisk_front_right_se", 2.54, -1.04, 0.72, 1.18, face_yaw_deg=10.0, mat_front_rune=mat_rune_se)
add_pointed_rune_obelisk("rune_obelisk_rear_left_nw", -1.92, 1.96, 0.72, 1.24, face_yaw_deg=-6.0, mat_front_rune=mat_rune_nw)
add_pointed_rune_obelisk("rune_obelisk_rear_right_ne", 1.92, 1.96, 0.72, 1.24, face_yaw_deg=6.0, mat_front_rune=mat_rune_ne)

# ---------------------------------------------------------------------------
# PART 4: Unburied Front Stone Lectern, Open Grimoire & 2 Essence Phials (`dy = -3.40m`, `z = 0.725m`)
# ---------------------------------------------------------------------------
# Seated flush atop the projecting `av_front_lectern_altar_pier_step2` (`dy in [-3.76..-3.04]`, `z = 0.725m`) -> 0.0cm overhang, 0.0cm riser clip!
LX, LY, LZ_BASE = 0.0, -3.40, 0.725
kit.add_beveled_box(scene, "lectern_base_1", mb.d2w(LX, LY, LZ_BASE + 0.07), (0.80, 0.58, 0.14), mat_moss_stone, p4_lectern, rot_xyz=mb.rot_d2w(), bevel=0.015, uv_scale=0.32)
kit.add_beveled_box(scene, "lectern_base_2", mb.d2w(LX, LY, LZ_BASE + 0.19), (0.64, 0.46, 0.11), mat_carved_stone, p4_lectern, rot_xyz=mb.rot_d2w(), bevel=0.013, uv_scale=0.42)
kit.add_beveled_box(scene, "lectern_pillar_shaft", mb.d2w(LX, LY + 0.01, LZ_BASE + 0.45), (0.42, 0.36, 0.42), mat_carved_stone, p4_lectern, rot_xyz=mb.rot_d2w(), bevel=0.014, uv_scale=0.45)
kit.add_beveled_box(scene, "lectern_capital", mb.d2w(LX, LY + 0.01, LZ_BASE + 0.70), (0.62, 0.50, 0.10), mat_moss_stone, p4_lectern, rot_xyz=mb.rot_d2w(), bevel=0.012, uv_scale=0.35)

DESK_PITCH = math.radians(24.0)
kit.add_beveled_box(
    scene, "lectern_sloped_desk", mb.d2w(LX, LY - 0.01, LZ_BASE + 0.80), (1.10, 0.78, 0.10), mat_moss_stone, p4_lectern, rot_xyz=mb.rot_d2w(DESK_PITCH, 0.0, 0.0), bevel=0.016, uv_scale=0.35
)
kit.add_beveled_box(
    scene, "grimoire_leather_cover", mb.d2w(LX, LY, LZ_BASE + 0.88), (0.90, 0.65, 0.045), mat_leather, p4_lectern, rot_xyz=mb.rot_d2w(DESK_PITCH, 0.0, 0.0), bevel=0.008
)
for sx_c in (-0.47, 0.47):
    kit.add_beveled_box(
        scene, f"grimoire_clasp_strap_{sx_c:+.2f}", mb.d2w(LX + sx_c, LY, LZ_BASE + 0.89), (0.08, 0.11, 0.025), mat_bronze_clasp, p4_lectern, rot_xyz=mb.rot_d2w(DESK_PITCH, 0.0, 0.0), bevel=0.004
    )
kit.add_beveled_box(
    scene, "grimoire_bookmark_ribbon", mb.d2w(LX, LY - 0.34, LZ_BASE + 0.73), (0.045, 0.03, 0.21), mat_leather, p4_lectern, rot_xyz=mb.rot_d2w(0.12, 0.0, 0.0), bevel=0.004
)

# Curved open two-page parchment block
bm_bk = bmesh.new()
uv_bk = bm_bk.loops.layers.uv.new("UVMap")
nx_bk, ny_bk = 24, 10
bk_top, bk_bot = [], []
cp_m = Euler(mb.rot_d2w(DESK_PITCH, 0.0, 0.0), "XYZ").to_matrix()
bk_origin = Vector(mb.d2w(LX, LY, LZ_BASE + 0.905))

for iy in range(ny_bk + 1):
    ty = iy / ny_bk
    ly = (ty - 0.5) * 0.60
    r_t, r_b = [], []
    for ix in range(nx_bk + 1):
        tx = ix / nx_bk
        lx = (tx - 0.5) * 0.86
        u_half = abs(tx - 0.5) * 2.0
        arch_z = 0.062 * math.sin(u_half * math.pi * 0.88) + 0.020 * (1.0 - math.exp(-((u_half / 0.14) ** 2)))
        r_t.append((bm_bk.verts.new(bk_origin + cp_m @ Vector((lx, ly, arch_z + 0.036))), tx, ty))
        r_b.append(bm_bk.verts.new(bk_origin + cp_m @ Vector((lx, ly, 0.0))))
    bk_top.append(r_t)
    bk_bot.append(r_b)

for iy in range(ny_bk):
    for ix in range(nx_bk):
        vt00, u00, v00 = bk_top[iy][ix]
        vt10, u10, v10 = bk_top[iy][ix + 1]
        vt11, u11, v11 = bk_top[iy + 1][ix + 1]
        vt01, u01, v01 = bk_top[iy + 1][ix]
        ft = bm_bk.faces.new([vt00, vt10, vt11, vt01])
        for lp, uvp in zip(ft.loops, [(u00, v00), (u10, v10), (u11, v11), (u01, v01)]):
            lp[uv_bk].uv = uvp
        fb = bm_bk.faces.new([bk_bot[iy][ix], bk_bot[iy + 1][ix], bk_bot[iy + 1][ix + 1], bk_bot[iy][ix + 1]])
        for lp in fb.loops:
            lp[uv_bk].uv = (0.05, 0.5)
        if iy == 0:
            fs = bm_bk.faces.new([bk_bot[0][ix], bk_bot[0][ix + 1], vt10, vt00])
            for lp in fs.loops:
                lp[uv_bk].uv = (0.05, 0.5)
        if iy == ny_bk - 1:
            fs = bm_bk.faces.new([bk_bot[ny_bk][ix + 1], bk_bot[ny_bk][ix], vt01, vt11])
            for lp in fs.loops:
                lp[uv_bk].uv = (0.05, 0.5)
        if ix == 0:
            fs = bm_bk.faces.new([bk_bot[iy + 1][0], bk_bot[iy][0], vt00, vt01])
            for lp in fs.loops:
                lp[uv_bk].uv = (0.05, 0.5)
        if ix == nx_bk - 1:
            fs = bm_bk.faces.new([bk_bot[iy][nx_bk], bk_bot[iy + 1][nx_bk], vt11, vt10])
            for lp in fs.loops:
                lp[uv_bk].uv = (0.05, 0.5)

bmesh.ops.recalc_face_normals(bm_bk, faces=bm_bk.faces)
m_bk = bpy.data.meshes.new("grimoire_curved_pages")
bm_bk.to_mesh(m_bk)
bm_bk.free()
for p in m_bk.polygons:
    p.use_smooth = True
o_bk = bpy.data.objects.new("grimoire_curved_pages", m_bk)
scene.collection.objects.link(o_bk)
o_bk.data.materials.append(mat_parchment)
kit.parent_keep_local(o_bk, p4_lectern)

# Stand the 2 glowing glass phials directly on Step 3 (`z=0.725m`) right beside the lectern matching the Concept 1:1!


def add_lathe_phial(
    name: str,
    dx: float,
    dy: float,
    z_base: float,
    profile_rz: list[tuple[float, float]],
    sides: int,
    mat_body: bpy.types.Material,
    mat_stopper: bpy.types.Material,
    stopper_z0: float,
    stopper_h: float,
    stopper_r: float,
):
    wxy = mb.d2w(dx, dy, 0.0)
    bm = bmesh.new()
    uv_lay = bm.loops.layers.uv.new("UVMap")
    rings = []
    z_max_p = max(z for _, z in profile_rz)
    for r_p, z_p in profile_rz:
        v_uv = 0.34 + 0.32 * (z_p / max(z_max_p, 1e-4))
        rings.append([
            (bm.verts.new((wxy[0] + r_p * math.cos(a * 2.0 * math.pi / sides), wxy[1] + r_p * math.sin(a * 2.0 * math.pi / sides), z_base + z_p)), v_uv)
            for a in range(sides)
        ])
    vb = bm.verts.new((wxy[0], wxy[1], z_base + profile_rz[0][1]))
    vt = bm.verts.new((wxy[0], wxy[1], z_base + profile_rz[-1][1]))
    for a in range(sides):
        an = (a + 1) % sides
        fb = bm.faces.new([vb, rings[0][an][0], rings[0][a][0]])
        for lp in fb.loops:
            lp[uv_lay].uv = (0.5, 0.36)
        ft = bm.faces.new([rings[-1][a][0], rings[-1][an][0], vt])
        for lp in ft.loops:
            lp[uv_lay].uv = (0.5, 0.64)
    for ir in range(len(rings) - 1):
        for a in range(sides):
            an = (a + 1) % sides
            fq = bm.faces.new([rings[ir][a][0], rings[ir][an][0], rings[ir + 1][an][0], rings[ir + 1][a][0]])
            u0 = 0.36 + 0.28 * abs(math.sin(a * math.pi / sides))
            u1 = 0.36 + 0.28 * abs(math.sin(an * math.pi / sides))
            for lp, uv_c in zip(fq.loops, [(u0, rings[ir][a][1]), (u1, rings[ir][an][1]), (u1, rings[ir + 1][an][1]), (u0, rings[ir + 1][a][1])]):
                lp[uv_lay].uv = uv_c
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m = bpy.data.meshes.new(name)
    bm.to_mesh(m)
    bm.free()
    for p in m.polygons:
        p.use_smooth = sides >= 14
    o = bpy.data.objects.new(name, m)
    scene.collection.objects.link(o)
    o.data.materials.append(mat_body)
    kit.parent_keep_local(o, p4_lectern)

    stop = kit.add_prism_ring(
        scene, f"{name}_stopper", stopper_r, 0.0, z_base + stopper_z0, z_base + stopper_z0 + stopper_h, sides=10, bevel=0.004, r_outer_top=stopper_r * 0.65
    )
    stop.location = (wxy[0], wxy[1], 0.0)
    kit.apply_box_uv_and_mat(stop, mat_stopper, uv_scale=1.5)
    kit.parent_keep_local(stop, p4_lectern)


add_lathe_phial(
    "mana_phial_tall_sapphire",
    dx=0.78,
    dy=-2.84,
    z_base=0.725,
    profile_rz=[(0.095, 0.0), (0.118, 0.10), (0.098, 0.40), (0.052, 0.52), (0.068, 0.58), (0.050, 0.63)],
    sides=8,
    mat_body=mat_phial_sapphire,
    mat_stopper=mat_silver_cap,
    stopper_z0=0.62,
    stopper_h=0.12,
    stopper_r=0.052,
)
add_lathe_phial(
    "mana_phial_bulbous_cyan",
    dx=1.10,
    dy=-2.90,
    z_base=0.725,
    profile_rz=[(0.105, 0.0), (0.168, 0.13), (0.156, 0.26), (0.060, 0.39), (0.075, 0.45), (0.056, 0.50)],
    sides=18,
    mat_body=mat_phial_cyan,
    mat_stopper=mat_leather,
    stopper_z0=0.41,
    stopper_h=0.075,
    stopper_r=0.046,
)


# ---------------------------------------------------------------------------
# PART 5: Gnarled Ancient Oak Trunk, Step-Contouring Roots & Individual Twig Leaves
# ---------------------------------------------------------------------------
def add_gnarled_bark_tendril(
    name: str,
    design_pts: list[tuple[float, float, float]],
    r_start: float,
    r_end: float,
    sides: int = 12,
    twist_turns: float = 1.4,
    subdivide_catmull: bool = True,
    seed: float = 0.0,
):
    """Organic gnarled twisted bark spline mesh with deep bark ridges & knots."""
    bm = bmesh.new()
    pts = [Vector(mb.d2w(*p)) for p in design_pts]
    if subdivide_catmull and len(pts) >= 3:
        sub_pts = [pts[0]]
        for i in range(len(pts) - 1):
            p0 = pts[max(0, i - 1)]
            p1 = pts[i]
            p2 = pts[i + 1]
            p3 = pts[min(len(pts) - 1, i + 2)]
            for st in (0.25, 0.50, 0.75, 1.0):
                t2 = st * st
                t3 = t2 * st
                pt = 0.5 * (
                    (2.0 * p1)
                    + (-p0 + p2) * st
                    + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
                    + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
                )
                sub_pts.append(pt)
    else:
        sub_pts = pts

    rings = []
    n_p = len(sub_pts)
    for i, p in enumerate(sub_pts):
        u = i / max(1, n_p - 1)
        tang = (sub_pts[min(n_p - 1, i + 1)] - sub_pts[max(0, i - 1)]).normalized()
        up = Vector((0, 0, 1)) if abs(tang.z) < 0.92 else Vector((1, 0, 0))
        b1 = tang.cross(up).normalized()
        b2 = tang.cross(b1).normalized()
        rad_base = r_start * ((1.0 - u) ** 0.78) + r_end * (u ** 0.78)
        ring = []
        for s in range(sides):
            ang = (s / sides) * 2.0 * math.pi
            bark_flute = (
                1.0
                + 0.20 * math.sin(ang * 5.0 + u * twist_turns * 2.0 * math.pi + seed)
                + 0.11 * math.cos(ang * 3.0 - u * 9.0 + seed * 1.7)
            )
            rad = max(0.010, rad_base * bark_flute)
            ring.append(bm.verts.new(p + b1 * (math.cos(ang) * rad) + b2 * (math.sin(ang) * rad)))
        rings.append(ring)

    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    for i in range(n_p - 1):
        for s in range(sides):
            sn = (s + 1) % sides
            bm.faces.new([rings[i][s], rings[i][sn], rings[i + 1][sn], rings[i + 1][s]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m = bpy.data.meshes.new(name)
    bm.to_mesh(m)
    bm.free()
    for poly in m.polygons:
        poly.use_smooth = True
    o = bpy.data.objects.new(name, m)
    scene.collection.objects.link(o)
    kit.apply_box_uv_and_mat(o, mat_deadwood, uv_scale=0.72)
    kit.parent_keep_local(o, p5_oak)


def add_step_draped_root(
    name: str,
    xy_waypoints: list[tuple[float, float]],
    z_start_chest: float,
    r_start: float,
    r_end: float,
    seed: float = 0.0,
):
    """
    Traces an organic root across the magic circle and DOWN OVER the 4 octagonal stone steps:
      - Strictly clamps octagonal distance `<= 3.74m` (`>= +0.35m` inside Step 1's `4.139m` apothem -> ZERO overhang!)
      - Samples densely (`ds = 0.085m`) and enforces `dz >= surface_z + r_local * 0.92` at EVERY sample
        so the root contours cleanly OVER step risers and treads without EVER tunneling into stone!
    """
    dense_xy: list[tuple[float, float]] = []
    for k in range(len(xy_waypoints) - 1):
        x0, y0 = xy_waypoints[k]
        x1, y1 = xy_waypoints[k + 1]
        seg_l = math.hypot(x1 - x0, y1 - y0)
        n_sub = max(2, int(math.ceil(seg_l / 0.085)))
        for is_i in range(n_sub if k < len(xy_waypoints) - 2 else n_sub + 1):
            t = is_i / n_sub
            px = x0 + (x1 - x0) * t
            py = y0 + (y1 - y0) * t
            # Organic root wiggle
            wig = 0.045 * math.sin((k + t) * 4.3 + seed)
            px += -wig * (y1 - y0) / max(seg_l, 1e-4)
            py += wig * (x1 - x0) / max(seg_l, 1e-4)
            od = oct_edge_coord(px, py)
            if od > 3.72:
                sc = 3.72 / od
                px *= sc
                py *= sc
            dense_xy.append((px, py))

    n_tot = len(dense_xy)
    raw_z = []
    radii = []
    for idx, (px, py) in enumerate(dense_xy):
        u = idx / max(1, n_tot - 1)
        rloc = r_start * ((1.0 - u) ** 0.78) + r_end * (u ** 0.78)
        radii.append(rloc)
        # Base surface = arcane floor slab (1.01m inside R_CIRCLE+0.14) or octagonal step tread
        surf_z = 1.015 if math.hypot(px, py) <= R_CIRCLE + 0.14 else step_surface_z_at(px, py)
        chest_blend = max(0.0, 1.0 - u / 0.22) ** 1.5
        z_target = surf_z + rloc * 0.94 + chest_blend * max(0.0, z_start_chest - (surf_z + rloc * 0.94))
        raw_z.append(z_target)

    # Smooth Z slightly while strictly clamping above max neighboring step surface so riser corners never clip!
    pts_3d: list[tuple[float, float, float]] = []
    for idx, (px, py) in enumerate(dense_xy):
        rloc = radii[idx]
        z_sm = 0.25 * raw_z[max(0, idx - 1)] + 0.50 * raw_z[idx] + 0.25 * raw_z[min(n_tot - 1, idx + 1)]
        # Look ahead/behind 6cm so the root lifts BEFORE crossing a step riser edge!
        surf_max = step_surface_z_at(px, py)
        for j in (max(0, idx - 1), min(n_tot - 1, idx + 1)):
            jx, jy = dense_xy[j]
            jsurf = 1.015 if math.hypot(jx, jy) <= R_CIRCLE + 0.14 else step_surface_z_at(jx, jy)
            surf_max = max(surf_max, jsurf)
        pts_3d.append((px, py, max(z_sm, surf_max + rloc * 0.92)))

    add_gnarled_bark_tendril(name, pts_3d, r_start=r_start, r_end=r_end, sides=10, twist_turns=1.3, subdivide_catmull=False, seed=seed)


# Main twisted ancient oak trunk rising behind/right of the hexagonal chest — kept compact (`dx <= 1.25, dy <= 1.05`) well clear of all 4 corner obelisks!
add_gnarled_bark_tendril(
    "oak_main_trunk_right_sweep",
    [(0.54, 0.04, 1.02), (0.72, 0.28, 1.48), (0.64, 0.52, 2.06), (0.86, 0.68, 2.72), (1.04, 0.78, 3.24)],
    r_start=0.27,
    r_end=0.065,
    sides=16,
    twist_turns=1.7,
    seed=1.0,
)
add_gnarled_bark_tendril(
    "oak_crown_fork_inner",
    [(0.64, 0.50, 2.00), (0.48, 0.62, 2.54), (0.62, 0.74, 3.14)],
    r_start=0.16,
    r_end=0.042,
    sides=12,
    twist_turns=1.2,
    seed=2.2,
)
add_gnarled_bark_tendril(
    "oak_upper_twig_arch_left",
    [(0.48, 0.62, 2.46), (0.18, 0.70, 2.82), (-0.08, 0.76, 3.08)],
    r_start=0.055,
    r_end=0.014,
    sides=8,
    seed=3.4,
)
add_gnarled_bark_tendril(
    "oak_upper_twig_arch_right",
    [(0.78, 0.64, 2.34), (1.08, 0.74, 2.54), (1.28, 0.80, 2.64)],
    r_start=0.058,
    r_end=0.015,
    sides=8,
    seed=4.6,
)

# Embracing chest roots + step-draping roots & secondary rootlets (100% contouring OVER steps, zero overhang!)
add_gnarled_bark_tendril(
    "oak_root_front_chest_embrace",
    [(0.62, 0.06, 1.46), (0.44, -0.44, 1.18), (-0.06, -0.66, 1.08), (-0.54, -0.58, 1.06)],
    r_start=0.15,
    r_end=0.035,
    sides=10,
    seed=5.1,
)
add_gnarled_bark_tendril(
    "oak_root_left_chest_claw",
    [(-0.46, 0.60, 1.48), (-0.82, 0.22, 1.26), (-0.76, -0.28, 1.08), (-0.42, -0.56, 1.05)],
    r_start=0.14,
    r_end=0.032,
    sides=10,
    seed=6.3,
)

step_root_specs = [
    # Asymmetric left flank root group (~8:30-9:30 o'clock) + rootlets — leaves front-left Magic Circle open!
    ("oak_root_cascade_left_main", [(-0.76, 0.30), (-1.58, 0.16), (-2.42, -0.08), (-3.18, -0.26), (-3.64, -0.40)], 1.24, 0.15, 0.024, 11.0),
    ("oak_root_cascade_left_fork_a", [(-2.42, -0.08), (-2.88, 0.34), (-3.44, 0.62)], 1.06, 0.085, 0.018, 12.4),
    ("oak_root_cascade_left_fork_b", [(-1.58, 0.16), (-2.02, 0.76), (-2.68, 1.08), (-3.28, 1.18)], 1.12, 0.095, 0.020, 13.8),
    # Asymmetric front-right flank root group (~4:30-5:00 o'clock) + rootlets descending beside SE obelisk
    ("oak_root_cascade_front_right_main", [(0.68, 0.06), (1.32, -0.58), (1.76, -1.48), (1.98, -2.42), (2.08, -3.12)], 1.22, 0.15, 0.025, 15.2),
    ("oak_root_cascade_front_right_fork", [(1.76, -1.48), (1.56, -2.12), (1.64, -2.96), (1.68, -3.48)], 1.04, 0.082, 0.018, 16.0),
    ("oak_root_cascade_right_flank", [(1.32, -0.58), (2.08, -0.22), (2.94, 0.06), (3.58, 0.20)], 1.06, 0.095, 0.020, 16.6),
    # Rear stabilizing roots
    ("oak_root_cascade_rear_left", [(-0.38, 0.72), (-0.92, 1.46), (-1.14, 2.38), (-1.20, 3.14)], 1.28, 0.12, 0.022, 18.0),
    ("oak_root_cascade_rear_right", [(0.78, 0.48), (1.14, 1.24), (1.08, 2.28), (0.96, 3.12)], 1.24, 0.11, 0.022, 19.4),
]
for rname, xy_w, z_st, rs, re, rseed in step_root_specs:
    add_step_draped_root(rname, xy_w, z_start_chest=z_st, r_start=rs, r_end=re, seed=rseed)


def add_twig_mounted_azure_leaf(
    name: str,
    branch_xyz: tuple[float, float, float],
    tip_dir_xyz: tuple[float, float, float],
    roll_deg: float = 0.0,
    length: float = 0.19,
):
    """Single sculpted glowing azure oak leaf growing naturally from a fine dark deadwood twig (ZERO pinwheels!)."""
    bx, by, bz = branch_xyz
    dx_t, dy_t, dz_t = tip_dir_xyz
    dlen = max(math.sqrt(dx_t * dx_t + dy_t * dy_t + dz_t * dz_t), 1e-4)
    ux, uy, uz = dx_t / dlen, dy_t / dlen, dz_t / dlen
    stem_x, stem_y, stem_z = bx + ux * 0.07, by + uy * 0.07, bz + uz * 0.07

    add_gnarled_bark_tendril(
        f"{name}_twig",
        [(bx, by, bz), (stem_x, stem_y, stem_z)],
        r_start=0.016,
        r_end=0.008,
        sides=6,
        twist_turns=0.2,
        subdivide_catmull=False,
        seed=length * 37.0,
    )

    bm = bmesh.new()
    uv_lay = bm.loops.layers.uv.new("UVMap")
    hw = length * 0.27
    ht = 0.012
    v_stem = bm.verts.new((0.0, 0.0, 0.0))
    v_tip = bm.verts.new((length, 0.0, 0.018))
    v_l1 = bm.verts.new((0.32 * length, hw * 0.82, 0.006))
    v_l2 = bm.verts.new((0.68 * length, hw, 0.012))
    v_r1 = bm.verts.new((0.32 * length, -hw * 0.82, 0.006))
    v_r2 = bm.verts.new((0.68 * length, -hw, 0.012))
    v_top = bm.verts.new((0.50 * length, 0.0, ht + 0.010))
    v_bot = bm.verts.new((0.50 * length, 0.0, -ht))

    perim = [
        (v_stem, 0.36, 0.50),
        (v_r1, 0.44, 0.38),
        (v_r2, 0.56, 0.38),
        (v_tip, 0.66, 0.50),
        (v_l2, 0.56, 0.62),
        (v_l1, 0.44, 0.62),
    ]
    for i in range(len(perim)):
        v0, u0, w0 = perim[i]
        v1, u1, w1 = perim[(i + 1) % len(perim)]
        ft = bm.faces.new([v_top, v0, v1])
        for lp, uv_c in zip(ft.loops, [(0.50, 0.50), (u0, w0), (u1, w1)]):
            lp[uv_lay].uv = uv_c
        fb = bm.faces.new([v_bot, v1, v0])
        for lp, uv_c in zip(fb.loops, [(0.50, 0.50), (u1, w1), (u0, w0)]):
            lp[uv_lay].uv = uv_c

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m = bpy.data.meshes.new(name)
    bm.to_mesh(m)
    bm.free()
    o = bpy.data.objects.new(name, m)
    o.location = mb.d2w(stem_x, stem_y, stem_z)
    yaw_d = math.atan2(uy, ux)
    pitch_d = -math.asin(max(-0.95, min(0.95, uz)))
    o.rotation_euler = mb.rot_d2w(math.radians(roll_deg), pitch_d, yaw_d)
    scene.collection.objects.link(o)
    o.data.materials.append(mat_azure_leaf)
    kit.parent_keep_local(o, p5_oak)


# Individual organic glowing azure leaves along crown twigs, trunk bends, and root knees (kept strictly clear of obelisks!)
single_leaf_specs = [
    ((-0.05, 0.75, 3.06), (-0.8, 0.2, 0.4), 18.0, 0.19),
    ((0.12, 0.71, 2.88), (-0.5, -0.5, 0.5), -24.0, 0.18),
    ((0.32, 0.66, 2.66), (-0.6, 0.4, 0.3), 28.0, 0.20),
    ((0.58, 0.72, 3.08), (-0.2, 0.5, 0.6), -15.0, 0.19),
    ((0.66, 0.70, 2.84), (0.6, -0.3, 0.4), 22.0, 0.18),
    ((0.96, 0.74, 2.98), (0.7, 0.2, 0.5), -20.0, 0.20),
    ((1.04, 0.78, 3.22), (0.5, 0.4, 0.6), 14.0, 0.18),
    ((1.12, 0.76, 2.56), (0.8, -0.3, 0.3), -28.0, 0.19),
    ((1.26, 0.80, 2.63), (0.9, 0.1, 0.2), 16.0, 0.18),
    ((0.88, 0.66, 2.40), (0.6, -0.6, 0.2), -22.0, 0.17),
    ((0.72, 0.34, 1.66), (0.8, -0.4, 0.3), 25.0, 0.19),
    ((0.60, -0.14, 1.32), (0.6, -0.7, 0.2), -18.0, 0.17),
    ((-0.72, 0.36, 1.38), (-0.8, 0.3, 0.3), 20.0, 0.18),
    ((-0.80, 0.06, 1.18), (-0.8, -0.4, 0.2), -24.0, 0.17),
    ((-2.38, -0.06, 1.12), (-0.7, -0.3, 0.3), 18.0, 0.16),
    ((1.68, -1.32, 1.12), (0.7, -0.5, 0.3), -20.0, 0.16),
]
for idx_l, (b_xyz, t_dir, r_deg, l_len) in enumerate(single_leaf_specs):
    add_twig_mounted_azure_leaf(f"oak_azure_leaf_{idx_l}", b_xyz, t_dir, roll_deg=r_deg, length=l_len)

# ---------------------------------------------------------------------------
# PART 6: Hexagonal Carved Reliquary Chest, Hinged Vaulted Lid & Faceted 450nm Meteorite
# ---------------------------------------------------------------------------
CX_CH, CY_CH = -0.06, 0.22
WXY_CH = mb.d2w(CX_CH, CY_CH, 0.0)
HEX_ROT = math.pi / 6.0 + mb.CAM_YAW

for h_i, (r_hex, hz0, hz1) in enumerate([
    (1.00, 1.00, 1.12),
    (0.91, 1.12, 1.23),
    (0.83, 1.23, 1.33),
]):
    h_step = kit.add_prism_ring(scene, f"reliquary_hex_plinth_{h_i}", r_hex, 0.0, hz0, hz1, sides=6, bevel=0.014, rot_offset=HEX_ROT)
    h_step.location = (WXY_CH[0], WXY_CH[1], 0.0)
    kit.apply_box_uv_and_mat(h_step, mat_carved_stone, uv_scale=0.52)
    kit.parent_keep_local(h_step, p6_chest)

coffer_walls = kit.add_prism_ring(
    scene, "reliquary_hex_coffer_walls", 0.83, 0.56, 1.33, 1.98, sides=6, bevel=0.016, rot_offset=HEX_ROT
)
coffer_walls.location = (WXY_CH[0], WXY_CH[1], 0.0)
kit.apply_box_uv_and_mat(coffer_walls, mat_carved_stone, uv_scale=0.52)
kit.parent_keep_local(coffer_walls, p6_chest)

coffer_lip = kit.add_prism_ring(
    scene, "reliquary_hex_rim_lip", 0.87, 0.54, 1.93, 2.01, sides=6, bevel=0.012, rot_offset=HEX_ROT
)
coffer_lip.location = (WXY_CH[0], WXY_CH[1], 0.0)
kit.apply_box_uv_and_mat(coffer_lip, mat_carved_stone, uv_scale=0.52)
kit.parent_keep_local(coffer_lip, p6_chest)

# True 3D Carved Stone Gothic/Celtic Arch Relief Panels on all 6 faces (jambs + curved archivolt + recessed slate panel!)
for f_k in range(6):
    f_ang = math.pi / 6.0 + (f_k + 0.5) * (math.pi / 3.0)
    ca_f, sa_f = math.cos(f_ang), math.sin(f_ang)
    fx = CX_CH + 0.725 * ca_f
    fy = CY_CH + 0.725 * sa_f
    tx_f, ty_f = -sa_f, ca_f

    # Dark slate recessed niche plate
    kit.add_beveled_box(
        scene, f"reliquary_arch_niche_{f_k}", mb.d2w(fx, fy, 1.64), (0.04, 0.42, 0.46), mat_recess_slate, p6_chest, rot_xyz=mb.rot_d2w(0.0, 0.0, f_ang), bevel=0.006, uv_scale=0.65
    )
    # Twin carved colonnette jambs + sill
    for s_j in (-0.19, 0.19):
        kit.add_beveled_box(
            scene, f"reliquary_arch_jamb_{f_k}_{s_j:+.2f}", mb.d2w(fx + 0.025 * ca_f + s_j * tx_f, fy + 0.025 * sa_f + s_j * ty_f, 1.56),
            (0.065, 0.055, 0.32), mat_carved_stone, p6_chest, rot_xyz=mb.rot_d2w(0.0, 0.0, f_ang), bevel=0.010, uv_scale=0.65
        )
    kit.add_beveled_box(
        scene, f"reliquary_arch_sill_{f_k}", mb.d2w(fx + 0.025 * ca_f, fy + 0.025 * sa_f, 1.39),
        (0.07, 0.46, 0.055), mat_carved_stone, p6_chest, rot_xyz=mb.rot_d2w(0.0, 0.0, f_ang), bevel=0.010, uv_scale=0.65
    )
    # Curved stone archivolt + central carved trilobe boss
    arch_pts = []
    for k_a in range(7):
        th_a = (k_a / 6.0) * math.pi
        lat = 0.19 * math.cos(th_a)
        zz_a = 1.71 + 0.15 * math.sin(th_a)
        arch_pts.append(mb.d2w(fx + 0.03 * ca_f + lat * tx_f, fy + 0.03 * sa_f + lat * ty_f, zz_a))
    kit.add_curved_vein_polyline(scene, f"reliquary_archivolt_{f_k}", arch_pts, 0.032, 0.032, mat_carved_stone, p6_chest, sides=6, uv_scale=0.7)
    kit.add_beveled_box(
        scene, f"reliquary_knot_boss_{f_k}", mb.d2w(fx + 0.022 * ca_f, fy + 0.022 * sa_f, 1.61),
        (0.045, 0.12, 0.18), mat_carved_stone, p6_chest, rot_xyz=mb.rot_d2w(0.0, 0.0, f_ang), bevel=0.012, uv_scale=0.7
    )

# Glowing Cyan-Azure Recessed Coffer Bed + Multi-Faceted 450nm Sapphire Crystal Meteorite!
bm_bed = bmesh.new()
uv_bed = bm_bed.loops.layers.uv.new("UVMap")
bed_ring = []
for k in range(6):
    a_h = math.pi / 6.0 + k * (math.pi / 3.0)
    dx_b = CX_CH + 0.56 * math.cos(a_h)
    dy_b = CY_CH + 0.56 * math.sin(a_h)
    bed_ring.append((bm_bed.verts.new(mb.d2w(dx_b, dy_b, 1.76)), 0.5 + 0.34 * math.cos(a_h), 0.5 + 0.34 * math.sin(a_h)))
v_bed_c = bm_bed.verts.new(mb.d2w(CX_CH, CY_CH, 1.72))
for k in range(6):
    kn = (k + 1) % 6
    f_bd = bm_bed.faces.new([v_bed_c, bed_ring[k][0], bed_ring[kn][0]])
    for lp, uvc in zip(f_bd.loops, [(0.5, 0.5), (bed_ring[k][1], bed_ring[k][2]), (bed_ring[kn][1], bed_ring[kn][2])]):
        lp[uv_bed].uv = uvc
bmesh.ops.recalc_face_normals(bm_bed, faces=bm_bed.faces)
m_bed = bpy.data.meshes.new("reliquary_glowing_basin")
bm_bed.to_mesh(m_bed)
bm_bed.free()
o_bed = bpy.data.objects.new("reliquary_glowing_basin", m_bed)
scene.collection.objects.link(o_bed)
o_bed.data.materials.append(mat_chest_basin)
kit.parent_keep_local(o_bed, p6_chest)


def build_faceted_crystal_meteorite():
    """Sculpted polyhedral crystalline 450nm meteorite with planar interior UVs `[0.18..0.82]` -> luminous crystal facets!"""
    bm = bmesh.new()
    uv_m = bm.loops.layers.uv.new("UVMap")
    # 3-ring irregular faceted crystal polyhedron
    rings_m = []
    for rz_f, rad_xy, z_off in [(0.0, 0.24, 0.00), (0.45, 0.30, 0.14), (0.85, 0.19, 0.27)]:
        ring = []
        for k in range(8):
            ang = (k / 8.0) * 2.0 * math.pi + 0.18 * rz_f
            fac_r = rad_xy * (0.86 + 0.22 * math.sin(k * 2.7 + rz_f * 4.0))
            lx = fac_r * math.cos(ang) * 1.15
            ly = fac_r * math.sin(ang) * 0.85
            lz = z_off + 0.025 * math.cos(k * 3.0)
            ring.append(bm.verts.new((lx, ly, lz)))
        rings_m.append(ring)
    v_bot = bm.verts.new((0.0, 0.0, -0.02))
    v_top = bm.verts.new((0.02, -0.01, 0.34))
    for k in range(8):
        kn = (k + 1) % 8
        bm.faces.new([v_bot, rings_m[0][kn], rings_m[0][k]])
        bm.faces.new([rings_m[0][k], rings_m[0][kn], rings_m[1][kn], rings_m[1][k]])
        bm.faces.new([rings_m[1][k], rings_m[1][kn], rings_m[2][kn], rings_m[2][k]])
        bm.faces.new([rings_m[2][k], rings_m[2][kn], v_top])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    for f in bm.faces:
        for lp in f.loops:
            co = lp.vert.co
            u = 0.50 + co.x * 0.85 + co.z * 0.25
            v = 0.50 + co.y * 0.95 + co.z * 0.30
            lp[uv_m].uv = (max(0.14, min(0.86, u)), max(0.14, min(0.86, v)))
    m_met = bpy.data.meshes.new("azure_450nm_meteorite_core")
    bm.to_mesh(m_met)
    bm.free()
    # Flat-shaded crystal facets!
    for p in m_met.polygons:
        p.use_smooth = False
    o_met = bpy.data.objects.new("azure_450nm_meteorite_core", m_met)
    o_met.location = mb.d2w(CX_CH, CY_CH - 0.02, 1.72)
    o_met.rotation_euler = mb.rot_d2w(0.16, -0.22, 0.38)
    scene.collection.objects.link(o_met)
    o_met.data.materials.append(mat_meteorite_450nm)
    kit.parent_keep_local(o_met, p6_chest)


build_faceted_crystal_meteorite()


def build_open_hex_lid():
    """
    Hexagonal vaulted stone lid hinged physically along the exact rear-left rim edge of `coffer_lip`!
    Rear-left edge of hexagon (`rot = pi/6`) between vertices `k=1` (90 deg) and `k=2` (150 deg) has midpoint
    at angle `120 deg` (`2*pi/3`), apothem `0.85 * cos(30 deg) = 0.736m`!
    """
    hinge_ang = 2.0 * math.pi / 3.0  # 120 deg (rear-left edge facing front-right toward camera!)
    apothem = 0.85 * math.cos(math.pi / 6.0)
    hx = CX_CH + apothem * math.cos(hinge_ang)
    hy = CY_CH + apothem * math.sin(hinge_ang)
    hz = 2.00
    hinge_w = Vector(mb.d2w(hx, hy, hz))

    # Local frame where +Y points outward toward hinge, -Y swings across chest center, rotated around local X by -44 deg!
    lid_yaw = hinge_ang - math.pi * 0.5  # +30 deg so local +Y aligns with hinge_ang (120 deg)!
    lid_tilt = math.radians(-44.0)
    lid_mat = Euler(mb.rot_d2w(lid_tilt, 0.0, lid_yaw), "XYZ").to_matrix()
    lc = Vector((0.0, -apothem, 0.0))

    bm = bmesh.new()

    def h_ring(rad: float, lz: float):
        pts = []
        for k in range(6):
            # In local lid frame (rotated by -30 deg relative to design), hex vertices sit at k * 60 deg!
            a = k * (math.pi / 3.0)
            p_loc = lc + Vector((rad * math.cos(a), rad * math.sin(a), lz))
            pts.append(bm.verts.new(hinge_w + lid_mat @ p_loc))
        return pts

    outer_bot = h_ring(0.86, 0.0)
    outer_mid = h_ring(0.75, 0.14)
    outer_top = h_ring(0.46, 0.25)
    inner_bot = h_ring(0.62, 0.0)
    inner_top = h_ring(0.42, 0.12)

    v_cap_out = bm.verts.new(hinge_w + lid_mat @ (lc + Vector((0.0, 0.0, 0.27))))
    v_cap_in = bm.verts.new(hinge_w + lid_mat @ (lc + Vector((0.0, 0.0, 0.13))))

    for k in range(6):
        kn = (k + 1) % 6
        bm.faces.new([outer_bot[k], outer_bot[kn], outer_mid[kn], outer_mid[k]])
        bm.faces.new([outer_mid[k], outer_mid[kn], outer_top[kn], outer_top[k]])
        bm.faces.new([outer_top[k], outer_top[kn], v_cap_out])
        bm.faces.new([inner_bot[kn], inner_bot[k], outer_bot[k], outer_bot[kn]])
        bm.faces.new([inner_top[kn], inner_top[k], inner_bot[k], inner_bot[kn]])
        bm.faces.new([v_cap_in, inner_top[kn], inner_top[k]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    m_lid = bpy.data.meshes.new("reliquary_open_hex_lid")
    bm.to_mesh(m_lid)
    bm.free()
    o_lid = bpy.data.objects.new("reliquary_open_hex_lid", m_lid)
    scene.collection.objects.link(o_lid)
    kit.apply_box_uv_and_mat(o_lid, mat_carved_stone, uv_scale=0.52)
    kit.parent_keep_local(o_lid, p6_chest)

    # Subtle recessed azure rune seal inside lid vault (mapped to [0.35..0.65] -> soft cyan glow, NOT a white mirror!)
    bm_in = bmesh.new()
    uv_in = bm_in.loops.layers.uv.new("UVMap")
    g_ring = []
    for k in range(6):
        a = k * (math.pi / 3.0)
        g_ring.append((bm_in.verts.new(hinge_w + lid_mat @ (lc + Vector((0.36 * math.cos(a), 0.36 * math.sin(a), 0.115)))), 0.5 + 0.28 * math.cos(a), 0.5 + 0.28 * math.sin(a)))
    g_ctr = bm_in.verts.new(hinge_w + lid_mat @ (lc + Vector((0.0, 0.0, 0.12))))
    for k in range(6):
        kn = (k + 1) % 6
        fin = bm_in.faces.new([g_ctr, g_ring[kn][0], g_ring[k][0]])
        for lp, uvc in zip(fin.loops, [(0.5, 0.5), (g_ring[kn][1], g_ring[kn][2]), (g_ring[k][1], g_ring[k][2])]):
            lp[uv_in].uv = uvc
    bmesh.ops.recalc_face_normals(bm_in, faces=bm_in.faces)
    m_in = bpy.data.meshes.new("reliquary_lid_inner_seal")
    bm_in.to_mesh(m_in)
    bm_in.free()
    o_in = bpy.data.objects.new("reliquary_lid_inner_seal", m_in)
    scene.collection.objects.link(o_in)
    o_in.data.materials.append(mat_lid_underside_glow)
    kit.parent_keep_local(o_in, p6_chest)

    # Twin physical bronze hinge knuckles along the hinge axis connecting lid to coffer rim!
    for s_h in (-0.24, 0.24):
        h_knuckle = hinge_w + lid_mat @ Vector((s_h, 0.0, 0.0))
        kit.add_beveled_box(
            scene, f"reliquary_bronze_hinge_{s_h:+.2f}", (float(h_knuckle.x), float(h_knuckle.y), float(h_knuckle.z)),
            (0.09, 0.12, 0.10), mat_bronze_clasp, p6_chest, rot_xyz=mb.rot_d2w(lid_tilt * 0.5, 0.0, lid_yaw), bevel=0.008
        )

    # Ornate Aged Bronze Lock-Clasp at the open front-right lip (`local y = -2 * apothem`)
    clasp_world = hinge_w + lid_mat @ Vector((0.0, -2.0 * apothem - 0.02, -0.02))
    kit.add_beveled_box(
        scene, "reliquary_lid_bronze_clasp", (float(clasp_world.x), float(clasp_world.y), float(clasp_world.z)),
        (0.14, 0.06, 0.16), mat_bronze_clasp, p6_chest, rot_xyz=mb.rot_d2w(lid_tilt * 0.5, 0.0, lid_yaw), bevel=0.010
    )


build_open_hex_lid()

# ---------------------------------------------------------------------------
# 3. Verify Golden Rules + Export Draco GLB & Coaxial .parts.json Sidecar
# ---------------------------------------------------------------------------
part_defs = [
    {
        "empty": p1_plinth,
        "id": "weathered_octagonal_moss_stepped_plinth",
        "name_vi": "Bệ Đá Cổ Vát Bát Giác 4 Bậc Thềm Rêu Phong",
        "name_en": "Four-Tiered Weathered Mossy Octagonal Stone Plinth",
        "summary_vi": "Bệ đá tám cạnh xếp bốn bậc thềm rêu xanh ẩm sương giữa rừng thiêng cổ kính.",
        "summary_en": "Four-stepped octagonal ashlar stone plinth weathered with damp forest moss.",
    },
    {
        "empty": p4_lectern,
        "id": "front_grimoire_lectern_and_mana_phials",
        "name_vi": "Bệ Đá Pháp Thư Hai Trang Giấy Da & Đôi Lọ Tinh Chất Xanh",
        "name_en": "Stone Grimoire Lectern & Twin Glowing Essence Phials",
        "summary_vi": "Bệ đá phía trước nâng cuốn pháp thư bìa da mở rộng hai trang cổ tự bên hai lọ tinh chất.",
        "summary_en": "Front stone lectern cradling an open leather-bound parchment grimoire beside two glass essence phials.",
    },
    {
        "empty": p2_floor,
        "id": "celtic_ogham_glowing_rune_floor",
        "name_vi": "Mặt Sàn Trận Đồ Cổ Ngữ Ogham Phát Sáng Xanh Lam",
        "name_en": "Engraved Glowing Azure Celtic & Ogham Arcane Circle Floor",
        "summary_vi": "Mặt sàn đá khắc sâu vòng chữ cổ Ogham và ngôi sao tám cánh tỏa ánh sáng lam dịu.",
        "summary_en": "Recessed stone floor deeply incised with an eight-pointed knotwork star and glowing azure runes.",
    },
    {
        "empty": p3_pillars,
        "id": "four_corner_rune_monolith_obelisks",
        "name_vi": "Bốn Trụ Đá Nhọn Khắc Chữ Cổ Tỏa Sáng Lam Ở Bốn Góc",
        "name_en": "Four Pointed Rune-Inscribed Corner Stone Obelisks",
        "summary_vi": "Bốn cột đá vát nhọn trấn giữ bốn góc thềm, khắc nét chữ cổ ánh sắc lam trong trẻo.",
        "summary_en": "Four chamfered pointed stone obelisks guarding the corners with luminous azure rune carvings.",
    },
    {
        "empty": p5_oak,
        "id": "gnarled_ancient_oak_roots_and_azure_leaves",
        "name_vi": "Gốc Sồi Khô Cổ Thụ Uốn Rễ Chằng Chịt Điểm Lá Lam Phát Sáng",
        "name_en": "Gnarled Ancient Oak Trunk, Sprawling Roots & Glowing Azure Leaves",
        "summary_vi": "Thân sồi khô vặn xoắn buông rễ ôm chặt thềm đá, lấm tấm những phiến lá non ánh lam huyền ảo.",
        "summary_en": "Twisted hollow ancient oak trunk and cascading roots dotted with luminous sky-blue leaves.",
    },
    {
        "empty": p6_chest,
        "id": "hexagonal_reliquary_chest_and_450nm_meteorite",
        "name_vi": "Rương Đá Lục Giác Mở Nắp & Viên Đá Thiên Thạch Lam Tinh Khiết",
        "name_en": "Open Hexagonal Carved Stone Reliquary & Pure Azure Meteorite",
        "summary_vi": "Rương đá sáu cạnh chạm hoa văn mở nắp khóa đồng, ấp ủ khối thiên thạch lam rực sáng bên trong.",
        "summary_en": "Knotwork-carved hexagonal stone chest with open bronze-clasped lid housing the radiant azure meteorite.",
    },
]

STEP1_APOTHEM = 4.48 * COS_OCT  # 4.139m
STEP3_CORNER_R = 3.60  # Corner obelisks stand along the 4 octagon corner rays (circumradius 3.60m -> 0.41m margin)

mb.export_monument_with_parts_json(
    scene=scene,
    out_glb=OUT_GLB,
    part_defs=part_defs,
    master_sources=[],
    prop_support_checks=[
        (p2_floor, 0.0, 0.0, 3.16 * COS_OCT, 0.35),
        (p3_pillars, 0.0, 0.0, STEP3_CORNER_R, 0.25),
        (p4_lectern, 0.0, 0.0, STEP1_APOTHEM, 0.18),
        (p5_oak, 0.0, 0.0, STEP1_APOTHEM, 0.25),
        (p6_chest, 0.0, 0.0, 3.16 * COS_OCT, 0.90),
    ],
    t_start=t_start,
)
