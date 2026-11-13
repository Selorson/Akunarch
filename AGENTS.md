# AGENTS.md — Akunarch (`E:\Akunarch`)

> Tự động nạp cho mọi tác vụ phát triển bên trong `E:\Akunarch` / `E:\Selorson-Ecosystem\Akunarch`.
> Trước khi viết code, **bắt buộc đọc kỹ** hai tài liệu gốc:
> 1. [`E:\Selorson-Ecosystem\AKUNARCH_MASTER_PLAN.md`](file:///E:/Selorson-Ecosystem/AKUNARCH_MASTER_PLAN.md) (`v2.0`) — Đại kế hoạch kiến trúc 6 chặng, triết lý *World-First & Bring-Your-Own-Assets*, và Bộ 6 Kỷ Luật Chống Hình Giả (`Zero-Placeholder Law`).
> 2. [`E:\Selorson-Ecosystem\AGENTS.md`](file:///E:/Selorson-Ecosystem/AGENTS.md) — Quy tắc bất khả xâm phạm toàn hệ sinh thái (`Co-Writer` ↔ `Selorson V3` ↔ `NeuroForge` ↔ `Akunarch`), đặc biệt là Mục `3.1` (`Zero-Rework 3D AAA`).

> **Định hướng `v2.2` (2026-11-13):** đọc Mục 6 của `AKUNARCH_MASTER_PLAN.md`. Tóm tắt:
> - Tác giả không dùng giao diện trực tiếp. Agent thao tác qua MCP `akunarch` (`E:\Akunarch\mcp\akunarch-mcp\`).
> - **Antigravity** dựng phần lớn, **Claude** kiểm tra, sửa, hoàn thiện.
> - Mỗi đợt có `docs\<đợt>\implementation_plan.md` + `ledger.md` + `walkthrough.md`. Làm task nào thì ghi ledger task đó.
> - Mọi cổng duyệt của tác giả phải dừng lại hỏi.
> - P0 (Tháp Eryndor) là mẫu chuẩn cho mọi công trình sau.
> - **Mở phiên:** đọc `docs\ops\KINH_NGHIEM.md` (bài học quy trình) và 5 dòng đầu `docs\ops\NHAT_KY_TONG.md`.
> - **Đóng phiên:** ghi log lần chạy vào `docs\ops\runs\` theo mẫu, rồi cập nhật log tổng.

## 7 Kỷ Luật Sắt Bắt Buộc Tuân Thủ (`v2.1`)

1. **CẤM TUYỆT ĐỐI Khối 3D Vẽ Chay Giả Lập (`Zero Toy Primitives`):**
   - Nghiêm cấm vẽ các hình trụ/hộp/đa giác/hình nón trơn (`CylinderGeometry`, `BoxGeometry`, `OctahedronGeometry`, hay `add_prism_ring` hình nón đặc sơ sài trong Blender) để giả làm công trình, mái vòm, bình gốm hay nhà cửa.
   - Sân khấu 3D chỉ hiển thị **mô hình `.glb` PBR điêu khắc & kiến trúc thật** (`GLTFLoader` + `DRACOLoader` cục bộ + Studio HDRI + Shadow + Selective Bloom), **cảnh Gaussian Splat thật** (`@sparkjsdev/spark`), hoặc **địa hình Heightmap Triplanar thật**. Khi dự án mới chưa có `.glb`, hiển thị **Bàn phóng Ảnh Concept sắc nét** kèm nút đúc 3D / nhập `.glb`.
2. **CẤM Để Trống `E:\Akunarch\projects\` & CẤM Chụp Ảnh Nghiệm Thu Từ `%TEMP%`:**
   - Khi bàn giao `C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe`, thư mục thật `E:\Akunarch\projects\` và DB thật `%LOCALAPPDATA%\Akunarch\akunarch.db` phải có sẵn các dự án thật kèm file `.glb` PBR thật sự nằm trên đĩa.
   - Ảnh chụp nghiệm thu cuối bắt buộc chụp từ `akunarch.exe` mở ở chế độ người dùng bình thường (không gắn biến môi trường trỏ vào `%TEMP%`), đảm bảo tác giả mở `Akunarch.lnk` trên Desktop thấy đúng 100% như ảnh báo cáo.
3. **Hỗ Trợ Xây Thế Giới Trước / Song Song & Kéo-Thả Tài Nguyên Ngoài (`World-First & BYOA`):**
   - Mọi dự án đều hoạt động độc lập kể cả khi chưa gắn `cowriter_key`. Luôn hỗ trợ nhập trực tiếp Ảnh ngoài (`.png/.jpg/.webp`), Mô hình ngoài (`.glb/.spz/.ply`), Nhạc nền ngoài (`.mp3/.wav/.ogg/.flac` từ `FL Studio`), và hỗ trợ xuất ngược **Phông nền Manga 2K (`Beauty + Depth`)** từ góc quay camera 3D.
4. **Stack Đồng Nhất & Bảo Toàn PBR Texture Trong Tauri CSP:**
   - Stack: `Tauri v2 + SvelteKit 5 (Runes: $state, $derived, $effect) + Three.js WebGL2 + @sparkjsdev/spark + 3d-tiles-renderer + SQLite (akunarch.db)`. Không dùng Svelte 4 stores, không nhúng React.
   - Trong `tauri.conf.json`, CSP luôn giữ `blob: data:` cho `connect-src` và `'self' blob:` cho `worker-src` kèm bộ giải mã Draco offline trong `static/draco/`.
5. **Tách Rời Sidecars (`Zero-OOM`), Cache Offline `D:\hf-cache` & Điều Phối `16GB VRAM` (`RTX 4080`):**
   - Các engine nặng (`materialcraft`, `effectcraft`, `filmcraft`, `ToneForge`) biên dịch riêng thành CLI trong `E:\Akunarch\bin\`.
   - Mọi script Python đúc `Hunyuan3D` (`sculpt_concept_to_glb.py`) bắt buộc thêm `sys.path.insert(0, r"E:\Tools-3D\Hunyuan3D-2")`, dùng đúng model đã cache offline tại `D:\hf-cache` (`tencent/Hunyuan3D-2mini`, `subfolder="hunyuan3d-dit-v2-mini-turbo"`, `fp16`) kết hợp làm sạch lưới bằng `pymeshlab`.
   - Mọi tác vụ GPU (`Hunyuan3D`, `Blender 5.2 Cycles OptiX`, `ComfyUI`, `WorldGen`, `VieNeu-TTS / OmniVoice`) đi qua `GpuJobQueue` tuần tự 1-model-tại-1-thời-điểm.
6. **Bảo Vệ `Co-Writer` 100% & Xuất Bản `Draft-First` Sang `Selorson`:**
   - Chỉ mở `%LOCALAPPDATA%\Co-Writer\co_writer.db` ở chế độ `SQLITE_OPEN_READ_ONLY` (`?mode=ro` + `PRAGMA query_only = ON`), không đụng tới `D:\Git-repo\Co-Writer` hay `cowriter-core.exe`.
   - Mọi gói đẩy sang `POST /api/v1/admin/sync/world-studio` mặc định ở trạng thái Nháp (`is_active = false`).
7. **CHUẨN KHỚP BẢN VẼ 1:1 (`Cấm Xào Lại Script Cũ Bị Loại Bỏ & Cấm Nhồi Nhét Sai Thiết Kế`):**
   - **CẤM TUYỆT ĐỐI** gọi lại 12 script lắp ráp cũ bị lỗi trong `E:\Tools-3D\scripts\archived_selorson_monuments\assemble_*.py` (ngoại trừ duy nhất mẫu chuẩn `assemble_temple_zyberon.py` và thư viện vật liệu/nướng AO `_aaa_monument_kit.py`). Mọi script lắp ráp mới phải viết sạch sẽ tại `E:\Akunarch\bin\scripts\monuments\`.
   - **Quy tắc `1 Bản Vẽ = 1 Công Trình Đúng Bố Cục 100%`:** Tuyệt đối không nhồi 2 bản vẽ khác nhau đè lên một cái đĩa tròn phẳng; không bao giờ ném nguyên bức tranh toàn cảnh nhiều nhà cửa/hàng cột vào 1 cục `Hunyuan3D` bị chảy nhão rồi nhét ra mép sau. Chỉ dùng `Hunyuan3D` cho các cấu kiện điêu khắc hữu cơ đơn lẻ (tượng, gốc cây, rương đá, bệ đại bàng, vòm chạm nổi...) giống hệt cách làm `temple-of-zyberon`, còn khung kiến trúc & địa hình phải dựng chuẩn xác 100% theo bố cục, hình khối, cao độ và số lượng hạng mục trên ảnh Concept gốc.
   - Trước khi kết thúc bất kỳ tác vụ đúc 3D nào, bắt buộc mở ảnh Concept gốc đặt cạnh ảnh chụp 3D trong `Akunarch` để tự kiểm định từng chi tiết kiến trúc khớp thiết kế gốc.
