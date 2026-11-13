#!/usr/bin/env python3
"""
Akunarch Phase 3 — Sequential Zero-OOM Local TTS Synthesizer (`VieNeu-TTS` VI + `OmniVoice` EN)
===============================================================================================
Executes 100% offline against `D:\\hf-cache`:
  - Vietnamese (`lang="vi"`): `E:\\Akunarch\\repos\\VieNeu-TTS\\.venv\\Scripts\\python.exe`
    using `pnnbao-ump/VieNeu-TTS-v3-Turbo` + Southern Vietnamese preset voices (`Thùy Dung`,
    `Minh Triết`, `Mỹ Duyên`, `Thái Sơn`, `Đức Trí`, `Kim Thanh`, `Thục Đoan`) or voice cloning.
  - English / Multilingual (`lang="en"`): `E:\\Akunarch\\repos\\OmniVoice\\.venv\\Scripts\\python.exe`
    using `k2-fsa/OmniVoice` (`fp16` on `cuda:0` + `OpenMOSS-Team/MOSS-Audio-Tokenizer-Nano`)
    with Voice Design `instruct` attributes or reference audio cloning.

Guarantees 1-model-at-a-time GPU execution: when given a mixed VI + EN batch JSON,
runs all VI lines in one `VieNeu-TTS` subprocess (which exits and frees 100% VRAM),
then runs all EN lines in one `OmniVoice` subprocess.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

HF_CACHE_DIR = r"D:\hf-cache"
VIENEU_REPO = Path(r"E:\Akunarch\repos\VieNeu-TTS")
VIENEU_PYTHON = VIENEU_REPO / ".venv" / "Scripts" / "python.exe"
OMNIVOICE_REPO = Path(r"E:\Akunarch\repos\OmniVoice")
OMNIVOICE_PYTHON = OMNIVOICE_REPO / ".venv" / "Scripts" / "python.exe"

SOUTHERN_VI_DEFAULT_VOICES = {
    "female": "Thùy Dung",
    "male": "Minh Triết",
    "narrator": "Mỹ Duyên",
    "elder": "Thái Sơn",
}

OMNIVOICE_VALID_INSTRUCT_TOKENS = {
    "american accent",
    "australian accent",
    "british accent",
    "canadian accent",
    "child",
    "chinese accent",
    "elderly",
    "female",
    "high pitch",
    "indian accent",
    "japanese accent",
    "korean accent",
    "low pitch",
    "male",
    "middle-aged",
    "moderate pitch",
    "portuguese accent",
    "russian accent",
    "teenager",
    "very high pitch",
    "very low pitch",
    "whisper",
    "young adult",
}

EN_VOICE_INSTRUCT_PRESETS = {
    "female": "female, young adult, moderate pitch, american accent",
    "male": "male, young adult, low pitch, british accent",
    "narrator": "female, young adult, moderate pitch, british accent",
    "elder": "male, middle-aged, low pitch, british accent",
    "whisper": "female, young adult, whisper, british accent",
}


def _sanitize_omnivoice_instruct(raw_voice: str) -> str:
    key = raw_voice.strip().lower()
    if key in EN_VOICE_INSTRUCT_PRESETS:
        return EN_VOICE_INSTRUCT_PRESETS[key]
    tokens = [tok.strip().lower() for tok in raw_voice.split(",") if tok.strip()]
    valid = [tok for tok in tokens if tok in OMNIVOICE_VALID_INSTRUCT_TOKENS]
    if valid:
        return ", ".join(valid)
    return EN_VOICE_INSTRUCT_PRESETS["narrator"]


def _configure_offline_env() -> None:
    os.environ["HF_HOME"] = HF_CACHE_DIR
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(Path(HF_CACHE_DIR) / "hub")
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["PYTHONUTF8"] = "1"


def _run_vieneu_worker(items: list[dict]) -> list[dict]:
    _configure_offline_env()
    for p in (str(VIENEU_REPO / "src"), str(VIENEU_REPO)):
        if p not in sys.path:
            sys.path.insert(0, p)

    import soundfile as sf  # type: ignore
    from vieneu import Vieneu  # type: ignore

    t0 = time.perf_counter()
    engine = Vieneu()
    preset_voices = engine.list_preset_voices()
    valid_names = {label for label, _ in preset_voices} | {vid for _, vid in preset_voices}

    results: list[dict] = []
    for item in items:
        text = str(item.get("text", "")).strip()
        out_path = Path(item["out_path"])
        if not text:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw_voice = str(item.get("voice", "")).strip()
        ref_audio = str(item.get("ref_audio", "")).strip()

        chosen_voice = raw_voice if raw_voice in valid_names else SOUTHERN_VI_DEFAULT_VOICES.get(
            raw_voice.lower(), "Thùy Dung"
        )
        if chosen_voice not in valid_names and preset_voices:
            chosen_voice = preset_voices[0][0]

        t_line = time.perf_counter()
        if ref_audio and Path(ref_audio).is_file():
            audio = engine.infer(text, voice=ref_audio)
        else:
            audio = engine.infer(text, voice=chosen_voice)

        engine.save(audio, str(out_path))
        info = sf.info(str(out_path))
        results.append(
            {
                "id": item.get("id", out_path.stem),
                "lang": "vi",
                "engine": "VieNeu-TTS-v3-Turbo",
                "voice": chosen_voice,
                "out_path": str(out_path),
                "sample_rate": info.samplerate,
                "duration_sec": round(float(info.duration), 3),
                "elapsed_sec": round(time.perf_counter() - t_line, 3),
            }
        )

    try:
        import torch  # type: ignore

        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass

    _ = t0
    return results


def _resolve_hf_snapshot(repo_folder_name: str) -> str | None:
    hub_dir = Path(HF_CACHE_DIR) / "hub" / repo_folder_name / "snapshots"
    if not hub_dir.is_dir():
        return None
    snaps = sorted([d for d in hub_dir.iterdir() if d.is_dir()], key=lambda p: p.stat().st_mtime, reverse=True)
    return str(snaps[0]) if snaps else None


def _run_omnivoice_worker(items: list[dict]) -> list[dict]:
    _configure_offline_env()
    if str(OMNIVOICE_REPO) not in sys.path:
        sys.path.insert(0, str(OMNIVOICE_REPO))

    import numpy as np  # type: ignore
    import soundfile as sf  # type: ignore
    import torch  # type: ignore
    from omnivoice import OmniVoice  # type: ignore

    device_map = "cuda:0" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if torch.cuda.is_available() else torch.float32
    local_snap = _resolve_hf_snapshot("models--k2-fsa--OmniVoice") or "k2-fsa/OmniVoice"

    model = OmniVoice.from_pretrained(
        local_snap,
        device_map=device_map,
        dtype=dtype,
    )

    results: list[dict] = []
    for item in items:
        text = str(item.get("text", "")).strip()
        out_path = Path(item["out_path"])
        if not text:
            continue
        out_path.parent.mkdir(parents=True, exist_ok=True)
        raw_voice = str(item.get("voice", "")).strip()
        ref_audio = str(item.get("ref_audio", "")).strip()
        ref_text = str(item.get("ref_text", "")).strip()

        instruct = _sanitize_omnivoice_instruct(raw_voice)

        t_line = time.perf_counter()
        if ref_audio and Path(ref_audio).is_file():
            kwargs = {"text": text, "ref_audio": ref_audio, "num_step": 24}
            if ref_text:
                kwargs["ref_text"] = ref_text
            wav_list = model.generate(**kwargs)
        else:
            wav_list = model.generate(text=text, instruct=instruct, num_step=24)

        wav = np.asarray(wav_list[0], dtype=np.float32).reshape(-1)
        sf.write(str(out_path), wav, 24000, subtype="PCM_16")
        dur = round(len(wav) / 24000.0, 3)
        results.append(
            {
                "id": item.get("id", out_path.stem),
                "lang": "en",
                "engine": "OmniVoice-fp16",
                "voice": instruct,
                "out_path": str(out_path),
                "sample_rate": 24000,
                "duration_sec": dur,
                "elapsed_sec": round(time.perf_counter() - t_line, 3),
            }
        )

    if torch.cuda.is_available():
        del model
        torch.cuda.empty_cache()

    return results


def _dispatch_worker_subprocess(python_exe: Path, worker_name: str, items: list[dict]) -> list[dict]:
    if not python_exe.is_file():
        raise FileNotFoundError(f"TTS Python runtime missing for {worker_name}: {python_exe}")

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf_in:
        json.dump(items, tf_in, ensure_ascii=False, indent=2)
        in_json = Path(tf_in.name)
    out_json = in_json.with_suffix(".out.json")

    env = os.environ.copy()
    env["HF_HOME"] = HF_CACHE_DIR
    env["HUGGINGFACE_HUB_CACHE"] = str(Path(HF_CACHE_DIR) / "hub")
    env["HF_HUB_OFFLINE"] = "1"
    env["TRANSFORMERS_OFFLINE"] = "1"
    env["HF_HUB_DISABLE_TELEMETRY"] = "1"
    env["PYTHONUTF8"] = "1"

    try:
        cmd = [
            str(python_exe),
            str(Path(__file__).resolve()),
            "--internal-worker",
            worker_name,
            "--batch-json",
            str(in_json),
            "--report-json",
            str(out_json),
        ]
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        if proc.returncode != 0:
            err_tail = "\n".join((proc.stderr or proc.stdout).splitlines()[-15:])
            raise RuntimeError(f"{worker_name} exited with {proc.returncode}: {err_tail}")
        if not out_json.is_file():
            raise RuntimeError(f"{worker_name} did not produce {out_json}")
        return json.loads(out_json.read_text(encoding="utf-8"))
    finally:
        in_json.unlink(missing_ok=True)
        out_json.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Sequential Local TTS Synthesizer (VieNeu-TTS + OmniVoice)")
    parser.add_argument("--lang", default="vi", choices=["vi", "en"], help="Language for single-line mode")
    parser.add_argument("--text", default="", help="Text to synthesize in single-line mode")
    parser.add_argument("--voice", default="", help="Voice name or instruct string")
    parser.add_argument("--ref-audio", default="", help="Optional reference audio path for zero-shot cloning")
    parser.add_argument("--ref-text", default="", help="Optional reference transcript")
    parser.add_argument("--out", default="", help="Output .wav path for single-line mode")
    parser.add_argument("--batch-json", default="", help="Path to JSON list of {id, lang, text, voice, out_path}")
    parser.add_argument("--report-json", default="", help="Optional output path for synthesis report JSON")
    parser.add_argument("--internal-worker", default="", choices=["", "vieneu", "omnivoice"])
    args = parser.parse_args()

    if args.internal_worker:
        items = json.loads(Path(args.batch_json).read_text(encoding="utf-8"))
        res = _run_vieneu_worker(items) if args.internal_worker == "vieneu" else _run_omnivoice_worker(items)
        if args.report_json:
            Path(args.report_json).write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[TTS_WORKER_OK] {json.dumps(res, ensure_ascii=False)}")
        return 0

    if args.batch_json:
        raw_loaded = json.loads(Path(args.batch_json).read_text(encoding="utf-8"))
        items = raw_loaded.get("items", raw_loaded) if isinstance(raw_loaded, dict) else raw_loaded
    else:
        if not args.text.strip() or not args.out.strip():
            raise SystemExit("Either --batch-json or both --text and --out must be provided.")
        items = [
            {
                "id": Path(args.out).stem,
                "lang": args.lang,
                "text": args.text.strip(),
                "voice": args.voice.strip(),
                "ref_audio": args.ref_audio.strip(),
                "ref_text": args.ref_text.strip(),
                "out_path": str(Path(args.out).resolve()),
            }
        ]

    vi_items = [it for it in items if str(it.get("lang", "vi")).lower().startswith("vi")]
    en_items = [it for it in items if not str(it.get("lang", "vi")).lower().startswith("vi")]

    all_results: list[dict] = []
    if vi_items:
        all_results.extend(_dispatch_worker_subprocess(VIENEU_PYTHON, "vieneu", vi_items))
    if en_items:
        all_results.extend(_dispatch_worker_subprocess(OMNIVOICE_PYTHON, "omnivoice", en_items))

    summary = {"ok": True, "count": len(all_results), "items": all_results}
    if args.report_json:
        Path(args.report_json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[LOCAL_TTS_OK] {json.dumps(summary, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
