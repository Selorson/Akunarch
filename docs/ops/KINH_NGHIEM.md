# Kinh nghiệm vận hành Akunarch (quy trình, dùng cho mọi lần chạy)

> Ghi bài học **về cách chạy dự án**, không ghi chi tiết riêng của một công trình. Mỗi mục: việc nên làm, lý do, nguồn (ngày, agent). Mới nhất ở cuối mỗi nhóm.

## 1. Mở phiên

- **Thứ tự đọc:**
  1. `E:\Akunarch\AGENTS.md`
  2. `E:\Selorson-Ecosystem\AKUNARCH_MASTER_PLAN.md`, mục 6
  3. File này
  4. 5 dòng đầu `NHAT_KY_TONG.md`
  5. `implementation_plan.md` + `ledger.md` của đợt đang làm

  Ledger là "trí nhớ" của đợt: task nào đã ghi "xong" thì không làm lại. *(2026-11-13, Claude)*
- **Điều khiển app qua MCP `akunarch`** (16 tool), không bấm giao diện:
  - Tool tự mở `akunarch.exe` kèm cổng điều khiển.
  - Nếu anh đã mở app từ Desktop, tool tự đóng nhẹ rồi mở lại (anh cho phép).
  - Phiên mới mới thấy tool. Phiên cũ dùng script Node import `E:\Akunarch\mcp\akunarch-mcp\src\*.mjs`.

  *(2026-11-13, Claude)*

## 2. GPU, CPU & nhiệt độ máy

- **Mọi job GPU** (Blender render, Hunyuan, ComfyUI, TTS) đi qua `gpu_enqueue`. Không gọi Blender render trực tiếp.
- **Dựng hình Blender không render** (chỉ tạo lưới + xuất `.glb`, khoảng 15 giây) là việc CPU, chạy trực tiếp được để gỡ lỗi. *(2026-11-13, Claude)*
- **Phần lớn việc nặng là CPU, không phải GPU:**

  | Việc | Thời gian | Cách chạy |
  |---|---|---|
  | Nén KTX2 UASTC mức 4 | ~30–40 phút / công trình | 2 job × 2 luồng |
  | Biên dịch Rust | | Luôn `cargo … -j 8` (32 luồng gây đỉnh nhiệt) |

  **Báo anh trước** mọi việc CPU nặng trên 5 phút. Không chạy 2 việc nặng cùng lúc. *(2026-11-13, Claude)*
- **⚠ KTX2: CHẠY và DỪNG (anh chốt 2026-11-14, áp dụng cho mọi agent):**
  1. Chỉ chạy `optimize_glb_runtime` khi anh **nói rõ cho chạy** VÀ **nói rõ bản nào** (bản thật / bản cơ khí / công trình nào). Không tự chạy, kể cả khi anh dặn "làm dứt điểm, đừng hỏi". Xong việc thì báo "chờ anh cho chạy KTX2 bản …".
  2. Anh bảo dừng một job **đã chạy được một lúc** (KTX2, render, build dài) → **hỏi lại trước khi dừng**: "Job #N (bản …) đã chạy X phút, dừng thì phải chạy lại từ đầu, anh chắc chắn dừng không?". Có nhiều job thì nêu rõ từng job. Job còn `queued` thì huỷ theo lời anh được.
  3. Câu anh nói không rõ phạm vi → hỏi lại, đừng đoán.
  *Lý do: 2026-11-14 Claude tự chạy KTX2 khi anh còn soi bản cơ khí, rồi lỡ dừng cả KTX2 bản thật (đã duyệt) khi anh chỉ muốn hoãn bản cơ khí. KTX2 không nối tiếp được, dừng là mất trắng ~20 phút CPU.*
- **KTX2 chỉ chạy khi chốt bản cuối** (anh chốt 2026-11-13): dựng → ảnh xem trước tự chạy; nén bằng `gpu_enqueue(slug, 'blender', {mode: 'optimize_glb_runtime'})`. *(2026-11-13)*
- **Đừng để công cụ tắt/mở lại app khi hàng đợi đang chạy job.** App chết thì job bị đánh dấu hỏng, nhưng tiến trình con (KTX2) vẫn chạy mồ côi; job sau trong hàng đợi chạy chồng lên, gây 2 việc nặng cùng lúc. MCP đã có khoá (`busyJobsFromDb`). Chụp ảnh khi hàng đợi bận thì dùng phiên app đang có cổng điều khiển. *(2026-11-14, Claude)*
- **Sau mỗi job lỗi hoặc quá hạn, kiểm tiến trình mồ côi:** `Get-Process ktx,blender,node`. App bản `654c1504` trở đi đã tự giết cả cây khi quá hạn, nhưng vẫn nên kiểm. *(2026-11-13, Claude)*
- **App Claude desktop tự nó cũng ngốn CPU** khi hội thoại rất dài. Mỗi đợt lớn nên mở phiên mới. *(2026-11-13, Claude)*

## 3. Vòng làm một công trình (nhanh, rẻ, đúng Luật #7)

1. Phóng to từng vùng ảnh concept để **đếm chi tiết** và **đo tỷ lệ** (lấy mốc là cửa vào hoặc người). Ghi vào `docs/<đợt>/<tên>_design.md`.
2. **Dựng nháp** (CPU) ra `E:\Akunarch\_archive\<đợt>\scratch\*.glb`.
3. **Render ảnh xem trước qua hàng đợi** mà không gắn dự án: `gpu_enqueue(null, 'blender', {mode: 'render_preview_card', glb_path: <nháp>})`.
4. **Ghép cạnh concept:** `powershell -File E:\Akunarch\bin\scripts\compose_compare.ps1 -Left <concept> -Right <ảnh> -Out docs\<đợt>\screenshots\CMP_vN.png`. Soát từng mục trong danh mục, sửa, lặp lại. Mỗi vòng khoảng 2–3 phút.
5. **Đạt** thì `gpu_enqueue(slug, 'blender', {mode: 'assemble_glb'})` (ảnh xem trước tự chạy). **Chốt** thì chạy KTX2 tay, rồi chụp sân khấu trong app bằng `ui_open_project` + `ui_screenshot` để nghiệm thu theo Luật #2.

*(2026-11-13, Claude)*

- **Góc camera của ảnh xem trước thấp hơn concept**, nên công trình trông cao và mảnh hơn. Đừng sửa mô hình vì chuyện này; hãy so tỷ lệ bằng số đo. *(2026-11-13, Claude)*
- **Thư viện cũ `_aaa_monument_kit.init_blender_optix_scene()` tự `mkdir` `Selorson\frontend-v3\static\world\models`** (thư mục đã gỡ có chủ đích, làm test Selorson #91 đỏ). Script mới phải đặt `kit.MODELS_OUT_DIR` về thư mục xuất **trước** khi gọi init. *(2026-11-13, Claude)*
- **Ảnh 3D chụp từ app ra đen:**
  1. Kiểm cửa sổ có đang thu nhỏ không (WebView2 không vẽ GPU khi thu nhỏ). `ui_screenshot` đã tự bung cửa sổ ra.
  2. Kiểm `isContextLost()`.

  Đừng vội kết luận là lỗi mô hình. *(2026-11-13, Claude)*

## 4. Mã, test, cài đặt

- **TDD cho mọi thay đổi mã:** viết test, xem nó đỏ đúng lý do, sửa, xem nó xanh. Test viết cùng lúc với mã thì phải tự phá hoại có chủ đích một lần để chứng minh test bắt được lỗi.

  | Bộ test | Lệnh | Đạt (2026-11-13) |
  |---|---|---|
  | Akunarch Rust | `cargo test -j 8 --lib` | 31 |
  | Akunarch UI | `npm test` | 41 |
  | MCP | `npm test` | 22 + 1 bỏ qua |
  | Python clockwork | `python -m unittest discover -s tests` | 23 |
  | Selorson frontend | `npm run test:runtime` | 99 |
  | Selorson backend | `cargo test --lib` | 60 |

  *(2026-11-13, Claude)*
- **Thay app (hot-swap) Akunarch:**
  1. `npm run build`
  2. `CARGO_TARGET_DIR=…\target-p0 cargo build -j 8 --release --features custom-protocol`
  3. Tắt app → **xoá** bản cài → chép bản mới (không chép đè)
  4. So SHA → chạy `mcp\akunarch-mcp\tests\acceptance.live.mjs` (6/6)
  5. **Không giữ `.bak`** (anh chốt)

  *(2026-11-13, Claude)*
- **Mọi quyết định lệch kế hoạch** ghi vào ledger theo dạng `Ruling: <quyết định> — <lý do> — <cái giá nếu sai>`. *(2026-11-13, Claude)*

## 5. Shell trên Windows (bẫy đã gặp)

- **PowerShell:**
  - Nuốt `--` của lệnh native → dùng **Bash** cho `claude mcp add … -- node …`.
  - `R` là alias của `Invoke-History`, đừng đặt tên hàm là `R`.
  - Đường dẫn có `[ ]` (ví dụ `[slug]`) cần `-LiteralPath`.
  - Thay nhiều dòng trong file thì dùng **script Python** (`Path.read_text / replace / write_text`) hoặc tool Edit. `.Replace()` của PowerShell hỏng vì lệch CRLF/LF.
- **Lệnh gộp có `Remove-Item` cạnh chuỗi lạ** có thể bị hook an toàn chặn cả lệnh. Hãy tách `Remove-Item` thành lệnh riêng.
- **Lệnh chạy nền của Claude** bị dừng sau 30 phút. Việc dài hãy để hàng đợi của app chạy, rồi chờ bằng `gpu_wait` hoặc vòng poll ngắn.

*(2026-11-13, Claude)*

## 6. Đồng bộ, git, dữ liệu

- **Đẩy sang Selorson luôn phải hỏi anh** (trừ lần thử 2026-11-13). Luôn ở trạng thái Nháp.
- **Co-Writer chỉ đọc** (`cowriter_entity`, `cowriter_search`).
- **Repo Selorson (`frontend-v3`, `backend-v3`) có nhiều thay đổi chưa commit từ các phiên trước**, và mã mới phụ thuộc vào chúng. Không commit tách lẻ được, phải hỏi anh cách commit. *(2026-11-13, Claude)*
- **`E:\Akunarch` là git** (`main`, remote `https://github.com/Selorson/Akunarch.git`). `.gitignore` đã loại các thư mục build, `node_modules`, `repos/`, `_archive/`, media dự án, ảnh chụp đo đạc. Commit sau mỗi đợt. *(2026-11-13, Claude)*

## 7. GitHub & phát hành (2026-11-14, Claude)
- **Push `main` của `selorson-fe` / `selorson-be` = PHÁT HÀNH** (Cloudflare Pages / Fly.io tự deploy). Code dở → đẩy nhánh `wip/<ngày>-<việc>` (không workflow nào chạy). Kiểm bằng `gh run list -R <repo>` (chạy qua Bash, PowerShell làm hỏng chuỗi jq).
- **Hai tài khoản GitHub trên máy:** `selorsontales-ai` (chủ `selorson-fe`, `selorson-be`; cũng là tài khoản của `gh`) và **`Selorson`** (chủ `Akunarch`, `Neuro-Fox`, `ToneForge`). Git Credential Manager lưu sẵn cả hai. Remote của repo thuộc `Selorson` **phải ghi tên trong URL**: `https://Selorson@github.com/Selorson/<repo>.git`, rồi push bằng helper mặc định. **Đừng** ép `credential.helper=!gh auth git-credential` (sẽ dùng nhầm `selorsontales-ai` → 403). *(2026-11-14, Claude — đã từng chẩn đoán nhầm là "thiếu quyền")*
- Commit message có dấu ngoặc kép hoặc tiếng Việt dài → dùng `git commit -F <file>`; PowerShell tách sai tham số khi truyền `-m`.

## 8. Dọn dẹp cuối phiên (2026-11-14, Claude)
- Cuối phiên xoá: bản nháp `_archive\<đợt>\scratch\`, `clockwork\_master\history\`, thư mục build phụ (`target-*` tạo trong phiên), thư mục tạm `%TEMP%\akun_*`, `cwmini_*`, ảnh chẩn đoán `docs\<đợt>\screenshots\DIAG_*`. **Không xoá:** bản `_master`, bản runtime, dữ liệu dự án, `local-media` của Selorson.
- Script mới tạo thư mục tạm (`tempfile.mkdtemp`) **phải tự xoá** khi xong. Đã sửa 3 chỗ rò: `render_glb_preview_card.py` (mỗi lần để lại 1–1,6 MB), `assemble_mechanism_glb.py` / `render_mechanism_intro.py` (`kit.BAKED_DIR`), `tests/test_mechanism_glb.py`.

## 9. Model AI & ComfyUI (2026-11-14, Claude)
- **ComfyUI dùng bản `E:\Akunarch\repos\ComfyUI`**:
  - Môi trường `.venv`: Python 3.13, torch cu130.
  - Model nằm ở `D:\AI-Models`, ComfyUI đọc qua `extra_model_paths.yaml`.
  - Model mới cần thư mục mới (ví dụ `geometry_estimation`) thì thêm khoá vào yaml.
  - Lệnh chạy: `.venv\Scripts\python.exe main.py` (cổng 8188, hàng đợi GPU của app gọi `/free` tại đây).
- **Tìm file model của workflow:** xem template chính thức `Comfy-Org/workflow_templates/templates/<tên>.json` (trường `models[].url`). Chỉ tải đúng các file đó.
- **Tải file lớn:** chạy `bin\scripts\download_comfy_models.ps1` bằng `Start-Process` (tiến trình tách rời).
  - Dùng `curl -C -` để tải nối tiếp được; log ghi ở `D:\AI-Models\_download.log`.
  - Cách này không bị giới hạn 30 phút của lệnh chạy nền của Claude.
- **Đọc LICENSE gốc trước khi tải model mở trọng số.** Trang giới thiệu có thể nói sai hoặc thiếu. Ví dụ MiniMax H3: trang Q&A viết khó hiểu, nhưng LICENSE ghi rõ chỉ loại trừ EU, Anh, Hàn Quốc, Mỹ.
- **TRELLIS.2 có sẵn trong ComfyUI**, không cần WSL2. Template: `3d_pixal3d_trellis2_image_to_model`.

## 10. Bản cơ khí (2026-11-14, Claude)
- **Quy trình đầy đủ:** [`QUY_TRINH_BAN_CO_KHI.md`](QUY_TRINH_BAN_CO_KHI.md). Bản cơ khí dùng lại các hàm `build_*` của bản thật, đổi bộ vật liệu, rồi bỏ tường để lộ máy (danh sách `DROP` báo lỗi nếu thiếu tên).
- **Ảnh xem trước tối ở lòng công trình** (đèn studio không rọi vào trong). Khi nghi một bộ phận "mất" hay "nhỏ", đọc bounding box trong `.glb` trước; vòng 1 Eryndor tưởng tầng bánh răng bé, thật ra đúng 6,3 m nhưng quá mỏng.
- **Sân khấu app** đặt camera mỗi lần mở có thể khác nhau. Muốn ảnh nhịp so sánh được thì chụp liền trong một lần mở (`seekSec` qua `window.__akunarchStage`).
- **Server MCP chỉ nạp mã mới khi mở phiên mới.** Trong phiên đang chạy, gọi thẳng `src/*.mjs` bằng script Node.

## 11. ComfyUI, FLUX, TRELLIS.2 qua hàng đợi (2026-11-14, Claude)
- **Mode `comfy_workflow`** (worker `comfyui`) gọi `bin/scripts/comfy_run_workflow.py`:
  - tự bật ComfyUI ở cổng 8188 rồi tự tắt, xả VRAM sau mỗi job;
  - đổi tham số bằng `set: ['<node>.<input>=<JSON>']`;
  - file ra mặc định ở `projects/<slug>/comfy/`.
  Không chạy model ngoài hàng đợi (Luật #5). Bật máy chủ chỉ để xuất workflow (chưa chạy model) thì được.
- **Workflow mẫu là dạng giao diện** (nodes/links), máy chủ không nhận trực tiếp. Chuyển sang dạng API bằng chính giao diện ComfyUI: `app.loadGraphData(t)`, rồi `await app.graphToPrompt()` lấy `.output`. Lưu file qua `POST /api/userdata/workflows%2F<tên>.json`.
- **VRAM đo được** trên RTX 4080: FLUX.1-schnell fp8 đỉnh 15,8 GB (sát trần, đừng chạy kèm thứ gì); TRELLIS.2 int8 đỉnh 11,2 GB, khoảng 1,5 phút một chi tiết.
- **Poly Haven API trả 403 nếu thiếu header User-Agent.** Texture tải về đặt theo tên kit cần: `Diffuse_2k.jpg`, `AO_2k.jpg`, `Rough_2k.jpg`, `nor_gl_2k.jpg`.
- **Test bản thật đọc `_master` (bản gốc trước KTX2).** Dựng lại sau lần nén thì bản runtime mới hơn, nên test lấy bản mới nhất.
- **Viết prompt FLUX cho chi tiết để nặn:** "a single <chi tiết> cast in aged dark bronze with worn golden highlights, …, front orthographic view, centered, full object visible, isolated on a pure white background, studio product photography, sharp details, no text". Kích thước bội số 64 theo dáng (768×1152 tấm đứng, 640×1344 chóp, 1152×768 vòm ngang). *(2026-11-14, Claude)*
- **Mỗi chi tiết FLUX → TRELLIS.2 khoảng 3–4 phút GPU.** Xếp nhiều job vào hàng đợi một lượt để máy chạy liền, nhưng xem ảnh FLUX trước khi tin kết quả 3D. *(2026-11-14, Claude)*
- **Nhập `.glb` vào Blender bằng importer glTF thì object để `rotation_mode = 'QUATERNION'`.** Gán `rotation_euler` sau đó sẽ bị bỏ qua mà không báo lỗi. Phải đặt `rotation_mode = 'XYZ'` trước. v7 Eryndor dính lỗi này: cổng lệch 90°, anh phát hiện bằng mắt. *(2026-11-14, Claude)*
- **Ảnh xem trước chỉ có một góc 3/4**, nên chi tiết đặt sai ở mặt sau không lộ ra. Soát bằng nút "Xoay" của sân khấu (chụp 4 góc) trước khi chốt, rồi mới chạy KTX2. *(2026-11-14, Claude)*

## 12. ComfyUI riêng của anh (2026-11-14, Claude)
- **Hai bản, chung kho model:** bản Akunarch `E:\Akunarch\repos\ComfyUI` (cổng 8188, **không cài custom node**) và bản riêng `D:\ComfyUI-Rieng` (cổng 8189, có ComfyUI-Manager). Hướng dẫn cho anh: [`HUONG_DAN_COMFYUI.md`](HUONG_DAN_COMFYUI.md). `D:\Git-repo\ComfyUI` là junction trỏ vào bản Akunarch.
- **Cổng 8189 sống = anh đang dùng card:** hàng đợi Akunarch giữ mọi job ở `queued` kèm ghi chú "Chờ: ComfyUI riêng…". Job đứng mãi thì kiểm 8189 trước khi nghi lỗi. Test của hàng đợi phải trỏ `personal_comfyui_url` vào cổng đóng, không thì máy anh đang mở bản riêng làm test treo.
- **Dựng lại bản riêng nhanh:** `git clone E:\Akunarch\repos\ComfyUI D:\ComfyUI-Rieng` (clone cục bộ), `uv venv --python 3.13`, `uv pip install torch… --index-url …/cu130` (cache uv có sẵn, vài phút), `-r requirements.txt -r manager_requirements.txt`, chép `extra_model_paths.yaml`. Venv do uv tạo **không có pip**; Manager tự dùng uv.
- **Danh sách template chạy được ngay:** đọc `comfyui_workflow_templates_json/templates/index.json` + trường `models` trong từng workflow, đối chiếu `D:\AI-Models\<directory>\<name>`. Nhanh và chắc hơn soi giao diện.
- **MCP `gpu_jobs` / `app_status` có thể tự mở app.** Trước khi hot-swap, kiểm tiến trình cha của `akunarch.exe` (node `server.mjs` = do em mở, đóng được; khác thì có thể là anh đang dùng → hỏi).
- **Ảnh chụp từ Browser pane hay hết giờ** khi cửa sổ Claude bị che (viewport 0×0). Dùng `find` / `read_page`, hoặc chụp ngay sau khi mở trang.

