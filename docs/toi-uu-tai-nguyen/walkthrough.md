# Walkthrough — đợt tối ưu tài nguyên toàn hệ sinh thái (2026-11-14 → 15, Claude)

## Kết quả đo trên máy (RTX 4080 16 GB, 31 GB RAM)

| App | Trước | Sau | Thay đổi |
|---|---|---|---|
| **ToneForge** | 1 lần tách stem 30 s → giữ **14,0 GB RAM + 11,1 GB VRAM** tới khi tắt app | rảnh 15 s → **2,9 GB + 0,49 GB**; đỉnh 10,1 GB VRAM; tắt luôn sạch | `IdleSlot` nhả bộ tách sau 15 s, arena `SameAsRequested`, lưới "tắt là tắt hẳn" (TerminateProcess). **Đã thay `ToneForge_Studio.exe`** |
| **Co-Writer** | 1 lượt tìm → giữ **10,8 GB RAM + 3,9 GB VRAM** tới khi tắt app | rảnh 60 s → **2,9 GB + 0,25 GB** | nhả phiên ONNX khi rảnh (`runtime.touch()`), phát hành **v1.9.0** |
| **Selorson** | Sa bàn từng cộng dồn VRAM | vào/ra 5 lần: 29,9 → 30,5 MB (**đạt**) | (sửa từ đợt VRAM v2) · deploy web + backend, desktop Admin 0.1.15 |
| Akunarch | — | rảnh 344 MB / 10 MB, tắt sạch | không đổi |
| ComfyUI riêng | — | đóng console → 0 python sót | không đổi |
| NeuroForge | — | rảnh ~475 MB, tắt 0 sót | **chỉ báo cáo**: [BAO_CAO_NEUROFORGE.md](BAO_CAO_NEUROFORGE.md) |

**Chọn thời gian nhả theo số đo, không theo cảm tính** (anh gợi ý rút ngắn):
- ToneForge nạp lại ~0,5 s (21,5 s lạnh / 20,8 s nóng / 21,3 s sau khi nhả) → 15 s.
- Co-Writer dựng lại embedder 1,26 s + reranker 0,70 s → 60 s.

## Công cụ để lại
- `bin\scripts\measure_app_resources.ps1 -App <app|all> -Label <nhãn>`: RAM + VRAM theo cây tiến trình, kể cả WebView2 và tiến trình mồ côi. Chỉ đọc.
- `bin\scripts\monitor_neuroforge.ps1`: theo dõi từ ngoài, ưu tiên thấp.
- `bin\scripts\scenarios\cowriter_resources.ps1`, `open_idle_close.ps1`, `app\ui\tests\toneforge-stem-scenario.mjs` (gọi `invoke` của Tauri qua cổng gỡ lỗi WebView2).

## Phát hành (2026-11-15)
- Selorson: fe/be `main` (backend bỏ API admin World Studio/Assets cũ; web mới không gọi chúng), tag `desktop-admin-v0.1.15`.
- Co-Writer: chốt 58 thay đổi đang chạy trên máy (`46f1bcd`), tag `v1.9.0`.
- ToneForge, Akunarch: push `main`.

## Còn lại
- Selorson Thế giới mở: dùng chung một renderer, khi có dữ liệu ô bản đồ (anh chốt để sau).
- Co-Writer: lượt tìm đầu ~12–15 s (không phải do nạp model, chưa điều tra); `sd-server` không tự tắt.
- ToneForge: nguyên nhân gốc lần treo lúc thoát chưa tìm ra (lưới TerminateProcess đã chặn).
- Các nhánh `wip/…` đã gộp vào `main` nhưng chưa xoá (bộ lọc an toàn chặn xoá nhánh trên GitHub).
