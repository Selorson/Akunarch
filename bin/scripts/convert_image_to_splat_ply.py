#!/usr/bin/env python3
"""
Akunarch Phase 2 — Local GPU BYOA Landscape Image -> 3D Gaussian Splat (.ply) Converter
=======================================================================================
Converts an imported 2D landscape / concept art plate (.png/.jpg/.webp) into:
  1. A binary little-endian 3D Gaussian Splatting `.ply` compatible 1:1 with
     `@sparkjsdev/spark` (`SparkRenderer` + `SplatMesh`, Three.js Y-up coordinates).
  2. An optional 8-bit grayscale depth map `.png` (`--depth-png`) for Manga / VFX plates.

Runs 100% offline on local GPU (`RTX 4080` CUDA within < 1.5 GB VRAM, Zero-OOM) via
PyTorch tensor operations:
  - Atmospheric Dark-Channel Haze Transmission (aerial perspective depth cue)
  - Perspective Ground-to-Horizon Elevation Curve + Automatic Sky Dome Segmentation
  - Multi-scale Luminance & Warm/Cool Chromatic Depth Relief
  - Edge-Preserving Joint Bilateral Filtering on GPU to keep cliff/architectural
    silhouettes crisp without rubber-sheet stretching
  - Surface-normal tangent quaternion alignment (`rot_0..3 = w, x, y, z`) and
    anisotropic disk footprints (`scale_0..2 = ln(sx), ln(sy), ln(sz)`)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from pathlib import Path

import cv2
import numpy as np
import torch
import torch.nn.functional as F

SH_C0 = 0.28209479177387814


def compute_gpu_landscape_depth(rgb_np: np.ndarray, device: torch.device) -> torch.Tensor:
    """
    Estimate normalized metric-like depth in [0.05 .. 1.0] (0.05 = closest foreground,
    1.0 = far horizon / sky dome) on GPU using multi-cue aerial perspective + bilateral
    edge preservation.
    """
    h, w, _ = rgb_np.shape
    img = torch.from_numpy(rgb_np).to(device=device, dtype=torch.float32) / 255.0  # [H, W, 3]
    chw = img.permute(2, 0, 1).unsqueeze(0)  # [1, 3, H, W]

    # 1. Vertical perspective ground-to-horizon prior (v=0 top -> far, v=1 bottom -> near)
    v_lin = torch.linspace(0.0, 1.0, h, device=device).view(1, 1, h, 1).expand(1, 1, h, w)
    ground_depth_prior = torch.pow(1.0 - v_lin, 1.28)  # 1.0 at top, 0.0 at bottom

    # 2. Atmospheric Dark-Channel Haze cue (He et al.): distant regions carry higher min-RGB veil
    pad = 7
    min_rgb, _ = torch.min(chw, dim=1, keepdim=True)  # [1, 1, H, W]
    dark_channel = -F.max_pool2d(-min_rgb, kernel_size=2 * pad + 1, stride=1, padding=pad)
    # Estimate atmospheric light from top 20% brightest dark-channel pixels in upper half
    upper_h = max(8, h // 2)
    flat_upper = dark_channel[:, :, :upper_h, :].reshape(-1)
    top_k = max(16, flat_upper.numel() // 20)
    atmos_val = torch.topk(flat_upper, top_k).values.mean().clamp(0.35, 0.98)
    haze_depth = (dark_channel / atmos_val).clamp(0.0, 1.0)

    # 3. Chromatic warmth + local micro-relief (foreground tends warmer & higher micro-contrast)
    r_ch, g_ch, b_ch = chw[:, 0:1], chw[:, 1:2], chw[:, 2:3]
    luma = 0.299 * r_ch + 0.587 * g_ch + 0.114 * b_ch
    coolness = ((b_ch - r_ch) * 0.5 + 0.5).clamp(0.0, 1.0)

    gx = luma[:, :, :, 1:] - luma[:, :, :, :-1]
    gy = luma[:, :, 1:, :] - luma[:, :, :-1, :]
    gx = F.pad(gx, (0, 1, 0, 0))
    gy = F.pad(gy, (0, 0, 0, 1))
    grad_mag = torch.sqrt(gx * gx + gy * gy + 1e-6)
    local_detail = F.avg_pool2d(grad_mag, kernel_size=9, stride=1, padding=4)
    local_detail = (local_detail / (local_detail.max().clamp(min=1e-4))).clamp(0.0, 1.0)

    # Sky mask: upper region, bright/cool, low high-frequency texture
    sky_vertical = ((0.62 - v_lin) / 0.62).clamp(0.0, 1.0)
    sky_bright = ((luma - 0.52) / 0.35).clamp(0.0, 1.0)
    sky_smooth = (1.0 - local_detail * 2.2).clamp(0.0, 1.0)
    sky_mask = (sky_vertical * sky_bright * sky_smooth).clamp(0.0, 1.0)

    # Multi-scale elevation relief from luminance shading
    blur_coarse = F.avg_pool2d(luma, kernel_size=25, stride=1, padding=12)
    relief_band = (luma - blur_coarse) * 0.35

    raw_depth = (
        0.50 * ground_depth_prior
        + 0.28 * haze_depth
        + 0.14 * coolness
        + 0.08 * (1.0 - local_detail)
        - 0.10 * relief_band
    )
    raw_depth = torch.lerp(raw_depth, torch.ones_like(raw_depth) * 0.98, sky_mask)
    raw_depth = raw_depth.clamp(0.05, 1.0)

    # 4. Edge-Preserving Joint Bilateral Filter on GPU (prevents bleeding across silhouettes)
    radius = 4
    sigma_space = 2.6
    sigma_color = 0.095
    filtered_num = torch.zeros_like(raw_depth)
    filtered_den = torch.zeros_like(raw_depth)

    padded_depth = F.pad(raw_depth, (radius, radius, radius, radius), mode="replicate")
    padded_guide = F.pad(chw, (radius, radius, radius, radius), mode="replicate")

    for dy in range(-radius, radius + 1):
        for dx in range(-radius, radius + 1):
            spatial_w = math.exp(-(dx * dx + dy * dy) / (2.0 * sigma_space * sigma_space))
            ys = dy + radius
            xs = dx + radius
            nb_depth = padded_depth[:, :, ys : ys + h, xs : xs + w]
            nb_guide = padded_guide[:, :, ys : ys + h, xs : xs + w]
            color_diff2 = torch.sum((nb_guide - chw) ** 2, dim=1, keepdim=True)
            range_w = torch.exp(-color_diff2 / (2.0 * sigma_color * sigma_color))
            w_total = spatial_w * range_w
            filtered_num += w_total * nb_depth
            filtered_den += w_total

    smooth_depth = (filtered_num / filtered_den.clamp(min=1e-6)).squeeze(0).squeeze(0)
    return smooth_depth.clamp(0.05, 1.0)


def normals_to_quaternions_wxyz(normals: torch.Tensor) -> torch.Tensor:
    """
    Convert unit normals [H, W, 3] in Three.js Y-up space to unit quaternions [H, W, 4]
    in (w, x, y, z) order that rotate the local +Z axis (0, 0, 1) onto `normals`,
    so scale_0 & scale_1 span the tangent plane and scale_2 is thin along the normal!
    """
    nx = normals[..., 0]
    ny = normals[..., 1]
    nz = normals[..., 2]

    # Shortest-arc quaternion from z_axis=(0,0,1) to n=(nx, ny, nz):
    # q = normalize([1 + nz, -ny, nx, 0]), handling antipodal nz ~ -1 cleanly
    w = 1.0 + nz
    x = -ny
    y = nx
    z = torch.zeros_like(nx)

    antipodal = w < 1e-4
    w = torch.where(antipodal, torch.zeros_like(w), w)
    x = torch.where(antipodal, torch.ones_like(x), x)
    y = torch.where(antipodal, torch.zeros_like(y), y)

    quat = torch.stack([w, x, y, z], dim=-1)
    norm = torch.linalg.norm(quat, dim=-1, keepdim=True).clamp(min=1e-7)
    return quat / norm


def convert_image_to_splat_ply(
    input_image: Path,
    output_ply: Path,
    depth_png: Path | None = None,
    max_splats: int = 160_000,
    world_span: float = 96.0,
    relief_scale: float = 28.0,
    base_elevation: float = 4.0,
) -> dict:
    t0 = time.perf_counter()
    if not input_image.is_file():
        raise FileNotFoundError(f"Input image does not exist: {input_image}")

    bgr = cv2.imread(str(input_image), cv2.IMREAD_COLOR)
    if bgr is None:
        raise RuntimeError(f"OpenCV failed to decode image: {input_image}")
    rgb_full = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    src_h, src_w, _ = rgb_full.shape

    aspect = src_w / max(src_h, 1)
    grid_h = max(96, int(round(math.sqrt(max_splats / max(aspect, 0.25)))))
    grid_w = max(96, int(round(grid_h * aspect)))
    while grid_w * grid_h > max_splats and grid_w > 96 and grid_h > 96:
        grid_h -= 2
        grid_w = max(96, int(round(grid_h * aspect)))

    rgb_resized = cv2.resize(rgb_full, (grid_w, grid_h), interpolation=cv2.INTER_AREA)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    with torch.no_grad():
        depth_01 = compute_gpu_landscape_depth(rgb_resized, device)  # [H, W] in [0.05..1.0]

        if depth_png is not None:
            depth_png.parent.mkdir(parents=True, exist_ok=True)
            # Near = bright (255), far = dark (15) per ControlNet / Manga depth convention
            inv_depth_u8 = (
                ((1.0 - (depth_01 - 0.05) / 0.95).clamp(0.0, 1.0) * 255.0)
                .to(torch.uint8)
                .cpu()
                .numpy()
            )
            cv2.imwrite(str(depth_png), inv_depth_u8)

        # Build curved 3D amphitheater diorama geometry in Three.js Y-up coordinates:
        #   +X = right, +Y = up, -Z = forward into the landscape
        u = torch.linspace(-1.0, 1.0, grid_w, device=device).view(1, grid_w).expand(grid_h, grid_w)
        v = torch.linspace(1.0, -1.0, grid_h, device=device).view(grid_h, 1).expand(grid_h, grid_w)

        # Horizontal panorama wrap (~115 deg gentle arc) + depth recession
        azim = u * (math.pi * 0.32)
        radial_dist = (0.36 + depth_01 * 0.64) * (world_span * 0.58)
        pos_x = torch.sin(azim) * radial_dist
        pos_z = -torch.cos(azim) * radial_dist + (world_span * 0.34)
        pos_y = (
            base_elevation
            + (v + 0.55) * (world_span * 0.24) * (0.48 + 0.52 * depth_01)
            + (1.0 - depth_01) * (relief_scale * 0.18)
        )

        pts = torch.stack([pos_x, pos_y, pos_z], dim=-1)  # [H, W, 3]

        # Finite-difference tangent vectors for normal & pixel footprint calculation
        dp_du = torch.zeros_like(pts)
        dp_dv = torch.zeros_like(pts)
        dp_du[:, 1:-1] = 0.5 * (pts[:, 2:] - pts[:, :-2])
        dp_du[:, 0] = pts[:, 1] - pts[:, 0]
        dp_du[:, -1] = pts[:, -1] - pts[:, -2]

        dp_dv[1:-1, :] = 0.5 * (pts[:-2, :] - pts[2:, :])
        dp_dv[0, :] = pts[0, :] - pts[1, :]
        dp_dv[-1, :] = pts[-2, :] - pts[-1, :]

        normals = torch.linalg.cross(dp_du, dp_dv, dim=-1)
        n_len = torch.linalg.norm(normals, dim=-1, keepdim=True).clamp(min=1e-6)
        normals = normals / n_len

        quats_wxyz = normals_to_quaternions_wxyz(normals)  # [H, W, 4]

        step_u = torch.linalg.norm(dp_du, dim=-1)
        step_v = torch.linalg.norm(dp_dv, dim=-1)

        # Detect silhouette depth jumps so boundary splats don't stretch into flying ribbons
        dz_u = torch.zeros_like(depth_01)
        dz_v = torch.zeros_like(depth_01)
        dz_u[:, 1:] = torch.abs(depth_01[:, 1:] - depth_01[:, :-1])
        dz_v[1:, :] = torch.abs(depth_01[1:, :] - depth_01[:-1, :])
        depth_jump = torch.maximum(dz_u, dz_v)

        base_step = float(world_span) / float(max(grid_w, grid_h))
        sx = (step_u * 0.82).clamp(min=base_step * 0.35, max=base_step * 2.8)
        sy = (step_v * 0.82).clamp(min=base_step * 0.35, max=base_step * 2.8)
        sz = (0.16 * torch.minimum(sx, sy)).clamp(min=0.008, max=0.25)

        log_scales = torch.log(torch.stack([sx, sy, sz], dim=-1))

        # High opacity on continuous surfaces, softly feathered on steep silhouette jumps
        alpha = torch.where(
            depth_jump > 0.085,
            torch.full_like(depth_01, 0.72),
            torch.full_like(depth_01, 0.978),
        )
        logit_opacity = torch.log(alpha / (1.0 - alpha)).unsqueeze(-1)

        rgb_t = torch.from_numpy(rgb_resized).to(device=device, dtype=torch.float32) / 255.0
        f_dc = (rgb_t - 0.5) / SH_C0
        luma_fg = 0.299 * rgb_t[..., 0] + 0.587 * rgb_t[..., 1] + 0.114 * rgb_t[..., 2]

        full_grid_vertices = torch.cat(
            [
                pts,           # x, y, z (3)
                log_scales,    # scale_0, scale_1, scale_2 (3)
                quats_wxyz,    # rot_0(w), rot_1(x), rot_2(y), rot_3(z) (4)
                logit_opacity, # opacity (1)
                f_dc,          # f_dc_0, f_dc_1, f_dc_2 (3)
            ],
            dim=-1,
        )
        fg_mask = luma_fg > 0.075
        if int(fg_mask.sum().item()) >= 4096:
            vertex_tensor = full_grid_vertices[fg_mask]
        else:
            vertex_tensor = full_grid_vertices.reshape(-1, 14)

        vram_peak_mb = (
            round(torch.cuda.max_memory_allocated(device) / (1024 * 1024), 2)
            if device.type == "cuda"
            else 0.0
        )
        vertices_np = np.ascontiguousarray(vertex_tensor.cpu().numpy(), dtype="<f4")

    if device.type == "cuda":
        torch.cuda.empty_cache()

    num_splats = int(vertices_np.shape[0])
    header = (
        "ply\n"
        "format binary_little_endian 1.0\n"
        f"element vertex {num_splats}\n"
        "property float x\n"
        "property float y\n"
        "property float z\n"
        "property float scale_0\n"
        "property float scale_1\n"
        "property float scale_2\n"
        "property float rot_0\n"
        "property float rot_1\n"
        "property float rot_2\n"
        "property float rot_3\n"
        "property float opacity\n"
        "property float f_dc_0\n"
        "property float f_dc_1\n"
        "property float f_dc_2\n"
        "end_header\n"
    ).encode("ascii")

    output_ply.parent.mkdir(parents=True, exist_ok=True)
    with open(output_ply, "wb") as fp:
        fp.write(header)
        fp.write(vertices_np.tobytes())

    elapsed_s = round(time.perf_counter() - t0, 3)
    meta = {
        "input_image": str(input_image),
        "output_ply": str(output_ply),
        "depth_png": str(depth_png) if depth_png else None,
        "source_resolution": [src_w, src_h],
        "splat_grid": [grid_w, grid_h],
        "num_splats": num_splats,
        "file_size_bytes": int(output_ply.stat().st_size),
        "world_span_m": world_span,
        "relief_scale_m": relief_scale,
        "device": str(device),
        "vram_peak_mb": vram_peak_mb,
        "elapsed_sec": elapsed_s,
    }
    meta_path = output_ply.with_suffix(output_ply.suffix + ".meta.json")
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return meta


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Convert a landscape image into a 3D Gaussian Splat (.ply) on local GPU"
    )
    parser.add_argument("--input", required=True, help="Path to source image (.png/.jpg/.webp)")
    parser.add_argument("--output", required=True, help="Path to output binary 3DGS .ply")
    parser.add_argument("--depth-png", default="", help="Optional path to output depth map .png")
    parser.add_argument("--max-splats", type=int, default=160000, help="Maximum splat count")
    parser.add_argument("--world-span", type=float, default=96.0, help="Horizontal world span (m)")
    parser.add_argument("--relief-scale", type=float, default=28.0, help="Depth relief scale (m)")
    parser.add_argument("--base-elevation", type=float, default=4.0, help="Base Y elevation (m)")
    args = parser.parse_args()

    meta = convert_image_to_splat_ply(
        input_image=Path(args.input),
        output_ply=Path(args.output),
        depth_png=Path(args.depth_png) if args.depth_png.strip() else None,
        max_splats=max(10_000, min(args.max_splats, 600_000)),
        world_span=args.world_span,
        relief_scale=args.relief_scale,
        base_elevation=args.base_elevation,
    )
    print(f"[IMAGE_TO_SPLAT_OK] {json.dumps(meta, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
