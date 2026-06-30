# DA-RE — Dashboard Danh sách Hết hạn & Tỷ lệ Gia hạn

Theo dõi order_id đến hạn mỗi tháng và tỷ lệ gia hạn. **Không dùng end_date** (tránh dự báo thiếu chính xác).

## Pipeline (chạy local)
```bash
pip install -r requirements.txt
# 1) Tải dữ liệu (cần VPN cho Metabase)
python Script/Step0_1_rem_collect.py     # REM.csv
python Script/Step0_gmv_collect.py        # GMV.csv
# 2) Ghép GMV x REM
python Script/step3_match.py
# 3) Ghi log hằng ngày (chạy MỖI NGÀY)
python Script/daily_snapshot.py
# 4) Đầu tháng: sinh danh sách hết hạn + tổng hợp tình huống
python Script/monthly_expiry.py 2026-07
python Script/situation_summary.py 2026-07
# 5) Cập nhật trạng thái gia hạn (đầu & cuối tháng)
python Script/expiry_renewal_check.py Output/expiry_2026-07.csv
# 6) Dashboard
streamlit run app.py
```

## Quy tắc danh sách hết hạn
- Xét order_id mới nhất của mỗi UID; remaining < 10 buổi (≈ học hết trong tháng, 2 buổi/tuần).
- remaining = 0 → cần idle ≤ 10 ngày; remaining 1–9 → idle ≤ 90 ngày.
- Frozen: áp cùng quy tắc, gắn tag "Frozen".
- Dedup: một order_id chỉ thuộc đúng một tháng.

## Gia hạn
- Chỉ tính khi có **thanh toán (GMV)** hoặc **kích hoạt đơn mới (REM)**.
- `da_gia_han_M90`: gia hạn ≤ hết tháng (cohort + 3) — KPI cố định.
- `da_gia_han_vo_han`: gia hạn bất kỳ lúc nào — Real rate.


## Chỉ số gia hạn (giống DA-OD1RP)
- **CRR** (Customer Renewal Rate) = số đơn gia hạn / số đơn đến hạn.
- **RRR** (Revenue Renewal Rate) = doanh thu đơn gia hạn / tổng giá trị đơn hết hạn trong kỳ.
- **Upsell** = giá trị đơn gia hạn mới / giá trị đơn cũ (chỉ nhóm đã gia hạn). >100% = khách chi nhiều hơn.
- **Renewal Revenue** = tổng giá trị các đơn gia hạn kế tiếp.
- Tất cả tính theo 2 định nghĩa: **M+90** (KPI cố định) và **Vô hạn** (Real rate). Giá trị đơn = REM Order Price ×100 (đồng nhất với GMV).

## Team
Map tên Sale → `Data_input/dim_sale.csv` (Cơ sở) → team chuẩn (giống DA1RP). Cập nhật dim_sale khi có sale mới.

## Triển khai
Repo **PRIVATE** (có UID khách). GitHub → Streamlit Community Cloud, file chính `app.py`.
Hằng ngày/đầu tháng: chạy pipeline local → `git push` → Cloud tự deploy.
