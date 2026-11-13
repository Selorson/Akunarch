# Walkthrough tổng — Kế hoạch VRAM v2 (Đợt A → B → C)

> Ngày: 2026-11-13 · Goal: [`goal_dot_BC.txt`](goal_dot_BC.txt) · Kế hoạch: [`implementation_plan.md`](implementation_plan.md) · Chi tiết từng đợt: [`walkthrough_dot_A.md`](walkthrough_dot_A.md), [`walkthrough_dot_B.md`](walkthrough_dot_B.md) · Sổ tiến độ và mọi quyết định: [`ledger_dot_BC.md`](ledger_dot_BC.md)
> **Trạng thái: ĐÃ HOT-SWAP cả 2 app, đã nghiệm thu ở chế độ người dùng thật. Kết thúc.**

## 1. Kết luận ngắn

- **Đạt:** cold boot không tạo context WebGL nào. Đứng yên thì GPU về P8 / ~1%. Không còn mất context hay cảnh báo "Too many contexts". Lần bật 3D thứ 30 lên hình trong 0,63 s. VRAM tab 01 khi bật 3D giảm từ 484 MB xuống 261 MB (54% của A0). Topbar đo đúng VRAM của app (lệch 0,4 MB so với script đo).
- **KHÔNG ĐẠT (3 chỉ tiêu):** S2 ≤ 40% A0 (đạt 54%); S4 "sau ⏹ + 300 ms ≤ S1 + 20 MB" (269 MB so với 127 MB); S5 Selorson "sau khi rời ≤ trước + 20 MB" (+62 MB; bản cũ là +264 MB).
- **Chưa kiểm:** phần đi WASD trong Thế giới mở của Selorson, vì Selorson local chưa có ô chunk nào. Chi tiết ở mục 5.

## 2. Bảng A0 → A → B → C (trung vị; C = 3 lượt trên bản đã hot-swap)

Đơn vị là VRAM App (PDH, cây tiến trình, LUID RTX 4080). A0 = bản cài cũ `c1498e8a`. A = bản Đợt A. B = bản trung gian có KTX2 (chưa có Chờ 2D). C = bản cài mới `129827ac`. Mỗi kịch bản A0/A chỉ đo 1 lần (xem walkthrough A, mục 8.1).

| # | Kịch bản | A0 | A | B | **C (trung vị 3 lượt)** | Chỉ tiêu | Kết quả |
|---|---|---|---|---|---|---|---|
| 0 | Nền máy, app tắt (GPU / P-state) | 6,3% · P8 | 3,0% · P8 | — | **1,0% · P8** | (tham chiếu) | — |
| 1 | Cold boot 10 s | 484 MB · 1 context · GPU app 13% | 451 MB · 1 context | — | **106,8 MB · 0 context · 0 canvas** (102,4 / 106,8 / 106,9) | 0 context WebGL; ≤ nền WebView2 + 15 MB | ✅ ĐẠT — 0 context ở cả 3 lượt; 106,8 MB thấp hơn nền WebView2 sau khi tháo 3D đo ở A (199,9 MB)* |
| 2 | 3D temple, xoay 3 s, đứng yên 10 s | 484 MB · GPU app 15% · P5 | 426 MB · 0% · P2 | 297 MB (temple KTX2) | **261,1 MB · GPU máy 1,0% · P8** (229 / 262 / 261) | GPU ≤ nền + 2 điểm, pstate như nền; ≤ 60% A0 (sau A); ≤ 40% A0 (sau B) | ✅ GPU (1,0% so với nền 1,0%, P8) · ✅ ≤ 60% (đạt 54%) · ❌ **KHÔNG ĐẠT ≤ 40%** (cần ≤ 194 MB) |
| 3 | 10 dự án × tab 01→02→03→01, 3 vòng | V1 4.845 → V3 3.835 MB · **75 context mất** | 690 → 636 MB · 0 mất | — | **V1 425,6 → V3 444,2 MB** · 1 context · 0 mất · 0 "Too many" | V3 ≤ V1 + 30 MB; 0 mất; 0 cảnh báo | ✅ ĐẠT theo trung vị (+18,6 MB; từng lượt +17 / **+58** / −30; 1/3 lượt vượt) |
| 4 | ⏹ + 300 ms → 🧹 → ▶/⏹ 30 lần | (dạng A) 4.052 MB sau khi rời · lần 30: 3,4 s · 105 mất | 200 MB · 0,29 s · 0 mất | — | **sau ⏹ + 300 ms: 269,1 MB** · sau 🧹: 202,3 MB · lần 30: **0,63 s** (đã nạp xong .glb) · 0 mất | sau ⏹ + 300 ms ≤ S1 + 20 MB (126,8); lần 30 ≤ 1,5 s; 0 mất | ❌ **KHÔNG ĐẠT** mức VRAM · ✅ 0,63 s · ✅ 0 mất |
| 5 | Selorson Admin: /world → 3D 30 s → /stories, chờ 3 s | trước 118,8 → trong 335,1 → **sau 382,9 MB (+264,1)** | — | — | trước 119,8 → trong 334,9 → **sau 181,2 MB (+61,8)** · 0 mất | sau ≤ trước + 20 MB | ❌ **KHÔNG ĐẠT** (giảm được 202 MB so với bản cũ) · ⚠️ đo trên Sa bàn 3D, không phải Thế giới mở WASD |

\* Chỉ tiêu S1 ghi "baseline nền WebView2" nhưng kế hoạch không định nghĩa con số này. Em so với mức nền WebView2 đo được ở A (tab 00 sau khi tháo 3D, 199,9 MB) và ghi rõ ở đây, không tự đặt con số mới.

Số liệu gốc: `scenarios_c3_r{1,2,3}.json`, `scenarios_c3_s5_r{1,2,3}.json`, `scenarios_a0_s5_r{1,2,3}.json`, `measurements.csv`; script tổng hợp [`summarize_c3.py`](summarize_c3.py).

## 3. Vì sao 3 mục KHÔNG ĐẠT (đã đo, không đoán)

1. **S2 ≤ 40%:** đã nén texture KTX2 BC7 (cùng một bản build, chỉ đổi .glb: 427–511 → 252–280 MB). Phần còn lại khoảng 100 MB là nền WebView2 (cold boot 2D là 106,8 MB, không có WebGL). Thêm shadow map 1536², render target MSAA HDR, bloom và 50 texture BC7 (~70 MB). Muốn xuống ≤ 194 MB phải giảm tiếp: shadow, bloom, hoặc độ phân giải texture (ví dụ 2K → 1K). Việc này đổi chất lượng hình nên em không tự làm.
2. **S4 sau ⏹:** sau ⏹ renderer chỉ còn 3 geometry, 2 texture, 5 program, tức app đã trả gần hết tài nguyên của mình. VRAM vẫn cao hơn S1 khoảng 160 MB lúc +300 ms và 95 MB sau 🧹, rồi giảm dần. Phần chênh nằm ở context WebGL dùng chung và bộ nhớ GPU process mà Chromium trả chậm. Theo nguyên tắc #1 của kế hoạch (một renderer, **không bao giờ** `loseContext`), context được giữ sống có chủ đích, nên không thể về đúng mức 0 context của S1.
3. **S5 Selorson:** chẩn đoán qua CDP cho thấy sau khi rời `/world` và ép GC, **canvas quả cầu (1352×776) vẫn còn sống** ngoài DOM. Threlte gọi `renderer.dispose()` trước khi dispose các `<T>`, nên three không xóa được buffer GL. Đã sửa (`WorldCanvas.svelte`: dọn cache texture/geo ngay, hoãn dispose thật sang macrotask kế tiếp, thu canvas về 1×1). Kết quả giảm từ **+264 → +62 MB**. Phần còn lại là chính context vẫn bị một tham chiếu JS giữ. Em đã lưu heap snapshot nhưng chưa tìm ra retainer trong thời gian cho phép (mục 7).

## 4. Ảnh đối chiếu

| Nội dung | Ảnh |
|---|---|
| Cold boot Chờ 2D (bản đã cài) | `screenshots/c3_r1/S1_cold_boot.png` |
| KTX2 vs JPEG, cùng build, cùng góc (4 kỳ quan, khung + cận cảnh) | `screenshots/ktx_ab_jpeg/SK_*.png` ↔ `screenshots/ktx_ab_ktx/SK_*.png`, ghép sẵn `screenshots/ktx_ab_ktx/CMP_*.png` (sai khác 0,2–1,0/255) |
| Ảnh xem trước Blender đặt cạnh concept gốc (Luật #7) | `screenshots/preview_cards/CMP_all.png` |
| Tab 03 Camera Rig: bản cũ / lỗi nền Đợt A / đã sửa | `screenshots/b0_old/B0_tab03_rig3d.png` · `screenshots/b0_new/…` · `screenshots/b0_fix/…` |
| Chụp Manga 2K 3 tab (beauty + depth) với .glb KTX2 | `screenshots/b0_ktx/B0_tab0{1,2,3}_*_{beauty,depth}.png` |
| Ultra (853×681) / Thước / Lưới | `screenshots/b0_fix/B0_tab01_{ultra,grid_off,wireframe_on}.png` |
| Selorson trước khi vào / trong Sa bàn 3D / sau khi rời | `screenshots/c3_s5_r1/S5_*.png` |

## 5. Chưa kiểm / lệch so với kế hoạch

- **S5 phần "Thế giới mở WASD 30 s":** Selorson local có **0 ô chunk** ("Ô bản đồ đã nạp: 0" ở cả Akunalia và Trái Đất). Muốn có chunk phải đồng bộ từ Akunarch rồi **duyệt bản nháp trong Admin**, tức là ghi và xuất bản dữ liệu thật của anh, nên em không tự làm. S5 được đo thay bằng Bản đồ 3D Sa bàn (Threlte). Mã sửa cho Thế giới mở (sessionToken, dọn sâu, dừng rAF khi mở VN) có test tĩnh, nhưng **chưa chạy thật**.
- **Cột B** chỉ có S2 (đo trên bản trung gian), vì theo goal gộp B và C được làm liền mạch, không có bản "chỉ B" để chạy đủ 5 kịch bản.
- **Fog tab 03 không bù ACES** (chỉ bù màu nền). Ảnh hưởng nhỏ ở vùng xa.
- **Thẻ Chờ 2D:** khi tên các cụm dài (Avalon 6 cụm), khung thông tin che khá nhiều ảnh preview. Chỉ là CSS; em không build và hot-swap thêm một lần nữa chỉ vì việc này.
- `static/basis/` (transcoder Basis) đã chép theo kế hoạch nhưng **hiện không dùng**: bản runtime là BC7 giải mã sẵn, vì transcoder cần `'unsafe-eval'` mà CSP không cho (mục B3 trong walkthrough B).
- File `.glb` runtime trên đĩa lớn hơn khoảng 3–4× (BC7 + zstd). Bản gốc nằm ở `_master`.
- Các phát hiện ngoài phạm vi ở mục 0.3 của kế hoạch: **không sửa**.

## 6. File đã thay đổi

**Akunarch (Đợt B + C).** Danh sách Đợt B đầy đủ ở [`walkthrough_dot_B.md` mục 5](walkthrough_dot_B.md). Thêm ở Đợt C:

| File | Nội dung |
|---|---|
| **[NEW]** `app/ui/src/lib/webgl/stage-mode.svelte.ts` | `stageMode = { pbr3d: false, chunk3d: false }` (Q2: Chờ 2D mặc định), giữ suốt phiên, về 2D khi nhận `akunarch:release-webgl-vram` |
| `RealPbrStageViewport.svelte` | Thẻ `pbr-2d-standby-card` (preview › Manga › concept, xem nhanh concept, danh sách cụm); `activate-3d-stage-btn` / `deactivate-3d-stage-btn`; nút "Tạo ảnh xem trước"; tự gọi `projects_ensure_preview_card` khi mở dự án |
| `OpenWorldChunkWorkbench.svelte` | `chunk-2d-standby-card`, `activate-chunk-3d-btn` / `deactivate-chunk-3d-btn` |
| `VnDirectorStagePanel.svelte` | Rig3d về play khi có yêu cầu nhường VRAM |
| `ProjectsStagePanel.svelte`, `ipc.ts`, `types.ts` | `previewRenderPath`, `projectsEnsurePreviewCard`, `preview_render_path` |
| `app/src-tauri/src/projects.rs` | `ClockworkConfig.preview_render_path` (`#[serde(default)]`) |
| `app/src-tauri/src/gpu_queue.rs`, `lib.rs` | Mode `render_preview_card` (Blender đọc `_master`, ghi manifest); `preview_card_path` / `preview_card_needed` (+ test); lệnh `projects_ensure_preview_card` (không trùng job, không chạy khi rescan) |
| **[NEW]** `bin/scripts/render_glb_preview_card.py` | Blender 5.2, Cycles OptiX, 40 mm, 3/4, nền `#090d16`, 1920×1080 |
| **[NEW]** `app/ui/tests/standby-2d.test.mjs` (5), `run-preview-cards.mjs`, `vram-selorson-s5.mjs`; `vram-scenarios.mjs` (S1 đếm context, S4 dạng ⏹/▶, `--swap-master`, TB) | Test và driver đo |
| Dữ liệu | 4 ảnh `clockwork/<slug>_preview_1080p.png` + `preview_render_path` trong manifest (render qua GpuJobQueue, job #4–#7). Sao lưu trước đó: `_archive/vram_dot_C/before_preview_cards/` |

**Selorson V3 (`E:\Selorson\frontend-v3`).** Bản gốc mọi file đã sửa: `E:\Akunarch\_archive\vram_dot_C\selorson_src_original\` (kèm `SHA256SUMS.txt`).

| File | Nội dung |
|---|---|
| **[NEW]** `src/lib/world/engine/webgl-dispose.ts` + `tests/webgl-dispose.test.mjs` (6) | Chép API A1 (không import chéo repo) |
| **[NEW]** `src/lib/world/engine/disposable-cache.ts` + `tests/disposable-cache.test.mjs` (4) | Cache Promise purge được (dispose đồng bộ mục đã xong, mục đang nạp dispose khi về) |
| `textures.svelte.ts`, `geo-data.svelte.ts` | `purgeWorldTextureCache()`, `purgePlanetGeoCache()` |
| `WorldCanvas.svelte` | Purge trong `renderer.dispose`; hoãn dispose thật sang macrotask; thu canvas 1×1; `renderLists.dispose()` |
| `ui/WorldOpenRealm.svelte` + `tests/world-open-realm-vram.test.mjs` (3) | sessionToken cho `.glb`/splat; dọn sâu cảnh trước `renderer.dispose()`; nhả audio + draco; thu canvas 1×1 rồi gỡ; dừng hẳn rAF khi mở VN |
| (không đổi) `GlobeScene.svelte`, `quality.ts`, backend | Theo kế hoạch. Terrain Selorson dùng vertex color nên không có texture terrain để cache |

## 7. Kiểm thử cuối (đều xanh trước và sau hot-swap)

| Repo | Lệnh | Kết quả |
|---|---|---|
| Akunarch | `cargo test` | 25 pass, 1 ignored (có sẵn) |
| Akunarch | `npm run check` / `npm run build` / `npm test` | 0 lỗi 0 cảnh báo / OK / **39/39** |
| Selorson frontend-v3 | `npm run check` / `npm run build` / `npm run test:runtime` | 0 lỗi 0 cảnh báo / OK / **91/91** |
| Selorson backend-v3 | `cargo test` | 58 + 27 pass. Cần Postgres portable `E:\PostgreSQL` (lần đầu lỗi `PoolTimedOut` vì Postgres tắt từ lúc anh tắt máy gấp; đã tự phục hồi WAL bình thường) |

Việc nên làm tiếp (không thuộc lượt này): tìm retainer giữ canvas Sa bàn ở Selorson. Heap snapshot của lượt chẩn đoán còn nằm ở thư mục scratchpad của phiên này (tạm, có thể đã bị dọn). Muốn lặp lại thì chạy `node app/ui/tests/vram-selorson-s5.mjs --gc true --snapshot <file>`.

## 8. Hot-swap & cách quay lại bản cũ

| App | Bản trước | Bản đang cài | File sao lưu |
|---|---|---|---|
| Akunarch | `c1498e8a…` | `129827ac…` | `C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe.bak-20261113-1825` (bản gốc cũng còn ở `E:\Akunarch\app\src-tauri\target\release\akunarch.exe` và `E:\Akunarch\_archive\vram_dot_A\`) |
| Selorson Admin | `f8b60134…` (gốc) → `9720abdb…` (lần 1) | `a170fbe6…` (lần 2, có sửa WorldCanvas) | `C:\Users\Admin\AppData\Local\Selorson Admin\app.exe.bak-20261113-1825` (**bản gốc**), `…\app.exe.bak-20261113-1901` (bản lần 1) |

Quay lại bản cũ: tắt app → xóa `akunarch.exe` (hoặc `app.exe`) → chép file `.bak-20261113-1825` tương ứng thành tên cũ. Cả hai bản mới đã mở thử ở chế độ người dùng thật và khởi động bình thường.

Dữ liệu có thể khôi phục:
- `.glb` gốc: `clockwork\_master\` và `E:\Akunarch\_archive\vram_dot_B\glb_originals\` (SHA-256 trong `SHA256SUMS.txt`).
- File trùng Q4: `E:\Akunarch\_archive\vram_dot_B\q4_duplicate\`.
- Manifest/DB trước khi tạo ảnh preview: `E:\Akunarch\_archive\vram_dot_C\before_preview_cards\`.
- Mọi lượt đo có ghi dữ liệu đều được sao lưu, khôi phục và so khớp SHA-256 100% (`_archive\vram_dot_B\data_backup_*`).

## 9. Bổ sung sau nghiệm thu (2026-11-13, tối) — 2 việc cần thiết

### 9.1 Selorson: hết rò VRAM cộng dồn khi vào/ra Bản đồ 3D
Đo đường cong 5 lần vào/ra (Sa bàn 3D → `/stories`) trên bản trước đó: **181 → 247 → 332 → 406 → 464 MB**. Mỗi lần giữ thêm khoảng 70 MB và thêm một context WebGL; sau khoảng 16 lần Chromium sẽ bắt đầu giết context. Heap snapshot (CDP) tìm ra **2 chuỗi giữ** canvas cùng context WebGL:

1. **Svelte 5 `untracked_writes`** (đã kiểm 5.55.5 và 5.57.3): ở tầng ngoài cùng, mảng này không bao giờ được xoá, nên giữ các derived của Threlte, rồi tới Map context, rồi tới `{canvas, renderer…}`. Sửa: **[NEW]** `engine/threlte-context-release.ts` + `ThrelteContextRelease.svelte` (đặt trong `<Canvas>`). Sau khi renderer dispose xong, xoá tham chiếu object/hàm trong giá trị context.
2. **three r185 `OrbitControls`**: `disconnect()` gỡ listener `keydown` trên `domElement.getRootNode()`, nhưng lúc đó Svelte đã tháo DOM nên `getRootNode()` là chính div. Listener trên `document` ở lại mãi. Sửa: **[NEW]** `engine/orbit-controls-release.ts`, gọi từ `GlobeScene` và `JourneyScene` khi scene huỷ.
3. Kèm theo: `WorldCanvas` dọn sâu mọi `Scene` đã render trước khi dispose thật.

Test mới (đỏ trước rồi xanh): `threlte-context-release.test.mjs` (2), `orbit-controls-release.test.mjs` (2), `disposable-cache.test.mjs` (+1). Selorson `test:runtime` **96/96**, check 0 lỗi 0 cảnh báo.

**Kết quả trên bản đã cài** (`app.exe` 98e807d8):

| | Trước khi sửa | Sau khi sửa |
|---|---|---|
| Đường cong 5 lần vào/ra (MB, đo 3 s sau khi rời) | 181 → 247 → 332 → 406 → 464 | **177 → 175 → 174 → 174 → 122** (không cộng dồn) |
| Canvas còn sống sau khi ép GC | 5 | **0** |
| VRAM sau khi GC | 401 MB | **70 MB** (thấp hơn lúc trước khi vào: ~115 MB) |
| S5 theo chỉ tiêu (3 s sau khi rời, trung vị 3 lượt) | +61,8 MB | **+62,1 MB → vẫn KHÔNG ĐẠT** mốc +20 MB: context cũ chờ GC (V8 không biết áp lực VRAM nên chưa thu hồi ngay), nhưng nay luôn được thu hồi và không tích luỹ |

### 9.2 Akunarch: khung thông tin thẻ Chờ 2D gọn lại
Danh sách cụm tối đa 2 dòng (rê chuột xem đủ), khung hẹp lại (tối đa 56% / 420 px), nên ảnh xem trước lộ rõ (`screenshots/css_check/S1_cold_boot.png`). Kiểm nhanh trên bản đã cài (`scenarios_c3b_r1.json`): S1 cold boot 0 context · S2 228,7 MB ở P8 · ⏹/▶ hoạt động.

### 9.3 Hot-swap lần 3 (20:13) — file sao lưu cập nhật
| App | Đang cài | Sao lưu |
|---|---|---|
| Akunarch | `ef4da65c…` | `akunarch.exe.bak-20261113-2013` (bản 129827ac nghiệm thu ở mục 2) · **`akunarch.exe.bak-20261113-1825` = bản gốc** |
| Selorson Admin | `98e807d8…` | `app.exe.bak-20261113-2013` (a170fbe6) · `app.exe.bak-20261113-1901` (9720abdb) · **`app.exe.bak-20261113-1825` = bản gốc** |
