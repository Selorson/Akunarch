"""
Akunarch v2.1 — Clockwork Stage PBR Assembler (Blender 5.2 + Cycles OptiX + Poly Haven 2K + Draco GLB).

Law #7 Compliance:
  1. Dispatches ONLY approved canonical monuments (`temple-of-zyberon` + clean v2.1 scripts in `E:\\Akunarch\\bin\\scripts\\monuments\\`)
     via `bake_canonical_monument.py` — ZERO fallback to deprecated archived scripts.
  2. For custom World-First / Bring-Your-Own-Assets (`--hero-glb`), bakes Cycles OptiX AO + Pointiness,
     projects 2D Concept Albedo + Poly Haven 2K scanned rock/stone/bronze PBR maps onto a geological cutaway dais,
     exports Draco `.glb`, and writes `<out>.parts.json` metadata.

Usage:
  blender.exe --background --python E:\\Akunarch\\bin\\scripts\\assemble_clockwork_glb.py -- \\
      --slug <slug> --out <out_glb> [--hero-glb <sculpt_glb>] [--concept <concept_img>]
"""

import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
KIT_DIR = Path(r"E:\Tools-3D\scripts\archived_selorson_monuments")
BAKE_CANONICAL_SCRIPT = SCRIPT_DIR / "bake_canonical_monument.py"


def parse_args() -> dict[str, str]:
    argv = sys.argv
    tail = argv[argv.index("--") + 1 :] if "--" in argv else []
    parsed: dict[str, str] = {}
    i = 0
    while i < len(tail):
        key = tail[i]
        if key.startswith("--") and i + 1 < len(tail):
            parsed[key[2:]] = tail[i + 1]
            i += 2
        else:
            i += 1
    return parsed


def main() -> None:
    opts = parse_args()
    slug = opts.get("slug", "custom-monument").strip()
    out_raw = opts.get("out", "").strip()
    if not out_raw:
        raise SystemExit("Missing --out <out_glb>")
    out_glb = Path(out_raw).resolve()
    hero_glb_str = opts.get("hero-glb", "").strip()
    concept_str = opts.get("concept", "").strip()

    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))

    # Dispatch to clean v2.1 canonical recipe when no custom hero sculpt override is forced
    if not hero_glb_str:
        from bake_canonical_monument import SLUG_TO_SCRIPT

        if slug in SLUG_TO_SCRIPT:
            import bpy

            blender_bin = bpy.app.binary_path
            res = subprocess.run(
                [blender_bin, "--background", "--python-exit-code", "1", "--python", str(BAKE_CANONICAL_SCRIPT), "--", slug, str(out_glb)],
                check=False,
            )
            if res.returncode != 0:
                raise SystemExit(res.returncode)
            return

    if not hero_glb_str:
        raise SystemExit(
            f"No canonical recipe for '{slug}' and no --hero-glb provided. Sculpt or import a .glb first."
        )

    hero_glb = Path(hero_glb_str).resolve()
    if not hero_glb.is_file():
        raise SystemExit(f"Hero GLB not found: {hero_glb}")

    monuments_dir = SCRIPT_DIR / "monuments"
    for extra_p in (str(monuments_dir), str(KIT_DIR)):
        if extra_p not in sys.path:
            sys.path.insert(0, extra_p)

    import bpy
    import numpy as np
    import _aaa_monument_kit as kit
    import _monument_builders as _mb  # noqa: F401 (activates 32-bit F32 world-position bake patch)

    tmp_baked = Path(tempfile.mkdtemp(prefix=f"akunarch_custom_{slug}_"))
    kit.BAKED_DIR = tmp_baked
    kit.MODELS_OUT_DIR = out_glb.parent
    out_glb.parent.mkdir(parents=True, exist_ok=True)

    try:
        scene, t_start = kit.init_blender_optix_scene(f"AKUNARCH CUSTOM CLOCKWORK STAGE: {slug}")

        mat_basalt = kit.build_polyhaven_gltf_material(
            f"{slug}_basalt",
            "rock_face_03",
            base_override_linear=(0.08, 0.09, 0.11),
            contrast=1.26,
            ao_strength=0.58,
            rough_scale=0.86,
            rough_bias=0.06,
            metallic=0.04,
            normal_strength=1.20,
            res=1024,
        )
        mat_stone = kit.build_polyhaven_gltf_material(
            f"{slug}_ashlar",
            "old_stone_wall_02",
            base_override_linear=(0.34, 0.32, 0.29),
            contrast=1.20,
            ao_strength=0.54,
            rough_scale=0.80,
            rough_bias=0.06,
            metallic=0.02,
            normal_strength=1.15,
            res=1024,
        )
        mat_bronze = kit.build_polyhaven_gltf_material(
            f"{slug}_bronze",
            "metal_plate_02",
            base_override_linear=(0.56, 0.39, 0.16),
            contrast=1.24,
            ao_strength=0.50,
            rough_scale=0.38,
            rough_bias=0.06,
            metallic=0.90,
            normal_strength=0.85,
            res=1024,
        )

        # Import & Cycles-bake the custom hero GLB
        kit.AI_DIR = hero_glb.parent
        hero_obj, ao_map, _pt, _nz, px, py, pz, cavity_boost, valid_mask = kit.import_hero_sculpt_raw(
            hero_glb.name,
            f"{slug}_hero",
            target_height=2.85,
            target_xy_span=3.20,
            decimate_max_polys=24000,
            bake_res=1024,
        )

        concept_path = Path(concept_str).resolve() if concept_str else None
        if concept_path and concept_path.is_file():
            kit.CONCEPT_DIR = concept_path.parent
            albedo, rough, metal, nor_f, emit_masked = kit.project_concept_albedo_onto_hero_mesh(
                concept_path.name,
                px,
                py,
                pz,
                ao_map,
                cavity_boost,
                valid_mask,
                pbr_tex_folder="old_stone_wall_02",
                pbr_detail_strength=0.22,
                ao_weight=0.38,
                rough_base=0.62,
                metal_base=0.06,
            )
            emit_max = float(np.max(emit_masked)) if emit_masked is not None else 0.0
            hero_src = kit.finalize_hero_pbr(
                hero_obj,
                f"{slug}_hero",
                albedo,
                ao_map,
                rough,
                metal,
                nor_f,
                emit_masked if emit_max > 0.02 else None,
                emit_strength=1.85 if emit_max > 0.02 else 0.0,
            )
        else:
            kit.apply_box_uv_and_mat(hero_obj, mat_stone, uv_scale=0.45)
            hero_src = hero_obj

        # High-resolution geological cutaway base (Zero Toy Primitives!)
        p1 = kit.create_part_empty(scene, "clockwork_geological_plinth")
        z_bot = -1.65
        geo_obj, g_ao, g_pt, g_nz, g_wx, g_wy, g_wz, _g_vm = kit.build_cutaway_geological_mesh(
            scene,
            f"{slug}_cutaway_bedrock",
            radii_top=[0.28, 0.56, 0.82, 1.0],
            z_cliff_bot=z_bot,
            outer_rim_r_fn=lambda th: 3.72 + 0.14 * np.cos(8.0 * th),
            top_surface_z_fn=lambda x, y, r, th: 0.0,
            cliff_r_fn=lambda th, zz, sf, r_top: r_top * (1.0 - 0.14 * (sf ** 1.2))
            + 0.08 * np.sin(zz * 9.0 + np.cos(th * 5.0)) * np.sin(sf * math.pi),
            n_ang=180,
            n_z=36,
        )
        col_s, rgh_s, nor_s = kit.sample_triplanar_or_cyl_pbr("rock_face_03", g_wx, g_wy, g_wz, g_nz, bake_res=2048)
        g_albedo = np.clip(col_s * np.array([0.38, 0.35, 0.33], dtype=np.float32) * (0.38 + 0.62 * g_ao), 0.01, 0.95)
        g_orm = np.concatenate([g_ao, np.clip(rgh_s * 0.92 + 0.05, 0.12, 0.98), np.full_like(g_ao, 0.03)], axis=2)
        g_col_img = kit.save_np_img(g_albedo, tmp_baked / f"{slug}_geo_col.jpg", is_data=False)
        g_orm_img = kit.save_np_img(g_orm, tmp_baked / f"{slug}_geo_orm.jpg", is_data=True)
        g_nor_img = kit.save_np_img(nor_s, tmp_baked / f"{slug}_geo_nor.jpg", is_data=True)
        geo_mat = kit.make_principled_gltf_material(f"{slug}_geo_mat", g_col_img, g_orm_img, g_nor_img, normal_strength=1.25)
        geo_obj.data.materials.clear()
        geo_obj.data.materials.append(geo_mat)
        kit.parent_keep_local(geo_obj, p1)
        kit.build_museum_plinth(scene, p1, r_outer=3.55, z_cliff_bot=z_bot, sides=24, mat_dark=mat_basalt, mat_trim=mat_bronze)

        # Part 2: Stepped Ashlar Sanctum Dais
        p2 = kit.create_part_empty(scene, "sanctum_octagonal_terrace")
        for idx, (r_o, z0, z1, m_use) in enumerate([
            (3.15, 0.00, 0.22, mat_stone),
            (2.72, 0.22, 0.44, mat_stone),
            (2.38, 0.44, 0.56, mat_bronze),
        ]):
            t_ring = kit.add_prism_ring(scene, f"sanctum_step_{idx}", r_o, 0.0, z0, z1, sides=8, bevel=0.014, rot_offset=math.pi / 8.0)
            kit.apply_box_uv_and_mat(t_ring, m_use, uv_scale=0.42)
            kit.parent_keep_local(t_ring, p2)

        # Part 3: Sculpted Hero Monument
        p3 = kit.create_part_empty(scene, "sculpted_hero_monument")
        hero_inst = bpy.data.objects.new(f"{slug}_hero_inst", hero_src.data)
        hero_inst.location = (0.0, 0.0, 0.56)
        scene.collection.objects.link(hero_inst)
        kit.parent_keep_local(hero_inst, p3)

        parts_spec = [
            (p1, 0.00),
            (p2, 2.40),
            (p3, 5.40),
        ]
        kit.verify_and_export_monument(
            scene=scene,
            out_glb=out_glb,
            parts_spec=parts_spec,
            master_sources=[hero_src],
            prop_support_checks=[],
            t_start=t_start,
        )

        parts_meta = [
            {
                "id": "clockwork_geological_plinth",
                "name_vi": "Đế Địa Tầng Đá Bazan Cắt Lớp",
                "name_en": "Fractured Basalt Cutaway Plinth",
                "summary_vi": "Khối đá nền cắt lớp địa chất kèm vành đồng cổ đỡ công trình.",
                "summary_en": "Cycles-baked fractured basalt foundation and brushed-bronze museum plinth.",
                "dir": [0.0, 0.0, 0.0],
            },
            {
                "id": "sanctum_octagonal_terrace",
                "name_vi": "Thềm Đá Bát Giác Trung Tâm",
                "name_en": "Octagonal Sanctum Terrace",
                "summary_vi": "Bậc thềm đá cổ vát cạnh và vành đồng niêm phong.",
                "summary_en": "Stepped ashlar octagonal terrace with bronze trim ring.",
                "dir": [0.0, 2.4, 0.0],
            },
            {
                "id": "sculpted_hero_monument",
                "name_vi": "Khối Kiến Trúc Điêu Khắc Chính",
                "name_en": "Primary Sculpted Monument",
                "summary_vi": "Khối điêu khắc 3D chủ đạo đã nướng AO & chất liệu PBR 2K.",
                "summary_en": "Primary 3D sculpted monument baked with Cycles AO and 2K PBR textures.",
                "dir": [0.0, 5.4, 0.0],
            },
        ]
        meta_path = out_glb.with_suffix(".parts.json")
        meta_path.write_text(json.dumps(parts_meta, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[AKUNARCH_OK] Custom Clockwork Stage '{slug}' exported -> {out_glb}")
    finally:
        shutil.rmtree(tmp_baked, ignore_errors=True)


if __name__ == "__main__":
    main()
