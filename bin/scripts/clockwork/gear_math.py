"""Toán bánh răng thân khai (không phụ thuộc bpy) — đơn vị mm, góc độ trừ khi ghi rõ."""

from __future__ import annotations

import math

PRESSURE_DEG = 20.0
ADDENDUM = 1.0   # × module
DEDENDUM = 1.25  # × module


def pitch_radius(module: float, teeth: int) -> float:
    return module * teeth / 2.0


def base_radius(module: float, teeth: int, pressure_deg: float = PRESSURE_DEG) -> float:
    return pitch_radius(module, teeth) * math.cos(math.radians(pressure_deg))


def outer_radius(module: float, teeth: int) -> float:
    return pitch_radius(module, teeth) + ADDENDUM * module


def root_radius(module: float, teeth: int) -> float:
    return pitch_radius(module, teeth) - DEDENDUM * module


def center_distance(module: float, z1: int, z2: int) -> float:
    return module * (z1 + z2) / 2.0


def escape_advance_deg(escape_teeth: int) -> float:
    """Bánh thoát neo nhích nửa răng mỗi nhịp lắc (một nhịp = nửa chu kỳ con lắc)."""
    return 360.0 / (2 * escape_teeth)


def _inv(alpha: float) -> float:
    return math.tan(alpha) - alpha


def involute_tooth(module: float, teeth: int, pressure_deg: float = PRESSURE_DEG, samples: int = 12) -> list[tuple[float, float]]:
    """Biên dạng một răng quanh trục +X (đối xứng qua X): chân dưới → sườn dưới → đỉnh → sườn trên → chân trên."""
    rp = pitch_radius(module, teeth)
    rb = base_radius(module, teeth, pressure_deg)
    ra = outer_radius(module, teeth)
    rf = root_radius(module, teeth)
    alpha_p = math.radians(pressure_deg)
    psi_p = math.pi / (2 * teeth)

    def half_angle(r: float) -> float:
        a = math.acos(min(1.0, rb / r))
        return psi_p + _inv(alpha_p) - _inv(a)

    r0 = max(rb, rf)
    radii = [r0 + (ra - r0) * i / (samples - 1) for i in range(samples)]
    lower: list[tuple[float, float]] = []
    if rf < rb:  # đoạn chân răng hướng tâm bên dưới vòng cơ sở
        a = -half_angle(rb)
        lower.append((rf * math.cos(a), rf * math.sin(a)))
    for r in radii:
        a = -half_angle(r)
        lower.append((r * math.cos(a), r * math.sin(a)))

    psi_a = half_angle(ra)
    tip = []
    k = 3
    for i in range(1, k + 1):
        a = -psi_a + 2 * psi_a * i / (k + 1)
        tip.append((ra * math.cos(a), ra * math.sin(a)))

    upper = [(x, -y) for x, y in reversed(lower)]
    return lower + tip + upper
