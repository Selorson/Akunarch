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

## 7. Vòng 2 (20:15 – 20:50): anh trả lời câu hỏi + model Co-Writer + tải thêm

- **Anh chốt:**
  - H3 cho mọi chuyển cảnh (quay phim, VN, intro);
  - ghi "MiniMax H3" trên giao diện;
  - anh duyệt mọi ảnh tham chiếu (từ FLUX hoặc model khác);
  - thư viện chi tiết nặn để sau;
  - phần thiết lập anh tự nghiên cứu dần;
  - model thêm "em cứ tải".
- **Dùng chung model với Co-Writer:**
  - Z-Image-Turbo và Qwen Image 2.1 bản GGUF đọc thẳng từ Co-Writer, không tải lại (tiết kiệm ~47 GB);
  - cài `ComfyUI-GGUF` + 3 chỗ vá, chỉ ở bản riêng;
  - chạy thật: Z-Image 24 s, Qwen 2.1 67 s.
- **Tải thêm:** SeedVR2 3B, Real-ESRGAN, FILM, Pixal3D multiview, ACE-Step 1.5, Wan 2.2 14B i2v. SeedVR2 đã chạy thật (1024→2048 trong 6 s).
- **Lỗi:**
  - sd.cpp GGUF lệch hình dạng `x_pad_token`;
  - không nhận ra kiến trúc Qwen 2.1;
  - bộ mã hoá chữ thiếu `mmproj` bị nhận thành Flux2.

  Đã vá cả 3, có bản vá lưu lại. Python ghi `\b` làm hỏng đường dẫn trong hướng dẫn, đã sửa và chép bài học vào KINH_NGHIEM.
- **Còn lại:**
  - H3 chạy thử qua hàng đợi (bước đầu của dây chuyền chuyển cảnh);
  - Wan 2.2, ACE-Step, FILM, Real-ESRGAN, Pixal3D multiview chưa chạy thử;
  - Qwen sửa ảnh cần `mmproj` (~1 GB) nếu anh muốn;
  - push GitHub chờ anh.
