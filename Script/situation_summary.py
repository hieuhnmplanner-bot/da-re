# -*- coding: utf-8 -*-
"""DA-RE — Tong hop QUY MO TINH HUONG cho 1 thang (chi so dem, KHONG PII -> an toan commit).
Phan loai don moi nhat moi UID theo luat danh sach het han, dem so luong + ty le.
Output: Output/situation_<month>.csv
Dung: python situation_summary.py 2026-07 [run_date]
"""
from pathlib import Path
import sys
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
THRESH, IDLE_NORMAL, IDLE_ZERO = 10, 90, 10

def cu(v):
    if pd.isna(v): return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())

def main(month, run_date=None):
    run_date = pd.Timestamp(run_date or (pd.Period(month,"M").start_time))
    r = pd.read_csv(BASE/"Data_input"/"REM.csv", dtype=str, encoding="utf-8-sig")
    r["uid"] = r["UID"].map(cu)
    r["rem"] = pd.to_numeric(r["Remain lesson Number"], errors="coerce")
    r["fr"] = pd.to_numeric(r["Is Frozen"], errors="coerce").fillna(0).astype(int)
    r["pt"] = pd.to_datetime(r["Purchase Time"], errors="coerce")
    r["last"] = pd.to_datetime(r["Last class time"], errors="coerce")
    r = r[r["uid"] != ""].sort_values(["uid","pt"])
    latest = r.groupby("uid").tail(1).copy()
    latest["idle"] = (run_date - latest["last"]).dt.days

    def cls(row):
        rem, idle, fr = row["rem"], row["idle"], row["fr"] == 1
        if pd.isna(rem) or rem >= THRESH: return "Chưa hết hạn (remaining ≥ 10)"
        if pd.isna(idle): return "Loại — chưa từng học"
        if rem == 0:
            if idle <= IDLE_ZERO: return "Vào list — remaining=0, idle≤10" + (" [Frozen]" if fr else "")
            return "Loại — remaining=0, idle>10"
        if idle <= IDLE_NORMAL: return "Vào list — 1–9 buổi, idle≤90" + (" [Frozen]" if fr else "")
        return "Loại — 1–9 buổi, idle>90"

    latest["nhom"] = latest.apply(cls, axis=1)
    N = len(latest)
    tab = latest["nhom"].value_counts().rename_axis("nhom").reset_index(name="so_luong")
    tab["ty_le_phan_tram"] = (tab["so_luong"] / N * 100).round(1)
    tab["vao_list"] = tab["nhom"].str.startswith("Vào list")
    tab["month"] = month
    out = BASE/"Output"/f"situation_{month}.csv"
    tab.to_csv(out, index=False, encoding="utf-8-sig")
    inlist = int(tab.loc[tab["vao_list"], "so_luong"].sum())
    print(f"Tong UID {N} | Vao list {inlist} ({round(inlist/N*100,1)}%) -> {out}")
    print(tab[["nhom","so_luong","ty_le_phan_tram"]].to_string(index=False))

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-07",
         sys.argv[2] if len(sys.argv) > 2 else None)
