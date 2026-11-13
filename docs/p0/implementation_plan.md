# Đợt 0 (Cổng điều khiển `akunarch`) + P0 (Tháp Đồng Hồ Thiên Văn Eryndor — bản thật & bản cơ khí) — Kế hoạch triển khai

> **Cho agent thực thi:** BẮT BUỘC dùng skill `superpowers:subagent-driven-development` (khuyên dùng) hoặc `superpowers:executing-plans` để làm theo từng task. Các bước dùng checkbox (`- [ ]`).

**Mục tiêu:** Em (Claude) điều khiển được Akunarch hoàn toàn qua công cụ, không cần ai bấm tay. Sau đó dùng chính cổng đó để làm ra Tháp Eryndor ở 2 dạng: bản thật (khám phá, quay phim) và bản cơ khí chạy được (sa bàn, intro). Cả hai lên được Selorson dưới dạng bản nháp.

**Kiến trúc:** MCP server Node `akunarch` mở `akunarch.exe` (đúng bản cài, đúng dữ liệu thật) kèm cổng CDP. Mọi lệnh đi qua `window.__TAURI__.core.invoke(...)`, tức là đi đúng đường của 35 lệnh IPC sẵn có: cùng `GpuJobQueue`, cùng DB, cùng `project.akun.json`. Không cần viết lại logic Rust nào cho Đợt 0. Phần cơ khí là một thư viện Python thuần (toán bánh răng, đồ thị truyền động, bộ kiểm luật "không bánh răng trang trí") cộng các script Blender đọc một file đặc tả cơ cấu `*.mechanism.json` rồi dựng và gắn animation, xuất `.glb` có clip.

**Stack:** Node 22.23 (`@modelcontextprotocol/sdk`, `zod`, `ws`, `node:sqlite`), Blender 5.2 (Cycles OptiX, glTF exporter), Python stdlib `unittest`, Rust/Tauri v2 (`gpu_queue.rs`, `projects.rs`, `selorson_sync.rs`), SvelteKit 5 Runes + Three r178 (Akunarch), Threlte + Three r185 (Selorson frontend-v3).

**Đặc tả:** Mục 0 bên dưới. Nguồn là trao đổi với anh ngày 2026-11-13, tóm lại thành các quyết định đã chốt.

---

## 0. Đặc tả (quyết định đã chốt với anh)

1. **Cách anh làm việc:** anh không dùng giao diện trực tiếp. Em điều khiển Akunarch qua công cụ, giống cách Co-Writer làm kho lưu và truy xuất. Từ giờ **không đầu tư thêm giao diện**, chỉ giữ đủ để anh xem và duyệt.
2. **Đợt 0 xong khi:** em tạo hoặc sửa được dự án, chạy được 1 job GPU qua đúng hàng đợi của app, chụp được ảnh từ app, mà không ai bấm tay.
3. **Nguyên mẫu P0 là Tháp Đồng Hồ Thiên Văn Eryndor** (anh chọn vì tháp chưa có bản 3D): làm cả bản thật lẫn bản cơ khí.
4. **Bản cơ khí phải "cơ khí luôn", không phải đổi chất liệu.** Giống ở dáng, cơ khí ở cấu tạo. **Không có bánh răng trang trí**: bánh răng nào cũng ăn khớp và kéo một thứ gì đó. Bảng ánh xạ ở mục 0.1.
5. **Eryndor ở Trái Đất** (núi phía đông Ai Cập, vách đá vôi 1.600 m, tháp đá bazan thế kỷ XIV, sự kiện 00:00 ngày 01/01/2000), không liên quan hành tinh Akunalia. Co-Writer: `story_entities.id = 499`, `subject_key = 'thap dong ho thien van eryndor'`. Địa danh mẹ là `id = 13` (`place:eryndor`).
6. **Concept bản cơ khí:** em viết prompt, anh tạo ảnh bằng Gemini, ChatGPT hoặc ComfyUI tuỳ ý (theo BYOA). Luật #7: dựng 1:1 theo ảnh đã được anh duyệt.
7. **Không chép intro Game of Thrones:** chỉ học tinh thần sa bàn cơ khí. Phong cách riêng là **đồng hồ thiên văn Eryndor**.
8. Phương tiện, vùng địa hình lớn và nhân vật **không thuộc P0** (ghi ở mục 7).

### 0.1 Bảng ánh xạ bản thật → bản cơ khí (nguồn thiết kế cho P0.2 và P0.5)

| Bộ phận thật | Bản cơ khí | Nguồn |
|---|---|---|
| Vách núi đá vôi 1.600 m | Các lớp đá xếp thành đĩa xoay chồng, trục vít nâng cả tháp lên khỏi mặt sa bàn | canon |
| Thân tháp bát giác bazan, cửa sổ lancet Gothic, tường răng cưa | 8 tấm vách bazan gia công, viền đồng, bản lề piano; bung như cánh hoa để lộ mặt cắt | concept |
| Con lắc 4 m, tạ đá hoa cương | **Động cơ của cả sa bàn**: nhịp lắc → bộ thoát neo → bánh thoát → đoàn bánh răng → trục cam chính | canon |
| Cầu thang xoắn ốc đá vôi | Trục vít Archimedes, quay để đưa các khối lên | canon |
| Mặt đồng hồ thiên văn số La Mã, các mặt phụ | Chạy thật: vòng hoàng đạo, kim mặt trời, kim mặt trăng | concept + canon |
| Gác chuông 2 chuông | Búa gõ theo trống chốt kiểu hộp nhạc, chốt xếp theo điểm phát âm của `eryndor_pendulum_chime.wav` | concept |
| Quả cầu thiên văn trên đỉnh | Các vòng quay trên khớp cardan | concept |
| Tĩnh thất ngầm 12 cung hoàng đạo | Ngăn kéo thanh răng–bánh răng trượt ra từ chân móng | canon |
| Bệ đá giữ mảnh thiên thạch (concept 2, đã có ngàm) | Kết: kim chạm XII → mảnh đá rơi → ngàm kẹp đóng → vạch tím sáng | concept 2 + canon |
| Chất liệu | Bazan gia công có ốc và đinh tán, đồng thau ngả xanh, thép tôi xanh, chân kính hồng ngọc | — |

## Ràng buộc toàn cục

- Luật #1: không `BoxGeometry`/`CylinderGeometry` trơn giả công trình. Bánh răng phải có **biên dạng răng thân khai thật**, vát cạnh, nan hoa, PBR.
- Luật #2: ảnh nghiệm thu chụp từ `C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe` với dữ liệu thật. **Không** đặt `AKUNARCH_DATA_DIR`, `AKUNARCH_PROJECTS_DIR`, `WEBVIEW2_USER_DATA_FOLDER`. Chỉ thêm cổng CDP (tiền lệ: `app/ui/tests/vram-scenarios.mjs:7-8`).
- **CDP chỉ bind 127.0.0.1, cổng `9241`, KHÔNG dùng `--remote-allow-origins=*`.** Client Node không gửi header Origin nên vẫn kết nối được. Trang web lạ trong trình duyệt thì không.
- Luật #5: mọi job GPU đi qua `gpu_enqueue_job`. **Cấm** gọi Blender hay Hunyuan trực tiếp từ MCP.
- Luật #6: Co-Writer chỉ mở `?mode=ro` + `PRAGMA query_only = ON`. Đẩy sang Selorson luôn `forceDraft = true`, và **hỏi anh trước mỗi lần đẩy**.
- Luật #7: **cấm** đọc hoặc gọi `E:\Tools-3D\scripts\archived_selorson_monuments\assemble_singularity_eryndor_saqqara.py` (script cũ bị loại). Script mới viết tại `E:\Akunarch\bin\scripts\monuments\` (bản thật) và `E:\Akunarch\bin\scripts\clockwork\` (bản cơ khí). Chỉ dùng `_aaa_monument_kit.py` và `_monument_builders.py` làm thư viện. Hunyuan chỉ dùng cho chi tiết điêu khắc hữu cơ (đầu thú, mảnh thiên thạch).
- `akunarch.exe` đã cài là **hard link** tới bản build release. Build vào `CARGO_TARGET_DIR=E:\Akunarch\app\src-tauri\target-p0` và kiểm SHA-256 trước và sau. Hot-swap **chỉ khi anh đồng ý**, giữ file `.bak-<yyyymmdd-hhmm>`.
- Nén KTX2 và các việc CPU nặng: `--jobs 2 --threads 2` (máy từng lên 95 °C).
- `E:\Akunarch` không phải git → mỗi task ghi 1 dòng vào `docs/p0/ledger.md` thay cho commit. Selorson (`frontend-v3`, `backend-v3` là git): **không tự commit**, chỉ commit khi anh bảo.
- Test Python dùng `unittest` (máy không có pytest). Test chạy trong Blender dùng `blender.exe --background --python-exit-code 1 --python <test>`.
- Tỷ lệ bản thật: chiều cao tháp **34 m ±2** (ước từ concept: cửa vào cao khoảng 1/13 thân tháp, cửa thật 2,6 m). Bản cơ khí: tỷ lệ **1:40**, mặt sa bàn đường kính 1,6 m.
- Nhịp cơ khí (cách điệu cho sa bàn): **1 nhịp = 0,5 s**. Clip `assemble` dài **48 nhịp = 24 s**. Clip `idle` lặp **8 nhịp = 4 s**. 24 fps.

## Trọng tâm kiểm tra (Review Focus)

1. **App đang mở nhưng không có cổng CDP** (anh tự mở từ Desktop): công cụ phải báo lỗi rõ bằng tiếng Việt, không tự tắt app → test ở Task 0.1.
2. **`project_patch` làm mất trường manifest không được nhắc tới** (ví dụ `clockwork.preview_render_path`, `stage_vn`): mọi trường ngoài patch giữ nguyên → test ở Task 0.2.
3. **Job GPU lỗi hoặc treo** (Blender hết 900 s): `gpu_wait` trả `failed` kèm `error_log`, hoặc `timeout`, không treo MCP → test ở Task 0.3.
4. **Animation bị mất** sau `optimize_glb_runtime.ps1` (KTX2/BC7/Draco) hoặc sau khi đồng bộ bản `_master` → test ở Task P0.6.
5. **Đường dẫn có dấu tiếng Việt hoặc khoảng trắng** (`F:\FL studio\…`, tên dự án có dấu) đi qua `invoke` và qua tham số Blender không bị hỏng → test ở Task 0.1 và Task P0.1.

---

## Cấu trúc file

```
E:\Akunarch\mcp\akunarch-mcp\
  package.json                 # type: module; deps: @modelcontextprotocol/sdk, zod, ws
  src\server.mjs               # đăng ký tool MCP (stdio)
  src\cdp.mjs                  # client CDP (tách từ vram-scenarios.mjs:182-240)
  src\app.mjs                  # tìm/mở app, invoke, chụp ảnh, điều hướng UI
  src\projects.mjs             # mergeManifest, project_* tools
  src\gpu.mjs                  # pollUntilDone, gpu_* tools
  src\cowriter.mjs             # đọc co_writer.db chỉ-đọc
  src\selorson.mjs             # audit/push nháp
  tests\*.test.mjs             # node --test
E:\Akunarch\bin\scripts\clockwork\
  gear_math.py                 # toán bánh răng thuần (không bpy)
  mechanism.py                 # đặc tả cơ cấu, validate, solve_kinematics (không bpy)
  audio_onsets.py              # điểm phát âm từ wav (stdlib)
  gear_kit_blender.py          # dựng bánh răng/trục/bản lề trong Blender
  assemble_eryndor_clockwork.py
  render_mechanism_intro.py
  tests\test_gear_math.py, test_mechanism.py, test_audio_onsets.py
  tests\blender_test_eryndor_clockwork.py
E:\Akunarch\bin\scripts\monuments\
  eryndor_parts.py             # hàm dựng từng bộ phận tháp (dùng chung cho 2 bản)
  assemble_eryndor_clocktower.py
  tests\blender_test_eryndor_real.py
E:\Akunarch\projects\eryndor-clocktower-concept\
  concepts\prompts\*.md        # prompt cho anh tạo ảnh
  clockwork\eryndor.mechanism.json
E:\Akunarch\docs\p0\           # kế hoạch, ledger, thiết kế, ảnh nghiệm thu, walkthrough
```

---

# ĐỢT 0 — Cổng điều khiển `akunarch`

### Task 0.1: Kết nối app (mở, CDP, invoke, lỗi khi không có cổng)

**Files:**
- Create: `mcp/akunarch-mcp/package.json`, `src/cdp.mjs`, `src/app.mjs`
- Test: `mcp/akunarch-mcp/tests/app.test.mjs`

**Interfaces:**
- Produces:
  - `buildLaunchEnv(baseEnv: Record<string,string>, port = 9241) -> Record<string,string>`
  - `buildInvokeExpression(cmd: string, args: object) -> string`
  - `class AppNotDebuggableError extends Error`
  - `appStatus() -> Promise<{running: boolean, cdp: boolean, exePath: string, exeSha256: string}>`
  - `connectApp({launchIfClosed = true}) -> Promise<AppSession>`
  - `AppSession`: `invoke(cmd, args) -> Promise<any>`, `evaluate(expr) -> Promise<any>`, `screenshot({clip?}) -> Promise<Buffer>`, `close()`

- [x] **Step 1: Viết test thất bại**

```js
test('buildLaunchEnv chỉ thêm cổng CDP, gỡ biến dữ liệu tạm', () => {
  const env = buildLaunchEnv({ AKUNARCH_DATA_DIR: 'C:\\Temp\\x', AKUNARCH_PROJECTS_DIR: 'y', WEBVIEW2_USER_DATA_FOLDER: 'z', PATH: 'p' });
  assert.equal(env.AKUNARCH_DATA_DIR, undefined);
  assert.equal(env.AKUNARCH_PROJECTS_DIR, undefined);
  assert.equal(env.WEBVIEW2_USER_DATA_FOLDER, undefined);
  assert.match(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, /--remote-debugging-port=9241/);
  assert.match(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, /--ignore-gpu-blocklist --enable-webgl --enable-gpu-rasterization/);
  assert.doesNotMatch(env.WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS, /remote-allow-origins/);
  assert.equal(env.PATH, 'p');
});
test('buildInvokeExpression giữ nguyên chuỗi có dấu và khoảng trắng', async () => {
  const args = { sourcePath: 'F:\\FL studio\\toneforge\\Tháp đồng hồ "x".wav' };
  const expr = buildInvokeExpression('projects_import_external_file', args);
  let seen; globalThis.window = { __TAURI__: { core: { invoke: async (c, a) => { seen = [c, a]; return 1; } } } };
  await eval(expr);
  assert.deepEqual(seen, ['projects_import_external_file', args]);
});
test('app mở mà không có CDP → AppNotDebuggableError, không tắt app', async () => {
  const killed = [];
  await assert.rejects(
    connectApp({ probe: async () => ({ running: true, cdp: false }), kill: (p) => killed.push(p) }),
    (e) => e instanceof AppNotDebuggableError && /Akunarch đang mở nhưng không có cổng điều khiển/.test(e.message));
  assert.deepEqual(killed, []);
});
```

- [x] **Step 2: Chạy test, phải thất bại.** `cd E:\Akunarch\mcp\akunarch-mcp; npm install; node --test tests/app.test.mjs`. Kết quả mong đợi: FAIL (`buildLaunchEnv is not defined`).
- [x] **Step 3: Cài đặt.**
  - `cdp.mjs`: tách lớp `Cdp` từ `app/ui/tests/vram-scenarios.mjs:182-240` (send, eval, `Page.captureScreenshot`). File driver cũ giữ nguyên, không refactor.
  - `app.mjs`:
    - `buildInvokeExpression` trả về `` `window.__TAURI__.core.invoke(${JSON.stringify(cmd)}, ${JSON.stringify(args)})` ``.
    - `evaluate` dùng `Runtime.evaluate` với `awaitPromise: true, returnByValue: true`. Nếu có exceptionDetails thì ném lỗi kèm thông điệp gốc của app.
    - Nhận biết app đang chạy bằng `tasklist /FI "IMAGENAME eq akunarch.exe"`. Nhận biết CDP bằng `GET http://127.0.0.1:9241/json/list`.
    - Nếu app chưa chạy thì `spawn(EXE, [], {env: buildLaunchEnv(process.env), detached: true, stdio: 'ignore'})` rồi chờ target tối đa 30 s.
    - `connectApp` nhận `probe` và `kill` để test tiêm vào được. Thông điệp lỗi chính xác: `Akunarch đang mở nhưng không có cổng điều khiển. Anh đóng app giúp em để em mở lại kèm cổng điều khiển (dữ liệu không đổi).`
- [x] **Step 4: Chạy lại, phải xanh.** `node --test tests/app.test.mjs` → PASS 3/3.
- [x] **Step 5: Kiểm sống (cần app đóng sẵn).** `$env:AKUNARCH_LIVE=1; node --test tests/app.live.test.mjs`. Test live: `connectApp()` → `invoke('projects_list', {})` trả mảng chứa slug `eryndor-clocktower-concept`. `appStatus().exeSha256` khớp `Get-FileHash` của exe đã cài.
- [x] **Step 6: Ghi ledger** `docs/p0/ledger.md`: `0.1 | xong | <ngày> | 3+1 test`.

### Task 0.2: Công cụ dự án (list/get/patch/create/import)

**Files:**
- Create: `mcp/akunarch-mcp/src/projects.mjs`
- Test: `tests/projects.test.mjs`

**Interfaces:**
- Consumes: `AppSession.invoke` (Task 0.1)
- Produces:
  - `mergeManifest(current: object, patch: object) -> object`
  - `projectList(s) -> ProjectRecord[]`
  - `projectGet(s, slug) -> ProjectRecord` (có `.id`, `.manifest`). Lỗi `Không có dự án '<slug>'`.
  - `projectPatch(s, slug, patch) -> ProjectRecord` gọi `projects_update({manifest, originalSlug: slug})`
  - `projectCreate(s, input) -> ProjectRecord` gọi `projects_create({input})`
  - `projectImportFile(s, slug, assetKind, sourcePath, setPrimary = false)` gọi `projects_import_external_file({slug, assetKind, sourcePath, setPrimary})`. `assetKind` ∈ `concept|image|glb|model|clockwork|audio|bgm` (theo `projects.rs:1262-1266`).

- [x] **Step 1: Viết test thất bại**

```js
test('mergeManifest giữ mọi trường không có trong patch', () => {
  const cur = { slug: 'a', planet: 'akunalia', clockwork: { glb_path: 'g', preview_render_path: 'p', parts: [1, 2] }, stage_vn: { episode_title: 't' } };
  const out = mergeManifest(cur, { planet: 'earth', clockwork: { glb_path: 'g2' } });
  assert.equal(out.planet, 'earth');
  assert.equal(out.clockwork.glb_path, 'g2');
  assert.equal(out.clockwork.preview_render_path, 'p');
  assert.deepEqual(out.clockwork.parts, [1, 2]);
  assert.deepEqual(out.stage_vn, { episode_title: 't' });
});
test('mảng bị thay thế, null đặt về null', () => {
  const out = mergeManifest({ concept_paths: ['a', 'b'], lat: 1 }, { concept_paths: ['c'], lat: null });
  assert.deepEqual(out.concept_paths, ['c']);
  assert.equal(out.lat, null);
});
test('projectPatch gửi manifest đầy đủ và originalSlug', async () => {
  const calls = [];
  const s = { invoke: async (c, a) => { calls.push([c, a]); return c === 'projects_list' ? [{ id: 7, manifest: { slug: 'x', title: 'T', era: '' } }] : { id: 7 }; } };
  await projectPatch(s, 'x', { era: 'Thế kỷ XIV' });
  assert.deepEqual(calls[1], ['projects_update', { manifest: { slug: 'x', title: 'T', era: 'Thế kỷ XIV' }, originalSlug: 'x' }]);
});
```

- [x] **Step 2: Chạy, phải FAIL.** `node --test tests/projects.test.mjs`
- [x] **Step 3: Cài đặt.** Merge sâu chỉ với plain object. Mảng và giá trị nguyên thủy thì thay thế.
- [x] **Step 4: Chạy, phải PASS 3/3.**
- [x] **Step 5: Ghi ledger.**

### Task 0.3: Công cụ GPU (enqueue/jobs/wait/cancel)

**Files:**
- Create: `mcp/akunarch-mcp/src/gpu.mjs`
- Test: `tests/gpu.test.mjs`

**Interfaces:**
- Consumes: `AppSession.invoke`, `projectGet` (Task 0.2)
- Produces:
  - `gpuEnqueue(s, slug|null, workerKind, payload) -> GpuJobRow`: tra `project_id` từ `projectGet(slug).id`, gọi `gpu_enqueue_job({input: {project_id, worker_kind, payload}})`. Nếu có slug thì tự thêm `payload.project_slug`.
  - `pollUntilDone(fetchJob: () => Promise<GpuJobRow>, {intervalMs = 3000, timeoutMs = 1_800_000, sleep, now}) -> Promise<{status, output_path, error_log, vram_peak_mb}>`
  - `gpuWait(s, jobId, timeoutSec = 1800)`, `gpuJobs(s, limit = 20)`, `gpuCancel(s, jobId)`

- [x] **Step 1: Viết test thất bại** (đồng hồ giả, không ngủ thật):

```js
const mk = (seq) => { let i = 0; return async () => seq[Math.min(i++, seq.length - 1)]; };
const fake = () => { let t = 0; return { now: () => t, sleep: async (ms) => { t += ms; } }; };
test('completed trả output_path', async () => {
  const r = await pollUntilDone(mk([{ status: 'queued' }, { status: 'running' }, { status: 'completed', output_path: 'E:\\o.glb', error_log: '', vram_peak_mb: 9000 }]), fake());
  assert.equal(r.status, 'completed'); assert.equal(r.output_path, 'E:\\o.glb');
});
test('failed trả error_log', async () => {
  const r = await pollUntilDone(mk([{ status: 'failed', error_log: 'Blender hết 900 s' }]), fake());
  assert.equal(r.status, 'failed'); assert.match(r.error_log, /900 s/);
});
test('quá hạn trả timeout, không ném lỗi', async () => {
  const r = await pollUntilDone(mk([{ status: 'running' }]), { ...fake(), timeoutMs: 10_000 });
  assert.equal(r.status, 'timeout');
});
test('cancelled là trạng thái kết thúc', async () => {
  const r = await pollUntilDone(mk([{ status: 'cancelled' }]), fake());
  assert.equal(r.status, 'cancelled');
});
```

- [x] **Step 2: FAIL → Step 3: cài đặt → Step 4: PASS 4/4.**
- [x] **Step 5: Kiểm sống.** `gpuEnqueue(s, null, 'blender', {mode: 'probe', simulate_ms: 500})` → `gpuWait` → `completed`. Mode `probe` có sẵn ở `gpu_queue.rs:692`.
- [x] **Step 6: Ghi ledger.**

### Task 0.4: Điều hướng giao diện + chụp ảnh

**Files:**
- Modify: `mcp/akunarch-mcp/src/app.mjs` (thêm hàm)
- Test: `tests/ui.test.mjs`

**Interfaces:**
- Produces:
  - `screenshotPath(name: string, dir = 'E:\\Akunarch\\docs\\p0\\screenshots') -> string`: bỏ ký tự cấm Windows, giữ chữ có dấu, đuôi `.png`.
  - `uiOpenProject(s, slug, {stage3d = false}) -> {standby: boolean, partsCount: number}`: click `[data-testid="nav-projects"]`, rồi `[data-testid="project-card-<slug>"]`. Nếu `stage3d` thì click `activate-3d-stage-btn` và chờ `real-pbr-stage` có canvas (logic như `waitPbrStage`, `vram-scenarios.mjs:290`).
  - `uiScreenshot(s, name, {selector?}) -> {path, bytes}`: chụp toàn cửa sổ, hoặc clip theo `getBoundingClientRect` của selector.

- [x] **Step 1: Test thất bại:**
  - `screenshotPath('CMP: Tháp/thật?')` → `E:\Akunarch\docs\p0\screenshots\CMP_ Tháp_thật_.png`
  - `uiOpenProject` với session giả: thứ tự các lệnh `evaluate` gồm `nav-projects` rồi `project-card-eryndor-clocktower-concept`.
- [x] **Step 2: FAIL → Step 3: cài đặt → Step 4: PASS.**
- [x] **Step 5: Kiểm sống.** Mở Eryndor (đang ở thẻ Chờ 2D), chụp `D0_eryndor_standby.png`. File > 50 KB. Em mở ảnh ra xem để xác nhận đúng thẻ dự án.
- [x] **Step 6: Ghi ledger.**

### Task 0.5: Co-Writer chỉ đọc + Selorson nháp

**Files:**
- Create: `src/cowriter.mjs`, `src/selorson.mjs`
- Test: `tests/cowriter.test.mjs`, `tests/selorson.test.mjs`

**Interfaces:**
- Produces:
  - `openCowriterRO(path = %LOCALAPPDATA%\Co-Writer\co_writer.db) -> DatabaseSync`: `new DatabaseSync(path, {readOnly: true})` rồi `exec('PRAGMA query_only = ON')`.
  - `cowriterEntity(db, idOrKeyOrName) -> {id, subject_key, kind, name, summary, visual_anchor} | null`
  - `cowriterSearch(db, {kind?, query, limit = 20}) -> Entity[]`: `LIKE` trên `name` và `summary`, sắp theo `mention_count DESC`.
  - `selorsonAudit(s, slug)` gọi `sync_audit_project({slug, forceDraft: true})`
  - `buildPushArgs(slug, opts?) -> {slug, forceDraft: true, baseUrl: null}`: **luôn** `forceDraft: true`, bỏ qua mọi giá trị truyền vào.
  - `selorsonPushDraft(s, slug)` gọi `sync_push_project(buildPushArgs(slug))`

- [x] **Step 1: Test thất bại:**
  - Fixture: test tự tạo `co_writer` tạm trong `os.tmpdir()` có bảng `story_entities` và 2 dòng.
  - `cowriterEntity(db, 499)` trả đúng tên.
  - `db.exec("INSERT INTO story_entities(name) VALUES('x')")` phải ném lỗi (readonly).
  - `buildPushArgs('a', {forceDraft: false}).forceDraft === true`.
- [x] **Step 2: FAIL → Step 3: cài đặt → Step 4: PASS.**
- [x] **Step 5: Kiểm sống (chỉ đọc).** `cowriterEntity(db, 'thap dong ho thien van eryndor').id === 499`. **Không** đẩy sang Selorson ở bước này.
- [x] **Step 6: Ghi ledger.**

### Task 0.6: MCP server, đăng ký, nghiệm thu Đợt 0

**Files:**
- Create: `src/server.mjs`, `mcp/akunarch-mcp/README.md` (danh sách tool, 1 dòng mỗi tool)
- Test: `tests/server.test.mjs`

**Interfaces:**
- Tool MCP (tên chính xác):
  - `app_status`
  - `project_list`, `project_get`, `project_patch`, `project_create`, `project_import_file`
  - `gpu_enqueue`, `gpu_jobs`, `gpu_wait`, `gpu_cancel`
  - `ui_open_project`, `ui_screenshot`
  - `cowriter_entity`, `cowriter_search`
  - `selorson_audit`, `selorson_push_draft`
- `ui_screenshot` trả cả content `image/png` (base64) lẫn đường dẫn file, để em xem ảnh ngay.
- Mô tả tool `selorson_push_draft` ghi rõ: "Chỉ gọi sau khi anh đồng ý trong chat".

- [x] **Step 1: Test thất bại.** `server.test.mjs` khởi động server qua stdio bằng `Client` của SDK. `listTools()` trả đúng 16 tên trên. Gọi `project_patch` thiếu `slug` thì trả lỗi validate từ zod.
- [x] **Step 2: FAIL → Step 3: cài đặt → Step 4: PASS.**
- [x] **Step 5: Đăng ký (HỎI ANH TRƯỚC, vì đây là đổi cấu hình Claude Code):**

```bash
claude mcp add --scope user akunarch -- node E:\Akunarch\mcp\akunarch-mcp\src\server.mjs
```

- [x] **Step 6: Nghiệm thu Đợt 0.** Ở **phiên mới** (để tool được nạp), chỉ dùng tool MCP:
  1. `app_status`
  2. `project_get eryndor-clocktower-concept`
  3. `gpu_enqueue probe` rồi `gpu_wait` → `completed`
  4. `ui_open_project` + `ui_screenshot D0_acceptance`

  Ghi kết quả vào `docs/p0/walkthrough.md` mục "Đợt 0". **Đạt** khi cả 4 bước thành công mà không ai bấm tay.

---

# P0 — Tháp Đồng Hồ Thiên Văn Eryndor

### Task P0.1: Sửa dữ liệu dự án theo canon

**Files:**
- Backup: `E:\Akunarch\_archive\p0\before_data_fix\project.akun.json` + dòng `projects` của DB (xuất JSON) + `SHA256SUMS.txt`
- Thay đổi qua tool: `project_patch eryndor-clocktower-concept`

- [ ] **Step 1: Sao lưu** rồi ghi SHA-256.
- [ ] **Step 2: Patch.** Giữ nguyên slug, vì đổi slug sẽ kéo theo thư mục, DB và lịch sử job:

```json
{ "title": "Tháp Đồng Hồ Thiên Văn Eryndor", "title_en": "Eryndor Astronomical Clock Tower",
  "planet": "earth", "region_slug": "eryndor", "era": "Thế kỷ XIV · Giao thừa 2000", "era_year": 2000,
  "lat": 26.95, "lng": 33.50, "biome": "limestone-highland",
  "cowriter_entity_id": 499, "cowriter_key": "thap dong ho thien van eryndor",
  "description_vi": "Tháp đá bazan thế kỷ XIV trên vách đá vôi 1.600 m ở vùng núi phía đông Ai Cập; đỉnh tháp là cỗ đồng hồ thiên văn bằng đồng thau, con lắc neo 4 m; nơi mảnh thiên thạch đen giáng xuống lúc 00:00 ngày 01/01/2000.",
  "description_en": "A 14th-century basalt tower on a 1,600 m limestone cliff in the mountains east of Egypt, crowned by a brass astronomical clock with a 4 m anchor pendulum; where the black meteorite fell at 00:00 on 1 January 2000." }
```

  Toạ độ 26.95 / 33.50 là **tạm** (dãy núi ven Biển Đỏ). Anh chỉnh được bất cứ lúc nào.
- [ ] **Step 3: Kiểm tra.**
  - `project_get` khớp từng trường trong patch.
  - `clockwork.pack_version`, `audio_paths`, `concept_paths` không đổi.
  - SQL chỉ đọc: `SELECT planet, region_slug FROM projects WHERE slug='eryndor-clocktower-concept'` → `earth|eryndor`.
- [ ] **Step 4: Ghi ledger.**

### Task P0.2: Tài liệu thiết kế + prompt concept (cổng duyệt của anh)

**Files:**
- Create: `docs/p0/eryndor_design.md`: bảng 0.1, chuỗi truyền động mục P0.5 (dạng sơ đồ), dòng thời gian 48 nhịp, danh mục bộ phận bản thật kèm số lượng đếm từ concept.
- Create: `projects/eryndor-clocktower-concept/concepts/prompts/real_turnaround.md`: 4 góc (trước, bên, sau, trên). Bám sát concept hiện có, thêm vách đá vôi phủ sương muối theo canon.
- Create: `prompts/clockwork_hero.md`: bản cơ khí, **cùng góc 3/4 với concept gốc**.
- Create: `prompts/clockwork_cutaway.md`: mặt cắt hoặc phân rã cho thấy chuỗi truyền động từ con lắc tới các cơ cấu.

Mỗi prompt có bản tiếng Anh (để dán vào công cụ) và 1 dòng tiếng Việt tóm ý. Cấm nhắc "Game of Thrones" hay tên tác phẩm khác.

- [ ] **Step 1: Đếm chi tiết từ concept**, ghi vào `eryndor_design.md`: số mặt thân, số cửa sổ lancet nhìn thấy, 2 chuông, số tháp nhọn nhỏ (pinnacle), số đầu thú, mặt đồng hồ chính + số mặt phụ, quả cầu thiên văn, cửa và bậc thềm bên phải.
- [ ] **Step 2: Viết 3 prompt.**
- [ ] **Step 3: CỔNG DUYỆT.** Gửi anh prompt và tài liệu thiết kế. Anh tạo ảnh rồi gửi lại. Em nhập bằng `project_import_file(slug, 'concept', <path>)`. **Chưa có ảnh `clockwork_hero` được duyệt thì không bắt đầu P0.5.** P0.3 và P0.4 vẫn làm song song được.
- [ ] **Step 4: Ghi ledger.**

### Task P0.3: Thư viện cơ khí thuần (toán bánh răng + đặc tả cơ cấu + luật "không trang trí")

**Files:**
- Create: `bin/scripts/clockwork/gear_math.py`, `mechanism.py`, `audio_onsets.py`
- Test: `bin/scripts/clockwork/tests/test_gear_math.py`, `test_mechanism.py`, `test_audio_onsets.py`, `tests/fixtures/mini.mechanism.json`

**Interfaces:**
- `gear_math`:
  - `pitch_radius(module: float, teeth: int) -> float` (= m·z/2)
  - `base_radius(module, teeth, pressure_deg = 20.0) -> float`
  - `center_distance(module, z1, z2) -> float` (= m·(z1+z2)/2)
  - `involute_tooth(module, teeth, pressure_deg = 20.0, samples = 12) -> list[tuple[float, float]]` (biên dạng 1 răng, đối xứng qua trục X)
  - `escape_advance_deg(escape_teeth: int) -> float` (= 360 / (2·z) mỗi nhịp)
- `mechanism`: dataclass
  - `Gear(id, module, teeth, shaft, thickness, material)`
  - `Shaft(id, axis, origin)`
  - `Mesh(a, b)`
  - `Pendulum(id, shaft, escape_gear)`
  - `LeadScrew(id, shaft, pitch_mm, drives)`
  - `Hinge(id, shaft, drives, max_deg)`
  - `Rack(id, pinion, drives, travel_mm)`
  - `CamDrum(id, shaft, pins_beats)`
  - `Step(id, beats: tuple[int, int], part, action, target)`
  - `Mechanism(gears, shafts, meshes, …, steps, beats_total = 48)`
- `load_mechanism(path: str) -> Mechanism`
- `validate(m: Mechanism) -> list[str]` (rỗng = hợp lệ). Thông điệp có `id` bộ phận.
- `solve_kinematics(m, beat: float) -> dict[str, float]`: góc (độ) cho trục và bánh răng, dịch chuyển (mm) cho vít, thanh răng và bản lề.
- `detect_onsets(wav_path: str, min_gap_s = 0.12, window_ms = 10) -> list[float]`: chỉ dùng stdlib `wave` + `array`. Đường bao RMS, ngưỡng tăng đột ngột.

- [ ] **Step 1: Test thất bại** (chỉ ghi các khẳng định):

```python
assert center_distance(2.0, 12, 36) == 48.0
assert base_radius(2.0, 12) < pitch_radius(2.0, 12)
pts = involute_tooth(2.0, 12); assert all(abs(y1 + y2) < 1e-6 for (_, y1), (_, y2) in zip(pts, reversed(pts)))  # đối xứng
assert escape_advance_deg(30) == 6.0
# test_mechanism (fixture mini: con lắc → bánh thoát 30T → 12T/36T → vít me pitch 2 mm)
assert validate(load_mechanism(MINI)) == []
assert any("trang trí" in e and "g_deco" in e for e in validate(with_extra_gear("g_deco")))   # bánh răng không ăn khớp, không kéo gì
assert any("không nối tới con lắc" in e for e in validate(with_island()))                   # cụm tách rời khỏi chuỗi truyền động
assert any("module" in e for e in validate(with_mesh(m1=2.0, m2=1.5)))                      # khác module mà ăn khớp
assert any("khoảng cách tâm" in e for e in validate(with_shaft_offset(+0.5)))                 # sai > 1% module
k = solve_kinematics(load_mechanism(MINI), beat=10); assert abs(k["g12"] + k["g36"] * 3) < 1e-6  # ngược chiều, tỉ số 3
# test_audio_onsets: tự sinh wav 44.1 kHz có tiếng click ở 0.50 / 1.25 / 2.00 s
assert all(abs(a - b) < 0.010 for a, b in zip(detect_onsets(tmp), [0.50, 1.25, 2.00]))
```

- [ ] **Step 2: Chạy, phải FAIL.** `cd E:\Akunarch\bin\scripts\clockwork; python -m unittest discover -s tests -p "test_*.py"`
- [ ] **Step 3: Cài đặt.** Định nghĩa "trang trí": bánh răng không nằm trong `Mesh` nào, **hoặc** nằm trên trục không kéo `LeadScrew`, `Hinge`, `Rack`, `CamDrum`, kim hay vòng quay nào, và cũng không truyền tiếp. Kiểm "nối tới con lắc" bằng BFS trên đồ thị (trục ↔ bánh răng ↔ ăn khớp).
- [ ] **Step 4: Chạy, phải PASS.**
- [ ] **Step 5: Ghi ledger.**

### Task P0.4: Tháp Eryndor bản thật (Blender, 1:1 theo concept + vách đá theo canon)

**Files:**
- Create: `bin/scripts/monuments/eryndor_parts.py`. Mỗi bộ phận là một hàm trả object có tên `ER_<bộ phận>`, dùng chung cho cả 2 bản.
  - `build_cliff`
  - `build_base_octagon`
  - `build_buttresses`
  - `build_lancet_windows`
  - `build_parapet`
  - `build_upper_body`
  - `build_clock_face`
  - `build_sub_dials`
  - `build_belfry`
  - `build_bells`
  - `build_pinnacles`
  - `build_spire`
  - `build_armillary`
  - `build_entrance_stairs`
  - `build_shaft_and_pendulum`
  - `build_spiral_stair`
  - `build_sanctuary`

  Hàm nào cũng nhận `scale: float = 1.0` (bản cơ khí truyền 1/40).
- Create: `bin/scripts/monuments/assemble_eryndor_clocktower.py` (theo khuôn `assemble_samos_olympus.py`: `kit.init_blender_optix_scene`, nướng AO, xuất Draco).
- Modify: `bin/scripts/bake_canonical_monument.py:23-28`: thêm `"eryndor-clocktower-concept": AKUNARCH_MONUMENTS_DIR / "assemble_eryndor_clocktower.py"`.
- Test: `bin/scripts/monuments/tests/blender_test_eryndor_real.py`

- [ ] **Step 1: Test thất bại (Blender headless).** Nạp `.glb` đầu ra rồi khẳng định:
  - Có đủ các object `ER_clock_face`, `ER_bell_L`, `ER_bell_R`, `ER_armillary`, `ER_pendulum`, `ER_spiral_stair`, `ER_sanctuary`, `ER_cliff`.
  - Chiều cao từ đáy móng tới đỉnh quả cầu ∈ [32, 36] m.
  - Số pinnacle, cửa sổ lancet và đầu thú **bằng đúng số đã đếm ở P0.2 Step 1**.
  - Tổng tam giác ≤ 600.000.
  - Mọi material có `baseColorTexture` (không có material màu trơn mặc định).
- [ ] **Step 2: Chạy, phải FAIL** (chưa có `.glb`): `"C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" --background --python-exit-code 1 --python bin\scripts\monuments\tests\blender_test_eryndor_real.py -- <glb>`
- [ ] **Step 3: Cài đặt** từng hàm `build_*` theo concept.
  - Đầu thú dùng Hunyuan qua `gpu_enqueue(slug, 'hunyuan3d', {mode: 'sculpt_hero_parts', filter: 'eryndor_gargoyle'})`. Trước đó thêm bộ `("eryndor_gargoyle", <ảnh cắt đầu thú từ concept>, <số mặt>)` vào `HERO_PARTS` trong `E:\Tools-3D\scripts\sculpt_hero_parts_gpu.py:20` (sao lưu file trước khi sửa).
  - Vật liệu: bazan đen xám, đồng thau ngả xanh (mặt đồng hồ, quả cầu), đá vôi phủ sương muối (vách).
- [ ] **Step 4: Dựng qua hàng đợi.** `gpu_enqueue(slug, 'blender', {mode: 'assemble_glb'})` rồi `gpu_wait`. Chuỗi tự chạy tiếp: `optimize_glb_runtime` → `render_preview_card` (`gpu_queue.rs:616-629`). Chạy lại test Step 1 → PASS.
- [ ] **Step 5: Đối chiếu Luật #7.**
  - `ui_open_project(slug, {stage3d: true})`, xoay về góc 3/4 giống concept, rồi `ui_screenshot P0_real_3q`.
  - Ghép cạnh concept thành `docs/p0/screenshots/CMP_real.png`.
  - Em tự soát từng dòng trong danh mục bộ phận. Lệch thì sửa và quay lại Step 4.
- [ ] **Step 6: CỔNG DUYỆT.** Gửi anh `CMP_real.png`. Anh duyệt xong mới khoá bản thật.
- [ ] **Step 7: Ghi ledger.**

### Task P0.5: Đặc tả cơ cấu Eryndor (`eryndor.mechanism.json`)

**Phụ thuộc:** P0.3 xong, ảnh `clockwork_hero` (và tốt nhất cả `clockwork_cutaway`) đã được anh duyệt.

**Files:**
- Create: `projects/eryndor-clocktower-concept/clockwork/eryndor.mechanism.json`
- Create: `projects/…/clockwork/eryndor_bell_pins.json` (điểm phát âm từ `audio/eryndor_pendulum_chime.wav`, đổi sang nhịp)
- Test: `bin/scripts/clockwork/tests/test_eryndor_mechanism.py`

Chuỗi truyền động bắt buộc:

```
con lắc → neo → bánh thoát → đoàn bánh răng → trục cam chính
                                                │
    ┌──────────┬──────────┬──────────┬──────────┼──────────┬──────────┬──────────┐
    ▼          ▼          ▼          ▼          ▼          ▼          ▼          ▼
 vít me     8 bản lề    vít        vòng       trống      cardan     thanh      ngàm
 nâng       vách        Archimedes đồng hồ    chốt       quả cầu    răng       bệ thiên
 vách đá               (cầu thang) (hoàng đạo, chuông    thiên văn  ngăn kéo   thạch
                                    mặt trời,                       tĩnh thất
                                    mặt trăng)
```

Dòng thời gian 48 nhịp:

| Nhịp | Sự kiện |
|---|---|
| 0–8 | Vách đá nâng lên |
| 6–16 | Thân tháp nâng lên |
| 14–24 | 8 vách bung ra |
| 20–30 | Cầu thang xoắn quay |
| 0–48 | Mặt đồng hồ chạy suốt |
| 28–36 | Ngăn kéo tĩnh thất trượt ra |
| 30–44 | Chuông gõ theo chốt |
| 44–46 | Kim chạm XII |
| 46–48 | Thiên thạch rơi, ngàm đóng, vạch tím sáng |

- [ ] **Step 1: Test thất bại:**

```python
m = load_mechanism(ERYNDOR)
assert validate(m) == []
assert m.beats_total == 48
k_end = solve_kinematics(m, beat=46)
assert abs((k_end["hand_hour"] % 360)) < 0.5            # kim giờ chạm XII ở nhịp 46
assert abs(solve_kinematics(m, beat=24)["hinge_wall_1"] - 110.0) < 0.5   # vách bung 110°
assert abs(solve_kinematics(m, beat=36)["rack_sanctuary"] - m.racks["rack_sanctuary"].travel_mm) < 0.1
assert all(0 <= b <= 48 for b in json.load(open(BELL_PINS))["beats"])
```

- [ ] **Step 2: FAIL → Step 3: viết JSON** theo ảnh đã duyệt. Chọn số răng sao cho tỉ số khớp đúng dòng thời gian. Dùng `detect_onsets` để sinh `eryndor_bell_pins.json`.
- [ ] **Step 4: PASS → Step 5: Ghi ledger.**

### Task P0.6: Dựng bản cơ khí + animation (Blender) và mode hàng đợi mới

**Files:**
- Create: `bin/scripts/clockwork/gear_kit_blender.py`:
  - `build_spur_gear(g: Gear, mat) -> Object`: đùn biên dạng `involute_tooth`, vát 0,08·m, 5 nan hoa, moay-ơ, lỗ trục.
  - `build_shaft(s, length, mat)`
  - `build_hinge(h, mat)`
  - `build_lead_screw(ls, mat)`
  - `build_rack(r, mat)`
  - `build_cam_drum(c, pins, mat)`
  - `build_jewel_bearing(at, mat)`
- Create: `bin/scripts/clockwork/assemble_eryndor_clockwork.py`. Tham số `-- --slug --mech --out`. Gọi `eryndor_parts.build_*(scale=1/40)`, cắt vách thành 8 tấm có bản lề, gắn bộ máy. Mỗi khung hình đặt keyframe từ `solve_kinematics`. Tạo 2 action `assemble` (48 nhịp) và `idle` (8 nhịp, lặp), xuất glTF kèm animation và Draco.
- Modify: `app/src-tauri/src/projects.rs`: `ClockworkConfig` thêm `#[serde(default)] pub mechanism_glb_path: Option<String>` (cập nhật `Default`).
- Modify: `app/src-tauri/src/gpu_queue.rs`:
  - Thêm mode `"assemble_mechanism_glb"` (khuôn như `assemble_glb`, `gpu_queue.rs:873-965`, timeout 1200 s). Ra file `clockwork/<slug>_mechanism.glb`, `bind_output_to_project(…, "mechanism_glb", …)`.
  - `follow_up_jobs`: `"assemble_mechanism_glb" => "optimize_glb_runtime"` với `glb_path` là file mechanism, **không** nối tiếp `render_preview_card`.
- Modify: `bin/scripts/optimize_glb_runtime.ps1` **chỉ khi** test Step 1 chứng minh nó làm rơi animation.
- Test:
  - `bin/scripts/clockwork/tests/blender_test_eryndor_clockwork.py`
  - Rust: `manifest_without_mechanism_field_still_loads`, `follow_up_chain_mechanism_then_optimize_only`
  - `app/ui/tests/glb-animations.test.mjs`

- [ ] **Step 1: Test thất bại:**
  - Blender: `.glb` có đúng 2 action `assemble` và `idle`. Mọi `Gear.id` trong JSON có object `CW_<id>`. Tại nhịp 0, 24, 46, góc của từng bánh răng khớp `solve_kinematics` (sai ≤ 0,5°). Tam giác ≤ 900.000. Không material màu trơn mặc định.
  - Node: `glb-animations.test.mjs` đọc chunk JSON của **cả** bản `_master` lẫn bản runtime sau optimize, khẳng định `animations.length === 2` và tên `['assemble', 'idle']`.
  - Rust: 2 test trên.
- [ ] **Step 2: Chạy, phải FAIL.** Blender như P0.4. `cd app\src-tauri; $env:CARGO_TARGET_DIR='E:\Akunarch\app\src-tauri\target-p0'; cargo test`. `cd app\ui; npm test`.
- [ ] **Step 3: Cài đặt.**
- [ ] **Step 4: Dựng qua hàng đợi.** `gpu_enqueue(slug, 'blender', {mode: 'assemble_mechanism_glb', mech_path: '<…>/eryndor.mechanism.json'})` rồi `gpu_wait`. Chạy lại toàn bộ test → PASS. `cargo test` giữ ≥ 25 pass như trước (thêm 2).
- [ ] **Step 5: Ghi ledger.**

### Task P0.7: Phát bản cơ khí trong Akunarch (tối thiểu, để duyệt và chụp)

**Files:**
- Create: `app/ui/src/lib/webgl/stage-variant.ts`: `pickStageGlb(manifest, variant: 'real' | 'mechanism') -> string | null` (mechanism không có file thì trả null).
- Modify: `app/ui/src/lib/components/RealPbrStageViewport.svelte`:
  - Nếu `.glb` có animation thì tạo `AnimationMixer`: phát `assemble` 1 lần, rồi lặp `idle`.
  - Thêm 1 công tắc `data-testid="stage-variant-toggle"` (Bản thật / Bản cơ khí).
  - Thêm hook điều khiển `window.__akunarchStage = { seek(sec), play(), pause(), variant(v) }` để chụp ảnh tất định.
  - Dispose mixer và action khi rời sân khấu, đúng quy tắc VRAM Đợt A (`webgl-dispose`).
- Modify: `mcp/akunarch-mcp/src/app.mjs`: `uiOpenProject(…, {variant, seekSec})`.
- Test: `app/ui/tests/stage-variant.test.mjs`

- [ ] **Step 1: Test thất bại.** `pickStageGlb({clockwork: {glb_path: 'a', mechanism_glb_path: null}}, 'mechanism') === null`, `…'real') === 'a'`.
- [ ] **Step 2: FAIL → Step 3: cài đặt → Step 4: PASS.** `npm run check` ra 0 lỗi 0 cảnh báo, `npm test` xanh hết.
- [ ] **Step 5: Kiểm VRAM nhanh.** Chạy lại kịch bản S2 và S4 (`vram-scenarios.mjs`) với Eryndor bản cơ khí. **Đạt**: 0 context bị mất, không cộng dồn sau 10 lần bật/tắt (V10 ≤ V1 + 30 MB).
- [ ] **Step 6: Ghi ledger.**

### Task P0.8: Video intro bản cơ khí

**Files:**
- Create: `bin/scripts/clockwork/render_mechanism_intro.py`. Phát action `assemble`.
  - Camera đi theo đường cong Catmull-Rom đã làm mượt (ý lấy từ skill metro: lấy mẫu dày rồi trung bình trượt), **camera không bao giờ đứng yên**. Kết bằng cận cảnh mặt đồng hồ ở nhịp 44–48.
  - Ánh sáng studio tối, nền `#090d16`.
  - Ghép `audio/eryndor_pendulum_chime.wav` bằng ffmpeg (`C:\Users\Admin\.local\bin\ffmpeg.exe`).
- Modify: `gpu_queue.rs` mode `render_intro_mp4`: nếu `payload.variant == "mechanism"` thì gọi script mới với `--glb <mechanism master> --out cinema/<slug>_mechanism_intro.mp4 --fps 24`, rồi gán vào `clockwork.intro_video_path`.
- Test: Rust `render_intro_variant_mechanism_picks_mechanism_script` (tách hàm chọn script/đầu ra thành hàm thuần để test được).

- [ ] **Step 1: FAIL → Step 2: cài đặt → Step 3: PASS.**
- [ ] **Step 4: Render qua hàng đợi.** 1920×1080, rồi kiểm tra bằng `ffprobe`: thời lượng 24 s ±0,5, có 1 luồng âm thanh, 24 fps.
- [ ] **Step 5: CỔNG DUYỆT.** Gửi anh video và 3 ảnh tĩnh (nhịp 12, 30, 47).
- [ ] **Step 6: Ghi ledger.**

### Task P0.9: Đưa lên Selorson (nháp) + trình xem sa bàn cơ khí

**Files:**
- Modify: `app/src-tauri/src/selorson_sync.rs:384-410`:
  - `local_clockwork_pack_path` = bản `_master` của `mechanism_glb_path` nếu có, ngược lại giữ như cũ.
  - `local_desktop_pack_path` = bản thật.
  - Test Rust `sync_payload_clockwork_pack_prefers_mechanism_master`.
- Kiểm tra (đọc mã, chưa sửa): `E:\Selorson\backend-v3` có lưu và trả `clockwork_pack_url` cho **location** không (hiện `types.ts:80` chỉ thấy ở region). **Luật quyết định:** nếu backend đã nhận `local_clockwork_pack_path` cho location và trả URL thì chỉ sửa frontend. Nếu chưa thì thêm trường vào đúng chỗ `desktop_pack_url` đang được lưu, kèm test `cargo test` tương ứng.
- Create: `E:\Selorson\frontend-v3\src\lib\world\ui\ClockworkPackViewer.svelte` (Threlte `<Canvas>` + GLTF + `AnimationMixer`: `assemble` 1 lần rồi lặp `idle`).
  - Bắt buộc dùng lại `ThrelteContextRelease.svelte` và `orbit-controls-release.ts` (bản sửa rò VRAM ngày 2026-11-13).
  - Chỉ hiện trong app desktop (dùng đúng cách phân biệt desktop/web mà `WorldOpenRealm.svelte` đang dùng).
- Modify: `src/routes/(app)/world/[region]/[slug]/+page.svelte`: thêm tab media "Sa bàn cơ khí" khi có `clockwork_pack_url` đuôi `.glb`.
- Test:
  - `frontend-v3/tests/clockwork-clip.test.mjs`: hàm thuần `pickClockworkClips(names: string[]) -> {intro: 'assemble' | null, loop: 'idle' | null}`.
  - Đo VRAM theo kiểu `vram-selorson-s5.mjs`: vào/ra trang 5 lần, **không cộng dồn** (canvas còn sống sau GC = 0).

- [ ] **Step 1: Test thất bại → Step 2: cài đặt → Step 3: PASS.** `npm run check` 0/0, `npm run test:runtime` xanh hết, `cargo test` (Akunarch + backend nếu có sửa) xanh.
- [ ] **Step 4: `selorson_audit` → HỎI ANH → `selorson_push_draft`.** Bản nháp `is_active = false`. Anh tự duyệt trong Admin.
- [ ] **Step 5: Ghi ledger.**

### Task P0.10: Nghiệm thu P0 + bàn giao

- [ ] **Step 1: Build và hot-swap (HỎI ANH TRƯỚC).**
  - Build Akunarch vào `target-p0`, Selorson Admin như thường lệ.
  - Kiểm SHA. Sao lưu `.bak-<yyyymmdd-hhmm>`, hot-swap, rồi so SHA bản cài với bản build.
- [ ] **Step 2: Chụp ảnh ở chế độ người dùng thật** (Luật #2) qua `ui_screenshot`, vào `docs/p0/screenshots/`:
  - `CMP_real.png`: concept ↔ bản thật.
  - `CMP_mechanism.png`: concept cơ khí ↔ bản cơ khí ở nhịp 47.
  - `MECH_beat_{00,12,24,36,47}.png`.
  - `SEL_location_clockwork.png` (Selorson).
- [ ] **Step 3: Viết `docs/p0/walkthrough.md`.**
  - Đạt / không đạt theo từng tiêu chí, kèm số liệu: test, tam giác, VRAM, thời lượng video.
  - Danh sách file đã đổi, cách quay lại bản cũ.
  - Ghi rõ những gì chưa làm (mục 7).
- [ ] **Step 4: Cập nhật memory** `vram-plan-v2-status`. Tạo memory mới `p0-eryndor-status` trỏ tới walkthrough.

---

## 7. Ngoài phạm vi (ghi lại để không quên, không làm trong P0)

- **Vùng khám phá Eryndor** (địa hình lớn quanh vách đá, đi WASD), Atlas địa điểm tự động từ Co-Writer, trạm dịch chuyển (lý do trong truyện do anh quyết).
- **Phương tiện theo thời đại:**

| Tuyến | Phương tiện |
|---|---|
| Ai Cập | Chiến xa, thuyền buồm sông Nile |
| Olympus | Chiến xa, thuyền chiến |
| Kyoto/Iga | Ngựa, kiệu kago, thuyền sông Kamo |
| Sài Gòn 2009 | Xe đạp, xe máy |
| Anh (Arya, Merlyn — Camelot thế kỷ VI) | Ngựa, xe bò, thuyền |
| Ấn (Dona Heracles — Núi Meru) | Voi, xe bò kéo, chiến xa |
| Celtic – Bắc Âu (Tom Feliscael — Dún Scáith) | Ngựa, thuyền gỗ, xe trượt băng |
| Akunalia | Anh quyết |

  Nhóm có bánh xe và thuyền làm trước. Nhóm động vật cần quy trình gắn xương và dáng đi, làm sau.
- Nhân vật 3D, đặt máy quay trong thế giới mở (phim trường), VN ngay trong vùng.
- Nội thất tĩnh thất ở kích thước thật để đi vào: P0 đã dựng hình học (`build_sanctuary`) dùng chung, nhưng chưa làm chiếu sáng nội thất hay tương tác.

## 8. Thứ tự và song song

```
0.1 → 0.2 → 0.3 → 0.4 → 0.5 → 0.6 ─┬─► P0.1 → P0.2 (chờ anh tạo ảnh) ──────► P0.5 → P0.6 → P0.7 → P0.8 → P0.9 → P0.10
                                    └─► P0.3 (song song, không cần ảnh) ───┘
                                    └─► P0.4 (song song, dùng concept cũ) ─┘
```
