# Nghiên cứu các repo trong `E:\Akunarch\repos` (2026-11-13, Claude)

> Câu hỏi của anh: có tận dụng được không (TRELLIS, ComfyUI…)? Để AI dựng 3D rồi em hoặc Antigravity chỉnh lại có được không?

## 1. Tóm tắt từng repo

| Repo | Là gì | Trạng thái trên máy | Dùng cho Akunarch |
|---|---|---|---|
| **ComfyUI** (2 bản: `repos\ComfyUI`, `D:\Git-repo\ComfyUI`) | Nền tảng chạy các model sinh ảnh theo sơ đồ node | Chỉ có mã. **Chưa có model nào** (`D:\AI-Models` trống) | ★★★ Tự tạo **ảnh concept**, ảnh tham chiếu từng bộ phận, texture, phóng to ảnh, depth map, mà không phải chờ anh |
| **TRELLIS** (Microsoft, MIT) | Ảnh → 3D: lưới có texture, Gaussian, radiance field | Chỉ có mã (cập nhật 2026-10-27). Chưa có môi trường, chưa có model | ★★ Nặn **cấu kiện hữu cơ đơn lẻ** (tượng, đầu thú, rương, xe thồ, thuyền, gốc cây) đẹp hơn Hunyuan3D-2mini đang dùng |
| **WorldGen** | Chữ hoặc ảnh → cảnh 3D 360° (Gaussian splat) | Chỉ có mã | ★ Phông xa cho vùng khám phá (đúng quyết định "splat chỉ làm phông xa"). Để sau |
| **Image2Splat** | Ảnh → splat | Có mã, ý tưởng đã dùng trong `convert_image_to_splat_ply.py` | Đang dùng |
| **OmniVoice**, **VieNeu-TTS** | Giọng đọc | Có model trong `D:\hf-cache` | Đang dùng (VN, phim) |
| **storytold**: `materialcraft`, `effectcraft`, `filmcraft`, `craft-libs`, `texturecraft`, `artcraft`, `spark` | Bộ công cụ Rust: vật liệu, hiệu ứng, dựng phim | 4 CLI đã biên dịch trong `bin\`. `texturecraft`, `artcraft` chưa dùng | Đang dùng một phần |
| **3DTilesRendererJS**, **spark** | Thư viện hiển thị trên web | Dùng qua npm | Đang dùng |
| **ToneForge** (15 GB), **Tools-3D** (6 GB) | Dự án nhạc; dây chuyền Hunyuan3D | Đang chạy | Đang dùng |

## 2. TRELLIS: điểm mạnh và điểm vướng

- **Mạnh:** từ một ảnh ra lưới 3D có texture, chất lượng hình khối thường tốt hơn Hunyuan3D-2mini (bản rút gọn em đang dùng). Giấy phép MIT, dùng thương mại được.
- **Vướng 1, hệ điều hành:** Microsoft chỉ kiểm trên **Linux**. Windows "chưa kiểm đủ", phải tự biên dịch `spconv`, `kaolin`, `nvdiffrast`, `flash-attn`, rất dễ hỏng. **Cách khả thi nhất:** chạy trong **WSL2 (Ubuntu trên Windows)**.
- **Vướng 2, VRAM:** yêu cầu ≥ 16 GB. RTX 4080 vừa đúng 16 GB nên sát ngưỡng. Khi chạy phải tắt mọi thứ khác dùng GPU (hàng đợi `GpuJobQueue` đã lo việc này).
- **Vướng 3, model:** phải tải từ HuggingFace (vài GB) và cần anh cho phép tải.
- **Theo Luật #7:** chỉ dùng cho cấu kiện điêu khắc đơn lẻ. **Không** dùng cho khung kiến trúc (tháp, đền, nhà), vì khung phải dựng đúng bố cục bằng script như Tháp Eryndor.

## 3. ComfyUI: đòn bẩy lớn nhất

Có ComfyUI cùng model sinh ảnh thì:
- Em hoặc Antigravity **tự tạo ảnh concept** (bản cơ khí, mặt cắt, 4 góc nhìn, bộ phận rời), anh chỉ cần duyệt.
- Tạo **ảnh tham chiếu sạch nền** cho TRELLIS hoặc Hunyuan nặn từng bộ phận.
- Tạo **texture** riêng (đá, gỗ, đồng), **phóng to** ảnh và **depth map** cho Phông nền Manga.

**Model em đề xuất, xét theo giấy phép thương mại:**

| Model | Giấy phép | Dung lượng / ghi chú |
|---|---|---|
| FLUX.1-schnell | Apache-2.0, dùng thương mại được | Khoảng 12 GB bản fp8 |
| SDXL | OpenRAIL++ | Khoảng 7 GB |
| ~~FLUX.1-dev~~ | Cấm dùng thương mại | Không dùng |

## 4. Quy trình "AI dựng thô → em hoặc Antigravity chỉnh" (trả lời câu anh hỏi)

1. **ComfyUI** tạo ảnh concept hoặc ảnh bộ phận. Anh duyệt ảnh.
2. **Khung kiến trúc:** dựng bằng script Blender đúng bố cục, như Tháp Eryndor.
3. **Bộ phận hữu cơ:** TRELLIS hoặc Hunyuan nặn từ ảnh bộ phận.
4. **Em hoặc Antigravity chỉnh bằng Blender Python:**
   - dọn lưới (`pymeshlab`), giảm số tam giác;
   - chỉnh tỷ lệ, xoay, đặt đúng chỗ, ghép vào khung;
   - gán vật liệu PBR thật, nướng AO;
   - đặt cạnh concept để soát theo vòng ở `KINH_NGHIEM.md`, mục 3.
5. **Giới hạn:** agent chỉnh hình học, vật liệu và bố cục rất tốt, nhưng **không "nặn tay" nghệ thuật** như một họa sĩ 3D. Muốn chi tiết điêu khắc đẹp thì cần ảnh tham chiếu đẹp và model nặn tốt. Đó là lý do ComfyUI cùng TRELLIS đáng đầu tư.

## 5. Thứ tự đề xuất (mỗi bước cần anh đồng ý vì phải tải model)

1. **ComfyUI + FLUX.1-schnell (fp8):** tải khoảng 12–17 GB vào `D:\AI-Models`. Thử: tự tạo 3 ảnh concept cơ khí của Eryndor rồi để anh duyệt.
2. **TRELLIS trong WSL2:** cần bật WSL2 (thay đổi hệ thống, anh tự bật hoặc cho phép), cài Ubuntu, tải model (vài GB). Thử: nặn cùng một ảnh tham chiếu bằng TRELLIS và Hunyuan rồi so kết quả.
3. **WorldGen:** để sau, khi bắt đầu dựng vùng khám phá.
