# -*- coding: utf-8 -*-
"""
DA-RE — Ghi log thay doi hang ngay theo UID (muc 2).
Moi UID, moi ngay luu: order_id MOI NHAT trong REM, remaining hien tai, last study,
is_frozen, tong so don. Ly do: REM cac truong nay la cap UID (khong phai order),
neu khong snapshot lai thi se bi ghi de khi khach kich hoat don moi.

Chay moi ngay (sau khi tai REM.csv). An toan: neu ngay do da co log thi BO QUA (khong ghi trung).
Output: State/daily_uid_log.csv  (append)
"""
from pathlib import Path
from datetime import date
import pandas as pd

BASE = Path(__file__).resolve().parent.parent
REM_PATH = BASE / "Data_input" / "REM.csv"
STATE = BASE / "State"; STATE.mkdir(parents=True, exist_ok=True)
LOG = STATE / "daily_uid_log.csv"


def clean_uid(v):
    if pd.isna(v): return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())


def main(snapshot_date=None):
    snap = str(snapshot_date or date.today())
    r = pd.read_csv(REM_PATH, dtype=str, encoding="utf-8-sig")
    r["_uid"] = r["UID"].map(clean_uid)
    r["_pt"] = pd.to_datetime(r["Purchase Time"], errors="coerce")
    r = r.sort_values(["_uid", "_pt"])
    latest = r.groupby("_uid").tail(1)
    cnt = r.groupby("_uid").size().rename("total_orders")
    out = pd.DataFrame({
        "snapshot_date": snap,
        "uid": latest["_uid"].values,
        "latest_order_id": latest["Order ID"].astype(str).values,
        "remaining": pd.to_numeric(latest["Remain lesson Number"], errors="coerce").values,
        "last_study": latest["Last class time"].values,
        "is_frozen": pd.to_numeric(latest["Is Frozen"], errors="coerce").fillna(0).astype(int).values,
    })
    out = out[out["uid"] != ""].merge(cnt, left_on="uid", right_index=True, how="left")

    if LOG.exists():
        old = pd.read_csv(LOG, dtype=str)
        if snap in set(old["snapshot_date"]):
            print(f"Ngay {snap} da co trong log -> BO QUA (tranh ghi trung).")
            return
        out.to_csv(LOG, mode="a", header=False, index=False, encoding="utf-8-sig")
    else:
        out.to_csv(LOG, index=False, encoding="utf-8-sig")
    print(f"OK Da ghi {len(out)} UID cho ngay {snap} -> {LOG}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else None)
