# Walkthrough — Đợt 0 (Cổng điều khiển `akunarch`) + P0 (Tháp Eryndor)

> Kế hoạch: [`implementation_plan.md`](implementation_plan.md) · Sổ tiến độ: [`ledger.md`](ledger.md)

## Đợt 0 — Cổng điều khiển `akunarch` (2026-11-13) — ĐẠT, đã đăng ký vào Claude Code (✔ Connected)

**Tiêu chí:** em tạo hoặc sửa được dự án, chạy 1 job GPU qua đúng hàng đợi của app và chụp ảnh từ app, không ai bấm tay.

Kiểm qua giao thức MCP thật (`mcp/akunarch-mcp/tests/acceptance.live.mjs`), trên `akunarch.exe` đã cài (SHA `ef4da65c…`, dữ liệu thật, không đặt biến môi trường trỏ dữ liệu):

| Bước | Tool | Kết quả |
|---|---|---|
| 1 | `app_status` | ✅ running, có CDP, SHA khớp |
| 2 | `project_get eryndor-clocktower-concept` | ✅ |
| 3 | `gpu_enqueue` probe → `gpu_wait` | ✅ job #9 `completed` sau 3 s, VRAM đỉnh 1.021 MB. App tự hiện "Đã tạm tắt 3D để nhường VRAM cho tác vụ GPU 'blender' #9" |
| 4 | `ui_open_project` → `ui_screenshot` | ✅ `screenshots/D0_acceptance.png` (543 KB, đúng dự án Eryndor) |

**Test:** `npm test` cho 20 pass, 1 skip (bài live chỉ chạy khi đặt `AKUNARCH_LIVE=1`). Bài live `app.live.test.mjs` 1/1. Mọi test đều đỏ trước khi viết mã và xanh sau đó.

**Mã mới** (`E:\Akunarch\mcp\akunarch-mcp\`): `src/{cdp,app,projects,gpu,ui,cowriter,selorson,server}.mjs`, `tests/*.test.mjs`, `tests/app.live.test.mjs`, `tests/acceptance.live.mjs`, `README.md`. Không sửa mã nào của app Akunarch hay Selorson.

**Còn chờ anh:**
- Đăng ký vào Claude Code: `claude mcp add --scope user akunarch -- node --disable-warning=ExperimentalWarning E:\Akunarch\mcp\akunarch-mcp\src\server.mjs` (đổi cấu hình nên cần anh đồng ý).
- Khai báo cùng lệnh này trong Antigravity.

**Ghi chú vận hành:**
- Nếu anh mở app từ Desktop (không có cổng điều khiển), tool sẽ báo lỗi và không tự tắt app. Đóng app đi là lần gọi sau tự mở lại kèm cổng.
- Sau buổi này app đang mở sẵn **kèm** cổng điều khiển (PID 25760).

**Tồn đọng nhỏ (chưa sửa):**
- Gọi 2 tool song song đúng lúc app đang khởi động thì lệnh thứ 2 báo lỗi. Gọi lại là được.
- Cổng 9241 nhận kết nối từ tiến trình cục bộ khác (trang web thì bị chặn).

**Đánh giá cuối:** em tự soát (không có agent soát riêng), nên yếu hơn một lượt soát độc lập. Anh có thể nhờ Antigravity soát chéo.

## P0 — Tháp Eryndor (đang làm, cập nhật 2026-11-13 khuya)

| Task | Trạng thái | Bằng chứng |
|---|---|---|
| P0.1 Dữ liệu theo canon | ✅ | Trái Đất, region `eryndor`, Co-Writer #499; sao lưu `_archive\p0\before_data_fix\` |
| P0.2 Thiết kế + prompt | ✅ phần em · ⏳ chờ anh | [`eryndor_design.md`](eryndor_design.md) + 4 prompt trong `projects\eryndor-clocktower-concept\concepts\prompts\` (cơ khí 3/4, mặt cắt, 4 góc nhìn, đầu thú) |
| P0.3 Thư viện cơ khí | ✅ | `bin\scripts\clockwork\` — 23 test (bánh răng thân khai, luật "không bánh răng trang trí", ly hợp theo nhịp, onset âm thanh, đường bay camera, xuất .glb 2 clip) |
| P0.4 Tháp bản thật | ✅ v4 (trừ 8 đầu thú) | So concept 4 vòng: `screenshots\CMP_real_v2/v3/v4.png`; 129.940 tam giác; test 5/6 (đầu thú chờ ảnh) |
| P0.5 Đặc tả cơ cấu Eryndor | ⏳ chờ ảnh cơ khí | Động cơ chung đã chạy với cơ cấu mẫu |
| P0.6 Bản cơ khí | ⏳ phần Eryndor · ✅ động cơ + Rust | `assemble_mechanism_glb.py`, mode hàng đợi `assemble_mechanism_glb` |
| P0.7 Phát trong Akunarch | ✅ mã | Công tắc Bản thật/Bản cơ khí + AnimationMixer + hook chụp ảnh |
| P0.8 Video intro | ✅ đường làm video | Thử với cơ cấu mẫu qua hàng đợi: mp4 24 s · 24 fps |
| P0.9 Selorson | ✅ mã (chưa build/đẩy) | Backend nạp riêng gói sa bàn (60/60); frontend tab "⚙ Sa bàn cơ khí" (99/99) |
| P0.10 Nghiệm thu | ⏳ | — |

**5 lỗi CŨ phát hiện và đã sửa trong app** (đều có test đỏ → xanh):
1. Bước KTX2 tự động sau khi dựng luôn hỏng (gọi `powershell` không có đường dẫn).
2. Mỗi lần dựng sinh **bản sao `_`** của file `.glb` và manifest trỏ nhầm sang bản chép.
3. Quá hạn thì chỉ giết tiến trình con, **`ktx.exe` cháu chạy mồ côi đốt CPU** (gây nóng máy).
4. Hạn 900 giây quá ngắn cho KTX2.
5. Ảnh xem trước **cắt mất đỉnh** công trình mảnh-cao.

Thêm: thư viện cũ tự tạo lại thư mục `Selorson/static/world/models` đã gỡ bỏ, làm 1 test Selorson đỏ. Đã gỡ thư mục và chặn tái diễn.

**Hot-swap Akunarch:**

| Lần | Thời điểm | Bản cài | Sao lưu |
|---|---|---|---|
| #1 | 22:43 | `ef4da65c` → `4e8cd438` | `akunarch.exe.bak-20261113-2243` |
| #2 | 23:04 | → `c1dff2fd` | `akunarch.exe.bak-20261113-2304` |

Quay lại bản cũ: tắt app, xoá `akunarch.exe`, chép file `.bak` tương ứng thành `akunarch.exe`.

**Selorson (frontend-v3, backend-v3):** chỉ sửa mã kèm test. Chưa build lại, chưa thay Selorson Admin, chưa commit (anh chưa bảo commit). Em làm các việc đó cùng lúc đẩy bản nháp, khi đã có bản cơ khí.
