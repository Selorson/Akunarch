"""Đặc tả cơ cấu Tháp Eryndor bản cơ khí (theo concept_eryndor_clockwork_hero.jpg, anh duyệt 2026-11-14)."""

import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from mechanism import idle_seam_errors, load_mechanism, motion_value, solve_kinematics, validate  # noqa: E402

SPEC = Path(r"E:\Akunarch\projects\eryndor-clocktower-concept\clockwork\eryndor-clocktower-concept.mechanism.json")
XII_BEAT = 34


class EryndorMechanismTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import json
        cls.m = load_mechanism(SPEC)
        cls.raw = json.loads(SPEC.read_text(encoding="utf-8"))

    def motion(self, part):
        return next(mo for mo in self.raw["motions"] if mo["part"] == part)

    def test_valid_no_decorative_gear(self):
        self.assertEqual(validate(self.m), [])

    def test_timeline_48_beats(self):
        self.assertEqual(self.m.beats_total, 48)

    def test_idle_loop_seamless(self):
        self.assertEqual(idle_seam_errors(self.m), [])

    def test_hand_reaches_xii_then_stops(self):
        mo = self.motion("dial_hands")
        at = lambda b: motion_value(self.m, mo, solve_kinematics(self.m, b))  # noqa: E731
        self.assertAlmostEqual(at(XII_BEAT), 0.0, places=6)
        self.assertAlmostEqual(at(48), 0.0, places=6)            # đồng hồ dừng ở nửa đêm
        self.assertGreater(abs(at(0)), 300)                       # kim chạy 2 vòng (24 giờ) rồi tới XII
        self.assertLess(at(10), at(0))                            # chiều kim đồng hồ (âm quanh +X nhìn từ trước)

    def test_twelve_strikes_after_midnight(self):
        drums = [e for e in self.m.elements.values() if e.kind == "cam_drum"]
        self.assertEqual(len(drums), 1)                            # 1 chuông, 1 búa (anh chốt 2026-11-14)
        pins = sorted(drums[0].pins_beats)
        self.assertEqual(len(pins), 12)
        self.assertTrue(all(XII_BEAT < p <= 47 for p in pins))
        # trống chỉ quay trong lúc gõ (chốt đặt theo góc trống tại nhịp gõ)
        drum = drums[0].gear
        k = lambda b: solve_kinematics(self.m, b)[drum]  # noqa: E731
        self.assertEqual(k(30), 0.0)
        self.assertNotEqual(k(40), k(36))

    def test_tiers_turn_in_staggered_windows(self):
        tiers = ["g_tier1", "g_tier2", "g_tier3", "g_tier4"]
        k = lambda b, g: solve_kinematics(self.m, b)[g]  # noqa: E731
        for i, g in enumerate(tiers):
            self.assertAlmostEqual(k(1, g), 0.0)
            self.assertGreater(abs(k(30, g)), 10.0, g)
            self.assertAlmostEqual(k(30, g), k(48, g))
        # tầng trên quay nhiều hơn tầng dưới → chồng đĩa "xoắn" lên
        totals = [abs(k(48, g)) for g in tiers]
        self.assertEqual(totals, sorted(totals))

    def test_crown_ring_driven_by_two_wheels(self):
        # vành răng quanh chân tường răng cưa: 2 bánh đứng cùng kéo (validate đã kiểm 2 đường khớp tỉ số)
        meshes = {tuple(sorted(x)) for x in self.m.meshes}
        self.assertIn(("g_crown_ring", "g_wheelA"), meshes)
        self.assertIn(("g_crown_ring", "g_wheelB"), meshes)
        k = lambda b: solve_kinematics(self.m, b)["g_crown_ring"]  # noqa: E731
        self.assertGreater(abs(k(48)), 60)
        self.assertAlmostEqual(k(48), k(56))

    def test_each_tier_driven_by_three_layshafts(self):
        # concept thân dưới dày bánh răng: mỗi tầng được 3 bánh nhỏ trên 3 trục phụ cùng kéo (song song, khớp tỉ số)
        for k in range(1, 5):
            drivers = [a if b == f"g_tier{k}" else b for a, b in self.m.meshes if f"g_tier{k}" in (a, b)]
            self.assertEqual(len({self.m.gears[g].shaft for g in drivers}), 3, f"g_tier{k}")

    def test_upper_cascade_has_many_visible_gears(self):
        # mặt hở bên trái (trục song song Y) phải đủ dày bánh răng như concept
        y_axis = [g for g in self.m.gears.values() if self.m.shafts[g.shaft].axis == (0, 1, 0) and g.kind != "bevel"]
        self.assertGreaterEqual(len(y_axis), 9)

    def test_only_heart_beats_in_idle(self):
        a, b = solve_kinematics(self.m, 48), solve_kinematics(self.m, 56)
        moving = {g for g in self.m.gears if abs(b[g] - a[g]) > 1e-9}
        self.assertEqual(moving, {"g_esc", "g_e2", "g_t1"})


if __name__ == "__main__":
    unittest.main()
