"""
Bộ hàm dựng Tháp Đồng Hồ Thiên Văn Eryndor — dùng chung cho BẢN THẬT (monuments/assemble_eryndor_clocktower.py)
và BẢN CƠ KHÍ (clockwork/assemble_eryndor_clockwork.py, scale empty cha 1/40).

Nguồn: docs/p0/eryndor_design.md (đo trên concept 0,0273 m/px). Đơn vị mét, Blender Z-up, trục tháp tại gốc.
Mặt tháp: +X = mặt cửa chính & mặt đồng hồ; −Y = mặt cửa sổ lancet "trái" trong concept (camera sân khấu nhìn từ +X,−Y).
Mỗi hàm build_* nhận `ctx` (scene + bộ vật liệu) và empty cha, trả empty nhóm; tên object có tiền tố ER_.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

KIT_DIR = Path(r"E:\Tools-3D\scripts\archived_selorson_monuments")
MONUMENTS_DIR = Path(__file__).resolve().parent if "__file__" in globals() else Path(r"E:\Akunarch\bin\scripts\monuments")
for _p in (str(MONUMENTS_DIR), str(KIT_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _aaa_monument_kit as kit  # noqa: E402
import _monument_builders as mb  # noqa: E402

# ---------------- mốc kích thước (m) ----------------
OCT_APOTHEM = 5.25                       # thân dưới bát giác: 10,5 m giữa hai mặt
OCT_R = OCT_APOTHEM / math.cos(math.radians(22.5))
Z_PLINTH = 1.0                           # ngưỡng cửa = đỉnh bệ
Z_BASE_TOP = 7.3
Z_PARAPET0, Z_PARAPET1, Z_TURRET = 7.9, 9.0, 9.6
UP_HALF = 2.8                            # thân trên vuông 5,6 m
Z_UP0, Z_UP1 = 7.9, 17.3
CLOCK_Z, CLOCK_R = 12.35, 2.45
BEL_HALF = 2.3                           # gác chuông vuông 4,6 m
Z_BEL0, Z_BEL1 = 17.7, 20.35
Z_GABLE_APEX, Z_SPIRE_APEX = 22.7, 23.1
ARMILLARY_Z, ARMILLARY_R = 25.0, 2.05


@dataclass
class Ctx:
    scene: bpy.types.Scene
    mats: dict


# ---------------- vật liệu ----------------

def build_materials() -> dict:
    ph = kit.build_polyhaven_gltf_material
    return {
        "basalt": ph("ER_basalt", "castle_wall_slates", base_override_linear=(0.24, 0.24, 0.25), contrast=1.6, ao_strength=0.6),
        "basalt_trim": ph("ER_basalt_trim", "old_stone_wall_02", base_override_linear=(0.30, 0.30, 0.31), contrast=1.4),
        "slate": ph("ER_slate", "grey_roof_tiles_02", tint_rgb=(0.36, 0.38, 0.42), contrast=1.1),
        "brass": ph("ER_brass", "metal_plate_02", base_override_linear=(0.80, 0.56, 0.20), metallic=1.0,
                    rough_scale=0.55, rough_bias=0.05, contrast=1.2),
        "bronze": ph("ER_bronze", "metal_plate_02", base_override_linear=(0.55, 0.40, 0.20), metallic=0.95,
                     rough_scale=0.7, contrast=1.3),
        "iron": ph("ER_iron", "metal_plate_02", base_override_linear=(0.06, 0.06, 0.065), metallic=0.85, rough_scale=0.9),
        "enamel": ph("ER_enamel", "metal_plate_02", base_override_linear=(0.025, 0.04, 0.075), metallic=0.25,
                     rough_scale=0.35),
        "glass": ph("ER_window_dark", "metal_plate_02", base_override_linear=(0.05, 0.035, 0.02), metallic=0.4,
                    rough_scale=0.3),
        "oak": ph("ER_oak", "brown_planks_03", tint_rgb=(0.62, 0.48, 0.36), contrast=1.05),
        "cedar": ph("ER_cedar", "fine_grained_wood", tint_rgb=(0.85, 0.52, 0.38)),
        # canon: đá vôi XÁM phủ sương muối (cliff_side gốc ngả cam → ép màu xám, giữ biến thiên sáng tối)
        "limestone": ph("ER_limestone", "cliff_side", base_override_linear=(0.40, 0.40, 0.41), contrast=1.3),
        "frost": ph("ER_limestone_frost", "cliff_side", base_override_linear=(0.60, 0.61, 0.64), contrast=1.2,
                    rough_bias=0.1),
        "limestone_step": ph("ER_limestone_step", "large_sandstone_blocks_01", tint_rgb=(0.86, 0.86, 0.86)),
        "granite": ph("ER_granite", "rock_face_03", tint_rgb=(0.78, 0.74, 0.72)),
        "wool_red": ph("ER_wool_red", "painted_plaster_wall", base_override_linear=(0.20, 0.012, 0.02), contrast=1.4,
                       rough_scale=1.0, rough_bias=0.15),
        "wool_white": ph("ER_wool_white", "painted_plaster_wall", base_override_linear=(0.78, 0.76, 0.72)),
        "wax": ph("ER_beeswax", "painted_plaster_wall", base_override_linear=(0.86, 0.84, 0.76), rough_scale=0.6),
    }


# ---------------- tiện ích hình học ----------------

def group(ctx: Ctx, name: str, parent=None) -> bpy.types.Object:
    e = kit.create_part_empty(ctx.scene, name)
    if parent is not None:
        e.parent = parent
    return e


def _finish(ctx: Ctx, bm, name, mat, parent, uv_scale=0.34, smooth=False, location=(0, 0, 0), rotation=(0, 0, 0)):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    ctx.scene.collection.objects.link(obj)
    kit.apply_box_uv_and_mat(obj, ctx.mats[mat] if isinstance(mat, str) else mat, uv_scale=uv_scale)
    if parent is not None:
        obj.parent = parent
    return obj


def box(ctx, name, center, size, mat, parent, rot=(0, 0, 0), bevel=0.02, uv=0.34):
    return kit.add_beveled_box(ctx.scene, name, center, size, ctx.mats[mat], parent, rot_xyz=rot, bevel=bevel, uv_scale=uv)


def prism(ctx, name, sides, r_out, z0, z1, mat, parent, r_in=0.0, r_top=None, rot=0.0, bevel=0.02, uv=0.3):
    obj = kit.add_prism_ring(ctx.scene, name, r_out, r_in, z0, z1, sides=sides, bevel=bevel, rot_offset=rot,
                             r_outer_top=r_top, r_inner_top=None if r_top is None else (r_in if r_in > 0 else 0.0))
    kit.apply_box_uv_and_mat(obj, ctx.mats[mat], uv_scale=uv)
    obj.parent = parent
    return obj


def lathe(ctx, name, profile, mat, parent, segments=32, location=(0, 0, 0), rotation=(0, 0, 0), uv=0.6, smooth=True):
    """Xoay biên dạng [(r, z), ...] quanh trục Z (r=0 ở đầu/cuối được khép thành đỉnh)."""
    bm = bmesh.new()
    rings = []
    for r, z in profile:
        if r < 1e-6:
            rings.append([bm.verts.new((0, 0, z))])
        else:
            rings.append([bm.verts.new((r * math.cos(2 * math.pi * k / segments), r * math.sin(2 * math.pi * k / segments), z))
                          for k in range(segments)])
    for a, b in zip(rings, rings[1:]):
        for k in range(segments):
            kn = (k + 1) % segments
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new([a[0], b[k], b[kn]])
            elif len(b) == 1:
                bm.faces.new([a[k], b[0], a[kn]])
            else:
                bm.faces.new([a[k], b[k], b[kn], a[kn]])
    return _finish(ctx, bm, name, mat, parent, uv_scale=uv, smooth=smooth, location=location, rotation=rotation)


def band_ring(ctx, name, radius, width, thick, mat, parent, segments=64, location=(0, 0, 0), rotation=(0, 0, 0)):
    """Vòng dẹt (đai quả cầu thiên văn, vành đồng hồ) nằm trong mặt phẳng XY."""
    bm = bmesh.new()
    loops = []
    for rr, zz in ((radius - width / 2, -thick / 2), (radius + width / 2, -thick / 2),
                   (radius + width / 2, thick / 2), (radius - width / 2, thick / 2)):
        loops.append([bm.verts.new((rr * math.cos(2 * math.pi * k / segments), rr * math.sin(2 * math.pi * k / segments), zz))
                      for k in range(segments)])
    for i in range(4):
        a, b = loops[i], loops[(i + 1) % 4]
        for k in range(segments):
            kn = (k + 1) % segments
            bm.faces.new([a[k], a[kn], b[kn], b[k]])
    return _finish(ctx, bm, name, mat, parent, uv_scale=1.2, smooth=True, location=location, rotation=rotation)


def lancet_outline(w: float, h: float, n_arc: int = 10) -> list[tuple[float, float]]:
    """Vòm nhọn đều cạnh (equilateral) rộng w, cao h tính từ đáy; trả polyline kín (u, v) theo chiều kim đồng hồ ngược."""
    rise = w * math.sqrt(3) / 2
    hs = max(0.0, h - rise)
    pts = [(-w / 2, 0.0), (-w / 2, hs)]
    # cung trái: tâm tại (w/2, hs), bán kính w, góc từ 180° xuống 120°
    for i in range(1, n_arc + 1):
        a = math.radians(180 - 60 * i / n_arc)
        pts.append((w / 2 + w * math.cos(a), hs + w * math.sin(a)))
    for i in range(1, n_arc + 1):
        a = math.radians(60 - 60 * i / n_arc)
        pts.append((-w / 2 + w * math.cos(a), hs + w * math.sin(a)))
    pts.append((w / 2, 0.0))
    return pts


def _resample(pts, n):
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg)
    out, acc, i = [], 0.0, 0
    for k in range(n):
        t = total * k / (n - 1)
        while i < len(seg) - 1 and acc + seg[i] < t:
            acc += seg[i]
            i += 1
        f = 0.0 if seg[i] == 0 else (t - acc) / seg[i]
        out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f))
    return out


def _face_frame(theta: float, apothem: float):
    """Gốc và hệ trục (u tiếp tuyến, n pháp tuyến ra ngoài) cho mặt tường có pháp tuyến theo góc theta."""
    n = Vector((math.cos(theta), math.sin(theta), 0))
    u = Vector((-math.sin(theta), math.cos(theta), 0))
    return n * apothem, u, n


def wall_profile(ctx, name, outline, depth, theta, apothem, z0, mat, parent, offset=0.0, uv=0.4):
    """Đùn một biên dạng kín 2D (u, v) dày `depth` ra ngoài mặt tường (góc theta, cách tâm `apothem`)."""
    o, u, n = _face_frame(theta, apothem + offset)
    bm = bmesh.new()
    front = [bm.verts.new(o + u * a + Vector((0, 0, z0 + b)) + n * depth) for a, b in outline]
    back = [bm.verts.new(o + u * a + Vector((0, 0, z0 + b))) for a, b in outline]
    bm.faces.new(front)
    bm.faces.new(list(reversed(back)))
    m = len(outline)
    for i in range(m):
        j = (i + 1) % m
        bm.faces.new([front[i], back[i], back[j], front[j]])
    return _finish(ctx, bm, name, mat, parent, uv_scale=uv)


def wall_frame(ctx, name, outer, inner, depth, theta, apothem, z0, mat, parent, offset=0.0, n=48, uv=0.4):
    """Khung vành (ngoài − trong) đùn ra khỏi mặt tường: vành cửa sổ, vành cửa, tường gác chuông có ô vòm."""
    o_pts, i_pts = _resample(outer, n), _resample(inner, n)
    o, u, nn = _face_frame(theta, apothem + offset)
    bm = bmesh.new()

    def V(p, d):
        return bm.verts.new(o + u * p[0] + Vector((0, 0, z0 + p[1])) + nn * d)

    of, ob = [V(p, depth) for p in o_pts], [V(p, 0.0) for p in o_pts]
    inf, inb = [V(p, depth) for p in i_pts], [V(p, 0.0) for p in i_pts]
    for k in range(n - 1):
        bm.faces.new([of[k], of[k + 1], inf[k + 1], inf[k]])      # mặt trước
        bm.faces.new([ob[k + 1], ob[k], inb[k], inb[k + 1]])      # mặt sau
        bm.faces.new([of[k + 1], of[k], ob[k], ob[k + 1]])        # cạnh ngoài
        bm.faces.new([inf[k], inf[k + 1], inb[k + 1], inb[k]])    # cạnh trong (má cửa)
    for a, b, c, d in ((of[0], inf[0], inb[0], ob[0]), (of[-1], ob[-1], inb[-1], inf[-1])):
        bm.faces.new([a, b, c, d])
    return _finish(ctx, bm, name, mat, parent, uv_scale=uv)


def place_on_face(obj, theta, apothem, z, along=0.0, out=0.0):
    """Đặt object (dựng quanh gốc, mặt hướng +X) lên mặt tường góc theta."""
    o, u, n = _face_frame(theta, apothem)
    p = o + u * along + n * out
    obj.location = (p.x, p.y, z)
    obj.rotation_euler = (obj.rotation_euler[0], obj.rotation_euler[1], theta + obj.rotation_euler[2])
    return obj


def text_mesh(ctx, name, body, size, depth, mat, parent):
    cu = bpy.data.curves.new(name + "_crv", "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = depth
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    tmp = bpy.data.objects.new(name + "_tmp", cu)
    ctx.scene.collection.objects.link(tmp)
    dg = bpy.context.evaluated_depsgraph_get()
    mesh = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg))
    ctx.scene.collection.objects.unlink(tmp)
    bpy.data.objects.remove(tmp)
    mesh.name = name
    obj = bpy.data.objects.new(name, mesh)
    ctx.scene.collection.objects.link(obj)
    kit.apply_box_uv_and_mat(obj, ctx.mats[mat], uv_scale=4.0)
    obj.parent = parent
    return obj


def lattice_panel(ctx, name, w, h, theta, apothem, z0, parent, mat="basalt_trim"):
    """Tấm khắc hoa văn hình thoi trên trụ ốp: khung + 2 thanh chéo chữ X + nút giữa (như concept)."""
    g = group(ctx, name + "_grp", parent)
    t = 0.07
    rect_o = [(-w / 2, 0), (-w / 2, h), (w / 2, h), (w / 2, 0)]
    rect_i = [(-w / 2 + t, t), (-w / 2 + t, h - t), (w / 2 - t, h - t), (w / 2 - t, t)]
    wall_frame(ctx, name, rect_o + [rect_o[0]], rect_i + [rect_i[0]], 0.06, theta, apothem, z0, mat, g, n=24)
    diag = math.hypot(w - 2 * t, h - 2 * t)
    ang = math.atan2(h - 2 * t, w - 2 * t)
    o, u, n = _face_frame(theta, apothem + 0.03)
    for sgn in (1, -1):
        b = box(ctx, f"{name}_x{'ab'[sgn < 0]}", (0, 0, 0), (0.05, diag, 0.05), mat, g, bevel=0.01)
        c = o + Vector((0, 0, z0 + h / 2))
        b.location = c
        b.rotation_euler = (sgn * ang, 0, theta)
    knot = box(ctx, f"{name}_knot", (0, 0, 0), (0.08, 0.16, 0.16), mat, g, bevel=0.02)
    knot.location = o + n * 0.04 + Vector((0, 0, z0 + h / 2))
    knot.rotation_euler = (math.pi / 4, 0, theta)
    return g


# ---------------- bộ phận ----------------

def lancet_window(ctx, name, theta, apothem, z_sill, w, h, parent, grille=True):
    """Cửa sổ lancet: 2 lớp vành, kính tối, song đá + vòng hoa hồng, chấn song sắt."""
    g = group(ctx, name, parent)
    wall_frame(ctx, f"{name}_frame_out", lancet_outline(w + 0.5, h + 0.35), _offset_lancet(w + 0.5, h + 0.35, 0.18),
               0.18, theta, apothem, z_sill - 0.15, "basalt_trim", g)
    wall_frame(ctx, f"{name}_frame_in", lancet_outline(w + 0.14, h + 0.08), lancet_outline(w, h), 0.1,
               theta, apothem, z_sill - 0.04, "basalt_trim", g, offset=0.02)
    wall_profile(ctx, f"{name}_glass", lancet_outline(w, h), 0.02, theta, apothem, z_sill, "glass", g, offset=0.01)
    box(ctx, f"{name}_sill", (0, 0, 0), (0.3, w + 0.6, 0.12), "basalt_trim", g)
    place_on_face(bpy.data.objects[f"{name}_sill"], theta, apothem, z_sill - 0.2, out=0.12)
    rise = w * math.sqrt(3) / 2
    hs = h - rise
    for k, a in enumerate((-w / 6, w / 6)):   # 2 song đá đứng → 3 ô
        m = box(ctx, f"{name}_mullion{k}", (0, 0, 0), (0.07, 0.07, hs + rise * 0.35), "basalt_trim", g, bevel=0.01)
        place_on_face(m, theta, apothem, z_sill + (hs + rise * 0.35) / 2, along=a, out=0.06)
    rose = band_ring(ctx, f"{name}_rose", w * 0.17, 0.05, 0.07, ctx.mats["basalt_trim"], g, segments=24,
                     rotation=(0, math.pi / 2, 0))
    place_on_face(rose, theta, apothem, z_sill + hs + rise * 0.45, out=0.06)
    if grille:
        for k in range(7):
            bar = box(ctx, f"{name}_bar{k}", (0, 0, 0), (0.025, 0.025, hs * 0.92), "iron", g, bevel=0.004)
            place_on_face(bar, theta, apothem, z_sill + hs * 0.48, along=-w / 2 + w * (k + 0.5) / 7, out=0.08)
        for k in range(4):
            bar = box(ctx, f"{name}_rail{k}", (0, 0, 0), (0.025, w * 0.96, 0.025), "iron", g, bevel=0.004)
            place_on_face(bar, theta, apothem, z_sill + hs * (k + 0.5) / 4, out=0.08)
    return g


def _offset_lancet(w, h, t):
    return [(x, y) for x, y in lancet_outline(w - 2 * t, h - t)]


def build_cliff(ctx, parent):
    """Vách đá vôi phủ sương muối (canon: 1.600 m — ở đây phần đỉnh ~9 m dưới chân tháp)."""
    g = group(ctx, "ER_cliff_grp", parent)
    n_a, n_z = 120, 30
    bm = bmesh.new()
    rings = []
    for iz in range(n_z):
        f = iz / (n_z - 1)
        z = -6.5 * f
        row = []
        for ia in range(n_a):
            th = 2 * math.pi * ia / n_a
            base = 7.6 + 2.2 * math.cos(th) ** 2 * (1 if math.cos(th) > 0 else 0.3)   # mở rộng về +X (bãi đáp trước cửa)
            strata = 0.18 * math.sin(z * 2.3 + 1.7 * math.sin(th * 3))
            crag = 0.75 * mb.fbm3(math.cos(th) * 2.0, math.sin(th) * 2.0, z * 0.35, seed=4.2)
            r = base + strata + crag * (0.4 + f) + 1.2 * f * f
            row.append(bm.verts.new((r * math.cos(th), r * math.sin(th), z + 0.25 * crag * (iz == 0))))
        rings.append(row)
    top_c = bm.verts.new((0, 0, 0.0))
    for ia in range(n_a):
        ian = (ia + 1) % n_a
        bm.faces.new([top_c, rings[0][ia], rings[0][ian]])
        for iz in range(n_z - 1):
            bm.faces.new([rings[iz][ia], rings[iz + 1][ia], rings[iz + 1][ian], rings[iz][ian]])
    bot_c = bm.verts.new((0, 0, -6.5))
    for ia in range(n_a):
        bm.faces.new([bot_c, rings[-1][(ia + 1) % n_a], rings[-1][ia]])
    obj = _finish(ctx, bm, "ER_cliff", "limestone", g, uv_scale=0.12)
    obj.data.materials.append(ctx.mats["frost"])   # sương muối đọng trên mặt hướng lên (đỉnh vách, gờ đá)
    for p in obj.data.polygons:
        p.use_smooth = True
        p.material_index = 1 if p.normal.z > 0.86 else 0
    return g


def build_base_octagon(ctx, parent):
    g = group(ctx, "ER_base_grp", parent)
    rot = math.radians(22.5)
    prism(ctx, "ER_plinth_0", 8, OCT_R * 1.07, 0.0, 0.55, "basalt_trim", g, rot=rot, bevel=0.04)
    prism(ctx, "ER_plinth_1", 8, OCT_R * 1.035, 0.55, Z_PLINTH, "basalt_trim", g, rot=rot, bevel=0.03)
    prism(ctx, "ER_base_wall", 8, OCT_R, Z_PLINTH, Z_BASE_TOP, "basalt", g, rot=rot, bevel=0.02, uv=0.28)
    prism(ctx, "ER_base_string", 8, OCT_R * 1.03, 4.1, 4.3, "basalt_trim", g, rot=rot)
    # dải đỡ tường răng cưa: hàng đá nhô (corbel) + gờ
    for k in range(8):
        th = k * math.pi / 4
        face_w = 2 * OCT_APOTHEM * math.tan(math.radians(22.5))
        for j in range(7):
            c = box(ctx, f"ER_corbel_{k}_{j}", (0, 0, 0), (0.28, 0.26, 0.32), "basalt_trim", g, bevel=0.02)
            place_on_face(c, th, OCT_APOTHEM, Z_BASE_TOP + 0.16, along=-face_w / 2 + face_w * (j + 0.5) / 7, out=0.12)
    prism(ctx, "ER_corbel_cap", 8, OCT_R * 1.06, Z_BASE_TOP + 0.32, Z_PARAPET0, "basalt_trim", g, rot=rot, bevel=0.03)
    return g


def build_buttresses(ctx, parent):
    """8 trụ ốp ở 8 đỉnh bát giác: 3 bậc thu nhỏ, mũ vát, tấm khắc hình thoi."""
    g = group(ctx, "ER_buttress_grp", parent)
    for k in range(8):
        th = math.radians(22.5) + k * math.pi / 4
        bg = group(ctx, f"ER_buttress_{k}", g)
        for lvl, (z0, z1, wd, pr) in enumerate(((Z_PLINTH, 3.4, 1.6, 1.15), (3.4, 5.6, 1.35, 0.85), (5.6, Z_BASE_TOP, 1.1, 0.55))):
            d = OCT_R + pr / 2 - 0.15
            b = box(ctx, f"ER_buttress_{k}_l{lvl}", (d * math.cos(th), d * math.sin(th), (z0 + z1) / 2),
                    (pr + 0.3, wd, z1 - z0), "basalt", bg, rot=(0, 0, th), bevel=0.03, uv=0.3)
            cap = box(ctx, f"ER_buttress_{k}_cap{lvl}", (0, 0, 0), (0.42, wd + 0.08, 0.12), "basalt_trim", bg, bevel=0.02)
            dc = OCT_R + pr - 0.05
            cap.location = (dc * math.cos(th), dc * math.sin(th), z1 - 0.1)
            cap.rotation_euler = (0, -0.6, th)
            lattice_panel(ctx, f"ER_buttress_{k}_panel{lvl}", wd * 0.7, (z1 - z0) * 0.62, th, OCT_R + pr,
                          z0 + (z1 - z0) * 0.19, bg)
    return g


def build_lancet_windows(ctx, parent):
    """4 cửa sổ lancet thân dưới (−90°, −45°, 90°, 135°) + 3 cửa sổ thân trên (−Y, +Y, −X)."""
    g = group(ctx, "ER_windows_grp", parent)
    for i, deg in enumerate((-90, -45, 90, 135)):
        lancet_window(ctx, f"ER_lancet_{i}", math.radians(deg), OCT_APOTHEM, 2.1, 1.25, 3.7, g)
    for i, deg in enumerate((-90, 90, 180)):
        lancet_window(ctx, f"ER_lancet_{4 + i}", math.radians(deg), UP_HALF, 10.3, 1.15, 4.1, g)
        _gable_hood(ctx, f"ER_hood_up{i}", math.radians(deg), UP_HALF, 14.6, 1.9, 1.5, g)
    # tấm ô trống (blind panel) ở các mặt còn lại thân dưới
    for i, deg in enumerate((45, 180, -135)):
        th = math.radians(deg)
        rect = [(-0.75, 0), (-0.75, 2.4), (0.75, 2.4), (0.75, 0), (-0.75, 0)]
        inner = [(-0.6, 0.15), (-0.6, 2.25), (0.6, 2.25), (0.6, 0.15), (-0.6, 0.15)]
        wall_frame(ctx, f"ER_blind_{i}", rect, inner, 0.14, th, OCT_APOTHEM, 3.0, "basalt_trim", g, n=24)
    return g


def _gable_hood(ctx, name, theta, apothem, z0, w, h, parent):
    """Mái hồi nhọn phía trên cửa sổ thân trên + huy hiệu tròn."""
    tri = [(-w / 2, 0), (0, h), (w / 2, 0), (-w / 2, 0)]
    tri_in = [(-w / 2 + 0.2, 0.12), (0, h - 0.25), (w / 2 - 0.2, 0.12), (-w / 2 + 0.2, 0.12)]
    g = group(ctx, name, parent)
    wall_frame(ctx, f"{name}_frame", tri, tri_in, 0.22, theta, apothem, z0, "basalt_trim", g, n=24)
    wall_profile(ctx, f"{name}_tympanum", tri_in[:-1], 0.08, theta, apothem, z0, "basalt", g)
    rose = band_ring(ctx, f"{name}_roundel", 0.24, 0.06, 0.08, ctx.mats["basalt_trim"], g, segments=24,
                     rotation=(0, math.pi / 2, 0))
    place_on_face(rose, theta, apothem, z0 + h * 0.42, out=0.12)
    return g


def build_entrance(ctx, parent):
    """Cửa chính mặt +X: vòm nhọn 2 lớp, cửa gỗ sồi 2 cánh, vòng sắt; 4 bậc thềm có tường má; ô trống phía trên."""
    g = group(ctx, "ER_door", parent)
    th = 0.0
    w, h = 2.0, 3.5
    wall_frame(ctx, "ER_door_arch_out", lancet_outline(w + 0.9, h + 0.55), lancet_outline(w + 0.42, h + 0.25), 0.3,
               th, OCT_APOTHEM, Z_PLINTH - 0.02, "basalt_trim", g)
    wall_frame(ctx, "ER_door_arch_in", lancet_outline(w + 0.42, h + 0.25), lancet_outline(w, h), 0.18,
               th, OCT_APOTHEM, Z_PLINTH - 0.01, "basalt_trim", g)
    for side, sgn in (("L", -1), ("R", 1)):
        leaf = [(p[0], p[1]) for p in lancet_outline(w, h) if p[0] * sgn >= -1e-6]
        leaf = [(0.0, 0.0)] + leaf if sgn > 0 else leaf + [(0.0, 0.0)]
        wall_profile(ctx, f"ER_door_leaf_{side}", leaf, 0.08, th, OCT_APOTHEM, Z_PLINTH, "oak", g, offset=0.02, uv=0.7)
        ring = band_ring(ctx, f"ER_door_ring_{side}", 0.1, 0.025, 0.025, ctx.mats["iron"], g, segments=16,
                         rotation=(0, math.pi / 2, 0))
        place_on_face(ring, th, OCT_APOTHEM, Z_PLINTH + 1.3, along=sgn * 0.3, out=0.14)
        for k in range(3):
            strap = box(ctx, f"ER_door_strap_{side}{k}", (0, 0, 0), (0.02, w / 2 - 0.1, 0.07), "iron", g, bevel=0.005)
            place_on_face(strap, th, OCT_APOTHEM, Z_PLINTH + 0.5 + k * 0.9, along=sgn * (w / 4), out=0.11)
    # bậc thềm (4 bậc × 0,25 m) + tường má vát
    for i in range(4):
        depth = 0.42 * (4 - i)
        box(ctx, f"ER_step_{i}", (OCT_APOTHEM + 0.25 + depth / 2, 0, 0.125 + 0.25 * i), (depth, 2.6, 0.25),
            "limestone_step", g, bevel=0.02)
    for sgn in (-1, 1):
        cheek = bmesh.new()
        x0, x1 = OCT_APOTHEM + 0.2, OCT_APOTHEM + 0.25 + 0.42 * 4 + 0.1
        y0, y1 = sgn * 1.3, sgn * 1.62
        v = [cheek.verts.new(p) for p in ((x0, y0, 0), (x1, y0, 0), (x1, y0, 0.35), (x0, y0, 1.25),
                                          (x0, y1, 0), (x1, y1, 0), (x1, y1, 0.35), (x0, y1, 1.25))]
        for f in ((0, 1, 2, 3), (7, 6, 5, 4), (0, 4, 5, 1), (1, 5, 6, 2), (2, 6, 7, 3), (3, 7, 4, 0)):
            cheek.faces.new([v[i] for i in f])
        _finish(ctx, cheek, f"ER_step_cheek_{'LR'[sgn > 0]}", "basalt_trim", g)
    rect = [(-0.9, 0), (-0.9, 1.6), (0.9, 1.6), (0.9, 0), (-0.9, 0)]
    inner = [(-0.75, 0.15), (-0.75, 1.45), (0.75, 1.45), (0.75, 0.15), (-0.75, 0.15)]
    wall_frame(ctx, "ER_door_blind_panel", rect, inner, 0.14, th, OCT_APOTHEM, 5.2, "basalt_trim", g, n=24)
    return g


def build_parapet(ctx, parent):
    """Tường răng cưa bát giác + 4 tháp góc (ở đỉnh 22.5°, 112.5°, 202.5°, 292.5°) có răng cưa riêng."""
    g = group(ctx, "ER_parapet_grp", parent)
    rot = math.radians(22.5)
    prism(ctx, "ER_parapet_wall", 8, OCT_R * 1.04, Z_PARAPET0, Z_PARAPET1 - 0.45, "basalt", g, r_in=OCT_R * 0.9, rot=rot)
    face_w = 2 * OCT_APOTHEM * 1.04 * math.tan(math.radians(22.5))
    for k in range(8):
        th = k * math.pi / 4
        for j in range(5):
            m = box(ctx, f"ER_merlon_{k}_{j}", (0, 0, 0), (0.42, 0.5, 0.6), "basalt", g, bevel=0.03)
            place_on_face(m, th, OCT_APOTHEM * 1.04 - 0.21, Z_PARAPET1 - 0.15, along=-face_w / 2 + 0.7 + j * (face_w - 1.4) / 4)
    for i, k in enumerate((0, 2, 4, 6)):
        th = math.radians(22.5) + k * math.pi / 4
        d = OCT_R * 1.0
        tg = group(ctx, f"ER_corner_turret_{i}", g)
        box(ctx, f"ER_corner_turret_{i}_body", (d * math.cos(th), d * math.sin(th), (Z_PARAPET0 + Z_TURRET - 0.45) / 2),
            (2.0, 2.0, Z_TURRET + 0.3 - 0.45 - Z_PARAPET0), "basalt", tg, rot=(0, 0, th), bevel=0.04)
        for j, (a, b) in enumerate(((-0.72, -0.72), (0.72, -0.72), (-0.72, 0.72), (0.72, 0.72))):
            off = Vector((a, b, 0))
            off.rotate(Matrix.Rotation(th, 3, "Z"))
            box(ctx, f"ER_corner_turret_{i}_m{j}", (d * math.cos(th) + off.x, d * math.sin(th) + off.y, Z_TURRET + 0.1),
                (0.52, 0.52, 0.6), "basalt", tg, rot=(0, 0, th), bevel=0.03)
    return g


def build_upper_body(ctx, parent):
    """Thân trên vuông 5,6 m (Z_UP0 → Z_UP1) + trụ góc + mái hiên đá nhỏ ở góc + gờ mái có hàng đá nhô."""
    g = group(ctx, "ER_upper_grp", parent)
    box(ctx, "ER_upper_wall", (0, 0, (Z_UP0 + Z_UP1) / 2), (2 * UP_HALF, 2 * UP_HALF, Z_UP1 - Z_UP0), "basalt", g,
        bevel=0.03, uv=0.28)
    for k, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
        box(ctx, f"ER_upper_pilaster_{k}", (sx * (UP_HALF + 0.05), sy * (UP_HALF + 0.05), (Z_UP0 + Z_UP1) / 2),
            (0.55, 0.55, Z_UP1 - Z_UP0), "basalt_trim", g, bevel=0.03)
        eave = box(ctx, f"ER_upper_eave_{k}", (sx * (UP_HALF + 0.35), sy * (UP_HALF + 0.35), 16.7), (0.95, 0.95, 0.12),
                   "slate", g, rot=(sy * 0.35, -sx * 0.35, 0), bevel=0.02)
    box(ctx, "ER_cornice", (0, 0, Z_UP1 + 0.2), (2 * UP_HALF + 0.9, 2 * UP_HALF + 0.9, 0.4), "basalt_trim", g, bevel=0.05)
    for k in range(4):
        th = k * math.pi / 2
        for j in range(9):
            c = box(ctx, f"ER_cornice_corbel_{k}_{j}", (0, 0, 0), (0.22, 0.22, 0.25), "basalt_trim", g, bevel=0.02)
            place_on_face(c, th, UP_HALF + 0.1, Z_UP1 - 0.13, along=-UP_HALF + 0.5 + j * (2 * UP_HALF - 1.0) / 8)
    return g


def _dial(ctx, name, parent, r, numerals=True, zodiac=True):
    """Mặt đồng hồ dựng trong mặt phẳng YZ, nhìn về +X (dựng quanh gốc rồi đặt lên mặt tường)."""
    g = group(ctx, name, parent)
    face = lathe(ctx, f"{name}_back", [(0, 0), (r, 0), (r, 0.08), (0, 0.08)], "enamel", g, segments=64, rotation=(0, math.pi / 2, 0))
    for i, (rr, w) in enumerate(((r, 0.12), (r * 0.72, 0.05), (r * 0.42, 0.04))):
        band_ring(ctx, f"{name}_ring{i}", rr - w / 2, w, 0.1, ctx.mats["brass"], g, segments=72,
                  location=(0.06, 0, 0), rotation=(0, math.pi / 2, 0))
    for k in range(24):   # vạch chia 24 giờ
        a = 2 * math.pi * k / 24
        t = box(ctx, f"{name}_tick{k}", (0.08, r * 0.9 * math.cos(a), r * 0.9 * math.sin(a)), (0.03, 0.03, 0.12 if k % 2 else 0.2),
                "brass", g, rot=(a - math.pi / 2, 0, 0), bevel=0.005)
    if numerals:
        roman = ["XII", "I", "II", "III", "IIII", "V", "VI", "VII", "VIII", "IX", "X", "XI"]
        for k, s in enumerate(roman):
            a = math.pi / 2 - 2 * math.pi * k / 12
            t = text_mesh(ctx, f"ER_numeral_{k}", s, r * 0.12, 0.02, "brass", g)
            t.location = (0.09, r * 0.81 * math.cos(a), r * 0.81 * math.sin(a))
            t.rotation_euler = (math.pi / 2, 0, math.pi / 2)
            t.rotation_euler.rotate(Matrix.Rotation(a - math.pi / 2, 3, "X").to_euler())
    if zodiac:   # vòng hoàng đạo lệch tâm với 12 huy hiệu
        zc = Vector((0.12, 0, r * 0.13))
        band_ring(ctx, f"{name}_zodiac_ring", r * 0.5, r * 0.11, 0.06, ctx.mats["brass"], g, segments=72,
                  location=tuple(zc), rotation=(0, math.pi / 2, 0))
        for k in range(12):
            a = 2 * math.pi * k / 12
            band_ring(ctx, f"ER_zodiac_{k}", r * 0.04, r * 0.025, 0.05, ctx.mats["brass"], g, segments=16,
                      location=(zc.x + 0.03, zc.y + r * 0.5 * math.cos(a), zc.z + r * 0.5 * math.sin(a)),
                      rotation=(0, math.pi / 2, 0))
    hand = box(ctx, f"{name}_hand_sun", (0.16, 0, r * 0.32), (0.03, 0.07, r * 0.64), "brass", g, bevel=0.005)
    sun = lathe(ctx, f"{name}_sun", [(0, -0.05), (r * 0.09, -0.02), (r * 0.09, 0.02), (0, 0.05)], "brass", g, segments=24,
                location=(0.18, 0, r * 0.62), rotation=(0, math.pi / 2, 0))
    moon = lathe(ctx, f"{name}_moon_hand", [(0, -r * 0.06), (r * 0.06, 0), (0, r * 0.06)], "iron", g, segments=16,
                 location=(0.2, r * 0.38, -r * 0.2))
    hub = lathe(ctx, f"{name}_hub", [(0, 0), (r * 0.07, 0), (r * 0.05, 0.08), (0, 0.1)], "brass", g, segments=24,
                rotation=(0, math.pi / 2, 0), location=(0.08, 0, 0))
    return g


def build_clock_face(ctx, parent):
    """Mặt đồng hồ thiên văn chính (mặt +X, Ø 4,9 m) nhô ra trong hộp vành đồng + mái vòm viền đồng
    với 3 mặt phụ + 3 huy hiệu (concept: mặt số gần bằng bề rộng mặt tường, mái vòm cuộn hai đầu)."""
    g = group(ctx, "ER_clock_grp", parent)
    proj = 0.55
    lathe(ctx, "ER_clock_housing", [(CLOCK_R - 0.08, 0.0), (CLOCK_R + 0.22, 0.0), (CLOCK_R + 0.22, proj - 0.05),
                                    (CLOCK_R + 0.12, proj + 0.04), (CLOCK_R - 0.08, proj + 0.04)],
          "brass", g, segments=72, location=(UP_HALF, 0, CLOCK_Z), rotation=(0, math.pi / 2, 0))
    lathe(ctx, "ER_clock_housing_stone", [(CLOCK_R + 0.2, 0.0), (CLOCK_R + 0.42, 0.0), (CLOCK_R + 0.42, 0.25),
                                          (CLOCK_R + 0.2, 0.32)],
          "basalt_trim", g, segments=72, location=(UP_HALF, 0, CLOCK_Z), rotation=(0, math.pi / 2, 0))
    dial = _dial(ctx, "ER_clock_face", g, CLOCK_R)
    dial.location = (UP_HALF + proj - 0.1, 0, CLOCK_Z)
    hz0, hr = CLOCK_Z + CLOCK_R + 0.12, 2.3
    sg = group(ctx, "ER_sub_dials", g)
    for i, (y, z, r) in enumerate(((-0.95, hz0 + 0.62, 0.55), (0.9, hz0 + 0.85, 0.62), (-0.05, hz0 + 1.62, 0.42))):
        d = _dial(ctx, f"ER_sub_dial_{i}", sg, r, numerals=False, zodiac=False)
        d.location = (UP_HALF + 0.12, y, z)
    for i, (y, z) in enumerate(((1.62, hz0 + 0.2), (-1.66, hz0 + 0.18), (0.62, hz0 + 1.72))):
        lathe(ctx, f"ER_sub_roundel_{i}", [(0, 0), (0.17, 0), (0.17, 0.05), (0.11, 0.1), (0, 0.11)], "brass", sg, segments=20,
              location=(UP_HALF + 0.12, y, z), rotation=(0, math.pi / 2, 0))
    hood = group(ctx, "ER_clock_hood", g)
    hdepth = 0.75
    arc_o = [(hr * math.cos(math.pi * i / 32), hr * math.sin(math.pi * i / 32)) for i in range(33)]
    arc_i = [((hr - 0.24) * math.cos(math.pi * i / 32), (hr - 0.24) * math.sin(math.pi * i / 32)) for i in range(33)]
    wall_frame(ctx, "ER_clock_hood_stone", [(-x, y) for x, y in arc_o], [(-x, y) for x, y in arc_i], hdepth, 0.0, UP_HALF,
               hz0, "basalt_trim", hood, n=33)
    for i, rr in enumerate((hr + 0.01, hr - 0.23)):
        trim = [(rr * math.cos(math.pi * k / 32), rr * math.sin(math.pi * k / 32)) for k in range(33)]
        trim_i = [((rr - 0.08) * math.cos(math.pi * k / 32), (rr - 0.08) * math.sin(math.pi * k / 32)) for k in range(33)]
        wall_frame(ctx, f"ER_clock_hood_brass{i}", [(-x, y) for x, y in trim], [(-x, y) for x, y in trim_i], 0.07, 0.0,
                   UP_HALF + hdepth, hz0, "brass", hood, n=33)
    for sgn in (-1, 1):   # hai đầu mái cuộn ra ngoài (volute)
        for j, (rad, dz) in enumerate(((0.24, 0.0), (0.15, 0.06))):
            band_ring(ctx, f"ER_clock_hood_scroll_{'LR'[sgn > 0]}{j}", rad, 0.08, 0.14, ctx.mats["brass"], hood, segments=24,
                      location=(UP_HALF + hdepth - 0.1, sgn * (hr + 0.12), hz0 + dz), rotation=(0, math.pi / 2, 0))
    return g


def build_belfry(ctx, parent):
    """Gác chuông vuông 4,6 m: 4 tường có ô vòm nhọn, lan can quanh gờ, 2 chuông đồng treo xà, 4 đầu hồi có huy hiệu."""
    g = group(ctx, "ER_belfry_grp", parent)
    h = Z_BEL1 - Z_BEL0
    outer = [(-BEL_HALF, 0), (-BEL_HALF, h), (BEL_HALF, h), (BEL_HALF, 0)]
    for k in range(4):
        th = k * math.pi / 2
        wall_frame(ctx, f"ER_belfry_arch_{k}", outer, lancet_outline(1.75, 2.75), 0.45, th, BEL_HALF - 0.45, Z_BEL0,
                   "basalt", g, n=48, uv=0.3)
        wall_frame(ctx, f"ER_belfry_arch_{k}_trim", lancet_outline(2.15, 2.95), lancet_outline(1.75, 2.75), 0.12, th,
                   BEL_HALF, Z_BEL0 + 0.0, "basalt_trim", g)
    box(ctx, "ER_belfry_floor", (0, 0, Z_BEL0 + 0.05), (2 * BEL_HALF, 2 * BEL_HALF, 0.1), "basalt_trim", g)
    box(ctx, "ER_belfry_top", (0, 0, Z_BEL1 + 0.1), (2 * BEL_HALF + 0.3, 2 * BEL_HALF + 0.3, 0.25), "basalt_trim", g, bevel=0.04)
    # lan can quanh gờ mái thân trên
    edge = UP_HALF + 0.38
    for k in range(4):
        th = k * math.pi / 2
        for j in range(15):
            a = -edge + 0.2 + j * (2 * edge - 0.4) / 14
            bal = lathe(ctx, f"ER_baluster_{k}_{j}", [(0, 0), (0.07, 0), (0.05, 0.12), (0.08, 0.3), (0.045, 0.5), (0.07, 0.62),
                                                    (0, 0.62)], "basalt_trim", g, segments=10)
            place_on_face(bal, th, edge, Z_UP1 + 0.4, along=a)
        box(ctx, f"ER_balustrade_rail_{k}", (0, 0, 0), (0.16, 2 * edge + 0.1, 0.1), "basalt_trim", g)
        place_on_face(bpy.data.objects[f"ER_balustrade_rail_{k}"], th, edge, Z_UP1 + 1.07)
    # xà gỗ + 2 chuông
    box(ctx, "ER_bell_beam", (0.7, -0.7, Z_BEL1 - 0.45), (0.2, 2 * BEL_HALF + 0.2, 0.2), "oak", g, rot=(0, 0, math.pi / 4))
    bell_profile = [(0, 0.95), (0.12, 0.95), (0.2, 0.88), (0.26, 0.7), (0.3, 0.45), (0.38, 0.2), (0.47, 0.05), (0.5, 0.0),
                    (0.44, 0.0), (0.4, 0.06), (0.32, 0.25), (0.25, 0.5), (0.2, 0.75), (0, 0.85)]
    bell_profile = [(r * 1.25, z * 1.25) for r, z in bell_profile]
    for side, (x, y) in (("L", (0.0, -1.42)), ("R", (1.42, 0.0))):
        lathe(ctx, f"ER_bell_{side}", bell_profile, "bronze", g, segments=36, location=(x, y, Z_BEL1 - 1.75))
        lathe(ctx, f"ER_bell_{side}_clapper", [(0, 0), (0.07, 0.04), (0.07, 0.1), (0.015, 0.14), (0.015, 0.75), (0, 0.75)],
              "iron", g, segments=12, location=(x, y, Z_BEL1 - 1.65))
    # 4 đầu hồi trên 4 ô vòm
    for k in range(4):
        th = k * math.pi / 2
        gh = _gable_hood(ctx, f"ER_gable_{k}", th, BEL_HALF, Z_BEL1 - 0.05, 3.7, Z_GABLE_APEX + 0.25 - Z_BEL1, g)
        o = Vector((math.cos(th), math.sin(th), 0)) * (BEL_HALF + 0.12)
        lathe(ctx, f"ER_gable_{k}_finial", [(0, 0), (0.12, 0), (0.05, 0.3), (0.07, 0.4), (0, 0.85)], "basalt_trim", gh,
              segments=8, location=(o.x, o.y, Z_GABLE_APEX + 0.15))
    return g


def build_pinnacles(ctx, parent):
    """8 tháp nhọn: 4 ở góc gác chuông (cao) + 4 ở góc lan can (thấp)."""
    g = group(ctx, "ER_pinnacle_grp", parent)
    i = 0
    for half, z0, hgt, w in ((BEL_HALF + 0.05, Z_BEL0, 5.3, 0.36), (UP_HALF + 0.38, Z_UP1 + 0.4, 3.1, 0.26)):
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            x, y = sx * half, sy * half
            pg = group(ctx, f"ER_pinnacle_{i}", g)
            shaft_h = hgt * 0.48
            box(ctx, f"ER_pinnacle_{i}_shaft", (x, y, z0 + shaft_h / 2), (w, w, shaft_h), "basalt_trim", pg, bevel=0.02)
            spire = prism(ctx, f"ER_pinnacle_{i}_spire", 4, w * 0.75, z0 + shaft_h, z0 + hgt, "basalt_trim", pg,
                          r_top=0.02, rot=math.pi / 4, bevel=0.0)
            spire.location = (x, y, 0)
            for c in range(3):   # nụ đá (crocket) dọc chóp
                zc = z0 + shaft_h + (hgt - shaft_h) * (0.2 + 0.25 * c)
                lathe(ctx, f"ER_pinnacle_{i}_crocket{c}", [(0, -0.06), (0.07, 0), (0, 0.06)], "basalt_trim", pg, segments=8,
                      location=(x + sx * w * 0.32 * (1 - 0.3 * c), y + sy * w * 0.32 * (1 - 0.3 * c), zc))
            lathe(ctx, f"ER_pinnacle_{i}_finial", [(0, 0), (0.06, 0.04), (0.06, 0.1), (0, 0.16)], "basalt_trim", pg,
                  segments=10, location=(x, y, z0 + hgt))
            i += 1
    return g


def build_spire(ctx, parent):
    """Mái chóp lợp đá phiến: chóp vuông + 4 mái hồi chéo (bờ nóc chạy từ đỉnh đầu hồi vào tâm) + trụ đồng."""
    g = group(ctx, "ER_spire", parent)
    prism(ctx, "ER_spire_core", 4, BEL_HALF * 1.45, Z_BEL1 + 0.22, Z_SPIRE_APEX, "slate", g, r_top=0.05,
          rot=math.pi / 4, uv=0.5, bevel=0.0)
    for k in range(4):
        th = k * math.pi / 2
        bm = bmesh.new()
        hw = 1.45
        ridge_out = Vector((BEL_HALF + 0.05, 0, Z_GABLE_APEX - 0.05))
        ridge_in = Vector((0.2, 0, Z_SPIRE_APEX - 0.05))
        eave_l, eave_r = Vector((BEL_HALF + 0.05, -hw, Z_BEL1 + 0.3)), Vector((BEL_HALF + 0.05, hw, Z_BEL1 + 0.3))
        in_l, in_r = Vector((0.2, -hw * 0.4, Z_BEL1 + 1.6)), Vector((0.2, hw * 0.4, Z_BEL1 + 1.6))
        rot = Matrix.Rotation(th, 3, "Z")
        vs = [bm.verts.new(rot @ p) for p in (eave_l, ridge_out, ridge_in, in_l, eave_r, in_r)]
        bm.faces.new([vs[0], vs[1], vs[2], vs[3]])
        bm.faces.new([vs[4], vs[5], vs[2], vs[1]])
        geom = bmesh.ops.extrude_face_region(bm, geom=list(bm.faces))
        for v in [e for e in geom["geom"] if isinstance(e, bmesh.types.BMVert)]:
            v.co.z -= 0.12
        _finish(ctx, bm, f"ER_spire_gable_roof_{k}", "slate", g, uv_scale=0.5)
        ridge = box(ctx, f"ER_spire_ridge_{k}", (0, 0, 0), ((ridge_out - ridge_in).length, 0.12, 0.12), "basalt_trim", g)
        mid = rot @ ((ridge_out + ridge_in) / 2)
        ridge.location = (mid.x, mid.y, mid.z + 0.06)
        ridge.rotation_euler = (0, math.atan2(ridge_in.z - ridge_out.z, ridge_out.x - ridge_in.x), th)
    lathe(ctx, "ER_spire_finial", [(0, 0), (0.28, 0), (0.22, 0.12), (0.12, 0.18), (0.16, 0.28), (0.1, 0.36), (0.09, 0.42),
                                   (0.18, 0.47), (0.07, 0.52), (0, 0.53)], "brass", g, segments=24,
          location=(0, 0, Z_SPIRE_APEX - 0.1))
    return g


def build_armillary(ctx, parent):
    """Quả cầu thiên văn Ø 4,1 m: địa cầu + 5 đai (xích đạo, hoàng đạo nghiêng 23,4°, 2 kinh tuyến, đai ngoài) + trục cực."""
    g = group(ctx, "ER_armillary", parent)
    g.location = (0, 0, ARMILLARY_Z)
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=32, v_segments=16, radius=0.48)
    _finish(ctx, bm, "ER_armillary_globe", "bronze", g, uv_scale=1.5, smooth=True)
    R = ARMILLARY_R
    band_ring(ctx, "ER_armillary_equator", R * 0.98, 0.14, 0.05, ctx.mats["bronze"], g)
    band_ring(ctx, "ER_armillary_ecliptic", R * 0.9, 0.2, 0.05, ctx.mats["bronze"], g, rotation=(math.radians(23.4), 0, 0))
    band_ring(ctx, "ER_armillary_meridian_a", R * 0.86, 0.14, 0.06, ctx.mats["bronze"], g, rotation=(math.pi / 2, 0, 0))
    band_ring(ctx, "ER_armillary_meridian_b", R * 0.84, 0.12, 0.05, ctx.mats["bronze"], g, rotation=(math.pi / 2, 0, math.pi / 2))
    band_ring(ctx, "ER_armillary_outer", R - 0.1, 0.2, 0.07, ctx.mats["bronze"], g, rotation=(math.radians(66), 0, math.radians(40)))
    for k in range(24):   # vạch khắc trên đai hoàng đạo
        a = 2 * math.pi * k / 24
        t = box(ctx, f"ER_armillary_tick{k}", (0, 0, 0), (0.03, 0.03, 0.22), "bronze", g, bevel=0.004)
        p = Vector((R * 0.9 * math.cos(a), R * 0.9 * math.sin(a), 0))
        p.rotate(Matrix.Rotation(math.radians(23.4), 3, "X"))
        t.location = p
    lathe(ctx, "ER_armillary_axis", [(0, -1.8), (0.04, -1.8), (0.04, 1.8), (0, 1.8)], "iron", g, segments=10,
          rotation=(math.radians(23.4), 0, 0))
    lathe(ctx, "ER_armillary_stem", [(0, Z_SPIRE_APEX + 0.43 - ARMILLARY_Z), (0.09, Z_SPIRE_APEX + 0.43 - ARMILLARY_Z),
                                     (0.07, -0.46), (0, -0.46)], "brass", g, segments=16)
    return g


def build_shaft_and_pendulum(ctx, parent):
    """Trục giếng thông tầng + con lắc neo 4 m (sắt rèn) + quả lắc đá hoa cương + 2 tạ đá treo xích (canon)."""
    g = group(ctx, "ER_shaft_grp", parent)
    prism(ctx, "ER_shaft_wall", 16, 1.35, Z_PLINTH, 16.6, "limestone_step", g, r_in=1.1, bevel=0.0)
    pg = group(ctx, "ER_pendulum", g)
    pivot_z = 15.8
    box(ctx, "ER_pendulum_rod", (0, 0, pivot_z - 2.0), (0.07, 0.07, 4.0), "iron", pg, bevel=0.01)
    lathe(ctx, "ER_pendulum_bob", [(0, -0.12), (0.3, -0.1), (0.45, 0), (0.3, 0.1), (0, 0.12)], "granite", pg, segments=32,
          location=(0, 0, pivot_z - 4.0), rotation=(math.pi / 2, 0, 0))
    box(ctx, "ER_pendulum_anchor", (0, 0, pivot_z + 0.15), (0.12, 0.9, 0.18), "iron", pg, rot=(0.0, 0, 0), bevel=0.02)
    for side, y in (("a", -0.7), ("b", 0.7)):
        for li in range(22):
            band_ring(ctx, f"ER_weight_chain_{side}{li}", 0.045, 0.02, 0.02, ctx.mats["iron"], g, segments=10,
                      location=(0.6, y, pivot_z - 0.15 - li * 0.1), rotation=(math.pi / 2, 0, (li % 2) * math.pi / 2))
        box(ctx, f"ER_weight_{side}", (0.6, y, pivot_z - 2.65), (0.35, 0.35, 0.7), "granite", g, bevel=0.03)
    return g


def build_spiral_stair(ctx, parent):
    """Cầu thang xoắn ốc đá vôi quanh trục giếng: 56 bậc từ tĩnh thất (z −1,2) lên sàn tường răng cưa (z 7,9)."""
    g = group(ctx, "ER_spiral_stair", parent)
    n = 56
    z0, z1 = -1.2, Z_PARAPET0
    for i in range(n):
        a = 2 * math.pi * i / 16
        z = z0 + (z1 - z0) * i / n
        st = box(ctx, f"ER_stair_step_{i}", (0, 0, 0), (1.25, 0.42, 0.16), "limestone_step", g, bevel=0.015)
        r = 1.35 + 0.65
        st.location = (r * math.cos(a), r * math.sin(a), z)
        st.rotation_euler = (0, 0, a)
    return g


def build_sanctuary(ctx, parent):
    """Tĩnh thất ngầm (canon): không cửa sổ/gương, lỗ thông gió sát trần, 12 cung hoàng đạo, 3 lớp thảm đỏ,
    giường tuyết tùng chạm hoa sen, bàn thấp, nến sáp ong trắng, cửa sồi vòm."""
    g = group(ctx, "ER_sanctuary", parent)
    z0, hw, hh = -4.4, 2.6, 2.6
    box(ctx, "ER_sanct_floor", (0, 0, z0 - 0.15), (2 * hw + 0.6, 2 * hw + 0.6, 0.3), "basalt", g)
    for k in range(4):
        th = k * math.pi / 2
        w = box(ctx, f"ER_sanct_wall_{k}", (0, 0, 0), (0.3, 2 * hw + 0.6, hh), "basalt", g)
        place_on_face(w, th, hw + 0.15, z0 + hh / 2)
        for j in range(3):   # 3 cung hoàng đạo mỗi tường → 12
            zr = lathe(ctx, f"ER_zodiac_relief_{k}{j}", [(0, 0), (0.32, 0), (0.32, 0.05), (0.24, 0.08), (0.12, 0.11), (0, 0.12)],
                       "basalt_trim", g, segments=24, rotation=(0, -math.pi / 2, 0))
            place_on_face(zr, th + math.pi, hw - 0.05, z0 + 1.5, along=(j - 1) * 1.5)
            zr.name = f"ER_sanct_zodiac_{k * 3 + j}"
        vent = box(ctx, f"ER_sanct_vent_{k}", (0, 0, 0), (0.32, 0.6, 0.12), "iron", g, bevel=0.01)
        place_on_face(vent, th + math.pi, hw - 0.12, z0 + hh - 0.3)
    vault = lathe(ctx, "ER_sanct_vault", [(hw + 0.3, 0), (hw + 0.3, 0.3), (hw * 0.8, 1.0), (hw * 0.45, 1.35), (0, 1.45)],
                  "basalt", g, segments=4, location=(0, 0, z0 + hh), rotation=(0, 0, math.pi / 4))
    for i, (s, dz) in enumerate(((3.2, 0.0), (2.8, 0.02), (2.3, 0.04))):
        box(ctx, f"ER_sanct_carpet_{i}", (0, 0, z0 + 0.01 + dz), (s, s * 0.8, 0.02), "wool_red", g, bevel=0.004, uv=1.2)
    bed = group(ctx, "ER_sanct_bed", g)
    box(ctx, "ER_sanct_bed_frame", (0, 1.4, z0 + 0.28), (2.1, 1.1, 0.35), "cedar", bed, bevel=0.03)
    box(ctx, "ER_sanct_bed_headboard", (0, 1.98, z0 + 0.75), (2.1, 0.08, 1.1), "cedar", bed, bevel=0.02)
    box(ctx, "ER_sanct_blanket", (0, 1.35, z0 + 0.5), (1.9, 1.0, 0.12), "wool_white", bed, bevel=0.05)
    for k in range(8):   # hoa sen chạm trên đầu giường
        a = 2 * math.pi * k / 8
        petal = lathe(ctx, f"ER_sanct_lotus_{k}", [(0, 0), (0.07, 0.06), (0.05, 0.2), (0, 0.26)], "cedar", bed, segments=10,
                      location=(0, 1.93, z0 + 0.95), rotation=(0, a, 0))
    box(ctx, "ER_sanct_table", (0, -0.6, z0 + 0.22), (0.9, 0.55, 0.06), "cedar", g, bevel=0.01)
    for k, (x, y) in enumerate(((-0.35, -0.8), (0.35, -0.8), (-0.35, -0.4), (0.35, -0.4))):
        box(ctx, f"ER_sanct_table_leg{k}", (x, y, z0 + 0.1), (0.06, 0.06, 0.2), "cedar", g, bevel=0.005)
    for k, (x, y) in enumerate(((-2.0, -2.0), (2.0, -2.0), (-2.0, 2.0), (2.0, 2.0), (-0.9, 1.9), (0.9, 1.9))):
        lathe(ctx, f"ER_sanct_candle_stand{k}", [(0, 0), (0.16, 0), (0.05, 0.08), (0.04, 0.9), (0.12, 0.95), (0, 0.97)], "cedar",
              g, segments=12, location=(x, y, z0))
        lathe(ctx, f"ER_sanct_candle{k}", [(0, 0), (0.07, 0), (0.07, 0.45), (0.01, 0.47), (0, 0.5)], "wax", g, segments=14,
              location=(x, y, z0 + 0.96))
    wall_frame(ctx, "ER_sanct_door_arch", lancet_outline(1.5, 2.3), lancet_outline(1.2, 2.15), 0.2, math.pi, hw - 0.2, z0,
               "basalt_trim", g)
    wall_profile(ctx, "ER_sanct_door", lancet_outline(1.2, 2.15), 0.08, math.pi, hw - 0.1, z0, "oak", g)
    return g
