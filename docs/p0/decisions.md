# Các việc cần anh chốt sau lần chạy đầu (2026-11-13)

> Mỗi mục ghi 2 phương án: giữ nguyên thì sao, thay đổi thì sao, kèm đề xuất của em. Anh chốt mục nào thì em ghi kết quả vào ledger. Phần cơ khí tạm dừng theo lời anh.

## A. Ảnh hưởng tới máy và thời gian làm việc

### A1. Tự động nén KTX2 sau mỗi lần dựng `.glb`
- **Giữ nguyên:** mỗi lần dựng lại (kể cả chỉ sửa nhỏ) đều kéo theo khoảng 40 phút CPU nén texture. Máy ấm suốt thời gian đó. Bản trong app luôn là bản nhẹ VRAM.
- **Thay đổi (chỉ nén khi chốt bản cuối):** dựng lại chỉ mất khoảng 15 giây cộng 1–2 phút render ảnh. Trong lúc làm, app dùng bản JPEG nặng VRAM hơn (tháp Eryndor khoảng +60–100 MB khi bật 3D). Nén bằng một lệnh riêng khi anh duyệt xong.
- **Em đề xuất:** thay đổi.

### A2. Mức nén KTX2 (UASTC 4 hay 2)
- **Giữ mức 4:** chất lượng texture cao nhất, mỗi lần nén khoảng 40 phút.
- **Hạ mức 2:** khoảng 10 phút, ít nóng máy. Texture kém hơn rất ít, gần như không thấy bằng mắt (bản cuối vẫn là BC7).
- **Em đề xuất:** giữ mức 4 nếu làm theo A1 (vì chỉ nén 1 lần ở bản cuối). Nếu không theo A1 thì hạ mức 2.

## B. Tháp Eryndor

### B1. Chiều cao 26 m
- **Giữ nguyên:** đo đúng trên concept, lấy cửa vào 3,5 m làm mốc.
- **Thay đổi:** nếu anh muốn tháp hùng vĩ hơn, ví dụ 34–40 m, em chỉ cần đổi tỷ lệ chung, mọi chi tiết giữ nguyên. Nhân vật đứng cạnh sẽ trông nhỏ hơn.

### B2. Toạ độ 26.95 / 33.50 (núi ven Biển Đỏ, phía đông Ai Cập)
- **Giữ nguyên:** đây là chỗ em tạm chọn. Canon chỉ ghi "núi phía đông Ai Cập, cao 1.600 m".
- **Thay đổi:** anh cho toạ độ khác (hoặc vùng khác). Chỉ là sửa 2 con số. Toạ độ quyết định vị trí trên quả cầu Trái Đất ở Selorson.

### B3. Vách đá dưới chân tháp (bản thật)
- **Giữ nguyên:** khối đá cao 6,5 m, chỉ là phần đỉnh vách. Vách 1.600 m thật sẽ làm sau, khi dựng vùng khám phá Eryndor.
- **Thay đổi:** bỏ hẳn vách đá để tháp đứng trơn như concept, hoặc làm vách cao hơn và kịch tính hơn ngay bây giờ.
- **Ghi chú:** dưới ánh sáng studio của app, vách trông trắng gần như tuyết (`screenshots\CMP_real_final_app.png`). Nếu giữ vách, em sẽ hạ sương muối xuống xám đá vôi rõ hơn.

## C. Selorson và đồng bộ

### C1. Đẩy bản nháp Tháp Eryndor (bản thật) sang Selorson ngay bây giờ, hay chờ có bản cơ khí
- **Đẩy ngay:** em build và thay Selorson Admin (đã có mã nạp gói sa bàn riêng và tab "⚙ Sa bàn cơ khí"), rồi đẩy bản nháp. Anh xem được tháp trong Admin ngay. Sau này có bản cơ khí thì đẩy lần nữa.
- **Chờ:** đỡ một lần build và thay app. Anh chưa thấy tháp trên Selorson.
- **Em đề xuất:** đẩy ngay, để kiểm luôn đường đồng bộ.

### C2. Commit mã Selorson
- **Giữ nguyên (chưa commit):** thay đổi của em nằm chung với **nhiều thay đổi cũ chưa commit** từ các phiên trước trong `backend-v3` (xoá `world_assets`, sửa `world.rs`, `library.rs`…) và `frontend-v3`. Khó tách ai sửa gì.
- **Commit:** em tách thành các commit rõ ràng, chỉ gồm phần của em. Các thay đổi cũ không phải của phiên này nên em **không tự commit**, trừ khi anh bảo.

### C3. Đưa `E:\Akunarch` vào git
- **Giữ nguyên:** chỉ có ledger và các bản `.bak` / `_archive` để quay lại. Em và Antigravity không thấy được chính xác bên kia đã sửa gì.
- **Thay đổi:** `git init` (bỏ qua `projects`, `target*`, `node_modules`, file nặng). Sửa sai và soát chéo giữa em với Antigravity dễ hơn hẳn.
- **Em đề xuất:** thay đổi, vì anh đang chia việc giữa hai agent.

### C4. Trình xem sa bàn cơ khí trên Selorson nạp bộ giải nén Draco từ mạng (gstatic của Google), giống `WorldOpenRealm`
- **Giữ nguyên:** máy mất mạng thì không xem được mô hình.
- **Thay đổi:** chép bộ giải nén vào Selorson (như Akunarch có sẵn `static/draco`), xem được hoàn toàn offline.

## D. Cổng điều khiển (MCP)

### D1. Anh tự mở Akunarch từ Desktop thì em không điều khiển được (phải đóng app để em mở lại)
- **Giữ nguyên:** an toàn hơn, cổng điều khiển chỉ mở khi em cần.
- **Thay đổi:** sửa shortcut trên Desktop để luôn mở kèm cổng điều khiển (chỉ trong máy). Anh mở app lúc nào em cũng dùng được ngay.

### D2. Ảnh xem trước của các kỳ quan cũ (Zyberon, Avalon, Stonehenge, Olympus)
- **Giữ nguyên:** vẫn dùng ảnh cũ (khung siết cố định).
- **Thay đổi:** render lại bằng cách đặt khung mới, vừa khít, không cắt đỉnh. Mất 4 job GPU, mỗi job 1–2 phút.

## E. Ghi nhận (anh không cần chốt)

- **Nhạc chuông `eryndor_pendulum_chime.wav` là dải âm ngân liên tục**, không có tiếng gõ rời, nên chưa xếp được chốt chuông cho bản cơ khí. Khi làm phần cơ khí, nên có một bản chuông gõ thật từ ToneForge.
- **Bản sao thừa do lỗi cũ** nằm ở `_archive\p0\dup_underscore_copy\` (khoảng 12 MB). Có thể xoá bất cứ lúc nào.
- **App Claude desktop tự nó cũng ngốn CPU** khi hội thoại rất dài. Bắt đầu phiên mới cho từng đợt sẽ nhẹ máy hơn.
