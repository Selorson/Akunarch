import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cinema_path import KEYS, camera_at  # noqa: E402


class CinemaPathTest(unittest.TestCase):
    def test_passes_through_keys(self):
        for beat, az, el, dist, tz in KEYS:
            got = camera_at(beat)
            self.assertAlmostEqual(got[0], az, places=6)
            self.assertAlmostEqual(got[1], el, places=6)
            self.assertAlmostEqual(got[2], dist, places=6)
            self.assertAlmostEqual(got[3], tz, places=6)

    def test_camera_never_static(self):
        # luật "camera không bao giờ đứng yên": mọi khung 1/12 nhịp đều dịch chuyển
        prev = camera_at(0.0)
        for f in range(1, 48 * 12 + 1):
            cur = camera_at(f / 12)
            self.assertGreater(sum(abs(a - b) for a, b in zip(cur, prev)), 1e-5, f"đứng yên ở khung {f}")
            prev = cur

    def test_ends_close_on_clock(self):
        az, el, dist, tz = camera_at(48.0)
        self.assertLess(dist, camera_at(0.0)[2] * 0.6, "kết bằng cận cảnh")
        self.assertGreater(tz, 0.35, "nhìn vào vùng mặt đồng hồ (≥ 35% chiều cao)")


if __name__ == "__main__":
    unittest.main()
