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

THRESH = 21        # remaining <= 20 (team sale 08/2026: <15 chua sat van hanh -> doi sang <=20). decide dung: rem >= THRESH -> loai.
IDLE_NORMAL = 90   # cho remaining 1..20
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
        lg = lg.dropna(subset=["snapshot_date"])
        # CHON MOC "dau thang": UU TIEN snapshot DAU TIEN >= dau thang (du lieu da settle sau dot kich hoat cuoi thang truoc).
        # Neu chua co snapshot nao trong thang moi -> lay snapshot gan nhat TRUOC dau thang.
        # (Snapshot cuoi thang truoc, vd 31/7, hay dinh data-lag: don vua kich hoat chua kip cong buoi vao tong UID.)
        after = lg[lg["snapshot_date"] >= run_date]
        before = lg[lg["snapshot_date"] <= run_date]
        asof = after["snapshot_date"].min() if len(after) else (before["snapshot_date"].max() if len(before) else None)
        if asof is not None:
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
                real_latest = s["latest_order_id"].astype(str)
                re_early = (oid != real_latest) & (~empty)   # don dang tieu hao KHAC don moi nhat => khach da gia han som
                oid = oid.where(~empty, real_latest)          # fallback khi rong (~0.9%)
                remc = remc.where(~empty, pd.to_numeric(s["remaining"], errors="coerce"))
                print(f"  Da co lich su thang truoc -> dung FIFO per-order ({int((~empty).sum())}/{len(s)}).")
            else:
                oid = s["latest_order_id"].astype(str)
                remc = pd.to_numeric(s["remaining"], errors="coerce")
                re_early = pd.Series(False, index=s.index)     # thang dau: khong co khai niem gia han som per-order
                print("  Thang dau / chua co lich su tieu thu thang truoc -> dung TONG REM UID + latest_order_id.")
            return pd.DataFrame({
                "uid": s["uid"].map(clean_uid),
                "latest_order_id": oid.values,
                "remaining": remc.values,
                "last_study": pd.to_datetime(s["last_study"], errors="coerce").values,
                "is_frozen": pd.to_numeric(s["is_frozen"], errors="coerce").fillna(0).astype(int).values,
                "renewed_early": re_early.values,
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
        "renewed_early": False,
    })


def main(month, operational=False):
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

    if operational:
        # GOC NHIN VAN HANH (cho sale): danh sach ≤20 tai dau thang, PER-UID,
        # KHONG dedup registry, KHONG witnessed-crossing, KHONG cap nhat registry.
        # -> Giu ca carry-over thang truoc (khach cu chua xu ly van hien lai).
        elig["month"] = month
        out = elig[["latest_order_id", "uid", "remaining", "last_study", "idle", "is_frozen", "tag", "reason", "month"]]
        out = out.rename(columns={"latest_order_id": "order_id"})
        out_path = OUT / f"operational_{month}.csv"
        out.to_csv(out_path, index=False, encoding="utf-8-sig")
        print(f"OK Danh sach VAN HANH {month}: {len(out)} UID (KHONG dedup) -> {out_path}")
        return

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

    # WITNESSED-CROSSING: don da gia han som (renewed_early) chi GIU neu log THANG TRUOC tung thay don do >= THRESH buoi
    # (tuc da chung kien no rot tu >=15 -> <15 TRONG KY). Don von da <15 tu truoc khi theo doi = backlog -> LOAI.
    removed_backlog = 0
    if "renewed_early" in elig.columns and bool(elig["renewed_early"].any()) and LOG.exists():
        lg2 = pd.read_csv(LOG, dtype=str)
        lg2["snapshot_date"] = pd.to_datetime(lg2["snapshot_date"], errors="coerce")
        prior_start = (run_date - pd.offsets.MonthBegin(1)).normalize()
        lg2 = lg2[(lg2["snapshot_date"] >= prior_start) & (lg2["snapshot_date"] < run_date)]
        witnessed = set()
        if len(lg2) and "so_buoi_con_cua_order" in lg2.columns:
            lg2["sb"] = pd.to_numeric(lg2["so_buoi_con_cua_order"], errors="coerce")
            ge = lg2[lg2["sb"] >= THRESH]
            witnessed = set(zip(ge["uid"].map(clean_uid), ge["order_id_tieu_hao"].astype(str)))
        keep = elig.apply(lambda r: (not r["renewed_early"]) or ((r["uid"], str(r["latest_order_id"])) in witnessed), axis=1)
        removed_backlog = int((~keep).sum())
        elig = elig[keep].copy()

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
    print(f"   Da loai backlog gia han som (chua chung kien rot <15 trong ky): {removed_backlog}")
    print(f"   Registry tong cong: {len(reg)+len(newreg)} order_id")


if __name__ == "__main__":
    m = sys.argv[1] if len(sys.argv) > 1 else "2026-07"
    op = (len(sys.argv) > 2 and sys.argv[2].lower() in ("operational", "op"))
    main(m, operational=op)
