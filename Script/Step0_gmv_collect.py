# -*- coding: utf-8 -*-
"""
DA-RE — Tu dong tai GMV.csv tu Google Sheets (3 mien: Ha Noi / HCM / Da Nang).
Sao chep co che tu du an "Order 1 - Order 2" (Step0_gmv_collect.py).
Sheet phai o che do public (hoac share) de export CSV truc tiep.
"""
import pandas as pd
import urllib.request
import urllib.error
import ssl
import io
from pathlib import Path

# CAU HINH DUONG DAN
BASE_DIR    = Path(__file__).resolve().parent.parent   # ...\DA-RE
INPUT_DIR   = BASE_DIR / "Data_input"
OUTPUT_PATH = INPUT_DIR / "GMV.csv"

# Google Sheets ID + GID tung tab
SHEET_ID = "1sEthbH-zcMavoQ1qi9J_CNnHAJoyt0gfsE-xsMW0LCc"
GID_HANOI  = 0
GID_HCM    = 1374953727
GID_DANANG = 355929644

COMMON_RENAME = {
    "bank day": "bank_day", "bank time": "bank_time", "Gateway": "gateway",
    "User Name": "user_name", "Phone": "phone", "UID": "uid", "Package": "package",
    "Fixed/ non-fixed": "fixed_non_fixed", "Pay Time": "pay_time",
    "Real Pay(VND)": "real_pay_vnd", "GMV (RMB)": "gmv_rmb",
    "Payment Method": "payment_method", "Type": "type", "Sales": "sales", "Note": "note",
}
HANOI_EXTRA_RENAME = {
    "Full Price(VND)": "full_price_vnd", "Month of payment": "month_of_payment",
    "总 B (被推荐） 课数": "total_b_lessons",
    "渠道号": "channel", "实际卖课单价 VND": "unit_price_vnd",
    "采购价格（包括转介绍赠送课)": "purchase_price_total",
    "Nguồn": "source_1",
}
HCM_EXTRA_RENAME    = {"Month of payment": "month_of_payment"}
DANANG_EXTRA_RENAME = {"渠道号": "channel"}

HANOI_TEAM_MAP = {
    "In-house 1": "In-house 1", "In-house 2": "In-house 2", "In-house": "In-house 1",
    "Linh Dam Store": "Offline-LĐ", "An Binh Store": "Offline-AB",
    "Aeon mall Booth": "In-house 1", "Offline-LĐ": "Offline-LĐ",
    "Offline-AB": "Offline-AB", "HCM team": "HCM team", "Danang team": "Danang team",
    "Khác": "Khác",
}
HANOI_TEAM_DEFAULT = "In-house 1"


def download_sheet(sheet_id, gid, sheet_name):
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    print(f"  Dang tai sheet '{sheet_name}'...")
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        opener = urllib.request.build_opener(urllib.request.HTTPSHandler(context=ssl_ctx))
        with opener.open(req, timeout=30) as resp:
            content = resp.read()
        df = pd.read_csv(io.BytesIO(content))
        print(f"  OK {sheet_name}: {len(df):,} hang, {len(df.columns)} cot")
        return df
    except Exception as e:
        raise RuntimeError(f"Khong tai duoc sheet '{sheet_name}' (gid={gid}). Loi: {e}\n  URL: {url}")


def clean_vnd(series: pd.Series) -> pd.Series:
    """Chuan hoa tien VND -> so nguyen (chuoi). Xu ly ca 3 dinh dang:
    - So thuc float: '10080000.0' -> 10080000  (KHONG xoa dau cham thap phan!)
    - VN nghin: '10.080.000' -> 10080000
    - Dau phay: '10,080,000' -> 10080000
    """
    def fix(x):
        s = str(x).strip().replace(" ", "").replace(",", "")
        if s.count(".") > 1:          # VN: nhieu dau cham = phan cach nghin
            s = s.replace(".", "")
        try:
            return str(int(round(float(s))))   # 1 dau cham = thap phan -> float xu ly dung
        except Exception:
            return "0"
    return series.map(fix)



def process_hanoi(df):
    bad_uid = df["UID"].astype(str).str.startswith("84-") | df["UID"].astype(str).str.startswith(":")
    df = df[~bad_uid].copy()
    df = df[~df["UID"].isna()].copy()
    rename_map = {**COMMON_RENAME, **HANOI_EXTRA_RENAME}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["real_pay_vnd"] = clean_vnd(df["real_pay_vnd"])
    if "Team" in df.columns:
        df["Team"] = df["Team"].map(HANOI_TEAM_MAP).fillna(
            df["Team"].where(df["Team"].notna(), HANOI_TEAM_DEFAULT)).fillna(HANOI_TEAM_DEFAULT)
    else:
        df["Team"] = HANOI_TEAM_DEFAULT
    if "TEAM" in df.columns and "Team" not in df.columns:
        df = df.rename(columns={"TEAM": "Team"})
        df["Team"] = df["Team"].map(HANOI_TEAM_MAP).fillna(HANOI_TEAM_DEFAULT)
    df["file_name"] = "Ha Noi"
    return df


def process_hcm(df):
    rename_map = {**COMMON_RENAME, **HCM_EXTRA_RENAME}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["real_pay_vnd"] = clean_vnd(df["real_pay_vnd"])
    df["Team"] = "HCM team"
    df["file_name"] = "Ho Chi Minh"
    return df


def process_danang(df):
    rename_map = {**COMMON_RENAME, **DANANG_EXTRA_RENAME}
    df = df.rename(columns={k: v for k, v in rename_map.items() if k in df.columns})
    df["real_pay_vnd"] = clean_vnd(df["real_pay_vnd"])
    df["Team"] = "Danang team"
    df["file_name"] = "Da Nang"
    return df


def merge_sources():
    print("=" * 50)
    print("STEP 0 — Tai & ghep 3 file tu Google Sheets -> GMV.csv")
    print("=" * 50)
    raw_hanoi  = download_sheet(SHEET_ID, GID_HANOI,  "SM Hanoi")
    raw_hcm    = download_sheet(SHEET_ID, GID_HCM,    "HCM REV")
    raw_danang = download_sheet(SHEET_ID, GID_DANANG, "Danang REV")
    df_hanoi  = process_hanoi(raw_hanoi)
    df_hcm    = process_hcm(raw_hcm)
    df_danang = process_danang(raw_danang)
    print(f"\n  Hanoi: {len(df_hanoi):,} | HCM: {len(df_hcm):,} | Danang: {len(df_danang):,}")
    df = pd.concat([df_hanoi, df_hcm, df_danang], ignore_index=True)
    print(f"  Tong: {len(df):,} hang")

    REQUIRED_COLS = [
        "no", "bank_id", "bank_day", "bank_time", "gateway", "user_name", "phone",
        "uid", "package", "fixed_non_fixed", "pay_time", "full_price_vnd",
        "real_pay_vnd", "gmv_rmb", "payment_method", "type", "sales", "note",
        "total_b_lessons", "a_referrer_ph_lessons", "a_uk", "unit_price_vnd",
        "rmb", "platform_type", "purchase_price_total", "month_of_payment",
        "source_1", "note_1", "file_name", "fixed", "package_1",
        "channel", "Sale_name", "Team", "Month",
    ]
    for col in REQUIRED_COLS:
        if col not in df.columns:
            df[col] = None
    df = df[REQUIRED_COLS]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_PATH, index=False)
    print(f"\nOK Da luu: {OUTPUT_PATH}")


if __name__ == "__main__":
    merge_sources()
