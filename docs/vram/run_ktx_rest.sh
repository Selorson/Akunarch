#!/usr/bin/env bash
for s in singularity-samos-olympus singularity-stonehenge-avalon avalon-mage-sanctum; do
  echo "=== $s $(date +%T)"
  powershell -NoProfile -ExecutionPolicy Bypass -File 'E:\Akunarch\bin\scripts\optimize_glb_runtime.ps1' -Glb "E:/Akunarch/projects/$s/clockwork/$s.glb" || echo "FAIL $s"
done
echo "=== done $(date +%T)"
