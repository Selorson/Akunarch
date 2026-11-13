"""
Akunarch v2.1 — Single-Prop / Concept Hunyuan3D-2mini Turbo GPU Sculptor (`16GB VRAM` RTX 4080 fp16).

Strictly offline-first against `D:\\hf-cache`:
  - Prepends `E:\\Tools-3D\\Hunyuan3D-2` to `sys.path` so `hy3dgen` never fails to import.
  - Loads cached `tencent/Hunyuan3D-2mini` (`subfolder="hunyuan3d-dit-v2-mini-turbo"`, `fp16` + `enable_flashvdm`).
  - Cleans, prunes floating islands, repairs non-manifold edges, and decimates via `pymeshlab` + `trimesh`.

Usage:
  E:\\Tools-3D\\.venv\\Scripts\\python.exe E:\\Akunarch\\bin\\scripts\\sculpt_concept_to_glb.py \\
      --concept <image_path> --out <out_glb_path> [--octree-res 320] [--steps 12] [--max-faces 24000]
"""

from __future__ import annotations

import argparse
import gc
import os
import sys
import tempfile
import time
from pathlib import Path

os.environ.setdefault("HF_HOME", r"D:\hf-cache")
os.environ.setdefault("HUGGINGFACE_HUB_CACHE", r"D:\hf-cache\hub")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

HUNYUAN_REPO = r"E:\Tools-3D\Hunyuan3D-2"
if HUNYUAN_REPO not in sys.path:
    sys.path.insert(0, HUNYUAN_REPO)


def clean_and_decimate_mesh(raw_mesh, target_faces: int, out_glb: Path) -> tuple[int, int]:
    import numpy as np
    import pymeshlab
    import trimesh

    with tempfile.TemporaryDirectory(prefix="akunarch_hy3d_") as tmp_dir:
        raw_ply = Path(tmp_dir) / "raw_sculpt.ply"
        raw_mesh.export(str(raw_ply))

        ms = pymeshlab.MeshSet()
        ms.load_new_mesh(str(raw_ply))
        ms.meshing_remove_duplicate_vertices()
        ms.meshing_remove_duplicate_faces()
        ms.meshing_remove_unreferenced_vertices()
        ms.meshing_remove_connected_component_by_diameter(
            mincomponentdiag=pymeshlab.PercentageValue(1.8)
        )
        if ms.current_mesh().face_number() > target_faces:
            ms.meshing_decimation_quadric_edge_collapse(
                targetfacenum=target_faces,
                preservenormal=True,
                preservetopology=True,
                optimalplacement=True,
                planarquadric=True,
            )
        ms.meshing_repair_non_manifold_edges()
        ms.compute_normal_per_vertex()

        cm = ms.current_mesh()
        verts = np.array(cm.vertex_matrix(), dtype=np.float32)
        faces = np.array(cm.face_matrix(), dtype=np.int32)

    raw_tm = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    comps = sorted(raw_tm.split(only_watertight=False), key=lambda c: len(c.vertices), reverse=True)
    if len(comps) > 1:
        min_keep_verts = max(36, int(len(comps[0].vertices) * 0.012))
        kept = [c for c in comps if len(c.vertices) >= min_keep_verts]
        raw_tm = trimesh.util.concatenate(kept) if len(kept) > 1 else kept[0]
        verts = np.array(raw_tm.vertices, dtype=np.float32)
        faces = np.array(raw_tm.faces, dtype=np.int32)

    # Center X/Z at 0 and place bottom cleanly at Y = 0, normalized max extent = 1.0
    vmin = verts.min(axis=0)
    vmax = verts.max(axis=0)
    extent = np.maximum(vmax - vmin, 1e-6)
    max_dim = float(extent.max())
    verts[:, 0] = (verts[:, 0] - 0.5 * (vmin[0] + vmax[0])) / max_dim
    verts[:, 2] = (verts[:, 2] - 0.5 * (vmin[2] + vmax[2])) / max_dim
    verts[:, 1] = (verts[:, 1] - vmin[1]) / max_dim

    clean_tm = trimesh.Trimesh(vertices=verts, faces=faces, process=False)
    clean_tm.export(str(out_glb))
    return len(verts), len(faces)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sculpt 3D GLB from 2D Concept Image via offline Hunyuan3D-2mini fp16 + pymeshlab"
    )
    parser.add_argument("--concept", required=True, help="Input 2D concept image path")
    parser.add_argument("--out", required=True, help="Output .glb mesh path")
    parser.add_argument("--octree-res", type=int, default=320, help="Marching cubes octree resolution")
    parser.add_argument("--steps", type=int, default=12, help="Turbo flow-matching inference steps")
    parser.add_argument("--guidance", type=float, default=5.0, help="Guidance scale")
    parser.add_argument("--max-faces", type=int, default=24000, help="Target max triangle count after pymeshlab cleanup")
    parser.add_argument("--seed", type=int, default=2026, help="Deterministic CUDA seed")
    args = parser.parse_args()

    concept_path = Path(args.concept).resolve()
    out_glb = Path(args.out).resolve()
    if not concept_path.is_file():
        raise SystemExit(f"Concept image not found: {concept_path}")
    out_glb.parent.mkdir(parents=True, exist_ok=True)

    import torch
    from PIL import Image
    from rembg import new_session, remove
    from hy3dgen.shapegen import Hunyuan3DDiTFlowMatchingPipeline

    if not torch.cuda.is_available():
        raise SystemExit("CUDA GPU is required for Hunyuan3D-2mini sculpting.")

    t0 = time.time()
    print(
        f"[Akunarch Hunyuan3D-2mini] GPU: {torch.cuda.get_device_name(0)} "
        f"| Cache: {os.environ.get('HF_HOME')} | Concept: {concept_path.name}"
    )

    raw_img = Image.open(concept_path).convert("RGBA")
    rembg_sess = new_session(providers=["CPUExecutionProvider"])
    rgba_cutout = remove(raw_img, session=rembg_sess, bgcolor=[255, 255, 255, 0])

    pipe = Hunyuan3DDiTFlowMatchingPipeline.from_pretrained(
        "tencent/Hunyuan3D-2mini",
        subfolder="hunyuan3d-dit-v2-mini-turbo",
        use_safetensors=True,
        variant="fp16",
        device="cuda",
        dtype=torch.float16,
    )
    pipe.enable_flashvdm(topk_mode="merge")

    gen = torch.Generator(device="cuda").manual_seed(args.seed)
    raw_mesh = pipe(
        image=rgba_cutout,
        num_inference_steps=max(4, min(args.steps, 50)),
        guidance_scale=args.guidance,
        octree_resolution=args.octree_res,
        num_chunks=10000,
        mc_algo="mc",
        generator=gen,
    )[0]

    n_verts, n_faces = clean_and_decimate_mesh(raw_mesh, args.max_faces, out_glb)

    del pipe
    del rembg_sess
    gc.collect()
    torch.cuda.empty_cache()

    elapsed = time.time() - t0
    size_kb = out_glb.stat().st_size / 1024.0
    print(
        f"[AKUNARCH_OK] Sculpted {out_glb.name} | {n_verts} verts / {n_faces} faces "
        f"| {size_kb:.1f} KB in {elapsed:.1f}s"
    )


if __name__ == "__main__":
    main()
