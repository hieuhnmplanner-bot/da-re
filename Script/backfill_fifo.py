# -*- coding: utf-8 -*-
"""
DA-RE — CHAY 1 LAN: bo sung 2 cot FIFO vao daily_uid_log.csv da co san.
  order_id_tieu_hao       : don dang tieu hao (don cu nhat con buoi) = don sap het han
  so_buoi_con_cua_order   : so buoi con cua chinh don do

Tinh lai cho TUNG ngay snapshot (30/6, 1/7, ...):
  - chi dung cac don co Purchase Time <= ngay snapshot do (khong tinh don mua sau nay)
  - dung so buoi con cap UID cua dung dong ngay do
An toan: tao ban backup .bak truoc khi ghi de. Neu log da co cot FIFO -> bo qua.
"""
from pathlib import Path
import shutil
import pandas as pd
from fifo_lessons import build_orders, active_order, clean_uid

BASE = Path(__file__).resolve().parent.parent
REM_PATH = BASE / "Data_input" / "REM.csv"
LOG = BASE / "State" / "daily_uid_log.csv"


def read_rem():
    try:
        return pd.read_csv(REM_PATH, dtype=str, encoding="utf-8-sig")
    except UnicodeDecodeError:
        return pd.read_csv(REM_PATH, dtype=str, encoding="latin-1", engine="python")


def main():
    if not LOG.exists():
        print("Chua co daily_uid_log.csv."); return
    log = pd.read_csv(LOG, dtype=str)
    if "order_id_tieu_hao" in log.columns:
        print("Log DA co cot FIFO -> bo qua (khong lam lai)."); return

    orders = build_orders(read_rem())
    uidc = log["uid"].map(clean_uid).tolist()
    remv = pd.to_numeric(log["remaining"], errors="coerce").tolist()
    asofv = (pd.to_datetime(log["snapshot_date"], errors="coerce") + pd.Timedelta(hours=23, minutes=59)).tolist()

    oh, sb = [], []
    for u, rm, af in zip(uidc, remv, asofv):
        a = active_order(orders.get(u), rm, asof=af)
        oh.append(a[0]); sb.append(a[1])
    log["order_id_tieu_hao"] = oh
    log["so_buoi_con_cua_order"] = sb

    shutil.copy2(LOG, str(LOG) + ".bak")
    log.to_csv(LOG, index=False, encoding="utf-8-sig")

    per_day = log.groupby("snapshot_date").apply(
        lambda g: pd.Series({
            "UID": len(g),
            "co_order_tieu_hao": int((g["order_id_tieu_hao"].astype(str) != "").sum()),
        }), include_groups=False)
    print("OK Da bo sung 2 cot FIFO cho log. Theo ngay:")
    print(per_day.to_string())
    print(f"\nBackup ban cu: {LOG}.bak")


if __name__ == "__main__":
    main()
