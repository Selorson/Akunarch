#!/usr/bin/env bash
# Nghiệm thu C3: S0–S4 × 3 lượt trên akunarch.exe ĐÃ HOT-SWAP, chế độ người dùng thật (driver không đặt biến trỏ %TEMP%)
cd /e/Akunarch/app/ui
for r in 1 2 3; do
  echo "=== lượt $r $(date +%T)"
  node tests/vram-scenarios.mjs --phase c3_r$r --only S0,S1,S2,S3,S4 2>&1 | grep -E "MEASURE|S1 standby|S4 lần|RESTORE|rror|PROBE S4_final" -A0
done
echo "=== xong $(date +%T)"
