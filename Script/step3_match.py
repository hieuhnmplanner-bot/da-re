# -*- coding: utf-8 -*-
"""
DA-RE — Ghep GMV.csv (Thu Hien) x REM.csv (Metabase) -> GMV_x_REM.csv (CHUA tinh end_date).

Phuong an (da kiem thu tren du lieu that, accuracy ~99.8% tren bo truth):
- Khoa chinh = SO TIEN (REM Order Price VND x100), dung sai = max(10.000d, 8% gia tri).
- Vung noi tien (>10k): BAT BUOC trung 1 khoa phu manh -> Ten Sale (sales~Order Sale)
  hoac Ten goi (package~Package Name).
- Don le (1 UID co dung 1 don moi ben): ghep thang theo UID.
- Nhieu don: gom theo bucket tien, xep theo THOI GIAN de phan dinh don trung (99.6% on dinh).
- Giu CA HAI ben (full outer): GMV Only / REM Only deu giu lai.
- Thu tu don chuan lay theo REM (CRM day du hon), van giu them thu tu GMV de doi chieu.
- Do tin cay: High (tien<=2% + Sale + Goi) / Med (1 khoa phu) / Low (chi tien).
- REM Only tach: 'Lich su' (Purchase Time < ngay bat dau ghi GMV) vs 'Audit'.

CHI DOC 2 file dau vao, KHONG sua. Output: Output/GMV_x_REM.csv + Output/GMV_x_REM_summary.csv
"""
from pathlib import Path
from collections import defaultdict
import pandas as pd
import numpy as np

BASE_DIR = Path(__file__).resolve().parent.parent
IN_DIR = BASE_DIR / "Data_input"
OUT_DIR = BASE_DIR / "Output"
OUT_DIR.mkdir(parents=True, exist_ok=True)
GMV_PATH = IN_DIR / "GMV.csv"
REM_PATH = IN_DIR / "REM.csv"
OUT_PATH = OUT_DIR / "GMV_x_REM.csv"
SUM_PATH = OUT_DIR / "GMV_x_REM_summary.csv"

TOL_ABS = 10000
TOL_REL = 0.08


def clean_uid(v):
    if pd.isna(v):
        return ""
    return "".join(ch for ch in str(v).split(".")[0] if ch.isdigit())


def toks(s):
    return frozenset(t for t in "".join(c if c.isalnum() else " " for c in str(s).upper()).split() if t)


def nname(s):
    if pd.isna(s):
        return ""
    return " ".join(str(s).upper().split())


def pkg_ok(a, b):
    return bool(a and b and (len(a & b) >= 2 or a <= b or b <= a))


def sale_ok(a, b):
    return bool(a and b and a == b)


def money_allow(gm, rm):
    """Cho phep ghep theo tien? Tra (allowed, how)."""
    d = abs(gm - rm)
    if d < TOL_ABS:
        return True, "tight"
    if d < max(TOL_ABS, TOL_REL * max(gm, rm)):
        return True, "fuzzy"
    return False, None


def main():
    print("Doc du lieu...")
    gmv = pd.read_csv(GMV_PATH, low_memory=False)
    rem = pd.read_csv(REM_PATH, dtype=str, encoding="utf-8-sig")

    # --- chuan hoa phu tro (khong ghi de cot goc) ---
    gmv["_uid"] = gmv["uid"].map(clean_uid)
    gmv["_money"] = pd.to_numeric(
        gmv["real_pay_vnd"].astype(str).str.replace(",", "", regex=False).str.replace(" ", ""),
        errors="coerce").fillna(0).astype("int64")
    gmv["_t"] = pd.to_datetime(gmv["pay_time"], errors="coerce")
    gmv["_pk"] = gmv["package"].map(toks)
    gmv["_sl"] = gmv["sales"].map(nname)

    rem["_uid"] = rem["UID"].map(clean_uid)
    rem["_money"] = (pd.to_numeric(
        rem["Order Price VND"].astype(str).str.replace(",", "", regex=False).str.replace(".", "", regex=False),
        errors="coerce").fillna(0).astype("int64")) * 100
    rem["_t"] = pd.to_datetime(rem["Purchase Time"], errors="coerce")
    rem["_pk"] = rem["Package Name"].map(toks)
    rem["_sl"] = rem["Order Sale"].map(nname)

    # thu tu don theo REM (CRM) va theo GMV
    rem = rem.sort_values(["_uid", "_t"]).reset_index(drop=True)
    rem["_order_no_rem"] = rem.groupby("_uid").cumcount() + 1
    gmv = gmv.sort_values(["_uid", "_t"]).reset_index(drop=True)
    gmv["_order_no_gmv"] = gmv.groupby("_uid").cumcount() + 1

    GMV_START = gmv["_t"].min()

    grec = gmv.to_dict("records")
    rrec = rem.to_dict("records")
    gidx_by_uid = defaultdict(list)
    ridx_by_uid = defaultdict(list)
    for i, r in enumerate(grec):
        gidx_by_uid[r["_uid"]].append(i)
    for j, r in enumerate(rrec):
        ridx_by_uid[r["_uid"]].append(j)

    g_matched = {}   # gidx -> (ridx, conf, how)
    r_used = set()

    def conf_of(g, r):
        d = abs(g["_money"] - r["_money"])
        rel = d / max(max(g["_money"], r["_money"]), 1)
        p = pkg_ok(g["_pk"], r["_pk"])
        s = sale_ok(g["_sl"], r["_sl"])
        if rel <= 0.02 and p and s:
            return "High"
        if p or s:
            return "Med"
        return "Low"

    print("Ghep theo tung UID...")
    for uid, gids in gidx_by_uid.items():
        if not uid:
            continue
        rids = ridx_by_uid.get(uid, [])
        if not rids:
            continue
        # don le 1-1: ghep thang theo UID
        if len(gids) == 1 and len(rids) == 1:
            gi, rj = gids[0], rids[0]
            g_matched[gi] = (rj, conf_of(grec[gi], rrec[rj]), "single")
            r_used.add(rj)
            continue
        # nhieu don: bucket tien + xep thoi gian
        used_local = set()
        rby = defaultdict(list)
        for rj in rids:
            rby[round(rrec[rj]["_money"] / TOL_ABS)].append(rj)
        for gi in sorted(gids, key=lambda i: (grec[i]["_t"] if pd.notna(grec[i]["_t"]) else pd.Timestamp.max)):
            g = grec[gi]
            kk = round(g["_money"] / TOL_ABS)
            cand = []
            for dk in (-1, 0, 1):
                for rj in rby.get(kk + dk, []):
                    if rj in used_local:
                        continue
                    r = rrec[rj]
                    ok, how = money_allow(g["_money"], r["_money"])
                    if not ok:
                        continue
                    # vung noi (fuzzy): bat buoc 1 khoa phu manh
                    if how == "fuzzy" and not (pkg_ok(g["_pk"], r["_pk"]) or sale_ok(g["_sl"], r["_sl"])):
                        continue
                    cand.append((rj, how))
            cand.sort(key=lambda x: (rrec[x[0]]["_t"] if pd.notna(rrec[x[0]]["_t"]) else pd.Timestamp.max))
            if cand:
                rj, how = cand[0]
                used_local.add(rj)
                r_used.add(rj)
                g_matched[gi] = (rj, conf_of(g, rrec[rj]), how)

    # --- dung output full outer ---
    drop_helpers = ["_uid", "_money", "_t", "_pk", "_sl"]
    print("Tao file ket qua...")
    rows = []
    for gi, (rj, conf, how) in g_matched.items():
        row = {k: v for k, v in grec[gi].items() if k not in ["_uid", "_money", "_t", "_pk", "_sl"]}
        rrow = {k: v for k, v in rrec[rj].items() if k not in ["_uid", "_money", "_t", "_pk", "_sl"]}
        row.update(rrow)
        row["match_method"] = "Match-Single" if how == "single" else "Match-MultiOrder"
        row["confidence"] = conf
        row["money_gmv_vnd"] = grec[gi]["_money"]
        row["money_rem_vnd"] = rrec[rj]["_money"]
        mx = max(grec[gi]["_money"], rrec[rj]["_money"], 1)
        row["money_diff_pct"] = round(abs(grec[gi]["_money"] - rrec[rj]["_money"]) / mx * 100, 2)
        row["order_no"] = grec[gi]["_order_no_gmv"]  # placeholder, overwrite below with REM
        row["order_no"] = rrec[rj]["_order_no_rem"]
        row["order_no_gmv"] = grec[gi]["_order_no_gmv"]
        rows.append(row)

    matched_g = set(g_matched.keys())
    for gi, g in enumerate(grec):
        if gi in matched_g:
            continue
        row = {k: v for k, v in g.items() if k not in ["_uid", "_money", "_t", "_pk", "_sl"]}
        in_rem = bool(g["_uid"]) and g["_uid"] in ridx_by_uid
        row["match_method"] = "GMV Only - UID co o REM" if in_rem else "GMV Only - UID khong co o REM"
        row["confidence"] = ""
        row["money_gmv_vnd"] = g["_money"]
        row["order_no_gmv"] = g["_order_no_gmv"]
        rows.append(row)

    for rj, r in enumerate(rrec):
        if rj in r_used:
            continue
        row = {k: v for k, v in r.items() if k not in ["_uid", "_money", "_t", "_pk", "_sl"]}
        in_gmv = bool(r["_uid"]) and r["_uid"] in gidx_by_uid
        if pd.notna(r["_t"]) and r["_t"] < GMV_START:
            row["match_method"] = "REM Only - Lich su (truoc ky ghi GMV)"
        elif not in_gmv:
            row["match_method"] = "REM Only - UID khong co o GMV"
        else:
            row["match_method"] = "REM Only - Audit (UID chung, khong khop)"
        row["confidence"] = ""
        row["money_rem_vnd"] = r["_money"]
        row["order_no"] = r["_order_no_rem"]
        rows.append(row)

    out = pd.DataFrame(rows)
    out.to_csv(OUT_PATH, index=False, encoding="utf-8-sig")
    print(f"OK Da luu {len(out)} dong -> {OUT_PATH}")

    # --- bang tom tat ---
    summ = out["match_method"].value_counts()
    conf = out.loc[out["match_method"].str.startswith("Match"), "confidence"].value_counts()
    lines = []
    TOTg, TOTr = len(gmv), len(rem)
    lines.append(("TONG GMV", TOTg, "", ""))
    lines.append(("TONG REM", TOTr, "", ""))
    for k, v in summ.items():
        base = "%GMV" if k.startswith("Match") or k.startswith("GMV") else "%REM"
        pct = round(v / (TOTg if base == "%GMV" else TOTr) * 100, 1)
        lines.append((k, v, base, pct))
    for k, v in conf.items():
        lines.append((f"  Confidence {k}", v, "%GMV", round(v / TOTg * 100, 1)))
    sdf = pd.DataFrame(lines, columns=["Nhom", "So_dong", "Mau_so", "Ty_le_%"])
    sdf.to_csv(SUM_PATH, index=False, encoding="utf-8-sig")
    print("\n=== BANG TOM TAT ===")
    print(sdf.to_string(index=False))


if __name__ == "__main__":
    main()
