# `E:\Akunarch\bin` — Precompiled Native Rust Sidecars (`Zero-OOM Architecture`)

Thư mục này chứa các binary worker độc lập bằng Rust được biên dịch sẵn từ `E:\Akunarch\repos\*` để không gộp 700+ crates khác phiên bản `wgpu` / `ort` vào `E:\Akunarch\app\src-tauri\Cargo.toml`:

1. `materialcraft-cli.exe` *(Chặng 2)* — Nấu vật liệu PBR 16-bit PNG/EXR bằng CPU SIMD (`0 MB VRAM`).
2. `effectcraft-cli.exe` *(Chặng 5)* — Kết xuất đồ họa cổ ngữ SVG / hiệu ứng `.ecproj` / Lottie.
3. `filmcraft-cli.exe` *(Chặng 5)* — Ghép nối timeline đa lớp, phụ đề song ngữ và kết xuất `.mp4`.
4. `akunarch-audio-cli.exe` *(Chặng 5)* — Bọc 4 crate DSP từ `ToneForge` (`dsp-proq4-eq`, `dsp-soothe3-spectral`, `dsp-ozone12-mastering`, `daw-core-graph`) chuẩn hóa âm thanh `-14 LUFS`.
