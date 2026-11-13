"""Đường bay camera cho video intro bản cơ khí (không phụ thuộc bpy).

Spline Catmull-Rom đều qua các mốc (nhịp → góc phương vị, góc ngẩng, khoảng cách × chiều cao mô hình,
điểm nhìn × chiều cao). Góc phương vị tăng đơn điệu nên camera không bao giờ đứng yên; kết bằng cận cảnh
mặt đồng hồ (phương vị 0° = mặt +X, mặt đồng hồ của tháp) đúng lúc kim chạm XII.
"""

from __future__ import annotations

# (nhịp, phương vị °, ngẩng °, khoảng cách × H, điểm nhìn × H)
KEYS: list[tuple[float, float, float, float, float]] = [
    (0.0, -110.0, 32.0, 2.4, 0.30),
    (12.0, -75.0, 26.0, 2.0, 0.35),
    (24.0, -45.0, 20.0, 1.6, 0.40),
    (36.0, -20.0, 14.0, 1.25, 0.45),
    (44.0, -8.0, 8.0, 0.85, 0.47),
    (48.0, 0.0, 4.0, 0.7, 0.45),
]


def _cr(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * (2 * p1 + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def camera_at(beat: float) -> tuple[float, float, float, float]:
    """(phương vị °, ngẩng °, khoảng cách × H, điểm nhìn × H) tại nhịp `beat` (kẹp trong [đầu, cuối])."""
    b = min(max(beat, KEYS[0][0]), KEYS[-1][0])
    i = max(k for k in range(len(KEYS) - 1) if KEYS[k][0] <= b) if b < KEYS[-1][0] else len(KEYS) - 2
    k0, k1 = KEYS[i], KEYS[i + 1]
    t = (b - k0[0]) / (k1[0] - k0[0])
    km = KEYS[i - 1] if i > 0 else tuple(2 * a - c for a, c in zip(k0, k1))
    kp = KEYS[i + 2] if i + 2 < len(KEYS) else tuple(2 * c - a for a, c in zip(k0, k1))
    return tuple(_cr(km[j], k0[j], k1[j], kp[j], t) for j in range(1, 5))
