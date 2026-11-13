"""
Akunarch v2.1 — Canonical AAA Monument Baker (Blender 5.2 + Cycles OptiX + Draco GLB).

Law #7 Compliance:
  - Strictly BANS all 12 deprecated archived scripts in `E:\\Tools-3D\\scripts\\archived_selorson_monuments\\`.
  - Retains ONLY the author-approved `assemble_temple_zyberon.py` (+ shared `_aaa_monument_kit.py`),
    and dispatches all newly engineered 1:1 concept-faithful monuments from `E:\\Akunarch\\bin\\scripts\\monuments\\`.

Usage:
  blender.exe --background --python E:\\Akunarch\\bin\\scripts\\bake_canonical_monument.py -- <slug> <out_glb>
"""

import shutil
import sys
import tempfile
from pathlib import Path

KIT_AND_ZYBERON_DIR = Path(r"E:\Tools-3D\scripts\archived_selorson_monuments")
AKUNARCH_MONUMENTS_DIR = Path(r"E:\Akunarch\bin\scripts\monuments")
DEFAULT_BAKED_DIR = Path(r"E:\Tools-3D\baked_pbr")

# Law #7: ONLY `temple-of-zyberon` from the legacy folder + clean v2.1 scripts in `E:\Akunarch\bin\scripts\monuments\`
SLUG_TO_SCRIPT: dict[str, Path] = {
    "temple-of-zyberon": KIT_AND_ZYBERON_DIR / "assemble_temple_zyberon.py",
    "singularity-stonehenge-avalon": AKUNARCH_MONUMENTS_DIR / "assemble_stonehenge_avalon.py",
    "avalon-mage-sanctum": AKUNARCH_MONUMENTS_DIR / "assemble_avalon_mage_sanctum.py",
    "singularity-samos-olympus": AKUNARCH_MONUMENTS_DIR / "assemble_samos_olympus.py",
    "eryndor-clocktower-concept": AKUNARCH_MONUMENTS_DIR / "assemble_eryndor_clocktower.py",
}


def parse_blender_cli_args() -> tuple[str, Path]:
    argv = sys.argv
    if "--" not in argv:
        raise SystemExit("Usage: blender --background --python bake_canonical_monument.py -- <slug> <out_glb>")
    tail = argv[argv.index("--") + 1 :]
    if len(tail) < 2:
        raise SystemExit("Expected <slug> and <out_glb> after '--'")
    slug = tail[0].strip()
    out_glb = Path(tail[1]).resolve()
    return slug, out_glb


def main() -> None:
    slug, out_glb = parse_blender_cli_args()
    script_path = SLUG_TO_SCRIPT.get(slug)
    if not script_path:
        raise SystemExit(
            f"Unknown canonical monument slug '{slug}'. Supported canonical recipes: {sorted(SLUG_TO_SCRIPT)}"
        )

    if not script_path.is_file():
        raise SystemExit(f"Canonical recipe script not found: {script_path}")

    out_glb.parent.mkdir(parents=True, exist_ok=True)
    tmp_baked = Path(tempfile.mkdtemp(prefix=f"akunarch_bake_{slug}_"))

    for extra_path in (str(AKUNARCH_MONUMENTS_DIR), str(KIT_AND_ZYBERON_DIR)):
        if extra_path not in sys.path:
            sys.path.insert(0, extra_path)

    try:
        import _aaa_monument_kit as kit

        kit.BAKED_DIR = tmp_baked
        kit.MODELS_OUT_DIR = out_glb.parent

        source_code = script_path.read_text(encoding="utf-8")

        if slug == "temple-of-zyberon":
            source_code = source_code.replace(
                'BAKED_DIR = Path(r"E:\\Tools-3D\\baked_pbr")',
                f'BAKED_DIR = Path(r"{tmp_baked}")',
            )
            source_code = source_code.replace(
                'OUT_GLB = Path(r"E:\\Selorson-Ecosystem\\Selorson\\frontend-v3\\static\\world\\models\\temple-of-zyberon.glb")',
                f'OUT_GLB = Path(r"{out_glb}")',
            )

        exec_globals = {
            "__name__": "__main__",
            "__file__": str(script_path),
            "AKUNARCH_OUT_GLB": str(out_glb),
            "AKUNARCH_BAKED_DIR": str(tmp_baked),
        }
        exec(compile(source_code, str(script_path), "exec"), exec_globals)

        if not out_glb.is_file() or out_glb.stat().st_size < 1024:
            raise RuntimeError(f"Expected output GLB missing or empty: {out_glb}")

        print(f"[AKUNARCH_OK] Canonical monument '{slug}' baked -> {out_glb} ({out_glb.stat().st_size} bytes)")
    finally:
        shutil.rmtree(tmp_baked, ignore_errors=True)
        if DEFAULT_BAKED_DIR.is_dir():
            for leftover in DEFAULT_BAKED_DIR.glob("*"):
                try:
                    if leftover.is_file():
                        leftover.unlink()
                except OSError:
                    pass


if __name__ == "__main__":
    try:
        main()
    except BaseException as exc:
        import traceback

        traceback.print_exc()
        sys.stderr.flush()
        sys.stdout.flush()
        raise SystemExit(1) from exc
