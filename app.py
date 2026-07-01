# -*- coding: utf-8 -*-
"""DA-RE — Dashboard Gia hạn. KHÔNG dùng end_date. Chạy thật từ 2026-07.
Tab1: Dữ liệu gia hạn (Đến hạn + Gia hạn sớm). Tab2: Chi tiết (có order_no_uid).
Đọc Output/: expiry_<m>_status_<d>.csv, early_renewal_<m>_<d>.csv.
"""
from pathlib import Path
import glob, re, os
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="DA-RE — Dashboard Gia hạn", layout="wide")
HERE = Path(__file__).resolve().parent
OUT = HERE / "Output"

def _truthy(s): return s.astype(str).str.strip().str.lower().isin(["true","1","yes"])
def _vnd(x):
    try: return f"{x:,.0f}đ"
    except Exception: return x

def _latest_per_month(pattern, required=None):
    files = glob.glob(str(OUT / pattern)); best = {}
    for f in files:
        m = re.search(r"_(\d{4}-\d{2})_.*?(\d{4}-\d{2}-\d{2})", Path(f).name) or re.search(r"(\d{4}-\d{2})_status_(\d{4}-\d{2}-\d{2})", Path(f).name)
        mm = re.search(r"(\d{4}-\d{2})", Path(f).name)
        if not mm: continue
        try:
            if required and required not in pd.read_csv(f, nrows=0).columns: continue
        except Exception: continue
        mt = os.path.getmtime(f); mth = mm.group(1)
        if mth not in best or mt > best[mth][0]: best[mth] = (mt, f)
    frames = []
    for mth,(_,f) in best.items():
        try: d = pd.read_csv(f, dtype=str)
        except Exception: continue
        if len(d): d["month"] = mth; frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

@st.cache_data
def load_expiry():
    d = _latest_per_month("expiry_*_status_*.csv", required="gia_tri_don_cu")
    if d.empty: return d
    for c in ["da_gia_han_M90","da_gia_han_vo_han"]: d[c] = _truthy(d[c])
    for c in ["gia_tri_don_cu","gia_tri_don_gia_han","remaining","order_no_uid"]:
        if c in d.columns: d[c] = pd.to_numeric(d[c], errors="coerce")
    if "nhom" not in d.columns: d["nhom"] = "Đến hạn"
    return d

@st.cache_data
def load_early():
    d = _latest_per_month("early_renewal_*.csv")
    if d.empty: return d
    for c in ["gia_tri_don_cu","gia_tri_don_gia_han","order_no_uid"]:
        if c in d.columns: d[c] = pd.to_numeric(d[c], errors="coerce")
    if "nhom" not in d.columns: d["nhom"] = "Gia hạn sớm"
    return d

def kpis_due(df, ren_col):
    n = len(df); ren = df[ren_col].fillna(False); renewed = int(ren.sum())
    exp_tot = df["gia_tri_don_cu"].sum(); new_ren = df.loc[ren,"gia_tri_don_gia_han"].sum(); old_ren = df.loc[ren,"gia_tri_don_cu"].sum()
    return dict(due=n, renewed=renewed, crr=(renewed/n*100 if n else 0),
                rrr=(new_ren/exp_tot*100 if exp_tot else 0), upsell=(new_ren/old_ren*100 if old_ren else 0), revenue=new_ren)

exp = load_expiry(); early = load_early()
st.title("📊 DA-RE — Dữ liệu Gia hạn")
if exp.empty and early.empty:
    st.warning("Chưa có dữ liệu trong Output/. Chạy expiry_renewal_check.py / early_renewal.py trước."); st.stop()

# ---- Sidebar ----
st.sidebar.header("Bộ lọc")
months = sorted(set(exp["month"].unique() if not exp.empty else []) | set(early["month"].unique() if not early.empty else []))
sel_months = st.sidebar.multiselect("Tháng", months, default=months)
ren_def = st.sidebar.radio("Định nghĩa gia hạn (nhóm Đến hạn)", ["M+90 (KPI cố định)","Vô hạn (Real rate)"], index=0)
REN = "da_gia_han_M90" if ren_def.startswith("M+90") else "da_gia_han_vo_han"
allteams = sorted(set(exp.get("team_sale_quan_ly", pd.Series(dtype=str)).dropna()) | set(early.get("team_sale_quan_ly", pd.Series(dtype=str)).dropna()))
sel_teams = st.sidebar.multiselect("Team (sale quản lý)", allteams, default=allteams)

def filt(d):
    if d.empty: return d
    x = d[d["month"].isin(sel_months)]
    if "team_sale_quan_ly" in x.columns and sel_teams: x = x[x["team_sale_quan_ly"].isin(sel_teams)]
    return x
fe = filt(exp); fr = filt(early)

tab1, tab2 = st.tabs(["📊 Dữ liệu gia hạn", "🧾 Chi tiết"])

with tab1:
    K = kpis_due(fe, REN) if not fe.empty else dict(due=0,renewed=0,crr=0,rrr=0,upsell=0,revenue=0)
    st.subheader("① Khách đến hạn (cohort cố định)")
    c = st.columns(5)
    c[0].metric("Đến hạn", f"{K['due']:,}", help="Số đơn tới hạn cần chăm sóc gia hạn")
    c[1].metric("CRR – Gia hạn KH", f"{K['crr']:.1f}%", help="Số đã gia hạn / Số đến hạn")
    c[2].metric("RRR – Gia hạn DT", f"{K['rrr']:.1f}%", help="Doanh thu gia hạn / Tổng giá trị đơn đến hạn")
    c[3].metric("Upsell", f"{K['upsell']:.1f}%", help=">100% = khách chi nhiều hơn lần trước")
    c[4].metric("Renewal Revenue", _vnd(K["revenue"]))

    st.subheader("② Gia hạn sớm (luồng trong tháng)")
    ne = len(fr); pend = int((fr.get("trang_thai_kich_hoat","")=="Chưa kích hoạt").sum()) if ne else 0
    erev = fr["gia_tri_don_gia_han"].sum() if ne else 0
    c = st.columns(4)
    c[0].metric("Gia hạn sớm", f"{ne:,}", help="Số khách gia hạn TRƯỚC khi hết hạn (theo pay_time)")
    c[1].metric("Doanh thu gia hạn sớm", _vnd(erev))
    c[2].metric("Chưa kích hoạt", f"{pend:,}", help="Đã trả tiền nhưng chưa bắt đầu học đơn mới — CS cần nhắc kích hoạt")
    c[3].metric("% chưa kích hoạt", f"{(pend/ne*100 if ne else 0):.1f}%")

    st.subheader("③ Tổng hợp gia hạn trong kỳ")
    tot_cust = K["renewed"] + ne; tot_rev = K["revenue"] + erev
    c = st.columns(2)
    c[0].metric("Tổng lượt gia hạn", f"{tot_cust:,}", help="Đã gia hạn (đến hạn) + gia hạn sớm")
    c[1].metric("Tổng doanh thu gia hạn", _vnd(tot_rev))
    st.caption(f"Định nghĩa nhóm đến hạn: **{ren_def}** · {len(sel_months)} tháng · {len(sel_teams)} team.")

    # Bieu do theo thang
    if not exp.empty:
        rows = []
        for mth in months:
            g = exp[exp["month"]==mth]
            kk = kpis_due(g, REN) if not g.empty else dict(due=0,renewed=0,crr=0)
            e = len(early[early["month"]==mth]) if not early.empty else 0
            rows.append({"month":mth,"Đến hạn":kk["due"],"Đã gia hạn":kk["renewed"],"CRR %":round(kk["crr"],1),"Gia hạn sớm":e})
        tr = pd.DataFrame(rows)
        cc = st.columns(2)
        with cc[0]:
            st.plotly_chart(px.bar(tr.melt(id_vars="month",value_vars=["Đến hạn","Đã gia hạn"],var_name="",value_name="Số đơn"),
                x="month",y="Số đơn",color="",barmode="group",title="Đến hạn vs Đã gia hạn"), use_container_width=True)
        with cc[1]:
            st.plotly_chart(px.line(tr, x="month", y="CRR %", markers=True, title="CRR theo tháng"), use_container_width=True)

    st.subheader("Theo Team (nhóm đến hạn)")
    if not fe.empty:
        g = []
        for name, sub in fe.groupby("team_sale_quan_ly"):
            kk = kpis_due(sub, REN); g.append({"team":name,"Đến hạn":kk["due"],"Đã gia hạn":kk["renewed"],
                "CRR %":round(kk["crr"],1),"RRR %":round(kk["rrr"],1),"Upsell %":round(kk["upsell"],1),"Renewal Revenue":round(kk["revenue"])})
        st.dataframe(pd.DataFrame(g).sort_values("Đến hạn",ascending=False), use_container_width=True)

with tab2:
    view = st.radio("Xem nhóm", ["Cả hai","Đến hạn","Gia hạn sớm"], horizontal=True)
    frames = []
    if view in ("Cả hai","Đến hạn") and not fe.empty:
        a = fe.copy(); a["trang_thai"] = a[REN].map({True:"Đã gia hạn",False:"Chưa"})
        a["gia_han/kich_hoat"] = a.get("ngay_gia_han"); a["order_id_moi"] = ""
        frames.append(a)
    if view in ("Cả hai","Gia hạn sớm") and not fr.empty:
        b = fr.copy(); b["trang_thai"] = b.get("trang_thai_kich_hoat")
        b["gia_han/kich_hoat"] = b.get("ngay_kich_hoat"); b["ngay_mua"] = b.get("pay_time")
        frames.append(b)
    if not frames:
        st.info("Không có dòng nào cho lựa chọn hiện tại.")
    else:
        d = pd.concat(frames, ignore_index=True)
        cols = ["month","nhom","order_id","order_no_uid","uid","order_id_moi","trang_thai",
                "remaining","ngay_mua","gia_han/kich_hoat","gia_tri_don_cu","gia_tri_don_gia_han",
                "sale_ban_don","team_sale_ban","sale_quan_ly","team_sale_quan_ly","teacher","tag"]
        cols = [c for c in cols if c in d.columns]
        st.write(f"{len(d):,} dòng")
        st.dataframe(d[cols], use_container_width=True, height=480)
        st.download_button("⬇️ Tải CSV", d[cols].to_csv(index=False).encode("utf-8-sig"), "chi_tiet_gia_han.csv", "text/csv")

st.caption("DA-RE · không dùng end_date · order_no_uid = đơn thứ mấy của UID · gia hạn sớm ghi theo pay_time, mã tạm TMP_ cho đơn chưa kích hoạt.")
