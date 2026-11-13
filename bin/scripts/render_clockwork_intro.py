"""
Akunarch v2.0 — Cinematic Turntable & Emerge Intro Video Renderer (Blender 5.2 + FFmpeg H.264).

Loads a real PBR `.glb` monument, builds a dark obsidian studio lighting rig (Key/Rim/Fill + World zenith),
animates a smooth 360-degree architectural turntable camera with subtle vertical crane rise,
renders crisp frames on RTX 4080, and encodes an H.264 `.mp4` (`yuv420p`) via FFmpeg.

Usage:
  blender.exe --background --python E:\\Akunarch\\bin\\scripts\\render_clockwork_intro.py -- \
      --glb <glb_path> --out <out_mp4> [--frames 48] [--width 1280] [--height 720] [--fps 24]
"""

import math
import shutil
import subprocess
import sys
import tempfile
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


def main() -> None:
    opts = parse_args()
    glb_path = Path(opts.get("glb", "")).resolve()
    out_mp4 = Path(opts.get("out", "")).resolve()
    frames = max(12, int(opts.get("frames", "48")))
    width = max(320, int(opts.get("width", "1280")))
    height = max(240, int(opts.get("height", "720")))
    fps = max(12, int(opts.get("fps", "24")))
    ffmpeg_bin = Path(opts.get("ffmpeg", str(FFMPEG_DEFAULT)))

    if not glb_path.is_file():
        raise SystemExit(f"Input GLB not found: {glb_path}")
    if not ffmpeg_bin.is_file():
        found = shutil.which("ffmpeg")
        if not found:
            raise SystemExit(f"FFmpeg binary not found at {ffmpeg_bin}")
        ffmpeg_bin = Path(found)

    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    tmp_frames_dir = Path(tempfile.mkdtemp(prefix="akunarch_intro_frames_"))

    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        scene = bpy.context.scene
        scene.unit_settings.system = "METRIC"

        bpy.ops.import_scene.gltf(filepath=str(glb_path))
        bpy.context.view_layer.update()

        meshes = [o for o in scene.objects if o.type == "MESH"]
        if not meshes:
            raise RuntimeError(f"No mesh geometry found in {glb_path}")

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
        radius = max(1.0, 0.5 * max(span.x, span.y, span.z))

        # Studio World lighting
        world = bpy.data.worlds.new("AkunarchStudioWorld")
        world.use_nodes = True
        bg = world.node_tree.nodes.get("Background")
        if bg:
            bg.inputs[0].default_value = (0.018, 0.024, 0.036, 1.0)
            bg.inputs[1].default_value = 1.15
        scene.world = world

        # 3-Point Studio Sun/Area Rig
        def add_sun(name: str, rot_deg: tuple[float, float, float], energy: float, rgb: tuple[float, float, float]):
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

        # Turntable Camera + Track-To Target
        target_emp = bpy.data.objects.new("CamTarget", None)
        target_emp.location = (center.x, center.y, center.z + span.z * 0.04)
        scene.collection.objects.link(target_emp)

        cam_data = bpy.data.cameras.new("TurntableCam")
        cam_data.lens = 42.0
        cam_data.clip_start = 0.05
        cam_data.clip_end = max(500.0, radius * 40.0)
        cam_obj = bpy.data.objects.new("TurntableCam", cam_data)
        scene.collection.objects.link(cam_obj)
        scene.camera = cam_obj

        track = cam_obj.constraints.new(type="TRACK_TO")
        track.target = target_emp
        track.track_axis = "TRACK_NEGATIVE_Z"
        track.up_axis = "UP_Y"

        scene.frame_start = 1
        scene.frame_end = frames
        cam_dist = radius * 2.55
        for f in range(1, frames + 1):
            t = (f - 1) / float(frames)
            ang = -math.pi * 0.5 + t * (2.0 * math.pi)
            elev = center.z + radius * (0.72 + 0.14 * math.sin(t * math.pi))
            cam_obj.location = (
                center.x + cam_dist * math.cos(ang),
                center.y + cam_dist * math.sin(ang),
                elev,
            )
            cam_obj.keyframe_insert(data_path="location", frame=f)

        # Render with Cycles OptiX GPU (low noise, fast 16 samples + denoiser fallback)
        scene.render.engine = "CYCLES"
        cprefs = bpy.context.preferences.addons["cycles"].preferences
        cprefs.compute_device_type = "OPTIX"
        cprefs.get_devices()
        for dev in cprefs.devices:
            dev.use = dev.type == "OPTIX" and "RTX" in dev.name
        scene.cycles.device = "GPU"
        scene.cycles.samples = 16
        scene.cycles.use_denoising = False

        scene.render.resolution_x = width
        scene.render.resolution_y = height
        scene.render.resolution_percentage = 100
        scene.render.fps = fps
        scene.render.image_settings.file_format = "PNG"
        scene.render.filepath = str(tmp_frames_dir / "frame_")
        scene.view_settings.view_transform = "AgX" if "AgX" in ["Standard", "AgX"] else "Filmic"

        bpy.ops.render.render(animation=True)

        cmd = [
            str(ffmpeg_bin),
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(tmp_frames_dir / "frame_%04d.png"),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-crf",
            "18",
            "-movflags",
            "+faststart",
            str(out_mp4),
        ]
        enc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if enc.returncode != 0:
            raise RuntimeError(f"FFmpeg encode failed: {enc.stderr}")

        print(f"[AKUNARCH_OK] Rendered Intro MP4 -> {out_mp4} ({out_mp4.stat().st_size} bytes)")
    finally:
        shutil.rmtree(tmp_frames_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
