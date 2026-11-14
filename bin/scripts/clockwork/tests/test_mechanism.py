import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mechanism import (  # noqa: E402
    idle_seam_errors, load_mechanism, mechanism_from_dict, motion_value, solve_kinematics, validate,
)

MINI = HERE / "fixtures" / "mini.mechanism.json"


def raw():
    return json.loads(MINI.read_text(encoding="utf-8"))


def errs(d):
    return validate(mechanism_from_dict(d))


class MechanismTest(unittest.TestCase):
    def test_mini_is_valid(self):
        self.assertEqual(validate(load_mechanism(MINI)), [])

    def test_decorative_gear_rejected(self):
        d = raw()
        d["shafts"].append({"id": "s_deco", "axis": [0, 0, 1], "origin": [200, 0, 0]})
        d["gears"].append({"id": "g_deco", "module": 2.0, "teeth": 20, "shaft": "s_deco", "thickness": 4, "material": "brass"})
        self.assertTrue(any("trang trí" in e and "g_deco" in e for e in errs(d)))

    def test_dead_end_gear_rejected(self):
        # ăn khớp vào đoàn bánh răng nhưng không kéo gì → vẫn là trang trí
        d = raw()
        d["shafts"].append({"id": "s_dead", "axis": [0, 0, 1], "origin": [0, 48, 0]})
        d["gears"].append({"id": "g_dead", "module": 2.0, "teeth": 36, "shaft": "s_dead", "thickness": 4, "material": "brass"})
        d["meshes"].append(["g12", "g_dead"])
        self.assertTrue(any("trang trí" in e and "g_dead" in e for e in errs(d)))

    def test_island_not_connected_to_pendulum(self):
        d = raw()
        d["shafts"] += [{"id": "s_i1", "axis": [0, 0, 1], "origin": [500, 0, 0]},
                        {"id": "s_i2", "axis": [0, 0, 1], "origin": [548, 0, 0]}]
        d["gears"] += [{"id": "g_i1", "module": 2.0, "teeth": 12, "shaft": "s_i1", "thickness": 4, "material": "brass"},
                       {"id": "g_i2", "module": 2.0, "teeth": 36, "shaft": "s_i2", "thickness": 4, "material": "brass"}]
        d["meshes"].append(["g_i1", "g_i2"])
        d["outputs"].append({"id": "o_island", "gear": "g_i2"})
        self.assertTrue(any("không nối tới con lắc" in e for e in errs(d)))

    def test_module_mismatch(self):
        d = raw()
        d["gears"][2]["module"] = 1.5
        self.assertTrue(any("module" in e for e in errs(d)))

    def test_center_distance_mismatch(self):
        d = raw()
        d["shafts"][1]["origin"] = [48.5, 0, 0]
        self.assertTrue(any("khoảng cách tâm" in e for e in errs(d)))

    def test_target_not_reached(self):
        d = raw()
        d["lead_screws"][0]["lift_mm"] = 5.0
        self.assertTrue(any("ls_lift" in e and "không đạt" in e for e in errs(d)))

    def test_step_unknown_part(self):
        d = raw()
        d["steps"].append({"id": "x", "beats": [0, 4], "part": "khong_co", "action": "move"})
        self.assertTrue(any("khong_co" in e for e in errs(d)))

    def test_kinematics_ratio_and_direction(self):
        k = solve_kinematics(load_mechanism(MINI), beat=10)
        self.assertAlmostEqual(k["g_esc"], 60.0)
        self.assertAlmostEqual(k["g12"], 60.0)  # cùng trục với bánh thoát
        self.assertAlmostEqual(k["g12"] + k["g36"] * 3, 0.0)  # ngược chiều, tỉ số 3
        self.assertAlmostEqual(abs(k["ls_lift"]), 20.0 / 360.0 * 2.0)

    def test_clutch_window(self):
        d = raw()
        d["gears"][2]["clutch"] = [10, 20]
        m = mechanism_from_dict(d)
        self.assertAlmostEqual(solve_kinematics(m, 5)["g36"], 0.0)
        self.assertAlmostEqual(solve_kinematics(m, 30)["g36"], solve_kinematics(m, 20)["g36"])
        # chỉ quay trong cửa sổ 10→20: bánh thoát đi (20−10)·6° = 60°, qua 12T→36T còn −20°
        self.assertAlmostEqual(solve_kinematics(m, 20)["g36"], -20.0)

    def test_pendulum_swing(self):
        m = load_mechanism(MINI)
        self.assertAlmostEqual(solve_kinematics(m, 0.5)["pendulum"], 8.0)
        self.assertAlmostEqual(solve_kinematics(m, 1.0)["pendulum"], 0.0, places=6)

    def test_clutch_on_meshed_gear_rejected(self):
        # g36 nhận chuyển động qua ăn khớp với g12 → ly hợp trên g36 là vô lý (g12 vẫn quay thì g36 phải quay)
        d = raw()
        d["gears"][2]["clutch"] = [10, 20]
        self.assertTrue(any("ly hợp" in e and "g36" in e for e in errs(d)))

    def test_clutch_on_shaft_linked_gear_ok(self):
        # g12 nối với bánh thoát qua chung trục → ly hợp vấu giữa bánh và trục là hợp lệ
        d = raw()
        d["gears"][1]["clutch"] = [10, 20]
        self.assertFalse(any("ly hợp" in e for e in errs(d)))

    def test_cam_drum_lift_rises_then_drops_at_pin(self):
        d = raw()
        d["cam_drums"].append({"id": "cd", "gear": "g36", "pins_beats": [10, 20], "drives": "hammer"})
        m = mechanism_from_dict(d)
        self.assertEqual(solve_kinematics(m, 5)["cd.lift"], 0.0)
        self.assertGreater(solve_kinematics(m, 9.7)["cd.lift"], 0.4)
        self.assertGreater(solve_kinematics(m, 9.95)["cd.lift"], solve_kinematics(m, 9.7)["cd.lift"])
        self.assertEqual(solve_kinematics(m, 10.05)["cd.lift"], 0.0)   # búa rơi đúng nhịp chốt
        self.assertGreater(solve_kinematics(m, 19.9)["cd.lift"], 0.8)

    def test_motion_zero_at_beat(self):
        m = load_mechanism(MINI)
        mo = {"part": "hand", "by": "g36", "type": "rotate", "scale": -1.0, "zero_at_beat": 30}
        self.assertAlmostEqual(motion_value(m, mo, solve_kinematics(m, 30)), 0.0)
        k10 = solve_kinematics(m, 10)
        want = -(k10["g36"] - solve_kinematics(m, 30)["g36"])
        self.assertAlmostEqual(motion_value(m, mo, k10), want)
        self.assertAlmostEqual(motion_value(m, {"part": "p", "by": "g36", "type": "rotate"}, k10), k10["g36"])

    def test_idle_seam(self):
        # mini: bánh thoát 30 răng, 6°/nhịp → 8 nhịp idle = 48° = 4 răng nhưng không chia hết 72° (5 nan hoa) → giật
        m = load_mechanism(MINI)
        self.assertTrue(any("g_esc" in e for e in idle_seam_errors(m)))
        d = raw()
        d["gears"][0]["style"] = "disc"          # không nan hoa → chỉ cần trọn răng
        d["gears"][1]["style"] = "disc"          # g12 cùng trục: 48°·12/360 = 1,6 răng → vẫn giật
        es = idle_seam_errors(mechanism_from_dict(d))
        self.assertFalse(any("g_esc" in e for e in es))
        self.assertTrue(any("g12" in e for e in es))

    def test_two_paths_disagree_means_jam(self):
        # g_par ăn khớp cả g12 lẫn g36 → g36 bị kéo theo 2 đường ngược chiều nhau → kẹt
        d = raw()
        d["shafts"].append({"id": "s_par", "axis": [0, 0, 1], "origin": [1.5, 11.90588, 0]})
        d["gears"].append({"id": "g_par", "module": 2.0, "teeth": 12, "shaft": "s_par", "thickness": 4})
        d["meshes"] += [["g12", "g_par"], ["g_par", "g36"]]
        self.assertTrue(any("kẹt" in e for e in errs(d)))

    def test_parallel_driver_is_useful(self):
        # bánh kéo song song (vòng kín khớp tỉ số) không bị coi là trang trí: 2 bánh côn cùng kéo 1 vành
        d = raw()
        d["shafts"] += [{"id": "s_v1", "axis": [1, 0, 0], "origin": [0, 0, 100]},
                        {"id": "s_v2", "axis": [0, 1, 0], "origin": [0, 0, 100]},
                        {"id": "s_ring", "axis": [0, 0, 1], "origin": [0, 0, 130]}]
        d["gears"] += [{"id": "g_b0", "module": 2.0, "teeth": 10, "shaft": "s_esc", "kind": "bevel", "z_mm": 90},
                       {"id": "g_v1", "module": 2.0, "teeth": 10, "shaft": "s_v1", "kind": "bevel"},
                       {"id": "g_v2", "module": 2.0, "teeth": 10, "shaft": "s_v2", "kind": "bevel"},
                       {"id": "g_ring", "module": 2.0, "teeth": 40, "shaft": "s_ring", "kind": "bevel", "style": "ring"}]
        d["meshes"] += [["g_b0", "g_v1"], ["g_b0", "g_v2"], ["g_v1", "g_ring"], ["g_v2", "g_ring"]]
        d["outputs"].append({"id": "o_ring", "gear": "g_ring", "drives": "ring"})
        self.assertEqual([e for e in errs(d) if "g_v" in e or "g_ring" in e or "kẹt" in e], [])

    def test_gear_style_parsed(self):
        d = raw()
        d["gears"][2]["style"] = "ring"
        m = mechanism_from_dict(d)
        self.assertEqual(m.gears["g36"].style, "ring")
        self.assertEqual(m.gears["g_esc"].style, "spoked")


if __name__ == "__main__":
    unittest.main()
