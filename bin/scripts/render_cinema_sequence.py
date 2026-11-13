#!/usr/bin/env python3
"""
Akunarch Phase 4 — Sequential 3D Cinema Beauty + Depth Sequence Renderer (Blender 5.2 Cycles OptiX).

Loads a real PBR `.glb` monument (or a 2K landscape/concept plate when no `.glb` is bound),
animates multi-keyframe cinematic camera motion (`keyframes.json`: `time_sec`, `pos`, `target`, `fov_deg`),
renders crisp `Beauty` frames on RTX 4080 Cycles OptiX GPU plus a real metric `Depth` pass preview PNG,
encodes the raw video stream via FFmpeg (`libx264 yuv420p`), writes `thumbnail.jpg`, and exits cleanly
so 100% of Blender's VRAM is freed before downstream `ComfyUI` / `effectcraft-cli` / `ToneForge` steps.

Usage:
  blender.exe --background --python-exit-code 1 --python E:\\Akunarch\\bin\\scripts\\render_cinema_sequence.py -- \
      --out-raw-mp4 <raw.mp4> --out-thumb <thumb.jpg> --out-depth <depth.png> \
      [--glb <model.glb>] [--plate <image.png>] [--keyframes-json <kf.json>] \
      [--duration 6.0] [--fps 24] [--width 1280] [--height 720] [--mood golden_hour]
"""

from __future__ import annotations

import json
import math
import shutil
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

import bpy
from mathutils import Vector

FFMPEG_DEFAULT = Path(r"C:\Users\Admin\.local\bin\ffmpeg.exe")


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


def write_gray16_png(out_path: Path, width: int, height: int, values_01: list[float]) -> None:
    """Writes a 16-bit grayscale PNG depth map without external dependencies."""
    raw_rows = bytearray()
    idx = 0
    for _y in range(height):
        raw_rows.append(0)  # filter type 0
        for _x in range(width):
            v = max(0.0, min(1.0, values_01[idx]))
            u16 = int(round(v * 65535.0))
            raw_rows.append((u16 >> 8) & 0xFF)
            raw_rows.append(u16 & 0xFF)
            idx += 1

    def png_chunk(chunk_type: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(chunk_type)
        crc = zlib.crc32(data, crc) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + chunk_type + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 16, 0, 0, 0, 0)
    compressed = zlib.compress(bytes(raw_rows), level=6)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "wb") as fp:
        fp.write(b"\x89PNG\r\n\x1a\n")
        fp.write(png_chunk(b"IHDR", ihdr))
        fp.write(png_chunk(b"IDAT", compressed))
        fp.write(png_chunk(b"IEND", b""))


def bake_metric_depth_preview(scene: bpy.types.Scene, cam_obj: bpy.types.Object, out_depth: Path) -> None:
    """Ray-casts exact metric camera depth across the 3D scene for the Cinema Depth Pass."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    dw, dh = 480, 270
    cam_mat = cam_obj.matrix_world
    cam_origin = cam_mat.to_translation()
    cam_data = cam_obj.data
    fov_x = cam_data.angle_x
    aspect = float(dw) / float(dh)
    tan_half_x = math.tan(0.5 * fov_x)
    tan_half_y = tan_half_x / aspect

    forward = (cam_mat.to_quaternion() @ Vector((0.0, 0.0, -1.0))).normalized()
    right = (cam_mat.to_quaternion() @ Vector((1.0, 0.0, 0.0))).normalized()
    up = (cam_mat.to_quaternion() @ Vector((0.0, 1.0, 0.0))).normalized()

    raw_dists: list[float] = []
    hit_dists: list[float] = []
    for py in range(dh):
        ndc_y = 1.0 - 2.0 * ((py + 0.5) / float(dh))
        for px in range(dw):
            ndc_x = 2.0 * ((px + 0.5) / float(dw)) - 1.0
            ray_dir = (forward + right * (ndc_x * tan_half_x) + up * (ndc_y * tan_half_y)).normalized()
            hit, loc, _norm, _idx, _obj, _mw = scene.ray_cast(depsgraph, cam_origin, ray_dir)
            if hit:
                d = (loc - cam_origin).length
                raw_dists.append(d)
                hit_dists.append(d)
            else:
                raw_dists.append(-1.0)

    if hit_dists:
        near_d = min(hit_dists)
        far_d = max(hit_dists)
        span = max(0.25, far_d - near_d)
        norm_vals = [
            0.04 if d < 0.0 else max(0.08, min(1.0, 1.0 - ((d - near_d) / span) * 0.90))
            for d in raw_dists
        ]
    else:
        norm_vals = [0.15] * (dw * dh)

    write_gray16_png(out_depth, dw, dh, norm_vals)


def setup_studio_lighting(scene: bpy.types.Scene, mood: str) -> None:
    world = bpy.data.worlds.new("AkunarchCinemaWorld")
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")

    mood_key = mood.strip().lower()
    if mood_key == "golden_hour":
        sky_col = (0.042, 0.030, 0.026, 1.0)
        key_col = (1.0, 0.84, 0.64)
        rim_col = (0.48, 0.76, 1.0)
        key_energy = 4.2
    elif mood_key == "arcane_night":
        sky_col = (0.012, 0.022, 0.042, 1.0)
        key_col = (0.72, 0.88, 1.0)
        rim_col = (0.32, 0.95, 0.82)
        key_energy = 3.2
    else:
        sky_col = (0.018, 0.026, 0.038, 1.0)
        key_col = (1.0, 0.94, 0.85)
        rim_col = (0.58, 0.82, 1.0)
        key_energy = 3.8

    if bg:
        bg.inputs[0].default_value = sky_col
        bg.inputs[1].default_value = 1.22
    scene.world = world

    def add_sun(name: str, rot_deg: tuple[float, float, float], energy: float, rgb: tuple[float, float, float]) -> None:
        ldata = bpy.data.lights.new(name, type="SUN")
        ldata.energy = energy
        ldata.color = rgb
        ldata.angle = math.radians(7.5)
        lobj = bpy.data.objects.new(name, ldata)
        lobj.rotation_euler = tuple(math.radians(d) for d in rot_deg)
        scene.collection.objects.link(lobj)

    add_sun("CinemaKeySun", (52.0, 14.0, 38.0), key_energy, key_col)
    add_sun("CinemaRimSun", (64.0, -18.0, -142.0), 2.1, rim_col)
    add_sun("CinemaFillSun", (76.0, 0.0, 136.0), 1.05, (0.86, 0.91, 1.0))


def build_plate_parallax_stage(scene: bpy.types.Scene, plate_path: Path) -> tuple[Vector, Vector, float]:
    """Builds a curved 2.5D architectural cyclorama stage when rendering from a 2K concept/manga plate."""
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=64, y_subdivisions=36, size=16.0, location=(0.0, 0.0, 4.5))
    plane = bpy.context.active_object
    plane.name = "CinemaPlateStage"
    plane.rotation_euler = (math.radians(90.0), 0.0, 0.0)
    plane.scale = (1.0, 0.5625, 1.0)

    # Subtle concave cyclorama curvature for genuine camera parallax
    mesh = plane.data
    for v in mesh.vertices:
        nx = v.co.x / 8.0
        ny = v.co.y / 8.0
        v.co.z -= 1.35 * (nx * nx + 0.35 * ny * ny)
    mesh.update()

    mat = bpy.data.materials.new("CinemaPlateMat")
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    nodes.clear()

    out_node = nodes.new("ShaderNodeOutputMaterial")
    emis = nodes.new("ShaderNodeEmission")
    emis.inputs["Strength"].default_value = 1.05
    tex = nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(str(plate_path))
    links.new(tex.outputs["Color"], emis.inputs["Color"])
    links.new(emis.outputs["Emission"], out_node.inputs["Surface"])
    plane.data.materials.append(mat)

    return Vector((0.0, 0.0, 4.5)), Vector((16.0, 2.5, 9.0)), 7.5


def main() -> None:
    opts = parse_args()
    glb_raw = opts.get("glb", "").strip()
    plate_raw = opts.get("plate", "").strip()
    kf_json_raw = opts.get("keyframes-json", "").strip()
    out_raw_mp4 = Path(opts.get("out-raw-mp4", "")).resolve()
    out_thumb = Path(opts.get("out-thumb", "")).resolve() if opts.get("out-thumb", "").strip() else None
    out_depth = Path(opts.get("out-depth", "")).resolve() if opts.get("out-depth", "").strip() else None

    duration_sec = max(2.0, min(30.0, float(opts.get("duration", "6.0"))))
    fps = max(12, min(60, int(opts.get("fps", "24"))))
    width = max(480, int(opts.get("width", "1280")))
    height = max(270, int(opts.get("height", "720")))
    samples = max(8, min(256, int(opts.get("samples", "20"))))
    still_only = opts.get("still-only", "0").strip() in ("1", "true", "yes")
    mood = opts.get("mood", "golden_hour")
    ffmpeg_bin = Path(opts.get("ffmpeg", str(FFMPEG_DEFAULT)))

    if not ffmpeg_bin.is_file():
        found = shutil.which("ffmpeg")
        if not found:
            raise SystemExit(f"FFmpeg not found at {ffmpeg_bin}")
        ffmpeg_bin = Path(found)

    total_frames = 1 if still_only else max(24, int(round(duration_sec * fps)))
    out_raw_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix="akunarch_cinema_seq_"))

    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.unit_settings.system = "METRIC"

        has_glb = bool(glb_raw and Path(glb_raw).is_file())
        has_plate = bool(plate_raw and Path(plate_raw).is_file())
        if not has_glb and not has_plate:
            raise SystemExit("Either a valid --glb or --plate file must be provided for Cinema rendering.")

        if has_glb:
            bpy.ops.import_scene.gltf(filepath=str(Path(glb_raw).resolve()))
            bpy.context.view_layer.update()
            meshes = [o for o in scene.objects if o.type == "MESH"]
            if not meshes:
                raise RuntimeError(f"No mesh objects found in {glb_raw}")
            b_min = Vector((1e9, 1e9, 1e9))
            b_max = Vector((-1e9, -1e9, -1e9))
            for m in meshes:
                mw = m.matrix_world
                for corner in m.bound_box:
                    wc = mw @ Vector(corner)
                    b_min.x = min(b_min.x, wc.x)
                    b_min.y = min(b_min.y, wc.y)
                    b_min.z = min(b_min.z, wc.z)
                    b_max.x = max(b_max.x, wc.x)
                    b_max.y = max(b_max.y, wc.y)
                    b_max.z = max(b_max.z, wc.z)
            center = 0.5 * (b_min + b_max)
            span = b_max - b_min
            radius = max(1.2, 0.5 * max(span.x, span.y, span.z))
            base_z = b_min.z
        else:
            center, span, radius = build_plate_parallax_stage(scene, Path(plate_raw).resolve())
            base_z = 0.0

        setup_studio_lighting(scene, mood)

        target_emp = bpy.data.objects.new("CinemaTarget", None)
        scene.collection.objects.link(target_emp)

        cam_data = bpy.data.cameras.new("CinemaCam")
        cam_data.clip_start = 0.05
        cam_data.clip_end = max(800.0, radius * 50.0)
        cam_obj = bpy.data.objects.new("CinemaCam", cam_data)
        scene.collection.objects.link(cam_obj)
        scene.camera = cam_obj

        track = cam_obj.constraints.new(type="TRACK_TO")
        track.target = target_emp
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        keyframes: list[dict] = []
        if kf_json_raw and Path(kf_json_raw).is_file():
            try:
                loaded = json.loads(Path(kf_json_raw).read_text(encoding="utf-8"))
                if isinstance(loaded, list):
                    keyframes = loaded
            except Exception:
                keyframes = []

        scene.frame_start = 1
        scene.frame_end = total_frames

        if has_glb and len(keyframes) >= 1:
            # Convert WebGL Y-up [x, y, z] coordinates (scaled auto-adaptively if normalized vs metric)
            # into Blender Z-up coordinates around monument center: (cx + x, cy - z, base_z + y)
            max_coord = max(
                max(abs(float(c)) for c in kf.get("pos", [0, 5, 16])) for kf in keyframes
            )
            scale_factor = (radius / 7.5) if max_coord <= 30.0 and radius > 9.0 else 1.0

            for kf in keyframes:
                t_sec = max(0.0, min(duration_sec, float(kf.get("time_sec", 0.0))))
                frame_idx = 1 if total_frames <= 1 else max(1, min(total_frames, 1 + int(round((t_sec / duration_sec) * (total_frames - 1)))))
                pos = kf.get("pos", [0.0, 5.5, 16.0])
                tgt = kf.get("target", [0.0, 3.0, 0.0])
                fov_deg = max(18.0, min(85.0, float(kf.get("fov_deg", 38.0))))

                px, py, pz = float(pos[0]) * scale_factor, float(pos[1]) * scale_factor, float(pos[2]) * scale_factor
                tx, ty, tz = float(tgt[0]) * scale_factor, float(tgt[1]) * scale_factor, float(tgt[2]) * scale_factor

                cam_obj.location = (center.x + px, center.y - pz, base_z + py)
                target_emp.location = (center.x + tx, center.y - tz, base_z + ty)
                cam_data.lens = (0.5 * cam_data.sensor_width) / math.tan(0.5 * math.radians(fov_deg))

                cam_obj.keyframe_insert(data_path="location", frame=frame_idx)
                target_emp.keyframe_insert(data_path="location", frame=frame_idx)
                cam_data.keyframe_insert(data_path="lens", frame=frame_idx)
        elif has_glb:
            # Hero architectural sweeping crane + arc shot
            cam_dist_start = radius * 2.45
            cam_dist_end = radius * 1.92
            for f in range(1, total_frames + 1):
                u = (f - 1) / float(max(1, total_frames - 1))
                smooth_u = u * u * (3.0 - 2.0 * u)
                ang = -math.pi * 0.68 + smooth_u * (math.pi * 0.46)
                dist = cam_dist_start + (cam_dist_end - cam_dist_start) * smooth_u
                elev = center.z + radius * (0.42 + 0.34 * smooth_u)
                cam_obj.location = (
                    center.x + dist * math.cos(ang),
                    center.y + dist * math.sin(ang),
                    elev,
                )
                target_emp.location = (center.x, center.y, center.z + span.z * (0.02 + 0.08 * smooth_u))
                fov_f = 39.0 - 4.0 * smooth_u
                cam_data.lens = (0.5 * cam_data.sensor_width) / math.tan(0.5 * math.radians(fov_f))
                cam_obj.keyframe_insert(data_path="location", frame=f)
                target_emp.keyframe_insert(data_path="location", frame=f)
                cam_data.keyframe_insert(data_path="lens", frame=f)
        else:
            # 2.5D Plate parallax push-in
            for f in range(1, total_frames + 1):
                u = (f - 1) / float(max(1, total_frames - 1))
                smooth_u = u * u * (3.0 - 2.0 * u)
                cam_obj.location = (-1.1 + 2.2 * smooth_u, -13.5 + 2.6 * smooth_u, 4.2 + 0.6 * smooth_u)
                target_emp.location = (0.0, 0.0, 4.5 + 0.15 * smooth_u)
                fov_f = 40.0 - 3.5 * smooth_u
                cam_data.lens = (0.5 * cam_data.sensor_width) / math.tan(0.5 * math.radians(fov_f))
                cam_obj.keyframe_insert(data_path="location", frame=f)
                target_emp.keyframe_insert(data_path="location", frame=f)
                cam_data.keyframe_insert(data_path="lens", frame=f)

        # Configure Cycles OptiX GPU
        scene.render.engine = "CYCLES"
        cprefs = bpy.context.preferences.addons["cycles"].preferences
        cprefs.compute_device_type = "OPTIX"
        cprefs.get_devices()
        for dev in cprefs.devices:
            dev.use = dev.type == "OPTIX" and "RTX" in dev.name
        scene.cycles.device = "GPU"
        scene.cycles.samples = samples
        scene.cycles.use_denoising = False

        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = 100
        scene.render.fps = fps
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(tmp_dir / "frame_")
        scene.view_settings.view_transform = "AgX"

        # Jump to midpoint frame first to write metric Depth Pass preview
        mid_frame = max(1, total_frames // 2)
        scene.frame_set(mid_frame)
        bpy.context.view_layer.update()
        if out_depth is not None:
            bake_metric_depth_preview(scene, cam_obj, out_depth)

        if still_only:
            still_png = tmp_dir / "frame_0001.png"
            scene.render.filepath = str(still_png)
            bpy.ops.render.render(write_still=True)
            mid_png = still_png
        else:
            bpy.ops.render.render(animation=True)
            mid_png = tmp_dir / f"frame_{mid_frame:04d}.png"
            if not mid_png.is_file():
                rendered = sorted(tmp_dir.glob("frame_*.png"))
                if rendered:
                    mid_png = rendered[len(rendered) // 2]

        if out_thumb is not None and mid_png.is_file():
            out_thumb.parent.mkdir(parents=True, exist_ok=True)
            if out_thumb.suffix.lower() in (".jpg", ".jpeg"):
                subprocess.run(
                    [str(ffmpeg_bin), "-y", "-i", str(mid_png), "-q:v", "2", str(out_thumb)],
                    capture_output=True,
                    check=False,
                )
            else:
                shutil.copy2(mid_png, out_thumb)

        if not still_only:
            cmd = [
                str(ffmpeg_bin),
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(tmp_dir / "frame_%04d.png"),
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-crf",
                "16",
                "-movflags",
                "+faststart",
                str(out_raw_mp4),
            ]
            enc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if enc.returncode != 0:
                raise RuntimeError(f"FFmpeg raw encode failed: {enc.stderr}")

        print(
            f"[CINEMA_SEQ_OK] {json.dumps({'raw_mp4': str(out_raw_mp4), 'frames': total_frames, 'fps': fps})}"
        )
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
