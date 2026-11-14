# Ledger — đợt tối ưu tài nguyên

| Task | Trạng thái | Ghi chú |
|---|---|---|
| G2 | ✅ xong | `bin\scripts\measure_app_resources.ps1 -App <app|all> -Label <nhãn> -Seconds N`: RAM private/working set + VRAM (PDH, GPU rời) theo cây tiến trình, nhận diện cả WebView2 theo identifier và tiến trình mồ côi (khớp đường dẫn). Chỉ đọc số liệu. Chạy thử `-App all` (thụ động): NeuroForge 8 tiến trình · 468 MB private · 43 MB VRAM; app khác đang tắt |
| G1 | 🔄 đang làm | Khảo sát mã (chỉ đọc) — nghi vấn bên dưới |

## G1 — nghi vấn theo app (chưa đo, chưa sửa)

**Selorson** (`E:\Selorson\frontend-v3`)
- Sa bàn 3D: đã hết cộng dồn (đợt VRAM v2, 5 lần vào/ra 177→122 MB). Còn ~62 MB context chờ GC.
- **Thế giới mở WASD chưa đo thật** (máy chưa có chunk). Có thể đây đúng là chỗ anh gặp "mở lại bản đồ cộng dồn VRAM".
- ⚠ `WorldOpenRealm.svelte:446`: **mỗi lần vào thế giới mở tạo `new THREE.WebGLRenderer` (context WebGL mới)**. Lúc thoát (`stopRuntimeOnly`), mã dọn kỹ nhưng cố ý không `forceContextLoss`, nên context cũ chờ GC mới trả VRAM. Vào/ra nhanh nhiều lần thì cộng dồn, giống lỗi Sa bàn trước đây. → Hướng sửa: **một renderer dùng chung** suốt vòng đời trang (giống Akunarch S4). Đo cần có chunk thật trên máy (phải đồng bộ + duyệt nháp → hỏi anh) hoặc dữ liệu thử cục bộ.

**Co-Writer** (`D:\Git-repo\Co-Writer`)
- ✅ Tắt app: vỏ Tauri dùng Job Object (`shell/src-tauri/src/job.rs`), Windows dọn cả cây tiến trình.
- ⚠ Phiên ONNX `bge-m3-fp32` CUDA (`local_models/runtime.py` `_SESSIONS`) **giữ ~2.820 MiB VRAM** (số đo của chính Co-Writer) từ lần nhúng/tìm đầu tiên tới khi tắt app. → nhả khi rảnh N phút?
- ⚠ `sd-server.exe` (Z-Image, ~10,5 GB VRAM khi vẽ) bật tay, không ai tự tắt; nằm ngoài cây tiến trình của Co-Writer.
- Repo còn 58 thay đổi chưa commit → cách commit phải bàn trước khi sửa.

**ToneForge** (`F:\FL studio\toneforge`)
- ⚠ 4+ bộ tách stem ONNX GPU trong biến toàn cục `OnceLock<Mutex<Option<…>>>` (`mdx_onnx_gpu.rs:1025`, `uvr5_htdemucs.rs:243`, `uvr5_mdx_tfctdf.rs:194`, `uvr5_vr_aspp.rs:154`): nạp một lần là giữ VRAM tới khi tắt app.
- ⚠ Trọng số `OnceLock<Vec<f32>>` (`REAL_PROJECTION_WEIGHT_POOL`, `REAL_TFCTDF_WEIGHTS`, `REAL_ASPP_WEIGHTS`): không bao giờ giải phóng RAM.
- Thoát app (`main.rs:3308`): chỉ tắt luồng âm thanh + dọn cache WebView; cần kiểm `toneforge-host.exe` / plugin scanner có bị bỏ lại không.

**NeuroForge** (`E:\NeuroForge`, CHỈ BÁO CÁO)
- ~110 chỗ sinh tiến trình con (os_utils 19, fleet 16, antigravity_cli 12, video_forge 9, ocr_studio 8, playwright 7, brain 7, tts 6…).
- Chỉ `brain.rs` dùng Job Object; vài chỗ `kill_on_drop`; còn lại `taskkill` rải rác.
- ✅ Đóng cửa sổ chính (`lib.rs:991`, `WindowEvent::Destroyed`): tắt Antigravity CLI, OCR Studio, OmniVoice, VieNeu (chỉ server do app bật), rồi `std::process::exit(0)`.
- ✅ Server giọng do app bật **tự tắt sau 5 phút rảnh** (`tts.rs:1605` `reap_idle_voice_servers`).
- ⚠ Các tiến trình con khác (Playwright, ffmpeg/video_forge, Claude CLI, fleet, chatgpt_pilot, social…) **không được dọn khi thoát**. `std::process::exit` không chạy destructor nên `kill_on_drop` cũng không kích hoạt. Tắt app lúc đang làm việc → có thể còn mồ côi. Cần đo bằng `measure_app_resources.ps1 -App neuroforge` sau khi anh tự tắt app (em không tắt).

**ComfyUI**: bản Akunarch tự bật/tắt + `/free` sau mỗi job. Bản riêng: đóng cửa sổ là tắt (đã kiểm). Cần kiểm thêm khi anh tắt cứng.
