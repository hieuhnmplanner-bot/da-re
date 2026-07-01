# -*- coding: utf-8 -*-
"""DA-RE — Dashboard Gia hạn. 3 ngôn ngữ (VI/EN/ZH). Tab1: dữ liệu gia hạn; Tab2: chi tiết."""
from pathlib import Path
import glob, re, os
import pandas as pd
import streamlit as st

st.set_page_config(page_title="DA-RE — Dashboard", layout="wide")
HERE = Path(__file__).resolve().parent
OUT = HERE / "Output"

# ---------------- i18n ----------------
LANG = {
 "Tiếng Việt": {
  "title":"📊 DA-RE — Dữ liệu Gia hạn","filters":"Bộ lọc","language":"Ngôn ngữ","month":"Tháng",
  "ren_def":"Định nghĩa gia hạn (nhóm Đến hạn)","m90":"M+90 (KPI cố định)","inf":"Vô hạn (Real rate)","team_f":"Team (sale quản lý)",
  "tab1":"📊 Dữ liệu gia hạn","tab2":"🧾 Chi tiết",
  "sec_due":"① Khách đến hạn (cohort cố định)","sec_early":"② Gia hạn sớm (luồng trong tháng)","sec_tot":"③ Tổng hợp gia hạn trong kỳ",
  "due":"Đến hạn","renewed":"Đã gia hạn","crr":"CRR – Gia hạn KH","rrr":"RRR – Gia hạn DT","upsell":"Upsell","rev":"Renewal Revenue",
  "early":"Gia hạn sớm","early_rev":"Doanh thu gia hạn sớm","pending":"Chưa kích hoạt","pending_pct":"% chưa kích hoạt",
  "tot_renew":"Tổng lượt gia hạn","tot_rev":"Tổng doanh thu gia hạn",
  "by_team":"Theo Team","team_dim":"Chọn loại team","t_ban":"Team sale bán","t_mgr":"Team sale quản lý",
  "by_indiv":"Theo cá nhân","indiv_dim":"Chọn theo","d_teacher":"Teacher","d_sban":"Sale bán","d_smgr":"Sale quản lý",
  "c_group":"Nhóm","c_due":"Đến hạn","c_renewed":"Đã gia hạn","c_crr":"CRR %","c_rrr":"RRR %","c_early":"Gia hạn sớm","c_totren":"Tổng lượt gia hạn","c_totrev":"Tổng DT gia hạn",
  "view":"Xem nhóm","v_both":"Cả hai","v_due":"Đến hạn","v_early":"Gia hạn sớm","download":"⬇️ Tải CSV","rows":"dòng",
  "h_crr":"Số đã gia hạn / Số đến hạn","h_rrr":"Doanh thu gia hạn / Tổng giá trị đơn đến hạn","h_up":">100% = khách chi nhiều hơn lần trước",
  "h_early":"Số khách gia hạn TRƯỚC khi hết hạn (theo ngày mua)","h_pend":"Đã trả tiền nhưng chưa bắt đầu học đơn mới",
  "def_now":"Định nghĩa nhóm đến hạn","warn":"Chưa có dữ liệu trong Output/. Chạy pipeline trước.","cap":"DA-RE · không dùng end_date · % = tỷ lệ, tiền = VND"},
 "English": {
  "title":"📊 DA-RE — Renewal Data","filters":"Filters","language":"Language","month":"Month",
  "ren_def":"Renewal definition (Due group)","m90":"M+90 (fixed KPI)","inf":"Unlimited (Real rate)","team_f":"Team (managing sale)",
  "tab1":"📊 Renewal data","tab2":"🧾 Detail",
  "sec_due":"① Customers due (fixed cohort)","sec_early":"② Early renewals (in-month flow)","sec_tot":"③ Total renewals in period",
  "due":"Due","renewed":"Renewed","crr":"CRR – Customer","rrr":"RRR – Revenue","upsell":"Upsell","rev":"Renewal Revenue",
  "early":"Early renewals","early_rev":"Early renewal revenue","pending":"Not activated","pending_pct":"% not activated",
  "tot_renew":"Total renewals","tot_rev":"Total renewal revenue",
  "by_team":"By Team","team_dim":"Team type","t_ban":"Selling sale team","t_mgr":"Managing sale team",
  "by_indiv":"By Individual","indiv_dim":"Group by","d_teacher":"Teacher","d_sban":"Selling sale","d_smgr":"Managing sale",
  "c_group":"Group","c_due":"Due","c_renewed":"Renewed","c_crr":"CRR %","c_rrr":"RRR %","c_early":"Early","c_totren":"Total renewals","c_totrev":"Total renewal rev",
  "view":"View","v_both":"Both","v_due":"Due","v_early":"Early","download":"⬇️ Download CSV","rows":"rows",
  "h_crr":"Renewed / Due","h_rrr":"Renewal revenue / Total due value","h_up":">100% = spending more than before",
  "h_early":"Customers who renewed BEFORE expiring (by purchase date)","h_pend":"Paid but not yet started the new order",
  "def_now":"Due-group definition","warn":"No data in Output/. Run the pipeline first.","cap":"DA-RE · no end_date · % = rate, money = VND"},
 "中文": {
  "title":"📊 DA-RE — 续费数据","filters":"筛选","language":"语言","month":"月份",
  "ren_def":"续费定义（到期组）","m90":"M+90（固定KPI）","inf":"不限时（真实率）","team_f":"团队（在管销售）",
  "tab1":"📊 续费数据","tab2":"🧾 明细",
  "sec_due":"① 到期客户（固定队列）","sec_early":"② 提前续费（当月流量）","sec_tot":"③ 当期续费汇总",
  "due":"到期","renewed":"已续费","crr":"CRR – 客户续费率","rrr":"RRR – 收入续费率","upsell":"升单率","rev":"续费收入",
  "early":"提前续费","early_rev":"提前续费收入","pending":"未激活","pending_pct":"未激活占比",
  "tot_renew":"总续费数","tot_rev":"总续费收入",
  "by_team":"按团队","team_dim":"团队类型","t_ban":"成交销售团队","t_mgr":"在管销售团队",
  "by_indiv":"按个人","indiv_dim":"分组方式","d_teacher":"老师","d_sban":"成交销售","d_smgr":"在管销售",
  "c_group":"分组","c_due":"到期","c_renewed":"已续费","c_crr":"CRR %","c_rrr":"RRR %","c_early":"提前续费","c_totren":"总续费数","c_totrev":"总续费收入",
  "view":"查看","v_both":"全部","v_due":"到期","v_early":"提前续费","download":"⬇️ 下载CSV","rows":"行",
  "h_crr":"已续费 / 到期","h_rrr":"续费收入 / 到期总价值","h_up":">100% = 比上次消费更多",
  "h_early":"在到期前续费的客户（按购买日期）","h_pend":"已付款但尚未开始新订单",
  "def_now":"到期组定义","warn":"Output/ 暂无数据，请先运行流程。","cap":"DA-RE · 不使用 end_date · % = 比率, 金额 = VND"},
}

def _truthy(s): return s.astype(str).str.strip().str.lower().isin(["true","1","yes"])
def _vnd(x):
    try: return f"{x:,.0f}đ"
    except Exception: return x
def _pct(x): return f"{x:.1f}%"

def _latest_per_month(pattern, required=None):
    best = {}
    for f in glob.glob(str(OUT / pattern)):
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
    return d

@st.cache_data
def load_early():
    d = _latest_per_month("early_renewal_*.csv")
    if d.empty: return d
    for c in ["gia_tri_don_cu","gia_tri_don_gia_han","order_no_uid"]:
        if c in d.columns: d[c] = pd.to_numeric(d[c], errors="coerce")
    return d

def kpis_due(df, ren_col):
    n = len(df); ren = df[ren_col].fillna(False); rn = int(ren.sum())
    et = df["gia_tri_don_cu"].sum(); nr = df.loc[ren,"gia_tri_don_gia_han"].sum(); orr = df.loc[ren,"gia_tri_don_cu"].sum()
    return dict(due=n, renewed=rn, crr=(rn/n*100 if n else 0), rrr=(nr/et*100 if et else 0),
                upsell=(nr/orr*100 if orr else 0), revenue=nr)

exp = load_expiry(); early = load_early()

# ---- Sidebar ----
lang_name = st.sidebar.selectbox("🌐 Ngôn ngữ / Language / 语言", list(LANG.keys()), index=0)
T = LANG[lang_name]
st.title(T["title"])
if exp.empty and early.empty: st.warning(T["warn"]); st.stop()

st.sidebar.header(T["filters"])
months = sorted(set(exp["month"].unique() if not exp.empty else []) | set(early["month"].unique() if not early.empty else []))
sel_months = st.sidebar.multiselect(T["month"], months, default=months)
ren_def = st.sidebar.radio(T["ren_def"], [T["m90"], T["inf"]], index=0)
REN = "da_gia_han_M90" if ren_def == T["m90"] else "da_gia_han_vo_han"
allteams = sorted(set(exp.get("team_sale_quan_ly", pd.Series(dtype=str)).dropna()) | set(early.get("team_sale_quan_ly", pd.Series(dtype=str)).dropna()))
sel_teams = st.sidebar.multiselect(T["team_f"], allteams, default=allteams)

def filt(d):
    if d.empty: return d
    x = d[d["month"].isin(sel_months)]
    if "team_sale_quan_ly" in x.columns and sel_teams: x = x[x["team_sale_quan_ly"].isin(sel_teams)]
    return x
fe = filt(exp); fr = filt(early)

def group_table(dim):
    """Bang gop Den han + Gia han som theo cot 'dim'. Tra DataFrame da format."""
    rows = {}
    if not fe.empty and dim in fe.columns:
        for name, sub in fe.groupby(dim):
            k = kpis_due(sub, REN)
            rows[name] = dict(due=k["due"], renewed=k["renewed"], crr=k["crr"], rrr=k["rrr"], revd=k["revenue"], early=0, reve=0)
    if not fr.empty and dim in fr.columns:
        for name, sub in fr.groupby(dim):
            r = rows.setdefault(name, dict(due=0,renewed=0,crr=0,rrr=0,revd=0,early=0,reve=0))
            r["early"] = len(sub); r["reve"] = sub["gia_tri_don_gia_han"].sum()
    if not rows: return pd.DataFrame()
    df = pd.DataFrame([{**{"g":k}, **v} for k,v in rows.items()]).sort_values("due", ascending=False)
    out = pd.DataFrame({
        T["c_group"]: df["g"], T["c_due"]: df["due"], T["c_renewed"]: df["renewed"],
        T["c_crr"]: df["crr"].map(_pct), T["c_rrr"]: df["rrr"].map(_pct),
        T["c_early"]: df["early"], T["c_totren"]: df["renewed"]+df["early"],
        T["c_totrev"]: (df["revd"]+df["reve"]).map(_vnd)})
    return out

tab1, tab2 = st.tabs([T["tab1"], T["tab2"]])

with tab1:
    K = kpis_due(fe, REN) if not fe.empty else dict(due=0,renewed=0,crr=0,rrr=0,upsell=0,revenue=0)
    st.subheader(T["sec_due"])
    c = st.columns(6)
    c[0].metric(T["due"], f"{K['due']:,}")
    c[1].metric(T["renewed"], f"{K['renewed']:,}")
    c[2].metric(T["crr"], _pct(K["crr"]), help=T["h_crr"])
    c[3].metric(T["rrr"], _pct(K["rrr"]), help=T["h_rrr"])
    c[4].metric(T["upsell"], _pct(K["upsell"]), help=T["h_up"])
    c[5].metric(T["rev"], _vnd(K["revenue"]))

    st.subheader(T["sec_early"])
    ne = len(fr); pend = int((fr.get("trang_thai_kich_hoat","")=="Chưa kích hoạt").sum()) if ne else 0
    erev = fr["gia_tri_don_gia_han"].sum() if ne else 0
    c = st.columns(4)
    c[0].metric(T["early"], f"{ne:,}", help=T["h_early"])
    c[1].metric(T["early_rev"], _vnd(erev))
    c[2].metric(T["pending"], f"{pend:,}", help=T["h_pend"])
    c[3].metric(T["pending_pct"], _pct(pend/ne*100 if ne else 0))

    st.subheader(T["sec_tot"])
    c = st.columns(2)
    c[0].metric(T["tot_renew"], f"{K['renewed']+ne:,}")
    c[1].metric(T["tot_rev"], _vnd(K["revenue"]+erev))
    st.caption(f"{T['def_now']}: **{ren_def}** · {len(sel_months)} {T['month']} · {len(sel_teams)} team")

    # Bang theo Team
    st.subheader(T["by_team"])
    tmap = {T["t_mgr"]:"team_sale_quan_ly", T["t_ban"]:"team_sale_ban"}
    tsel = st.selectbox(T["team_dim"], list(tmap.keys()), index=0, key="team_dim")
    gt = group_table(tmap[tsel])
    if not gt.empty: st.dataframe(gt, use_container_width=True, hide_index=True)

    # Bang theo Ca nhan
    st.subheader(T["by_indiv"])
    imap = {T["d_teacher"]:"teacher", T["d_sban"]:"sale_ban_don", T["d_smgr"]:"sale_quan_ly"}
    isel = st.selectbox(T["indiv_dim"], list(imap.keys()), index=0, key="indiv_dim")
    gi = group_table(imap[isel])
    if not gi.empty: st.dataframe(gi, use_container_width=True, hide_index=True)

with tab2:
    view = st.radio(T["view"], [T["v_both"], T["v_due"], T["v_early"]], horizontal=True)
    frames = []
    if view in (T["v_both"], T["v_due"]) and not fe.empty:
        a = fe.copy(); a["trang_thai"] = a[REN].map({True:T["renewed"], False:"—"}); a["order_id_moi"]=""
        a["ngay_gh"] = a.get("ngay_gia_han"); frames.append(a)
    if view in (T["v_both"], T["v_early"]) and not fr.empty:
        b = fr.copy(); b["trang_thai"] = b.get("trang_thai_kich_hoat"); b["ngay_mua"]=b.get("pay_time"); b["ngay_gh"]=b.get("ngay_kich_hoat"); frames.append(b)
    if not frames: st.info("—")
    else:
        d = pd.concat(frames, ignore_index=True)
        cols = ["month","nhom","order_id","order_no_uid","uid","order_id_moi","trang_thai","remaining",
                "ngay_mua","ngay_gh","gia_tri_don_cu","gia_tri_don_gia_han",
                "sale_ban_don","team_sale_ban","sale_quan_ly","team_sale_quan_ly","teacher","tag"]
        cols = [c for c in cols if c in d.columns]
        st.write(f"{len(d):,} {T['rows']}")
        st.dataframe(d[cols], use_container_width=True, height=470)
        st.download_button(T["download"], d[cols].to_csv(index=False).encode("utf-8-sig"), "chi_tiet.csv","text/csv")

st.caption(T["cap"])
