"""Kiểm thẳng file bản cơ khí Eryndor đã dựng qua hàng đợi (`assemble_mechanism_glb`): 2 clip, đủ bánh răng,
góc quay khớp động học, kim đứng XII ở nhịp 34, ngân sách tam giác. Bỏ qua nếu chưa dựng."""

import json
import math
import struct
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
from mechanism import load_mechanism, solve_kinematics  # noqa: E402
from test_mechanism_glb import accessor, read_glb  # noqa: E402

PROJ = Path(r"E:\Akunarch\projects\eryndor-clocktower-concept\clockwork")
GLB = PROJ / "eryndor-clocktower-concept_mechanism.glb"
SPEC = PROJ / "eryndor-clocktower-concept.mechanism.json"


def qmul(a, b):
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (aw * bx + ax * bw + ay * bz - az * by, aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw, aw * bw - ax * bx - ay * by - az * bz)


def rel_angle_deg(q0, q1) -> float:
    """Góc (0–180°) của phép quay đưa q0 tới q1."""
    x, y, z, w = qmul(q1, (-q0[0], -q0[1], -q0[2], q0[3]))
    return math.degrees(2 * math.atan2(math.sqrt(x * x + y * y + z * z), abs(w)))


def fold(deg: float) -> float:
    d = abs(deg) % 360
    return min(d, 360 - d)


@unittest.skipUnless(GLB.is_file(), "chưa dựng bản cơ khí Eryndor")
class EryndorMechanismGlbTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.gltf, cls.bin = read_glb(GLB)
        cls.mech = load_mechanism(SPEC)
        cls.names = [n.get("name") for n in cls.gltf["nodes"]]
        cls.anim = next(a for a in cls.gltf["animations"] if a["name"] == "assemble")

    def track(self, node_name):
        node = self.names.index(node_name)
        ch = next(c for c in self.anim["channels"] if c["target"]["node"] == node and c["target"]["path"] == "rotation")
        smp = self.anim["samplers"][ch["sampler"]]
        times = [t[0] for t in accessor(self.gltf, self.bin, smp["input"])]
        return times, accessor(self.gltf, self.bin, smp["output"])

    def at(self, times, vals, beat):
        return vals[min(range(len(times)), key=lambda j: abs(times[j] - beat * 0.5))]

    def test_two_clips(self):
        self.assertEqual(sorted(a["name"] for a in self.gltf["animations"]), ["assemble", "idle"])

    def test_every_gear_built(self):
        missing = [g for g in self.mech.gears if f"CW_{g}" not in self.names]
        self.assertEqual(missing, [])

    def test_gear_angles_match_kinematics(self):
        for gid in self.mech.gears:
            times, quats = self.track(f"CW_{gid}")
            q0 = self.at(times, quats, 0)
            for beat in (12, 24, 34, 46):
                got = rel_angle_deg(q0, self.at(times, quats, beat))
                want = fold(solve_kinematics(self.mech, beat)[gid])
                self.assertLess(abs(got - want), 0.5, f"{gid} nhịp {beat}: glTF {got:.2f}° ≠ động học {want:.2f}°")

    def test_hands_at_xii_on_beat_34(self):
        times, quats = self.track("CW_dial_hands")
        self.assertLess(rel_angle_deg((0, 0, 0, 1), self.at(times, quats, 34)), 0.5)
        self.assertGreater(rel_angle_deg((0, 0, 0, 1), self.at(times, quats, 10)), 20)

    def test_sculpts_face_outward(self):
        # chi tiết nặn (mặt trước lúc nặn = −Y Blender = +Z glTF) phải quay mặt ra ngoài tháp, không lệch 90°/180°
        # (lỗi v7: .glb nhập vào ở chế độ quay quaternion → rotation_euler bị bỏ qua, mọi bản cùng hướng)
        checked = 0
        for node in self.gltf["nodes"]:
            name = node.get("name") or ""
            if not name.startswith(("CW_portal_tracery", "CW_buttress_panel", "CW_clock_hood")):
                continue
            x, _, z = node.get("translation", [0, 0, 0])
            qx, qy, qz, qw = node.get("rotation", [0, 0, 0, 1])
            # vector (0,0,1) quay theo quaternion → lấy thành phần x, z (mặt phẳng ngang của glTF)
            fx = 2 * (qx * qz + qw * qy)
            fz = 1 - 2 * (qx * qx + qy * qy)
            d = math.hypot(x, z) * math.hypot(fx, fz)
            self.assertGreater((x * fx + z * fz) / d, 0.95, f"{name} không quay mặt ra ngoài")
            checked += 1
        self.assertEqual(checked, 3 + 24 + 1)

    def test_zodiac_ring_concentric_with_dial(self):
        # bản cơ khí: vòng hoàng đạo quay quanh tâm mặt đồng hồ → phải đồng tâm, lệch tâm thì quay bị chao (anh bắt lỗi)
        n = self.gltf["nodes"][self.names.index("ER_clock_face_zodiac_ring")]
        self.assertAlmostEqual(n["translation"][1], 12.35, places=2)    # glTF Y = Blender Z
        self.assertAlmostEqual(n["translation"][2], 0.0, places=2)      # glTF Z = −Blender Y

    def test_numerals_bright_gilt(self):
        # số La Mã + vạch giờ dùng vàng đánh bóng để nổi trên nền mặt số tối (anh yêu cầu)
        for name in ("ER_numeral_0", "ER_numeral_6", "ER_clock_face_tick0"):
            node = self.gltf["nodes"][self.names.index(name)]
            prim = self.gltf["meshes"][node["mesh"]]["primitives"][0]
            self.assertEqual(self.gltf["materials"][prim["material"]]["name"], "ER_cw_gilt", name)

    def test_triangle_budget(self):
        tris = 0
        for mesh in self.gltf["meshes"]:
            for p in mesh["primitives"]:
                idx = p.get("indices")
                if idx is not None:
                    tris += self.gltf["accessors"][idx]["count"] // 3
        self.assertLessEqual(tris, 900_000)


if __name__ == "__main__":
    unittest.main()
