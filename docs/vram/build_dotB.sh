#!/usr/bin/env bash
# Build thử Akunarch vào target-dotA (KHÔNG đụng target\release = hard link của bản cài). Kiểm SHA exe cài trước/sau.
set -e
INST=/c/Users/Admin/AppData/Local/Akunarch/akunarch.exe
before=$(sha256sum "$INST" | cut -d' ' -f1)
cd /e/Akunarch/app/ui && npm run build > /e/Akunarch/docs/vram/build_dotB_ui.log 2>&1
touch /e/Akunarch/app/src-tauri/src/lib.rs
cd /e/Akunarch/app/src-tauri && CARGO_TARGET_DIR='E:\Akunarch\app\src-tauri\target-dotA' cargo build -j 4 --release --features custom-protocol > /e/Akunarch/docs/vram/build_dotB.log 2>&1
after=$(sha256sum "$INST" | cut -d' ' -f1)
echo "installed before=$before after=$after"
[ "$before" = "$after" ] || { echo "!!! EXE CÀI BỊ ĐỔI"; exit 2; }
sha256sum /e/Akunarch/app/src-tauri/target-dotA/release/akunarch.exe
tail -2 /e/Akunarch/docs/vram/build_dotB.log
