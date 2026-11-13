# docs/ops — Kinh nghiệm & nhật ký vận hành (dùng chung Claude ↔ Antigravity)

Đọc trước khi bắt đầu **mọi** phiên làm việc trên Akunarch / hệ sinh thái:

1. [`KINH_NGHIEM.md`](KINH_NGHIEM.md): bài học về **quy trình**, áp dụng cho mọi lần chạy. Không ghi chi tiết của riêng một công trình.
2. [`NHAT_KY_TONG.md`](NHAT_KY_TONG.md): log tổng, mỗi lần chạy 1 dòng, mới nhất ở trên. Đọc 5 dòng đầu để biết đang dở việc gì.
3. `runs/`: log chi tiết từng lần chạy, đặt tên `YYYY-MM-DD_<agent>_<đợt>.md` và viết theo [`runs/_MAU_LOG_LAN_CHAY.md`](runs/_MAU_LOG_LAN_CHAY.md).

**Quy ước ghi (bắt buộc với cả hai agent):**
- **Mở phiên:** tạo file log lần chạy từ mẫu và thêm 1 dòng "đang chạy" vào đầu `NHAT_KY_TONG.md`.
- **Trong phiên:** ghi tiến độ từng task vào `ledger.md` của đợt (`docs/<đợt>/ledger.md`), không ghi vào đây.
- **Đóng phiên:** điền phần kết quả của log lần chạy, sửa dòng log tổng thành trạng thái cuối. Có bài học quy trình mới thì thêm vào `KINH_NGHIEM.md`, ghi rõ ngày và agent.
- Không xoá log cũ. Thấy bài học cũ sai thì gạch đi (`~~…~~`) và ghi lý do ngay bên dưới.
