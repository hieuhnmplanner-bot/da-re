@echo off
chcp 65001 >nul
REM ====== DA-RE — CHAY DAU THANG (chay SAU run_daily.bat) ======
cd /d "%~dp0"
set /p M="Nhap thang can tao danh sach (vd 2026-08): "
echo [1/3] Sinh danh sach HET HAN thang %M% (co dedup)...
python "Script\monthly_expiry.py" %M%        || goto err
echo [2/3] Trang thai gia han (den han) + CRR/RRR/Upsell...
python "Script\expiry_renewal_check.py" "Output\expiry_%M%.csv" || goto err
echo [3/3] Nhom GIA HAN SOM thang %M%...
python "Script\early_renewal.py" %M%          || goto err
python "Script\mid_month_expiry.py" %M%       || goto err
python "Script\dormant.py"
git add -A
git commit -m "monthly list %M%"
git push
echo === XONG === Danh sach thang %M% da tao + day len GitHub.
pause
exit /b 0
:err
echo X Loi - xem thong bao phia tren.
pause
exit /b 1
