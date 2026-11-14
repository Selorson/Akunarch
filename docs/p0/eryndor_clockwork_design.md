# Thiết kế bản CƠ KHÍ — Tháp Đồng Hồ Thiên Văn Eryndor

> **Nguồn:**
> - Concept `projects/eryndor-clocktower-concept/concepts/concept_eryndor_clockwork_hero.jpg` (anh gửi và duyệt 2026-11-14)
> - Bản thật: [`eryndor_design.md`](eryndor_design.md)
>
> **Đặc tả máy:** `projects/eryndor-clocktower-concept/clockwork/eryndor-clocktower-concept.mechanism.json`
>
> **Bộ phận riêng:** `bin/scripts/clockwork/eryndor_clocktower_concept_mechanism_parts.py`
>
> **Test:**
> - `bin/scripts/clockwork/tests/test_eryndor_mechanism.py` (đặc tả, 7 test)
> - `test_eryndor_mechanism_glb.py` (file `.glb` đã dựng, 5 test)

## 1. Đọc concept (đối chiếu với bản thật)

| Vùng | Concept cơ khí | Cách dựng |
|---|---|---|
| Dáng tổng | Giữ 1:1 dáng bản thật, toàn bộ là đồng thau/đồng | Dùng lại `eryndor_parts.py` (cùng số đo), đổi bộ vật liệu |
| Thân dưới | Bỏ tường, chỉ còn 8 trụ ốp. Bên trong là chồng tầng bánh răng xếp bậc quanh cột thép giữa | Bỏ `ER_base_wall`, cửa sổ, ô trống. Thêm bệ tròn 2 bậc và 4 tầng bánh răng đĩa đặc |
| Trụ ốp | Có ống đồng dọc, có nắp | `build_buttress_tubes` |
| Thân trên | Mặt trái là cổng đầu hồi mở gần hết, thấy bánh răng bên trong | Khung 3 mặt có cổng đầu hồi cao 8,85 m, viền đồng, 2 trụ mảnh. Mặt +X là tấm đồng sau đồng hồ |
| Mặt đồng hồ | Vành ngoài có răng | Vành răng `g_dial_ring` (kiểu `ring`, không nan hoa) thay vành đồng ngoài cùng |
| Gác chuông | 2 chuông, có đĩa tròn dưới chuông | Đĩa đó là trống chốt `g_drum`. Thêm 2 búa và chốt trên trống |
| Mái chóp, quả cầu | Giống bản thật | Giữ nguyên. Mái đổi sang tấm đồng đỏ |

## 2. Chuỗi truyền động (không bánh răng trang trí: `validate` = [])

```
con lắc 4 m (y −2,05) ⇄ neo ⇄ bánh thoát g_esc 20T (9°/nhịp)
  └ s_esc: g_e2 40T → g_t1 20T ─ s_t1: g_t1b 16T [ly hợp 0–48] → g_up_spur 30T
       └ s_up: g_up_bevel ⟂ g_main_up ── CỘT THÉP GIỮA s_main (9,6°/nhịp) ──┐
   ┌─────────────────┬───────────────────────────┬───────────────┬───────┘
   ▼                 ▼                           ▼               ▼
 g_main_top 80T   g_main_dial ⟂ g_dp_bevel   g_main_bel 14T  g_main_crown 15T
 → g_lay_top 56T    s_dp: g_dp 12T [0–34]    [34–47]         → g_cx1 15T, g_cx2 10T
 s_lay: g_p1..p4    → vành răng mặt đồng hồ  → trống g_drum   → g_arm 20T
 [ly hợp so le]       100T (vòng hoàng đạo)    28T, 2 hàng    → quả cầu thiên văn
 → 4 tầng đĩa         → g_mw1 50T → g_mw2 10T  chốt → 2 búa
   124/106/88/68T       g_mw3 40T → g_hand 20T (kim, ×10 vành)
```

**Tầng đáy:**
- Bánh nhỏ trên trục phụ `s_lay` tăng dần từ dưới lên (12 → 68 răng), cách tâm 3,4 m. Vì vậy 4 tầng đĩa nhỏ dần lên trên, thành hình bậc như concept.
- Tầng trên quay nhiều hơn tầng dưới (16° → 165°).

## 3. Dòng thời gian (1 nhịp = 0,5 s)

| Nhịp | Sự kiện |
|---|---|
| 0–48 | Con lắc đập nhịp, bánh thoát nhích; quả cầu thiên văn quay |
| 2–26 | 4 tầng bánh răng lần lượt quay (ly hợp so le 2–14, 6–18, 10–22, 14–26) |
| 0–34 | Vành hoàng đạo quay chậm (−39°); kim chạy gần trọn vòng |
| **34** | **Kim chạm XII (00:00, đúng sự kiện canon), cả bộ dừng** |
| 35–46 | Trống quay, 12 tiếng chuông gõ luân phiên búa trái/phải |
| idle (lặp 4 s) | Chỉ còn "tim đập": con lắc, bánh thoát, 2 bánh đầu. Mỗi lượt quay trọn bước răng và nan hoa nên vòng lặp không giật (`idle_seam_errors` = []) |

## 4. Quyết định em tự đưa ra (Ruling)

- **Xuất ở kích thước thật (26 m), không thu 1:40** — concept không có mặt sa bàn, sân khấu và trình xem tự co — cái giá nếu sai: chỉ cần scale empty gốc.
- **Không vách đá, ngăn kéo, thiên thạch** — anh chốt 2026-11-14 — bệ cơ khí có thể bổ sung sau.
- **Bánh côn dựng tạm bằng 2 đĩa răng thẳng chạm nhau** — 3 cặp đều nằm khuất trong lõi tháp — muốn đẹp hơn thì viết `build_bevel_gear`.
- **Bệ tròn 2 bậc (không phải bánh răng)** lấp sàn thân dưới — tầng bánh răng lớn nhất bị giới hạn ở bán kính 3,1 m, vì trục phụ phải nằm trong lòng bát giác.
- **Idle chỉ còn tim đập** — để vòng lặp không giật, và hợp ý "thời gian dừng lúc nửa đêm".

## 5. Chỗ còn lệch concept (cần anh chốt — xem log phiên)

1. **Đầu rồng ở góc tường răng cưa:** concept có. Bản thật anh đã bỏ đầu thú, nên em bỏ theo.
2. **Hai bánh răng đứng lớn** ở hai ô trên thân dưới, sát tường răng cưa.
3. **Vành răng lớn chạy quanh chân tường răng cưa.**
4. **Hoa văn rỗng Gothic** hai bên cổng thân trên.

Mục 2–4 phải gắn vào chuỗi truyền động (Luật "không trang trí"). Nếu anh muốn đủ thì em thiết kế thêm nhánh cho chúng.

## 6. Vòng 4–5 (anh góp ý 2026-11-14: tầng 1–2 nhiều chi tiết hơn, không đầu rồng, 1 chuông)

| Thêm | Nối vào chuỗi truyền động |
|---|---|
| Vành răng 218T quanh chân tường răng cưa (thay hàng đá nhô) | 2 bánh đứng 50T (ô trái, ô trước) trên 2 trục ngang, côn từ cột giữa — 2 đường song song khớp tỉ số |
| 3 chồng bánh nhỏ (trục phụ 135°, −45°, −135°) | Cùng kéo 4 tầng đáy song song |
| Chuỗi 5 bánh đổ xuống ở mặt hở thân trên | Thay nhánh côn cột giữa → mặt đồng hồ; kim chạy 2 vòng (24 giờ) tới XII |
| 1 chuông treo giữa, 1 búa, trống 12 chốt | Trống đặt ở −75° để chốt đi dưới đuôi búa; quả cầu kéo bằng trục phụ vòng qua chuông |
| Hoa văn vòm nhọn 2 bên cổng, đinh tán trụ/bệ, vòng đai cột | Chi tiết tĩnh (không phải bánh răng) |

Động cơ thêm luật **vòng kín**: bánh được kéo theo 2 đường phải khớp tỉ số và cửa sổ ly hợp, không thì báo "kẹt".

## 7. Vòng 6 — chi tiết nặn bằng AI (anh chọn 2026-11-14)

| Chi tiết | Cách làm | Dùng ở |
|---|---|---|
| Khung cổng vòm nhọn hoa văn rỗng | FLUX.1-schnell tạo ảnh tham chiếu sạch nền → TRELLIS.2 nặn `.glb` PBR → `clockwork/parts/eryndor_portal_tracery.glb` | 3 mặt hở thân trên (cao 8,4 m, dày 0,3 m, 60k tam giác, chung 1 mesh) |

Vật liệu vỏ đổi sang texture kim loại mòn Poly Haven (CC0) nhuộm màu đồng.

## 8. Vòng 7 — chốt đợt (2026-11-14)

| Chi tiết nặn (FLUX → TRELLIS.2) | Số bản | Tam giác/bản | Thay cho |
|---|---|---|---|
| Khung cổng vòm nhọn hoa văn rỗng | 3 | ~42k | viền/trụ hình học ở 3 mặt hở thân trên |
| Tấm chạm hình thoi + hoa hồng | 24 | ~4k | tấm chữ X trên 8 trụ ốp × 3 tầng |
| Chóp nhọn có hốc + đầu hoa huệ | 8 | ~10k | 8 tháp nhọn hình học |
| Mái vòm cong hai đầu cuộn | 1 | ~50k | mái vòm hình học trên 3 mặt phụ (v7 lỡ quay ngang, v9 sửa) |

Tổng ~817k tam giác (≤ 900k), 51 bánh răng, 1 chuông. Không đầu rồng (anh chốt).
