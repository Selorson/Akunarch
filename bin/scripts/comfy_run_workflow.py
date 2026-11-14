"""
Chạy một workflow ComfyUI dạng API (xuất từ giao diện bằng app.graphToPrompt) và chép file đầu ra.

Gọi qua hàng đợi của app: gpu_enqueue(slug, 'comfyui', {mode: 'comfy_workflow', workflow, out_dir, image, image_node, set}).
Chạy tay:
  E:\\Akunarch\\repos\\ComfyUI\\.venv\\Scripts\\python.exe comfy_run_workflow.py --workflow <api.json> --out-dir <thư mục>
      [--image <ảnh> --image-node 122] [--set 316.value=true --set 6.text="..."] [--prefix ten] [--timeout 1800]

Máy chủ ComfyUI chưa chạy thì tự bật (127.0.0.1:8188, kho model D:\\AI-Models), xong việc thì xả VRAM (/free) và tắt
— đúng luật 1 model một lúc của GpuJobQueue. Dòng cuối stdout: `OUTPUT=<file đầu ra chính>`.
"""

from __future__ import annotations

import argparse
import copy
import json
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

COMFY_DIR = Path(r"E:\Akunarch\repos\ComfyUI")
COMFY_PY = COMFY_DIR / ".venv" / "Scripts" / "python.exe"
BASE = "http://127.0.0.1:8188"


def apply_sets(wf: dict, sets: list[str]) -> dict:
    """`node.input=value`: value đọc theo JSON (true, 4096, "chuỗi"), không phải JSON thì giữ nguyên chuỗi."""
    out = copy.deepcopy(wf)
    for item in sets:
        key, _, raw = item.partition("=")
        node, _, field = key.partition(".")
        if node not in out:
            raise KeyError(f"Workflow không có node '{node}' (đặt {item}).")
        try:
            val = json.loads(raw)
        except json.JSONDecodeError:
            val = raw
        out[node]["inputs"][field] = val
    return out


def collect_outputs(history_entry: dict) -> list[dict]:
    """Mọi file kết quả thật (type 'output', bỏ ảnh xem trước 'temp') trong history của một lượt chạy."""
    files = []
    for node_out in history_entry.get("outputs", {}).values():
        for items in node_out.values():
            if isinstance(items, list):
                files += [f for f in items if isinstance(f, dict) and f.get("filename") and f.get("type") == "output"]
    return files


def multipart(field: str, filename: str, data: bytes, extra: dict[str, str]) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in extra.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{field}"; filename="{filename}"\r\n'
                 f'Content-Type: application/octet-stream\r\n\r\n'.encode() + data + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _req(path: str, data: bytes | None = None, ctype: str = "application/json", timeout: float = 30):
    r = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": ctype} if data is not None else {})
    with urllib.request.urlopen(r, timeout=timeout) as resp:
        return resp.read()


def _alive() -> bool:
    try:
        _req("/system_stats", timeout=2)
        return True
    except OSError:
        return False


def start_server(log_path: Path) -> subprocess.Popen:
    log = open(log_path, "w", encoding="utf-8")
    p = subprocess.Popen([str(COMFY_PY), "main.py", "--listen", "127.0.0.1", "--port", "8188", "--disable-auto-launch"],
                         cwd=COMFY_DIR, stdout=log, stderr=subprocess.STDOUT,
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    for _ in range(180):
        if _alive():
            return p
        if p.poll() is not None:
            raise RuntimeError(f"ComfyUI tắt ngay khi khởi động — xem {log_path}")
        time.sleep(1)
    p.kill()
    raise RuntimeError(f"ComfyUI không lên sau 180 s — xem {log_path}")


def run(args) -> list[Path]:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    wf = json.loads(Path(args.workflow).read_text(encoding="utf-8"))
    sets = list(args.set or [])
    log_path = out_dir / f"_comfy_server_{time.strftime('%Y%m%d_%H%M%S')}.log"
    server = None if _alive() else start_server(log_path)
    try:
        if args.image:
            img = Path(args.image)
            body, ctype = multipart("image", img.name, img.read_bytes(), {"overwrite": "true", "type": "input"})
            name = json.loads(_req("/upload/image", body, ctype))["name"]
            sets.append(f"{args.image_node}.image={json.dumps(name)}")
        wf = apply_sets(wf, sets)
        resp = json.loads(_req("/prompt", json.dumps({"prompt": wf, "client_id": uuid.uuid4().hex}).encode()))
        if resp.get("node_errors"):
            raise RuntimeError(f"ComfyUI từ chối workflow: {json.dumps(resp['node_errors'], ensure_ascii=False)[:2000]}")
        pid = resp["prompt_id"]
        deadline = time.time() + args.timeout
        while True:
            hist = json.loads(_req(f"/history/{pid}"))
            if pid in hist and hist[pid].get("status", {}).get("completed") is not None:
                entry = hist[pid]
                break
            if time.time() > deadline:
                raise TimeoutError(f"Workflow chạy quá {args.timeout} s")
            time.sleep(2)
        status = entry.get("status", {})
        if status.get("status_str") != "success":
            msgs = [m for m in status.get("messages", []) if m[0] == "execution_error"]
            raise RuntimeError(f"Workflow lỗi: {json.dumps(msgs, ensure_ascii=False)[:2000]}")
        saved = []
        for f in collect_outputs(entry):
            q = urllib.parse.urlencode({"filename": f["filename"], "subfolder": f.get("subfolder", ""), "type": f["type"]})
            dest = out_dir / f"{args.prefix}_{f['filename']}" if args.prefix else out_dir / f["filename"]
            with urllib.request.urlopen(f"{BASE}/view?{q}", timeout=120) as r, open(dest, "wb") as fh:
                shutil.copyfileobj(r, fh)
            saved.append(dest)
        if not saved:
            raise RuntimeError("Workflow chạy xong nhưng không có file đầu ra.")
        return saved
    except Exception as e:
        if server is not None and log_path.is_file():   # máy chủ do mình bật: kèm đuôi log để biết vì sao chết
            tail = log_path.read_text(encoding="utf-8", errors="replace")[-3000:]
            raise RuntimeError(f"{e}\n--- đuôi log ComfyUI ({log_path.name}) ---\n{tail}") from e
        raise
    finally:
        try:
            _req("/free", json.dumps({"unload_models": True, "free_memory": True}).encode())
        except OSError:
            pass
        if server is not None:
            server.terminate()
            try:
                server.wait(30)
            except subprocess.TimeoutExpired:
                server.kill()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--workflow", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--image")
    ap.add_argument("--image-node", default="122")
    ap.add_argument("--set", action="append")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--timeout", type=int, default=1800)
    saved = run(ap.parse_args())
    for p in saved:
        print(f"SAVED={p}")
    main_out = next((p for p in saved if p.suffix.lower() in (".glb", ".gltf", ".obj", ".ply")), saved[0])
    print(f"OUTPUT={main_out}")


if __name__ == "__main__":
    sys.exit(main())
