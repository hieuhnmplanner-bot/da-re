# -*- coding: utf-8 -*-
"""DA-RE — Tab NGỦ ĐÔNG / RỜI BỎ: khach con buoi nhung dang khong hoc.
- Đóng băng chủ động: Is Frozen = 1 (cap UID).
- Im lặng rời bỏ: Is Frozen=0, còn >=1 buổi, idle > 90 ngày, chưa gia hạn, chưa vào cohort nào.
Chi keo DON MOI NHAT da kich hoat (REM) + don mua chua kich hoat (GMV) cua UID (khong keo don cu).
Kem cot 'den_han_thang' = order_id nay dang thuoc Den han thang nao (neu co).
Output: Output/dormant_<run_date>.csv
Dung: python dormant.py [run_date]
"""
from pathlib import Path
from datetime import date
import sys
import pandas as pd
try:
    from unidecode import unidecode
except Exception:
    def unidecode(s): return s

BASE = Path(__file__).resolve().parent.parent
IDLE_CHURN = 90   # nghi > 90 ngay = im lang roi bo

def cu(v):
    if pd.isna(v): return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())
def nsale(s):
    if pd.isna(s): return ""
    return " ".join(unidecode(str(s)).split()).strip()

def team_mapper():
    dim = pd.read_csv(BASE/"Data_input"/"dim_sale.csv", dtype=str)
    dim["key"] = dim["Tên trên CRM"].map(nsale)
    coso = dim.dropna(subset=["key"]).drop_duplicates("key").set_index("key")["Cơ sở"].to_dict()
    def team_of(name):
        k = nsale(name)
        if k == "": return "Not have Sale care"
        cs = coso.get(k)
        return {"HN-An Bình":"Offline Team HaNoi","HN-Linh Đàm":"Offline Team HaNoi","HN-Team 2":"Inhouse 2",
                "HN-Inhouse":"Inhouse 1","HCM":"Ho Chi Minh","IND":"IND","DN":"DN"}.get(cs, "Other")
    return team_of

def main(run_date=None):
    run_date = pd.Timestamp(run_date or date.today())
    team_of = team_mapper()
    # registry: order_id -> den han thang
    reg = BASE/"State"/"expiry_registry.csv"
    oid_month = {}
    if reg.exists() and reg.stat().st_size > 0:
        rr = pd.read_csv(reg, dtype=str); oid_month = dict(zip(rr["order_id"].astype(str), rr["month"]))

    rem = pd.read_csv(BASE/"Data_input"/"REM.csv", dtype=str, encoding="utf-8-sig")
    rem["uid"] = rem["UID"].map(cu); rem["oid"] = rem["Order ID"].astype(str).str.split(".").str[0]
    rem["pt"] = pd.to_datetime(rem["Purchase Time"], errors="coerce")
    rem["rem"] = pd.to_numeric(rem["Remain lesson Number"], errors="coerce")
    rem["fr"] = pd.to_numeric(rem["Is Frozen"], errors="coerce").fillna(0).astype(int)
    rem["last"] = pd.to_datetime(rem["Last class time"], errors="coerce")
    rem = rem[rem["uid"] != ""].sort_values(["uid","pt"])
    latest = rem.groupby("uid").tail(1).copy()
    latest["idle"] = (run_date - latest["last"]).dt.days

    # GMV: co don mua sau don moi nhat (chua kich hoat) khong
    g = pd.read_csv(BASE/"Data_input"/"GMV.csv", low_memory=False)
    g["uid"] = g["uid"].map(cu); g["pay"] = pd.to_datetime(g["pay_time"], errors="coerce")
    g["m"] = pd.to_numeric(g["real_pay_vnd"].astype(str).str.replace(",","",regex=False).str.replace(" ",""), errors="coerce").fillna(0)
    gby = g.dropna(subset=["pay"]).groupby("uid").apply(lambda d: sorted(zip(d["pay"], d["m"])), include_groups=False).to_dict()

    recs = []
    for _, o in latest.iterrows():
        u = o["uid"]; boundary = o["pt"]
        bought_after = [(t,m) for t,m in gby.get(u, []) if pd.notna(boundary) and t > boundary and m > 0]
        renewed = len(bought_after) > 0
        frozen = o["fr"] == 1
        if frozen:
            loai = "Đóng băng chủ động"
        elif (not renewed) and pd.notna(o["rem"]) and o["rem"] >= 1 and pd.notna(o["idle"]) and o["idle"] > IDLE_CHURN:
            loai = "Im lặng rời bỏ"
        else:
            continue   # khong thuoc nhom ngu dong
        pend = ""
        if bought_after:
            pend = "TMP_%s_%s" % (u, min(bought_after)[0].strftime("%Y%m%d"))
        recs.append({
            "run_date": run_date.date(), "uid": u, "loai": loai,
            "order_id": o["oid"], "order_no_uid": "",
            "remaining": (int(o["rem"]) if pd.notna(o["rem"]) else ""),
            "last_study": o["last"], "idle_ngay": (int(o["idle"]) if pd.notna(o["idle"]) else ""),
            "don_chua_kich_hoat": pend,
            "den_han_thang": oid_month.get(o["oid"], ""),
            "sale_ban_don": o.get("Order Sale",""), "team_sale_ban": team_of(o.get("Order Sale","")),
            "sale_quan_ly": o.get("Sale",""), "team_sale_quan_ly": team_of(o.get("Sale","")),
            "teacher": o.get("Teacher",""),
        })
    out = pd.DataFrame(recs)
    # order_no_uid
    on = rem.dropna(subset=["pt"]).drop_duplicates("oid").sort_values(["uid","pt"])
    on["no"] = on.groupby("uid").cumcount()+1
    nomap = dict(zip(on["oid"], on["no"]))
    if not out.empty: out["order_no_uid"] = out["order_id"].map(nomap)
    out_path = BASE/"Output"/f"dormant_{run_date.date()}.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")
    nfr = int((out["loai"]=="Đóng băng chủ động").sum()) if len(out) else 0
    nsl = int((out["loai"]=="Im lặng rời bỏ").sum()) if len(out) else 0
    print(f"Ngủ đông {run_date.date()}: {len(out)} UID (Đóng băng {nfr}, Im lặng {nsl}) -> {out_path}")

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
