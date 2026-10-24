@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
    py -3 "%~dp0fileshare.py" %*
) else (
    python "%~dp0fileshare.py" %*
)
echo.
pause
