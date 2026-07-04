# -*- coding: utf-8 -*-
"""DA-RE — Dashboard Gia hạn. 4 tab: Gia hạn (hiện tại) | Gia hạn (bản mới) | Chi tiết | Ngủ đông.
KHÔNG dùng end_date. 3 ngôn ngữ VI/EN/ZH."""
from pathlib import Path
import glob, re, os
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

st.set_page_config(page_title="DA-RE — Dashboard", layout="wide")
HERE = Path(__file__).resolve().parent
OUT = HERE / "Output"

# --------- i18n ---------
def L(vi, en, zh): return {"Tiếng Việt": vi, "English": en, "中文": zh}
K = {
 "title": L("📊 DA-RE — Dữ liệu Gia hạn","📊 DA-RE — Renewal Data","📊 DA-RE — 续费数据"),
 "filters": L("Bộ lọc","Filters","筛选"), "month": L("Tháng","Month","月份"),
 "ren_def": L("Định nghĩa gia hạn","Renewal definition","续费定义"),
 "m90": L("M+90 (KPI cố định)","M+90 (fixed KPI)","M+90（固定KPI）"), "inf": L("Vô hạn (Real rate)","Unlimited (Real)","不限时"),
 "team_f": L("Team (sale quản lý)","Team (managing sale)","团队（在管销售）"), "ono_f": L("Đơn thứ mấy của UID","Order # of UID","客户第几单"),
 "t_old": L("📊 Gia hạn (hiện tại)","📊 Renewal (current)","📊 续费(现版)"),
 "t_new": L("🆕 Gia hạn (bản mới)","🆕 Renewal (new)","🆕 续费(新版)"),
 "t_detail": L("🧾 Chi tiết","🧾 Detail","🧾 明细"), "t_dorm": L("😴 Ngủ đông / Rời bỏ","😴 Dormant / Churn","😴 冻结/流失"),
 # cards
 "due": L("Đến hạn","Due","到期"), "renewed": L("Đã gia hạn","Renewed","已续费"),
 "crr": L("CRR – Gia hạn KH","CRR – Customer","CRR-客户续费率"), "rrr": L("RRR – Gia hạn DT","RRR – Revenue","RRR-收入续费率"),
 "upsell": L("Upsell","Upsell","升单率"), "rev": L("Renewal Revenue","Renewal Revenue","续费收入"),
 "early": L("Gia hạn sớm","Early renewals","提前续费"), "early_rev": L("DT gia hạn sớm","Early rev","提前续费收入"),
 "pending": L("Chưa kích hoạt","Not activated","未激活"), "pending_pct": L("% chưa kích hoạt","% not activated","未激活占比"),
 "tot_renew": L("Tổng lượt gia hạn","Total renewals","总续费数"), "tot_rev": L("Tổng DT gia hạn","Total renewal rev","总续费收入"),
 # new model
 "sec_kpi": L("Tỷ lệ (KPI)","Ratios (KPI)","比率 (KPI)"), "sec_mau": L("MẪU SỐ — Khách tới hạn trong kỳ","DENOMINATOR — Customers due","分母 — 到期客户"),
 "sec_tu": L("TỬ SỐ — Đã gia hạn theo thời điểm","NUMERATOR — Renewed by timing","分子 — 按时间续费"),
 "sec_funnel": L("Phễu chuyển đổi","Conversion funnel","转化漏斗"),
 "src_den": L("Đến hạn (đầu tháng)","Due (month start)","到期(月初)"), "src_mid": L("Hết hạn phát sinh","Mid-month expiry","月中到期"),
 "tot_mau": L("Tổng mẫu số","Total denominator","分母合计"),
 "tim_dung": L("Đúng hạn","On-time","按时"), "tim_som": L("Sớm","Early","提前"), "tim_muon": L("Muộn","Late","延迟"), "tot_tu": L("Tổng đã gia hạn","Total renewed","已续费合计"),
 "explain": L("📖 Công thức tính CRR/RRR/Upsell (bấm để xem)","📖 CRR/RRR/Upsell formula (click)","📖 CRR/RRR/Upsell 公式（点击）"),
 "explain_body": L(
   "**CRR** = Tử số / Mẫu số.\n\n**Mẫu số** = Đến hạn (đầu tháng) + Hết hạn phát sinh (về 0 buổi giữa tháng) + Gia hạn sớm (mua đơn mới khi chưa tới hạn).\n\n**Tử số** = số đã gia hạn = Đúng hạn (gia hạn trong tháng cohort) + Sớm (nhóm gia hạn sớm) + Muộn (gia hạn ở tháng sau).\n\n**RRR** = Doanh thu các đơn gia hạn / Tổng giá trị đơn tới hạn.\n\n**Upsell** = Giá trị đơn gia hạn mới / Giá trị đơn cũ (của nhóm đã gia hạn). >100% = chi nhiều hơn.\n\nHai chế độ: **M+90** khóa trong ~3 tháng (KPI cố định); **Real** tính mọi lúc.",
   "**CRR** = Numerator / Denominator.\n\n**Denominator** = Due (month start) + Mid-month expiry (hit 0 mid-month) + Early renewals (bought before due).\n\n**Numerator** = renewed = On-time + Early + Late.\n\n**RRR** = renewal revenue / total due value.\n\n**Upsell** = new renewal value / old value of renewers. >100% = spending more.\n\nTwo modes: **M+90** locked ~3 months; **Real** anytime.",
   "**CRR** = 分子 / 分母。\n\n**分母** = 到期(月初) + 月中到期(月中归零) + 提前续费。\n\n**分子** = 已续费 = 按时 + 提前 + 延迟。\n\n**RRR** = 续费收入 / 到期总价值。\n\n**Upsell** = 新续费金额 / 续费者旧金额。>100%=消费更多。\n\n两种模式：**M+90** 锁定约3个月；**Real** 任意时间。"),
 # dormant
 "d_type": L("Loại","Type","类型"), "d_freeze": L("Đóng băng chủ động","Active freeze","主动冻结"), "d_silent": L("Im lặng rời bỏ","Silent churn","静默流失"),
 "d_total_left": L("Tổng buổi còn treo","Total lessons hanging","剩余课时合计"), "d_denhan": L("Thuộc Đến hạn tháng","In Due month","所属到期月"),
 "d_pending": L("Đơn chưa kích hoạt","Pending order","待激活订单"), "d_idle": L("Số ngày nghỉ","Idle days","停学天数"),
 "d_remain": L("Số buổi còn","Lessons left","剩余课时"),
 # detail headers (giu tu ban truoc)
 "h_month":L("Tháng","Month","月份"),"h_group":L("Nhóm","Group","分组"),"h_reason":L("Lý do","Reason","原因"),"h_uid":L("UID","UID","UID"),
 "h_oid":L("Order ID","Order ID","订单ID"),"h_ono":L("Đơn thứ mấy","Order #","第几单"),"h_status":L("Trạng thái","Status","状态"),
 "h_oidnew":L("Order ID mới","New Order ID","新订单ID"),"h_rendate":L("Ngày gia hạn","Renewal date","续费日期"),
 "h_remain":L("Số buổi còn","Lessons left","剩余课时"),"h_buydate":L("Ngày mua","Purchase date","购买日期"),
 "h_valold":L("Giá trị đơn","Order value","订单金额"),"h_valnew":L("Giá trị đơn gia hạn","Renewal value","续费金额"),
 "h_sban":L("Sale bán","Selling sale","成交销售"),"h_tban":L("Team bán","Selling team","成交团队"),
 "h_smgr":L("Sale quản lý","Managing sale","在管销售"),"h_tmgr":L("Team quản lý","Managing team","在管团队"),"h_teacher":L("Teacher","Teacher","老师"),
 "r_th1":L("Còn 1–9 buổi, đang học","1–9 left, active","剩1–9,在学"),"r_th2":L("Vừa hết buổi (≤10 ngày)","Just finished","刚上完"),
 "r_frozen":L(" · Frozen"," · Frozen"," · 冻结"),"r_eact":L("Gia hạn sớm · đã kích hoạt","Early · activated","提前·已激活"),"r_epend":L("Gia hạn sớm · chưa kích hoạt","Early · not activated","提前·未激活"),
 "s_renewed":L("Đã gia hạn","Renewed","已续费"),"s_not":L("Chưa gia hạn","Not renewed","未续费"),"s_act":L("Đã kích hoạt","Activated","已激活"),"s_notact":L("Chưa kích hoạt","Not activated","未激活"),
 "view":L("Xem nhóm","View","查看"),"v_both":L("Cả hai","Both","全部"),"v_due":L("Đến hạn","Due","到期"),"v_early":L("Gia hạn sớm","Early","提前"),
 "download":L("⬇️ Tải CSV","⬇️ Download","⬇️ 下载"),"rows":L("dòng","rows","行"),
 "by_team":L("Theo Team","By Team","按团队"),"team_dim":L("Chọn loại team","Team type","团队类型"),"t_ban":L("Team sale bán","Selling team","成交团队"),"t_mgr":L("Team sale quản lý","Managing team","在管团队"),
 "by_indiv":L("Theo cá nhân","By Individual","按个人"),"indiv_dim":L("Chọn theo","Group by","分组"),"d_teacher":L("Teacher","Teacher","老师"),"d_sban":L("Sale bán","Selling sale","成交销售"),"d_smgr":L("Sale quản lý","Managing sale","在管销售"),
 "c_group":L("Nhóm","Group","分组"),"c_totren":L("Tổng lượt gia hạn","Total renewals","总续费"),"c_totrev":L("Tổng DT gia hạn","Total renewal rev","总续费收入"),
 "warn": L("Chưa có dữ liệu. Chạy pipeline trước.","No data. Run pipeline first.","暂无数据。"),
 "cap": L("DA-RE · không dùng end_date · % = tỷ lệ, tiền = VND","DA-RE · no end_date","DA-RE · 不使用end_date"),
 "h_crr": L("Đã gia hạn / Tới hạn","Renewed / Due","已续费/到期"), "h_rrr": L("DT gia hạn / Giá trị tới hạn","Renewal rev / due value","续费收入/到期价值"),
 "h_up": L(">100% = chi nhiều hơn",">100% = spending more",">100%=消费更多"), "h_early": L("Mua đơn mới khi chưa tới hạn","Bought before due","到期前购买"),
}
def TR(lang): return {k: v[lang] for k, v in K.items()}

def _truthy(s): return s.astype(str).str.strip().str.lower().isin(["true","1","yes"])
def _vnd(x):
    try: return f"{x:,.0f}đ"
    except Exception: return x
def _pct(x): return f"{x:.1f}%"

def _latest(pattern, required=None):
    best = {}
    for f in glob.glob(str(OUT / pattern)):
        mm = re.search(r"(\d{4}-\d{2})", Path(f).name)
        if not mm: continue
        try:
            if required and required not in pd.read_csv(f, nrows=0).columns: continue
        except Exception: continue
        mt = os.path.getmtime(f); m = mm.group(1)
        if m not in best or mt > best[m][0]: best[m] = (mt, f)
    frames = []
    for m,(_,f) in best.items():
        try: d = pd.read_csv(f, dtype=str)
        except Exception: continue
        if len(d): d["month"] = m; frames.append(d)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

@st.cache_data
def load_expiry():
    d = _latest("expiry_*_status_*.csv", required="gia_tri_don_cu")
    if d.empty: return d
    for c in ["da_gia_han_M90","da_gia_han_vo_han"]: d[c] = _truthy(d[c])
    for c in ["gia_tri_don_cu","gia_tri_don_gia_han","remaining","order_no_uid"]:
        if c in d.columns: d[c] = pd.to_numeric(d[c], errors="coerce")
    return d
@st.cache_data
def load_early():
    d = _latest("early_renewal_*.csv")
    if d.empty: return d
    for c in ["gia_tri_don_cu","gia_tri_don_gia_han","order_no_uid"]:
        if c in d.columns: d[c] = pd.to_numeric(d[c], errors="coerce")
    return d
@st.cache_data
def load_mid():
    return _latest("mid_expiry_*.csv")
@st.cache_data
def load_dormant():
    files = glob.glob(str(OUT/"dormant_*.csv"))
    if not files: return pd.DataFrame()
    f = max(files, key=os.path.getmtime)
    try: d = pd.read_csv(f, dtype=str)
    except Exception: return pd.DataFrame()
    if "remaining" in d.columns: d["remaining"] = pd.to_numeric(d["remaining"], errors="coerce")
    return d

def kpis_due(df, ren_col):
    n = len(df); ren = df[ren_col].fillna(False); rn = int(ren.sum())
    et = df["gia_tri_don_cu"].sum(); nr = df.loc[ren,"gia_tri_don_gia_han"].sum(); orr = df.loc[ren,"gia_tri_don_cu"].sum()
    return dict(due=n, renewed=rn, crr=(rn/n*100 if n else 0), rrr=(nr/et*100 if et else 0), upsell=(nr/orr*100 if orr else 0), revenue=nr)

exp = load_expiry(); early = load_early(); mid = load_mid(); dorm = load_dormant()
lang = st.sidebar.selectbox("🌐 Ngôn ngữ / Language / 语言", ["Tiếng Việt","English","中文"], index=0)
T = TR(lang)
st.title(T["title"])
if exp.empty and early.empty: st.warning(T["warn"]); st.stop()

st.sidebar.header(T["filters"])
months = sorted(set(exp["month"].unique() if not exp.empty else []) | set(early["month"].unique() if not early.empty else []))
sel_months = st.sidebar.multiselect(T["month"], months, default=months)
ren_def = st.sidebar.radio(T["ren_def"], [T["m90"], T["inf"]], index=0)
REN = "da_gia_han_M90" if ren_def == T["m90"] else "da_gia_han_vo_han"
allteams = sorted(set(exp.get("team_sale_quan_ly", pd.Series(dtype=str)).dropna()) | set(early.get("team_sale_quan_ly", pd.Series(dtype=str)).dropna()))
sel_teams = st.sidebar.multiselect(T["team_f"], allteams, default=allteams)
onos = sorted({int(x) for x in pd.concat([(exp["order_no_uid"] if not exp.empty else pd.Series(dtype=float)),(early["order_no_uid"] if not early.empty else pd.Series(dtype=float))]).dropna().tolist()})
sel_ono = st.sidebar.multiselect(T["ono_f"], onos, default=onos)

def filt(d):
    if d.empty: return d
    x = d[d["month"].isin(sel_months)] if "month" in d.columns else d
    if "team_sale_quan_ly" in x.columns and sel_teams: x = x[x["team_sale_quan_ly"].isin(sel_teams)]
    if "order_no_uid" in x.columns and sel_ono: x = x[pd.to_numeric(x["order_no_uid"], errors="coerce").isin(sel_ono)]
    return x
fe = filt(exp); fr = filt(early); fm = filt(mid) if not mid.empty else mid

def group_table(dim):
    rows = {}
    if not fe.empty and dim in fe.columns:
        for name, sub in fe.groupby(dim):
            k = kpis_due(sub, REN); rows[name] = dict(due=k["due"], renewed=k["renewed"], crr=k["crr"], rrr=k["rrr"], revd=k["revenue"], early=0, reve=0)
    if not fr.empty and dim in fr.columns:
        for name, sub in fr.groupby(dim):
            r = rows.setdefault(name, dict(due=0,renewed=0,crr=0,rrr=0,revd=0,early=0,reve=0)); r["early"]=len(sub); r["reve"]=sub["gia_tri_don_gia_han"].sum()
    if not rows: return pd.DataFrame()
    df = pd.DataFrame([{**{"g":k},**v} for k,v in rows.items()]).sort_values("due", ascending=False)
    return pd.DataFrame({T["c_group"]:df["g"], T["due"]:df["due"], T["renewed"]:df["renewed"],
        T["crr"]:df["crr"].map(_pct), T["rrr"]:df["rrr"].map(_pct), T["early"]:df["early"],
        T["c_totren"]:df["renewed"]+df["early"], T["c_totrev"]:(df["revd"]+df["reve"]).map(_vnd)})

tab_old, tab_new, tab_detail, tab_dorm = st.tabs([T["t_old"], T["t_new"], T["t_detail"], T["t_dorm"]])

# ---------------- TAB HIỆN TẠI ----------------
with tab_old:
    K0 = kpis_due(fe, REN) if not fe.empty else dict(due=0,renewed=0,crr=0,rrr=0,upsell=0,revenue=0)
    st.subheader("① " + T["due"])
    c = st.columns(6)
    c[0].metric(T["due"], f"{K0['due']:,}"); c[1].metric(T["renewed"], f"{K0['renewed']:,}")
    c[2].metric(T["crr"], _pct(K0["crr"]), help=T["h_crr"]); c[3].metric(T["rrr"], _pct(K0["rrr"]), help=T["h_rrr"])
    c[4].metric(T["upsell"], _pct(K0["upsell"]), help=T["h_up"]); c[5].metric(T["rev"], _vnd(K0["revenue"]))
    st.subheader("② " + T["early"])
    ne = len(fr); pend = int((fr.get("trang_thai_kich_hoat","")=="Chưa kích hoạt").sum()) if ne else 0
    erev = fr["gia_tri_don_gia_han"].sum() if ne else 0
    c = st.columns(4); c[0].metric(T["early"], f"{ne:,}", help=T["h_early"]); c[1].metric(T["early_rev"], _vnd(erev))
    c[2].metric(T["pending"], f"{pend:,}"); c[3].metric(T["pending_pct"], _pct(pend/ne*100 if ne else 0))
    st.subheader(T["by_team"])
    tmap = {T["t_mgr"]:"team_sale_quan_ly", T["t_ban"]:"team_sale_ban"}
    tsel = st.selectbox(T["team_dim"], list(tmap.keys()), key="old_team")
    g = group_table(tmap[tsel]);  st.dataframe(g, use_container_width=True, hide_index=True) if not g.empty else None
    st.subheader(T["by_indiv"])
    imap = {T["d_teacher"]:"teacher", T["d_sban"]:"sale_ban_don", T["d_smgr"]:"sale_quan_ly"}
    isel = st.selectbox(T["indiv_dim"], list(imap.keys()), key="old_indiv")
    g = group_table(imap[isel]); st.dataframe(g, use_container_width=True, hide_index=True) if not g.empty else None

# ---------------- TAB BẢN MỚI ----------------
def cohort(fe, fr, fm, REN):
    n_den = len(fe); n_mid = len(fm) if fm is not None and not fm.empty else 0; n_early = len(fr)
    denom = n_den + n_mid + n_early
    ren_fe = fe[fe[REN].fillna(False)] if not fe.empty else fe
    if not ren_fe.empty:
        ghm = pd.to_datetime(ren_fe["ngay_gia_han"], errors="coerce").dt.to_period("M").astype(str)
        dung = int((ghm == ren_fe["month"]).sum()); muon = int((ghm != ren_fe["month"]).sum())
    else: dung = muon = 0
    som = n_early; num = dung + som + muon
    rev = (ren_fe["gia_tri_don_gia_han"].sum() if not ren_fe.empty else 0) + (fr["gia_tri_don_gia_han"].sum() if not fr.empty else 0)
    exp_val = (fe["gia_tri_don_cu"].sum() if not fe.empty else 0) + (fr["gia_tri_don_cu"].sum() if not fr.empty else 0)
    old_ren = (ren_fe["gia_tri_don_cu"].sum() if not ren_fe.empty else 0) + (fr["gia_tri_don_cu"].sum() if not fr.empty else 0)
    return dict(n_den=n_den,n_mid=n_mid,n_early=n_early,denom=denom,dung=dung,som=som,muon=muon,num=num,
                crr=(num/denom*100 if denom else 0), rrr=(rev/exp_val*100 if exp_val else 0), ups=(rev/old_ren*100 if old_ren else 0), rev=rev)

with tab_new:
    with st.expander(T["explain"]):
        st.markdown(T["explain_body"])
    C = cohort(fe, fr, fm, REN)
    st.subheader(T["sec_kpi"])
    c = st.columns(4)
    c[0].metric(T["crr"], _pct(C["crr"]), help=T["h_crr"]); c[1].metric(T["rrr"], _pct(C["rrr"]), help=T["h_rrr"])
    c[2].metric(T["upsell"], _pct(C["ups"]), help=T["h_up"]); c[3].metric(T["rev"], _vnd(C["rev"]))
    st.subheader(T["sec_mau"])
    c = st.columns(4)
    c[0].metric(T["src_den"], f"{C['n_den']:,}"); c[1].metric(T["src_mid"], f"{C['n_mid']:,}")
    c[2].metric(T["early"], f"{C['n_early']:,}"); c[3].metric(T["tot_mau"], f"{C['denom']:,}")
    st.subheader(T["sec_tu"])
    c = st.columns(4)
    c[0].metric(T["tim_dung"], f"{C['dung']:,}"); c[1].metric(T["tim_som"], f"{C['som']:,}")
    c[2].metric(T["tim_muon"], f"{C['muon']:,}"); c[3].metric(T["tot_tu"], f"{C['num']:,}")
    st.subheader(T["sec_funnel"])
    fig = go.Figure(go.Funnel(y=[T["tot_mau"], T["tot_tu"]], x=[C["denom"], C["num"]], textinfo="value+percent initial"))
    fig.update_layout(height=260, margin=dict(l=10,r=10,t=10,b=10)); st.plotly_chart(fig, use_container_width=True)
    st.subheader(T["by_team"])
    tmap = {T["t_mgr"]:"team_sale_quan_ly", T["t_ban"]:"team_sale_ban"}
    tsel = st.selectbox(T["team_dim"], list(tmap.keys()), key="new_team")
    g = group_table(tmap[tsel]); st.dataframe(g, use_container_width=True, hide_index=True) if not g.empty else None
    st.subheader(T["by_indiv"])
    imap = {T["d_teacher"]:"teacher", T["d_sban"]:"sale_ban_don", T["d_smgr"]:"sale_quan_ly"}
    isel = st.selectbox(T["indiv_dim"], list(imap.keys()), key="new_indiv")
    g = group_table(imap[isel]); st.dataframe(g, use_container_width=True, hide_index=True) if not g.empty else None

# ---------------- TAB CHI TIẾT ----------------
with tab_detail:
    view = st.radio(T["view"], [T["v_both"], T["v_due"], T["v_early"]], horizontal=True)
    def _reason(r):
        if r.get("nhom") == "Đến hạn":
            base = T["r_th2"] if "remaining=0" in str(r.get("ly_do_vao_list","")) else T["r_th1"]
            if str(r.get("tag","")) == "Frozen": base += T["r_frozen"]
            return base
        return T["r_eact"] if str(r.get("trang_thai_kich_hoat","")) == "Đã kích hoạt" else T["r_epend"]
    def _status(r, kind):
        if kind == "due": return T["s_renewed"] if bool(r.get(REN)) else T["s_not"]
        return T["s_act"] if str(r.get("trang_thai_kich_hoat","")) == "Đã kích hoạt" else T["s_notact"]
    def _mny(x): return _vnd(x) if pd.notna(x) else ""
    def _row(r, kind):
        rdate = r.get("ngay_gia_han") if kind=="due" else r.get("ngay_kich_hoat")
        bdate = r.get("ngay_mua") if kind=="due" else r.get("pay_time")
        return {T["h_month"]:r.get("month"), T["h_group"]:r.get("nhom"), T["h_reason"]:_reason(r), T["h_uid"]:r.get("uid"),
            T["h_oid"]:r.get("order_id"), T["h_ono"]:r.get("order_no_uid"), T["h_status"]:_status(r,kind),
            T["h_oidnew"]:r.get("order_id_moi",""), T["h_rendate"]:rdate,
            T["h_remain"]:(int(r["remaining"]) if kind=="due" and pd.notna(r.get("remaining")) else ""),
            T["h_buydate"]:bdate, T["h_valold"]:_mny(r.get("gia_tri_don_cu")), T["h_valnew"]:_mny(r.get("gia_tri_don_gia_han")),
            T["h_sban"]:r.get("sale_ban_don"), T["h_tban"]:r.get("team_sale_ban"), T["h_smgr"]:r.get("sale_quan_ly"),
            T["h_tmgr"]:r.get("team_sale_quan_ly"), T["h_teacher"]:r.get("teacher")}
    recs = []
    if view in (T["v_both"],T["v_due"]) and not fe.empty:
        for _,r in fe.iterrows(): recs.append(_row(r,"due"))
    if view in (T["v_both"],T["v_early"]) and not fr.empty:
        for _,r in fr.iterrows(): recs.append(_row(r,"early"))
    if not recs: st.info("—")
    else:
        disp = pd.DataFrame(recs); st.write(f"{len(disp):,} {T['rows']}")
        st.dataframe(disp, use_container_width=True, height=470, hide_index=True)
        st.download_button(T["download"], disp.to_csv(index=False).encode("utf-8-sig"), "chi_tiet.csv","text/csv")

# ---------------- TAB NGỦ ĐÔNG ----------------
with tab_dorm:
    if dorm.empty: st.info("—")
    else:
        d = dorm.copy()
        if sel_teams and "team_sale_quan_ly" in d.columns: d = d[d["team_sale_quan_ly"].isin(sel_teams)]
        nf = int((d["loai"]=="Đóng băng chủ động").sum()); ns = int((d["loai"]=="Im lặng rời bỏ").sum())
        left = pd.to_numeric(d["remaining"], errors="coerce").sum()
        c = st.columns(3)
        c[0].metric(T["d_freeze"], f"{nf:,}"); c[1].metric(T["d_silent"], f"{ns:,}"); c[2].metric(T["d_total_left"], f"{left:,.0f}")
        cols = {"loai":T["d_type"],"uid":T["h_uid"],"order_id":T["h_oid"],"order_no_uid":T["h_ono"],"remaining":T["d_remain"],
                "last_study":T["h_buydate"],"idle_ngay":T["d_idle"],"don_chua_kich_hoat":T["d_pending"],"den_han_thang":T["d_denhan"],
                "sale_ban_don":T["h_sban"],"team_sale_ban":T["h_tban"],"sale_quan_ly":T["h_smgr"],"team_sale_quan_ly":T["h_tmgr"],"teacher":T["h_teacher"]}
        cc = [c for c in cols if c in d.columns]
        st.write(f"{len(d):,} {T['rows']}")
        st.dataframe(d[cc].rename(columns=cols), use_container_width=True, height=440, hide_index=True)
        st.download_button(T["download"], d[cc].rename(columns=cols).to_csv(index=False).encode("utf-8-sig"), "ngu_dong.csv","text/csv")

st.caption(T["cap"])
