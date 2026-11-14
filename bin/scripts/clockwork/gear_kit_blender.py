"""Dựng bộ máy đồng hồ trong Blender từ đặc tả `mechanism.py` — bánh răng thân khai thật (không phải hình trụ trơn).

Đơn vị đặc tả: mm → Blender: m (× MM). Mỗi bánh răng nằm trong mặt phẳng vuông góc trục của nó, tâm tại gốc trục.
"""

from __future__ import annotations

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from gear_math import involute_tooth, outer_radius, pitch_radius, root_radius

MM = 0.001


def _uv_and_mat(obj, mat, uv_scale):
    import _aaa_monument_kit as kit
    kit.apply_box_uv_and_mat(obj, mat, uv_scale=uv_scale)


def _link(scene, bm, name, mat, parent, uv_scale=40.0, smooth=False):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    if smooth:
        for p in mesh.polygons:
            p.use_smooth = True
    obj = bpy.data.objects.new(name, mesh)
    scene.collection.objects.link(obj)
    _uv_and_mat(obj, mat, uv_scale)
    if parent is not None:
        obj.parent = parent
    return obj


def _resample_closed(pts, n):
    pts = list(pts) + [pts[0]]
    seg = [math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    total = sum(seg)
    out, acc, i = [], 0.0, 0
    for k in range(n):
        t = total * k / n
        while i < len(seg) - 1 and acc + seg[i] < t:
            acc += seg[i]
            i += 1
        f = 0.0 if seg[i] == 0 else (t - acc) / seg[i]
        out.append((pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f))
    return out


def gear_outline(module: float, teeth: int, samples: int = 8) -> list[tuple[float, float]]:
    """Biên dạng kín của cả bánh răng (mm), ngược chiều kim đồng hồ."""
    tooth = involute_tooth(module, teeth, samples=samples)
    pts = []
    for i in range(teeth):
        a = 2 * math.pi * i / teeth
        ca, sa = math.cos(a), math.sin(a)
        pts += [(x * ca - y * sa, x * sa + y * ca) for x, y in tooth]
    return pts


def build_spur_gear(scene, gear, mat, parent, spokes: int = 5, sector_deg: float | None = None):
    """Bánh răng trụ răng thẳng, dựng trong mặt XY quanh gốc, dày theo Z. Vành răng thân khai luôn có; phần giữa
    theo `gear.style`: spoked = moay-ơ + 5 nan hoa, disc = moay-ơ + đĩa đặc, ring = để trống (vành mặt đồng hồ)."""
    m, z = gear.module, gear.teeth
    t = gear.thickness * MM
    outline = gear_outline(m, z)
    rf = root_radius(m, z)
    rim_in = max(rf - 2.2 * m, rf * 0.55)
    n = len(outline)
    inner = [(rim_in * math.cos(2 * math.pi * k / n + math.atan2(outline[0][1], outline[0][0])),
              rim_in * math.sin(2 * math.pi * k / n + math.atan2(outline[0][1], outline[0][0]))) for k in range(n)]
    bm = bmesh.new()

    def ring(pts, zz):
        return [bm.verts.new((x * MM, y * MM, zz)) for x, y in pts]

    of, ob = ring(outline, t / 2), ring(outline, -t / 2)
    inf, inb = ring(inner, t / 2), ring(inner, -t / 2)
    for k in range(n):
        j = (k + 1) % n
        bm.faces.new([of[k], of[j], inf[j], inf[k]])
        bm.faces.new([ob[j], ob[k], inb[k], inb[j]])
        bm.faces.new([of[j], of[k], ob[k], ob[j]])
        bm.faces.new([inf[k], inf[j], inb[j], inb[k]])
    obj = _link(scene, bm, f"CW_{gear.id}", mat, parent)
    style = getattr(gear, "style", "spoked")
    if style == "ring":
        return obj
    # moay-ơ + nan hoa / đĩa (object con để quay theo bánh)
    hub_r = max(rim_in * 0.22, 1.2 * m)
    hb = bmesh.new()
    bmesh.ops.create_cone(hb, cap_ends=True, segments=24, radius1=hub_r * MM, radius2=hub_r * MM, depth=t * 1.4)
    _link(scene, hb, f"CW_{gear.id}_hub", mat, obj, smooth=True)
    if style == "disc":
        # đĩa mỏng hơn vành, có gân tròn ở giữa — đọc rõ là bánh đúc đặc chứ không phải hình trụ trơn
        wb = bmesh.new()
        prof = [(hub_r, -t * 0.3), (rim_in * 1.01, -t * 0.3), (rim_in * 1.01, t * 0.3), (hub_r, t * 0.3)]
        rib = (hub_r + rim_in) / 2
        prof[2:2] = [(rib + m, t * 0.3), (rib + m * 0.6, t * 0.45), (rib - m * 0.6, t * 0.45), (rib - m, t * 0.3)]
        rings = [[wb.verts.new((r * MM * math.cos(2 * math.pi * k / 64), r * MM * math.sin(2 * math.pi * k / 64), zz))
                  for k in range(64)] for r, zz in prof]
        for a, b in zip(rings, rings[1:] + rings[:1]):
            for k in range(64):
                wb.faces.new([a[k], a[(k + 1) % 64], b[(k + 1) % 64], b[k]])
        _link(scene, wb, f"CW_{gear.id}_web", mat, obj)
        return obj
    for s in range(spokes):
        a = 2 * math.pi * s / spokes
        sb = bmesh.new()
        bmesh.ops.create_cube(sb, size=1.0)
        L = (rim_in - hub_r) * MM
        for v in sb.verts:
            v.co.x *= L * 1.08
            v.co.y *= max(0.9 * m, rim_in * 0.08) * MM
            v.co.z *= t * 0.7
            v.co.x += (hub_r * MM + L / 2)
            v.co = Matrix.Rotation(a, 3, "Z") @ v.co
        _link(scene, sb, f"CW_{gear.id}_spoke{s}", mat, obj)
    return obj


def build_shaft(scene, name, length_mm, radius_mm, mat, parent):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius_mm * MM, radius2=radius_mm * MM, depth=length_mm * MM)
    return _link(scene, bm, name, mat, parent, smooth=True)


def build_lead_screw(scene, name, length_mm, radius_mm, pitch_mm, mat, parent):
    """Trục vít: lõi + ren xoắn (chuỗi đoạn nghiêng theo bước ren)."""
    core = build_shaft(scene, name, length_mm, radius_mm * 0.8, mat, parent)
    turns = max(1, int(length_mm / pitch_mm))
    seg = 12
    bm = bmesh.new()
    prev = None
    for i in range(turns * seg + 1):
        a = 2 * math.pi * i / seg
        zz = (-length_mm / 2 + pitch_mm * i / seg) * MM
        p_in = Vector((radius_mm * 0.8 * MM * math.cos(a), radius_mm * 0.8 * MM * math.sin(a), zz))
        p_out = Vector((radius_mm * 1.15 * MM * math.cos(a), radius_mm * 1.15 * MM * math.sin(a), zz))
        h = Vector((0, 0, pitch_mm * 0.18 * MM))
        quad = [bm.verts.new(p_in - h), bm.verts.new(p_out - h * 0.3), bm.verts.new(p_out + h * 0.3), bm.verts.new(p_in + h)]
        if prev:
            for k in range(4):
                bm.faces.new([prev[k], prev[(k + 1) % 4], quad[(k + 1) % 4], quad[k]])
        prev = quad
    _link(scene, bm, f"{name}_thread", mat, core)
    return core


def axis_matrix(axis) -> Matrix:
    """Ma trận xoay đưa trục Z cục bộ về hướng `axis`."""
    return Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized()).to_matrix().to_4x4()
