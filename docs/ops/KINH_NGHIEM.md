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
- **KTX2 chỉ chạy khi chốt bản cuối** (anh chốt 2026-11-13): dựng → ảnh xem trước tự chạy; nén bằng `gpu_enqueue(slug, 'blender', {mode: 'optimize_glb_runtime'})`. *(2026-11-13)*
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
- `gh` đăng nhập tài khoản `selorsontales-ai` (chủ `selorson-fe`, `selorson-be`). Repo `Selorson/Akunarch` thuộc tài khoản khác → cần lời mời collaborator (Write) rồi mới push được.
- Commit message có dấu ngoặc kép hoặc tiếng Việt dài → dùng `git commit -F <file>`; PowerShell tách sai tham số khi truyền `-m`.
