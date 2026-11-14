# Báo cáo NeuroForge: cách làm việc và tài nguyên (CHỈ QUAN SÁT, KHÔNG SỬA)

> 2026-11-14, Claude. Anh cho theo dõi bài cuối của ngày, từ 22:04 đến 22:28 (anh tắt app).
> Cách đo: chỉ từ bên ngoài, mỗi 10 giây, ưu tiên thấp. Đọc danh sách tiến trình và bộ đếm RAM/VRAM/CPU; không đọc DB, không gửi gì vào app.
> Mã nguồn: chỉ đọc. Log thô (có tên bài) để ngoài git ở `_archive\toi-uu\neuroforge\`.

## 1. NeuroForge làm việc thế nào (theo mã + quan sát thật)

**Đội máy chia việc qua ổ chia sẻ, không mở cổng mạng mới** (`commands/fleet.rs`):
- Mỗi máy ghi **nhịp tim** `<outputs>/machine.json` mỗi phút: vai trò, năng lực, tải, hạn mức Claude.
- **Bảng việc** nằm ở `<outputs>/Temp/Board/{open,claimed,done}`:
  - máy giao ghi phiếu vào `open/` (ký HMAC bằng khoá đội);
  - máy rảnh và đủ năng lực **nhận việc bằng cách đổi tên phiếu sang `claimed/`** (thao tác nguyên tử, chỉ một máy thắng), cứ 20 giây gia hạn một lần;
  - làm xong thì ghi `done/`.
- **Máy điều phối** là máy bật đầu tiên trong thứ tự chung, không bầu chọn. Máy cần mà đang tắt thì được đánh thức bằng Wake-on-LAN.
- API nội bộ chỉ nghe trong máy, ở `127.0.0.1:3030`.

**Bài cuối quan sát được trên máy này (RTX):**

| Giờ | Bước | Tiến trình | Thời gian | Tài nguyên |
|---|---|---|---|---|
| 22:11 | Đọc thông tin video nguồn trên ổ chia sẻ máy khác (`\\M4800\…`) | `ffprobe` | ~12 s | nhẹ |
| 22:11 → 22:17 | Bộ não AI soạn nội dung: 3 phiên Antigravity CLI, mỗi phiên kèm 2 máy chủ MCP (`rea.mjs` qua node, `craft-anything-cli`) | `agy` → `node` + `craft-anything-cli` | 78 s · 146 s · 56 s | RAM cây app ~950 MB–1,3 GB, CPU ≈ 0 (chờ mô hình trên mạng) |
| 22:13 | Nhận dạng lời nói, phụ đề | `whisper-cli` (CUDA, model `small`) | 22 s | **đỉnh RAM 2,6 GB, VRAM 1,2 GB** |
| 22:17 → 22:19 | Dựng các đoạn video | `ffmpeg` (×9, mỗi lần ~11 s; 1 lần 78 s) | ~2 phút | VRAM ~530 MB (mã hoá GPU), CPU ~10% |
| 22:19 | Trộn các bài nhạc | `ffmpeg` | ~12 s | nhẹ |
| 22:19 → 22:24 | Trộn nhạc nền lặp vào video (video chép thẳng, chỉ mã hoá lại âm thanh AAC) | `ffmpeg -c:v copy` | 5,4 phút | CPU ~0,6%, chủ yếu đọc/ghi file dài |
| 22:21 | Kiểm hạn mức Antigravity | `agy --print /usage` | 11 s | nhẹ |
| 22:24 → 22:28 | Rảnh | — | — | ~475 MB RAM, 81–91 MB VRAM |

**Tổng cả phiên:**
- RAM cây app: trung bình 753 MB, đỉnh 2,6 GB (lúc whisper).
- VRAM: trung bình 139 MB, đỉnh 1,2 GB.
- CPU: trung bình 0,9%, đỉnh 11%.
- GPU toàn máy: đỉnh 38% (whisper).

## 2. Đánh giá tài nguyên

- ✅ **Nhẹ khi rảnh:** ~460–530 MB RAM (phần lớn là WebView2), dưới 100 MB VRAM.
- ✅ **Tiến trình con thoát hết sau mỗi bước.** 13 lần ffmpeg, 6 lần agy, 3 cặp máy chủ MCP, whisper: không cái nào bị bỏ lại.
- ✅ **Anh tắt app → 0 tiến trình sót** (đo lúc 22:28:05, VRAM toàn máy về 1.070 MB).
- ✅ Server giọng (OmniVoice/VieNeu) do app bật **tự tắt sau 5 phút rảnh** (`tts.rs` `reap_idle_voice_servers`). Đóng cửa sổ chính thì tắt Antigravity CLI, OCR Studio, OmniVoice, VieNeu (`lib.rs:991`).
- Bài này không dùng OmniVoice trên máy này nên chưa thấy đường VRAM của TTS.

## 3. Rủi ro tiềm ẩn (đọc mã, CHƯA xảy ra trong lần quan sát này) — để anh cân nhắc, em không sửa

1. **Tắt app giữa lúc đang làm việc** → các tiến trình con không nằm trong danh sách dọn (`ffmpeg`, `whisper-cli`, `agy`/Claude CLI, Playwright, chatgpt_pilot, fleet…) có thể **chạy mồ côi**. Lý do:
   - `std::process::exit(0)` không chạy destructor, nên `kill_on_drop` cũng không kích hoạt;
   - chỉ `brain.rs` gắn Job Object.

   Cách chắc nhất (nếu anh muốn sửa sau): gắn **mọi** tiến trình con vào **một Job Object `KILL_ON_JOB_CLOSE`** của app (như Co-Writer đang làm). Khi đó Windows tự dọn cả cây tiến trình, kể cả khi app bị tắt cứng.
2. **Máy chủ MCP sinh lại mỗi phiên Antigravity** (`node rea.mjs` + `craft-anything-cli`, 3 lần trong bài này). Mỗi lần tốn vài trăm MB RAM và thời gian khởi động. Không lãng phí lâu dài vì tắt theo phiên; chỉ đáng giữ sống nếu một bài mở rất nhiều phiên.
3. **Whisper nạp lại model mỗi lần gọi** (`small`, ~1,2 GB VRAM, 22 s). Ổn cho 1 bài; chạy hàng loạt nhiều bài thì giữ một tiến trình whisper sống sẽ nhanh hơn. Đây là đánh đổi tốc độ, không phải rò rỉ.
