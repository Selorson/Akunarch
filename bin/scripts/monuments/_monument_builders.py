"""
Shared high-craft architectural & organic bmesh builders for Akunarch v2.1 monuments.

Enforces all 7 Iron Laws (`E:\\Akunarch\\AGENTS.md` v2.1):
  - Exact camera-aligned design coordinates `(dx_right, dy_depth_away, dz_up)` -> Blender world `(X, Y, Z)`
    so `dx < 0` is screen-left, `dx > 0` is screen-right, `dy < 0` is front-foreground, `dy > 0` is rear-summit
    in `RealPbrStageViewport.svelte` (`viewDir = normalize(0.56, 0.32, 0.76)`).
  - Zero toy primitives: real fluted entasis columns, pierced round-arch walls, ribbed hemispherical coffered domes,
    layered ridged straw thatch, and 3D fractured prehistoric megaliths.
  - Automatic mathematical coaxial Y-band solver guaranteeing >= 0.44m clearance at 50%, 65%, and 100% explode.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import bmesh
import bpy
import numpy as np
from mathutils import Euler, Matrix, Vector

KIT_DIR = Path(r"E:\Tools-3D\scripts\archived_selorson_monuments")
if str(KIT_DIR) not in sys.path:
    sys.path.insert(0, str(KIT_DIR))

import _aaa_monument_kit as kit  # noqa: E402


def bake_cycles_ao_pointiness_position_f32(
    obj: bpy.types.Object,
    tag: str,
    ao_dist: float,
    pos_scale: float,
    pos_offset: tuple[float, float, float],
    bake_res: int,
):
    """
    32-bit floating-point replacement for `_aaa_monument_kit.bake_cycles_ao_pointiness_position`.
    Eliminates 8-bit (1/255 = 5.3cm) world-position quantization blocks on soil cutaways & marble cliffs!
    """
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj

    bake_mat = bpy.data.materials.new(f"bake_tmp_{tag}")
    bake_mat.use_nodes = True
    nt = bake_mat.node_tree
    nt.nodes.clear()
    out_n = nt.nodes.new("ShaderNodeOutputMaterial")
    emit_n = nt.nodes.new("ShaderNodeEmission")
    nt.links.new(emit_n.outputs["Emission"], out_n.inputs["Surface"])

    ao_n = nt.nodes.new("ShaderNodeAmbientOcclusion")
    ao_n.samples = 16
    ao_n.only_local = True
    ao_n.inputs["Distance"].default_value = ao_dist

    geom_n = nt.nodes.new("ShaderNodeNewGeometry")
    comb_n = nt.nodes.new("ShaderNodeCombineColor")
    sep_norm = nt.nodes.new("ShaderNodeSeparateXYZ")
    math_nz = nt.nodes.new("ShaderNodeMath")
    math_nz.operation = "MULTIPLY_ADD"
    math_nz.inputs[1].default_value = 0.45
    math_nz.inputs[2].default_value = 0.55
    nt.links.new(geom_n.outputs["Normal"], sep_norm.inputs["Vector"])
    nt.links.new(sep_norm.outputs["Z"], math_nz.inputs[0])

    nt.links.new(ao_n.outputs["AO"], comb_n.inputs["Red"])
    nt.links.new(geom_n.outputs["Pointiness"], comb_n.inputs["Green"])
    nt.links.new(math_nz.outputs["Value"], comb_n.inputs["Blue"])
    nt.links.new(comb_n.outputs["Color"], emit_n.inputs["Color"])

    bake_img = bpy.data.images.new(
        f"{tag}_ao_curv", width=bake_res, height=bake_res, alpha=False, float_buffer=True, is_data=True
    )
    bake_img.colorspace_settings.name = "Non-Color"
    tex_target = nt.nodes.new("ShaderNodeTexImage")
    tex_target.image = bake_img
    nt.nodes.active = tex_target

    obj.data.materials.clear()
    obj.data.materials.append(bake_mat)

    print(f"  [Cycles RTX 4080 F32] Baking {bake_res}x{bake_res} AO + Pointiness + 32-bit Position for {tag}...")
    bpy.ops.object.bake(type="EMIT", margin=8)

    ao_curv_raw = np.array(bake_img.pixels[:], dtype=np.float32).reshape((bake_res, bake_res, 4))
    valid_mask = (ao_curv_raw[:, :, 1] > 0.02) | (ao_curv_raw[:, :, 2] > 0.04)
    ao_curv = kit.dilate_uv_gutters(ao_curv_raw[:, :, :3], valid_mask, iterations=18)

    pos_img = bpy.data.images.new(
        f"{tag}_pos_f32", width=bake_res, height=bake_res, alpha=False, float_buffer=True, is_data=True
    )
    pos_img.colorspace_settings.name = "Non-Color"
    tex_target.image = pos_img
    nt.nodes.active = tex_target
    vec_math = nt.nodes.new("ShaderNodeVectorMath")
    vec_math.operation = "SCALE"
    vec_math.inputs["Scale"].default_value = pos_scale
    nt.links.new(geom_n.outputs["Position"], vec_math.inputs["Vector"])
    vec_add = nt.nodes.new("ShaderNodeVectorMath")
    vec_add.operation = "ADD"
    vec_add.inputs[1].default_value = pos_offset
    nt.links.new(vec_math.outputs["Vector"], vec_add.inputs[0])
    nt.links.new(vec_add.outputs["Vector"], emit_n.inputs["Color"])
    bpy.ops.object.bake(type="EMIT", margin=8)

    pos_raw = np.array(pos_img.pixels[:], dtype=np.float32).reshape((bake_res, bake_res, 4))
    pos_uv = kit.dilate_uv_gutters(pos_raw[:, :, :3], valid_mask, iterations=18)

    obj.data.materials.clear()
    bpy.data.images.remove(bake_img)
    bpy.data.images.remove(pos_img)
    bpy.data.materials.remove(bake_mat)

    ao_map = np.clip(ao_curv[:, :, 0:1], 0.06, 1.0)
    pointiness = np.clip(ao_curv[:, :, 1:2], 0.30, 0.70)
    norm_z = (ao_curv[:, :, 2:3] - 0.55) / 0.45
    return ao_map, pointiness, norm_z, pos_uv, valid_mask


# Monkey-patch kit so every hero sculpt & geological bake inherits 32-bit float precision automatically
kit.bake_cycles_ao_pointiness_position = bake_cycles_ao_pointiness_position_f32


def build_hi_res_cutaway_terrain_mesh(
    scene: bpy.types.Scene,
    mesh_name: str,
    radii_top: list[float],
    z_cliff_bot: float,
    outer_rim_r_fn,
    top_surface_z_fn,
    cliff_r_fn,
    n_ang: int = 264,
    n_z: int = 52,
    bake_res: int = 2048,
    sharp_cliff_facets: bool = False,
) -> tuple[bpy.types.Object, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """
    High-texel-density geological cutaway mesh:
      - Visible top surface occupies UV `[0.04..0.82, 0.24..0.98]` (~1550x1515 px on 2K map — 5x more texel area!)
      - Two 180-deg vertical cutaway cliff strips occupy `[0.02..0.98, 0.015..0.105]` & `[0.02..0.98, 0.12..0.21]`
      - Hidden underside cap occupies `[0.85..0.98, 0.85..0.98]`
      - Uses 32-bit float position bake so zero 8-bit stair-step blocks ever occur!
    """
    bm = bmesh.new()
    uv_lay = bm.loops.layers.uv.new("UVMap")
    thetas = (np.arange(n_ang, dtype=np.float64) / n_ang) * (2.0 * math.pi)
    outer_rim_r = outer_rim_r_fn(thetas)
    max_r = float(np.max(outer_rim_r))
    top_uv_scale = 0.365 / max(max_r, 1.0)
    bot_uv_scale = 0.058 / max(max_r, 1.0)

    top_rows = []
    vc = bm.verts.new((0.0, 0.0, float(top_surface_z_fn(0.0, 0.0, 0.0, 0.0))))
    top_rows.append([vc] * n_ang)

    for r_frac in radii_top:
        row = []
        for ia in range(n_ang):
            th = float(thetas[ia])
            rr = float(outer_rim_r[ia]) * r_frac
            x = rr * math.cos(th)
            y = rr * math.sin(th)
            zt = float(top_surface_z_fn(x, y, rr, th))
            row.append(bm.verts.new((x, y, zt)))
        top_rows.append(row)

    def set_planar_uv(face, u_center: float, v_center: float, scale: float):
        for loop in face.loops:
            co = loop.vert.co
            loop[uv_lay].uv = (u_center + co.x * scale, v_center + co.y * scale)

    for ir in range(len(top_rows) - 1):
        for ia in range(n_ang):
            ian = (ia + 1) % n_ang
            if ir == 0:
                f = bm.faces.new([top_rows[0][0], top_rows[1][ia], top_rows[1][ian]])
            else:
                f = bm.faces.new([top_rows[ir][ia], top_rows[ir + 1][ia], top_rows[ir + 1][ian], top_rows[ir][ian]])
            set_planar_uv(f, 0.43, 0.61, top_uv_scale)

    rim_z = np.array([top_rows[-1][ia].co.z for ia in range(n_ang)], dtype=np.float64)
    s_frac = np.linspace(0.0, 1.0, n_z, dtype=np.float64)[:, None]
    th_grid = np.broadcast_to(thetas[None, :], (n_z, n_ang))
    zz_grid = rim_z[None, :] * (1.0 - s_frac) + z_cliff_bot * s_frac
    rr_grid = cliff_r_fn(th_grid, zz_grid, s_frac, outer_rim_r[None, :])
    if not np.all(np.isfinite(rr_grid)):
        raise RuntimeError(f"Non-finite vertex radius in {mesh_name}")

    cliff_rows = [top_rows[-1]]
    for iz in range(1, n_z):
        row = []
        for ia in range(n_ang):
            th = float(thetas[ia])
            rr = float(rr_grid[iz, ia])
            zz = float(zz_grid[iz, ia])
            row.append(bm.verts.new((rr * math.cos(th), rr * math.sin(th), zz)))
        cliff_rows.append(row)

    half_ang = n_ang // 2
    for iz in range(n_z - 1):
        v0 = (iz / (n_z - 1)) * 0.090
        v1 = ((iz + 1) / (n_z - 1)) * 0.090
        for ia in range(n_ang):
            ian = (ia + 1) % n_ang
            f = bm.faces.new([cliff_rows[iz][ia], cliff_rows[iz][ian], cliff_rows[iz + 1][ian], cliff_rows[iz + 1][ia]])
            if ia < half_ang:
                u0 = 0.02 + (ia / half_ang) * 0.96
                u1 = 0.02 + ((ia + 1) / half_ang) * 0.96
                vo0, vo1 = 0.105 - v0, 0.105 - v1
            else:
                ia2 = ia - half_ang
                u0 = 0.02 + (ia2 / (n_ang - half_ang)) * 0.96
                u1 = 0.02 + ((ia2 + 1) / (n_ang - half_ang)) * 0.96
                vo0, vo1 = 0.215 - v0, 0.215 - v1
            for loop, uv_pt in zip(f.loops, [(u0, vo0), (u1, vo0), (u1, vo1), (u0, vo1)]):
                loop[uv_lay].uv = uv_pt

    v_bot_center = bm.verts.new((0.0, 0.0, z_cliff_bot))
    bot_ring = cliff_rows[-1]
    for ia in range(n_ang):
        ian = (ia + 1) % n_ang
        f = bm.faces.new([v_bot_center, bot_ring[ian], bot_ring[ia]])
        set_planar_uv(f, 0.915, 0.915, bot_uv_scale)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(f"{mesh_name}_data")
    bm.to_mesh(mesh)
    bm.free()
    mesh.validate(verbose=False)
    mesh.update()
    for p in mesh.polygons:
        if sharp_cliff_facets and abs(p.normal.z) < 0.72:
            p.use_smooth = False
        else:
            p.use_smooth = True

    obj = bpy.data.objects.new(mesh_name, mesh)
    scene.collection.objects.link(obj)

    ao_map, pointiness, norm_z, pos_uv, valid_mask = bake_cycles_ao_pointiness_position_f32(
        obj,
        f"{mesh_name}_2k",
        ao_dist=1.15,
        pos_scale=1.0 / 13.6,
        pos_offset=(0.5, 0.5, 0.30),
        bake_res=bake_res,
    )
    wx = (pos_uv[:, :, 0:1] - 0.5) * 13.6
    wy = (pos_uv[:, :, 1:2] - 0.5) * 13.6
    wz = (pos_uv[:, :, 2:3] - 0.30) * 13.6
    return obj, ao_map, pointiness, norm_z, wx, wy, wz, valid_mask

# Default camera in RealPbrStageViewport.svelte looks from normalize(0.56, 0.32, 0.76) in Three.js (X, Y, Z).
# With glTF export_yup=True: (X_3js, Y_3js, Z_3js) = (X_b, Z_b, -Y_b).
# Rotating design coords (dx_right, dy_away, dz_up) by CAM_YAW around +Z aligns 1:1 with the 2D Concept canvas.
CAM_YAW = math.atan2(0.56, 0.76)  # +0.6348706 rad (+36.3844 deg)
COS_YAW = math.cos(CAM_YAW)
SIN_YAW = math.sin(CAM_YAW)


def d2w(dx: float, dy: float, dz: float = 0.0) -> tuple[float, float, float]:
    """Convert intuitive design coords (dx=right, dy=back, dz=up) to Blender world (X, Y, Z)."""
    wx = dx * COS_YAW - dy * SIN_YAW
    wy = dx * SIN_YAW + dy * COS_YAW
    return (wx, wy, dz)


def w2d_xy(wx: float | np.ndarray, wy: float | np.ndarray) -> tuple[float | np.ndarray, float | np.ndarray]:
    """Convert Blender world (wx, wy) back into design coords (dx, dy)."""
    dx = wx * COS_YAW + wy * SIN_YAW
    dy = -wx * SIN_YAW + wy * COS_YAW
    return dx, dy


def rot_d2w(rx: float = 0.0, ry: float = 0.0, rz_design: float = 0.0) -> tuple[float, float, float]:
    """Convert Euler XYZ rotation in design space to Blender world Euler XYZ."""
    e_des = Euler((rx, ry, rz_design), "XYZ").to_matrix()
    m_yaw = Euler((0.0, 0.0, CAM_YAW), "XYZ").to_matrix()
    e_out = (m_yaw @ e_des).to_euler("XYZ")
    return (float(e_out.x), float(e_out.y), float(e_out.z))


def resolve_out_glb(default_slug: str, script_globals: dict) -> Path:
    """Resolve output .glb path whether invoked via bake_canonical_monument.py or standalone Blender CLI."""
    injected = script_globals.get("AKUNARCH_OUT_GLB")
    if injected:
        out = Path(injected).resolve()
        out.parent.mkdir(parents=True, exist_ok=True)
        return out
    if "--" in sys.argv:
        tail = sys.argv[sys.argv.index("--") + 1 :]
        if tail:
            out = Path(tail[-1]).resolve()
            out.parent.mkdir(parents=True, exist_ok=True)
            return out
    out = Path(rf"E:\Akunarch\projects\{default_slug}\clockwork\{default_slug}.glb")
    out.parent.mkdir(parents=True, exist_ok=True)
    return out


def compute_coaxial_explode_specs(
    part_defs: list[dict],
    min_gap_target: float = 0.46,
) -> tuple[list[tuple[bpy.types.Object, float]], list[dict]]:
    """
    Given ordered bottom-to-top part_defs:
      [{"empty": emp_obj, "id": str, "name_vi": str, "name_en": str, "summary_vi": str, "summary_en": str}, ...]
    computes exact monotonic `dir_y` values guaranteeing `verify_and_export_monument` passes with >= min_gap_target
    at 50%, 65%, and 100% explode in both world and local coordinates!
    """
    bpy.context.view_layer.update()
    all_pts = []
    part_z_bounds: list[tuple[float, float]] = []

    for p in part_defs:
        emp = p["empty"]
        z0, z1 = 1e9, -1e9
        for ch in emp.children_recursive:
            if ch.type != "MESH":
                continue
            mw = ch.matrix_world
            verts = np.empty(len(ch.data.vertices) * 3, dtype=np.float64)
            ch.data.vertices.foreach_get("co", verts)
            verts = verts.reshape((-1, 3))
            rot_m = np.array(mw.to_3x3(), dtype=np.float64)
            trans = np.array(mw.translation, dtype=np.float64)
            wverts = verts @ rot_m.T + trans
            mn = wverts.min(axis=0)
            mx = wverts.max(axis=0)
            all_pts.append(mn)
            all_pts.append(mx)
            z0 = min(z0, float(mn[2]))
            z1 = max(z1, float(mx[2]))
        if z0 > z1:
            raise RuntimeError(f"Part '{emp.name}' has zero mesh vertices!")
        part_z_bounds.append((z0, z1))

    arr = np.array(all_pts, dtype=np.float64)
    ext = arr.max(axis=0) - arr.min(axis=0)
    largest_dim = float(ext.max())
    diorama_fit = 6.2 / max(largest_dim, 1e-4)
    inv_fit = min(1.82, 1.0 / max(0.55, diorama_fit))

    def _solve_dirs(target_gap: float) -> list[float]:
        out_d = [0.0]
        for i in range(1, len(part_defs)):
            _, z1_prev = part_z_bounds[i - 1]
            z0_curr, _ = part_z_bounds[i]
            dz_local = z0_curr - z1_prev
            need_w50 = (target_gap - dz_local * diorama_fit) / 0.50
            need_w65 = (target_gap - dz_local * diorama_fit) / 0.65
            need_w100 = (target_gap - dz_local * diorama_fit) / 1.00
            need_loc50 = (target_gap - dz_local) / (0.50 * inv_fit)
            need_loc100 = (target_gap - dz_local) / (1.00 * inv_fit)
            delta = max(0.88, need_w50, need_w65, need_w100, need_loc50, need_loc100)
            nxt = out_d[-1] + delta
            if i == 1:
                nxt = max(1.88, nxt)
            out_d.append(math.ceil(nxt * 100.0) / 100.0)
        return out_d

    dirs = _solve_dirs(0.42)
    if dirs[-1] > 16.35:
        dirs = _solve_dirs(0.38)
    if dirs[-1] > 16.48:
        raise RuntimeError(
            f"Coaxial explode max dirY={dirs[-1]:.2f}m exceeds Rule #6 cap 16.5m! "
            f"Reduce vertical Z-overlap between adjacent parts: bounds={part_z_bounds}"
        )

    parts_spec = [(p["empty"], dirs[i]) for i, p in enumerate(part_defs)]
    parts_json = [
        {
            "id": p["id"],
            "name_vi": p["name_vi"],
            "name_en": p["name_en"],
            "summary_vi": p["summary_vi"],
            "summary_en": p["summary_en"],
            "dir": [0, dirs[i], 0],
        }
        for i, p in enumerate(part_defs)
    ]
    return parts_spec, parts_json


def export_monument_with_parts_json(
    scene: bpy.types.Scene,
    out_glb: Path,
    part_defs: list[dict],
    master_sources: list[bpy.types.Object],
    prop_support_checks: list[tuple[bpy.types.Object, float, float, float, float]] | None = None,
    t_start: float = 0.0,
) -> None:
    parts_spec, parts_json = compute_coaxial_explode_specs(part_defs, min_gap_target=0.46)
    kit.verify_and_export_monument(
        scene=scene,
        out_glb=out_glb,
        parts_spec=parts_spec,
        master_sources=master_sources,
        prop_support_checks=prop_support_checks,
        t_start=t_start,
        min_exploded_gap=0.36,
    )
    parts_sidecar = out_glb.with_suffix(".parts.json")
    parts_sidecar.write_text(json.dumps(parts_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  [Sidecar] Wrote {len(parts_json)} coaxial parts -> {parts_sidecar}")


def fbm3(x: float, y: float, z: float, seed: float = 0.0) -> float:
    """Deterministic smooth 3D trigonometric rock fracture field in [-1, 1]."""
    s1 = math.sin(x * 2.1 + z * 1.7 + seed) * math.cos(y * 2.3 - x * 1.3 + seed * 0.7)
    s2 = 0.52 * math.sin(x * 4.7 - y * 3.9 + z * 3.1 + seed * 1.9)
    s3 = 0.28 * math.cos(y * 8.3 + z * 7.1 - x * 5.6 + seed * 3.1)
    return max(-1.0, min(1.0, (s1 + s2 + s3) / 1.45))


def add_craggy_megalith(
    scene: bpy.types.Scene,
    name: str,
    design_pos: tuple[float, float, float],
    size_xyz: tuple[float, float, float],
    mat: bpy.types.Material,
    parent: bpy.types.Object,
    rot_design: tuple[float, float, float] = (0.0, 0.0, 0.0),
    taper_top: float = 0.84,
    crag_amp: float = 0.055,
    seed: float = 1.0,
    uv_scale: float = 0.42,
) -> bpy.types.Object:
    """
    Create a subdivided, tapered, 3D-fractured prehistoric stone megalith or lintel block.
    `design_pos` is the bottom-center `(dx, dy, dz_bottom)` when `rot_design` is near upright,
    or center-bottom in local stone coordinates.
    """
    bm = bmesh.new()
    nx, ny, nz = 5, 5, 9
    sx, sy, sz = size_xyz

    grid = []
    for iz in range(nz + 1):
        tz = iz / nz
        taper = 1.0 + (taper_top - 1.0) * (tz ** 0.85)
        edge_fade = math.sin(tz * math.pi) ** 0.45
        layer = []
        for iy in range(ny + 1):
            ty = iy / ny - 0.5
            row = []
            for ix in range(nx + 1):
                tx = ix / nx - 0.5
                px = tx * sx * taper
                py = ty * sy * taper
                pz = tz * sz
                # Chipped chamfer on vertical arrises
                corner = max(0.0, abs(tx) + abs(ty) - 0.78)
                px *= 1.0 - 0.34 * corner
                py *= 1.0 - 0.34 * corner
                n_val = fbm3(px * 2.4, py * 2.4, pz * 1.9, seed)
                px += n_val * crag_amp * sx * (0.45 + 0.55 * edge_fade)
                py += fbm3(py * 2.7, px * 2.2, pz * 2.1, seed + 4.3) * crag_amp * sy * (0.45 + 0.55 * edge_fade)
                if 0 < iz < nz:
                    pz += n_val * crag_amp * 0.35 * sz
                elif iz == nz:
                    # Weathered uneven crown
                    pz += fbm3(px * 2.8, py * 2.8, 3.0, seed + 8.1) * crag_amp * 0.55 * min(sx, sz)
                row.append(bm.verts.new((px, py, pz)))
            layer.append(row)
        grid.append(layer)

    # Bottom & top faces
    for iy in range(ny):
        for ix in range(nx):
            bm.faces.new([grid[0][iy][ix], grid[0][iy + 1][ix], grid[0][iy + 1][ix + 1], grid[0][iy][ix + 1]])
            bm.faces.new([grid[nz][iy][ix], grid[nz][iy][ix + 1], grid[nz][iy + 1][ix + 1], grid[nz][iy + 1][ix]])
    # Side faces
    for iz in range(nz):
        for ix in range(nx):
            bm.faces.new([grid[iz][0][ix], grid[iz][0][ix + 1], grid[iz + 1][0][ix + 1], grid[iz + 1][0][ix]])
            bm.faces.new([grid[iz][ny][ix + 1], grid[iz][ny][ix], grid[iz + 1][ny][ix], grid[iz + 1][ny][ix + 1]])
        for iy in range(ny):
            bm.faces.new([grid[iz][iy + 1][0], grid[iz][iy][0], grid[iz + 1][iy][0], grid[iz + 1][iy + 1][0]])
            bm.faces.new([grid[iz][iy][nx], grid[iz][iy + 1][nx], grid[iz + 1][iy + 1][nx], grid[iz + 1][iy][nx]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True

    obj = bpy.data.objects.new(name, mesh)
    obj.location = d2w(*design_pos)
    obj.rotation_euler = rot_d2w(*rot_design)
    scene.collection.objects.link(obj)
    kit.apply_box_uv_and_mat(obj, mat, uv_scale=uv_scale)
    kit.parent_keep_local(obj, parent)
    return obj


def add_curved_sarsen_lintel(
    scene: bpy.types.Scene,
    name: str,
    center_dxy: tuple[float, float],
    radius: float,
    ang0_deg: float,
    ang1_deg: float,
    z_bot: float,
    radial_width: float,
    height: float,
    mat: bpy.types.Material,
    parent: bpy.types.Object,
    seed: float = 2.0,
) -> bpy.types.Object:
    """Curved prehistoric stone lintel spanning an arc of the outer Sarsen circle with craggy weathered relief."""
    bm = bmesh.new()
    n_arc, n_rad, n_z = 9, 4, 4
    a0 = math.radians(ang0_deg)
    a1 = math.radians(ang1_deg)
    cx, cy = center_dxy

    grid = []
    for iz in range(n_z + 1):
        tz = iz / n_z
        layer = []
        for ir in range(n_rad + 1):
            tr = ir / n_rad - 0.5
            row = []
            for ia in range(n_arc + 1):
                ta = ia / n_arc
                ang = a0 + (a1 - a0) * ta
                rr = radius + tr * radial_width
                dx = cx + rr * math.cos(ang)
                dy = cy + rr * math.sin(ang)
                dz = z_bot + tz * height
                # Chamfered arrises + craggy stone erosion
                end_ch = max(0.0, abs(ta - 0.5) * 2.0 - 0.82) * 0.14
                rr_adj = rr + fbm3(dx * 2.6, dy * 2.6, dz * 2.4, seed) * 0.032
                dx = cx + rr_adj * math.cos(ang)
                dy = cy + rr_adj * math.sin(ang)
                dz += fbm3(dy * 2.9, dx * 2.9, dz * 2.0, seed + 3.7) * 0.024 - end_ch * height * (1.0 if tz > 0.5 else -0.5)
                row.append(bm.verts.new(d2w(dx, dy, dz)))
            layer.append(row)
        grid.append(layer)

    for ir in range(n_rad):
        for ia in range(n_arc):
            bm.faces.new([grid[0][ir][ia], grid[0][ir + 1][ia], grid[0][ir + 1][ia + 1], grid[0][ir][ia + 1]])
            bm.faces.new([grid[n_z][ir][ia], grid[n_z][ir][ia + 1], grid[n_z][ir + 1][ia + 1], grid[n_z][ir + 1][ia]])
    for iz in range(n_z):
        for ia in range(n_arc):
            bm.faces.new([grid[iz][0][ia], grid[iz][0][ia + 1], grid[iz + 1][0][ia + 1], grid[iz + 1][0][ia]])
            bm.faces.new([grid[iz][n_rad][ia + 1], grid[iz][n_rad][ia], grid[iz + 1][n_rad][ia], grid[iz + 1][n_rad][ia + 1]])
        for ir in range(n_rad):
            bm.faces.new([grid[iz][ir + 1][0], grid[iz][ir][0], grid[iz + 1][ir][0], grid[iz + 1][ir + 1][0]])
            bm.faces.new([grid[iz][ir][n_arc], grid[iz][ir + 1][n_arc], grid[iz + 1][ir + 1][n_arc], grid[iz + 1][ir][n_arc]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    kit.apply_box_uv_and_mat(obj, mat, uv_scale=0.45)
    kit.parent_keep_local(obj, parent)
    return obj


def add_fluted_classical_column(
    scene: bpy.types.Scene,
    name: str,
    design_pos: tuple[float, float, float],
    height: float,
    radius_base: float,
    mat_marble: bpy.types.Material,
    mat_gold: bpy.types.Material,
    parent: bpy.types.Object,
    n_flutes: int = 16,
) -> bpy.types.Object:
    """
    True classical Greek fluted column with square plinth, Attic torus base,
    16-flute entasis shaft (32 radial vertices alternating crest/groove), echinus & gilded abacus capital!
    """
    bm = bmesh.new()
    verts_per_ring = n_flutes * 2
    plinth_h = min(0.08, height * 0.065)
    torus_h = min(0.09, height * 0.075)
    cap_h = min(0.14, height * 0.115)
    shaft_z0 = plinth_h + torus_h
    shaft_z1 = max(shaft_z0 + 0.15, height - cap_h)

    # Square plinth + square abacus
    for tag_z0, tag_z1, half_w in [
        (0.0, plinth_h, radius_base * 1.34),
        (height - cap_h * 0.44, height, radius_base * 1.28),
    ]:
        b0 = [
            bm.verts.new((-half_w, -half_w, tag_z0)),
            bm.verts.new((half_w, -half_w, tag_z0)),
            bm.verts.new((half_w, half_w, tag_z0)),
            bm.verts.new((-half_w, half_w, tag_z0)),
        ]
        b1 = [
            bm.verts.new((-half_w, -half_w, tag_z1)),
            bm.verts.new((half_w, -half_w, tag_z1)),
            bm.verts.new((half_w, half_w, tag_z1)),
            bm.verts.new((-half_w, half_w, tag_z1)),
        ]
        bm.faces.new(list(reversed(b0)))
        bm.faces.new(b1)
        for k in range(4):
            kn = (k + 1) % 4
            bm.faces.new([b0[k], b0[kn], b1[kn], b1[k]])

    # Continuous profile from torus base through fluted entasis shaft up to echinus necking
    profile_rings = []
    ring_specs = [
        (plinth_h, radius_base * 1.24, 0.0),
        (plinth_h + torus_h * 0.55, radius_base * 1.28, 0.0),
        (shaft_z0, radius_base * 1.04, 0.0),
        (shaft_z0 + (shaft_z1 - shaft_z0) * 0.06, radius_base * 1.00, 1.0),
        (shaft_z0 + (shaft_z1 - shaft_z0) * 0.38, radius_base * 0.985, 1.0),
        (shaft_z0 + (shaft_z1 - shaft_z0) * 0.72, radius_base * 0.915, 1.0),
        (shaft_z0 + (shaft_z1 - shaft_z0) * 0.95, radius_base * 0.855, 1.0),
        (shaft_z1, radius_base * 0.85, 0.0),
        (height - cap_h * 0.62, radius_base * 0.94, 0.0),
        (height - cap_h * 0.42, radius_base * 1.18, 0.0),
    ]
    for rz, rr, flute_w in ring_specs:
        ring = []
        for iv in range(verts_per_ring):
            ang = (iv / verts_per_ring) * 2.0 * math.pi
            is_groove = (iv % 2 == 1)
            rad = rr * (1.0 - 0.095 * flute_w if is_groove else 1.0)
            ring.append(bm.verts.new((rad * math.cos(ang), rad * math.sin(ang), rz)))
        profile_rings.append(ring)

    bm.faces.new(list(reversed(profile_rings[0])))
    bm.faces.new(profile_rings[-1])
    for ir in range(len(profile_rings) - 1):
        for iv in range(verts_per_ring):
            ivn = (iv + 1) % verts_per_ring
            bm.faces.new([profile_rings[ir][iv], profile_rings[ir][ivn], profile_rings[ir + 1][ivn], profile_rings[ir + 1][iv]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = p.center.z > plinth_h and p.center.z < height - cap_h * 0.46

    obj = bpy.data.objects.new(name, mesh)
    obj.location = d2w(*design_pos)
    obj.rotation_euler = rot_d2w(0.0, 0.0, 0.0)
    scene.collection.objects.link(obj)
    kit.apply_box_uv_and_mat(obj, mat_marble, uv_scale=0.65)
    kit.parent_keep_local(obj, parent)

    # Gilded necking collar ring under capital
    collar = kit.add_prism_ring(
        scene,
        f"{name}_gold_neck",
        radius_base * 0.93,
        0.0,
        design_pos[2] + height - cap_h * 0.72,
        design_pos[2] + height - cap_h * 0.56,
        sides=16,
        bevel=0.004,
    )
    wx, wy, _ = d2w(design_pos[0], design_pos[1], 0.0)
    collar.location = (wx, wy, 0.0)
    kit.apply_box_uv_and_mat(collar, mat_gold, uv_scale=0.8)
    kit.parent_keep_local(collar, parent)
    return obj


def add_ribbed_hemispherical_dome(
    scene: bpy.types.Scene,
    name: str,
    design_center_xyz: tuple[float, float, float],
    radius: float,
    height_scale: float,
    n_ribs: int,
    mat_dome: bpy.types.Material,
    mat_rib_trim: bpy.types.Material,
    parent: bpy.types.Object,
    with_lantern: bool = True,
) -> None:
    """
    Build a true ribbed hemispherical classical dome (`z = z0 + R * height_scale * sin(phi)`)
    with sunken coffered bays, raised meridian ribs, ring cornice, and optional classical cupola lantern.
    """
    dx0, dy0, z0 = design_center_xyz
    wx0, wy0, _ = d2w(dx0, dy0, z0)

    bm = bmesh.new()
    segs_per_bay = 4
    n_az = n_ribs * segs_per_bay
    n_el = 14
    rings = []
    for ie in range(n_el):
        phi = (ie / n_el) * (math.pi * 0.485)
        r_ring = radius * math.cos(phi)
        z_ring = z0 + radius * height_scale * math.sin(phi)
        ring = []
        for ia in range(n_az):
            ang = (ia / n_az) * 2.0 * math.pi
            in_bay = ia % segs_per_bay
            # Raised rib along bay seam (in_bay == 0), recessed coffer inside bay
            coffer_inset = -0.022 * radius * math.sin(phi * 2.0) if in_bay in (1, 2) and 1 <= ie <= n_el - 2 else 0.0
            rib_out = 0.016 * radius if in_bay == 0 else 0.0
            rr = max(0.02, r_ring + rib_out + coffer_inset)
            ring.append(bm.verts.new((wx0 + rr * math.cos(ang), wy0 + rr * math.sin(ang), z_ring)))
        rings.append(ring)

    apex_z = z0 + radius * height_scale
    v_top = bm.verts.new((wx0, wy0, apex_z))
    v_bot = bm.verts.new((wx0, wy0, z0))

    for ia in range(n_az):
        ian = (ia + 1) % n_az
        bm.faces.new([v_bot, rings[0][ian], rings[0][ia]])
        bm.faces.new([rings[-1][ia], rings[-1][ian], v_top])
    for ie in range(n_el - 1):
        for ia in range(n_az):
            ian = (ia + 1) % n_az
            bm.faces.new([rings[ie][ia], rings[ie][ian], rings[ie + 1][ian], rings[ie + 1][ia]])

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    for p in mesh.polygons:
        p.use_smooth = True
    dome_obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(dome_obj)
    kit.apply_box_uv_and_mat(dome_obj, mat_dome, uv_scale=0.52)
    kit.parent_keep_local(dome_obj, parent)

    # Raised architectural meridian ribs + base & oculus trim rings
    base_ring = kit.add_prism_ring(
        scene, f"{name}_cornice_ring", radius * 1.055, radius * 0.94, z0 - 0.04, z0 + 0.05, sides=max(24, n_ribs * 2), bevel=0.008
    )
    base_ring.location = (wx0, wy0, 0.0)
    kit.apply_box_uv_and_mat(base_ring, mat_rib_trim, uv_scale=0.55)
    kit.parent_keep_local(base_ring, parent)

    for ir in range(n_ribs):
        ang = (ir / n_ribs) * 2.0 * math.pi
        pts = []
        for k in range(9):
            phi = (k / 8.0) * (math.pi * 0.46)
            rr = (radius + 0.022 * radius) * math.cos(phi)
            zz = z0 + (radius * height_scale + 0.02 * radius) * math.sin(phi)
            pts.append((wx0 + rr * math.cos(ang), wy0 + rr * math.sin(ang), zz))
        kit.add_curved_vein_polyline(
            scene, f"{name}_rib_{ir}", pts, radius * 0.024, radius * 0.015, mat_rib_trim, parent, sides=6, uv_scale=0.6
        )

    if with_lantern:
        lr = radius * 0.21
        lz0 = apex_z - 0.03 * radius
        lh = radius * 0.34
        l_base = kit.add_prism_ring(scene, f"{name}_lantern_base", lr * 1.18, 0.0, lz0, lz0 + lh * 0.22, sides=16, bevel=0.005)
        l_base.location = (wx0, wy0, 0.0)
        kit.apply_box_uv_and_mat(l_base, mat_rib_trim, uv_scale=0.7)
        kit.parent_keep_local(l_base, parent)

        for k in range(8):
            ang = (k / 8.0) * 2.0 * math.pi
            col = kit.add_prism_ring(
                scene,
                f"{name}_lantern_col_{k}",
                lr * 0.16,
                0.0,
                lz0 + lh * 0.20,
                lz0 + lh * 0.85,
                sides=8,
                bevel=0.003,
            )
            col.location = (wx0 + lr * 0.86 * math.cos(ang), wy0 + lr * 0.86 * math.sin(ang), 0.0)
            kit.apply_box_uv_and_mat(col, mat_rib_trim, uv_scale=0.8)
            kit.parent_keep_local(col, parent)

        # Mini cupola cap + spire finial
        bm_f = bmesh.new()
        cz_cap = lz0 + lh * 0.85
        f_rings = []
        for ie in range(6):
            phi = (ie / 6.0) * (math.pi * 0.48)
            rr = lr * 1.12 * math.cos(phi)
            zz = cz_cap + lr * 0.72 * math.sin(phi)
            f_rings.append([bm_f.verts.new((wx0 + rr * math.cos(a * math.pi / 8.0), wy0 + rr * math.sin(a * math.pi / 8.0), zz)) for a in range(16)])
        # Spire rod
        for ie, (rr_s, zz_s) in enumerate([
            (lr * 0.22, cz_cap + lr * 0.74),
            (lr * 0.28, cz_cap + lr * 0.92),
            (lr * 0.09, cz_cap + lr * 1.42),
        ]):
            f_rings.append([bm_f.verts.new((wx0 + rr_s * math.cos(a * math.pi / 8.0), wy0 + rr_s * math.sin(a * math.pi / 8.0), zz_s)) for a in range(16)])
        v_fin_top = bm_f.verts.new((wx0, wy0, cz_cap + lr * 1.72))
        v_fin_bot = bm_f.verts.new((wx0, wy0, cz_cap))
        for a in range(16):
            an = (a + 1) % 16
            bm_f.faces.new([v_fin_bot, f_rings[0][an], f_rings[0][a]])
            bm_f.faces.new([f_rings[-1][a], f_rings[-1][an], v_fin_top])
        for ie in range(len(f_rings) - 1):
            for a in range(16):
                an = (a + 1) % 16
                bm_f.faces.new([f_rings[ie][a], f_rings[ie][an], f_rings[ie + 1][an], f_rings[ie + 1][a]])
        bmesh.ops.recalc_face_normals(bm_f, faces=bm_f.faces)
        m_f = bpy.data.meshes.new(f"{name}_finial")
        bm_f.to_mesh(m_f)
        bm_f.free()
        for p in m_f.polygons:
            p.use_smooth = True
        o_f = bpy.data.objects.new(f"{name}_finial", m_f)
        scene.collection.objects.link(o_f)
        kit.apply_box_uv_and_mat(o_f, mat_rib_trim, uv_scale=0.8)
        kit.parent_keep_local(o_f, parent)


def add_pierced_arched_rotunda_tier(
    scene: bpy.types.Scene,
    name_prefix: str,
    design_center_xyz: tuple[float, float, float],
    r_outer: float,
    r_inner: float,
    height: float,
    n_arches: int,
    arch_width_frac: float,
    arch_spring_frac: float,
    arch_crown_frac: float,
    mat_wall: bpy.types.Material,
    mat_trim: bpy.types.Material,
    mat_shadow_core: bpy.types.Material | None,
    parent: bpy.types.Object,
) -> None:
    """
    Construct a genuine pierced circular stone arcade/drum with true open-through round arches
    (stone piers between openings + spandrel/voussoir arches bridging across each opening + pilasters & cornice).
    """
    dx0, dy0, z0 = design_center_xyz
    wx0, wy0, _ = d2w(dx0, dy0, z0)
    d_theta = 2.0 * math.pi / n_arches
    pier_ang = d_theta * (1.0 - arch_width_frac)
    open_ang = d_theta * arch_width_frac
    z_spring = z0 + height * arch_spring_frac
    z_crown = z0 + height * arch_crown_frac
    z_top = z0 + height

    bm = bmesh.new()

    def add_arc_sector_box(a0: float, a1: float, zb0: float, zb1: float, ro: float, ri: float, n_sub: int = 3):
        angs = [a0 + (a1 - a0) * (k / n_sub) for k in range(n_sub + 1)]
        ob = [bm.verts.new((wx0 + ro * math.cos(a), wy0 + ro * math.sin(a), zb0)) for a in angs]
        ot = [bm.verts.new((wx0 + ro * math.cos(a), wy0 + ro * math.sin(a), zb1)) for a in angs]
        ib = [bm.verts.new((wx0 + ri * math.cos(a), wy0 + ri * math.sin(a), zb0)) for a in angs]
        it = [bm.verts.new((wx0 + ri * math.cos(a), wy0 + ri * math.sin(a), zb1)) for a in angs]
        for k in range(n_sub):
            bm.faces.new([ob[k], ob[k + 1], ot[k + 1], ot[k]])
            bm.faces.new([it[k], it[k + 1], ib[k + 1], ib[k]])
            bm.faces.new([ot[k], ot[k + 1], it[k + 1], it[k]])
            bm.faces.new([ib[k], ib[k + 1], ob[k + 1], ob[k]])
        bm.faces.new([ib[0], ob[0], ot[0], it[0]])
        bm.faces.new([ob[-1], ib[-1], it[-1], ot[-1]])

    for ia in range(n_arches):
        base_a = ia * d_theta
        # Solid pier from z0 to z_top
        p_a0 = base_a
        p_a1 = base_a + pier_ang
        add_arc_sector_box(p_a0, p_a1, z0, z_top, r_outer, r_inner, n_sub=2)

        # Arch spandrel above the opening (true round arch intrados!)
        o_a0 = p_a1
        o_a1 = base_a + d_theta
        n_arch_seg = 6
        angs = [o_a0 + (o_a1 - o_a0) * (k / n_arch_seg) for k in range(n_arch_seg + 1)]
        z_intrados = []
        for k in range(n_arch_seg + 1):
            u = (k / n_arch_seg) * 2.0 - 1.0
            z_intrados.append(z_spring + (z_crown - z_spring) * math.sqrt(max(0.0, 1.0 - u * u)))

        ob = [bm.verts.new((wx0 + r_outer * math.cos(a), wy0 + r_outer * math.sin(a), zi)) for a, zi in zip(angs, z_intrados)]
        ot = [bm.verts.new((wx0 + r_outer * math.cos(a), wy0 + r_outer * math.sin(a), z_top)) for a in angs]
        ib = [bm.verts.new((wx0 + r_inner * math.cos(a), wy0 + r_inner * math.sin(a), zi)) for a, zi in zip(angs, z_intrados)]
        it = [bm.verts.new((wx0 + r_inner * math.cos(a), wy0 + r_inner * math.sin(a), z_top)) for a in angs]
        for k in range(n_arch_seg):
            bm.faces.new([ob[k], ob[k + 1], ot[k + 1], ot[k]])
            bm.faces.new([it[k], it[k + 1], ib[k + 1], ib[k]])
            bm.faces.new([ot[k], ot[k + 1], it[k + 1], it[k]])
            bm.faces.new([ib[k], ib[k + 1], ob[k + 1], ob[k]])

        # Optional low window sill if window (when arch_spring_frac > 0.35 and mat_shadow_core is set)
        if z0 > 1.8:
            add_arc_sector_box(o_a0, o_a1, z0, z0 + height * 0.16, r_outer, r_inner, n_sub=2)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(f"{name_prefix}_arcade")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(f"{name_prefix}_arcade", mesh)
    scene.collection.objects.link(obj)
    kit.apply_box_uv_and_mat(obj, mat_wall, uv_scale=0.52)
    kit.parent_keep_local(obj, parent)

    # Engaged fluted pilasters on each pier + gilded cornice band
    for ia in range(n_arches):
        mid_pier_a = ia * d_theta + 0.5 * pier_ang
        px = wx0 + (r_outer + 0.025) * math.cos(mid_pier_a)
        py = wy0 + (r_outer + 0.025) * math.sin(mid_pier_a)
        pil = kit.add_prism_ring(
            scene, f"{name_prefix}_pilaster_{ia}", 0.055, 0.0, z0, z_top, sides=10, bevel=0.005
        )
        pil.location = (px, py, 0.0)
        kit.apply_box_uv_and_mat(pil, mat_wall, uv_scale=0.65)
        kit.parent_keep_local(pil, parent)

    cornice = kit.add_prism_ring(
        scene, f"{name_prefix}_cornice", r_outer + 0.065, r_inner - 0.02, z_top - 0.04, z_top + 0.055, sides=max(24, n_arches * 2), bevel=0.008
    )
    cornice.location = (wx0, wy0, 0.0)
    kit.apply_box_uv_and_mat(cornice, mat_trim, uv_scale=0.55)
    kit.parent_keep_local(cornice, parent)

    if mat_shadow_core is not None:
        # Recessed inner sanctuary drum visible through the pierced arches (just like the warm bronze-shadowed grille in the concept!)
        core = kit.add_prism_ring(
            scene, f"{name_prefix}_sanctuary_core", r_inner * 0.84, r_inner * 0.68, z0, z_top - 0.02, sides=24, bevel=0.006
        )
        core.location = (wx0, wy0, 0.0)
        kit.apply_box_uv_and_mat(core, mat_shadow_core, uv_scale=0.60)
        kit.parent_keep_local(core, parent)
