import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from gear_math import base_radius, center_distance, escape_advance_deg, involute_tooth, pitch_radius  # noqa: E402


class GearMathTest(unittest.TestCase):
    def test_center_distance(self):
        self.assertEqual(center_distance(2.0, 12, 36), 48.0)

    def test_pitch_and_base_radius(self):
        self.assertEqual(pitch_radius(2.0, 12), 12.0)
        self.assertAlmostEqual(base_radius(2.0, 12), 12.0 * math.cos(math.radians(20.0)))
        self.assertLess(base_radius(2.0, 12), pitch_radius(2.0, 12))

    def test_involute_tooth_symmetric_and_bounded(self):
        m, z = 2.0, 12
        pts = involute_tooth(m, z)
        self.assertGreaterEqual(len(pts), 8)
        for (x1, y1), (x2, y2) in zip(pts, reversed(pts)):
            self.assertAlmostEqual(x1, x2, places=6)
            self.assertAlmostEqual(y1, -y2, places=6)
        rs = [math.hypot(x, y) for x, y in pts]
        self.assertAlmostEqual(max(rs), pitch_radius(m, z) + m, places=6)  # đỉnh răng = r + addendum
        self.assertGreaterEqual(min(rs), pitch_radius(m, z) - 1.25 * m - 1e-6)  # không sâu hơn chân răng

    def test_tooth_thickness_at_pitch_is_half_pitch(self):
        m, z = 2.0, 20
        half_angle = max(abs(math.atan2(y, x)) for x, y in involute_tooth(m, z, samples=64)
                         if abs(math.hypot(x, y) - pitch_radius(m, z)) < 0.05)
        # bề dày cung tại vòng chia ≈ π·m/2 → nửa góc ≈ π/(2z)
        self.assertAlmostEqual(half_angle, math.pi / (2 * z), delta=0.01)

    def test_escape_advance(self):
        self.assertEqual(escape_advance_deg(30), 6.0)


if __name__ == "__main__":
    unittest.main()
