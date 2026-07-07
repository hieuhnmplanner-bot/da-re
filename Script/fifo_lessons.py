# -*- coding: utf-8 -*-
"""
DA-RE — FIFO: tai dung so buoi con cua TUNG order.
Nguon: REM co 'Total Lesson' (so buoi GOC moi order, cap ORDER) + 'Remain lesson Number' (cap UID).
Quy tac: don CU (Purchase Time som nhat) bi tru HET truoc, roi moi den don moi.
  consumed (tong buoi da hoc cua UID) = sum(Total Lesson cac don) - so buoi con cap UID
  -> phan bo consumed cho cac don theo thu tu cu->moi.
'order_id_tieu_hao' = don cu nhat con > 0 buoi (= don dang hoc / sap het han).
'so_buoi_con_cua_order' = so buoi con cua chinh don do.

Dung chung cho daily_snapshot.py (chay live) va backfill_fifo.py (bo sung cot cho log cu).
"""
import pandas as pd
import numpy as np


def clean_uid(v):
    if pd.isna(v):
        return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())


def build_orders(rem):
    """rem: DataFrame REM. Tra dict: uid -> list[(oid, total_lesson, purchase_time)] da sap xep CU->MOI."""
    r = rem.copy()
    r["_uid"] = r["UID"].map(clean_uid)
    r["_oid"] = r["Order ID"].astype(str).str.split(".").str[0]
    r["_tot"] = pd.to_numeric(r["Total Lesson"], errors="coerce").fillna(0.0)
    r["_pt"] = pd.to_datetime(r["Purchase Time"], errors="coerce")
    r = r.drop_duplicates(["_uid", "_oid"]).copy()
    r["_ptf"] = r["_pt"].fillna(pd.Timestamp.max)
    r = r.sort_values(["_uid", "_ptf"])
    return {u: list(zip(g["_oid"], g["_tot"], g["_pt"])) for u, g in r.groupby("_uid")}


def active_order(orders_uid, remU, asof=None):
    """Tra (order_id_tieu_hao, so_buoi_con_cua_order).
    orders_uid: list[(oid, total, purchase_time)] cu->moi (tu build_orders).
    remU: so buoi con cap UID tai thoi diem xet.
    asof: neu dua vao, CHI tinh don co Purchase Time <= asof (dung khi backfill ngay qua khu)."""
    if not orders_uid:
        return ("", np.nan)
    ods = [(o, t) for (o, t, p) in orders_uid if (asof is None or pd.isna(p) or p <= asof)]
    if not ods or pd.isna(remU):
        return ("", np.nan)
    sumT = sum(t for _, t in ods)
    c = max(0.0, sumT - float(remU))          # tong buoi da hoc; neu remU > sumT (buoi thuong) -> 0
    per = []
    for o, t in ods:
        used = min(c, t)
        per.append((o, t - used))
        c -= used
    for o, left in per:
        if left > 0.5:                        # don cu nhat con buoi = dang tieu hao
            return (o, int(round(left)))
    return (per[-1][0], 0)                     # tat ca da het -> don moi nhat, 0 buoi
