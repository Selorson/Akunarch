"""Dựng cơ cấu mẫu `mini` bằng Blender rồi đọc thẳng .glb: phải có 2 clip assemble/idle và góc bánh răng
trong animation khớp solve_kinematics (≤ 0,5°). Bỏ qua nếu máy không có Blender 5.2."""

import json
import math
import os
import struct
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mechanism import load_mechanism, solve_kinematics  # noqa: E402

BLENDER = Path(r"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe")
MINI = HERE / "fixtures" / "mini.mechanism.json"


def read_glb(p: Path):
    b = p.read_bytes()
    jl = struct.unpack_from("<I", b, 12)[0]
    gltf = json.loads(b[20:20 + jl])
    off = 20 + jl
    bl = struct.unpack_from("<I", b, off)[0]
    return gltf, b[off + 8: off + 8 + bl]


def accessor(gltf, binc, idx):
    acc = gltf["accessors"][idx]
    bv = gltf["bufferViews"][acc["bufferView"]]
    n = {"SCALAR": 1, "VEC3": 3, "VEC4": 4}[acc["type"]]
    start = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", 4 * n)
    return [struct.unpack_from(f"<{n}f", binc, start + i * stride) for i in range(acc["count"])]


@unittest.skipUnless(BLENDER.is_file(), "chưa cài Blender 5.2")
class MechanismGlbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="cwmini_")
        cls.out = Path(cls.tmp) / "mini_mechanism.glb"
        r = subprocess.run([str(BLENDER), "--background", "--python-exit-code", "1", "--python",
                            str(HERE.parent / "assemble_mechanism_glb.py"), "--", "--slug", "mini",
                            "--mech", str(MINI), "--out", str(cls.out)], capture_output=True, text=True, timeout=600)
        if r.returncode != 0:
            raise AssertionError(r.stdout[-3000:] + r.stderr[-2000:])
        cls.gltf, cls.bin = read_glb(cls.out)

    @classmethod
    def tearDownClass(cls):
        __import__("shutil").rmtree(cls.tmp, ignore_errors=True)

    def test_two_clips(self):
        self.assertEqual(sorted(a["name"] for a in self.gltf["animations"]), ["assemble", "idle"])

    def test_gear_styles(self):
        names = {n.get("name") for n in self.gltf["nodes"]}
        self.assertIn("CW_g_esc_spoke0", names)                       # spoked (mặc định): 5 nan hoa
        self.assertIn("CW_g12_web", names)                            # disc: đĩa đặc, không nan hoa
        self.assertNotIn("CW_g12_spoke0", names)
        self.assertFalse(any(n and n.startswith(("CW_g36_hub", "CW_g36_spoke", "CW_g36_web")) for n in names))  # ring

    def test_gear_rotation_matches_kinematics(self):
        mech = load_mechanism(MINI)
        names = [n.get("name") for n in self.gltf["nodes"]]
        anim = next(a for a in self.gltf["animations"] if a["name"] == "assemble")
        for gid in ("g_esc", "g12", "g36"):
            node = names.index(f"CW_{gid}")
            ch = next(c for c in anim["channels"] if c["target"]["node"] == node and c["target"]["path"] == "rotation")
            smp = anim["samplers"][ch["sampler"]]
            times = [t[0] for t in accessor(self.gltf, self.bin, smp["input"])]
            quats = accessor(self.gltf, self.bin, smp["output"])
            for beat in (0, 10, 24, 47):
                i = min(range(len(times)), key=lambda j: abs(times[j] - beat * 0.5))
                x, y, z, w = quats[i]
                got = math.degrees(2 * math.atan2(y, w))   # trục Z Blender → trục Y glTF
                want = solve_kinematics(mech, beat)[gid]
                diff = (got - want + 180) % 360 - 180
                self.assertLess(abs(diff), 0.5, f"{gid} nhịp {beat}: glTF {got:.2f}° ≠ động học {want:.2f}°")


if __name__ == "__main__":
    unittest.main()
