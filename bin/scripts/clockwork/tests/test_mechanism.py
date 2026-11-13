import copy
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mechanism import load_mechanism, mechanism_from_dict, solve_kinematics, validate  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
