# -*- coding: utf-8 -*-
"""
DA-RE — Tu dong tai REM.csv tu Metabase (card/question 14393).
Sao chep co che tu du an "Order 1 - Order 2".
Luong: login /api/session lay token -> POST /api/card/{id}/query/csv -> luu REM.csv
KHONG can VPN neu may da o trong mang noi bo / metabase truy cap duoc truc tiep.
"""
import requests
from pathlib import Path

# --- CAU HINH TAI KHOAN VA METABASE ---
METABASE_URL = "https://metabase.ibanyu.com"
USERNAME = "hoanghieuw00617@ipalfish.com"
PASSWORD = "Sumo@9919"
QUESTION_ID_REMAIN = 14393

# --- CAU HINH DUONG DAN LUU FILE ---
BASE_DIR = Path(__file__).resolve().parent.parent   # ...\DA-RE
INPUT_DIR = BASE_DIR / "Data_input"
OUTPUT_FILE = INPUT_DIR / "REM.csv"

INPUT_DIR.mkdir(parents=True, exist_ok=True)


def download_metabase_api():
    print("Bat dau tai REM tu Metabase...")
    session = requests.Session()

    # BUOC 1: Lay session token
    session_url = f"{METABASE_URL}/api/session"
    login_payload = {"username": USERNAME, "password": PASSWORD}
    print("Dang dang nhap Metabase...")
    try:
        session_response = session.post(session_url, json=login_payload, timeout=60)
        session_response.raise_for_status()
        session_token = session_response.json().get("id")
        session.headers.update({"X-Metabase-Session": session_token})
        print("Dang nhap thanh cong.")
    except Exception as e:
        print(f"X Loi dang nhap. Kiem tra Username/Password / VPN. Chi tiet: {e}")
        return

    # BUOC 2: Tai CSV
    print(f"Dang tai du lieu card {QUESTION_ID_REMAIN}...")
    csv_url = f"{METABASE_URL}/api/card/{QUESTION_ID_REMAIN}/query/csv"
    try:
        csv_response = session.post(csv_url, timeout=None)
        csv_response.raise_for_status()
        with open(OUTPUT_FILE, "wb") as f:
            f.write(csv_response.content)
        print(f"OK Da luu: {OUTPUT_FILE}")
    except Exception as e:
        print(f"X Loi khi tai CSV. Chi tiet: {e}")


if __name__ == "__main__":
    download_metabase_api()
