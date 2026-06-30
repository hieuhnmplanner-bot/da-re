# -*- coding: utf-8 -*-
"""DA-RE — Trang thai GIA HAN + Sale/Team/Teacher + GIA TRI don (cho CRR/RRR/Upsell).
Gia han chi tinh khi co THANH TOAN (GMV money>0) HOAC KICH HOAT don moi (REM),
thoi diem muon hon Purchase Time cua don dang het han (cung UID).
- da_gia_han_M90    : gia han <= het thang (cohort+3)  (KPI co dinh)
- da_gia_han_vo_han : gia han bat ky luc nao (Real rate)
- gia_tri_don_cu       : gia tri don dang het han (REM Order Price x100)
- gia_tri_don_gia_han  : gia tri don gia han ke tiep (paid GMV, hoac REM x100)
Team: map ten Sale -> dim_sale (Co so) -> team chuan (giong DA1RP).
Dung: python expiry_renewal_check.py Output/expiry_2026-07.csv [run_date]
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

def main(exp_path, run_date=None):
    exp_path = Path(exp_path)
    run_date = pd.Timestamp(run_date or date.today())
    exp = pd.read_csv(exp_path)
    exp["uid"] = exp["uid"].astype(str).map(cu)
    exp["order_id"] = exp["order_id"].astype(str).str.split(".").str[0]
    month = str(exp["month"].iloc[0]) if "month" in exp.columns else exp_path.stem
    cutoff = (pd.Period(month, "M") + 3).end_time.normalize()
    team_of = build_team_mapper()

    rem = pd.read_csv(BASE/"Data_input"/"REM.csv", dtype=str, encoding="utf-8-sig")
    rem["uidm"] = rem["UID"].map(cu)
    rem["oid"] = rem["Order ID"].astype(str).str.split(".").str[0]
    rem["pt"] = pd.to_datetime(rem["Purchase Time"], errors="coerce")
    rem["price"] = pd.to_numeric(rem["Order Price VND"].astype(str).str.replace(",","",regex=False).str.replace(".","",regex=False), errors="coerce").fillna(0) * 100
    rem_by_oid = rem.drop_duplicates("oid").set_index("oid")
    rem_price = rem_by_oid["price"].to_dict()
    rem_orders_by_uid = rem.dropna(subset=["pt"]).groupby("uidm").apply(
        lambda d: list(zip(d["oid"], d["pt"])), include_groups=False).to_dict()

    gxr = pd.read_csv(BASE/"Output"/"GMV_x_REM.csv", low_memory=False)
    gxr["oid"] = gxr["Order ID"].astype(str).str.split(".").str[0]
    gxr["pay"] = pd.to_datetime(gxr["pay_time"], errors="coerce")
    buy_date = gxr.dropna(subset=["pay"]).drop_duplicates("oid").set_index("oid")["pay"].to_dict()

    gmv = pd.read_csv(BASE/"Data_input"/"GMV.csv", low_memory=False)
    gmv["uidm"] = gmv["uid"].map(cu)
    gmv["pay"] = pd.to_datetime(gmv["pay_time"], errors="coerce")
    gmv["money"] = pd.to_numeric(gmv["real_pay_vnd"].astype(str).str.replace(",","",regex=False).str.replace(" ",""), errors="coerce").fillna(0)
    gmv_by_uid = gmv.dropna(subset=["pay"]).groupby("uidm").apply(
        lambda d: list(zip(d["pay"], d["money"])), include_groups=False).to_dict()

    recs = []
    for _, row in exp.iterrows():
        oid = row["order_id"]; u = row["uid"]
        rr = rem_by_oid.loc[oid] if oid in rem_by_oid.index else None
        boundary = rr["pt"] if rr is not None else pd.NaT
        order_sale = (rr["Order Sale"] if rr is not None else "")
        cur_sale = (rr["Sale"] if rr is not None else "")
        gia_tri_cu = float(rem_price.get(oid, 0))
        # ung vien gia han: (ngay, gia tri)
        g_cands = [(t, m) for t, m in gmv_by_uid.get(u, []) if pd.notna(boundary) and t > boundary and m > 0]
        r_cands = [(t, float(rem_price.get(oo, 0))) for oo, t in rem_orders_by_uid.get(u, []) if pd.notna(boundary) and t > boundary and oo != oid]
        cands = sorted(g_cands + r_cands, key=lambda x: x[0])
        if cands:
            ngay_gh, gia_tri_gh = cands[0]
            src = "GMV+REM" if (g_cands and r_cands) else ("GMV" if g_cands else "REM")
        else:
            ngay_gh, gia_tri_gh, src = pd.NaT, np.nan, ""
        recs.append({
            "month": month, "order_id": oid, "uid": u, "tag": row.get("tag",""),
            "ly_do_vao_list": row.get("reason",""),
            "ngay_mua": buy_date.get(oid, pd.NaT), "ngay_kich_hoat": boundary,
            "remaining": row.get("remaining"), "last_study": row.get("last_study"),
            "idle_ngay": row.get("idle"),
            "sale_ban_don": order_sale, "team_sale_ban": team_of(order_sale),
            "sale_quan_ly": cur_sale, "team_sale_quan_ly": team_of(cur_sale),
            "teacher": (rr["Teacher"] if rr is not None else ""),
            "gia_tri_don_cu": gia_tri_cu,
            "da_gia_han_M90": bool(cands) and (ngay_gh <= cutoff),
            "da_gia_han_vo_han": bool(cands),
            "ngay_gia_han": ngay_gh, "gia_tri_don_gia_han": gia_tri_gh,
            "nguon_gia_han": src,
            "so_ngay_den_gia_han": ((ngay_gh - boundary).days if (pd.notna(ngay_gh) and pd.notna(boundary)) else np.nan),
            "run_date": run_date.date(),
        })
    out = pd.DataFrame(recs)
    out_path = BASE/"Output"/f"expiry_{month}_status_{run_date.date()}.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")

    N = len(out)
    def kpis(col):
        ren = out[col]
        due = N
        renewed = int(ren.sum())
        crr = round(renewed/due*100, 1) if due else 0
        exp_tot = out["gia_tri_don_cu"].sum()
        new_ren = out.loc[ren, "gia_tri_don_gia_han"].sum()
        old_ren = out.loc[ren, "gia_tri_don_cu"].sum()
        rrr = round(new_ren/exp_tot*100, 1) if exp_tot else 0
        ups = round(new_ren/old_ren*100, 1) if old_ren else 0
        return renewed, crr, rrr, ups, new_ren
    r90, crr90, rrr90, up90, rev90 = kpis("da_gia_han_M90")
    print(f"List {month} | {N} đến hạn | mốc M+90 = {cutoff.date()}")
    print(f"   [M+90] Gia han {r90} | CRR {crr90}% | RRR {rrr90}% | Upsell {up90}% | Renewal Rev {rev90:,.0f}đ")

    track = BASE/"Output"/"renewal_rate_tracking.csv"
    line = pd.DataFrame([{"month":month,"run_date":run_date.date(),"list_size":N,
        "gia_han_M90":r90,"CRR_M90_%":crr90,"RRR_M90_%":rrr90,"Upsell_M90_%":up90,
        "renewal_revenue_M90":round(rev90),
        "gia_han_vo_han":int(out["da_gia_han_vo_han"].sum())}])
    if track.exists() and track.stat().st_size > 0:
        line.to_csv(track, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        line.to_csv(track, index=False, encoding="utf-8-sig")
    print(f"   -> {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2: sys.exit("Dung: python expiry_renewal_check.py <file> [run_date]")
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
