# Walkthrough — đợt ComfyUI riêng (2026-11-14, Claude)

- **Anh dùng:** bấm đúp `ComfyUI riêng` trên Desktop → trang ComfyUI ở 127.0.0.1:8189. Đóng cửa sổ đen = tắt. Hướng dẫn: [`docs/ops/HUONG_DAN_COMFYUI.md`](../ops/HUONG_DAN_COMFYUI.md).
- **Hai bản:** Akunarch `E:\Akunarch\repos\ComfyUI` (8188, giữ sạch) và riêng `D:\ComfyUI-Rieng` (8189, có Manager). Chung kho `D:\AI-Models`.
- **Nhường card hai chiều:** hàng đợi Akunarch giữ job khi 8189 bật (`gpu_queue.rs`, test `queue_holds_jobs_while_personal_comfyui_is_on`); lối tắt chờ khi 8188 hoặc Blender đang chạy.
- **App:** `akunarch.exe` SHA `8d16a586…`, acceptance 6/6, Rust 33/33.
- **Kiểm thật:** job #69 bị giữ khi bản riêng bật, chạy xong khi tắt.
- **Chưa làm / chờ anh:** chọn model tải thêm (mục 5 hướng dẫn); H3 chưa chạy thử; dựng sẵn chế độ App cho việc hay dùng (nếu anh muốn).
