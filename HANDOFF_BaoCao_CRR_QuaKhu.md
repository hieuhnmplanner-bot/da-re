# HANDOFF — Dự án Báo cáo CRR Quá khứ (nối tiếp DA-RE)

> Tài liệu bàn giao để tiếp tục ở một cuộc trò chuyện mới. Mục tiêu: dựng **báo cáo tỷ lệ gia hạn (CRR) cho dữ liệu QUÁ KHỨ** trên repo + Streamlit riêng, tái dùng tối đa từ dự án **DA-RE**, và **không đếm trùng** với DA-RE.

---

## 0. TL;DR

- **DA-RE** = báo cáo gia hạn chạy kiểu **snapshot** → chỉ phản ánh đúng **từ 2026-07 về sau**.
- **Dự án mới** = báo cáo **quá khứ (≤ 2026-06)**, ước lượng "tháng tới hạn" bằng công thức, để biết CRR thực tế đã qua.
- **Chống trùng**: chỉ tính order có `end_month < 2026-07` **VÀ** order_id **không nằm** trong `State/expiry_registry.csv` của DA-RE.

---

## A. Mô hình DA-RE hiện tại (tóm tắt)

**Bài toán:** đo tỷ lệ khách gia hạn gói học (Palfish, gia sư tiếng Anh). Mỗi khách (UID) có thể có nhiều đơn (order_id).

**Mẫu số — danh sách "Đến hạn" (khóa đầu tháng):**
- Số buổi còn **< 15** vào đầu tháng, **idle ≤ 90 ngày**, **loại remaining = 0**.
- **Tháng đầu (2026-07):** dùng **TỔNG số buổi còn của UID** + `latest_order_id` (chưa có lịch sử tiêu thụ).
- **Từ 2026-08:** dùng **per-order FIFO** (số buổi còn của từng đơn).
- Đơn **Frozen** (bảo lưu) vẫn tính, gắn nhãn. **1 order_id chỉ vào đúng 1 tháng** (registry).

**Tử số — đã gia hạn:** đơn nào đã có đơn kế (mua/kích hoạt). Chia theo thời điểm: **Đúng hạn** (mua trong tháng tới hạn) / **Sớm–trước hạn** (mua tháng trước) / **Muộn** (mua tháng sau).

**Chỉ số:** CRR = tử/mẫu · RRR = DT gia hạn / tổng giá trị đơn · Upsell = giá trị mới/cũ · Renewal Revenue. **2 chế độ: M+90 (KPI cố định) & Real (bất cứ lúc nào).**

**Cơ chế FIFO (quan trọng, tái dùng được cho dự án mới):**
- REM chỉ cho **TỔNG buổi còn cấp UID** (`Remain lesson Number`), không tách theo đơn.
- Nhưng REM có cột **`Total Lesson`** = số buổi GỐC của **từng đơn** (đã xác minh là cấp order).
- Quy tắc FIFO: đơn mua trước học hết trước. Suy ra số buổi còn từng đơn:
  - `đã học = Σ(Total Lesson) − tổng buổi còn (UID)`
  - trừ số đã học vào đơn cũ trước → đơn cũ còn = `Total Lesson(cũ) − đã học`.
- Ví dụ thật (UID 3035203085): đơn cũ 53 + đơn mới 106 = 159; còn 119 → đã học 40 → đơn cũ còn 13.

---

## B. Tài sản DA-RE tái dùng được (thư mục `DA-RE/Script/`)

| File | Vai trò | Dùng cho dự án mới? |
|---|---|---|
| `Step0_1_rem_collect.py` | Tải REM.csv từ Metabase (card 14393) | ✅ nguyên |
| `Step0_gmv_collect.py` | Tải GMV.csv từ Google Sheets (3 tab) | ✅ nguyên |
| `step3_match.py` | Ghép GMV × REM (money ×100 + package + time, ±8%) | ✅ nguyên |
| `expiry_renewal_check.py` | **Logic dò gia hạn** (tìm đơn kế qua GMV pay / REM activation sau đơn cũ) | ✅ tái dùng lõi |
| `fifo_lessons.py` | Engine FIFO (Total Lesson → số buổi còn từng đơn) | ✅ nếu cần |
| `dim_sale.csv` + mapping team | Gán Sale → Cơ sở → Team | ✅ nguyên |
| `app.py` | Khung Streamlit (bố cục, đa ngôn ngữ VI/EN/ZH, thẻ CRR/RRR/Upsell) | ✅ copy làm khung |
| `State/expiry_registry.csv` | **Danh sách order_id đã được DA-RE tính** | ✅ **làm bộ lọc loại trừ** |

---

## C. KẾ HOẠCH — Báo cáo CRR Quá khứ (dự án mới)

### C1. Ước lượng "tháng tới hạn" cho mỗi đơn quá khứ
```
end_date  ≈ Purchase Time (ngày kích hoạt) + (Total Lesson ÷ 2 buổi/tuần) × 7
          = Purchase Time + Total Lesson × 3.5 (ngày)
end_month = tháng của end_date
```
- Hiệu chỉnh: đơn **Frozen** kéo dài hơn → cân nhắc loại hoặc cộng thời gian đóng băng.
- Đối chiếu `end_date` ước lượng với `Last class time` thực (REM) để bắt ca lệch nhiều.

### C2. Cơ chế loại trừ (không trùng DA-RE) — MẤU CHỐT
> Tính order_id vào tháng M (= end_month) **khi và chỉ khi**:
> 1. **M < 2026-07** (trước mốc DA-RE bắt đầu), **VÀ**
> 2. **order_id KHÔNG có trong `State/expiry_registry.csv`** của DA-RE.
- (1) chia ranh giới: quá khứ ≤ 2026-06, DA-RE ≥ 2026-07.
- (2) xử lý ca biên (ước lượng hết tháng 6 nhưng thực tế sang tháng 7 → DA-RE đã bắt).
- → mỗi order_id chỉ đếm **đúng 1 lần** trên cả 2 báo cáo.

### C3. Tính CRR quá khứ
- **Mẫu số** tháng M = số order có end_month = M (sau loại trừ).
- **Tử số** = trong đó khách đã mua đơn kế (dùng lại logic `expiry_renewal_check`).
- Lợi thế: quá khứ đã "chốt" → CRR là con số cuối cùng, không đổi. Tính được cả M+90 lẫn Real chính xác.

---

## D. Sự thật kỹ thuật về dữ liệu (đừng khám phá lại)

- **REM `Remain lesson Number` = cấp UID** (giống hệt mọi đơn của 1 UID), KHÔNG per-order.
- **REM `Total Lesson` = cấp ORDER** (số buổi gốc mỗi đơn). ✅
- **REM `Purchase Time` = ngày KÍCH HOẠT** đơn.
- **REM chỉ chứa đơn ĐÃ kích hoạt.** Đơn đã mua nhưng **chưa kích hoạt** → chỉ nằm ở GMV (không có bản ghi REM).
- **Ghép đơn:** khóa chính = tiền (REM `Order Price VND` × 100), phụ = tên gói / tên sale; dung sai ±8%.
- **Đọc REM.csv** có thể lỗi encoding (ký tự Trung): fallback `encoding="latin-1", engine="python"` (chỉ cần UID/Order ID/Purchase Time/Total Lesson — đều ASCII/số).
- **DA-RE bắt đầu cohort từ 2026-07** (đây là mốc phân chia quá khứ / hiện tại).
- **Số liệu tham chiếu DA-RE tháng 7/2026:** mẫu số 829, CRR (M+90) 12,9%.

---

## E. Đường dẫn & hạ tầng

- Thư mục dự án DA-RE: `C:\Users\ASUS\Desktop\Palfish data\DA-RE`
- Dữ liệu thô (gitignore): `Data_input/REM.csv`, `Data_input/GMV.csv`
- Registry loại trừ: `State/expiry_registry.csv`
- Log FIFO hằng ngày: `State/daily_uid_log.csv` (đã có cột `order_id_tieu_hao`, `so_buoi_con_cua_order`)
- **Git (DA-RE):** `origin` = `github.com/hieuhnmplanner-bot/da-re` → **da-re-2026.streamlit.app** (bản chính, run_daily tự đẩy); `v2` = `github.com/hieuhnmplanner-bot/da-re-2` → da-re-2.streamlit.app.
- **Dự án mới:** tạo repo + Streamlit RIÊNG (đừng đẩy chung).

---

## F. Việc đầu tiên nên làm ở chat mới

1. Tạo thư mục/repo mới cho báo cáo quá khứ (vd `DA-RE-Past`).
2. Copy các script tái dùng (mục B) sang.
3. Viết script tính `end_month` (mục C1) + áp bộ lọc loại trừ (mục C2).
4. Dò gia hạn cho từng cohort quá khứ (mục C3) → ra CRR theo tháng.
5. Dựng Streamlit từ khung `app.py`.
6. **Kiểm chứng chống trùng:** đảm bảo không order_id nào vừa ở báo cáo quá khứ vừa trong `expiry_registry.csv`.
