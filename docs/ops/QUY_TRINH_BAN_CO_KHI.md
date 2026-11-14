# Quy trình mẫu: làm BẢN CƠ KHÍ cho một công trình

> Rút ra từ Tháp Eryndor (2026-11-14, Claude). Áp dụng cho mọi công trình có bản thật rồi muốn thêm bản cơ khí chạy được.
>
> Mẫu đầy đủ để chép:
> - `docs/p0/eryndor_clockwork_design.md`
> - `projects/eryndor-clocktower-concept/clockwork/eryndor-clocktower-concept.mechanism.json`
> - `bin/scripts/clockwork/eryndor_clocktower_concept_mechanism_parts.py`

## 0. Điều kiện trước

- Bản thật đã dựng bằng một bộ hàm `build_*`, ví dụ `monuments/eryndor_parts.py`. Bản cơ khí **dùng lại đúng các hàm này** nên dáng khớp 1:1 mà không phải đo lại.
- Có **ảnh concept cơ khí anh đã duyệt**. Không có ảnh thì dừng và hỏi (Luật #7).

## 1. Đọc concept (khoảng 10 phút)

1. Ghép concept cơ khí cạnh concept thật, rồi phóng to từng vùng: đỉnh, thân trên, thân dưới.
2. Lập bảng **"giữ / bỏ / thêm"** cho từng vùng:
   - Tường nào bỏ để lộ máy.
   - Mảnh nào thành bánh răng (vành mặt đồng hồ, đĩa dưới chuông…).
   - Thứ gì concept có mà bản thật không có.
3. Ghi vào `docs/<đợt>/<tên>_clockwork_design.md`, mục 1.

## 2. Thiết kế chuỗi truyền động trên giấy

- **Một nguồn:** con lắc → bánh thoát. Mọi chuyển động khác đều đi từ đó. Tốt nhất có một trục chính chạy suốt công trình rồi chia nhánh.
- **Mỗi bộ phận chuyển động là một "đầu ra"** (`outputs`, `cam_drums`, `lead_screws`…). Bánh răng nào không dẫn tới đầu ra là bánh trang trí, sẽ bị `validate` chặn.
- **Hình học:**
  - Hai trục ăn khớp phải song song, khoảng cách tâm = m·(z₁+z₂)/2.
  - Trục vuông góc dùng `"kind": "bevel"`.
  - Đặt toạ độ bằng mm, cùng hệ toạ độ với bản thật (×1000). Trục đặt theo **điểm giữa** (`origin`) và `length_mm`; bánh trên trục đặt bằng `z_mm`.
- **Ly hợp (`clutch: [a, b]`)** chỉ đặt trên bánh nhận chuyển động **qua trục**, không đặt qua ăn khớp. `validate` sẽ chặn nếu đặt sai.
- **Vòng lặp idle (8 nhịp) không được giật:**
  - Bánh nào còn quay trong idle phải quay trọn bước răng, và trọn 72° nếu có 5 nan hoa.
  - Bánh thoát 20 răng có 5 nan hoa quay đúng 72° sau 8 nhịp.
  - Cách đơn giản nhất: cho mọi thứ dừng ở nhịp 48 bằng ly hợp, chỉ để "tim đập".
- **Kiểu bánh** (`style`): `spoked` (mặc định), `disc` (đĩa đặc, cho tầng lớn), `ring` (chỉ vành răng, cho mặt đồng hồ).
- **Bộ phận không phải bánh răng** khai báo trong `motions`:
  - `rotate` / `translate` theo một giá trị động học, kèm `axis`, `pivot_mm`, `scale`.
  - `zero_at_beat` để bộ phận đứng đúng tư thế dựng sẵn ở nhịp đó (kim chạm XII).
  - Búa chuông dùng `by: "<cam_drum>.lift"`.

## 3. Viết test trước, rồi đặc tả JSON

1. Viết `tests/test_<tên>_mechanism.py`, kiểm:
   - `validate == []`;
   - `idle_seam_errors == []`;
   - mốc dòng thời gian (kim, chuông, tầng…);
   - bộ phận nào còn chạy trong idle.
2. Chạy, thấy đỏ.
3. Viết `projects/<slug>/clockwork/<slug>.mechanism.json`. Dùng Python tính toạ độ có căn, ví dụ khoảng cách tâm chéo, đừng tính nhẩm.
4. Chạy lại, phải xanh.

## 4. Module bộ phận riêng

Tạo file `bin/scripts/clockwork/<slug_gạch_dưới>_mechanism_parts.py` với hàm `build(scene, root, mech, raw) -> {part_id: Object}`. Hàm làm 4 việc:

1. Gọi các `build_*` của bản thật với **bộ vật liệu cơ khí** (cùng khoá: `basalt`, `basalt_trim`… nhưng trỏ sang đồng).
2. Bỏ mảnh theo danh sách `DROP`. Thiếu tên nào thì báo lỗi ngay, để danh sách không lệch khi bản thật đổi tên.
3. Thêm những thứ động cơ không dựng: con lắc, búa, chốt trống (gắn làm con của bánh trống, đặt theo góc trống tại nhịp gõ), khung đỡ.
4. Gom các mảnh cùng quay vào một empty (`_regroup`, giữ vị trí thế giới) và trả về theo `part_id` của `motions`.

## 4b. Chi tiết chạm trổ bằng AI (FLUX → TRELLIS.2), khi hình học không đủ đẹp

1. **Ảnh tham chiếu (FLUX):**
   ```
   gpu_enqueue(slug, 'comfyui', {mode: 'comfy_workflow', workflow: 'E:\Akunarch\bin\comfy_workflows\flux_schnell_t2i.api.json', prefix: 'ref', set: ['6.text="<một chi tiết duy nhất>, front orthographic view, isolated on a pure white background"', '27.width=768', '27.height=1152', '31.seed=<số>', '9.filename_prefix="<tên>"']})
   ```
   - Mô tả một chi tiết duy nhất, nhìn thẳng, nền trắng.
   - Ảnh ra ở `projects/<slug>/comfy/`.
2. **Nặn (TRELLIS.2):**
   ```
   gpu_enqueue(slug, 'comfyui', {mode: 'comfy_workflow', workflow: '…\trellis2_image_to_glb.api.json', image: <ảnh>, image_node: '122', prefix: 'trellis', set: ['316.value=true', '288.value=2048', '186.target_face_count=120000', '322.filename_prefix="3d/<tên>"']})
   ```
   - `316=true` chọn nhánh TRELLIS.2 (mặc định của mẫu là Pixal3D).
   - Kết quả là `.glb` PBR khoảng 120k tam giác. Xem nhanh bằng `render_preview_card`.
3. **Lưu và gắn:**
   - Chép vào `projects/<slug>/clockwork/parts/`.
   - Trong module bộ phận, gọi `import_sculpt(ctx, path, name, decimate, height=… | width=…, depth=None, min_island=0)`; mặt trước lúc nặn hướng −Y.
   - Chi tiết lặp lại thì dùng `_instances(ctx, src, [(vị trí, góc Z, tỉ lệ)], parent)` để chung mesh.
   - TRELLIS nướng sẵn normal map từ lưới cao, nên `decimate` 0,07–0,25 vẫn giữ chi tiết; chi tiết nhỏ lặp nhiều thì giảm mạnh để giữ ngân sách tam giác.
   - FLUX hay vẽ thừa mảnh nhỏ lơ lửng: chọn ảnh khác hoặc đổi seed trước khi nặn.
   - **Chi tiết nặn gắn vào lỗ khoét trên tường** (khung cửa, cổng): khoét tường theo **đúng dáng nhìn thẳng của chính mesh nặn** (`silhouette_opening`), thu vào một chút để viền chi tiết đè mép tường. Đừng khoét theo hình vẽ tay, sẽ hở khe. Kiểm bằng hình chiếu thẳng 2D: chỗ nào lộ màu nền ngoài lòng khung là còn hở.
   - **Bắt buộc có test hướng** (như `test_sculpts_face_outward`): mặt trước từng bản nặn phải quay ra ngoài công trình. Soát thêm bằng mắt ở 4 góc xoay trong app, không chỉ góc 3/4 của ảnh xem trước.
4. **Thêm workflow mới:** mở giao diện ComfyUI, nạp template, gọi `await app.graphToPrompt()` rồi lấy `.output`. Lưu vào `bin/comfy_workflows/<tên>.api.json`.

## 5. Vòng soát (mỗi vòng khoảng 2 phút)

1. **Dựng nháp (CPU, khoảng 35 giây):**
   ```
   blender --background --python-exit-code 1 --python bin/scripts/clockwork/assemble_mechanism_glb.py -- --slug <slug> --mech <json> --out _archive/<đợt>/scratch/cw_vN.glb
   ```
   Xem dòng `[MECHANISM] … tam giác` (ngân sách ≤ 900k) và các dòng `[CẢNH BÁO idle]`.
2. **Ảnh xem trước qua hàng đợi:** `gpu_enqueue(null, 'blender', {mode: 'render_preview_card', glb_path})`.
3. **Ghép cạnh concept** bằng `compose_compare.ps1` thành `docs/<đợt>/screenshots/CMP_mech_vN.png`.
   - Ảnh xem trước rọi ít vào lòng công trình, phần trong trông tối. Phần đó đánh giá trong app.
   - Muốn biết kích thước thật của một bánh, đọc bounding box trong `.glb` (Blender nhập vào rồi in ra). Đừng đoán theo ảnh.
4. Sửa rồi lặp lại.

## 6. Bản chính thức và kiểm trong app

1. `gpu_enqueue(slug, 'blender', {mode: 'assemble_mechanism_glb'})`: ra `clockwork/<slug>_mechanism.glb` và tự gắn `mechanism_glb_path`.
2. `ui_open_project(slug, {stage3d: true, variant: 'mechanism', seekSec: N})` rồi `ui_screenshot`. Chụp vài mốc nhịp.
   - Bảng "Cụm chi tiết" che sân khấu: thu gọn trước khi chụp, rồi chụp riêng `[data-testid="real-pbr-stage"]`.
3. Viết `tests/test_<tên>_mechanism_glb.py` đọc thẳng `.glb`:
   - 2 clip;
   - đủ `CW_<gear>`;
   - góc quay khớp động học (≤ 0,5°);
   - tư thế mốc (kim XII);
   - số tam giác.
   Phá thử một lần (nhân góc ×1,01) để chắc test bắt được lỗi.

## 7. Cổng duyệt

Gửi anh:
- ảnh `CMP_mech_vN.png`;
- ảnh trong app ở 3 mốc nhịp;
- **danh sách chỗ còn lệch concept**.

**KTX2 (khoảng 30–40 phút CPU) chỉ chạy khi anh chốt bản cuối.** Video intro chỉ làm khi anh yêu cầu.
