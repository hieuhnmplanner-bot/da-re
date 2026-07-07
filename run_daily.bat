@echo off
chcp 65001 >nul
REM ====== DA-RE — CHAY HANG NGAY (sau khi da ket noi VPN) ======
cd /d "%~dp0"
echo [1/5] Tai REM (Metabase) + GMV (Google Sheet)...
python "Script\Step0_1_rem_collect.py"  || goto err
python "Script\Step0_gmv_collect.py"     || goto err
echo [2/5] Ghep GMV x REM...
python "Script\step3_match.py"           || goto err
echo [3/5] Ghi log thay doi hang ngay (QUAN TRONG)...
python "Script\daily_snapshot.py"        || goto err
echo [4/5] Cap nhat trang thai DEN HAN (tu so) cho cac thang da co list...
for %%f in (Output\expiry_20??-??.csv) do python "Script\expiry_renewal_check.py" "%%f"
echo [5/5] Ngu dong / roi bo...
python "Script\dormant.py"
REM Mo hinh moi: BO early_renewal + mid_month_expiry khoi mau so.
echo === Day len GitHub (Streamlit tu cap nhat) ===
git add -A
git commit -m "daily update %date%"
git push
echo === XONG ===
pause
exit /b 0
:err
echo X Loi o buoc tren - kiem tra VPN / dang nhap Metabase / mang.
pause
exit /b 1
