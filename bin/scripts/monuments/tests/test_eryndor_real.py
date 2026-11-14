"""Kiểm bản thật Tháp Eryndor bằng cách đọc thẳng chunk JSON của .glb (không cần Blender).

Chạy: python -m unittest discover -s E:\\Akunarch\\bin\\scripts\\monuments\\tests -p "test_eryndor_real.py"
Biến môi trường ERYNDOR_GLB để kiểm file khác (mặc định: bản _master nếu có, không thì bản runtime).
"""

import json
import os
import re
import struct
import unittest
from pathlib import Path

import math

PROJ = Path(r"E:\Akunarch\projects\eryndor-clocktower-concept\clockwork")
SLUG = "eryndor-clocktower-concept"


def glb_path() -> Path:
    if os.environ.get("ERYNDOR_GLB"):
        return Path(os.environ["ERYNDOR_GLB"])
    # `_master` là bản gốc trước khi nén KTX2; dựng lại sau lần nén thì bản runtime mới hơn → lấy bản mới nhất
    master, runtime = PROJ / "_master" / f"{SLUG}.glb", PROJ / f"{SLUG}.glb"
    found = [p for p in (master, runtime) if p.is_file()]
    return max(found, key=lambda p: p.stat().st_mtime) if found else runtime


def load_gltf(p: Path) -> dict:
    b = p.read_bytes()
    n = struct.unpack_from("<I", b, 12)[0]
    return json.loads(b[20:20 + n].decode("utf-8"))


def _mat(nd):
    if "matrix" in nd:
        m = nd["matrix"]
        return [[m[c * 4 + r] for c in range(4)] for r in range(4)]
    tx, ty, tz = nd.get("translation", [0, 0, 0])
    qx, qy, qz, qw = nd.get("rotation", [0, 0, 0, 1])
    sx, sy, sz = nd.get("scale", [1, 1, 1])
    r = [[1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qz * qw), 2 * (qx * qz + qy * qw)],
         [2 * (qx * qy + qz * qw), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qx * qw)],
         [2 * (qx * qz - qy * qw), 2 * (qy * qz + qx * qw), 1 - 2 * (qx * qx + qy * qy)]]
    return [[r[0][0] * sx, r[0][1] * sy, r[0][2] * sz, tx],
            [r[1][0] * sx, r[1][1] * sy, r[1][2] * sz, ty],
            [r[2][0] * sx, r[2][1] * sy, r[2][2] * sz, tz],
            [0, 0, 0, 1]]


def _mul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(4)) for j in range(4)] for i in range(4)]


def world_bounds(g: dict):
    """(minY, maxY, tên node có mesh) — glTF Y-up."""
    ys, names = [], set()

    def walk(i, pm):
        nd = g["nodes"][i]
        m = _mul(pm, _mat(nd))
        names.add(nd.get("name", ""))
        if "mesh" in nd:
            for prim in g["meshes"][nd["mesh"]]["primitives"]:
                acc = g["accessors"][prim["attributes"]["POSITION"]]
                for x in (acc["min"][0], acc["max"][0]):
                    for y in (acc["min"][1], acc["max"][1]):
                        for z in (acc["min"][2], acc["max"][2]):
                            ys.append(m[1][0] * x + m[1][1] * y + m[1][2] * z + m[1][3])
        for c in nd.get("children", []):
            walk(c, m)

    eye = [[1 if i == j else 0 for j in range(4)] for i in range(4)]
    for r in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(r, eye)
    return min(ys), max(ys), names


class EryndorRealTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.path = glb_path()
        if not cls.path.is_file():
            raise unittest.SkipTest(f"Chưa có {cls.path}")
        cls.g = load_gltf(cls.path)
        cls.ymin, cls.ymax, cls.names = world_bounds(cls.g)

    def count(self, prefix):
        """Đếm nhóm đúng dạng `<prefix><số>` (không đếm object con như ER_lancet_0_glass)."""
        pat = re.compile(re.escape(prefix) + r"\d+$")
        return len({n for n in self.names if pat.match(n)})

    def test_required_parts_present(self):
        for n in ["ER_clock_face", "ER_bell", "ER_armillary", "ER_pendulum",
                  "ER_spiral_stair", "ER_sanctuary", "ER_cliff", "ER_door", "ER_spire", "ER_sub_dials"]:
            self.assertIn(n, self.names, n)

    def test_single_bell(self):
        # anh chốt 2026-11-14: concept vẽ 2 chuông là lỗi thiết kế → 1 chuông treo giữa gác
        self.assertEqual(sorted(n for n in self.names if re.fullmatch(r"ER_bell(_[LR])?", n)), ["ER_bell"])

    def test_tower_height(self):
        # đỉnh quả cầu thiên văn tính từ mặt đất chân tháp (z=0): 26 m ±1,5
        self.assertGreaterEqual(self.ymax, 24.5)
        self.assertLessEqual(self.ymax, 27.5)
        self.assertLess(self.ymin, -6.0, "vách đá vôi phải nằm dưới chân tháp")

    def test_counts_match_concept_inventory(self):
        self.assertEqual(self.count("ER_pinnacle_"), 8)
        self.assertEqual(self.count("ER_lancet_"), 7)
        self.assertEqual(self.count("ER_buttress_"), 8)
        self.assertEqual(self.count("ER_corner_turret_"), 4)
        self.assertEqual(self.count("ER_belfry_arch_"), 4)
        self.assertEqual(self.count("ER_gable_"), 4)
        self.assertEqual(self.count("ER_zodiac_"), 12)
        self.assertEqual(self.count("ER_numeral_"), 12)

    def test_triangle_budget(self):
        tris = 0
        for m in self.g["meshes"]:
            for p in m["primitives"]:
                if "indices" in p:
                    tris += self.g["accessors"][p["indices"]]["count"] // 3
        self.assertLessEqual(tris, 600_000, tris)

    def test_every_material_textured(self):
        for mat in self.g.get("materials", []):
            pbr = mat.get("pbrMetallicRoughness", {})
            self.assertIn("baseColorTexture", pbr, f"material trơn: {mat.get('name')}")


if __name__ == "__main__":
    unittest.main()
