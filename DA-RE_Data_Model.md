# DA-RE — Data Model & Pipeline (Tài liệu cho Data Analyst)

> Hệ thống đo **tỷ lệ gia hạn (renewal)** của Palfish (gia sư tiếng Anh). Mỗi khách (UID) mua các gói buổi học (order); khi gói sắp hết, ta muốn biết họ có mua gói tiếp theo (gia hạn) hay không. Tài liệu này mô tả nguồn dữ liệu, pipeline, mô hình tính, các edge case và cấu trúc file để bạn có thể tự phân tích / tái lập.

---

## 1. Mục tiêu & khái niệm

- **Đến hạn (Due):** order sắp hết buổi vào đầu tháng → cần chăm sóc gia hạn. Đây là **mẫu số**.
- **Đã gia hạn (Renewed):** khách trong danh sách đến hạn đã mua/kích hoạt order kế tiếp. Đây là **tử số**.
- **CRR = Tử số / Mẫu số** (Customer Renewal Rate). Ngoài ra có RRR (theo doanh thu), Upsell, Renewal Revenue.
- Nguyên tắc xuyên suốt: **mỗi order_id chỉ được tính vào đúng 1 tháng** (chống trùng bằng registry); **mẫu số khóa đầu tháng**, tử số cập nhật hằng ngày.

---

## 2. Nguồn dữ liệu

### 2.1. `Data_input/REM.csv` — export từ Metabase (CRM)
Đơn vị: **1 dòng = 1 order** của 1 UID.

| Cột | Ý nghĩa | ⚠️ Lưu ý quan trọng |
|---|---|---|
| `UID` | ID khách | |
| `Order ID` | ID đơn hàng | khóa chính order |
| `Remain lesson Number` | Số buổi còn | **CẤP UID** — giống hệt trên mọi order của cùng 1 UID (KHÔNG phải per-order) |
| `Total Lesson` | Số buổi GỐC của gói | **CẤP ORDER** — khác nhau theo từng đơn |
| `Purchase Time` | Thời điểm **kích hoạt** đơn | dùng làm mốc thứ tự đơn (FIFO) |
| `Last class time` | Buổi học cuối | **CẤP UID** |
| `Is Frozen` | Đang bảo lưu (1/0) | |
| `Package Name`, `Order Price VND`, `Order Sale`, `Sale`, `Teacher`, `PF level`, `depart*_name` | Gói, giá, sale, teacher, phân cấp | dùng để ghép + gán team |

**Quirk quan trọng của REM:**
- `Remain lesson Number` và `Last class time` là **cấp UID** (tổng/gộp), không tách theo order. Đây là lý do phải dùng FIFO (mục 5.2).
- REM **chỉ chứa order ĐÃ kích hoạt.** Đơn đã thanh toán nhưng **chưa kích hoạt** → không có bản ghi REM (chỉ có ở GMV).
- File có ký tự tiếng Trung → khi đọc bằng pandas nên fallback `encoding="latin-1", engine="python"` (các cột cần: UID/Order ID/Total Lesson/Purchase Time đều ASCII/số).

### 2.2. `Data_input/GMV.csv` — doanh thu (Google Sheet, 3 miền HN/HCM/ĐN)
Đơn vị: **1 dòng = 1 lần thanh toán**.

| Cột | Ý nghĩa |
|---|---|
| `uid` | ID khách |
| `pay_time` | Ngày thanh toán (= ngày MUA, có thể trước ngày kích hoạt) |
| `real_pay_vnd` | Số tiền thực trả (VND) |
| `package`, `sales`, `Team`, `phone`, `full_price_vnd`, `gmv_rmb` | Gói, sale, team, SĐT… |

**Quirk:** `real_pay_vnd` có nhiều định dạng (float `10080000.0`, VN `10.080.000`, dấu phẩy) → cần chuẩn hóa cẩn thận (đã xử lý trong `Step0_gmv_collect.py`, hàm `clean_vnd`).

### 2.3. `dim_sale.csv` — map Sale → Cơ sở → Team.

---

## 3. Pipeline (thư mục `Script/`)

**Chạy hằng ngày — `run_daily.bat`:**
1. `Step0_1_rem_collect.py` → tải REM.csv (Metabase).
2. `Step0_gmv_collect.py` → tải GMV.csv (Google Sheet).
3. `step3_match.py` → ghép GMV × REM → `Output/GMV_x_REM.csv`.
4. `daily_snapshot.py` → ghi snapshot trạng thái từng UID vào `State/daily_uid_log.csv` (kèm cột FIFO).
5. `expiry_renewal_check.py` (loop mọi tháng đã có list) → cập nhật **tử số** (ai đã gia hạn).
6. `dormant.py` → nhóm ngủ đông / rời bỏ.

**Chạy đầu tháng — `run_monthly.bat`:**
1. `monthly_expiry.py <YYYY-MM>` → dựng **danh sách Đến hạn** (mẫu số) → `Output/expiry_<month>.csv` + cập nhật `State/expiry_registry.csv`.
2. `expiry_renewal_check.py` → tử số ban đầu → `Output/expiry_<month>_status_<run_date>.csv`.
3. `dormant.py`.

> **Thứ tự đầu tháng:** chạy `run_daily` TRƯỚC (tạo snapshot đầu tháng) rồi `run_monthly` SAU.

---

## 4. Ghép đơn GMV × REM (`step3_match.py`)

- Khóa chính = **số tiền**: `REM.Order Price VND × 100` so với `GMV.real_pay_vnd`, dung sai `max(10.000đ, 8%)`.
- Vùng nới (fuzzy) bắt buộc trùng thêm 1 khóa phụ mạnh: **tên Sale** hoặc **tên gói**.
- Nhiều đơn/UID: gom theo bucket tiền, xếp theo thời gian để phân định.
- Giữ full outer (GMV Only / REM Only đều giữ). Độ chính xác ~99.8% trên bộ truth.

---

## 5. Mô hình tính gia hạn

### 5.1. MẪU SỐ — danh sách "Đến hạn"
Điều kiện tại **đầu tháng**:
- Số buổi còn **≤ 20** (chốt với sale 08/2026; trước đó là <15).
- **idle ≤ 90 ngày** (buổi học cuối trong 90 ngày; quá 90 → coi rời bỏ).
- **Loại `remaining = 0`** (đã hết sạch — biến không đoán trước, số ít).
- Đơn **Frozen** vẫn tính, gắn nhãn.

**Chọn mốc "đầu tháng":** dùng **snapshot đầu tiên ≥ ngày 1** trong `daily_uid_log` (dữ liệu đã settle sau đợt kích hoạt cuối tháng trước). Chỉ khi chưa có snapshot nào trong tháng mới thì lùi về snapshot gần nhất trước đó. *(Snapshot cuối tháng trước, vd 31/7, hay dính data-lag: đơn vừa kích hoạt chưa kịp cộng buổi vào tổng UID.)*

**Tháng đầu vs tháng sau:**
- **Tháng đầu tiên** (chưa có lịch sử tiêu thụ của tháng liền trước): dùng **TỔNG REM cấp UID** + `latest_order_id`.
- **Từ tháng sau:** dùng **per-order FIFO** (mục 5.2).

### 5.2. FIFO — tái dựng số buổi còn của TỪNG order
Vì `Remain lesson Number` chỉ cấp UID, ta suy ra per-order bằng `Total Lesson` + quy tắc FIFO (đơn mua trước tiêu trước):
```
Đã học (UID)          = Σ(Total Lesson các đơn) − Remain lesson Number (UID)
Số buổi còn đơn cũ nhất = Total Lesson(cũ) − Đã học   (trừ dồn oldest→newest; đơn mới chưa đụng)
order_id_tieu_hao      = đơn cũ nhất còn > 0 buổi (= đơn sắp hết hạn)
```
Ví dụ: đơn cũ Total 53 + đơn mới Total 106 = 159; UID còn 119 → đã học 40 → đơn cũ = 53−40 = **13**, đơn mới = 106.
→ Ghi 2 cột vào log: `order_id_tieu_hao`, `so_buoi_con_cua_order`. **Mỗi ngày tự tính độc lập** (không trừ dồn từ hôm trước) nên hụt 1 ngày không hỏng dây chuyền.

### 5.3. TỬ SỐ — đã gia hạn (theo thời điểm)
Trong danh sách, order nào đã có đơn kế (mua GMV / kích hoạt REM sau đơn cũ) → đã gia hạn. Chia:
- **Đúng hạn:** mua đơn kế trong tháng tới hạn.
- **Sớm / trước hạn:** mua đơn kế từ tháng TRƯỚC.
- **Muộn:** mua đơn kế ở tháng SAU.

### 5.4. Chỉ số
- **CRR** = số đã gia hạn ÷ mẫu số.
- **RRR** = Σ doanh thu đơn gia hạn ÷ Σ giá trị đơn trong danh sách.
- **Upsell** = giá trị đơn mới ÷ giá trị đơn cũ (nhóm đã gia hạn).
- **Renewal Revenue** = Σ giá trị đơn gia hạn.
- **2 chế độ:** `da_gia_han_M90` (gia hạn trong ~3 tháng kể từ kỳ tới hạn — KPI cố định) và `da_gia_han_vo_han` (Real — bất cứ lúc nào).

---

## 6. Chống trùng & Witnessed-crossing (`State/expiry_registry.csv`)

- **Registry** ghi mọi order_id đã được đưa vào danh sách của bất kỳ tháng nào (cột: order_id, uid, month, tag). `monthly_expiry` loại các order_id đã có trong registry (của tháng trước) → **1 order = 1 tháng**.
- **Dựng lại 1 tháng sạch:** khi chạy lại 1 tháng, registry tự bỏ entry cũ CỦA CHÍNH tháng đó rồi dựng lại (idempotent), không đụng tháng khác.
- **Witnessed-crossing (từ tháng 2+):** với đơn cũ của khách **đã gia hạn sớm** (`order_id_tieu_hao ≠ latest_order_id`), chỉ giữ nếu log **chứng kiến đơn đó rớt từ ≥ ngưỡng → dưới ngưỡng trong kỳ**. Đơn vốn đã dưới ngưỡng từ trước khi theo dõi = backlog → loại. (Tránh dồn cục đơn quá khứ vào tháng hiện tại.)

---

## 7. Các edge case đã xử lý / đang lưu ý

| Vấn đề | Cách xử lý / trạng thái |
|---|---|
| `Remain` cấp UID, không per-order | Dùng `Total Lesson` + FIFO |
| Đơn chưa kích hoạt | Không có ở REM, chỉ ở GMV (GMV Only) |
| Data-lag đơn kích hoạt cuối tháng | Chọn snapshot ≥ ngày 1 (đã settle) thay vì cuối tháng trước |
| Cold-start / đổi ngưỡng | Tháng đầu áp ngưỡng dồn tồn kho một lần; ổn định từ tháng sau (registry loại) |
| **Gói nhỏ (vd 26 buổi)** | ≤20 chạm quá sớm (còn 20/26 đã vào list) → khách gói nhỏ lặp lại nhiều tháng. **ĐANG cân nhắc ngưỡng theo tỷ lệ gói** (chưa chốt) |
| Frozen | Vẫn tính, gắn nhãn; nhóm ngủ đông tách riêng |

---

## 8. Cấu trúc file (output)

| File | Đơn vị | Nội dung |
|---|---|---|
| `Output/expiry_<month>.csv` | 1 order | Danh sách Đến hạn (mẫu số): order_id, uid, remaining, last_study, idle, is_frozen, tag, reason, month |
| `Output/expiry_<month>_status_<run_date>.csv` | 1 order | **Bản đầy đủ** (dashboard đọc): thêm sale/team, order_no_uid, gia_tri_don_cu, ngay_gia_han, gia_tri_don_gia_han, da_gia_han_M90/vo_han, order_id_moi, so_buoi_hien_tai… |
| `Output/GMV_x_REM.csv` | 1 order | Kết quả ghép GMV×REM (có phone → gitignore) |
| `State/daily_uid_log.csv` | 1 UID/ngày | Lịch sử snapshot: remaining, last_study, is_frozen, **order_id_tieu_hao, so_buoi_con_cua_order** |
| `State/expiry_registry.csv` | 1 order | Sổ chống trùng (order_id → tháng) |
| `Output/dormant_<date>.csv` | 1 UID | Ngủ đông (Frozen) + im lặng rời bỏ |

Dashboard `app.py` (Streamlit) đọc file `*_status_*` mới nhất (chọn theo NGÀY trong tên file).

---

## 9. Số liệu tham chiếu (tại 08/2026)

- Tháng 7 (ngưỡng <15, tháng đầu, tổng UID): mẫu số **829**.
- Tháng 8 (ngưỡng ≤20, per-order): mẫu số **~1053** (gồm 586 nhóm 1–14 + 467 nhóm 15–20 — vùng mới do nới ngưỡng, dồn một lần).
- Registry: 829 (T7) + 1053 (T8) ≈ 1882, không trùng.

---

## 10. Hạn chế & TODO

- Ngưỡng theo **tỷ lệ gói** cho gói nhỏ (chưa chốt).
- Witnessed-crossing chỉ áp cho đơn `renewed_early`; nhóm 15–20 chưa gia hạn ở tháng chuyển tiếp vẫn dồn một lần.
- FIFO giả định tiêu thụ đúng thứ tự oldest→newest (Palfish có thể không tuyệt đối).
- `end_date` quá khứ (dự án phụ) ước lượng bằng `Purchase Time + Total Lesson × 3.5 ngày` (2 buổi/tuần) — chỉ tương đối.

---

## 11. Tái lập / phân tích

- Đọc thẳng `REM.csv` + `GMV.csv` để tự phân tích thô.
- Hoặc dùng `GMV_x_REM.csv` (đã ghép) + `daily_uid_log.csv` (lịch sử FIFO) + `expiry_<month>_status_*.csv` (bản cuối) để đối chiếu logic.
- Mọi script ở `Script/`, chạy độc lập được (đọc REM/GMV, không cần DB).
