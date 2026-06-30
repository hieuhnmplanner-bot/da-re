@echo off
chcp 65001 >nul
REM ============================================================
REM  DA-RE — Tai tu dong GMV.csv + REM.csv vao Data_input
REM ============================================================
cd /d "%~dp0"

echo.
echo [1/2] Tai REM.csv tu Metabase (card 14393)...
python "Script\Step0_1_rem_collect.py" > "fetch_log.txt" 2>&1
type "fetch_log.txt"

echo.
echo [2/2] Tai GMV.csv tu Google Sheets (3 mien)...
python "Script\Step0_gmv_collect.py" >> "fetch_log.txt" 2>&1

echo.
echo === XONG === Kiem tra Data_input + fetch_log.txt
pause
exit /b 0
