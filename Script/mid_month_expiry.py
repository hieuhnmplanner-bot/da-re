# -*- coding: utf-8 -*-
"""DA-RE — HẾT HẠN PHÁT SINH: don dau thang con >=10 buoi nhung VE 0 BUOI giua thang.
Doc daily_uid_log: don xuat hien remaining=0 trong thang M, truoc do >0, chua thuoc Den han,
va UID KHONG mua don moi (neu mua thi la Gia han som). -> con-thieu-log thi ket qua ~0 (binh thuong).
Output: Output/mid_expiry_<month>_<run_date>.csv
Dung: python mid_month_expiry.py 2026-07 [run_date]
"""
from pathlib import Path
from datetime import date
import sys
import pandas as pd

BASE = Path(__file__).resolve().parent.parent

def cu(v):
    if pd.isna(v): return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())

def main(month, run_date=None):
    run_date = pd.Timestamp(run_date or date.today())
    lo = pd.Timestamp(month+"-01"); hi = (pd.Period(month,"M")+1).start_time
    log = BASE/"State"/"daily_uid_log.csv"
    cols = ["month","order_id","uid","ngay_ve_0","run_date"]
    if not log.exists() or log.stat().st_size == 0:
        pd.DataFrame(columns=cols).to_csv(BASE/"Output"/f"mid_expiry_{month}_{run_date.date()}.csv", index=False, encoding="utf-8-sig")
        print(f"Hết hạn phát sinh {month}: 0 (chưa có log)"); return
    lg = pd.read_csv(log, dtype=str)
    lg["d"] = pd.to_datetime(lg["snapshot_date"], errors="coerce")
    lg["rem"] = pd.to_numeric(lg["remaining"], errors="coerce")
    lg["uid"] = lg["uid"].map(cu); lg["oid"] = lg["latest_order_id"].astype(str).str.split(".").str[0]
    # registry Den han + gia han som (de loai trung)
    seen = set()
    reg = BASE/"State"/"expiry_registry.csv"
    if reg.exists() and reg.stat().st_size>0: seen |= set(pd.read_csv(reg,dtype=str)["order_id"].astype(str))
    # GMV mua trong thang -> UID da gia han (bo qua)
    g = pd.read_csv(BASE/"Data_input"/"GMV.csv", low_memory=False)
    g["uid"] = g["uid"].map(cu); g["pay"] = pd.to_datetime(g["pay_time"], errors="coerce")
    g["m"] = pd.to_numeric(g["real_pay_vnd"].astype(str).str.replace(",","",regex=False).str.replace(" ",""),errors="coerce").fillna(0)
    bought_uid = set(g[(g["pay"]>=lo)&(g["pay"]<hi)&(g["m"]>0)]["uid"])

    recs = []
    for oid, grp in lg.dropna(subset=["d"]).groupby("oid"):
        grp = grp.sort_values("d")
        in_m = grp[(grp["d"]>=lo)&(grp["d"]<hi)]
        if in_m.empty: continue
        zero_day = in_m[in_m["rem"]==0]["d"].min()
        if pd.isna(zero_day): continue                        # khong ve 0 trong thang
        before = grp[grp["d"]<zero_day]
        if before.empty or (before["rem"]>0).sum()==0: continue  # phai tung >0 truoc do
        u = grp["uid"].iloc[0]
        if oid in seen or u in bought_uid: continue           # da o Den han / da gia han
        recs.append({"month":month,"order_id":oid,"uid":u,"ngay_ve_0":zero_day.date(),"run_date":run_date.date()})
    out = pd.DataFrame(recs, columns=cols)
    out.to_csv(BASE/"Output"/f"mid_expiry_{month}_{run_date.date()}.csv", index=False, encoding="utf-8-sig")
    print(f"Hết hạn phát sinh {month}: {len(out)} order_id")

if __name__ == "__main__":
    import glob
    arg = sys.argv[1] if len(sys.argv)>1 else "all"
    rd = sys.argv[2] if len(sys.argv)>2 else None
    if arg.lower()=="all":
        months = sorted({Path(f).stem.replace("expiry_","") for f in glob.glob(str(BASE/"Output"/"expiry_20??-??.csv"))})
        cur = str(pd.Timestamp(rd or date.today()).to_period("M"))
        for m in sorted(set(months)|{cur}): main(m, rd)
    else:
        main(arg, rd)
