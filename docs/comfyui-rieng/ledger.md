# Ledger — đợt ComfyUI riêng

| Task | Trạng thái | Ghi chú |
|---|---|---|
| T1 | ✅ xong | `D:\ComfyUI-Rieng`: clone cục bộ từ bản Akunarch (cùng commit `eee59185f`, remote về GitHub Comfy-Org), venv uv py3.13 + torch 2.14.1 cu130 (lấy từ cache uv), `comfyui_manager` 4.2.2. Venv 4,4 GB. `/models/*` thấy đủ FLUX, TRELLIS.2, Pixal3D, H3, BiRefNet, MoGe |
| T2 | ✅ xong | `bin\scripts\comfyui_rieng.ps1` (UTF-8 BOM cho PS 5.1) + `Desktop\ComfyUI riêng.lnk` (icon `D:\ComfyUI-Rieng\comfyui-rieng.ico`). Chạy đúng lệnh của lối tắt: máy chủ lên sau 8 s |
| T3 | ✅ xong | `gpu_queue.rs`: `PERSONAL_COMFYUI_URL` + `comfyui_alive()`; job đứng `queued` kèm ghi chú, thử lại sau 5 s; lúc chạy xoá ghi chú. Test `queue_holds_jobs_while_personal_comfyui_is_on` đỏ đúng lý do → xanh. `cargo test --lib` 33/33 (+1 ignored) |
| T4 | ✅ xong | Build release 1 phút 18 s. Hot-swap `akunarch.exe` → SHA `8d16a586…` khớp. Acceptance 6/6. App lúc đó do MCP tự mở khi gọi `gpu_jobs` (cha là node server.mjs), không phải anh → đóng |
| T5 | ✅ xong | Bản riêng bật → job #69 `queued` + "Chờ: ComfyUI riêng của anh đang bật…"; tắt → `completed`, ghi chú rỗng |
| T6 | ✅ xong | `docs/ops/HUONG_DAN_COMFYUI.md` + 3 ảnh `docs/ops/img_comfyui/`. Bảng template chạy được ngay tính từ `index.json` của gói templates đối chiếu `D:\AI-Models` |

**Ruling:** bản riêng ở cổng 8189 (không dùng chung 8188) — để hàng đợi Akunarch phân biệt được "anh đang dùng" với "ComfyUI do chính hàng đợi bật" — cái giá nếu sai: anh mở nhầm 2 tab cổng khác nhau, chỉ là nhầm lẫn nhỏ.
**Ruling:** "anh đang dùng" = cổng 8189 trả lời — chịu được trường hợp cửa sổ bị tắt cứng (không có file khoá bị kẹt) — cái giá nếu sai: trong ~10 s máy chủ đang khởi động, Akunarch vẫn có thể nhận job; lối tắt đã tự chờ Akunarch rảnh mới bật nên khe này rất hẹp.
**Ruling:** việc riêng "em chạy hộ" đi qua hàng đợi trên **bản Akunarch** (chỉ template chính thức) — đúng Luật #5, không cần sửa thêm — cái giá nếu sai: workflow cần node chỉ có ở bản riêng thì phải nối hàng đợi sang bản riêng (chưa làm, làm khi cần).
**Ruling:** không tải thêm model nào — anh chưa chọn; bảng gợi ý ở mục 5 hướng dẫn.

## Vòng 2 (2026-11-14 tối): anh trả lời 4 câu hỏi + "Z-Image/Qwen đã có trong Co-Writer, model thêm em cứ tải"

| Task | Trạng thái | Ghi chú |
|---|---|---|
| T7 | ✅ xong | Ghi quyết định của anh: H3 cho mọi chuyển cảnh (quay phim, VN, intro), ghi credit "MiniMax H3" trên UI, anh duyệt mọi ảnh tham chiếu, thư viện chi tiết nặn để sau → `NGHIEN_CUU_TAI_NGUYEN_SAN_XUAT.md` mục 6 |
| T8 | ✅ xong | Co-Writer có Z-Image-Turbo Q8 GGUF (10,4 GB) + Qwen Image 2.1 Q8 GGUF + Qwen3VL-8B Q4_K_M + VAE (12,5 GB). Bản riêng đọc thẳng qua mục `cowriter:` trong `extra_model_paths.yaml` (chỉ đọc). Cài `ComfyUI-GGUF` (city96, `6ea2651`) **chỉ ở bản riêng** + 3 chỗ vá (bản vá `bin/patches/comfyui-gguf_cowriter-sdcpp.patch`). Chạy thật: Z-Image 24 s, Qwen 2.1 67 s. 2 workflow lưu ở Workflows của bản riêng (bản sao `bin/comfy_workflows/rieng/`) |
| T9 | ✅ xong | Tải thêm (giấy phép đã đọc: Apache-2.0 / BSD-3 / MIT): SeedVR2 3B, Real-ESRGAN, FILM, Pixal3D multiview, ACE-Step 1.5 AIO, Wan 2.2 14B i2v + LoRA 4 bước. SeedVR2 chạy thật bằng template chính thức: 1024→2048 trong 6 s, nét rõ |

**Ruling:** dùng chung GGUF của Co-Writer thay vì tải bản `.safetensors` gốc (tiết kiệm ~47 GB) — anh yêu cầu tránh trùng model — cái giá nếu sai: Co-Writer xoá/đổi model thì 2 workflow hỏng; Qwen chỉ tạo ảnh từ chữ (không sửa ảnh vì thiếu `mmproj`).
**Ruling:** vá trực tiếp node `ComfyUI-GGUF` (3 chỗ, có chú thích "Local addition") thay vì viết node riêng — ít mã nhất, cạnh đúng chỗ vá sd.cpp sẵn có — cái giá nếu sai: cập nhật node bằng Manager sẽ mất vá; đã lưu bản vá để áp lại.
**Ruling:** chạy thử model trên bản riêng (cổng 8189) ngoài hàng đợi Akunarch — lúc 8189 bật, hàng đợi Akunarch tự giữ job, nên vẫn 1 model một lúc đúng tinh thần Luật #5 — cái giá nếu sai: Co-Writer tạo ảnh cùng lúc thì giành card (Co-Writer nằm ngoài cả hai cơ chế).
