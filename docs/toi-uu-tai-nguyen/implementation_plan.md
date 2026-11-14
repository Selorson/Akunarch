# Đợt tối ưu tài nguyên toàn hệ sinh thái — kế hoạch (2026-11-14, Claude)

**Anh giao (2026-11-14):** mọi app anh làm có dùng RAM/VRAM thì đo và tối ưu. Tắt app là tắt hết tiến trình. NeuroForge chỉ điều tra và báo cáo.

**Lý do:** sau vụ Selorson mở lại bản đồ thì VRAM cộng dồn, anh nhận ra các app chưa được tối ưu.

| App | Mã | Quyền |
|---|---|---|
| Selorson | `E:\Selorson\frontend-v3`, `backend-v3` | sửa → nhánh `wip/…` |
| Akunarch | `E:\Akunarch` | sửa, push main |
| Co-Writer | `D:\Git-repo\Co-Writer` | sửa; thay exe **chỉ khi đo thấy tốt hơn** |
| ToneForge | `F:\FL studio\toneforge` | sửa |
| ComfyUI | `E:\Akunarch\repos\ComfyUI`, `D:\ComfyUI-Rieng` | sửa |
| NeuroForge | `E:\NeuroForge` | **chỉ đọc mã + đọc số liệu tiến trình từ ngoài, báo cáo** |

## Giai đoạn
| # | Việc | Điều kiện |
|---|---|---|
| G1 | Đọc mã từng app: tiến trình con, đường tắt app, tài nguyên GPU/WebGL, cache, listener → danh sách nghi vấn | làm ngay (chỉ đọc) |
| G2 | Script đo chung `bin\scripts\measure_app_resources.ps1`: RAM (private/working set) + VRAM theo cây tiến trình, 4 thời điểm (mở, lặp thao tác, rảnh, **sau tắt**) | viết ngay, **chạy khi anh cho** (máy đang chờ dữ liệu cho NeuroForge) |
| G3 | Đo nền toàn bộ → báo cáo xếp hạng | chờ anh |
| G4 | Sửa theo thứ tự tốn nhất; mỗi sửa có test/kịch bản lặp + số trước/sau | sau G3 |
| G5 | Báo cáo NeuroForge (không sửa) | đọc mã làm ngay; số liệu tiến trình đọc khi anh cho |

Luật đo: không chạy 2 việc nặng cùng lúc; báo anh trước mỗi app sẽ đóng/mở; không đụng tiến trình NeuroForge.
