# Log lần chạy — 2026-11-14/15 · Claude · Tối ưu RAM/VRAM 6 app + phát hành

| Mục | Nội dung |
|---|---|
| Bắt đầu – kết thúc | `20:55 (14/11)` – `00:55 (15/11)` |
| Kế hoạch / ledger | `docs/toi-uu-tai-nguyen/implementation_plan.md` · `ledger.md` · `walkthrough.md` |
| Mục tiêu lần chạy | Anh nhờ đo và tối ưu RAM/VRAM mọi app; tắt app là tắt hết tiến trình; NeuroForge chỉ điều tra. Sau đó đưa mọi app lên bản mới nhất và phát hành |
| Trạng thái cuối | ✅ ToneForge và Co-Writer đã sửa, đo trước/sau; mọi app tắt sạch; đã phát hành (CI chạy, anh tự theo dõi) |

## 1. Việc đã làm
- Script đo chung + theo dõi NeuroForge bài cuối từ ngoài → `BAO_CAO_NEUROFORGE.md`.
- ToneForge: 14,0 GB RAM / 11,1 GB VRAM giữ mãi → nhả sau 15 s + tắt hẳn. Đã thay exe.
- Co-Writer: 10,8 GB RAM / 3,9 GB VRAM giữ mãi → nhả sau 60 s. Phát hành v1.9.0 (gồm 58 thay đổi đang chạy trên máy).
- Selorson: Sa bàn đạt. Deploy fe/be, desktop Admin 0.1.15.
- Akunarch, ComfyUI riêng: tắt sạch.

| Kiểm | Kết quả |
|---|---|
| Co-Writer pytest | 852/852 |
| ToneForge stem-engine | 12/12 (4 mới) |
| Selorson backend / frontend / svelte-check | 60/60 · 99/99 · 0 lỗi |

## 2. Lỗi gặp & cách xử lý
- Script đo bắt nhầm lệnh của em (dòng lệnh chứa đường dẫn app) → tách dấu hiệu exe / dòng lệnh.
- Tên `runtime` trong adapter Co-Writer trùng biến cục bộ → `import … as onnx_runtime`.
- Test nhả phiên bị bộ đếm 600 s của test khác chiếm → fixture huỷ bộ đếm.
- ToneForge: `get_or_init` không nạp lại sau khi nhả → `IdleSlot` 3 trạng thái.
- ToneForge bản mới 1 lần treo lúc thoát sau 11 phút rảnh → lưới TerminateProcess; kiểm lại sạch.
- Bash không có `bc` → cộng bằng `$(( ))`.

## 3. Quyết định đã tự đưa ra (Ruling)
- Xem `docs/toi-uu-tai-nguyen/ledger.md` (thời gian nhả theo số đo; commit riêng 58 thay đổi Co-Writer; bỏ API admin cũ khi deploy Selorson sau khi kiểm web mới không gọi).

## 4. Việc cần anh chốt
- Có muốn xoá các nhánh `wip/…` đã gộp không (bộ lọc chặn em xoá nhánh trên GitHub).
- Kết quả CI/phát hành: anh tự xem, đỏ thì báo em.

## 5. File / app đã thay đổi
- Akunarch: `bin/scripts/{measure_app_resources,monitor_neuroforge}.ps1`, `bin/scripts/scenarios/*`, `app/ui/tests/toneforge-stem-scenario.mjs`, `docs/toi-uu-tai-nguyen/*`.
- Co-Writer: `local_models/runtime.py`, `providers/adapters/local_onnx.py`, `tests/test_idle_release.py`, `RELEASE_NOTES.md` + commit 58 thay đổi.
- ToneForge: `idle_release.rs` (mới), 4 file bộ tách, `onnx_gpu_runtime.rs`, `shell/src-tauri/src/main.rs`, `ToneForge_Studio.exe`.
- Selorson: gộp `wip` → `main`, nâng version desktop Admin.

## 6. Bài học quy trình mới (đã chép vào KINH_NGHIEM.md?)
- Mục 13 · [x] đã chép
