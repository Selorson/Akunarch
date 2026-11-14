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
