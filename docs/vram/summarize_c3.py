"""Tổng hợp nghiệm thu C3: trung vị 3 lượt cho từng số đo (scenarios_c3_r*.json + scenarios_c3_s5_r*.json)."""
import json
import statistics
from pathlib import Path

D = Path(r"E:\Akunarch\docs\vram")


def load(pattern):
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(D.glob(pattern))]


def med(vals):
    vals = [v for v in vals if v is not None]
    return round(statistics.median(vals), 1) if vals else None


runs = load("scenarios_c3_r[123].json")
print(f"Akunarch: {len(runs)} lượt")
keys = sorted({k for r in runs for k in r.get("measurements", {})})
for k in keys:
    ms = [r["measurements"].get(k) for r in runs]
    ms = [m for m in ms if m]
    print(
        f"{k:34s} app={med([m['app_vram_mb_median'] for m in ms])!s:>7} MB  "
        f"app3D={med([m['app_gpu3d_pct_avg'] for m in ms])!s:>5}%  gpu={med([m['gpu_util_avg'] for m in ms])!s:>5}%  "
        f"pstate={[m['gpu_pstate_mode'] for m in ms]}  W={med([m['gpu_power_w_avg'] for m in ms])}  "
        f"từng lượt={[m['app_vram_mb_median'] for m in ms]}"
    )
for pk in ["S1_cold_boot", "S2_3d_idle", "S3_round_1", "S3_round_3", "S4_after_stop", "S4_final"]:
    ps = [r.get("probes", {}).get(pk) for r in runs]
    print(pk, [{k: p.get(k) for k in ("created", "lost", "consoleTooManyContexts", "standby2d") if p and k in p} for p in ps])
for r in runs:
    print(r["phase"], [n for n in r.get("notes", []) if "S4" in n or "RESTORE" in n or "khôi phục" in n])

s5 = load("scenarios_c3_s5_r[123].json")
print(f"\nSelorson S5: {len(s5)} lượt")
for r in s5:
    print(r["phase"], r.get("summary"), r.get("error"), r.get("notes"))
if s5 and all(r.get("summary") for r in s5):
    for f in ["before_mb", "in_world_mb", "after_mb", "delta_mb"]:
        print(f, med([r["summary"][f] for r in s5]))
