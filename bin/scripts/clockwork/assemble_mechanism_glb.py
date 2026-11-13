"""
Akunarch P0 — Dựng BẢN CƠ KHÍ từ đặc tả `<slug>.mechanism.json` và xuất .glb có 2 clip `assemble` + `idle`.

  blender --background --python assemble_mechanism_glb.py -- --slug <slug> --mech <file.mechanism.json> --out <out.glb>

Luồng: kiểm luật (mechanism.validate — không bánh răng trang trí) → dựng bánh răng thân khai / trục / vít me
→ (tuỳ chọn) bộ phận công trình riêng của dự án: module `<slug_gạch_dưới>_mechanism_parts.py` có
`build(ctx, root, mech, raw) -> dict[part_id, Object]` → keyframe từng khung theo solve_kinematics
→ mỗi object 1 action / clip, đẩy vào NLA track tên clip → exporter gộp theo tên track thành 2 animation glTF.
Nhịp: 1 nhịp = 0,5 s, 24 fps (12 khung / nhịp). Đặc tả dùng mm; Blender dùng m.
"""

from __future__ import annotations

import importlib
import json
import math
import sys
import time
from pathlib import Path

import bpy
from mathutils import Matrix, Quaternion, Vector

HERE = Path(r"E:\Akunarch\bin\scripts\clockwork")
for p in (str(HERE), r"E:\Akunarch\bin\scripts\monuments", r"E:\Tools-3D\scripts\archived_selorson_monuments"):
    if p not in sys.path:
        sys.path.insert(0, p)

import _aaa_monument_kit as kit  # noqa: E402
import gear_kit_blender as gk  # noqa: E402
from mechanism import mechanism_from_dict, solve_kinematics, validate  # noqa: E402

FPS = 24
FRAMES_PER_BEAT = 12
IDLE_BEATS = 8


def parse_args() -> dict[str, str]:
    tail = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    return {tail[i][2:]: tail[i + 1] for i in range(0, len(tail) - 1, 2) if tail[i].startswith("--")}


def mechanism_materials() -> dict:
    ph = kit.build_polyhaven_gltf_material
    return {
        "brass": ph("CW_brass", "metal_plate_02", base_override_linear=(0.62, 0.42, 0.16), metallic=1.0,
                    rough_scale=0.5, rough_bias=0.04, contrast=1.2),
        "steel": ph("CW_blued_steel", "metal_plate_02", base_override_linear=(0.05, 0.08, 0.16), metallic=1.0,
                    rough_scale=0.45),
        "iron": ph("CW_iron", "metal_plate_02", base_override_linear=(0.07, 0.07, 0.075), metallic=0.85),
        "ruby": ph("CW_ruby", "metal_plate_02", base_override_linear=(0.45, 0.02, 0.05), metallic=0.2, rough_scale=0.25),
    }


def place(obj, origin_mm, axis, angle_deg=0.0, extra=Vector((0, 0, 0))):
    """Đặt object có trục cục bộ Z trùng trục `axis`, tại gốc trục (mm), xoay `angle_deg` quanh trục."""
    rot = gk.axis_matrix(axis) @ Matrix.Rotation(math.radians(angle_deg), 4, "Z")
    obj.rotation_mode = "QUATERNION"
    obj.rotation_quaternion = rot.to_quaternion()
    obj.location = Vector(origin_mm) * gk.MM + extra


def build_scene(slug: str, mech_path: Path):
    """Dựng toàn bộ cảnh cơ khí + NLA track `assemble`/`idle`. Trả (scene, t0, mech, số object chuyển động, số bộ phận)."""
    raw = json.loads(mech_path.read_text(encoding="utf-8"))
    mech = mechanism_from_dict(raw)
    errs = validate(mech)
    if errs:
        raise SystemExit("Đặc tả cơ cấu không hợp lệ:\n  - " + "\n  - ".join(errs))

    # kit.init_blender_optix_scene tự mkdir MODELS_OUT_DIR (mặc định trỏ vào Selorson static/world/models — đã gỡ bỏ)
    kit.MODELS_OUT_DIR = mech_path.parent
    kit.BAKED_DIR = Path(__import__("tempfile").mkdtemp(prefix="akun_cw_baked_"))
    scene, t0 = kit.init_blender_optix_scene(f"CLOCKWORK MECHANISM — {slug}")
    mats = mechanism_materials()
    root = kit.create_part_empty(scene, "CW_root")
    animated: list[tuple[bpy.types.Object, callable]] = []   # (object, hàm(k) → đặt transform)

    # trục
    for sh in mech.shafts.values():
        raw_sh = next(s for s in raw["shafts"] if s["id"] == sh.id)
        shaft = gk.build_shaft(scene, f"CW_{sh.id}", raw_sh.get("length_mm", 30.0), raw_sh.get("radius_mm", 1.5),
                               mats["steel"], root)
        place(shaft, sh.origin, sh.axis)
    # bánh răng (+ chân kính hồng ngọc ở đầu trục)
    for g in mech.gears.values():
        sh = mech.shafts[g.shaft]
        z_off_mm = next(x for x in raw["gears"] if x["id"] == g.id).get("z_mm", 0.0)
        obj = gk.build_spur_gear(scene, g, mats.get(g.material, mats["brass"]), root)
        off = Vector(sh.axis).normalized() * z_off_mm * gk.MM
        place(obj, sh.origin, sh.axis, 0.0, off)
        animated.append((obj, lambda k, o=obj, s=sh, gid=g.id, off=off: place(o, s.origin, s.axis, k.get(gid, 0.0), off)))
    # vít me
    for e in mech.elements.values():
        if e.kind == "lead_screw":
            sh = mech.shafts[mech.gears[e.gear].shaft]
            raw_e = next(x for x in raw.get("lead_screws", []) if x["id"] == e.id)
            ls = gk.build_lead_screw(scene, f"CW_{e.id}", raw_e.get("length_mm", 60.0), raw_e.get("radius_mm", 3.0),
                                     e.pitch_mm, mats["steel"], root)
            place(ls, sh.origin, sh.axis)
            animated.append((ls, lambda k, o=ls, s=sh, gid=e.gear: place(o, s.origin, s.axis, k.get(gid, 0.0))))

    # bộ phận công trình riêng của dự án (nếu có module)
    parts: dict[str, bpy.types.Object] = {}
    mod_name = slug.replace("-", "_") + "_mechanism_parts"
    if (HERE / f"{mod_name}.py").is_file():
        parts = importlib.import_module(mod_name).build(scene, root, mech, raw)
        for pid, obj in parts.items():
            base = obj.matrix_basis.copy()
            motion = next((m for m in raw.get("motions", []) if m["part"] == pid), None)
            if not motion:
                continue

            def apply(k, o=obj, base=base, mo=motion):
                v = k.get(mo["by"], 0.0)
                if mo["type"] == "translate":
                    o.matrix_basis = Matrix.Translation(Vector(mo["axis"]).normalized() * v * mo.get("scale", 1.0) * gk.MM) @ base
                else:   # rotate quanh trục đi qua `pivot_mm`
                    piv = Vector(mo["pivot_mm"]) * gk.MM
                    r = Matrix.Translation(piv) @ Matrix.Rotation(math.radians(v * mo.get("scale", 1.0)), 4, Vector(mo["axis"])) @ Matrix.Translation(-piv)
                    o.matrix_basis = r @ base
            animated.append((obj, apply))

    # keyframe → NLA track theo tên clip
    clips = {"assemble": (0.0, float(mech.beats_total)), "idle": (float(mech.beats_total), float(mech.beats_total + IDLE_BEATS))}
    for clip, (b0, b1) in clips.items():
        n_frames = int(round((b1 - b0) * FRAMES_PER_BEAT))
        actions = {}
        for obj, _ in animated:
            obj.animation_data_create()
            act = bpy.data.actions.new(f"{obj.name}|{clip}")
            obj.animation_data.action = act
            actions[obj.name] = act
        for f in range(n_frames + 1):
            k = solve_kinematics(mech, b0 + f / FRAMES_PER_BEAT)
            for obj, setter in animated:
                setter(k)
                obj.keyframe_insert("location", frame=f)
                obj.keyframe_insert("rotation_quaternion" if obj.rotation_mode == "QUATERNION" else "rotation_euler", frame=f)
                obj.keyframe_insert("scale", frame=f)
        for obj, _ in animated:
            track = obj.animation_data.nla_tracks.new()
            track.name = clip
            track.strips.new(clip, 0, actions[obj.name])
            obj.animation_data.action = None
    k0 = solve_kinematics(mech, 0.0)
    for obj, setter in animated:
        setter(k0)
    return scene, t0, mech, len(animated), len(parts)


def main():
    a = parse_args()
    slug, mech_path, out = a["slug"], Path(a["mech"]), Path(a["out"])
    scene, t0, mech, n_anim, n_parts = build_scene(slug, mech_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=str(out), export_format="GLB", use_visible=True, export_yup=True, export_apply=False,
        export_texcoords=True, export_normals=True, export_materials="EXPORT", export_image_format="JPEG",
        export_jpeg_quality=92, export_animations=True, export_animation_mode="NLA_TRACKS",
        export_force_sampling=True, export_frame_step=1, export_optimize_animation_size=False,
        export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6,
    )
    print(f"=== [MECHANISM] {slug}: {len(mech.gears)} bánh răng, {n_anim} object chuyển động, "
          f"{n_parts} bộ phận → {out} ({out.stat().st_size / 1048576:.2f} MB) trong {time.time() - t0:.1f}s ===")
    __import__("shutil").rmtree(kit.BAKED_DIR, ignore_errors=True)   # texture nướng tạm đã nhúng vào .glb


if __name__ == "__main__":
    main()
