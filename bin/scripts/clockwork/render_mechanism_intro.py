"""
Akunarch P0 — Video intro BẢN CƠ KHÍ: dựng lại cảnh từ đặc tả (cùng động cơ assemble_mechanism_glb.build_scene,
nên khớp 1:1 với .glb), phát clip `assemble`, camera bay theo cinema_path (không bao giờ đứng yên, kết cận mặt
đồng hồ), studio tối #090d16, EEVEE → PNG → ffmpeg H.264 (+ nhạc nền lặp nếu có --audio).

  blender --background --python render_mechanism_intro.py -- --glb <clockwork/<slug>_mechanism.glb>
          --out <cinema/<slug>_mechanism_intro.mp4> [--width 1920 --height 1080 --audio <bgm>] [--slug s --mech m]
Gọi qua hàng đợi: gpu_enqueue(slug, 'blender', {mode: 'render_intro_mp4', variant: 'mechanism'}).
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import bpy
from mathutils import Vector

HERE = Path(r"E:\Akunarch\bin\scripts\clockwork")
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import assemble_mechanism_glb as amg  # noqa: E402
from cinema_path import camera_at  # noqa: E402

FFMPEG = Path(r"C:\Users\Admin\.local\bin\ffmpeg.exe")


def resolve_spec(glb: Path, slug: str | None, mech: str | None) -> tuple[str, Path]:
    clock = glb.parent.parent if glb.parent.name == "_master" else glb.parent
    s = slug or glb.stem.removesuffix("_mechanism")
    return s, Path(mech) if mech else clock / f"{s}.mechanism.json"


def world_bounds(scene):
    lo, hi = Vector((1e9, 1e9, 1e9)), Vector((-1e9, -1e9, -1e9))
    for ob in scene.objects:
        if ob.type != "MESH":
            continue
        for c in ob.bound_box:
            w = ob.matrix_world @ Vector(c)
            lo = Vector(map(min, lo, w))
            hi = Vector(map(max, hi, w))
    return lo, hi


def main():
    a = amg.parse_args()
    glb, out = Path(a["glb"]), Path(a["out"])
    w, h = int(a.get("width", 1920)), int(a.get("height", 1080))
    slug, mech_path = resolve_spec(glb, a.get("slug"), a.get("mech"))
    scene, _t0, mech, _n, _p = amg.build_scene(slug, mech_path)

    for ob in scene.objects:   # chỉ phát clip lắp ráp
        if ob.animation_data:
            for tr in ob.animation_data.nla_tracks:
                tr.mute = tr.name != "assemble"
    last = mech.beats_total * amg.FRAMES_PER_BEAT
    scene.frame_start, scene.frame_end = 0, last
    scene.render.fps = amg.FPS

    bounds = [world_bounds(scene)]
    scene.frame_set(last)
    bounds.append(world_bounds(scene))
    scene.frame_set(0)
    lo = Vector(map(min, bounds[0][0], bounds[1][0]))
    hi = Vector(map(max, bounds[0][1], bounds[1][1]))
    H = max(hi.z - lo.z, 1e-3)
    cx, cy = (lo.x + hi.x) / 2, (lo.y + hi.y) / 2

    target = bpy.data.objects.new("CAM_target", None)
    scene.collection.objects.link(target)
    cam = bpy.data.objects.new("CAM", bpy.data.cameras.new("CAM"))
    cam.data.lens = 40
    cam.data.clip_start = H * 0.002
    cam.data.clip_end = H * 50
    scene.collection.objects.link(cam)
    scene.camera = cam
    tt = cam.constraints.new("TRACK_TO")
    tt.target, tt.track_axis, tt.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
    for f in range(last + 1):
        az, el, d, tz = camera_at(f / amg.FRAMES_PER_BEAT)
        ra, re = math.radians(az), math.radians(el)
        cam.location = (cx + d * H * math.cos(re) * math.cos(ra), cy + d * H * math.cos(re) * math.sin(ra), lo.z + tz * H + d * H * math.sin(re))
        target.location = (cx, cy, lo.z + tz * H)
        cam.keyframe_insert("location", frame=f)
        target.keyframe_insert("location", frame=f)

    world = bpy.data.worlds.new("studio")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.0034, 0.0042, 0.0085, 1.0)   # #090d16
    scene.world = world
    for name, typ, energy, color, loc in (
        ("KEY", "AREA", 900.0, (1.0, 0.92, 0.80), (H * 1.2, -H * 1.1, H * 1.6)),
        ("RIM", "AREA", 500.0, (0.62, 0.80, 1.0), (-H * 1.3, H * 1.2, H * 1.2)),
        ("FILL", "AREA", 160.0, (0.86, 0.9, 1.0), (-H * 0.4, -H * 1.6, H * 0.4)),
    ):
        lt = bpy.data.lights.new(name, typ)
        lt.energy, lt.color = energy * H * H, color
        lt.size = H * 0.8
        lo_ = bpy.data.objects.new(name, lt)
        lo_.location = loc
        c = lo_.constraints.new("TRACK_TO")
        c.target, c.track_axis, c.up_axis = target, "TRACK_NEGATIVE_Z", "UP_Y"
        scene.collection.objects.link(lo_)

    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.render.image_settings.file_format = "PNG"
    frames = Path(tempfile.mkdtemp(prefix="akun_mechintro_"))
    try:
        scene.render.filepath = str(frames / "f_")
        bpy.ops.render.render(animation=True)
        out.parent.mkdir(parents=True, exist_ok=True)
        cmd = [str(FFMPEG), "-y", "-framerate", str(amg.FPS), "-i", str(frames / "f_%04d.png")]
        audio = a.get("audio")
        if audio and Path(audio).is_file():
            cmd += ["-stream_loop", "-1", "-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
        cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError("ffmpeg lỗi: " + r.stderr[-1500:])
        print(f"=== [MECH INTRO] {out} ({out.stat().st_size / 1048576:.1f} MB, {last + 1} khung) ===")
    finally:
        shutil.rmtree(frames, ignore_errors=True)
        shutil.rmtree(amg.kit.BAKED_DIR, ignore_errors=True)


main()
