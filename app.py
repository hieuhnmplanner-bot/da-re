# -*- coding: utf-8 -*-
"""DA-RE — Dashboard Hết hạn & Gia hạn (CRR / RRR / Upsell). KHÔNG dùng end_date.
Đọc Output/: expiry_<month>_status_<date>.csv, situation_<month>.csv.
"""
from pathlib import Path
import glob, re, os
import pandas as pd
import streamlit as st
import plotly.express as px

st.set_page_config(page_title="DA-RE — Dashboard Gia hạn", layout="wide")
HERE = Path(__file__).resolve().parent
OUT = HERE / "Output"
REQUIRED = "gia_tri_don_cu"  # cot bat buoc -> bo qua file status cu thieu gia tri

def _truthy(s):
    return s.astype(str).str.strip().str.lower().isin(["true", "1", "yes"])

def _vnd(x):
    try: return f"{x:,.0f}đ"
    except Exception: return x

@st.cache_data
def load_status():
    files = glob.glob(str(OUT / "expiry_*_status_*.csv"))
    best = {}  # month -> (mtime, file)
    for f in files:
        m = re.search(r"expiry_(\d{4}-\d{2})_status_\d{4}-\d{2}-\d{2}", Path(f).name)
        if not m:
            continue
        try:
            head = pd.read_csv(f, nrows=0)
        except Exception:
            continue
        if REQUIRED not in head.columns:
            continue
        mt = os.path.getmtime(f)
        mth = m.group(1)
        if mth not in best or mt > best[mth][0]:
            best[mth] = (mt, f)
    if not best:
        return pd.DataFrame()
    out = []
    for mth, (_, f) in best.items():
        d = pd.read_csv(f, dtype=str)
        d["month"] = mth
        out.append(d)
    res = pd.concat(out, ignore_index=True)
    for c in ["da_gia_han_M90", "da_gia_han_vo_han"]:
        res[c] = _truthy(res[c])
    for c in ["gia_tri_don_cu", "gia_tri_don_gia_han", "remaining", "idle_ngay", "so_ngay_den_gia_han"]:
        if c in res.columns:
            res[c] = pd.to_numeric(res[c], errors="coerce")
    return res

@st.cache_data
def load_situation():
    files = glob.glob(str(OUT / "situation_*.csv"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_csv(f) for f in files], ignore_index=True)

def kpis(df, ren_col):
    n = len(df)
    ren = df[ren_col].fillna(False)
    renewed = int(ren.sum())
    crr = renewed / n * 100 if n else 0
    exp_tot = df["gia_tri_don_cu"].sum()
    new_ren = df.loc[ren, "gia_tri_don_gia_han"].sum()
    old_ren = df.loc[ren, "gia_tri_don_cu"].sum()
    rrr = new_ren / exp_tot * 100 if exp_tot else 0
    ups = new_ren / old_ren * 100 if old_ren else 0
    return dict(due=n, renewed=renewed, crr=crr, rrr=rrr, upsell=ups, revenue=new_ren)

status = load_status()
situation = load_situation()
st.title("📊 DA-RE — Hết hạn & Tỷ lệ Gia hạn")
if status.empty:
    st.warning("Chưa có file expiry_*_status_*.csv (có cột giá trị) trong Output/. Chạy expiry_renewal_check.py trước.")
    st.stop()

# ---------- Sidebar ----------
st.sidebar.header("Bộ lọc")
months = sorted(status["month"].unique())
sel_months = st.sidebar.multiselect("Tháng (cohort)", months, default=months)
ren_def = st.sidebar.radio("Định nghĩa gia hạn", ["M+90 (KPI cố định)", "Vô hạn (Real rate)"], index=0)
REN = "da_gia_han_M90" if ren_def.startswith("M+90") else "da_gia_han_vo_han"
teams = sorted(status["team_sale_quan_ly"].dropna().unique())
sel_teams = st.sidebar.multiselect("Team (sale quản lý)", teams, default=teams)
tags = sorted(status["tag"].dropna().unique())
sel_tags = st.sidebar.multiselect("Tag", tags, default=tags)

f = status[status["month"].isin(sel_months) & status["team_sale_quan_ly"].isin(sel_teams) & status["tag"].isin(sel_tags)].copy()

tab1, tab2, tab3 = st.tabs(["📊 Tổng quan & theo nhóm", "🧾 Danh sách chi tiết", "📈 Quy mô tình huống"])

with tab1:
    K = kpis(f, REN)
    c = st.columns(5)
    c[0].metric("Đến hạn (order_id)", f"{K['due']:,}")
    c[1].metric("CRR – Gia hạn KH", f"{K['crr']:.1f}%", help="Số đơn gia hạn / Số đơn đến hạn")
    c[2].metric("RRR – Gia hạn DT", f"{K['rrr']:.1f}%", help="Doanh thu gia hạn / Tổng giá trị đơn hết hạn")
    c[3].metric("Upsell", f"{K['upsell']:.1f}%", help="Giá trị đơn gia hạn mới / Giá trị đơn cũ (nhóm đã gia hạn). >100% = chi nhiều hơn")
    c[4].metric("Renewal Revenue", _vnd(K["revenue"]))
    st.caption(f"Định nghĩa: **{ren_def}** · {len(sel_months)} tháng · {len(sel_teams)} team.")

    # Trend theo thang (neu nhieu thang)
    if len(months) > 1:
        rows = []
        for mth in months:
            g = status[status["month"] == mth]
            kk = kpis(g, REN)
            rows.append({"month": mth, "CRR %": round(kk["crr"], 1), "RRR %": round(kk["rrr"], 1), "Upsell %": round(kk["upsell"], 1)})
        trend = pd.DataFrame(rows)
        long = trend.melt(id_vars="month", value_vars=["CRR %", "RRR %", "Upsell %"], var_name="Chỉ số", value_name="%")
        st.plotly_chart(px.line(long, x="month", y="%", color="Chỉ số", markers=True, title="Diễn biến theo tháng"), use_container_width=True)

    # Theo nhom
    st.subheader("Theo nhóm")
    dim = st.selectbox("Phân tích theo", ["team_sale_quan_ly", "team_sale_ban", "sale_quan_ly", "sale_ban_don", "teacher"], index=0)
    grp = []
    for name, g in f.groupby(dim):
        kk = kpis(g, REN)
        grp.append({dim: name, "Đến hạn": kk["due"], "Gia hạn": kk["renewed"],
                    "CRR %": round(kk["crr"], 1), "RRR %": round(kk["rrr"], 1),
                    "Upsell %": round(kk["upsell"], 1), "Renewal Revenue": round(kk["revenue"])})
    gdf = pd.DataFrame(grp).sort_values("Đến hạn", ascending=False)
    st.plotly_chart(px.bar(gdf.head(25), x=dim, y="CRR %", hover_data=["Đến hạn", "RRR %", "Upsell %"],
                           title=f"CRR theo {dim} (top 25 theo số đến hạn)"), use_container_width=True)
    st.dataframe(gdf, use_container_width=True)

with tab2:
    cols = ["month", "order_id", "uid", "tag", "ly_do_vao_list", "ngay_mua", "ngay_kich_hoat",
            "remaining", "last_study", "idle_ngay", "gia_tri_don_cu",
            "sale_ban_don", "team_sale_ban", "sale_quan_ly", "team_sale_quan_ly", "teacher",
            "da_gia_han_M90", "da_gia_han_vo_han", "ngay_gia_han", "gia_tri_don_gia_han",
            "nguon_gia_han", "so_ngay_den_gia_han"]
    cols = [c for c in cols if c in f.columns]
    only_ren = st.checkbox("Chỉ hiện đơn đã gia hạn", value=False)
    show = f[f[REN]] if only_ren else f
    st.write(f"{len(show):,} dòng")
    st.dataframe(show[cols], use_container_width=True, height=460)
    st.download_button("⬇️ Tải CSV đang lọc", show[cols].to_csv(index=False).encode("utf-8-sig"),
                       "expiry_filtered.csv", "text/csv")

with tab3:
    if situation.empty:
        st.info("Chưa có situation_*.csv.")
    else:
        s = situation[situation["month"].isin(sel_months)] if "month" in situation.columns else situation
        agg = s.groupby("nhom", as_index=False)["so_luong"].sum()
        tot = agg["so_luong"].sum()
        agg["ty_le_%"] = (agg["so_luong"] / tot * 100).round(1)
        agg = agg.sort_values("so_luong", ascending=False)
        st.plotly_chart(px.bar(agg, x="so_luong", y="nhom", orientation="h", text="ty_le_%",
                               title=f"Quy mô tình huống (tổng {tot:,} UID)"), use_container_width=True)
        st.dataframe(agg, use_container_width=True)

st.caption("DA-RE · không dùng end_date · CRR/RRR/Upsell theo định nghĩa DA-OD1RP · M+90 = cohort + 3 tháng.")
