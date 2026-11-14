# Log lần chạy — 2026-11-14 · Claude · ComfyUI riêng cho anh + Akunarch nhường card

| Mục | Nội dung |
|---|---|
| Bắt đầu – kết thúc | `17:30` – `18:35` |
| Kế hoạch / ledger | `docs/comfyui-rieng/implementation_plan.md` · `ledger.md` · `walkthrough.md` |
| Mục tiêu lần chạy | Anh muốn dùng ComfyUI cho cả Selorson lẫn việc riêng, thấy thiết lập quá phức tạp → dựng sẵn + hướng dẫn |
| Trạng thái cuối | ✅ T1–T6 xong. Chờ anh chọn model tải thêm |

## 1. Việc đã làm
- Mở phiên: trình bày đợt trước và việc tiếp theo (từ `NGHIEN_CUU_TAI_NGUYEN_SAN_XUAT.md`).
- Anh chốt: dùng cả hai cách (tự bấm + dặn em), đủ loại việc, **tách 2 bản**, **Akunarch chờ anh**.
- Bản riêng `D:\ComfyUI-Rieng` (8189, Manager 4.2.2, chung `D:\AI-Models`), lối tắt Desktop `ComfyUI riêng`.
- `gpu_queue.rs`: giữ job khi 8189 sống (TDD). Hot-swap `akunarch.exe` `8d16a586…`.
- Hướng dẫn `docs/ops/HUONG_DAN_COMFYUI.md` + 3 ảnh.

| Kiểm | Kết quả |
|---|---|
| Rust `cargo test --lib` | 33/33 (+1 ignored) |
| Acceptance MCP | 6/6 |
| Job thật #69 | giữ khi bản riêng bật → chạy khi tắt |
| Lối tắt Desktop | máy chủ lên sau 8 s |

## 2. Lỗi gặp & cách xử lý
- Bật máy chủ thử lần đầu ghi log sai thư mục tạm → bật lại đúng scratchpad.
- Hot-swap lần 1 trượt vì app đang mở — do MCP tự mở khi em gọi `gpu_jobs`, không phải anh → đóng, làm lại. Bản cài cũ không bị đụng.
- Ảnh chụp Browser pane hay hết giờ (viewport 0×0) → chuyển sang đọc `index.json` của gói templates.
- Python ghi `\r` trong chuỗi thường làm hỏng đường dẫn trong KINH_NGHIEM → sửa byte.

## 3. Quyết định đã tự đưa ra (Ruling)
- Xem `docs/comfyui-rieng/ledger.md` (cổng 8189; phát hiện bằng cổng sống; chạy hộ trên bản Akunarch; chưa tải model).

## 4. Việc cần anh chốt
- Model tải thêm cho việc riêng (bảng mục 5 hướng dẫn; gợi ý đầu: SeedVR2 3B 4 GB + FILM 0,1 GB).
- Có muốn em dựng sẵn chế độ App cho FLUX / TRELLIS / H3 không.
- Push 4 commit lên GitHub `Selorson/Akunarch`.

## 5. File / app đã thay đổi
- Mã: `app/src-tauri/src/gpu_queue.rs`, `bin/scripts/comfyui_rieng.ps1` (mới)
- Ngoài git: `D:\ComfyUI-Rieng\` (bản riêng), `Desktop\ComfyUI riêng.lnk`
- App: `akunarch.exe` → `8d16a586…`
- Tài liệu: `docs/ops/HUONG_DAN_COMFYUI.md`, `docs/ops/img_comfyui/`, `docs/comfyui-rieng/*`, `KINH_NGHIEM.md` mục 12

## 6. Bài học quy trình mới (đã chép vào KINH_NGHIEM.md?)
- Mục 12 · [x] đã chép
