# Walkthrough Đợt B — Đo VRAM đúng phần App + Pipeline KTX2

> Ngày: 2026-11-13 · Kế hoạch: [`implementation_plan.md`](implementation_plan.md) mục 4 · Goal: [`goal_dot_BC.txt`](goal_dot_BC.txt) · Sổ tiến độ: [`ledger_dot_BC.md`](ledger_dot_BC.md)
> Theo goal gộp B+C: **không dừng chờ duyệt**, đi tiếp sang C. Chưa hot-swap ở đợt này; exe đang cài giữ nguyên SHA `c1498e8a…` qua mọi lần build (build thử ở `target-dotA`).

## 1. Kết luận ngắn

| Hạng mục | Kết quả |
|---|---|
| B0. Ba việc còn treo từ Đợt A | Chụp Manga 2K ở tab 01/02/03 đều ra đúng kích thước. Thước/Lưới chạy thật. Phát hiện và **sửa 2 lỗi**: nút Ultra không có tác dụng, nền tab 03 bị tối. |
| B1. VRAM của riêng app qua PDH (`windows-sys`) | Chạy được, có 5 test (gồm 1 test đọc PDH thật) |
| B2. Topbar `VRAM App · Máy`, đỉnh VRAM job lấy mẫu mỗi 1 s, nhường VRAM trước job nặng | Xong. Topbar lệch `measure_vram.ps1` **0,4 MB** ✅ (chỉ tiêu ±5% hoặc ±10 MB) |
| B3. KTX2 cho 4 kỳ quan | VRAM App khi bật 3D, cùng một bản build: **427–511 → 252–280 MB (−41 đến −45%)**. Ảnh A/B cùng góc máy sai khác trung bình 0,2–1,0/255 ✅ |
| B4. Kiểm thử | cargo test 25 pass / 1 ignored (có sẵn), npm check 0 lỗi 0 cảnh báo, npm build OK, npm test 39/39 |

## 2. B0 — kiểm thật trên bản `target-dotA` (driver CDP, có sao lưu)

Mỗi lượt sao lưu `project.akun.json` + `manga_plates\` + `stage_vn\` của cả 10 dự án và `akunarch.db` vào `E:\Akunarch\_archive\vram_dot_B\data_backup_<lượt>_meta\`. Sau lượt chạy khôi phục lại: **46 file, SHA-256 khớp 100%** (chạy 5 lượt: b0_old, b0_new, b0_fix, b0_ktx, cộng một lượt chụp tab 03 trên bản cũ).

| Kiểm | Kết quả |
|---|---|
| ⊞ Thước (grid) | Ảnh khác 0,35/255 khi tắt, về đúng 0 khi bật lại ✅ |
| 🕸 Lưới (wireframe) | Khác 4,9/255 khi bật, về 0 khi tắt ✅ |
| 📸 Manga 2K tab 01 | `beauty` + `depth` 2048×1152, đã xem bằng mắt ✅ |
| 📸 Manga 2K tab 02 | 2560×1440 ✅ |
| 📸 Góc máy 2K tab 03 | 2560×1440 ✅ |
| Ultra | ❌ **lỗi** → đã sửa (mục 2.1) |
| Tab 03 trước/sau Đợt A | ❌ **lỗi màu nền** → đã sửa (mục 2.2) |

### 2.1 Lỗi Ultra
Ultra tính `min(devicePixelRatio, 1.5)`. Màn của anh có DPR 1,0, nên Ultra cho ra đúng bằng HD (canvas vẫn 569×454). Ultra giờ luôn siêu lấy mẫu 1,5×: canvas 853×681, ảnh khác HD 1,18/255. Hàm thuần `pbrPixelRatio` có test.

### 2.2 Lỗi nền tab 03 Camera Rig
Đợt A chuyển tab 03 sang composer MSAA. Từ đó màu nền đi qua `OutputPass`, bị tone-map ACES và tối đi: RGB `12,21,34` → `2,6,16`. Lỗi này ảnh hưởng cả **ảnh phông nền VN chụp ra**. Đã sửa bằng hàm thuần `inverseAcesFilmic` (bù ACES ngược cho màu nền), có test khứ hồi sai số < 1/255. Sau sửa, nền về đúng `12,21,34`; ảnh trước/sau Đợt A khác **0,58/255** (trước khi sửa là 9,35). Sương (fog) không bù vì ảnh hưởng rất nhỏ (ghi ở ledger).

Ảnh: `screenshots/b0_old/B0_tab03_rig3d.png` (bản cũ) · `screenshots/b0_new/…` (lỗi) · `screenshots/b0_fix/…` (đã sửa).

## 3. B1–B2 — đo VRAM đúng phần App

- **[NEW]** `app/src-tauri/src/vram_win32.rs`: đọc PDH `GPU Process Memory\Local Usage` + `GPU Adapter Memory\Dedicated Usage`, chọn LUID của GPU rời (Dedicated lớn nhất), chỉ tính `phys_0`. Cây tiến trình lấy từ một snapshot Toolhelp, chia nhóm webview / worker / host. Chạy qua `spawn_blocking`, timeout 1,5 s, lỗi thì trả `available = false`.
- `VramTelemetry` thêm 5 trường có `#[serde(default)]`. `merge_app_vram` tính `other_system_mb = max(0, used − app)`.
- **Sửa P2-2:** trong lúc job chạy, mỗi 1 s lấy mẫu VRAM (`tokio::select!`). Đỉnh toàn máy ghi vào `vram_peak_mb`, đỉnh nhóm worker ghi vào `payload_json.worker_vram_peak_mb` (không đổi schema DB). Đo thật với job Blender render ảnh xem trước: **máy 2.925–3.055 MB, worker 1.974–2.070 MB**. Trước đây cột này chỉ ghi mức nền.
- Trước mỗi job nặng: `GpuJobQueue` gọi callback → `emit("akunarch://gpu-job-starting")` rồi chờ 500 ms. UI phát `akunarch:release-webgl-vram`, các sân khấu về 2D (hoàn chỉnh ở C2).
- Topbar `data-testid="topbar-vram-pill"`: `VRAM App: X MB · Máy: Y / 16376 MB`, tooltip gồm WebView2 / GPU Worker / Windows & app khác / GPU % / °C. 🧹: tháo WebGL → chờ 300 ms → giải phóng ComfyUI → đo lại. `GpuQueuePanel` có thanh kép (phần app màu đồng, phần nền màu xám).

**B4 đối chiếu cùng thời điểm** (`scenarios_b4.json`):

| Trạng thái | Topbar (trung vị 5 mẫu) | `measure_vram.ps1` | Lệch |
|---|---|---|---|
| Chờ 2D | 103 MB | 102,6 MB | +0,4 MB ✅ |
| 3D temple | 268 MB | 267,6 MB | +0,4 MB ✅ |

## 4. B3 — KTX2

### 4.1 Đính chính kế hoạch (quan trọng)
Kế hoạch giả định transcoder Basis của three chạy được với CSP hiện tại. **Sai.** `basis_transcoder.js` (Emscripten embind) gọi `new Function`, cần `'unsafe-eval'`. Đo thật qua CDP thấy lỗi `EvalError … 'unsafe-eval' is not an allowed source`, và temple KTX2 đứng ở màn "Đang nạp" mãi. Em **không nới CSP**. Thay vào đó:

- `optimize_glb_runtime.ps1`: `dedup` + `prune` → UASTC mức 4 (`--jobs 2`) → [`ktx2_to_bc7.mjs`](../../bin/scripts/ktx2_to_bc7.mjs) giải mã sẵn **offline** sang KTX2 **BC7 + zstd**. KTX2Loader nạp thẳng BC7 qua `createRawTexture`, không cần worker transcoder; zstd wasm chỉ cần `'wasm-unsafe-eval'` (đã có).
- Slot màu là `BC7_SRGB`, slot dữ liệu (normal/ORM) là `BC7_UNORM`. Script tự kiểm và báo lỗi nếu sai.
- Bỏ ETC1S: đích cuối đều là BC7, nên ETC1S chỉ làm giảm chất lượng mà không giảm VRAM.
- Đánh đổi: file `.glb` trên đĩa lớn hơn khoảng 3–4×, và chỉ chạy trên GPU có BPTC (Akunarch chỉ chạy Windows desktop, RTX 4080 có BPTC).

### 4.2 Bảng nghiệm thu (cùng bản build, cùng góc máy, chỉ đổi file `.glb`)

| Kỳ quan | Ảnh gốc → KTX2 | File gốc → KTX2 | `renderer.info.textures` | VRAM App bật 3D (JPEG → KTX2) | Sai khác ảnh khung / cận cảnh |
|---|---|---|---|---|---|
| temple-of-zyberon | 36 → 35 | 10,8 → 43,7 MB | 51 → 50 | 462 → **258 MB** | 0,30 / 0,53 |
| singularity-samos-olympus | 46 → 43 | 12,3 → 46,3 MB | 61 → 58 | 511 → **280 MB** | 0,23 / 0,30 |
| singularity-stonehenge-avalon | 33 → 29 | 11,7 → 36,9 MB | 48 → 44 | 427 → **252 MB** | 0,42 / 1,02 |
| avalon-mage-sanctum | 69 → 52 | 13,0 → 33,0 MB | 84 → 67 | 462 → **262 MB** | 0,33 / 0,63 |

Sai khác tính theo |ΔRGB| trung bình trên thang 255. Có 1 lượt Avalon lệch 7,6, nhưng lặp lại KTX2↔KTX2 cũng lệch 7,6 (khung hình chưa ổn định lúc chụp); lượt KTX2 thứ hai so với JPEG chỉ còn 0,33. Hình học được kiểm riêng: cùng hộp bao, cùng 247 node. Số mesh giảm do `dedup` gộp mesh trùng.
Ảnh: `screenshots/ktx_ab_jpeg/SK_*.png` ↔ `screenshots/ktx_ab_ktx/SK_*.png` và `CMP_*.png`. Tab 02 / tab 03 / Manga dùng `.glb` KTX2 cũng khớp bản JPEG (0,05–0,3/255, `screenshots/b0_ktx/`).

### 4.3 An toàn dữ liệu
- Bản gốc: `clockwork\_master\<slug>.glb` (Q3), SHA khớp bản sao lưu ở `E:\Akunarch\_archive\vram_dot_B\glb_originals\`. Script **không bao giờ ghi đè `_master`**: bản xuất mới thì `_master` cũ được chuyển vào `_master\history\`. Bản runtime được thay nguyên tử.
- **Q4:** `temple_of_zyberon.glb` (trùng từng byte, 0 tham chiếu) đã chuyển sang `E:\Akunarch\_archive\vram_dot_B\q4_duplicate\`.
- Blender (Video Intro, Điện ảnh, `hero_glb` khi lắp ráp lại) đọc `_master` qua `blender_source_glb()`. **Đồng bộ Selorson** gửi `_master` cho pack/placements, vì Selorson web/Android không có BC7 và không có KTX2Loader. Có test.
- Sau `sculpt_concept` / `assemble_glb` thành công, hàng đợi tự xếp `optimize_glb_runtime` → `render_preview_card` (`follow_up_jobs`, có test).

### 4.4 Sự cố nhiệt độ CPU
Lượt nén 3 kỳ quan đầu dùng mặc định của gltf-transform (số job bằng số nhân, mỗi `ktx.exe` lại chạy đa luồng). CPU lên khoảng **95°C**, máy cạn tài nguyên, anh phải tắt máy gấp. Đã kiểm sau sự cố: `akunarch.db` integrity `ok`, mọi `project.akun.json` / `episode.json` đọc được, 4 `.glb` header hợp lệ, `_master` khớp SHA, Postgres của Selorson tự phục hồi WAL bình thường. Script nay chạy `--jobs 2`.

## 5. File đã thay đổi (Đợt B)

| File | Nội dung |
|---|---|
| **[NEW]** `app/src-tauri/src/vram_win32.rs` | PDH + Toolhelp, 5 test |
| `app/src-tauri/Cargo.toml` | `windows-sys 0.61` (target windows; có sẵn trong Cargo.lock; không vi phạm test Rule #3) |
| `app/src-tauri/src/gpu_queue.rs` | Trường VRAM App, `merge_app_vram`, `VramPeak`, sampler 1 s, `JobStartNotifier`, `blender_source_glb`, `follow_up_jobs`, mode `optimize_glb_runtime` (+ C2: `render_preview_card`) |
| `app/src-tauri/src/lib.rs` | `mod vram_win32`, `.setup` gắn emit `gpu-job-starting` |
| `app/src-tauri/src/selorson_sync.rs` | Gửi `_master` sang Selorson + test |
| **[NEW]** `app/ui/src/lib/webgl/stage-quality.ts` | `pbrPixelRatio`, `acesFilmic`, `inverseAcesFilmic` |
| **[NEW]** `app/ui/src/lib/webgl/ktx2.ts` | Một KTX2Loader dùng chung theo renderer chung |
| `app/ui/src/lib/webgl/webgl-stage.ts` | `RELEASE_WEBGL_VRAM_EVENT`, `requestWebglVramRelease` |
| `RealPbrStageViewport.svelte`, `OpenWorldChunkWorkbench.svelte`, `VnDirectorStagePanel.svelte` | KTX2Loader; tab 01 Ultra; tab 03 bù ACES nền |
| `+page.svelte`, `GpuQueuePanel.svelte`, `types.ts` | Topbar VRAM App/Máy, 🧹 tháo WebGL, thanh kép, lắng nghe `gpu-job-starting` |
| **[NEW]** `app/ui/static/basis/` | `basis_transcoder.{js,wasm}` (theo kế hoạch; hiện không dùng vì BC7 không cần transcoder) |
| **[NEW]** tests | `stage-quality.test.mjs` (5), `ktx2-runtime.test.mjs` (3) |
| **[NEW]** `bin/scripts/optimize_glb_runtime.ps1`, `bin/scripts/ktx2_to_bc7.mjs` | Pipeline KTX2 BC7 |
| **[NEW]** `bin/tools/ktx-software/` (KTX-Software 4.4.2 chính thức, SHA-256 khớp digest GitHub, chữ ký Khronos hợp lệ), `bin/tools/gltf-transform/` (npm 4.5.1) | Công cụ cục bộ, không vào package.json/Cargo.toml của app |
| `app/ui/tests/vram-scenarios.mjs` | Thêm B0, SK, TB, `--swap-master`, `--wonders` |

## 6. Chưa đạt / chưa kiểm ở Đợt B
- Chỉ tiêu "S2 ≤ 40% baseline A0" sẽ được đo ở C3 (×3, trung vị). Số tham khảo: temple KTX2 bật 3D **258 MB = 53% của A0 (484 MB)** → khả năng cao **KHÔNG ĐẠT** mốc 40%. Phần còn lại phần lớn là nền WebView2 (~100 MB ở chế độ 2D) cộng shadow map và render target.
- Theo goal gộp, B và C được làm liền mạch nên không có bản build "chỉ có B" để chạy đủ 5 kịch bản. Cột "sau B" trong bảng tổng lấy từ các lượt SK/TB ở trên.
