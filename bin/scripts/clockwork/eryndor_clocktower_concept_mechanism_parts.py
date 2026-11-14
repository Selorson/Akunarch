"""
Bộ phận riêng của Tháp Eryndor BẢN CƠ KHÍ — động cơ chung `assemble_mechanism_glb.py` tự gọi `build(...)`.

Nguồn: concept `projects/eryndor-clocktower-concept/concepts/concept_eryndor_clockwork_hero.jpg` (anh duyệt 2026-11-14),
thiết kế `docs/p0/eryndor_clockwork_design.md`. Bánh răng & trục do động cơ dựng từ `<slug>.mechanism.json`.

Vỏ tháp dùng lại `monuments/eryndor_parts.py` (cùng số đo bản thật, kích thước thật) với bộ vật liệu đồng, rồi bỏ
tường thân dưới / tường thân trên để lộ bộ máy như concept. Module này chỉ thêm phần concept có mà động cơ không dựng:
con lắc + neo thoát, khung đỡ bộ máy, búa chuông + chốt trống, ống đồng trên trụ ốp, và gom các mảnh mặt đồng hồ
thành nhóm quay (vòng hoàng đạo, kim).
"""

from __future__ import annotations

import math

from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

import _aaa_monument_kit as kit
import eryndor_parts as ep
from mechanism import solve_kinematics

MM = 0.001
# chi tiết chạm trổ nặn bằng TRELLIS.2 từ ảnh FLUX (qua hàng đợi: gpu_enqueue 'comfyui' {mode: 'comfy_workflow'})
SCULPT_DIR = Path(r"E:\Akunarch\projects\eryndor-clocktower-concept\clockwork\parts")
PORTAL_SCULPT = SCULPT_DIR / "eryndor_portal_tracery.glb"
PANEL_SCULPT = SCULPT_DIR / "eryndor_buttress_panel.glb"
PINNACLE_SCULPT = SCULPT_DIR / "eryndor_pinnacle.glb"
HOOD_SCULPT = SCULPT_DIR / "eryndor_clock_hood.glb"
TAIL = 0.22   # đuôi búa (m) — chốt trống đi qua dưới đầu đuôi

# Mảnh của bản thật KHÔNG có trong concept cơ khí (tường bị bỏ để lộ bộ máy). Thiếu tên nào → lỗi ngay, để danh sách
# này không lặng lẽ lệch khi eryndor_parts đổi tên.
DROP = (
    ["ER_base_wall", "ER_base_string", "ER_door_blind_panel", "ER_upper_wall", "ER_clock_face_ring0"]
    + [f"ER_lancet_{i}" for i in range(4)]                     # cửa sổ thân dưới: tường không còn
    + [f"ER_blind_{i}" for i in range(3)]
    + [f"ER_lancet_{i}" for i in (4, 5, 6)] + [f"ER_hood_up{i}" for i in range(3)]   # thân trên: thay bằng cổng vòm lớn
    + [f"ER_corbel_{k}_{j}" for k in range(8) for j in range(7)]  # hàng đá nhô → vành răng lớn quanh chân tường răng cưa
    + [f"ER_buttress_{k}_panel{lvl}_grp" for k in range(8) for lvl in range(3)]   # → tấm chạm nặn
    + [f"ER_pinnacle_{i}" for i in range(8)] + ["ER_clock_hood"]                  # → chóp nhọn, mái vòm nặn
)


def materials() -> dict:
    ph = kit.build_polyhaven_gltf_material
    # đồng cổ (concept: đồng già, tương phản mạnh): hoa văn mòn/xước lấy từ texture gỉ Poly Haven (CC0), nhuộm màu đồng;
    # tấm vỏ tối, viền sáng hơn, bánh răng (vật liệu động cơ) sáng nhất
    bronze = ph("ER_cw_bronze", "rusty_metal_04", base_override_linear=(0.24, 0.16, 0.07), metallic=0.9,
                rough_scale=0.85, rough_bias=0.05, contrast=1.8, ao_strength=0.8)
    brass = ph("ER_cw_brass", "rusty_metal_03", base_override_linear=(0.46, 0.32, 0.13), metallic=1.0,
               rough_scale=0.65, rough_bias=0.04, contrast=1.6, ao_strength=0.8)
    return {
        "basalt": bronze,
        "basalt_trim": brass,
        "limestone_step": bronze,
        "oak": bronze,
        "brass": brass,
        "bronze": ph("ER_cw_bell_bronze", "rusty_metal_03", base_override_linear=(0.35, 0.23, 0.09), metallic=1.0,
                     rough_scale=0.6, contrast=1.4),
        "slate": ph("ER_cw_copper", "rusty_metal_sheet", base_override_linear=(0.28, 0.12, 0.06), metallic=0.95,
                    rough_scale=0.7, contrast=1.5),
        "iron": ph("ER_cw_iron", "metal_plate_02", base_override_linear=(0.07, 0.07, 0.075), metallic=0.85,
                   rough_scale=0.9),
        "enamel": ph("ER_cw_dial_dark", "rusty_metal_04", base_override_linear=(0.11, 0.08, 0.045), metallic=0.85,
                     rough_scale=0.5),
        "glass": ph("ER_cw_glass_unused", "metal_plate_02", base_override_linear=(0.05, 0.035, 0.02)),
        "granite": ph("ER_cw_granite", "rock_face_03", tint_rgb=(0.78, 0.74, 0.72)),
        # vàng đánh bóng cho số La Mã + vạch giờ: sáng, ít nhám, nổi trên nền mặt số tối (anh yêu cầu)
        # (kim loại một phần: kim loại 100% chỉ phản chiếu môi trường tối của sân khấu → chữ vẫn tối; không dùng phát sáng — Luật #6)
        "gilt": ph("ER_cw_gilt", "metal_plate_02", base_override_linear=(1.0, 0.80, 0.38), metallic=0.35,
                   rough_scale=0.35, rough_bias=0.05, contrast=0.6),
        "ruby": ph("ER_cw_ruby", "metal_plate_02", base_override_linear=(0.45, 0.02, 0.05), metallic=0.2,
                   rough_scale=0.25),
    }


def _drop(name: str):
    ob = bpy.data.objects.get(name)
    if ob is None:
        raise KeyError(f"Không có '{name}' để bỏ — eryndor_parts đã đổi tên? Sửa DROP.")
    for ch in list(ob.children_recursive):
        bpy.data.objects.remove(ch, do_unlink=True)
    bpy.data.objects.remove(ob, do_unlink=True)


def _regroup(scene, name: str, members: list[str], parent) -> bpy.types.Object:
    """Gom các mảnh (giữ nguyên vị trí thế giới) vào một empty ở gốc để quay chung quanh trục của motion."""
    bpy.context.view_layer.update()
    g = kit.create_part_empty(scene, name)
    g.parent = parent
    for n in members:
        ob = bpy.data.objects[n]
        mw = ob.matrix_world.copy()
        ob.parent = g
        ob.matrix_world = mw
    return g


def _mm(v) -> Vector:
    return Vector(v) * MM


def rivets(ctx: ep.Ctx, name: str, points, parent, r: float = 0.035):
    """Một mesh gồm nhiều đinh tán chỏm cầu (gộp để không đẻ hàng trăm object)."""
    bm = bmesh.new()
    for p in points:
        res = bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=4, radius=r)
        bmesh.ops.translate(bm, vec=Vector(p), verts=res["verts"])
    return ep._finish(ctx, bm, name, "basalt_trim", parent, uv_scale=2.0, smooth=True)


def _instances(ctx: ep.Ctx, src, placements, parent):
    """Đặt các bản (chung mesh với `src`): placements = [(vị trí, góc quay Z, tỉ lệ)]; bản đầu dùng chính `src`."""
    for i, (loc, rz, sc) in enumerate(placements):
        ob = src if i == 0 else src.copy()
        if i:
            ob.name = f"{src.name}_{i}"
            ctx.scene.collection.objects.link(ob)
        ob.location, ob.rotation_euler, ob.scale = loc, (0, 0, rz), (sc, sc, sc)
        ob.parent = parent


def build_buttress_panels(ctx: ep.Ctx, parent):
    """Tấm chạm hoa văn (nặn) trên mặt trước 3 tầng của 8 trụ ốp — cùng chỗ tấm chữ X của bản thật."""
    levels = ((ep.Z_PLINTH, 3.4, 1.6, 1.15), (3.4, 5.6, 1.35, 0.85), (5.6, ep.Z_BASE_TOP, 1.1, 0.55))
    h0 = (levels[0][1] - levels[0][0]) * 0.66
    src = import_sculpt(ctx, PANEL_SCULPT, "CW_buttress_panel", decimate=0.07, height=h0, depth=0.08)
    places = []
    for k in range(8):
        th = math.radians(22.5) + k * math.pi / 4
        n = Vector((math.cos(th), math.sin(th), 0))
        for z0, z1, _wd, pr in levels:
            h = (z1 - z0) * 0.66
            places.append((n * (ep.OCT_R + pr + 0.04) + Vector((0, 0, z0 + (z1 - z0) * 0.17)), th + math.pi / 2, h / h0))
    _instances(ctx, src, places, parent)


def build_pinnacles(ctx: ep.Ctx, parent):
    """8 tháp nhọn (nặn): 4 cao ở góc gác chuông, 4 thấp ở góc lan can — cùng vị trí/cao độ bản thật."""
    sets = ((ep.BEL_HALF + 0.05, ep.Z_BEL0, 5.3), (ep.UP_HALF + 0.38, ep.Z_UP1 + 0.4, 3.1))
    src = import_sculpt(ctx, PINNACLE_SCULPT, "CW_pinnacle", decimate=0.25, height=sets[0][2])
    places = []
    for half, z0, hgt in sets:
        for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            places.append((Vector((sx * half, sy * half, z0)), math.atan2(sy, sx) + math.pi / 2, hgt / sets[0][2]))
    _instances(ctx, src, places, parent)


def build_clock_hood(ctx: ep.Ctx, parent):
    """Mái vòm cong (nặn) trùm 3 mặt phụ phía trên mặt đồng hồ, hai đầu cuộn xoắn — thay mái vòm hình học."""
    hz0 = ep.CLOCK_Z + ep.CLOCK_R + 0.12
    ob = import_sculpt(ctx, HOOD_SCULPT, "CW_clock_hood", decimate=0.5, width=2 * 2.3 + 0.5, depth=0.75, min_island=0.25)
    ob.location = (ep.UP_HALF + 0.375, 0, hz0 - 0.45)
    ob.rotation_euler = (0, 0, math.pi / 2)        # mặt trước nặn hướng −Y → quay ra +X (mặt đồng hồ)
    ob.parent = parent


def finish_dial(ctx: ep.Ctx):
    """Mặt đồng hồ bản cơ khí: vòng hoàng đạo về đồng tâm (bản thật để lệch tâm kiểu đồng hồ thiên văn cổ, nhưng ở đây nó
    quay quanh tâm mặt số nên lệch tâm thì chao — anh bắt lỗi); số La Mã + vạch giờ đổi sang vàng đánh bóng."""
    dz = ep.CLOCK_R * 0.13     # độ lệch tâm của vòng hoàng đạo trong eryndor_parts._dial
    for n in ["ER_clock_face_zodiac_ring"] + [f"ER_zodiac_{k}" for k in range(12)]:
        bpy.data.objects[n].location.z -= dz
    for ob in bpy.data.objects:
        if ob.type == "MESH" and ob.name.startswith(("ER_numeral_", "ER_clock_face_tick")):
            ob.data.materials.clear()
            ob.data.materials.append(ctx.mats["gilt"])


def build_upper_rivets(ctx: ep.Ctx, parent):
    """Đinh tán dọc 4 trụ góc thân trên (concept: viền tán đinh)."""
    pts = []
    for sx, sy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
        px, py = sx * (ep.UP_HALF + 0.05), sy * (ep.UP_HALF + 0.05)
        for z in [ep.Z_UP0 + 0.25 + 0.4 * i for i in range(23)]:
            for e in (-0.2, 0.2):
                pts += [(px + sx * 0.28, py + e, z), (px + e, py + sy * 0.28, z)]
    rivets(ctx, "CW_upper_pilaster_rivets", pts, parent)


def build_base_details(ctx: ep.Ctx, parent):
    """Vòng đai trên cột thép giữa + đinh tán quanh bệ bát giác."""
    for i, z in enumerate((4.45, 5.15, 6.95)):
        ep.lathe(ctx, f"CW_column_collar_{i}", [(0, -0.09), (0.34, -0.09), (0.36, -0.05), (0.36, 0.05), (0.34, 0.09),
                                                 (0, 0.09)], "basalt_trim", parent, segments=32, location=(0, 0, z))
    pts = []
    for k in range(8):
        o, u, _n = ep._face_frame(k * math.pi / 4, ep.OCT_APOTHEM * 1.035 + 0.01)
        w = 2 * ep.OCT_APOTHEM * 1.035 * math.tan(math.radians(22.5))
        for i in range(12):
            q = o + u * (-w / 2 + w * (i + 0.5) / 12)
            pts.append((q.x, q.y, 0.78))
    rivets(ctx, "CW_plinth_rivets", pts, parent, r=0.045)


def build_upper_frame(ctx: ep.Ctx, parent):
    """Thân trên: tấm đồng sau mặt đồng hồ (+X); 3 mặt còn lại là tường NGUYÊN, chỉ khoét đúng dáng khung cổng nặn
    (thụt vào trong mép ngoài khung `PORTAL_OVERLAP`, viền khung đè lên mép tường) — không còn khe hở quanh khung
    (anh bắt lỗi v9: ô khoét ngũ giác to hơn khung vòm nhọn → hở tam giác trên đỉnh và 2 dải bên)."""
    h = ep.Z_UP1 - ep.Z_UP0
    half = ep.UP_HALF
    outer = [(-half, 0), (-half, h), (half, h), (half, 0), (-half, 0)]
    ep.wall_profile(ctx, "CW_upper_plate_front", outer[:-1], 0.1, 0.0, half - 0.12, ep.Z_UP0, "basalt", parent)
    v0 = 0.45
    portal = build_portal_sculpts(ctx, parent, bottom=ep.Z_UP0 + v0, height=h - v0 - 0.9)
    opening = [(u, v + v0) for u, v in silhouette_opening(portal.data, PORTAL_OVERLAP)]
    for k, deg in enumerate((90, 180, -90)):
        ep.wall_frame(ctx, f"CW_upper_frame_{k}", outer, opening, 0.12, math.radians(deg), half - 0.12, ep.Z_UP0,
                      "basalt", parent, n=96)


PORTAL_OVERLAP = 0.12   # m: ô khoét nhỏ hơn mép ngoài khung cổng chừng này mỗi bên


def silhouette_opening(me, margin: float, bins: int = 64) -> list[tuple[float, float]]:
    """Dáng nhìn thẳng của mesh (đáy tại z=0, đối xứng quanh x=0): nửa bề rộng lớn nhất theo từng dải cao, thu vào
    `margin`; trả đường kín (u, v) đi lên mép trái, qua đỉnh, xuống mép phải — cùng chiều với khung chữ nhật ngoài."""
    top = max(v.co.z for v in me.vertices)
    hw = [0.0] * bins
    for v in me.vertices:
        i = min(int(v.co.z / top * bins), bins - 1)
        hw[i] = max(hw[i], abs(v.co.x))
    # lấy hẹp nhất của 3 dải liền kề: ở bậc chuyển (vòm nhọn gặp trụ đứng) không bị khoét theo phần trụ rộng → hở khe
    hw = [min(hw[max(i - 1, 0):i + 2]) for i in range(bins)]
    pts = [(w - margin, (i + 0.5) / bins * top) for i, w in enumerate(hw) if w - margin > 0.02]
    pts = [(w, z) for w, z in pts if z <= pts[-1][1]]
    return [(-w, z) for w, z in pts] + [(w, z) for w, z in reversed(pts)] + [(-pts[0][0], pts[0][1])]


def _drop_small_islands(me, frac: float):
    """Bỏ các mảnh rời có đường chéo hộp bao < `frac` × mảnh lớn nhất (vd cuộn xoắn thừa FLUX vẽ lơ lửng)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    seen, islands = set(), []
    for f in bm.faces:
        if f in seen:
            continue
        stack, isl = [f], []
        seen.add(f)
        while stack:
            cur = stack.pop()
            isl.append(cur)
            for e in cur.edges:
                for nb in e.link_faces:
                    if nb not in seen:
                        seen.add(nb)
                        stack.append(nb)
        vs = {v for fc in isl for v in fc.verts}
        lo = Vector((min(v.co.x for v in vs), min(v.co.y for v in vs), min(v.co.z for v in vs)))
        hi = Vector((max(v.co.x for v in vs), max(v.co.y for v in vs), max(v.co.z for v in vs)))
        islands.append(((hi - lo).length, isl))
    big = max(d for d, _ in islands)
    dead = [f for d, isl in islands if d < frac * big for f in isl]
    bmesh.ops.delete(bm, geom=dead, context="FACES")
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bm.to_mesh(me)
    bm.free()


def import_sculpt(ctx: ep.Ctx, path: Path, name: str, decimate: float, height: float | None = None,
                  width: float | None = None, depth: float | None = None, min_island: float = 0.0) -> bpy.types.Object:
    """Nhập 1 mesh nặn (.glb TRELLIS.2, giữ vật liệu PBR + normal map nướng sẵn của nó), chuẩn hoá: đáy-giữa tại gốc,
    cao `height` (hoặc rộng `width`), dày `depth` theo trục Y (bỏ trống = giữ tỉ lệ), mặt trước hướng −Y như lúc nặn;
    giảm tam giác còn `decimate` phần; `min_island` > 0 thì bỏ mảnh rời nhỏ."""
    if not path.is_file():
        raise FileNotFoundError(f"Chưa có chi tiết nặn {path} — chạy lại bước FLUX → TRELLIS.2 (docs/ops/QUY_TRINH_BAN_CO_KHI.md).")
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(path))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if len(meshes) != 1:
        raise RuntimeError(f"{path.name}: cần đúng 1 mesh, có {len(meshes)}.")
    ob = meshes[0]
    bpy.context.view_layer.update()
    ob.data.transform(ob.matrix_world)
    ob.parent = None
    ob.matrix_world = Matrix.Identity(4)
    ob.rotation_mode = "XYZ"   # importer glTF để QUATERNION → rotation_euler gán sau sẽ bị bỏ qua (lỗi v7: cổng lệch 90°)
    for o in new:
        if o is not ob:
            bpy.data.objects.remove(o, do_unlink=True)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    ctx.scene.collection.objects.link(ob)
    if min_island > 0:
        _drop_small_islands(ob.data, min_island)
    co = [v.co for v in ob.data.vertices]
    mn = Vector((min(c.x for c in co), min(c.y for c in co), min(c.z for c in co)))
    mx = Vector((max(c.x for c in co), max(c.y for c in co), max(c.z for c in co)))
    k = height / (mx.z - mn.z) if height else width / (mx.x - mn.x)
    ky = depth / (mx.y - mn.y) if depth else k
    ob.data.transform(Matrix.Diagonal((k, ky, k, 1.0))
                      @ Matrix.Translation(-Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))))
    mod = ob.modifiers.new("decimate", "DECIMATE")
    mod.ratio = decimate
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    ob.modifiers.clear()
    old, ob.data = ob.data, me
    bpy.data.meshes.remove(old)
    ob.name = me.name = name
    return ob


def build_portal_sculpts(ctx: ep.Ctx, parent, bottom: float, height: float) -> bpy.types.Object:
    """Khung cổng vòm nhọn hoa văn rỗng (nặn TRELLIS.2) trên 3 mặt hở thân trên — 3 bản dùng chung 1 mesh; trả bản gốc
    (mesh đã chuẩn hoá: đáy-giữa tại gốc) để khoét tường theo đúng dáng."""
    src = import_sculpt(ctx, PORTAL_SCULPT, "CW_portal_tracery", decimate=0.35, height=height, depth=0.3)
    for k, deg in enumerate((90, 180, -90)):
        th = math.radians(deg)
        ob = src if k == 0 else src.copy()
        if k:
            ob.name = f"CW_portal_tracery_{k}"
            ctx.scene.collection.objects.link(ob)
        n = Vector((math.cos(th), math.sin(th), 0))
        ob.location = n * (ep.UP_HALF + 0.15) + Vector((0, 0, bottom))
        ob.rotation_euler = (0, 0, th + math.pi / 2)    # mặt trước nặn hướng −Y → quay ra pháp tuyến mặt tường
        ob.parent = parent
    return src


def build_movement_frame(ctx: ep.Ctx, parent, raw):
    """Khung đỡ bộ máy sau đoàn bánh răng (mặt phẳng y = −1,05 m): thanh đồng + chân kính hồng ngọc ở đầu trục."""
    g = ep.group(ctx, "CW_movement_frame", parent)
    y = -0.7
    ep.box(ctx, "CW_frame_top", (-0.3, y, 16.75), (3.8, 0.1, 0.14), "basalt_trim", g)
    ep.box(ctx, "CW_frame_bottom", (-0.3, y, 8.45), (3.8, 0.1, 0.14), "basalt_trim", g)
    for k, x in enumerate((-2.15, 1.55)):
        ep.box(ctx, f"CW_frame_post{k}", (x, y, 12.6), (0.14, 0.1, 8.3), "basalt_trim", g)
    # dầm treo con lắc chạy ngang mặt hở
    ep.box(ctx, "CW_pendulum_beam", (0, -2.05, 16.75), (5.2, 0.16, 0.18), "basalt_trim", g)
    for sid in ("s_esc", "s_t1", "s_up", "s_d1", "s_d3"):
        s = next(x for x in raw["shafts"] if x["id"] == sid)
        p = _mm(s["origin"])
        ep.box(ctx, f"CW_frame_cross_{sid}", (p.x, y, p.z), (0.5, 0.08, 0.1), "basalt_trim", g)
        ep.lathe(ctx, f"CW_jewel_{sid}", [(0, -0.07), (0.08, -0.05), (0.08, 0.05), (0, 0.07)], "ruby", g, segments=16,
                 location=(p.x, y - 0.06, p.z), rotation=(math.pi / 2, 0, 0))
    return g


def build_pendulum(ctx: ep.Ctx, parent, pivot: Vector) -> bpy.types.Object:
    """Con lắc neo 4 m (canon) + neo thoát hai móc ôm bánh thoát. Dựng ở toạ độ thế giới, nhóm quay quanh `pivot`."""
    g = ep.group(ctx, "CW_pendulum", parent)
    L = 4.0
    ep.box(ctx, "CW_pendulum_rod", (pivot.x, pivot.y, pivot.z - L / 2), (0.06, 0.06, L), "iron", g, bevel=0.01)
    ep.lathe(ctx, "CW_pendulum_bob", [(0, -0.13), (0.3, -0.11), (0.45, 0), (0.3, 0.11), (0, 0.13)], "granite", g,
             segments=32, location=(pivot.x, pivot.y, pivot.z - L), rotation=(math.pi / 2, 0, 0))
    ep.lathe(ctx, "CW_pendulum_hub", [(0, -0.09), (0.12, -0.09), (0.12, 0.09), (0, 0.09)], "brass", g, segments=20,
             location=tuple(pivot), rotation=(math.pi / 2, 0, 0))
    for sgn in (-1, 1):   # hai cánh neo + móc (pallet) xuống tới vành bánh thoát
        arm = ep.box(ctx, f"CW_anchor_arm_{'LR'[sgn > 0]}", (0, 0, 0), (0.5, 0.05, 0.07), "iron", g)
        arm.location = (pivot.x + sgn * 0.2, pivot.y + 0.25, pivot.z - 0.14)
        arm.rotation_euler = (0, sgn * math.radians(32), 0)
        pal = ep.box(ctx, f"CW_anchor_pallet_{'LR'[sgn > 0]}", (0, 0, 0), (0.06, 0.06, 0.16), "ruby", g, bevel=0.01)
        pal.location = (pivot.x + sgn * 0.4, pivot.y + 0.25, pivot.z - 0.32)
    return g


def build_hammer(ctx: ep.Ctx, parent, name: str, pivot: Vector, toward: Vector, tail_dir: Vector) -> bpy.types.Object:
    """Búa chuông: cán từ trục xoay lên tới vành dưới quả chuông (theo hướng `toward`), đầu búa tròn, đuôi (hướng
    `tail_dir`, dài TAIL) gác lên đường đi của chốt trống."""
    g = ep.group(ctx, name, parent)
    head = pivot + toward * 0.18 + Vector((0, 0, 0.33))
    mid = (pivot + head) / 2
    d = head - pivot
    arm = ep.box(ctx, f"{name}_arm", (0, 0, 0), (0.05, 0.05, d.length), "iron", g, bevel=0.008)
    arm.location = mid
    arm.rotation_euler = d.to_track_quat("Z", "Y").to_euler()
    ep.lathe(ctx, f"{name}_head", [(0, -0.09), (0.07, -0.08), (0.08, 0), (0.07, 0.08), (0, 0.09)], "iron", g,
             segments=16, location=tuple(head), rotation=toward.to_track_quat("Z", "Y").to_euler())
    tail = pivot + tail_dir * TAIL - Vector((0, 0, 0.05))
    t = ep.box(ctx, f"{name}_tail", (0, 0, 0), (0.05, 0.05, TAIL + 0.04), "iron", g, bevel=0.008)
    t.location = (pivot + tail) / 2
    t.rotation_euler = (tail - pivot).to_track_quat("Z", "Y").to_euler()
    ep.lathe(ctx, f"{name}_pivot", [(0, -0.06), (0.05, -0.06), (0.05, 0.06), (0, 0.06)], "brass", g, segments=12,
             location=tuple(pivot), rotation=(0, math.pi / 2, 0) if abs(toward.x) < 0.5 else (math.pi / 2, 0, 0))
    return g


def build_hammer_post(ctx: ep.Ctx, parent, name: str, pivot: Vector):
    """Giá treo trục búa (đứng yên): thanh đứng từ trục xoay lên ngang xà chuông + tay nối vào xà (sàn có trống)."""
    top = ep.BELL_BEAM_Z
    ep.box(ctx, name, (pivot.x, pivot.y, (top + pivot.z) / 2), (0.08, 0.08, top - pivot.z), "basalt_trim", parent)
    ep.box(ctx, f"{name}_arm", (pivot.x, pivot.y / 2, top), (0.08, abs(pivot.y), 0.08), "basalt_trim", parent)


def build_drum_pins(ctx: ep.Ctx, mech, raw):
    """Chốt trên trống: chốt của búa nào nằm đúng phương vị búa đó vào đúng nhịp gõ (tính từ góc trống tại nhịp đó)."""
    drum_spec = raw["cam_drums"][0]
    drum = bpy.data.objects[f"CW_{drum_spec['gear']}"]
    s = next(x for x in raw["shafts"] if x["id"] == mech.gears[drum_spec["gear"]].shaft)
    c = _mm(s["origin"])
    th = mech.gears[drum_spec["gear"]].thickness * MM
    for cd in raw["cam_drums"]:
        mo = next(m for m in raw["motions"] if m["by"] == f"{cd['id']}.lift")
        piv = _mm(mo["pivot_mm"])
        alpha = math.atan2(piv.y - c.y, piv.x - c.x)
        r = (piv - c).xy.length - TAIL           # chốt đi qua ngay dưới đầu đuôi búa
        for i, beat in enumerate(cd["pins_beats"]):
            phi = alpha - math.radians(solve_kinematics(mech, beat)[cd["gear"]])
            pin = ep.lathe(ctx, f"CW_{cd['id']}_pin{i}", [(0, 0), (0.035, 0), (0.035, 0.1), (0.02, 0.12), (0, 0.12)],
                           "brass", None, segments=10, location=(r * math.cos(phi), r * math.sin(phi), th / 2))
            pin.parent = drum


def build_gear_dais(ctx: ep.Ctx, parent):
    """Bệ tròn 2 bậc dưới chồng tầng bánh răng (concept: các bậc tròn lấp sàn thân dưới tới chân trụ ốp)."""
    ep.lathe(ctx, "CW_gear_dais", [(0, ep.Z_PLINTH), (4.65, ep.Z_PLINTH), (4.65, 1.28), (4.55, 1.32), (3.95, 1.32),
                                   (3.95, 1.56), (3.85, 1.6), (0, 1.6)], "basalt", parent, segments=96, smooth=False)
    rivets(ctx, "CW_dais_rivets", [(r * math.cos(2 * math.pi * k / 48), r * math.sin(2 * math.pi * k / 48), z)
                                    for k in range(48) for r, z in ((4.5, 1.32), (3.8, 1.6))], parent)


def build_buttress_tubes(ctx: ep.Ctx, parent):
    """Ống đồng có nắp trên mặt mỗi trụ ốp (concept: 8 ống dọc ở tầng giữa trụ)."""
    for k in range(8):
        th = math.radians(22.5) + k * math.pi / 4
        d = ep.OCT_R + 0.85 + 0.05
        ep.lathe(ctx, f"CW_buttress_tube_{k}",
                 [(0, 0), (0.11, 0), (0.11, 0.05), (0.08, 0.08), (0.08, 0.95), (0.12, 1.0), (0.12, 1.08), (0.05, 1.16),
                  (0.06, 1.22), (0, 1.25)], "basalt_trim", parent, segments=16,
                 location=(d * math.cos(th), d * math.sin(th), 4.05))


def build(scene, root, mech, raw) -> dict:
    ctx = ep.Ctx(scene, materials())
    tower = ep.group(ctx, "CW_tower", root)
    ep.build_base_octagon(ctx, tower)
    ep.build_buttresses(ctx, tower)
    ep.build_entrance(ctx, tower)
    ep.build_lancet_windows(ctx, tower)
    ep.build_parapet(ctx, tower)
    ep.build_upper_body(ctx, tower)
    ep.build_clock_face(ctx, tower)
    ep.build_belfry(ctx, tower)
    ep.build_pinnacles(ctx, tower)
    ep.build_spire(ctx, tower)
    ep.build_armillary(ctx, tower)
    for name in DROP:
        _drop(name)
    finish_dial(ctx)

    build_upper_frame(ctx, tower)
    build_upper_rivets(ctx, tower)
    build_buttress_panels(ctx, tower)
    build_pinnacles(ctx, tower)
    build_clock_hood(ctx, tower)
    build_base_details(ctx, tower)
    build_gear_dais(ctx, tower)
    build_buttress_tubes(ctx, tower)
    build_movement_frame(ctx, tower, raw)
    motion = {m["part"]: m for m in raw["motions"]}

    parts = {"pendulum": build_pendulum(ctx, root, _mm(motion["pendulum"]["pivot_mm"]))}
    piv = _mm(motion["hammer"]["pivot_mm"])
    drum_c = _mm(next(x for x in raw["shafts"] if x["id"] == "s_drum")["origin"])
    toward = Vector((-piv.x, -piv.y, 0)).normalized()                       # từ trục búa về tâm chuông
    tail_dir = Vector((drum_c.x - piv.x, drum_c.y - piv.y, 0)).normalized()  # đuôi chĩa về tâm trống
    build_hammer_post(ctx, tower, "CW_hammer_post", piv + Vector((0, 0, 0.07)))
    parts["hammer"] = build_hammer(ctx, root, "CW_hammer", piv, toward, tail_dir)
    build_drum_pins(ctx, mech, raw)

    parts["zodiac_ring"] = _regroup(scene, "CW_zodiac_ring", ["ER_clock_face_zodiac_ring", "ER_clock_face_moon_hand"]
                                    + [f"ER_zodiac_{k}" for k in range(12)], root)
    parts["dial_hands"] = _regroup(scene, "CW_dial_hands", ["ER_clock_face_hand_sun", "ER_clock_face_sun"], root)
    parts["armillary"] = bpy.data.objects["ER_armillary"]
    return parts
