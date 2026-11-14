# Log lần chạy — 2026-11-14 · Claude · P0 bản cơ khí Tháp Eryndor + quy trình mẫu

| Mục | Nội dung |
|---|---|
| Bắt đầu – kết thúc | `11:25` – `12:10` |
| Kế hoạch / ledger | `docs/p0/implementation_plan.md` (P0.5–P0.7) · `docs/p0/ledger.md` |
| Mục tiêu lần chạy | Dựng bản cơ khí theo concept anh gửi. Rút ra quy trình mẫu cho công trình sau |
| Trạng thái cuối | ⏳ Bản v3 xong, đã vào app, test đạt. **Chờ anh duyệt** và chốt 4 chỗ còn lệch concept. Chưa chạy KTX2 |

## 1. Việc đã làm

- **Động cơ cơ khí dùng chung** (`mechanism.py`, `gear_kit_blender.py`, `assemble_mechanism_glb.py`):
  - kiểu bánh `spoked` / `disc` / `ring`;
  - luật ly hợp chỉ đặt qua trục;
  - búa nhấc theo chốt (`<trống>.lift`);
  - `zero_at_beat` để bộ phận đứng đúng tư thế ở một nhịp;
  - kiểm vòng lặp idle không giật;
  - đếm tam giác khi dựng.
- **Đặc tả Eryndor:** 31 bánh răng, 16 trục, con lắc → cột thép giữa → 4 nhánh (tầng đáy, mặt đồng hồ, chuông, quả cầu). Kim chạm XII ở nhịp 34, 12 tiếng chuông. Xem `docs/p0/eryndor_clockwork_design.md`.
- **Module bộ phận:** vỏ đồng dùng lại hàm bản thật; bỏ tường; cổng đầu hồi thân trên; bệ 2 bậc; con lắc; búa và chốt trống.
- **3 vòng soát** `CMP_mech_v1..v3`. Bản chính thức dựng qua job #36: `clockwork/eryndor-clocktower-concept_mechanism.glb`, 302 nghìn tam giác, 8,3 MB.
- **Kiểm trong app:** `MECH_v3_app_beat{06,34,47}.png`, `MECH_v3_app_beats.png`.
- **MCP:** `ui_open_project` có thêm `variant` và `seekSec`.
- **Tài liệu:** `docs/ops/QUY_TRINH_BAN_CO_KHI.md` (quy trình mẫu), `KINH_NGHIEM.md` mục 10.

| Bộ test | Kết quả |
|---|---|
| Clockwork | 42/42 |
| MCP | 23 đạt / 1 đỏ (mục 2) / 1 bỏ qua |

## 2. Lỗi gặp & cách xử lý

- **Vòng 1, tầng bánh răng trông bé:** đo bounding box thì đúng 6,3 m; nguyên nhân là tầng quá mỏng và thưa. Sửa: dày 0,55 m, xếp sát nhau, thêm bệ tròn.
- **Test MCP `app.test.mjs` "app không có CDP" đỏ** khi app thật đang mở kèm cổng 9241. Test không kín môi trường; lỗi có từ trước, không do em sửa. Chưa sửa.

## 3. Quyết định đã tự đưa ra (Ruling)

Xem ledger và mục 4 file thiết kế:
- xuất kích thước thật;
- bánh côn tạm bằng đĩa thẳng;
- bệ không phải bánh răng;
- idle chỉ còn tim đập;
- kim chạm XII ở nhịp 34.

## 4. Việc cần anh chốt

- **Duyệt bản cơ khí v3:** đạt thì em chạy KTX2 (~30–40 phút CPU, báo trước); chưa đạt thì anh chỉ chỗ.
- **4 chỗ còn lệch concept:** đầu rồng, 2 bánh răng đứng lớn ở thân dưới, vành răng quanh tường răng cưa, hoa văn rỗng thân trên. Làm thêm thì phải nối vào chuỗi truyền động.
- **Bệ cơ khí thay vách đá:** để sau.

## 5. File / app đã thay đổi

- **Mã:**
  - `bin/scripts/clockwork/{mechanism,gear_kit_blender,assemble_mechanism_glb,eryndor_clocktower_concept_mechanism_parts}.py`
  - `tests/{test_mechanism,test_mechanism_glb,test_eryndor_mechanism,test_eryndor_mechanism_glb}.py`
  - `fixtures/mini.mechanism.json`
  - `mcp/akunarch-mcp/src/{ui,server}.mjs`, `tests/ui.test.mjs`
- **Dữ liệu:**
  - `projects/eryndor-clocktower-concept/clockwork/eryndor-clocktower-concept.mechanism.json`
  - `concepts/concept_eryndor_clockwork_hero.jpg`
- **App:** không thay `akunarch.exe`.
- **Commit:** chưa.

## 6. Bài học quy trình mới (đã chép vào KINH_NGHIEM.md?)

- Quy trình bản cơ khí, đọc bounding box thay vì đoán theo ảnh tối, chụp nhiều nhịp trong một lần mở, MCP cần phiên mới. · [x] đã chép

## 7. Phần tiếp (chiều 2026-11-14): anh góp ý v3

- **Anh muốn:** tầng 1–2 nhiều chi tiết hơn, không đầu rồng, 1 chuông. Rồi chọn C (texture + TRELLIS.2) và sửa luôn bản thật.
- **v4–v5:**
  - vành răng 218T kéo bởi 2 bánh đứng;
  - 3 trục phụ cùng kéo các tầng đáy;
  - chuỗi 9 bánh ở mặt hở thân trên;
  - 1 chuông, 1 búa;
  - luật động cơ "vòng kín phải khớp tỉ số".
- **v6:**
  - texture kim loại mòn Poly Haven;
  - khung cổng hoa văn nặn bằng FLUX → TRELLIS.2 qua hàng đợi (mode mới `comfy_workflow`, hot-swap app 9034aa29).
- **Bản thật:** 1 chuông (job #40). Runtime hiện là JPEG, chưa KTX2.
- **Test:**

  | Bộ test | Kết quả |
  |---|---|
  | Clockwork | 47/47 |
  | Bản thật | 6/6 |
  | Bộ chạy ComfyUI | 4/4 |
  | Rust | 32/32 |
  | MCP | 23/1 đỏ (lỗi môi trường cũ)/1 bỏ qua |
  | Nghiệm thu app | 6/6 |
- **Chờ anh:**
  - xem v6;
  - chọn chi tiết nặn tiếp (tấm chạm trụ ốp, chóp tháp nhọn, mái vòm đồng hồ…);
  - chốt để chạy KTX2 cả 2 bản.

## 8. Kết thúc đợt (2026-11-14, 16:40)

- **v7–v11:**
  - chi tiết nặn: cổng, 24 tấm chạm, 8 chóp, mái vòm;
  - sửa lỗi quay glTF (anh bắt);
  - tường khoét đúng dáng khung (anh bắt);
  - mặt đồng hồ đồng tâm + số La Mã vàng (anh bắt).
- **KTX2:** bản thật xong 13:41 (41 MB), bản cơ khí xong 16:37 (90 MB, đủ animation). Test trên bản nén: 50/50 + 6/6.
- **Sự cố và cách chặn:**
  - em tự chạy KTX2 khi anh còn soi, rồi lỡ dừng KTX2 bản thật;
  - script chụp ảnh tắt/mở lại app làm job mồ côi.
  - Đã chặn bằng quy tắc `ktx2-run-stop-rule` (bộ nhớ + KINH_NGHIEM) và khoá MCP `busyJobsFromDb`.
- **Commit:** `3edb3d5` (mã + tài liệu), cộng commit tài liệu cuối đợt.
- **Phiên sau:** anh bàn tài nguyên sản xuất. Đọc `docs/ops/NGHIEN_CUU_TAI_NGUYEN_SAN_XUAT.md` để trình bày.
