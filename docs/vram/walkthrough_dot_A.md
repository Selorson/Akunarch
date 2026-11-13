# Walkthrough Đợt A — "Cầm Máu" VRAM cho Akunarch

> Ngày: 2026-11-13 · Kế hoạch: [`implementation_plan.md`](implementation_plan.md) mục 3 · Trạng thái: **⏸ DỪNG chờ anh duyệt**
> Không sửa Rust · Không hot-swap · Không đụng `E:\Selorson` · Không đụng Co-Writer.

## 1. Kết luận ngắn

| Vấn đề | Trước (bản đang cài) | Sau (bản Đợt A) |
|---|---|---|
| 20 nét điêu khắc ở tab 02 | VRAM app **868 → 5.983 MB** (+5,1 GB), tạo 22 context, mất 6 | **695 → 707 MB** (+12 MB), 1 context, 0 mất |
| Chuyển liên hoàn 10 dự án × 3 tab × 3 vòng | **111 context tạo, 75 bị Chromium giết**, VRAM 3,8–4,8 GB | **1 context, 0 mất**, VRAM 636–690 MB |
| Bật/tắt 3D 30 lần → rời sang tab không 3D | Vẫn giữ **4.052 MB**; lần bật thứ 30 mất 3,4 s | Còn **200 MB**; lần bật thứ 30: 0,29 s* |
| Tab 01 đứng yên sau khi xoay | GPU riêng của app **15,1%**, GPU ở P5 | **0%**, không còn rAF nào |
| Xoay tự động rồi **thu nhỏ cửa sổ** | Vẫn render (WebView2 không báo `hidden`) | GPU riêng của app **7,5% → 0%** |
| VRAM tab 01 đứng yên | 484 MB | 426 MB (**chỉ −12%**, xem mục 4) |

\* xem ghi chú đo ở mục 3.5.

## 2. Phương pháp đo

- **Bản trước:** `C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe` (SHA-256 `c1498e8a…727a`, build 2026-11-12 04:43).
- **Bản sau:** `E:\Akunarch\app\src-tauri\target-dotA\release\akunarch.exe`, build vào **thư mục target riêng**, vì exe đang cài là *hard link* tới `target\release\akunarch.exe` (một lần `cargo build --release` thường có thể vô tình hot-swap). SHA-256 của exe đang cài được kiểm **trước và sau mọi lần build: không đổi**. Bản sao lưu nằm ở `E:\Akunarch\_archive\vram_dot_A\`.
- **Chế độ người dùng thật (Luật #2):** DB `C:\Users\Admin\AppData\Local\Akunarch\akunarch.db`, `E:\Akunarch\projects` (10 dự án), không đặt biến môi trường nào trỏ `%TEMP%`. Chỉ thêm cổng CDP qua `WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS`, giữ nguyên các cờ GPU của `tauri.conf.json`.
- **Công cụ:** [`bin/scripts/measure_vram.ps1`](../../bin/scripts/measure_vram.ps1). Nó đọc PDH `GPU Process Memory` và `GPU Engine` cho cây tiến trình `akunarch.exe`, **lọc theo LUID của RTX 4080** (`0x00010af9`), đồng thời chạy `nvidia-smi -lms 500`. Driver [`app/ui/tests/vram-scenarios.mjs`](../../app/ui/tests/vram-scenarios.mjs) điều khiển app qua CDP và đếm context WebGL bằng cách bọc `getContext`.
- **Dữ liệu thật bị kịch bản điêu khắc ghi vào** (2 ô chunk + DB) được sao lưu trước và khôi phục sau mỗi lượt. Đã kiểm **SHA-256 khớp 100%** (lượt trước 22 file, lượt sau 24 file; số file khác nhau vì DB lúc đó có file `-wal`/`-shm`).
- Số liệu gốc: [`scenarios_baseline.json`](scenarios_baseline.json), [`scenarios_baseline_s3s4.json`](scenarios_baseline_s3s4.json), [`scenarios_baseline_sm.json`](scenarios_baseline_sm.json), [`scenarios_after.json`](scenarios_after.json), [`measurements.csv`](measurements.csv).

## 3. Bảng số liệu theo kịch bản

Cột "App VRAM" là trung vị PDH của cây tiến trình Akunarch. "GPU app" là bộ đếm engine 3D **riêng của app**. "GPU máy" là `nvidia-smi` toàn máy (bị app khác trên máy làm nhiễu, xem 3.6).

### 3.1 S0 — nền máy, Akunarch tắt
| | GPU máy | P-state | Công suất |
|---|---|---|---|
| Lượt trước | 6,3% | P8 | 15,1 W |
| Lượt sau | 3,0% | P8 | 14,2 W |

### 3.2 S1 — Cold boot (bản hiện tại vẫn tự mở tab 01 với 3D; chế độ Chờ 2D thuộc Đợt C)
| | App VRAM | GPU app | Context tạo/mất |
|---|---|---|---|
| Trước | 484,3 MB | 13,07% | 1 / 0 |
| Sau | 451,4 MB | 0,01% | 1 / 0 |

Chỉ tiêu "0 context WebGL lúc cold boot" thuộc Đợt C → **chưa áp dụng**.

### 3.3 S2 — 3D `temple-of-zyberon`, xoay 3 s rồi đứng yên 10 s
| | App VRAM | GPU app | GPU máy | P-state / W |
|---|---|---|---|---|
| Trước | 484,3 MB | 15,07% | 27,7% | P5 / 27,4 W |
| Sau | 425,9 MB | **0,00%** | 19,8% | P2 / 71,7 W |

- ❌ **KHÔNG ĐẠT** "App VRAM ≤ 60% baseline": đạt **88%** (426/484). Nguyên nhân ở mục 4.
- ❌ **KHÔNG ĐẠT theo tiêu chí toàn máy** "GPU máy ≤ nền + 2 điểm": 19,8% so với nền 3,0%. Trong cùng cửa sổ đo, bộ đếm engine riêng của app là **0,00%**, tức tải đến từ tiến trình khác. Em ghi đúng là "không đạt theo tiêu chí đã viết", không tự đổi tiêu chí.

### 3.4 SC — 20 nét điêu khắc liên tiếp ở tab 02 (`chunk-akunalia-0-0`)
| | Sau nét 1 | Sau nét 20 | Chênh | Context tạo/mất | Cảnh báo "Too many contexts" |
|---|---|---|---|---|---|
| Trước | 867,6 MB | **5.983,4 MB** | **+5.115,8 MB** | 22 / 6 | 6 |
| Sau | 695,3 MB | 707,1 MB | **+11,8 MB** ✅ (≤ +30) | 1 / 0 | 0 |

Bằng chứng không dựng lại sân khấu: `webgl-stage.acquires` giữ nguyên **2** từ nét 1 đến nét 20, `renderer.info.memory.textures` giữ nguyên **113** ✅.

### 3.5 S3 — 10 dự án × tab `01 → 02 → 03 (rig3d) → 01`, 3 vòng
| | Cuối vòng 1 | Cuối vòng 3 | Context tạo/mất | "Too many contexts" |
|---|---|---|---|---|
| Trước | 4.845 MB | 3.834 MB | 111 / **75** | 75 |
| Sau | 690 MB | 636 MB ✅ (≤ vòng 1 + 30) | **1 / 0** ✅ | **0** ✅ |

Ở bản trước, VRAM vòng 3 thấp hơn vòng 1 vì Chromium đã **giết** 75 context cũ, không phải vì app tự dọn.

### 3.6 S4 (dạng Đợt A) — bật/tắt sân khấu 3D 30 lần (tab 00 ↔ 01), rồi 🧹 và rời sang tab 00
| | 3D bật sau 30 lần | Sau 🧹 + tab 00 | Lần bật thứ 30 | Context tạo/mất |
|---|---|---|---|---|
| Trước | 4.113 MB | **4.052 MB** | 3.405 ms | 142 / 105 |
| Sau | 462 MB | **200 MB** ✅ | 285 ms* | 1 / 0 ✅ |

\* "Lên hình" ở đây là lúc canvas có mặt và lớp "đang nạp" biến mất, **không phải** lúc `.glb` đã nạp xong (probe ngay sau đó chỉ thấy 4 texture; `.glb` nạp xong trong lúc đo). Cách đo này giống nhau cho cả hai bản. Đợt A chưa có nút `⏹ Ngắt 3D` (thuộc Đợt C), nên "tắt 3D" ở đây là rời tab.

### 3.7 SM — xoay tự động (hoạt ảnh liên tục) rồi thu nhỏ cửa sổ
| | Đang hiện | Thu nhỏ |
|---|---|---|
| Sau | GPU app 7,46% | **0,00%** ✅ |
| Trước | 0,00%** | 8,41% |

\*\* Bộ đếm engine của bản trước dao động mạnh giữa các lượt (cùng kịch bản S2 đo được lúc 15,1%, lúc 3,6%). Bằng chứng chắc chắn hơn cho bản trước là phép thử riêng: thu nhỏ cửa sổ → `document.visibilityState` vẫn `visible`, `requestAnimationFrame` vẫn **60/s**.

### 3.8 S5 — Selorson Admin: **chưa áp dụng** (Đợt C).

## 4. Vì sao VRAM tab 01 chỉ giảm 12% (mục chưa đạt)

Kế hoạch (mục 0.2 P1-1) ước "một nửa VRAM tab 01 là framebuffer". **Ước tính đó sai.** Khung 3D thực tế chỉ khoảng **569×454 px** (canvas cũ 853×681 do ép DPR 1.5), nên toàn bộ framebuffer cũ chỉ khoảng 75 MB. Phần lớn còn lại là **texture JPEG của `.glb`** (temple: 36 ảnh, khoảng 261 MB khi giải nén RGBA8 + mip) cộng phần nền của WebView2 (~200 MB, đo ở S4 sau khi rời tab 3D). Đòn bẩy để đạt chỉ tiêu ≤ 60% là **KTX2 ở Đợt B (B3)**, không phải Đợt A.

## 5. Đã thay đổi gì

| File | Nội dung |
|---|---|
| **[NEW]** `app/ui/src/lib/webgl/dispose.ts` | `disposeMaterialDeep` (mọi thuộc tính texture + uniforms), `disposeObject3DDeep` (geometry/material dùng chung, InstancedMesh, shadow map, SplatMesh, nền/env), `disposeComposer` (dispose từng pass, bắt được UnrealBloomPass), `disposeSparkRenderer` (Spark 0.1.10 không có `dispose()`; không đụng `EMPTY_SPLAT_TEXTURE` tĩnh) |
| **[NEW]** `app/ui/src/lib/webgl/webgl-stage.ts` | Một `WebGLRenderer` + canvas cho cả app (`antialias: false`, `preserveDrawingBuffer: false`). `acquireStage` / `release` chuyển canvas giữa các tab, thu về 1×1, **không bao giờ** `dispose()` / `forceContextLoss()`. `window.__akunarchWebglStage()` để chẩn đoán |
| **[NEW]** `app/ui/src/lib/webgl/on-demand-loop.ts` | `invalidate` / `setContinuous` / `dispose`; `setAllLoopsSuspended` khi cửa sổ thu nhỏ |
| `RealPbrStageViewport.svelte` | Mượn renderer chung; DPR theo màn hình (HD ≤ 1,0 · Ultra ≤ 1,5, nút `HD/Ultra` trên thanh tiêu đề); shadow 1536/2048; composer chỉ còn 1 bộ đệm MSAA (`outputPass.needsSwap = false`, `readBuffer = msaaTarget`, `renderTarget2` 1×1); một hàm dọn duy nhất cho unmount / đổi dự án / nạp muộn / lỗi nạp; render theo nhu cầu |
| `OpenWorldChunkWorkbench.svelte` | three/Spark nạp động; tách 6 effect (sân khấu chỉ theo `activeChunkSlug`; địa hình cập nhật cao độ tại chỗ; cỏ; kỳ quan diff theo `id` + cache `.glb` đếm tham chiếu; vòng nhạc/trigger; splat có token); 4 texture Poly Haven dùng chung cho mọi ô; nút **🌊 Sóng** (mặc định **OFF**) |
| `VnDirectorStagePanel.svelte` | three nạp động trong nhánh `rig3d`; renderer chung + MSAA 4× qua composer (giữ khử răng cưa như `antialias: true` cũ); dọn đầy đủ; `.glb` về muộn thì dọn ngay |
| `+page.svelte` | Poll `nvidia-smi` 4,5 s khi có job hoặc đang ở tab GPU, còn lại 15 s; dừng hẳn khi ẩn/thu nhỏ (qua `getCurrentWindow().isMinimized()` + `onResized`/`onFocusChanged`) |
| **[NEW]** tests | `webgl-dispose.test.mjs` (6), `on-demand-loop.test.mjs` (7), `webgl-static.test.mjs` (5) |
| **[NEW]** đo đạc | `bin/scripts/measure_vram.ps1`, `app/ui/tests/vram-scenarios.mjs` (driver CDP, không thuộc `npm test`) |

## 6. Kiểm thử tự động

| Lệnh | Kết quả |
|---|---|
| `npm test` (app/ui) | **26/26 pass** (8 test cũ + 18 test mới) |
| `npm run check` | 865 file, **0 lỗi, 0 cảnh báo** |
| `npm run build` | OK |
| `cargo test` (target riêng) | **14 pass**, 0 fail, 1 ignored (sẵn trong code) |
| `cargo build --release --features custom-protocol` (target riêng) | OK |

Test được viết **trước** phần cài đặt: `webgl-dispose` và `setAllLoopsSuspended` đều đỏ trước rồi mới xanh.

## 7. Ảnh đối chiếu cùng góc máy

| Kịch bản | Trước | Sau |
|---|---|---|
| Tab 01 temple, explode 0% | `screenshots/baseline/S2_temple_default_view.png` | `screenshots/after/S2_temple_default_view.png` |
| Tab 02 ô [0,0] trước khi điêu khắc | `screenshots/baseline/SC_chunk_0_0_before_sculpt.png` | `screenshots/after/SC_chunk_0_0_before_sculpt.png` |
| Cold boot | `screenshots/baseline/S1_cold_boot.png` | `screenshots/after/S1_cold_boot.png` |

Đã xem trực tiếp từng cặp: hình học, vật liệu PBR, bloom, khử răng cưa, địa hình triplanar, 87.160 splat và ô kề **giống nhau**. Khác biệt nhìn thấy được chỉ là: nút `HD` mới trên thanh tiêu đề tab 01, nút `🌊 Sóng OFF` ở tab 02, và **mặt nước đứng yên theo mặc định**.

## 8. Lệch so với kế hoạch & điều chưa kiểm — anh cần biết

1. **Mỗi kịch bản chỉ đo 1 lần**, không phải 3 lần lấy trung vị như mục 6 của kế hoạch (vì mỗi lượt đầy đủ mất 8–12 phút, và bản cũ bị treo CDP sau kịch bản điêu khắc). Các kết luận về context và rò rỉ chênh lệch hàng GB nên không bị ảnh hưởng. Các con số nhỏ (GPU %) thì có nhiễu.
2. **Đính chính kỹ thuật A4:** chỉ đổi `renderTarget2` sang `samples: 0` (như kế hoạch viết) sẽ làm MSAA nhấp nháy theo khung, vì `OutputPass` hoán đổi buffer mỗi khung. Đã làm theo cách đúng và ghi lại trong plan.
3. **A7 đo được thực tế:** thu nhỏ cửa sổ thì WebView2 **không** báo `hidden`, nên đã dùng API cửa sổ Tauri (quyền `allow-is-minimized` có sẵn trong `core:default`, không sửa `capabilities/`).
4. **Sóng nước mặc định OFF**, là thay đổi hành vi nhìn thấy được. Anh muốn mặc định ON thì chỉ cần đổi `wavesEnabled = $state(true)`; đổi lại thì tab 02 sẽ chạy liên tục khi đang hiện.
5. **Sửa thêm một lỗi có sẵn** ngay chỗ đang làm: các `$effect` `stageApi?.setGridVisible(showGrid)` / `setWireframe` lần đầu không đăng ký phụ thuộc, nên nút Thước/Lưới có thể không tác dụng. Đã sửa bằng cách đọc state trước. **Chưa kiểm bằng thao tác bấm thật.**
6. **Chưa kiểm bằng thao tác thật:**
   - nút **📸 Chụp Phông Nền Manga 2K** (tab 01, 02, 03): đường render đã đổi (composer 1 buffer, renderer chung), nhưng em không bấm vì nó ghi đè `beauty_plate.png` / `depth_map.png` thật của anh;
   - hình ảnh tab 03 `rig3d` (chỉ đo context/VRAM, chưa chụp so sánh);
   - nút `Ultra`.
   Đề nghị kiểm 3 mục này ở đầu Đợt B (có sao lưu `manga_plates\` trước).
7. **Chưa hot-swap** đúng theo phạm vi. Bản cài của anh vẫn là bản cũ (SHA `c1498e8a…`).

## 9. Đề nghị cho Đợt B

- B3 (KTX2) là việc đáng làm nhất để kéo VRAM tab 01/02 xuống. Texture `.glb` hiện chiếm phần lớn, không phải framebuffer.
- Đầu Đợt B nên chạy 3 kiểm tra ở mục 8.6 trên bản `target-dotA`, có sao lưu.
