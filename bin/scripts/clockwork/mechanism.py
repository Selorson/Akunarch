"""Đặc tả cơ cấu đồng hồ (`*.mechanism.json`), bộ kiểm luật "không bánh răng trang trí" và động học.

Mô hình: con lắc → bánh thoát (nhích `escape_advance_deg` mỗi nhịp) → bánh răng truyền qua ăn khớp
(ngoài: đảo chiều, tỉ số z_a/z_b; côn: giữ chiều) hoặc chung trục (cùng góc). Bánh có `clutch: [a, b]`
chỉ nhận chuyển động trong cửa sổ nhịp [a, b] (ly hợp cam) — cách sa bàn mở từng phần theo dòng thời gian.
Phần tử chấp hành (vít me, bản lề, thanh răng, trống chốt, đầu ra) đều gắn vào một bánh răng.
Không phụ thuộc bpy — đơn vị mm, góc độ.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path

from gear_math import center_distance, escape_advance_deg, pitch_radius


@dataclass
class Shaft:
    id: str
    axis: tuple[float, float, float]
    origin: tuple[float, float, float]


@dataclass
class Gear:
    id: str
    module: float
    teeth: int
    shaft: str
    thickness: float = 3.0
    material: str = "brass"
    kind: str = "spur"  # spur | bevel | sector
    clutch: tuple[float, float] | None = None
    style: str = "spoked"  # spoked (5 nan hoa) | disc (đĩa đặc) | ring (chỉ vành răng, như vành mặt đồng hồ)


@dataclass
class Element:
    """Phần tử chấp hành gắn vào một bánh răng. kind: lead_screw | hinge | rack | cam_drum | output."""
    id: str
    kind: str
    gear: str
    drives: str = ""
    pitch_mm: float = 0.0     # vít me
    lift_mm: float = 0.0      # vít me: độ nâng cần đạt
    max_deg: float = 0.0      # bản lề: góc mở cần đạt
    travel_mm: float = 0.0    # thanh răng: hành trình cần đạt
    pins_beats: list[float] = field(default_factory=list)  # trống chốt


@dataclass
class Step:
    id: str
    beats: tuple[float, float]
    part: str
    action: str = ""
    target: object = None


@dataclass
class Mechanism:
    name: str
    beats_total: int
    shafts: dict[str, Shaft]
    gears: dict[str, Gear]
    meshes: list[tuple[str, str]]
    pendulum_id: str
    escape_gear: str
    amplitude_deg: float
    elements: dict[str, Element]
    steps: list[Step]
    parts: list[str] = field(default_factory=list)

    @property
    def racks(self) -> dict[str, Element]:
        return {k: e for k, e in self.elements.items() if e.kind == "rack"}


_ELEMENT_KEYS = {"lead_screws": "lead_screw", "hinges": "hinge", "racks": "rack", "cam_drums": "cam_drum", "outputs": "output"}


def mechanism_from_dict(d: dict) -> Mechanism:
    shafts = {s["id"]: Shaft(s["id"], tuple(s["axis"]), tuple(s["origin"])) for s in d.get("shafts", [])}
    gears = {}
    for g in d.get("gears", []):
        gears[g["id"]] = Gear(
            g["id"], float(g["module"]), int(g["teeth"]), g["shaft"], float(g.get("thickness", 3.0)),
            g.get("material", "brass"), g.get("kind", "spur"), tuple(g["clutch"]) if g.get("clutch") else None,
            g.get("style", "spoked"),
        )
    elements = {}
    for key, kind in _ELEMENT_KEYS.items():
        for e in d.get(key, []):
            gear = e.get("gear") or e.get("pinion", "")
            elements[e["id"]] = Element(
                e["id"], kind, gear, e.get("drives", ""), float(e.get("pitch_mm", 0)), float(e.get("lift_mm", 0)),
                float(e.get("max_deg", 0)), float(e.get("travel_mm", 0)), list(e.get("pins_beats", [])),
            )
    p = d.get("pendulum", {})
    steps = [Step(s["id"], tuple(s["beats"]), s["part"], s.get("action", ""), s.get("target")) for s in d.get("steps", [])]
    return Mechanism(
        d.get("name", ""), int(d.get("beats_total", 48)), shafts, gears, [tuple(m) for m in d.get("meshes", [])],
        p.get("id", "pendulum"), p.get("escape_gear", ""), float(p.get("amplitude_deg", 8.0)), elements, steps,
        list(d.get("parts", [])),
    )


def load_mechanism(path: str | Path) -> Mechanism:
    return mechanism_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


# ---------- hình học ----------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _norm(a):
    n = math.sqrt(_dot(a, a))
    return (a[0] / n, a[1] / n, a[2] / n)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _parallel(a, b, tol=1e-6):
    c = _cross(_norm(a), _norm(b))
    return _dot(c, c) < tol


def _axis_distance(s1: Shaft, s2: Shaft) -> float:
    """Khoảng cách giữa hai trục song song."""
    ax = _norm(s1.axis)
    d = _sub(s2.origin, s1.origin)
    along = _dot(d, ax)
    perp = (d[0] - ax[0] * along, d[1] - ax[1] * along, d[2] - ax[2] * along)
    return math.sqrt(_dot(perp, perp))


# ---------- đồ thị truyền động ----------

def _propagate(m: Mechanism):
    """BFS từ bánh thoát: ratio (góc bánh / góc bánh thoát), cửa sổ ly hợp, và cha trên cây truyền động."""
    by_shaft: dict[str, list[str]] = {}
    for g in m.gears.values():
        by_shaft.setdefault(g.shaft, []).append(g.id)
    adj: dict[str, list[tuple[str, str]]] = {gid: [] for gid in m.gears}
    for a, b in m.meshes:
        if a in adj and b in adj:
            adj[a].append((b, "mesh"))
            adj[b].append((a, "mesh"))
    for ids in by_shaft.values():
        for a in ids:
            for b in ids:
                if a != b:
                    adj[a].append((b, "shaft"))

    info: dict[str, tuple[float, tuple[float, float]]] = {}
    parent: dict[str, str | None] = {}
    if m.escape_gear not in m.gears:
        return info, parent, adj
    inf = (-math.inf, math.inf)

    def window(gid, w):
        c = m.gears[gid].clutch
        return w if not c else (max(w[0], c[0]), min(w[1], c[1]))

    info[m.escape_gear] = (1.0, window(m.escape_gear, inf))
    parent[m.escape_gear] = None
    link: dict[str, str] = {}   # bánh → cách nhận chuyển động từ cha: "shaft" | "mesh"
    q = deque([m.escape_gear])
    while q:
        a = q.popleft()
        ra, wa = info[a]
        for b, how in adj[a]:
            if b in info:
                continue
            ga, gb = m.gears[a], m.gears[b]
            if how == "shaft":
                rb = ra
            elif "bevel" in (ga.kind, gb.kind):
                rb = ra * ga.teeth / gb.teeth
            else:
                rb = -ra * ga.teeth / gb.teeth
            info[b] = (rb, window(b, wa))
            parent[b] = a
            link[b] = how
            q.append(b)
    return info, parent, adj, link


LIFT_BEATS = 0.6   # búa được nhấc dần trong 0,6 nhịp trước chốt rồi rơi đúng nhịp chốt


def _cam_lift(pins: list[float], beat: float) -> float:
    for p in pins:
        if p - LIFT_BEATS <= beat < p:
            return (beat - (p - LIFT_BEATS)) / LIFT_BEATS
    return 0.0


def solve_kinematics(m: Mechanism, beat: float) -> dict[str, float]:
    """Góc (độ) của mọi bánh răng, giá trị của mọi phần tử (mm hoặc độ), và góc lắc con lắc tại nhịp `beat`."""
    adv = escape_advance_deg(m.gears[m.escape_gear].teeth) if m.escape_gear in m.gears else 0.0
    info = _propagate(m)[0]
    out: dict[str, float] = {}
    for gid, (ratio, (w0, w1)) in info.items():
        lo = max(0.0, w0)
        b = min(max(beat, lo), w1) if w1 >= lo else lo
        out[gid] = ratio * adv * (b - lo)
    for e in m.elements.values():
        ang = out.get(e.gear, 0.0)
        if e.kind == "lead_screw":
            out[e.id] = ang / 360.0 * e.pitch_mm
        elif e.kind == "rack":
            g = m.gears[e.gear]
            out[e.id] = abs(math.radians(ang)) * pitch_radius(g.module, g.teeth)
        elif e.kind == "hinge":
            out[e.id] = abs(ang)
        else:
            out[e.id] = ang
        if e.kind == "cam_drum":
            out[f"{e.id}.lift"] = _cam_lift(e.pins_beats, beat)   # 0 → 1: búa được nhấc, rơi về 0 tại chốt
    out[m.pendulum_id] = m.amplitude_deg * math.sin(math.pi * beat)
    return out


def motion_value(m: Mechanism, motion: dict, k: dict[str, float]) -> float:
    """Giá trị đẩy một bộ phận theo `motions[]` của đặc tả: k[by] · scale, trừ đi giá trị tại `zero_at_beat`
    (nếu có) để bộ phận đứng đúng tư thế dựng sẵn ở nhịp đó — ví dụ kim chạm XII đúng nhịp 34."""
    v = k.get(motion["by"], 0.0)
    if "zero_at_beat" in motion:
        v -= solve_kinematics(m, float(motion["zero_at_beat"])).get(motion["by"], 0.0)
    return v * motion.get("scale", 1.0)


def idle_seam_errors(m: Mechanism, idle_beats: int = 8, spokes: int = 5) -> list[str]:
    """Clip `idle` lặp vô hạn: sau `idle_beats` nhịp mọi bánh phải về hình y hệt lúc đầu (trọn răng, và trọn bước
    nan hoa nếu kiểu spoked); mọi giá trị khác (con lắc, búa, vít…) phải bằng nhau. Trả danh sách chỗ bị giật."""
    a, b = solve_kinematics(m, m.beats_total), solve_kinematics(m, m.beats_total + idle_beats)
    errs = []
    for key in a:
        d = b[key] - a[key]
        g = m.gears.get(key)
        if g is None:
            if abs(d) > 1e-6:
                errs.append(f"{key}: lệch {d:.3f} sau {idle_beats} nhịp idle.")
            continue
        # góc nhỏ nhất bánh trông y hệt: bước răng, hoặc bội chung của bước răng và bước nan hoa
        pitch = 360.0 / (math.gcd(g.teeth, spokes) if g.style == "spoked" else g.teeth)
        r = abs(d) % pitch
        if min(r, pitch - r) > 1e-6:
            errs.append(f"Bánh răng {key}: quay {d:.3f}° trong idle, không trọn bước {pitch:.3f}° → vòng lặp bị giật.")
    return errs


def validate(m: Mechanism) -> list[str]:
    errs: list[str] = []
    for g in m.gears.values():
        if g.shaft not in m.shafts:
            errs.append(f"Bánh răng {g.id}: trục '{g.shaft}' không có.")
    if m.escape_gear not in m.gears:
        errs.append(f"Con lắc: bánh thoát '{m.escape_gear}' không có.")
        return errs

    for a, b in m.meshes:
        if a not in m.gears or b not in m.gears:
            errs.append(f"Ăn khớp {a}–{b}: bánh răng không có.")
            continue
        ga, gb = m.gears[a], m.gears[b]
        if abs(ga.module - gb.module) > 1e-9:
            errs.append(f"Ăn khớp {a}–{b}: khác module ({ga.module} ≠ {gb.module}).")
            continue
        sa, sb = m.shafts.get(ga.shaft), m.shafts.get(gb.shaft)
        if not sa or not sb:
            continue
        if "bevel" in (ga.kind, gb.kind):
            if abs(_dot(_norm(sa.axis), _norm(sb.axis))) > 1e-3:
                errs.append(f"Ăn khớp côn {a}–{b}: hai trục phải vuông góc.")
            continue
        if not _parallel(sa.axis, sb.axis):
            errs.append(f"Ăn khớp {a}–{b}: hai trục không song song (dùng kind 'bevel' cho trục vuông góc).")
            continue
        want = center_distance(ga.module, ga.teeth, gb.teeth)
        got = _axis_distance(sa, sb)
        if abs(got - want) > 0.01 * ga.module:
            errs.append(f"Ăn khớp {a}–{b}: khoảng cách tâm {got:.3f} mm ≠ {want:.3f} mm.")

    info, parent, adj, link = _propagate(m)
    for gid, g in m.gears.items():
        if g.clutch and link.get(gid) == "mesh":
            errs.append(f"Bánh răng {gid}: ly hợp phải đặt giữa bánh và trục — bánh này nhận chuyển động qua ăn khớp "
                        f"với {parent[gid]} nên không thể đứng yên khi {parent[gid]} quay.")
    for e in m.elements.values():
        if e.gear not in m.gears:
            errs.append(f"Phần tử {e.id}: bánh răng '{e.gear}' không có.")
        elif e.gear not in info:
            errs.append(f"Phần tử {e.id}: không nối tới con lắc.")

    # bánh "có ích" = bánh của phần tử + mọi tổ tiên của nó trên cây truyền động
    useful: set[str] = set()
    for e in m.elements.values():
        g = e.gear if e.gear in info else None
        while g is not None and g not in useful:
            useful.add(g)
            g = parent.get(g)
    useful.add(m.escape_gear)

    # vòng kín: một bánh được kéo theo 2 đường (vd 2 bánh côn cùng kéo 1 vành) → tỉ số và cửa sổ ly hợp phải khớp,
    # không thì bộ máy kẹt; bánh kéo song song vào bánh có ích cũng là bánh có ích (chỉ xét ăn khớp, không xét chung trục)
    loops = [(a, b, how) for a in info for b, how in adj[a]
             if b in info and a < b and parent.get(b) != a and parent.get(a) != b]
    for a, b, how in loops:
        ga, gb = m.gears[a], m.gears[b]
        ra = info[a][0]
        want = ra if how == "shaft" else (ra if "bevel" in (ga.kind, gb.kind) else -ra) * ga.teeth / gb.teeth
        # bánh chung trục được phép khác cửa sổ (ly hợp nằm giữa bánh và trục); bánh ăn khớp thì không
        if abs(want - info[b][0]) > 1e-9 or (how == "mesh" and info[a][1] != info[b][1]):
            errs.append(f"Bánh răng {a}–{b}: hai đường truyền mâu thuẫn (tỉ số hoặc ly hợp) — bộ máy sẽ kẹt.")
    changed = True
    while changed:
        changed = False
        for a, b, how in loops:
            for x, y in ((a, b), (b, a)):
                if how == "mesh" and y in useful and x not in useful:
                    g = x
                    while g is not None and g not in useful:
                        useful.add(g)
                        g = parent.get(g)
                    changed = True
    for gid in m.gears:
        if gid in useful:
            continue
        if gid not in info and adj[gid]:
            errs.append(f"Bánh răng {gid}: không nối tới con lắc.")
        else:
            errs.append(f"Bánh răng {gid}: trang trí — không ăn khớp hoặc không kéo phần tử nào.")

    end = solve_kinematics(m, m.beats_total)
    for e in m.elements.values():
        if e.id not in end or e.gear not in info:
            continue
        v = abs(end[e.id])
        if e.kind == "lead_screw" and e.lift_mm and abs(v - e.lift_mm) > 0.1:
            errs.append(f"Vít me {e.id}: không đạt độ nâng {e.lift_mm} mm (được {v:.3f}).")
        if e.kind == "hinge" and e.max_deg and abs(v - e.max_deg) > 0.5:
            errs.append(f"Bản lề {e.id}: không đạt góc {e.max_deg}° (được {v:.2f}°).")
        if e.kind == "rack" and e.travel_mm and abs(v - e.travel_mm) > 0.1:
            errs.append(f"Thanh răng {e.id}: không đạt hành trình {e.travel_mm} mm (được {v:.3f}).")
        if e.kind == "cam_drum" and any(not (0 <= p <= m.beats_total) for p in e.pins_beats):
            errs.append(f"Trống chốt {e.id}: có chốt ngoài [0, {m.beats_total}] nhịp.")

    known = set(m.gears) | set(m.elements) | {e.drives for e in m.elements.values() if e.drives} | set(m.parts) | {m.pendulum_id}
    for s in m.steps:
        if s.part not in known:
            errs.append(f"Bước {s.id}: tham chiếu bộ phận '{s.part}' không có.")
        if not (0 <= s.beats[0] <= s.beats[1] <= m.beats_total):
            errs.append(f"Bước {s.id}: nhịp {s.beats} ngoài [0, {m.beats_total}].")
    return errs
