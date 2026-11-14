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
| G5a | 🔄 đang chạy | Anh cho theo dõi NeuroForge bài cuối (2026-11-14 22:04): `bin\scripts\monitor_neuroforge.ps1` chạy tách rời, ưu tiên thấp, mỗi 10 s. Chỉ đọc danh sách tiến trình + bộ đếm hiệu năng, không đọc DB, không gửi gì vào app. Log thô (có thể chứa tên bài) ở `_archive\toi-uu\neuroforge\` (ngoài git). Lúc bắt đầu: rảnh, 8 tiến trình, ~460 MB RAM, ~90 MB VRAM, đang chờ phiếu việc từ đội máy (ổ chia sẻ `outputs\Temp\Board`) |
| G5a | ✅ xong | Theo dõi NeuroForge 22:04–22:28 → [`BAO_CAO_NEUROFORGE.md`](BAO_CAO_NEUROFORGE.md). Anh tắt app → **0 tiến trình sót** |
| G3-CW | ✅ đo | Co-Writer nền (`scenarios/cowriter_resources.ps1`): mở 3,9 GB RAM / 0,81 GB VRAM → sau 1 lượt truy xuất **10,8 GB / 3,9 GB** → rảnh 5 phút **y nguyên** → tắt **0 sót** (Job Object). Bản cài chạy lõi Python **từ repo** (`D:\Git-repo\Co-Writer\app\core\.venv`), không phải `cowriter-core.exe` |
| G4-CW | ✅ xong | Nhả phiên ONNX khi rảnh 600 s (`local_models/runtime.py` `touch()`/`on_release`, `local_onnx.py`). TDD: `tests/test_idle_release.py` đỏ → xanh; toàn bộ **852** test xanh. Đo lại: rảnh 11 phút → **2,9 GB RAM / 0,28 GB VRAM** (trả ~7,9 GB RAM + ~3,6 GB VRAM). Lần truy xuất đầu sau khi nhả ~12–15 s (như lần đầu sau khi mở app). Commit `911b831` trên nhánh `wip/2026-11-14-toi-uu-vram` (chưa push: anh chưa nói push repo Co-Writer). Không cần thay exe |

**Ruling (Co-Writer):** ngưỡng nhả 10 phút — đủ dài để một buổi viết liên tục không bị nạp lại, đủ ngắn để rời bàn là trả máy — cái giá nếu sai: hay tìm cách quãng >10 phút thì mỗi lần chờ ~12 s; chỉnh `IDLE_RELEASE_SECONDS`.
**Ruling (Co-Writer):** commit chỉ 3 file của em lên nhánh `wip/…`, 58 thay đổi dở của anh để nguyên trong working tree — các file em sửa không trùng file đang dở — cái giá nếu sai: không có.
| G3-TF | ✅ đo | ToneForge nền (`app/ui/tests/toneforge-stem-scenario.mjs`, mở kèm cổng gỡ lỗi WebView2, `invoke` nạp WAV tổng hợp 30 s + `cmd_run_uvr5_separation`): mở 2,6 GB RAM / 0,52 GB VRAM → sau 1 lần tách (21,3 s) **14,0 GB / 11,1 GB** → rảnh 5 phút **y nguyên** → tắt **0 sót**. **App tốn nhất.** Nguyên nhân: `ArenaExtendStrategy::NextPowerOfTwo` + 4 bộ tách trong biến toàn cục sống suốt đời app (model chỉ ~25 MB/cái) |
| G4-TF | 🔄 build | `idle_release.rs` (`IdleSlot`: chưa nạp / đã nạp / hỏng; nhả → tự nạp lại lần sau; luồng canh 30 s, nhả sau 600 s rảnh), 3 bộ tách chuyển sang `IdleSlot`, bộ ensemble đăng ký nhả + `touch()`, arena `SameAsRequested`. Test crate 12/12 (4 mới). Nhánh `wip/2026-11-14-toi-uu-vram` |
| G2b | ✅ sửa | `measure_app_resources.ps1`: tách dấu hiệu `path` (so ĐƯỜNG DẪN EXE) và `cmd` (so DÒNG LỆNH, chỉ identifier WebView) — bản đầu bắt nhầm lệnh node của em có tham số chứa `\toneforge\` |
| G4-TF đo | ✅ | Bản mới (`ToneForge_Studio_new.exe`): tách 20,6 s (cũ 21,3 s) · đỉnh **10,1 GB VRAM** (cũ 11,1) · rảnh 11 phút → **2,9 GB RAM / 0,49 GB VRAM** (cũ giữ 14,0 / 11,1). ⚠ Lần đóng sau 11 phút rảnh: tiến trình chính **treo ở bước thoát** (WebView đã tắt, exe còn 2,4 GB/409 MB). Bản thử nhả sau 60 s + rảnh 100 s → đóng **sạch**; bản mới không rảnh → đóng sạch. Đang chạy bản CŨ rảnh 11 phút để biết treo có sẵn từ trước không |
| G3-SA | ✅ đo | Selorson Admin: mở 261 MB RAM / 35 MB VRAM → bấm X **0 sót**. Sa bàn 3D vào/ra 5 lần: trong 328 MB → sau khi rời **29,9 → 30,5 MB** (+9 MB, **ĐẠT** mốc +20 MB, đợt v2 còn +62 MB) |
| G3-AK | ✅ đo | Akunarch: mở 344 MB / 10 MB VRAM → bấm X **0 sót** (3D đã đo kỹ ở đợt VRAM v2) |
| G3-CF | ✅ đo | ComfyUI riêng: lối tắt → đóng cửa sổ console → **0 python sót**. Lối tắt có mở 1 tab Brave (`--auto-launch`) |
| G4-TF kiểm | ⏸ dừng | Bản CŨ rảnh 11 phút → đóng **sạch** (14,0 GB / 11,1 GB giữ nguyên tới lúc đóng). → Treo lúc thoát chỉ thấy ở bản mới, 1/1 lần rảnh 11 phút (bản nhả-60 s: 1/1 sạch). Lượt lặp lại bị dừng vì **anh tự mở ToneForge lúc 23:48:55** (từ Explorer) — em không đụng. Code: commit `a095ca5` nhánh `wip/2026-11-14-toi-uu-vram` (F:\FL studio). **Chưa thay `ToneForge_Studio.exe`**; bản thử để ở `ToneForge_Studio_new.exe` |
| G4-TF xong | ✅ | Thêm lưới "tắt là tắt hẳn" (`RunEvent::Exit`: luồng canh 5 s + `TerminateProcess` sau khi dọn) và rút nhả còn **15 s** (đo: tách lần đầu 21,5 s / nóng 20,8 s / sau khi nhả 21,3 s → nạp lại ~0,5 s). Kiểm: rảnh 11 phút rồi đóng → **0 sót**; rảnh 25 s → 2,9 GB RAM / 0,49 GB VRAM. **Đã thay `ToneForge_Studio.exe`** (SHA `a348a864…`), bản cũ ở `_archive\toi-uu\toneforge_exe_cu\`. Commit `0ae9724` + exe, nhánh `wip/2026-11-14-toi-uu-vram` (chưa push) |
| G4-CW 60 s | ✅ | Anh gợi ý rút ngắn. Đo dựng lại sau khi nhả: embedder 1,26 s + reranker 0,70 s → `IDLE_RELEASE_SECONDS` = **60**. App thật: rảnh 90 s → 2,9 GB RAM / 0,25 GB VRAM. Commit `5cf8cf0`, đã push nhánh `wip`. **Chưa phát hành**: bản cài 4/11 chứa 58 thay đổi chưa commit → hỏi anh cách chốt trước khi gắn tag |
| Còn lại | ⏳ | Selorson Thế giới mở: để sau khi có dữ liệu (anh chốt). Co-Writer: lượt tìm đầu ~12–15 s chủ yếu không phải nạp model (chưa điều tra). `sd-server` không tự tắt (chưa đo) |
