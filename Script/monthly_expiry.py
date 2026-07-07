# -*- coding: utf-8 -*-
"""
DA-RE — Sinh DANH SACH HET HAN theo thang (muc 1,3,4).

Quy tac (da chot voi nguoi dung):
- Xet order_id MOI NHAT cua moi UID (theo Purchase Time) tai dau thang.
- remaining < 10 moi la ung vien.
    + remaining == 0  : chi vao list neu idle (so ngay tu last study toi ngay chay) <= 10.
    + 1 <= remaining<=9: vao list neu idle <= 90.
- idle > nguong  -> LOAI (khong vao list thang nay).
- Frozen (is_frozen=1): ap dung CUNG quy tac 90/10 ngay, nhung gan them tag "Frozen".
  Nhom Frozen sau nay kich hoat hoc lai van giu order_id nay thuoc thang da liet ke.
- DEDUP: 1 order_id da tung vao list bat ky thang nao -> KHONG vao lai (State/expiry_registry.csv).

Nguon trang thai 'dau thang':
- Neu co State/daily_uid_log.csv: lay snapshot co ngay <= run_date va gan nhat (dung trang thai dau thang).
- Neu chua co log (lan dau): dung truc tiep REM.csv hien tai lam xap xi.

Output: Output/expiry_<YYYY-MM>.csv  + cap nhat State/expiry_registry.csv
"""
from pathlib import Path
import sys
import glob
import pandas as pd
import numpy as np

BASE = Path(__file__).resolve().parent.parent
REM_PATH = BASE / "Data_input" / "REM.csv"
STATE = BASE / "State"; STATE.mkdir(parents=True, exist_ok=True)
OUT = BASE / "Output"; OUT.mkdir(parents=True, exist_ok=True)
LOG = STATE / "daily_uid_log.csv"
REG = STATE / "expiry_registry.csv"

THRESH = 15        # remaining < 15 (chot voi sep 07/2026: <10 kho convert; gia hang 6th-1yr -> <15 hop ly)
IDLE_NORMAL = 90   # cho remaining 1..14
IDLE_ZERO = 10     # cho remaining == 0 (chi dung neu ADMIT_ZERO=True)
# LOAI HAN nhom remaining==0 khoi "Den han": nhom nay la bien khong doan truoc dau thang,
# rat it (chi ~7 case cham bien), va chay run_monthly buoi sang truoc gio hoc toi nen ho van con >=1 buoi.
ADMIT_ZERO = False


def clean_uid(v):
    if pd.isna(v): return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())


def load_state(run_date):
    """Tra DataFrame: uid, latest_order_id, remaining, last_study, is_frozen."""
    if LOG.exists():
        lg = pd.read_csv(LOG, dtype=str)
        lg["snapshot_date"] = pd.to_datetime(lg["snapshot_date"], errors="coerce")
        lg = lg[lg["snapshot_date"] <= run_date]
        if len(lg):
            asof = lg["snapshot_date"].max()
            print(f"Dung snapshot log ngay {asof.date()} lam trang thai dau thang.")
            s = lg[lg["snapshot_date"] == asof].copy()
            # QUY TAC:
            #  - THANG DAU (chua co lich su tieu thu buoi cua THANG TRUOC): chi dung TONG REM UID < 15 + latest_order_id.
            #  - TU THANG SAU (log da phu ky thang lien truoc): moi dung per-order FIFO (don dang tieu hao + so buoi rieng).
            prior_start = (run_date - pd.offsets.MonthBegin(1)).normalize()   # dau thang lien truoc
            have_history = (lg["snapshot_date"] <= prior_start).any()
            use_fifo = have_history and ("order_id_tieu_hao" in s.columns)
            if use_fifo:
                oid = s["order_id_tieu_hao"].astype(str).str.strip()
                remc = pd.to_numeric(s["so_buoi_con_cua_order"], errors="coerce")
                empty = (oid == "") | (oid.str.lower() == "nan")
                oid = oid.where(~empty, s["latest_order_id"].astype(str))          # fallback khi rong (~0.9%)
                remc = remc.where(~empty, pd.to_numeric(s["remaining"], errors="coerce"))
                print(f"  Da co lich su thang truoc -> dung FIFO per-order ({int((~empty).sum())}/{len(s)}).")
            else:
                oid = s["latest_order_id"].astype(str)
                remc = pd.to_numeric(s["remaining"], errors="coerce")
                print("  Thang dau / chua co lich su tieu thu thang truoc -> dung TONG REM UID + latest_order_id.")
            return pd.DataFrame({
                "uid": s["uid"].map(clean_uid),
                "latest_order_id": oid.values,
                "remaining": remc.values,
                "last_study": pd.to_datetime(s["last_study"], errors="coerce").values,
                "is_frozen": pd.to_numeric(s["is_frozen"], errors="coerce").fillna(0).astype(int).values,
            })
    # fallback: REM hien tai
    print("Chua co log phu hop -> dung REM.csv hien tai (xap xi dau thang).")
    r = pd.read_csv(REM_PATH, dtype=str, encoding="utf-8-sig")
    r["uid"] = r["UID"].map(clean_uid)
    r["_pt"] = pd.to_datetime(r["Purchase Time"], errors="coerce")
    r = r.sort_values(["uid", "_pt"])
    s = r.groupby("uid").tail(1)
    return pd.DataFrame({
        "uid": s["uid"].values,
        "latest_order_id": s["Order ID"].astype(str).values,
        "remaining": pd.to_numeric(s["Remain lesson Number"], errors="coerce").values,
        "last_study": pd.to_datetime(s["Last class time"], errors="coerce").values,
        "is_frozen": pd.to_numeric(s["Is Frozen"], errors="coerce").fillna(0).astype(int).values,
    })


def main(month):
    run_date = pd.Timestamp(month + "-01")
    st = load_state(run_date)
    st = st[st["uid"] != ""].copy()
    st["idle"] = (run_date - st["last_study"]).dt.days

    def decide(row):
        rem, idle, fr = row["remaining"], row["idle"], row["is_frozen"] == 1
        if pd.isna(rem) or rem >= THRESH:
            return ("", "remaining>=%d" % THRESH)
        if pd.isna(idle):
            return ("", "chua tung hoc")
        if rem == 0:
            if not ADMIT_ZERO:
                return ("", "remaining=0 -> loai (khong vao Den han)")
            if idle <= IDLE_ZERO:
                return ("Frozen" if fr else "Normal", "remaining=0, idle<=%d" % IDLE_ZERO)
            return ("", "remaining=0, idle>%d" % IDLE_ZERO)
        if idle <= IDLE_NORMAL:
            return ("Frozen" if fr else "Normal", "1-%d, idle<=%d" % (THRESH-1, IDLE_NORMAL))
        return ("", "1-%d, idle>%d" % (THRESH-1, IDLE_NORMAL))

    res = st.apply(decide, axis=1, result_type="expand")
    st["tag"], st["reason"] = res[0], res[1]
    elig = st[st["tag"] != ""].copy()

    # dedup voi registry
    if REG.exists():
        reg = pd.read_csv(REG, dtype=str)
        # cho phep DUNG LAI 1 thang sach: bo cac entry cu CUA CHINH thang nay ra khoi registry
        reg = reg[reg["month"].astype(str) != str(month)].copy()
        seen = set(reg["order_id"].astype(str))
    else:
        reg = pd.DataFrame(columns=["order_id", "uid", "month", "tag"])
        seen = set()
    # MO HINH MOI: KHONG loai order trong early_renewal/mid_expiry nua.
    # Ly do: khach gia han som van de order N-1 tu chay xuong <15 roi vao "Den han" thang tuong lai (co che "doi" - Giai doan 2).
    # Registry chi dam bao 1 order_id vao dung 1 thang (khong lap), khong loai theo nhom khac.
    before = len(elig)
    elig = elig[~elig["latest_order_id"].astype(str).isin(seen)].copy()
    removed = before - len(elig)

    elig["month"] = month
    out = elig[["latest_order_id", "uid", "remaining", "last_study", "idle", "is_frozen", "tag", "reason", "month"]]
    out = out.rename(columns={"latest_order_id": "order_id"})
    out_path = OUT / f"expiry_{month}.csv"
    out.to_csv(out_path, index=False, encoding="utf-8-sig")

    # cap nhat registry
    newreg = out[["order_id", "uid", "month", "tag"]]
    pd.concat([reg, newreg], ignore_index=True).to_csv(REG, index=False, encoding="utf-8-sig")

    print(f"OK Danh sach het han {month}: {len(out)} order_id "
          f"(Frozen: {(out['tag']=='Frozen').sum()}) -> {out_path}")
    print(f"   Da loai do trung registry (da o thang truoc): {removed}")
    print(f"   Registry tong cong: {len(reg)+len(newreg)} order_id")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "2026-07")
