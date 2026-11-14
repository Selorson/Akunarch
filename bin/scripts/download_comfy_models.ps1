# Tải model cho ComfyUI vào kho chung D:\AI-Models (ComfyUI đọc qua extra_model_paths.yaml).
# Tải tuần tự, nối tiếp được (curl -C -): chạy lại script sẽ bỏ qua file đã đủ.
# Log: D:\AI-Models\_download.log
#
# Bộ model (2026-11-14):
#   FLUX.1-schnell fp8 (Apache-2.0)          — ảnh concept
#   TRELLIS.2 + Pixal3D (MIT, native ComfyUI) — ảnh → 3D
#   MiniMax H3 fl2va pruned int8 + turbo 8 bước (MiniMax H3 Community License) — video có tiếng

$ErrorActionPreference = 'Continue'
$root = 'D:\AI-Models'
$log  = Join-Path $root '_download.log'
$hf   = 'https://huggingface.co'

$files = @(
  @('checkpoints',         "$hf/Comfy-Org/flux1-schnell/resolve/main/flux1-schnell-fp8.safetensors"),
  @('diffusion_models',    "$hf/Comfy-Org/TRELLIS.2/resolve/main/diffusion_models/trellis_2_int8_convrot.safetensors"),
  @('vae',                 "$hf/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_shape_vae_bf16.safetensors"),
  @('vae',                 "$hf/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_texture_vae_bf16.safetensors"),
  @('diffusion_models',    "$hf/Comfy-Org/Pixal3D/resolve/main/diffusion_models/pixal3d_int8_convrot.safetensors"),
  @('clip_vision',         "$hf/Comfy-Org/Pixal3D/resolve/main/clip_vision/dino_v3_L_naf_fp32.safetensors"),
  @('geometry_estimation', "$hf/Comfy-Org/MoGe/resolve/main/geometry_estimation/moge_2_vitl_normal_fp16.safetensors"),
  @('background_removal',  "$hf/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors"),
  @('vae',                 "$hf/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_video_vae_int8_convrot.safetensors"),
  @('vae',                 "$hf/Comfy-Org/MiniMax-H3/resolve/main/vae/minimax_h3_audio_vae_fp32.safetensors"),
  @('loras',               "$hf/lightx2v/Minimax-h3-Turbo/resolve/main/minimax_h3_fl2v_turbo_8step_v1.0_comfyui_bf16.safetensors"),
  @('text_encoders',       "$hf/Comfy-Org/MiniMax-H3/resolve/main/text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"),
  @('diffusion_models',    "$hf/Comfy-Org/MiniMax-H3/resolve/main/diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors")
)

function Log($m) { "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $m" | Out-File -FilePath $log -Append -Encoding utf8 }

Log "=== BẮT ĐẦU ($($files.Count) file)"
foreach ($f in $files) {
  $dir  = Join-Path $root $f[0]
  $name = [IO.Path]::GetFileName($f[1])
  $dest = Join-Path $dir $name
  New-Item -ItemType Directory -Force $dir | Out-Null

  # Kích thước thật trên HF (theo redirect tới CDN)
  $head = & curl.exe -sIL $f[1] | Select-String -Pattern '^content-length:\s*(\d+)' | Select-Object -Last 1
  $want = if ($head) { [int64]$head.Matches[0].Groups[1].Value } else { -1 }
  if ((Test-Path $dest) -and $want -gt 0 -and (Get-Item $dest).Length -eq $want) { Log "ĐÃ CÓ  $($f[0])\$name"; continue }

  $ok = $false
  for ($try = 1; $try -le 5 -and -not $ok; $try++) {
    Log "TẢI    $($f[0])\$name ($([math]::Round($want/1GB,2)) GB, lần $try)"
    & curl.exe -L --fail --retry 5 --retry-delay 10 -C - -s -o $dest $f[1]
    $ok = ($LASTEXITCODE -eq 0 -or $LASTEXITCODE -eq 33) -and (Test-Path $dest) -and ($want -le 0 -or (Get-Item $dest).Length -eq $want)
  }
  if ($ok) { Log "XONG   $($f[0])\$name" } else { Log "LỖI    $($f[0])\$name (curl=$LASTEXITCODE)" }
}
Log "=== KẾT THÚC"
