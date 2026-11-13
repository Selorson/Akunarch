"""
Akunarch — Ảnh xem trước 1920×1080 cho thẻ Chờ 2D (Kế hoạch VRAM v2 · C2), Blender 5.2 --background.

Nạp .glb (bản gốc clockwork/_master/<slug>.glb — Blender không đọc được texture KTX2 của bản runtime),
khung 3/4 theo hộp bao (cùng hướng nhìn mặc định của sân khấu PBR tab 01), ống kính 40 mm,
studio 3 điểm, Cycles OptiX trên RTX 4080, nền phẳng #090d16 (ghép alpha, không phụ thuộc view transform).

Usage:
  blender.exe --background --python-exit-code 1 --python render_glb_preview_card.py -- \
      --glb <model.glb> --out <slug>_preview_1080p.png [--width 1920] [--height 1080] [--samples 48]
"""

import math
import sys
import tempfile
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

BG_SRGB = (9 / 255.0, 13 / 255.0, 22 / 255.0)  # #090d16


def parse_args() -> dict[str, str]:
    argv = sys.argv
    tail = argv[argv.index("--") + 1 :] if "--" in argv else []
    parsed: dict[str, str] = {}
    i = 0
    while i < len(tail):
        if tail[i].startswith("--") and i + 1 < len(tail):
            parsed[tail[i][2:]] = tail[i + 1]
            i += 2
        else:
            i += 1
    return parsed


def main() -> None:
    opts = parse_args()
    glb_path = Path(opts.get("glb", "")).resolve()
    out_png = Path(opts.get("out", "")).resolve()
    width = max(320, int(opts.get("width", "1920")))
    height = max(180, int(opts.get("height", "1080")))
    samples = max(8, int(opts.get("samples", "48")))
    if not glb_path.is_file():
        raise SystemExit(f"Input GLB not found: {glb_path}")
    out_png.parent.mkdir(parents=True, exist_ok=True)

    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    bpy.context.view_layer.update()

    meshes = [o for o in scene.objects if o.type == "MESH"]
    if not meshes:
        raise RuntimeError(f"No mesh geometry found in {glb_path}")
    b_min = Vector((1e9, 1e9, 1e9))
    b_max = Vector((-1e9, -1e9, -1e9))
    for m in meshes:
        for corner in m.bound_box:
            wc = m.matrix_world @ Vector(corner)
            b_min = Vector((min(b_min.x, wc.x), min(b_min.y, wc.y), min(b_min.z, wc.z)))
            b_max = Vector((max(b_max.x, wc.x), max(b_max.y, wc.y), max(b_max.z, wc.z)))
    center = 0.5 * (b_min + b_max)
    span = b_max - b_min
    sphere_r = max(0.5, 0.5 * span.length)

    # Studio: world tối + 3 đèn sun (Key ấm / Rim lạnh / Fill)
    world = bpy.data.worlds.new("AkunarchPreviewWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.018, 0.024, 0.036, 1.0)
        bg.inputs[1].default_value = 1.0
    scene.world = world

    def add_sun(name, rot_deg, energy, rgb):
        ldata = bpy.data.lights.new(name, type="SUN")
        ldata.energy = energy
        ldata.color = rgb
        ldata.angle = math.radians(8.0)
        lobj = bpy.data.objects.new(name, ldata)
        lobj.rotation_euler = tuple(math.radians(d) for d in rot_deg)
        scene.collection.objects.link(lobj)

    add_sun("KeySun", (48.0, 12.0, 36.0), 3.4, (1.0, 0.94, 0.84))
    add_sun("RimSun", (62.0, -18.0, -142.0), 1.8, (0.62, 0.80, 1.0))
    add_sun("FillSun", (74.0, 0.0, 138.0), 0.9, (0.85, 0.90, 1.0))

    # Camera 3/4: cùng hướng (6.8, 4.4, 7.6) của sân khấu three.js (Y-up) → Blender Z-up (x, -z, y)
    cam_data = bpy.data.cameras.new("PreviewCam")
    cam_data.lens = 40.0
    cam_data.sensor_fit = "HORIZONTAL"
    cam_data.sensor_width = 36.0
    v_fov = 2.0 * math.atan((36.0 * height / width) / (2.0 * cam_data.lens))
    dist = sphere_r / math.sin(v_fov / 2.0) * 0.66  # hộp bao chéo rộng hơn hình chiếu thật → siết khung
    cam_data.clip_start = max(0.01, dist * 0.005)
    cam_data.clip_end = dist * 20.0
    cam_obj = bpy.data.objects.new("PreviewCam", cam_data)
    scene.collection.objects.link(cam_obj)
    direction = Vector((6.8, -7.6, 4.4)).normalized()
    cam_obj.location = center + direction * dist
    cam_obj.rotation_euler = (center - cam_obj.location).to_track_quat("-Z", "Y").to_euler()
    scene.camera = cam_obj
    scene.render.resolution_x, scene.render.resolution_y = width, height

    # P0: hệ số 0.66 cố định cắt mất đỉnh công trình mảnh-cao (tháp Eryndor mất quả cầu thiên văn) → tìm khoảng
    # cách nhỏ nhất mà cả 8 góc hộp bao nằm trong khung (lề 4%), vẫn siết sát như cũ với công trình bè ngang.
    from bpy_extras.object_utils import world_to_camera_view
    # canh theo đỉnh lưới thật (hộp bao chéo rộng hơn hình chiếu thật → khung lỏng); lấy mẫu ≤ 20.000 đỉnh
    all_pts = [m.matrix_world @ v.co for m in meshes for v in m.data.vertices]
    step = max(1, len(all_pts) // 20000)
    corners = all_pts[::step]

    def fits(d):
        cam_obj.location = center + direction * d
        bpy.context.view_layer.update()
        for c in corners:
            p = world_to_camera_view(scene, cam_obj, c)
            if p.z <= 0 or not (0.03 <= p.x <= 0.97 and 0.03 <= p.y <= 0.97):
                return False
        return True

    lo_d, hi_d = dist * 0.4, dist * 3.0
    for _ in range(28):
        mid = 0.5 * (lo_d + hi_d)
        lo_d, hi_d = (lo_d, mid) if fits(mid) else (mid, hi_d)
    dist = hi_d
    cam_obj.location = center + direction * dist
    cam_data.clip_start = max(0.01, dist * 0.005)
    cam_data.clip_end = dist * 20.0

    scene.render.engine = "CYCLES"
    cprefs = bpy.context.preferences.addons["cycles"].preferences
    cprefs.compute_device_type = "OPTIX"
    cprefs.get_devices()
    for dev in cprefs.devices:
        dev.use = dev.type == "OPTIX" and "RTX" in dev.name
    scene.cycles.device = "GPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = "AgX"
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    tmp_png = Path(tempfile.mkdtemp(prefix="akun_preview_")) / "rgba.png"
    scene.render.filepath = str(tmp_png)
    bpy.ops.render.render(write_still=True)

    # Ghép lên nền phẳng #090d16 trong không gian hiển thị (PNG lưu alpha thẳng)
    src = bpy.data.images.load(str(tmp_png))
    px = np.array(src.pixels[:], dtype=np.float32).reshape(-1, 4)
    a = px[:, 3:4]
    rgb = px[:, :3] * a + np.array(BG_SRGB, dtype=np.float32) * (1.0 - a)
    out = np.concatenate([rgb, np.ones_like(a)], axis=1)
    dst = bpy.data.images.new("preview_card", width=src.size[0], height=src.size[1], alpha=False)
    dst.colorspace_settings.name = "Non-Color"  # giá trị đã ở không gian hiển thị → ghi nguyên
    dst.pixels[:] = out.ravel().tolist()
    dst.filepath_raw = str(out_png)
    dst.file_format = "PNG"
    dst.save()
    print(f"PREVIEW_CARD_OK {out_png} {src.size[0]}x{src.size[1]}")
    # dọn thư mục tạm (trước đây mỗi lần render để lại 1–1,6 MB trong %TEMP%)
    bpy.data.images.remove(src)
    import shutil
    shutil.rmtree(tmp_png.parent, ignore_errors=True)


if __name__ == "__main__":
    main()
