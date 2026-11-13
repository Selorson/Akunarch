"""
Akunarch P0 — Tháp Đồng Hồ Thiên Văn Eryndor: BẢN THẬT (kích thước thật, ~26 m + vách đá 9 m).
1:1 theo `projects/eryndor-clocktower-concept/concepts/concept_eryndor_astronomical_clocktower.jpg` + canon Co-Writer #499.
Thiết kế & số đo: E:\\Akunarch\\docs\\p0\\eryndor_design.md. Bộ phận dùng chung: eryndor_parts.py.

Gọi qua hàng đợi: gpu_enqueue(slug, 'blender', {mode: 'assemble_glb'}) → assemble_clockwork_glb.py → bake_canonical_monument.py.
Chạy tay: blender --background --python assemble_eryndor_clocktower.py -- <out.glb>
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import bpy

MONUMENTS_DIR = Path(r"E:\Akunarch\bin\scripts\monuments")
KIT_DIR = Path(r"E:\Tools-3D\scripts\archived_selorson_monuments")
for p in (str(MONUMENTS_DIR), str(KIT_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import _aaa_monument_kit as kit  # noqa: E402
import _monument_builders as mb  # noqa: E402
import eryndor_parts as ep  # noqa: E402

SLUG = "eryndor-clocktower-concept"
OUT_GLB = mb.resolve_out_glb(SLUG, globals())
if globals().get("AKUNARCH_BAKED_DIR"):
    kit.BAKED_DIR = Path(globals()["AKUNARCH_BAKED_DIR"])
# kit.init_blender_optix_scene tự mkdir MODELS_OUT_DIR (mặc định trỏ vào Selorson static/world/models — thư mục đã gỡ bỏ)
kit.MODELS_OUT_DIR = OUT_GLB.parent

# 6 cụm từ dưới lên; dir = độ tách dọc (đơn vị sân khấu) khi bấm tách tầng 100%.
PARTS = [
    ("cliff", "Vách đá vôi & Tĩnh thất ngầm", "Limestone Cliff & Underground Sanctuary",
     "Vách đá vôi phủ sương muối cao 1.600 m; sâu dưới móng là Tĩnh thất của Thánh Đồng: 12 cung hoàng đạo, 3 lớp thảm đỏ, giường tuyết tùng.",
     "Frost-dusted limestone cliff; beneath the foundation lies the windowless sanctuary with 12 zodiac reliefs and a cedar bed.", 0.0),
    ("base", "Thân dưới bát giác & Cửa chính", "Octagonal Base & Main Door",
     "Đá bazan đen thế kỷ XIV, 8 trụ ốp khắc hoa văn thoi, cửa sổ lancet chấn song sắt, cửa sồi vòm nhọn, cầu thang xoắn ốc đá vôi bên trong.",
     "14th-century black basalt with 8 carved buttresses, lancet windows, arched oak door and the inner limestone spiral stair.", 1.9),
    ("parapet", "Tường răng cưa & 4 tháp góc", "Crenellated Parapet & Corner Turrets",
     "Vòng tường răng cưa trên hàng đá nhô, 4 tháp góc canh giữ vách núi.",
     "Crenellated ring on corbels with four corner turrets.", 3.2),
    ("upper", "Thân trên & Đồng hồ thiên văn", "Upper Body & Astronomical Clock",
     "Mặt đồng hồ thiên văn bằng đồng thau khắc số La Mã, vòng hoàng đạo lệch tâm, 3 mặt phụ dưới mái vòm; trong lòng là con lắc neo 4 m và tạ đá hoa cương.",
     "Brass astronomical dial with Roman numerals and an eccentric zodiac ring, three sub-dials, and the 4 m anchor pendulum inside.", 4.6),
    ("belfry", "Gác chuông", "Belfry",
     "Hai chuông đồng treo xà gỗ sau 4 ô vòm nhọn, 4 đầu hồi có huy hiệu tròn, 8 tháp nhọn.",
     "Two bronze bells behind four pointed arches under roundel gables and eight pinnacles.", 6.1),
    ("crown", "Mái chóp & Quả cầu thiên văn", "Spire & Armillary Sphere",
     "Mái chóp đá phiến có 4 mái hồi chéo, trụ đồng đỡ quả cầu thiên văn 5 đai.",
     "Cross-gabled slate spire carrying a five-ring brass armillary sphere.", 7.7),
]


def main():
    scene, t0 = kit.init_blender_optix_scene("ERYNDOR ASTRONOMICAL CLOCK TOWER — REAL SCALE (P0)")
    ctx = ep.Ctx(scene, ep.build_materials())
    empties = {pid: kit.create_part_empty(scene, f"part_{pid}") for pid, *_ in PARTS}

    ep.build_cliff(ctx, empties["cliff"])
    ep.build_sanctuary(ctx, empties["cliff"])
    ep.build_base_octagon(ctx, empties["base"])
    ep.build_buttresses(ctx, empties["base"])
    ep.build_entrance(ctx, empties["base"])
    ep.build_spiral_stair(ctx, empties["base"])
    windows = ep.build_lancet_windows(ctx, empties["base"])
    for ch in list(windows.children):   # cửa sổ thân trên đi theo cụm thân trên khi tách tầng
        if ch.name in ("ER_lancet_4", "ER_lancet_5", "ER_lancet_6") or ch.name.startswith("ER_hood_up"):
            ch.parent = empties["upper"]
    ep.build_parapet(ctx, empties["parapet"])
    ep.build_upper_body(ctx, empties["upper"])
    ep.build_clock_face(ctx, empties["upper"])
    ep.build_shaft_and_pendulum(ctx, empties["upper"])
    ep.build_belfry(ctx, empties["belfry"])
    ep.build_pinnacles(ctx, empties["belfry"])
    ep.build_spire(ctx, empties["crown"])
    ep.build_armillary(ctx, empties["crown"])

    # kiểm: mọi mesh có vật liệu, không slot rỗng; không vật liệu phát sáng (Luật #6 kit)
    bpy.context.view_layer.update()
    tris = 0
    for ob in scene.objects:
        if ob.type != "MESH":
            continue
        slots = list(ob.data.materials)
        if not slots or any(s is None for s in slots):
            raise RuntimeError(f"Mesh '{ob.name}' thiếu vật liệu PBR")
        ob.data.calc_loop_triangles()
        tris += len(ob.data.loop_triangles)
    print(f"[ERYNDOR] objects={len(scene.objects)} triangles={tris}")
    if tris > 600_000:
        raise RuntimeError(f"Vượt ngân sách tam giác: {tris} > 600000")

    OUT_GLB.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(OUT_GLB), export_format="GLB", use_visible=True, export_yup=True, export_apply=True,
        export_texcoords=True, export_normals=True, export_tangents=False, export_materials="EXPORT",
        export_image_format="JPEG", export_jpeg_quality=92,
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14, export_draco_normal_quantization=10, export_draco_texcoord_quantization=12,
    )
    parts_json = [{"id": f"part_{pid}", "name_vi": vi, "name_en": en, "summary_vi": svi, "summary_en": sen, "dir": [0, d, 0]}
                  for pid, vi, en, svi, sen, d in PARTS]
    OUT_GLB.with_suffix(".parts.json").write_text(json.dumps(parts_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"=== [ERYNDOR] EXPORT {OUT_GLB} ({OUT_GLB.stat().st_size / 1048576:.2f} MB) in {time.time() - t0:.1f}s ===")


main()
