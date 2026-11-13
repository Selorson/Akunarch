# Kế Hoạch VRAM Siêu Nhẹ `v2` — 3 Đợt Có Điểm Dừng (`Akunarch v2.2` ↔ `Selorson V3`)

> Bản này thay thế `implementation_plan.v1.md` (bản cũ vẫn nằm ở `C:\Users\Admin\.gemini\antigravity\brain\c064ef62-1e70-4ae8-b036-824a58386e76\` để đối chiếu).
> Viết lại sau khi audit trực tiếp mã nguồn ngày `2026-11-13`. Mọi khẳng định bên dưới đều có dẫn chứng `file:dòng` hoặc lệnh đã chạy thật. Số dòng có thể lệch ±3 do định dạng.

---

## 0. Kết Quả Audit (Đọc Trước Khi Làm Bất Cứ Gì)

### 0.1 Những gì bản `v1` chẩn đoán đúng
| Nhận định `v1` | Xác minh | Dẫn chứng |
|---|---|---|
| Vòng `requestAnimationFrame` chạy liên tục | ✅ Đúng ở cả 3 sân khấu | `RealPbrStageViewport.svelte:899-907`, `OpenWorldChunkWorkbench.svelte:751-774`, `VnDirectorStagePanel.svelte:332-339` |
| Dọn cảnh chỉ gọi `renderer.dispose()`, không duyệt cây scene | ✅ Đúng | `RealPbrStageViewport.svelte:912-924`, `OpenWorldChunkWorkbench.svelte:776-790`, `VnDirectorStagePanel.svelte:341-347`, `WorldOpenRealm.svelte:723-741` |
| Topbar chỉ đọc `nvidia-smi` toàn máy | ✅ Đúng | `gpu_queue.rs:2019-2043`, pill VRAM trong `+page.svelte` |
| Có 4 kỳ quan `.glb` thật | ✅ Đúng | `projects/{temple-of-zyberon, singularity-stonehenge-avalon, avalon-mage-sanctum, singularity-samos-olympus}/clockwork/*.glb` |
| `renderer.dispose()` không giải phóng texture/geometry đã upload | ✅ Đúng (three r178): `WebGLRenderer.dispose()` chỉ reset bảng thuộc tính, không `deleteTexture`. VRAM chỉ được trả khi (a) phát sự kiện `dispose` cho từng tài nguyên **trước khi** renderer bị hủy, hoặc (b) context bị GC/mất. | three `WebGLRenderer.dispose` |

### 0.2 Những gì bản `v1` BỎ SÓT — nghiêm trọng hơn các mục đã nêu

**🔴 P0-1. Tab `02 Thế Giới Mở` dựng lại TOÀN BỘ renderer sau MỖI thao tác chỉnh sửa.**
`$effect` tại `OpenWorldChunkWorkbench.svelte:389-391` đọc `activeChunk` (một `$derived` từ mảng `projects`). Mỗi nét điêu khắc / đặt `.glb` / thêm vùng nhạc / trigger VN đều gọi `onProjectMutated` (`:812, 912, 929, 945, 970, 992`) → `api.projectsList()` → `projects` là mảng object mới → `activeChunk` đổi danh tính → effect chạy lại:
- tạo `new THREE.WebGLRenderer` mới (context WebGL2 mới),
- nạp lại 4 texture Poly Haven `Diffuse_2k.jpg` **cho từng ô** (ô chính + mỗi ô hàng xóm tạo material riêng, `:164-172`, `:486`),
- nạp lại mọi `.glb` đặt trên đất và cả file splat `.ply`,
- nhưng phần dọn dẹp cũ không `dispose` texture/geometry nào.

Hệ quả: 20 nét điêu khắc ≈ 20 context bị bỏ rơi, mỗi context giữ khoảng `4 × ~21 MB × (1 + số ô lân cận)` texture địa hình cộng texture `.glb`. Đây gần như chắc chắn là nguồn chính của mức `+500 → +930 MB` mà `v1` đo được. Chromium cũng giới hạn khoảng **16 context WebGL đang sống**; vượt ngưỡng thì nó tự làm mất context cũ nhất (`"Too many active WebGL contexts"`). Tức là chỉ cần điêu khắc khoảng 16 nét là chạm đúng lỗi mà `v1` muốn tránh bằng cách cấm `loseContext`.

**🔴 P0-2. Mỗi lần bật/tắt 3D hay đổi dự án đều tạo context mới.**
Kế hoạch `v1` (tạo rồi hủy renderer, không `loseContext`) vẫn để lại context chờ GC, nên **30 lần chuyển dự án liên tiếp vẫn chạm giới hạn 16 context**. Cách đúng là **một `WebGLRenderer` + một `<canvas>` dùng chung cho cả app**: gắn vào khung khi cần, tháo ra khi không cần, và không bao giờ hủy context.

**🟠 P1-1. Khoảng một nửa VRAM của tab 01 là framebuffer chứ không phải texture.** Ước tính trên màn `2560×1440 @ 96 DPI` (đã kiểm `AppliedDPI = 96`, tức `devicePixelRatio = 1`):
- `RealPbrStageViewport.svelte:257` **ép DPR tối thiểu 1.5** dù màn hình là 1.0, nên số điểm ảnh tăng ×2.25.
- `:262` canvas `antialias: true` (MSAA 4× trên swapchain), dù toàn bộ cảnh đã render qua composer offscreen. Đây là VRAM lãng phí (~70–80 MB).
- `:346-357` `EffectComposer(renderer, msaaTarget)` **clone** target MSAA HalfFloat thành `renderTarget2` (`three/examples/jsm/postprocessing/EffectComposer.js:80`). Như vậy có **2 bộ đệm MSAA 4× RGBA16F**, mỗi bộ ~100–120 MB, trong khi bộ thứ hai chỉ cần 1×.
- `UnrealBloomPass` không bao giờ được `dispose()`: `composer.dispose()` chỉ giải phóng `renderTarget1/2` và `copyPass` (`EffectComposer.js:352-357`), bỏ sót chuỗi mip của bloom. Shadow map 2048² của `keyLight` cũng không được `shadow.dispose()`.
- Texture trong `.glb` (đo bằng script đọc header GLB, không đoán):

| Kỳ quan | Ảnh | Tam giác | Texture RGBA8+mip ước tính |
|---|---|---|---|
| `temple-of-zyberon` | 36 (4×2K, 3×1.5K, còn lại 1K) | 144,045 | ~261 MB |
| `singularity-samos-olympus` | 46 | 339,325 | ~297 MB |
| `singularity-stonehenge-avalon` | 33 | 124,762 | ~224 MB |
| `avalon-mage-sanctum` | 69 (nhiều ảnh 256² lặp) | 32,440 | ~252 MB |

  Tất cả đều là JPEG thường, **chưa nén KTX2/Basis**. Nén sang KTX2 (BC7/BC1 trên GPU) giảm 4–8×.
- **Kết luận:** sửa framebuffer cộng KTX2 có thể đưa sân khấu 3D **đang bật** về khoảng 150–220 MB (ước tính, phải đo xác nhận), tức đạt chỉ tiêu `v1` mà không cần tắt 3D. Chế độ Chờ 2D vẫn hữu ích nhưng xuống ưu tiên thấp hơn.

**🟠 P1-2. Nhánh "nạp xong nhưng đã hủy" bị rò rỉ.** `RealPbrStageViewport.svelte:379-383`: nếu người dùng đổi dự án trong lúc `.glb` đang nạp, code chỉ gọi `dracoLoader.dispose(); renderer.dispose()`. `gltf.scene`, PMREM `envRT`, composer, bloom và shadow đều bị bỏ lại. Bấm `[` `]` nhanh qua các dự án (`+page.svelte`, phím tắt) sẽ kích hoạt đúng nhánh này.

**🟠 P1-3. Tab 02 nạp trùng tài nguyên.** Cùng một `.glb` đặt ở 2 chỗ thì nạp 2 lần (không có cache, `:538-590`). 4 texture địa hình được nạp lại cho mỗi ô lân cận. `SparkRenderer` (`:413`) không được dispose. `preserveDrawingBuffer: true` (`:398`, và `VnDirectorStagePanel.svelte:237`) giữ thêm một bộ đệm khung hình trong khi không cần: các hàm chụp đều `render()` rồi `toDataURL()` ngay trong cùng một tác vụ.

**🟡 P2-1. Đo "GPU 0%" bị chính app làm nhiễu.** `+page.svelte:123` gọi `refreshHardwareAndJobs` mỗi `4.5 s`, và lần nào cũng spawn `nvidia-smi` (`gpu_queue.rs:2020`). Khởi tạo NVML có thể kéo GPU ra khỏi `P8` trong chốc lát. Vòng poll này cũng **không dừng khi cửa sổ bị ẩn**. Bản thân `utilization.gpu` của `nvidia-smi` chỉ là một mẫu tức thời nên không đủ làm bằng chứng "0%".

**🟡 P2-2. `vram_peak_mb` trong `gpu_jobs` không phản ánh đỉnh thật.** `gpu_queue.rs` (trong `try_process_next_queued_job`, quanh `vram_before` / `vram_after`) chỉ đo trước và sau job. Khi job xong thì Hunyuan/Blender đã thoát, VRAM đã trả, nên giá trị "đỉnh" thực ra là mức nền.

**🟡 P2-3. PDH chạy được, nhưng có 2 bẫy (đã thử bằng `Get-Counter` trên máy anh):**
- Tên mẫu đúng dạng `pid_<PID>_luid_0x..._0x..._phys_0`, nhưng **một PID có thể xuất hiện trên 2 LUID khác nhau** (ví dụ `pid_27680` có cả `0x00010af9` và `0x00011c8d`). Lọc theo `phys_0` thôi là không đủ, phải **lọc theo LUID của RTX 4080**.
- Lần đọc đầu có thể ném lỗi `"The data in one of the performance counter samples is not valid"`. Phải kiểm `CStatus` từng mẫu và thử lại một lần.
- Đã xác nhận cây tiến trình: tiến trình gốc `msedgewebview2.exe` là con trực tiếp của app chủ, và GPU process là con của tiến trình gốc đó. Cách duyệt hậu duệ từ `std::process::id()` là đúng.

**🟡 P2-4. Có những mục trong `v1` đã có sẵn trong code (đừng làm lại):**
- `RealPbrStageViewport` **đã** `await import('three')` động (`:236-250`). `OpenWorldChunkWorkbench` và `VnDirectorStagePanel` mới là chỗ import tĩnh (`:3-7`).
- `GlobeScene.svelte:623-624` **đã** `cosmicStars?.dispose(); cosmicStarMat?.dispose()`. `:490-493` **đã** dispose `bloomPass/outputPass/composer/hdrTarget`.
- `WorldOpenRealm.svelte:583` **đã** bỏ qua `render()` khi `activeVnModal` mở (nhưng `rAF` vẫn quay).
- `requestAnimationFrame` **tự dừng** khi `document.hidden`. Điều cần kiểm là WebView2 trong Tauri có thật sự báo `hidden` khi **thu nhỏ cửa sổ** hay không (xem `A7`).

**🟡 P2-5. Một số chi tiết của `v1` không khớp thực tế:**
- `v1` nói cold boot "mở dự án đầu tiên `temple-of-zyberon`", nhưng `list_projects` sắp `ORDER BY updated_at DESC` (`projects.rs:1112`), nên dự án clockwork mở đầu tiên là **dự án sửa gần nhất**, không cố định.
- Lệnh `/goal` của `v1` ghi "Luật #5 Giữ Cargo.toml siêu nhẹ", nhưng Luật #5 trong `AGENTS.md` là về Sidecar / `D:\hf-cache` / `GpuJobQueue`. Ràng buộc Cargo thật nằm ở test `Rule #3` (`ui/tests/akunarch-runtime.test.mjs:58-67`), chỉ cấm `wgpu, egui, ort =, materialcraft, effectcraft, filmcraft`.
- `temple-of-zyberon/clockwork/temple_of_zyberon.glb` **trùng từng byte** với `temple-of-zyberon.glb` (`cmp` → IDENTICAL), và không manifest nào tham chiếu tới nó.
- Tên `_preview_2k.png` nhưng render `1920×1080`. Đổi thành `_preview_1080p.png` hoặc render `2048×1152`.

### 0.3 Phát hiện ngoài phạm vi VRAM (ghi nhận, KHÔNG sửa trong kế hoạch này)
- `lib.rs` `run()` quét `rescan_projects_from_disk` **đồng bộ trước khi tạo cửa sổ**, rồi `studio_bootstrap` quét lại lần nữa cộng quét kho asset. Cold boot bị chậm gấp đôi phần quét.
- `media_protocol` đăng ký bằng `register_uri_scheme_protocol` (đồng bộ) và `read_to_end` cả file (`.glb` 11–13 MB, texture 2K). Trên WebView2, handler đồng bộ có thể chặn luồng UI. Nên chuyển sang `register_asynchronous_uri_scheme_protocol`.
- `WorldOpenRealm.svelte:484` nạp Draco decoder từ `gstatic.com`, nên bản **Selorson Admin desktop** sẽ lỗi khi offline.
- CSP `connect-src` của Akunarch mở rộng `https: ws: wss:` (`tauri.conf.json`), rộng hơn mức cần.

---

## 1. Quyết Định Cần Anh Chốt Trước Khi Chạy (có mặc định nếu anh không trả lời)

> ✅ **Đã chốt ngày 2026-11-13:** anh chọn **theo mặc định cho cả Q1–Q4** (`windows-sys` · Chờ 2D bật mặc định · bản gốc vào `_master/` · file trùng chuyển sang `E:\Akunarch\_archive\`).

| # | Câu hỏi | Mặc định đề xuất |
|---|---|---|
| Q1 | Đo PDH bằng FFI viết tay (0 crate) hay `windows-sys` (crate bindings thuần, không runtime, không vi phạm test `Rule #3`)? | **`windows-sys`**: FFI tay cho `PDH_FMT_COUNTERVALUE_ITEM_W` + vòng `PDH_MORE_DATA` rất dễ sai layout. Nếu anh muốn giữ 0 crate thì đổi lại. |
| Q2 | Chế độ Chờ 2D khi khởi động: bật mặc định hay chỉ là tùy chọn? | **Bật mặc định** (đúng ý anh ở `v1`), nhưng làm ở **Đợt C**, sau khi 3D đã nhẹ. |
| Q3 | Nén KTX2: giữ bản gốc ở đâu? | Bản gốc chuyển sang `clockwork/_master/<slug>.glb`. Bản runtime KTX2 **giữ nguyên tên** `<slug>.glb`, nên mọi manifest (chunk/cinema/vn đang trỏ tới `temple-of-zyberon.glb`) không phải sửa. |
| Q4 | File trùng `temple_of_zyberon.glb`? | Chuyển sang `E:\Akunarch\_archive\` (ngoài `projects\` để không bị quét), **không xóa**. |

---

## 2. Nguyên Tắc Kỹ Thuật Xuyên Suốt (Áp dụng cho cả 3 đợt)

1. **Một renderer, không bao giờ mất context:** cấm `forceContextLoss()` / `WEBGL_lose_context`. Trong `E:\Akunarch\app\ui\src` chỉ được có **đúng 1** chỗ gọi `new WebGLRenderer` (trong `webgl-stage.ts`). Test tĩnh sẽ kiểm điều này.
2. **Thứ tự giải phóng:** dispose từng tài nguyên (geometry, material, texture, render target, pass, shadow map, PMREM, Spark) **trong khi renderer còn sống**, rồi mới thu canvas về `1×1`.
3. **Chống nạp muộn:** mọi loader bất đồng bộ mang theo `sessionToken`. Callback về muộn thì `disposeObject3DDeep(result)` ngay.
4. **Render theo nhu cầu:** khi đứng yên thì không có `rAF` nào chạy. Mọi nguồn thay đổi phải gọi `invalidate()`.
5. **Zero Toy Primitives (Luật #1):** không thêm `Box/Cylinder/Cone/Torus/OctahedronGeometry`. Test `akunarch-runtime.test.mjs:104-138` phải tiếp tục pass.
6. **Nghiệm thu bằng số đo tương đối:** luôn đo **baseline trước khi sửa** bằng đúng script đó. Chỉ tiêu tuyệt đối trong `v1` (`≤ 55 MB`, `160–230 MB`) chỉ còn là tham khảo, không phải điều kiện pass. Cấm chỉnh số cho khớp. Số nào không đạt thì ghi rõ là không đạt.
7. **Luật #2:** đo và chụp nghiệm thu từ `C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe` ở chế độ người dùng thật, đọc `E:\Akunarch\projects\` và `%LOCALAPPDATA%\Akunarch\akunarch.db`, không trỏ `%TEMP%`.

---

## 3. ĐỢT A — "Cầm Máu": Hết Rò Rỉ, Hết Quay GPU Khi Đứng Yên (chỉ `E:\Akunarch`)

**Mục tiêu:** sửa P0-1, P0-2, P1-1 (phần framebuffer), P1-2, P1-3 và P2-1. Đợt này không thêm khái niệm UI mới, không đụng Rust.

### A0. Đo baseline trước khi sửa  → verify: có file CSV baseline
- **[NEW]** `E:\Akunarch\bin\scripts\measure_vram.ps1`:
  - Tìm PID `akunarch.exe` và toàn bộ hậu duệ (`Win32_Process.ParentProcessId`), chia nhóm `webview / worker / host`.
  - Đọc `\GPU Process Memory(*)\Local Usage` qua `Get-Counter`: lọc theo **LUID của RTX 4080** (LUID có tổng `\GPU Adapter Memory(*)\Dedicated Usage` lớn nhất), bỏ mẫu `Status ≠ 0`, thử lại một lần nếu lỗi.
  - Chạy song song `nvidia-smi --query-gpu=utilization.gpu,power.draw,pstate,memory.used --format=csv,noheader,nounits -lms 500` trong `N` giây, lấy **trung bình, p95 và pstate chiếm ưu thế**.
  - Xuất `E:\Akunarch\docs\vram\<label>_<yyyyMMdd-HHmm>.csv` cộng một dòng tóm tắt.
- Đo baseline với **app đã tắt** (nền máy) và với bản `akunarch.exe` hiện tại, theo 5 kịch bản ở mục 6.

### A1. **[NEW]** `app/ui/src/lib/webgl/dispose.ts`  → verify: unit test `node --test`
- `disposeMaterialDeep(mat)`: duyệt **mọi thuộc tính** có `isTexture` (không dùng danh sách cứng, để bao được `iridescenceMap`, `anisotropyMap`…), cộng `uniforms[*].value` (đơn hoặc mảng) với `ShaderMaterial`, rồi `mat.dispose()`. Dùng `Set` để không dispose trùng.
- `disposeObject3DDeep(root)`: geometry, material (đơn hoặc mảng), `InstancedMesh.dispose()`, `light.shadow?.dispose()` (giải phóng shadow map), `SplatMesh.dispose?.()`. Với `Scene` thì thêm `background` / `environment` nếu là texture, rồi `clear()`.
- `disposeComposer(composer)`: `composer.passes.forEach(p => p.dispose?.())` (bắt được `UnrealBloomPass`) rồi `composer.dispose()`.
- **Test** `app/ui/tests/webgl-dispose.test.mjs` (Node, không cần GPU): dựng cảnh three thật gồm `MeshStandardMaterial` đủ map, `ShaderMaterial` có uniform texture và mảng texture, `InstancedMesh`, `DirectionalLight` có shadow. Gắn listener `'dispose'` cho từng tài nguyên, rồi assert **100% đều phát `dispose` đúng 1 lần**.

### A2. **[NEW]** `app/ui/src/lib/webgl/webgl-stage.ts` — renderer dùng chung  → verify: test tĩnh và kịch bản bật/tắt 30 lần
- Tạo lười một `WebGLRenderer({ antialias: false, alpha: false, powerPreference: 'high-performance', preserveDrawingBuffer: false })` cho cả vòng đời app. Dùng lại cùng ý tưởng `acquireSafeWebGLContext` và `sessionStorage` như `Selorson quality.ts:143-180` (chép logic, không import chéo repo).
- `attach(host, opts)`: chuyển canvas vào `host`; đặt lại `toneMapping`, `toneMappingExposure`, `outputColorSpace`, `shadowMap.enabled/type` theo từng sân khấu; trả về `{ renderer, setSize, detach }`. Mỗi thời điểm chỉ một sân khấu được giữ quyền; `attach` mới tự `detach` sân khấu cũ.
- `detach()`: gọi callback dọn cảnh của sân khấu, rồi `renderer.setRenderTarget(null)`, `renderer.renderLists.dispose()`, `setPixelRatio(1)`, `setSize(1, 1, false)`, chuyển canvas vào một holder `display:none` ngoài DOM của tab. **Không** gọi `renderer.dispose()`.
- `getStats()`: trả `renderer.info.memory.{geometries,textures}` và `info.programs.length` để kiểm rò rỉ trong test.
- Lắng nghe `webglcontextlost` / `webglcontextrestored`: ghi log và cho phép `attach` lại.
- **Khử răng cưa sau khi bỏ `antialias` trên canvas:** tab 01 vẫn dùng MSAA qua render target của composer. Tab 02 trước giờ đã `antialias: false`. Tab 03 (đang `antialias: true`) chuyển sang render qua `WebGLRenderTarget({ samples: 4 })` cộng `OutputPass`, hoặc chấp nhận không AA. **Mặc định:** dùng target MSAA ở độ phân giải khung nhỏ của tab 03.

### A3. **[NEW]** `app/ui/src/lib/webgl/on-demand-loop.ts`
- `createOnDemandLoop(step: (dt) => boolean /* true = cần thêm khung */)` cung cấp `invalidate(frames = 2)`, `setContinuous(reason, on)` (tập lý do như `autoRotate`, `wasd`, `waves`, `splatSettle`), `dispose()`.
- Không có lý do liên tục và hết khung chờ thì `rafId = 0` (không còn `rAF` nào).
- Nguồn đánh thức bắt buộc: `controls 'change'` (OrbitControls tự phát cả khi đang damping), `pointerdown`, `wheel`, `keydown`, `ResizeObserver`, mọi lời gọi `stageApi.*` (explode, ẩn/hiện cụm, wireframe, grid, highlight, resetCamera), mỗi `.glb` hay texture nạp xong (`LoadingManager.onLoad` và `onProgress`).
- **Spark:** sau mỗi lần camera dừng, giữ `setContinuous('splatSettle')` thêm khoảng 30 khung (≈0.5 s) để worker sắp xếp splat kịp đẩy kết quả cuối lên màn hình. Kiểm bằng mắt: dừng chuột rồi chụp, không được thấy splat sai thứ tự.

### A4. **[MODIFY]** `RealPbrStageViewport.svelte`
- Dùng `webgl-stage.attach`, bỏ `new THREE.WebGLRenderer` (`:262-272`).
- DPR: `Math.min(devicePixelRatio || 1, cap)` với `cap = 1.0` (HD) hoặc `1.5` (Ultra). **Bỏ mức tối thiểu 1.5** ở `:257`.
- Composer: giữ `msaaTarget` (samples 4) làm `renderTarget1`, rồi **thay `renderTarget2` bằng target `samples: 0` cùng `HalfFloatType`**. Ghi chú: `EffectComposer.reset()` sẽ clone lại, nên tránh gọi `reset()`; nếu bắt buộc thì gán lại sau đó.
  - ⚠️ **Đính chính khi triển khai (2026-11-13):** chỉ đổi `renderTarget2` sang `samples: 0` là **sai**. `OutputPass` kế thừa `Pass.needsSwap = true`, nên composer hoán đổi read/write **mỗi khung**; MSAA sẽ chỉ có ở khung chẵn. Ngoài ra constructor đặt `readBuffer = renderTarget2` và `RenderPass` vẽ vào `readBuffer`. Cách đúng (đã áp dụng): `outputPass.needsSwap = false` (nó vẽ thẳng ra màn hình), `composer.readBuffer = msaaTarget`, và `renderTarget2 = writeBuffer =` target 1×1 khóa `setSize`.
- Shadow map: HD `1536`, Ultra `2048`.
- Cleanup đầy đủ: `disposeObject3DDeep(scene)` (gồm `gltf.scene`, `shadowFloor`, `gridHelper`, shadow của `keyLight`), `disposeComposer(composer)`, `envRT.dispose()`, `pmrem.dispose()`, `dracoLoader.dispose()`, `controls.dispose()`, gỡ listener, `resizeObs.disconnect()`, rồi `stage.detach()`.
- **Nhánh nạp muộn (`:379-383`)** đi qua **cùng hàm cleanup đầy đủ** ở trên. Không giữ nhánh rút gọn riêng.
- `tick` chuyển sang `createOnDemandLoop`, với `autoRotate` là một lý do liên tục.
- Bỏ `tex.needsUpdate = true` sau khi đổi `anisotropy` (quanh `:416-419`): texture chưa upload lần nào thì không cần.
- Thêm nút `[HD | Ultra]` (`data-testid="pbr-quality-toggle"`). **Chụp Manga 2K vẫn render đúng `2048×1152` / `1440×2048`** bất kể HD hay Ultra (giữ logic `:830-893`).

### A5. **[MODIFY]** `OpenWorldChunkWorkbench.svelte` — sửa P0-1
- Chuyển `import * as THREE`, `OrbitControls`, `GLTFLoader`, `DRACOLoader`, `@sparkjsdev/spark` (`:3-7`) sang `await import()` trong effect. Dùng `import type` cho phần kiểu.
- **Tách effect:**
  1. **Effect sân khấu** chỉ phụ thuộc `activeChunk?.slug`, `showNeighbors`, `viewportHost`. Mọi thứ khác đọc qua `untrack`. Effect này dựng renderer attach, ánh sáng, controls, loop.
  2. **Effect địa hình** phụ thuộc `heightmap_values`, `grid_resolution`, `water_level` của ô chính và ô lân cận. Cập nhật **tại chỗ**: ghi đè `position` của `BufferGeometry`, `computeVertexNormals()`, `attributes.position.needsUpdate = true`, rồi `invalidate()`. Kích thước lưới đổi thì mới thay geometry (dispose cái cũ).
  3. **Effect công trình** đối chiếu `placements` theo `id`/khóa: thêm cái mới, gỡ cái đã xóa (`disposeObject3DDeep` nếu không còn ai dùng chung), cập nhật vị trí, xoay, tỉ lệ cho cái đã đổi.
  4. **Effect vùng nhạc / trigger VN** dựng lại riêng các `Line` (rẻ), dispose cái cũ.
- **Cache texture địa hình** trong phạm vi sân khấu: 4 texture Poly Haven nạp **một lần**, dùng chung cho ô chính và mọi ô lân cận. Giá trị riêng từng ô (`uIsNeighbor`, `uWaterLevel`) để ở material clone **dùng chung texture** (`ShaderMaterial.clone()` giữ tham chiếu texture, không nhân bản).
- **Cache `.glb`** theo đường dẫn trong phạm vi sân khấu: nạp 1 lần, các vị trí đặt dùng `root.clone()` (chung geometry và material). Đếm tham chiếu; chỉ dispose khi không còn vị trí nào dùng.
- Splat: `sessionToken`; `SplatMesh.dispose()`; `SparkRenderer` gỡ khỏi scene, gọi `dispose?.()` nếu API bản `0.1.10` có (kiểm trong `node_modules/@sparkjsdev/spark` trước khi viết).
- Sóng nước: là một lý do liên tục, **chỉ bật khi** công tắc `🌊 Sóng` bật **và** tab đang hiển thị. Tắt thì đóng băng `uTime`.
- Bỏ `preserveDrawingBuffer: true` (`:398`). `captureMangaPlates2K` (`:705-745`) đã `render()` rồi `toDataURL()` cùng tác vụ, nên giữ nguyên thứ tự đó. Dispose `MeshDepthMaterial` tạm sau khi chụp.

### A6. **[MODIFY]** `VnDirectorStagePanel.svelte`
- Chuyển các import three ở `:3-6` sang động bên trong nhánh `rig3d`.
- Dùng `webgl-stage.attach` + `createOnDemandLoop` + cleanup đầy đủ + `sessionToken` cho `loader.load` (`:285`).
- Bỏ `preserveDrawingBuffer: true` (`:237`). Dispose `MeshDepthMaterial` tạo trong `captureBackdropDataUrl`.

### A7. **[MODIFY]** `+page.svelte` — polling không làm nhiễu GPU
- `refreshHardwareAndJobs` (`:123`): bỏ qua khi `document.hidden`. Khi không có job `running`/`queued` **và** không mở tab `gpu`, giãn chu kỳ lên 15 s; khi có job thì giữ 4.5 s.
- ✅ **Đã đo (2026-11-13):** thu nhỏ `akunarch.exe` → `document.visibilityState` **vẫn `visible`**, `requestAnimationFrame` **vẫn 60/s**. Vì vậy dùng `getCurrentWindow().isMinimized()` + `onResized`/`onFocusChanged` (quyền `allow-is-minimized` đã có sẵn trong `core:default`) để gọi `setAllLoopsSuspended()` và dừng poll.
- **Kiểm thu nhỏ cửa sổ:** đo xem `document.visibilityState` có thành `hidden` khi thu nhỏ `akunarch.exe` không. Nếu **không**, thêm lắng nghe `getCurrentWindow().onResized` + `isMinimized()` từ `@tauri-apps/api/window` để tạm dừng poll và mọi loop. Cần thêm quyền `core:window:allow-is-minimized` vào `capabilities/` nếu thiếu.

### A8. Kiểm thử Đợt A
- `app/ui`: `npm run check`, `npm run build`, `npm test` (gồm test mới `webgl-dispose.test.mjs` và test tĩnh mới):
  - Trong `src/` không có chuỗi `forceContextLoss`, `loseContext`, `WEBGL_lose_context`.
  - `new THREE.WebGLRenderer` hoặc `new WebGLRenderer` xuất hiện **đúng 1 lần**, trong `lib/webgl/webgl-stage.ts`.
  - Trong 3 file sân khấu không còn `preserveDrawingBuffer: true`.
- `app/src-tauri`: `cargo test` (không đổi Rust ở đợt này, chỉ chạy để chắc không hỏng gì).
- Kịch bản đo ở mục 6 (#2, #3, #4) cộng hai kiểm tra riêng:
  - **20 nét điêu khắc liên tiếp** ở tab 02: `App VRAM` sau nét 20 không quá `+30 MB` so với sau nét 1; `renderer.info.memory.textures` không tăng.
  - **30 lần đổi dự án / bật-tắt tab 3D:** qua CDP (harness sẵn có `ui/tests/verify-live-user-mode.mjs`), `0` sự kiện `webglcontextlost`, `0` dòng console `Too many active WebGL contexts`.

### ⏸ ĐIỂM DỪNG A
Xuất `E:\Akunarch\docs\vram\walkthrough_dot_A.md` gồm bảng **baseline và sau sửa** cho từng kịch bản, ảnh chụp đối chiếu cùng góc máy (trước/sau, chứng minh chất lượng hình không giảm), và danh sách mục chưa đạt nếu có. **Dừng, chờ anh duyệt.** Chưa hot-swap ở đợt này nếu anh chưa đồng ý.

---

## 4. ĐỢT B — Đo VRAM Đúng Phần App + Pipeline Tài Nguyên Nhẹ (`E:\Akunarch`)

### B1. **[NEW]** `app/src-tauri/src/vram_win32.rs`
- Theo Q1: dùng `windows-sys` (features `Win32_System_Performance`, `Win32_System_Diagnostics_ToolHelp`, `Win32_Foundation`) hoặc FFI tay.
- Giữ một `PdhQuery` tĩnh trong `Mutex<Option<…>>`, lười khởi tạo bằng `PdhAddEnglishCounterW` cho `\GPU Process Memory(*)\Local Usage` và `\GPU Adapter Memory(*)\Dedicated Usage`.
- Gọi `PdhGetFormattedCounterArrayW` theo kiểu **hai lần** (lần đầu lấy kích thước, `PDH_MORE_DATA`), bỏ mẫu có `CStatus` khác `PDH_CSTATUS_VALID_DATA` / `NEW_DATA`, thử lại 1 lần khi lần đầu lỗi.
- **Chọn LUID:** LUID có `Dedicated Usage` lớn nhất trong `GPU Adapter Memory`. Chỉ cộng các mẫu `pid_*_luid_<LUID đó>_phys_0`.
- Hậu duệ của `std::process::id()` lấy qua `CreateToolhelp32Snapshot`, chia nhóm `webview` (`msedgewebview2.exe`), `worker` (`python.exe`, `blender.exe`, `*-cli.exe`, `akunarch-audio-cli.exe`), `host`. Dựng cây **trong một snapshot** để tránh lẫn PID tái sử dụng.
- `#[cfg(not(windows))]` trả về toàn số 0.
- **Unit test:** parser `pid_<u32>_luid_0x…_0x…_phys_<n>` (cả tên hợp lệ lẫn sai), hàm dựng tập hậu duệ từ danh sách `(pid, ppid)` giả (gồm vòng lặp PID và PID mồ côi), hàm chọn LUID.
- Chạy qua `spawn_blocking`, có timeout 1500 ms. Lỗi thì trả 0 kèm `app_vram_available: false`, không làm hỏng IPC.

### B2. **[MODIFY]** `gpu_queue.rs`, `lib.rs`, `types.ts`, `+page.svelte`, `GpuQueuePanel.svelte`
- `VramTelemetry` thêm `#[serde(default)]` cho `app_used_mb`, `webview_used_mb`, `worker_used_mb`, `other_system_mb`, `app_vram_available`. Tính `other_system_mb = (used_mb - app_used_mb).max(0)`.
- **Sửa P2-2:** trong lúc job chạy, lấy mẫu VRAM mỗi 1 s bằng một task song song (`tokio::select!` với job), ghi `vram_peak_mb` là giá trị lớn nhất **của toàn máy và của nhóm worker**.
- **Nhường VRAM cho job GPU nặng:** trước khi chạy job `hunyuan3d | blender | comfyui | worldgen | tts`, `app.emit("akunarch://gpu-job-starting", {kind})`. UI nhận được thì phát `akunarch:release-webgl-vram`, sân khấu đang mở `detach()` về ảnh tĩnh (nếu đã có Đợt C) hoặc hiện thông báo "Đã tạm tắt 3D để nhường VRAM". Việc này cần cho `GpuJobQueue` giữ `AppHandle` (truyền vào lúc `setup`).
- Topbar `data-testid="topbar-vram-pill"`: `VRAM App: X MB · Máy: Y / 16384 MB`. Tooltip: `WebView2 (UI/3D) · GPU Worker · Windows & app khác · GPU % · °C`.
- `🧹`: phát `akunarch:release-webgl-vram`, chờ 300 ms, gọi `api.gpuReleaseVram()`, rồi đo lại.
- `GpuQueuePanel` thêm thanh kép: phần app (đồng) và phần nền (xám).

### B3. Pipeline KTX2 cho `.glb`  → verify: so ảnh trước/sau cùng góc máy theo Luật #7
- **[NEW]** `E:\Akunarch\bin\scripts\optimize_glb_runtime.ps1`, gọi `gltf-transform` (Node CLI, cài cục bộ trong `E:\Akunarch\bin\tools\`) và `toktx` (KTX-Software). Không thêm gì vào `Cargo.toml` hay `package.json` của app.
  - `baseColor` và `emissive`: `ETC1S` (hoặc `UASTC` nếu thấy vệt khối). `normal`, `ORM`/`roughness`/`metalness`: `UASTC` + `zstd`.
  - Giữ Draco cho mesh. Gộp ảnh trùng (`dedup`), xóa ảnh không dùng (`prune`). Hai bước này có thể giảm mạnh số ảnh của `avalon-mage-sanctum` (nhiều ảnh 256² lặp).
  - Bản gốc chuyển vào `clockwork/_master/<slug>.glb` (Q3). **Không bao giờ ghi đè `_master`.**
- **[MODIFY]** 3 sân khấu: thêm `KTX2Loader` với `setTranscoderPath('/basis/')` và `detectSupport(renderer)`. Chép `node_modules/three/examples/jsm/libs/basis/basis_transcoder.{js,wasm}` vào `app/ui/static/basis/`. CSP hiện đã có `'wasm-unsafe-eval'`, `worker-src 'self' blob:`, nên không cần đổi (kiểm lại bằng test CSP hiện có).
- **[MODIFY]** `gpu_queue.rs`: sau `assemble_glb` / `sculpt_concept` thành công, tự xếp thêm bước `optimize_glb_runtime` (worker `blender`, chạy CPU nhưng vẫn qua queue để tuần tự). Nhờ vậy bản xuất mới không quay lại JPEG thường.
- Chạy cho 4 kỳ quan. Bảng nghiệm thu: số ảnh, dung lượng file, `renderer.info.memory.textures`, VRAM App khi bật 3D, cùng ảnh chụp đối chiếu.
- Chuyển `temple_of_zyberon.glb` trùng sang `E:\Akunarch\_archive\` (Q4) sau khi `grep` DB và manifest xác nhận không có tham chiếu.

### B4. Kiểm thử Đợt B
- `cargo test` (gồm test mới của `vram_win32`), `npm run check`, `npm run build`, `npm test`.
- Đối chiếu số đo Topbar với `measure_vram.ps1` cùng thời điểm: lệch không quá `±5%` hoặc `±10 MB`.

### ⏸ ĐIỂM DỪNG B
Xuất `walkthrough_dot_B.md`. Dừng, chờ anh duyệt.

---

## 5. ĐỢT C — Selorson V3 + Chế Độ Chờ 2D + Hot-Swap & Nghiệm Thu Tổng

### C1. Selorson V3 (`E:\Selorson\frontend-v3`)
- **[NEW]** `src/lib/world/engine/webgl-dispose.ts`: cùng API với `A1` (chép, không import chéo repo) cộng test `tests/webgl-dispose.test.mjs`.
- **[MODIFY]** `WorldOpenRealm.svelte`:
  - `sessionToken` cho `gltfLoader.load` (`:504`) và `loadPlySplatCloud` (`:531`): callback về muộn thì dispose ngay, không `scene.add`.
  - `stopRuntimeOnly()` (`:723`): `disposeObject3DDeep(scene)` (gồm shadow map `sun` 2048²), `draco.dispose()`, gỡ `Audio` (`src = ''`, `load()`), rồi `setSize(1,1,false)`, `renderLists.dispose()`, `renderer.dispose()` và gỡ canvas. Ở đây chấp nhận tạo/hủy renderer vì người dùng vào/ra Thế giới mở **thưa**. Nếu đo thấy chạm giới hạn context thì áp dụng renderer dùng chung như `A2`.
  - Khi `activeVnModal` mở: **dừng hẳn `rAF`** (hiện chỉ bỏ qua `render` ở `:583`), mở lại khi đóng modal.
  - Texture terrain: cache dùng chung giữa các chunk như `A5`.
- **[MODIFY]** `textures.svelte.ts`: thêm `purgeWorldTextureCache()` (await các promise, `texture?.dispose()`, `cache.clear()`). `geo-data.svelte.ts`: thêm `purgePlanetGeoCache()` (dispose `elevSdfTex` và `normalSpecTex` của từng bundle, `bundleCache.clear()`).
- **[MODIFY]** `WorldCanvas.svelte`: khi unmount (`:76-79`), gọi `purgeWorldTextureCache()` + `purgePlanetGeoCache()` **trước** `releaseActiveRenderer()`. Kiểm Threlte `<T>` có tự dispose khi unmount ở bản `@threlte/core 8.5.x` không (đọc mã trong `node_modules`); nếu không thì dispose thủ công trong `GlobeScene`.
- **Không đổi:** `GlobeScene.svelte:490-493, 623-624` (đã đúng). `quality.ts` (đã đúng quy tắc không `loseContext`).
- Kiểm thử: `npm run check`, `npm run build`, `npm run test:runtime` ở `frontend-v3`; `cargo test` ở `backend-v3` (không đổi backend, chỉ để chắc).

### C2. Chế độ Chờ 2D (Akunarch, theo Q2)
- **[NEW]** `E:\Akunarch\bin\scripts\render_glb_preview_card.py` (Blender 5.2 `--background`): nạp `<slug>.glb`, góc 3/4 theo hộp bao, ống kính 40 mm, studio 3 điểm, nền `#090d16`, EEVEE (nhanh) hoặc Cycles OptiX. Xuất `clockwork/<slug>_preview_1080p.png` `1920×1080`.
- **[MODIFY]** `projects.rs`: `ClockworkConfig.preview_render_path: Option<String>` có `#[serde(default)]`; thêm vào `types.ts`.
- **[MODIFY]** `gpu_queue.rs`: thêm mode `render_preview_card` (worker `blender`). **Không** tự gọi khi `rescan_projects`. Chỉ xếp hàng khi (a) `assemble_glb`/`sculpt`/`optimize` vừa xong, hoặc (b) người dùng bấm "Tạo ảnh xem trước", hoặc (c) ảnh thiếu hay `mtime(glb) > mtime(png)` lúc mở dự án. Trường hợp (c) thì xếp hàng nền, không chặn UI.
- **[MODIFY]** `RealPbrStageViewport.svelte`, `ProjectsStagePanel.svelte`: `stage3dActive` (mặc định `false` nếu Q2 = bật).
  - Thẻ chờ `data-testid="pbr-2d-standby-card"`: ưu tiên `preview_render_path ?? manga_plates[0]?.beauty_path ?? concept`, chuyển nhanh sang concept, thông tin `partsMeta`, BGM, Intro.
  - Nút `▶ Bật Sân Khấu 3D` (`activate-3d-stage-btn`) và `⏹ Ngắt 3D` (`deactivate-3d-stage-btn`).
  - Đổi dự án thì giữ nguyên trạng thái 3D người dùng đã chọn trong phiên (đỡ phải bấm lại; renderer dùng chung nên rẻ). Nhận `akunarch:release-webgl-vram` thì về 2D.
- Tương tự cho `OpenWorldChunkWorkbench` (`chunk-2d-standby-card` dùng `manga_plates[0].beauty_path`, đã có trên đĩa cho cả 2 chunk; `activate-chunk-3d-btn` / `deactivate-chunk-3d-btn`). `VnDirectorStagePanel` đã mặc định `play` (2D) nên giữ nguyên.
- Chạy `render_preview_card` cho 4 kỳ quan qua `GpuJobQueue`, rồi **đặt từng ảnh preview cạnh ảnh concept gốc** để tự kiểm định (Luật #7).

### C3. Hot-swap & nghiệm thu tổng
- Tắt hẳn `akunarch.exe` và `Selorson Admin\app.exe` đang chạy (kiểm `Get-Process`).
- **Sao lưu** `akunarch.exe` và `app.exe` thành `*.bak-<yyyyMMdd-HHmm>` cùng thư mục.
- Build `--release --features custom-protocol` (Akunarch) và `desktop-admin --release --features tauri/custom-protocol` (Selorson), rồi chép đè.
- Mở lại ở chế độ người dùng thật; nếu không khởi động được thì **khôi phục `.bak` ngay** và ghi lại lỗi.
- Chạy đủ 5 kịch bản (mục 6), xuất `E:\Akunarch\docs\vram\walkthrough_final.md` gồm bảng **baseline A0 → sau A → sau B → sau C**.

### ⏸ ĐIỂM DỪNG C (kết thúc)

---

## 6. Năm Kịch Bản Đo (dùng chung cho cả 3 đợt, cùng một script `measure_vram.ps1`)

| # | Kịch bản | Thao tác | Chỉ tiêu PASS (tương đối) |
|---|---|---|---|
| 1 | Cold boot | Mở `akunarch.exe`, chờ 10 s | Sau C (2D mặc định): `0` context WebGL (kiểm qua CDP: không có canvas WebGL trong DOM, cộng cờ trạng thái của `webgl-stage`). App VRAM ≤ baseline nền WebView2 `+15 MB`. |
| 2 | 3D bật, đứng yên | Bật 3D `temple-of-zyberon`, xoay 3 s, buông chuột, đo 10 s | Trung bình `utilization.gpu` ≤ mức nền máy (app tắt) `+2` điểm; pstate về giống nền. App VRAM ≤ **60% baseline A0** (sau A); sau B thì ≤ **40% baseline A0**. |
| 3 | Chuyển liên hoàn | 10 dự án × tab `01→02 (3D + splat)→03 (rig3d)→01`, lặp 3 vòng | App VRAM cuối vòng 3 ≤ cuối vòng 1 `+30 MB`. `0` `webglcontextlost`. `0` "Too many active WebGL contexts". |
| 4 | Ngắt / 🧹 / bật lại | `⏹` rồi `🧹`, bật/tắt 3D 30 lần | Sau `⏹` + 300 ms: App VRAM ≤ mức kịch bản 1 `+20 MB`. Lần bật thứ 30 lên hình trong ≤ 1.5 s. `0` context lost. |
| 5 | Selorson Admin | `/world` → Thế giới mở WASD 30 s → `/stories`, chờ 3 s | VRAM của cây tiến trình `app.exe` sau khi rời ≤ mức trước khi vào `/world` `+20 MB`. |

**Ghi chú đo lường:** mỗi kịch bản chạy **3 lần**, báo cáo trung vị. Trong lúc đo không mở thêm ứng dụng GPU khác; ghi lại danh sách tiến trình GPU nền vào CSV. Kịch bản #1 và #4 chỉ áp dụng đầy đủ sau Đợt C (khi có chế độ 2D); ở Đợt A/B ghi số đo để so sánh.

---

## 7. Lệnh `/goal` Cho Từng Đợt (dán riêng từng lệnh, chạy xong một đợt mới dán đợt sau)

```text
/goal ĐỢT A — Cầm máu VRAM cho Akunarch (E:\Akunarch) theo đúng mục 3 của
E:\Akunarch\docs\vram\implementation_plan.md
- Bắt buộc đọc trước: implementation_plan.md (đặc biệt mục 0 Audit và mục 2 Nguyên tắc), E:\Akunarch\AGENTS.md, E:\Selorson-Ecosystem\AKUNARCH_MASTER_PLAN.md, E:\Selorson-Ecosystem\SELORSON_WORLD_3D_VN_ROADMAP.md (cấm WEBGL_lose_context / forceContextLoss).
- Làm theo thứ tự A0 (đo baseline TRƯỚC khi sửa) → A1 → A2 → A3 → A4 → A5 → A6 → A7 → A8. Viết test webgl-dispose.test.mjs TRƯỚC khi viết dispose.ts.
- Không sửa Rust, không hot-swap, không đụng E:\Selorson, không đụng Co-Writer.
- Chạy tự chủ trong phạm vi Đợt A. Kết thúc bằng E:\Akunarch\docs\vram\walkthrough_dot_A.md (bảng baseline và sau sửa, ảnh đối chiếu cùng góc máy, mục chưa đạt nếu có) rồi DỪNG chờ duyệt.
- Số đo phải là số thật từ measure_vram.ps1; mục nào không đạt thì ghi rõ không đạt, cấm điều chỉnh tiêu chí.
```

```text
/goal ĐỢT B — Đo VRAM đúng phần App (PDH) + Pipeline KTX2 cho Akunarch theo mục 4 của implementation_plan.md (cùng đường dẫn).
- Điều kiện: Đợt A đã được duyệt (walkthrough_dot_A.md).
- Quyết định đã chốt: Q1 = <windows-sys | FFI tay>, Q3 = _master/, Q4 = chuyển sang E:\Akunarch\_archive\.
- B1 → B2 → B3 → B4. Không ghi đè clockwork/_master/. Kiểm định ảnh trước/sau KTX2 cho cả 4 kỳ quan cùng góc máy (Luật #7).
- Kết thúc bằng walkthrough_dot_B.md rồi DỪNG chờ duyệt.
```

```text
/goal ĐỢT C — Selorson V3 + Chế độ Chờ 2D + Hot-swap & nghiệm thu tổng theo mục 5 và 6 của implementation_plan.md (cùng đường dẫn).
- Điều kiện: Đợt B đã được duyệt. Q2 = <bật mặc định | tùy chọn>.
- C1 → C2 → C3. Sao lưu .bak trước khi chép đè akunarch.exe và Selorson Admin\app.exe; app không khởi động được thì khôi phục ngay.
- Đo đủ 5 kịch bản mục 6 ở chế độ người dùng thật (Luật #2), chụp ảnh nghiệm thu, xuất E:\Akunarch\docs\vram\walkthrough_final.md với bảng A0 → A → B → C.
```

### 7.1 Lệnh GỘP Đợt B + C (anh chọn ngày 2026-11-13 — chạy một mạch, không dừng giữa B và C)

> **Bản chính thức (< 4000 ký tự, vừa giới hạn `/goal`):** [`goal_dot_BC.txt`](goal_dot_BC.txt). Khối bên dưới là bản đầy đủ chữ hơn, cùng nội dung.

```text
/goal ĐỢT B + C GỘP — Hoàn tất Kế hoạch VRAM v2 cho Akunarch (E:\Akunarch) và Selorson V3 (E:\Selorson), chạy MỘT MẠCH từ B0 tới C3, không dừng chờ duyệt giữa B và C.

ĐỌC TRƯỚC (bắt buộc):
1) E:\Akunarch\docs\vram\implementation_plan.md — mục 0 (Audit), 1 (Q1–Q4 đã chốt), 2 (Nguyên tắc), 4 (Đợt B), 5 (Đợt C), 6 (5 kịch bản đo) và các dòng "⚠️ Đính chính" / "✅ Đã đo".
2) E:\Akunarch\docs\vram\walkthrough_dot_A.md — đặc biệt mục 4 (VRAM tab 01 chủ yếu là texture .glb), mục 8 (việc chưa kiểm), mục 9.
3) E:\Akunarch\AGENTS.md, E:\Selorson-Ecosystem\AKUNARCH_MASTER_PLAN.md, E:\Selorson-Ecosystem\SELORSON_WORLD_3D_VN_ROADMAP.md (cấm WEBGL_lose_context / forceContextLoss).

QUYẾT ĐỊNH ĐÃ CHỐT: Q1 = windows-sys · Q2 = Chờ 2D BẬT mặc định · Q3 = bản gốc .glb vào clockwork\_master\ (bản KTX2 giữ nguyên tên <slug>.glb) · Q4 = temple_of_zyberon.glb trùng chuyển sang E:\Akunarch\_archive\ (không xóa).

THỨ TỰ:
B0. Kiểm 3 việc còn treo của Đợt A trên bản target-dotA: (a) nút 📸 Chụp Phông Nền Manga 2K ở tab 01/02/03 — SAO LƯU toàn bộ thư mục manga_plates\ của các dự án liên quan trước, khôi phục + so SHA-256 sau; (b) chụp so sánh hình tab 03 Camera Rig 3D trước/sau; (c) nút Ultra và nút Thước/Lưới/Wireframe có tác dụng thật. Lỗi nào phát hiện thì sửa ngay, có test.
B1 → B2 → B3 → B4 theo mục 4 (PDH vram_win32.rs bằng windows-sys, lọc theo LUID RTX 4080; Topbar VRAM App vs Máy; đỉnh VRAM job lấy mẫu 1 s; nhường VRAM trước job GPU nặng; KTX2 cho 4 kỳ quan + KTX2Loader + basis transcoder offline trong static\basis\). Xuất E:\Akunarch\docs\vram\walkthrough_dot_B.md rồi ĐI TIẾP sang C, không dừng.
C1 → C2 → C3 theo mục 5 (Selorson V3: WorldOpenRealm/WorldCanvas/textures/geo-data; Chờ 2D + ảnh preview Blender qua GpuJobQueue + nút ▶ Bật / ⏹ Ngắt 3D; hot-swap cả 2 bản; nghiệm thu).

AN TOÀN (bắt buộc):
- C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe là HARD LINK tới app\src-tauri\target\release\akunarch.exe. Mọi bản build để thử/đo dùng CARGO_TARGET_DIR=E:\Akunarch\app\src-tauri\target-dotA. Kiểm SHA-256 exe đang cài trước/sau mỗi lần build. Kiểm tương tự với C:\Users\Admin\AppData\Local\Selorson Admin\app.exe trước khi build Selorson.
- Hot-swap CHỈ ở C3: tắt hẳn app đang chạy → sao lưu *.bak-<yyyyMMdd-HHmm> → chép đè (tách hard link: xóa tên cũ rồi chép file mới) → mở thử ở chế độ người dùng thật; không khởi động được thì khôi phục .bak ngay và ghi lỗi.
- KTX2: không bao giờ ghi đè clockwork\_master\; so ảnh trước/sau cùng góc máy cho cả 4 kỳ quan (Luật #7); nếu hình xuống cấp thấy rõ (vệt khối, sai màu normal) thì dùng UASTC cho kênh đó, không chấp nhận hình xấu đi.
- Mọi kịch bản đo ghi vào dữ liệu thật (điêu khắc, chụp Manga) phải sao lưu trước, khôi phục + so SHA-256 sau.
- Co-Writer chỉ đọc (SQLITE_OPEN_READ_ONLY); gói đồng bộ Selorson vẫn Draft-First (is_active = false). Không sửa các phát hiện ngoài phạm vi ở mục 0.3 — chỉ ghi lại.
- Công cụ tải về (gltf-transform qua npm, KTX-Software từ GitHub release chính thức của KhronosGroup) cài cục bộ trong E:\Akunarch\bin\tools\, không thêm vào Cargo.toml / package.json của app.

CHỈ DỪNG SỚM KHI: test đỏ không sửa được; khôi phục dữ liệu lệch SHA-256; KTX2 làm hỏng hình không khắc phục được; bản hot-swap không khởi động được (đã khôi phục .bak). Khi dừng sớm: ghi rõ lý do + trạng thái vào walkthrough tương ứng.

KIỂM THỬ: cargo test + npm run check + npm run build + npm test ở E:\Akunarch; npm run check + npm run build + npm run test:runtime ở E:\Selorson\frontend-v3; cargo test ở E:\Selorson\backend-v3. Tất cả phải xanh trước C3.

ĐO & NGHIỆM THU: dùng E:\Akunarch\bin\scripts\measure_vram.ps1 + E:\Akunarch\app\ui\tests\vram-scenarios.mjs (mở rộng cho ⏹ Ngắt 3D, chế độ Chờ 2D và kịch bản 5 Selorson Admin). Lượt nghiệm thu cuối ở C3: đủ 5 kịch bản mục 6, MỖI kịch bản 3 lần lấy trung vị, trên bản đã hot-swap, chế độ người dùng thật (Luật #2). Số đo là số thật; mục nào không đạt ghi rõ KHÔNG ĐẠT, cấm điều chỉnh tiêu chí.

KẾT THÚC: E:\Akunarch\docs\vram\walkthrough_final.md gồm bảng A0 → A → B → C cho từng kịch bản, ảnh đối chiếu cùng góc máy, danh sách đã thay đổi, mục không đạt, mục chưa kiểm, và đường dẫn các file .bak để quay lại bản cũ. Sau đó DỪNG.
```
