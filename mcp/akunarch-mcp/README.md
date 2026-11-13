# akunarch-mcp — cổng điều khiển AI cho Akunarch

MCP server (stdio, Node ≥ 22.13) giúp AI agent (Claude Code, Antigravity) thao tác Akunarch mà không cần ai bấm giao diện. Server mở `C:\Users\Admin\AppData\Local\Akunarch\akunarch.exe` (bản đã cài, dữ liệu thật) kèm cổng CDP `127.0.0.1:9241`, rồi gọi đúng các lệnh IPC của app qua `window.__TAURI__.core.invoke`. Vì vậy DB, `project.akun.json` và `GpuJobQueue` vẫn là của app. Bối cảnh: `E:\Selorson-Ecosystem\AKUNARCH_MASTER_PLAN.md` mục 6.

## Đăng ký

```bash
claude mcp add --scope user akunarch -- node --disable-warning=ExperimentalWarning E:\Akunarch\mcp\akunarch-mcp\src\server.mjs
```

Antigravity: khai báo cùng lệnh stdio này (`command: node`, `args: ["--disable-warning=ExperimentalWarning", "E:\\Akunarch\\mcp\\akunarch-mcp\\src\\server.mjs"]`) trong cấu hình MCP của Antigravity.

## Lưu ý vận hành

- App **đang mở sẵn mà không có cổng điều khiển** (ví dụ anh mở từ Desktop): anh đã cho phép (2026-11-13) nên tool **đóng app nhẹ nhàng** (gửi WM_CLOSE, sau 5 giây mới ép tắt), rồi **mở lại kèm cổng**. Dữ liệu không đổi.
- Cửa sổ app đang thu nhỏ thì WebView2 không vẽ nội dung GPU (ảnh 3D ra đen). `ui_screenshot` tự bung cửa sổ ra, chụp xong thu nhỏ lại.
- App do server mở chạy độc lập. Server dừng thì app vẫn mở.
- Cổng CDP không bật `--remote-allow-origins`, nên trang web trong trình duyệt không kết nối được vào app.
- `selorson_push_draft` luôn đẩy ở trạng thái **Nháp**. Agent phải hỏi tác giả trước mỗi lần đẩy.

## Tool

| Tool | Việc |
|---|---|
| `app_status` | App có chạy không, có cổng CDP không, SHA-256 của exe |
| `project_list` / `project_get` | Danh sách dự án / manifest đầy đủ |
| `project_patch` | Sửa manifest bằng patch gộp sâu, trường không nhắc tới giữ nguyên |
| `project_create` | Tạo dự án mới |
| `project_import_file` | Nhập ảnh concept, `.glb` hoặc nhạc vào dự án |
| `gpu_enqueue` / `gpu_wait` / `gpu_jobs` / `gpu_cancel` | Xếp, chờ, xem, huỷ job trong GpuJobQueue |
| `ui_open_project` | Mở dự án trên giao diện, tuỳ chọn bật sân khấu 3D |
| `ui_screenshot` | Chụp ảnh app → PNG (mặc định `E:\Akunarch\docs\p0\screenshots`) |
| `cowriter_entity` / `cowriter_search` | Đọc Co-Writer, chỉ đọc |
| `selorson_audit` / `selorson_push_draft` | Kiểm định / đẩy nháp sang Selorson |

## Test

```bash
npm test
```

Kiểm sống trên app thật (app phải đang đóng, hoặc đang mở kèm cổng CDP):

```powershell
$env:AKUNARCH_LIVE=1; node --test tests/app.live.test.mjs
```
