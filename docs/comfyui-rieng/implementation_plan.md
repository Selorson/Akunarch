# Đợt ComfyUI riêng — kế hoạch (2026-11-14, Claude)

**Anh chốt (2026-11-14):** dùng ComfyUI cả cho Selorson lẫn việc riêng (ảnh, video, nâng cấp ảnh/video, 3D); việc riêng **anh tự bấm hoặc dặn em chạy hộ**; **tách 2 bản cài**; khi anh đang dùng bản riêng thì **hàng đợi Akunarch chờ anh**.

| # | Việc | Kiểm |
|---|---|---|
| T1 | Bản riêng `D:\ComfyUI-Rieng` (clone từ bản Akunarch, venv riêng bằng uv, có ComfyUI-Manager), cổng **8189**, model chung `D:\AI-Models` | `--quick-test-for-ci` đạt; `/object_info` thấy FLUX, TRELLIS.2, H3 |
| T2 | Lối tắt Desktop `ComfyUI riêng.lnk` → `bin\scripts\comfyui_rieng.ps1`: báo nếu Akunarch đang dùng card, bật máy chủ, mở trình duyệt | bấm thử, trang mở ở 127.0.0.1:8189 |
| T3 | Hàng đợi Akunarch giữ job khi bản riêng đang bật (cổng 8189 sống) — TDD trong `gpu_queue.rs` | test đỏ → xanh; `cargo test --lib` đạt |
| T4 | Build + hot-swap `akunarch.exe` | SHA khớp, acceptance 6/6 |
| T5 | Kiểm thật: bật bản riêng → gửi 1 job → job đứng `queued`; tắt → job chạy | trạng thái job đọc qua MCP |
| T6 | Hướng dẫn có ảnh `docs/ops/HUONG_DAN_COMFYUI.md` | anh đọc là dùng được |

Bản Akunarch (`E:\Akunarch\repos\ComfyUI`, cổng 8188) **giữ sạch**: không cài custom node.
