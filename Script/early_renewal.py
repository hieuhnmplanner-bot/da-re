# -*- coding: utf-8 -*-
"""DA-RE — NHOM GIA HAN SOM cua 1 thang (driver = pay_time GMV).
Moi lan MUA trong GMV (pay_time) = 1 lan gia han cho don LIEN TRUOC (N-1 = don REM active
ngay truoc pay_time). Thang = thang cua pay_time. CHI dung pay_time (khong dung Purchase Time).
- order_id (ghi vao list) = N-1 (don ket thuc), luon co id that -> moi order_id thuoc 1 thang.
- order_id_moi = don moi N: neu da kich hoat -> order_id that; neu chua -> ma tam TMP_<uid>_<paydate>.
- trang_thai_kich_hoat: Da/Chua kich hoat.
- Dedup: bo qua neu N-1 da nam trong danh sach het han (on-time renewal, dem o list het han).
Output: Output/early_renewal_<month>_<run_date>.csv  (flow, moi lan chay tao ban moi theo ngay)
Dung: python early_renewal.py 2026-07 [run_date]
"""
from pathlib import Path
from datetime import date
import sys
import pandas as pd
import numpy as np
try:
    from unidecode import unidecode
except Exception:
    def unidecode(s): return s

BASE = Path(__file__).resolve().parent.parent

def cu(v):
    if pd.isna(v): return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())

def nsale(s):
    if pd.isna(s): return ""
    return " ".join(unidecode(str(s)).split()).strip()

def build_team_mapper():
    dim = pd.read_csv(BASE/"Data_input"/"dim_sale.csv", dtype=str)
    dim["key"] = dim["Tên trên CRM"].map(nsale)
    coso = dim.dropna(subset=["key"]).drop_duplicates("key").set_index("key")["Cơ sở"].to_dict()
    def team_of(name):
        k = nsale(name)
        if k == "": return "Not have Sale care"
        cs = coso.get(k)
        if cs in ("HN-An Bình", "HN-Linh Đàm"): return "Offline Team HaNoi"
        if cs == "HN-Team 2": return "Inhouse 2"
        if cs == "HN-Inhouse": return "Inhouse 1"
        if cs == "HCM": return "Ho Chi Minh"
        if cs == "IND": return "IND"
        if cs == "DN": return "DN"
        return "Other"
    return team_of

def load_expiry_registry():
    reg = BASE/"State"/"expiry_registry.csv"
    if reg.exists() and reg.stat().st_size > 0:
        return set(pd.read_csv(reg, dtype=str)["order_id"].astype(str))
    return set()

def main(month, run_date=None):
    run_date = pd.Timestamp(run_date or date.today())
    lo = pd.Timestamp(month + "-01"); hi = (pd.Period(month, "M") + 1).start_time
    team_of = build_team_mapper()
    expiry_reg = load_expiry_registry()

    rem = pd.read_csv(BASE/"Data_input"/"REM.csv", dtype=str, encoding="utf-8-sig")
    rem["uid"] = rem["UID"].map(cu)
    rem["oid"] = rem["Order ID"].astype(str).str.split(".").str[0]
    rem["pt"] = pd.to_datetime(rem["Purchase Time"], errors="coerce")
    rem["price"] = pd.to_numeric(rem["Order Price VND"].astype(str).str.replace(",","",regex=False).str.replace(".","",regex=False), errors="coerce").fillna(0) * 100
    rem["remnum"] = pd.to_numeric(rem["Remain lesson Number"], errors="coerce")
    uid_now = rem.drop_duplicates("uid").set_index("uid")["remnum"].to_dict()
    rem = rem[rem["uid"] != ""].dropna(subset=["pt"]).sort_values(["uid", "pt"])
    rem["order_no_uid"] = rem.groupby("uid").cumcount() + 1     # don thu may cua UID
    order_no = dict(zip(rem["oid"], rem["order_no_uid"]))
    rem_by_oid = rem.drop_duplicates("oid").set_index("oid")
    orders_by_uid = {u: list(zip(d["pt"], d["oid"])) for u, d in rem.groupby("uid")}

    gmv = pd.read_csv(BASE/"Data_input"/"GMV.csv", low_memory=False)
    gmv["uid"] = gmv["uid"].map(cu)
    gmv["pay"] = pd.to_datetime(gmv["pay_time"], errors="coerce")
    gmv["money"] = pd.to_numeric(gmv["real_pay_vnd"].astype(str).str.replace(",","",regex=False).str.replace(" ",""), errors="coerce").fillna(0)
    gmv = gmv[(gmv["uid"] != "") & gmv["pay"].notna() & (gmv["money"] > 0)]
    gmv = gmv[(gmv["pay"] >= lo) & (gmv["pay"] < hi)].sort_values(["uid", "pay"])

    recs = []
    for _, row in gmv.iterrows():
        u = row["uid"]; t = row["pay"]
        orders = orders_by_uid.get(u, [])
        prior = [(pt, oid) for pt, oid in orders if pt < t]
        if not prior:
            continue                              # khach moi (khong co N-1) -> khong phai gia han
        nm1 = max(prior)[1]                        # N-1 = don active ngay truoc pay_time
        if nm1 in expiry_reg:
            continue                              # da o list het han -> on-time, khong dem lai
        after = [(pt, oid) for pt, oid in orders if pt >= t]
        if after:
            n_pt, n_oid = min(after)              # don kich hoat = don REM som nhat sau pay_time
            order_id_moi = n_oid; status = "Đã kích hoạt"; ngay_kh = n_pt
        else:
            order_id_moi = f"TMP_{u}_{t.strftime('%Y%m%d')}"; status = "Chưa kích hoạt"; ngay_kh = pd.NaT
        rr = rem_by_oid.loc[nm1] if nm1 in rem_by_oid.index else None
        osale = rr["Order Sale"] if rr is not None else ""
        csale = rr["Sale"] if rr is not None else ""
        recs.append({
            "month": month, "order_id": nm1, "order_no_uid": order_no.get(nm1, ""),
            "uid": u, "nhom": "Gia hạn sớm",
            "so_buoi_hien_tai": (int(uid_now.get(u)) if pd.notna(uid_now.get(u)) else ""),
            "pay_time": t.date(), "gia_tri_don_cu": float(rr["price"]) if rr is not None else 0.0,
            "order_id_moi": order_id_moi, "gia_tri_don_gia_han": float(row["money"]),
            "trang_thai_kich_hoat": status, "ngay_kich_hoat": ngay_kh,
            "sale_ban_don": osale, "team_sale_ban": team_of(osale),
            "sale_quan_ly": csale, "team_sale_quan_ly": team_of(csale),
            "teacher": (rr["Teacher"] if rr is not None else ""),
            "run_date": run_date.date(),
        })
    out = pd.DataFrame(recs)
    if not out.empty:
        out = out.drop_duplicates("order_id")     # 1 order_id (N-1) chi 1 lan
    out_path = BASE/"Output"/f"early_renewal_{month}_{run_date.date()}.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    n = len(out); act = int((out["trang_thai_kich_hoat"] == "Đã kích hoạt").sum()) if n else 0
    rev = out["gia_tri_don_gia_han"].sum() if n else 0
    print(f"Gia han som {month} | run {run_date.date()} | {n} order_id "
          f"(Đã kích hoạt {act}, Chưa {n-act}) | doanh thu {rev:,.0f}đ")
    print(f"   -> {out_path}")

if __name__ == "__main__":
    import glob
    arg = sys.argv[1] if len(sys.argv) > 1 else "all"
    rd = sys.argv[2] if len(sys.argv) > 2 else None
    if arg.lower() == "all":
        months = sorted({Path(f).stem.replace("expiry_", "")
                         for f in glob.glob(str(BASE/"Output"/"expiry_20??-??.csv"))})
        cur = str(pd.Timestamp(rd or date.today()).to_period("M"))
        for m in sorted(set(months) | {cur}):
            main(m, rd)
    else:
        main(arg, rd)
