# Log lần chạy — 2026-11-14 · Claude · Dựng ComfyUI + tải model (FLUX, TRELLIS.2, MiniMax H3)

| Mục | Nội dung |
|---|---|
| Bắt đầu – kết thúc | `10:35` – `11:20` |
| Kế hoạch / ledger | Không thuộc đợt nào; theo `docs/ops/NGHIEN_CUU_REPOS.md` mục 5 |
| Mục tiêu lần chạy | Anh cho tải trước ComfyUI + FLUX, TRELLIS và MiniMax H3 (làm video) |
| Trạng thái cuối | ✅ Tải và dựng xong. Chưa chạy thử sinh ảnh/3D/video nào (cần anh chọn việc thử đầu tiên) |

## 1. Việc đã làm
- **ComfyUI** `E:\Akunarch\repos\ComfyUI`: `git pull` từ 0.34.0 lên **0.45.0**. Tạo `.venv` gồm Python 3.13, torch 2.14.1+cu130 và đủ `requirements.txt`. Kiểm bằng `main.py --quick-test-for-ci`: nhận RTX 4080 (16 375 MB), nạp đủ đường dẫn `D:\AI-Models`.
- `extra_model_paths.yaml`: thêm khoá `geometry_estimation`, vì TRELLIS.2 cần MoGe-2.
- **Tải 13 file, tổng 74,5 GB** vào `D:\AI-Models`, bằng script `bin\scripts\download_comfy_models.ps1`. Dung lượng từng file khớp với HuggingFace. Tốc độ khoảng 40 MB/s, mất 28 phút.

  | Bộ | File | GB | Giấy phép |
  |---|---|---|---|
  | FLUX.1-schnell | `flux1-schnell-fp8` (checkpoint gộp) | 17,2 | Apache-2.0 |
  | TRELLIS.2 + Pixal3D | `trellis_2_int8_convrot`, `pixal3d_int8_convrot`, 2 VAE trellis_2, `dino_v3_L_naf_fp32`, `moge_2_vitl_normal_fp16`, `birefnet` | 15,2 | MIT |
  | MiniMax H3 (fl2va: chữ/ảnh/khung đầu-cuối → video có tiếng) | `minimax_h3_fl2va_pruned_int8_convrot`, `qwen3vl_32b_minimax_h3_nvfp4_awq`, VAE video int8 + VAE audio, LoRA turbo 8 bước | 42,0 | MiniMax H3 Community License |

## 2. Lỗi gặp & cách xử lý
- Không có lỗi.

## 3. Quyết định đã tự đưa ra (Ruling)
- **TRELLIS chạy trong ComfyUI (TRELLIS.2, có sẵn từ ComfyUI 0.34), không dùng WSL2** — không phải bật WSL (một thay đổi hệ thống), không phải tự biên dịch CUDA, bản int8 vừa 16 GB VRAM — cái giá nếu sai: chất lượng kém bản gốc thì mới phải quay lại dùng WSL.
- **H3 chỉ tải đúng bộ file mà template chính thức `video_minimax_h3_i2v/t2v` dùng** (bản pruned int8 + text encoder nvfp4, đã chạy được trên GPU không phải Blackwell) — máy có 16 GB VRAM và 31 GB RAM, bản lớn hơn không chạy nổi — cái giá nếu sai: phải tải thêm.
- **Chưa tải `ref2va`** (giữ nhân vật đồng nhất theo ảnh tham chiếu, thêm khoảng 21 GB) — đợi anh cần.
- Dùng bản `E:\Akunarch\repos\ComfyUI`; bản trùng `D:\Git-repo\ComfyUI` để nguyên.

## 4. Việc cần anh chốt
- **Giấy phép H3:** được dùng ở Việt Nam. Vùng bị loại trừ chỉ gồm EU, Anh, Hàn Quốc, Mỹ. Doanh thu dưới 20 triệu USD/năm thì dùng thương mại không cần xin phép. Sản phẩm thương mại dùng H3 **phải ghi "MiniMax H3"** trên giao diện. Nếu Selorson phát hành video làm bằng H3 thì nên ghi credit này.
- **Việc thử đầu tiên:** ảnh concept bằng FLUX, nặn 3D bằng TRELLIS.2 (so với Hunyuan), hay video bằng H3? Mỗi lần chạy phải đi qua `gpu_enqueue(kind='comfyui')`.

## 5. File / app đã thay đổi
- Mã: `bin/scripts/download_comfy_models.ps1` (mới), `repos/ComfyUI/extra_model_paths.yaml` (nằm ngoài git)
- App: không thay
- Commit: chưa commit

## 6. Bài học quy trình mới (đã chép vào KINH_NGHIEM.md?)
- Tải file lớn bằng tiến trình tách rời (`Start-Process` + `curl -C -`), ghi log ra đĩa. Cách này không bị giới hạn 30 phút của lệnh chạy nền và chạy lại được. · [x] đã chép
- Trước khi tải model mở trọng số, đọc **LICENSE gốc** (vùng được dùng, điều khoản thương mại); đừng chỉ tin trang giới thiệu. · [x] đã chép
