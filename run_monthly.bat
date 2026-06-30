@echo off
chcp 65001 >nul
REM ====== DA-RE — CHAY DAU THANG (chay SAU run_daily.bat) ======
cd /d "%~dp0"
set /p M="Nhap thang can tao danh sach (vd 2026-08): "
echo [1/3] Sinh danh sach het han thang %M% (co dedup)...
python "Script\monthly_expiry.py" %M%        || goto err
echo [2/3] Tong hop quy mo tinh huong...
python "Script\situation_summary.py" %M%     || goto err
echo [3/3] Cap nhat trang thai gia han + CRR/RRR/Upsell...
python "Script\expiry_renewal_check.py" "Output\expiry_%M%.csv" || goto err
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
