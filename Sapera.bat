@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
    py -3 -m sapera wizard
) else (
    python -m sapera wizard
)
echo.
echo Press any key to close this window.
pause >nul
