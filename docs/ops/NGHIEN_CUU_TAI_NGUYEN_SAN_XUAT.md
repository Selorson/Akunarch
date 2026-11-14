# Tài nguyên sản xuất AI: hiện trạng, số đo, đề xuất (chuẩn bị trao đổi với anh)

> Viết 2026-11-14 (Claude), sau đợt bản cơ khí Eryndor. Phiên sau anh muốn bàn về quy trình ComfyUI, TRELLIS, Blender, MiniMax H3. Đây là bản trình bày: **số liệu là đo thật trên máy**, chỗ nào chưa thử thì ghi rõ "chưa thử".
>
> Máy: RTX 4080 16 GB VRAM, 31 GB RAM, CPU nóng nhanh (KTX2 song song từng làm sập máy).

## 1. Bộ công cụ đang có và vai trò

| Công cụ | Ở đâu | Vai trò trong dây chuyền | Trạng thái |
|---|---|---|---|
| **ComfyUI 0.45** | `E:\Akunarch\repos\ComfyUI` (.venv py3.13, torch 2.14 cu130), model ở `D:\AI-Models` | Nền chạy mọi model sinh ảnh/3D/video | ✅ chạy qua hàng đợi app (`comfy_workflow`) |
| **FLUX.1-schnell fp8** | `D:\AI-Models\checkpoints` (17 GB, Apache-2.0) | Ảnh tham chiếu sạch nền cho từng chi tiết; ảnh concept nháp | ✅ đã dùng 5 lần |
| **TRELLIS.2 int8** (+ Pixal3D) | `D:\AI-Models` (MIT) | Ảnh → `.glb` PBR (có normal map nướng sẵn) cho chi tiết chạm trổ | ✅ đã dùng 4 lần |
| **Hunyuan3D-2mini** | `E:\Tools-3D`, `D:\hf-cache` | Ảnh → 3D (cũ) | Có, chưa so với TRELLIS.2 |
| **Blender 5.2** | cài sẵn | Dựng khung kiến trúc bằng script (đúng bố cục, Luật #7), lắp bộ máy + animation, nhập chi tiết nặn, ảnh xem trước | ✅ nền chính |
| **MiniMax H3** (video có tiếng) | `D:\AI-Models` (bộ fl2va pruned int8 + text encoder nvfp4 + VAE + LoRA turbo 8 bước, 42 GB) | Video ngắn ≤ 15 s có tiếng từ chữ/ảnh/khung đầu-cuối | ⏳ **đã tải, CHƯA chạy thử** |
| **Poly Haven** (CC0) | `E:\Tools-3D\polyhaven\textures` (+5 bộ kim loại mòn) | Texture PBR nhuộm màu | ✅ |
| **KTX2** (`optimize_glb_runtime`) | `bin\scripts\optimize_glb_runtime.ps1` | Nén texture cho app (~30–40 phút CPU/công trình) | ✅, chỉ chạy khi anh cho |

## 2. Dây chuyền đã chạy thật trong đợt Eryndor

```
concept (anh duyệt)
  ├─ khung kiến trúc ── Blender script (eryndor_parts.py) ── đúng bố cục/cao độ (Luật #7)
  ├─ bộ máy cơ khí ─── đặc tả .mechanism.json → động cơ clockwork (kiểm luật, động học) → Blender + animation
  └─ chi tiết chạm trổ ─ FLUX (ảnh 1 chi tiết, nền trắng) → TRELLIS.2 (.glb PBR) → Blender import_sculpt
                          (chuẩn hoá kích thước, decimate, nhân bản chung mesh, khoét tường theo dáng)
→ assemble_mechanism_glb (hàng đợi) → soát trong app (4 góc xoay) → anh duyệt → KTX2 (anh cho chạy)
```

## 3. Số đo thật (RTX 4080 16 GB)

| Việc | Thời gian | VRAM đỉnh | Ghi chú |
|---|---|---|---|
| FLUX.1-schnell 768×1152, 4 bước | ~1–2 phút (gồm bật/tắt ComfyUI, nạp model) | **15,4–15,8 GB** | Sát trần → không chạy kèm gì khác. 1 lần ComfyUI chết giữa chừng (#48), chưa rõ vì sao (đã thêm log riêng mỗi lần) |
| TRELLIS.2 int8 (tex 2048, 40–120k mặt) | ~1,5–2 phút | 8,9–14,4 GB | Chất lượng tốt: hoa văn rỗng thật, đinh tán, normal map |
| Blender dựng bản cơ khí (51 bánh, 28 chi tiết nặn) | ~60 s CPU | — | 807k tam giác, 15 MB JPEG |
| Ảnh xem trước 1080p | ~15 s | ~3,5 GB | Chỉ 1 góc 3/4 → **không đủ để soát mặt sau** |
| KTX2 UASTC mức 4 | ~28–30 phút CPU | — | Không nối tiếp được; dừng là mất trắng |

## 4. Bài học chính (chi tiết ở `KINH_NGHIEM.md` mục 9–11, `QUY_TRINH_BAN_CO_KHI.md`)

1. **AI không thay được khung kiến trúc** (bố cục, cao độ, số lượng phải đúng concept). AI rất mạnh ở **chi tiết điêu khắc đơn lẻ**: một chi tiết, một ảnh, nền trắng, nhìn thẳng.
2. **Mọi model GPU qua hàng đợi** (`comfy_workflow`): bộ chạy tự bật ComfyUI rồi tắt, trả VRAM. Workflow mẫu phải xuất sang dạng API bằng `app.graphToPrompt()`.
3. **Gắn chi tiết nặn vào công trình có 3 bẫy đã gặp:**
   - quay sai do importer glTF để quaternion;
   - khoét tường không khớp dáng chi tiết → hở khe;
   - chi tiết lặp quá nhiều → vượt ngân sách tam giác (giải bằng decimate + chung mesh).
   Cả 3 đã có test hoặc kiểm tra kèm.
4. **Soát bằng mắt ở 4 góc xoay trong app** trước khi báo xong. Mỗi lần dựng lại phải bấm "Ngắt 3D", không thì sân khấu còn giữ mô hình cũ.

## 5. MiniMax H3: điều đã biết, chưa thử

- **Giấy phép** (đọc LICENSE gốc):
  - Việt Nam nằm trong vùng được dùng (chỉ loại trừ EU, Anh, Hàn, Mỹ).
  - Dùng thương mại dưới 20 triệu USD/năm thì không cần xin phép, nhưng **phải ghi "MiniMax H3" trên giao diện** sản phẩm thương mại dùng nó.
  - Cấm dùng đầu ra để huấn luyện model khác.
- **Đã tải đúng bộ template chính thức dùng:**
  - `minimax_h3_fl2va_pruned_int8_convrot` (21 GB);
  - `qwen3vl_32b_minimax_h3_nvfp4_awq` (15,7 GB);
  - VAE video int8, VAE audio;
  - LoRA turbo 8 bước.
- **Lo ngại phần cứng (chưa đo):** model chính 21 GB cộng text encoder 15,7 GB, đều lớn hơn 16 GB VRAM. ComfyUI phải offload qua RAM 31 GB, nên có thể chậm hoặc thiếu RAM. Cần chạy thử 1 clip ngắn (768p, 5 s, turbo 8 bước) qua hàng đợi để đo.
- **Workflow:** chưa xuất API. Làm như TRELLIS: template `video_minimax_h3_t2v` / `video_minimax_h3_i2v` → `graphToPrompt()` → `bin/comfy_workflows/`.
- **Chỗ dùng trong Selorson/Akunarch (đề xuất để bàn):**
  - video giới thiệu ngắn có tiếng cho địa điểm/công trình (từ ảnh xem trước hoặc concept);
  - cảnh chuyển trong VN;
  - thử nghiệm intro thay cho dựng Blender khi chưa cần đúng hình học.

## 6. Việc còn dở và câu hỏi để anh chốt (phiên sau)

**Việc kỹ thuật còn dở:**
- [ ] **Chạy thử H3** qua hàng đợi: đo thời gian, VRAM, RAM; xem chất lượng 1 clip.
- [ ] **So TRELLIS.2 với Hunyuan3D-2mini** trên cùng ảnh tham chiếu. Nếu TRELLIS hơn rõ, bỏ Hunyuan khỏi dây chuyền.
- [ ] **Lỗi app:** khởi động lại thì job đang chạy bị đánh dấu hỏng nhưng tiến trình con (ktx/powershell) vẫn chạy mồ côi. Nên dọn cây tiến trình lúc app khởi động.
- [ ] **Bánh côn trong bộ máy** đang dựng tạm bằng 2 đĩa phẳng (khuất trong lõi). Viết `build_bevel_gear` nếu cần nhìn gần.
- [ ] **Vật liệu chi tiết nặn:** đang giữ nguyên PBR của TRELLIS (chóp nhọn hơi xám so với vỏ đồng). Có thể thêm hệ số nhuộm.

**Câu hỏi cho anh:**
1. H3 dùng vào việc gì trước: intro địa điểm, cảnh VN, hay chỉ thử chất lượng?
2. Chấp nhận ghi "MiniMax H3" trên giao diện Selorson nếu đăng video làm bằng H3 không?
3. Chi tiết nặn bằng AI có cần anh duyệt từng ảnh FLUX trước khi nặn không, hay em tự chọn rồi anh duyệt kết quả cuối (như đợt này)?
4. Có muốn một "thư viện chi tiết nặn" dùng chung cho mọi công trình (tấm chạm, chóp nhọn, khung cửa…) để đỡ nặn lại?

**Anh trả lời (2026-11-14 tối):**
1. **H3 dùng cho toàn bộ chuyển cảnh trong thế giới Selorson:** quay phim, VN, intro. Bước kế tiếp là chạy thử H3 qua hàng đợi để đo thời gian, VRAM, RAM trước khi dựng dây chuyền.
2. **Có ghi "MiniMax H3" trên giao diện** Selorson ở những chỗ phát video làm bằng H3.
3. **Anh duyệt mọi ảnh tham chiếu trước khi nặn 3D hoặc làm video.** Ảnh có thể từ FLUX hoặc model khác anh tự tạo. Em không tự chọn ảnh rồi nặn luôn.
4. **Thư viện chi tiết nặn dùng chung:** có lý, để sau. Đã ghi nhận.
