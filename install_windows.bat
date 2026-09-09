@echo off
setlocal
cd /d "%~dp0"
echo ===========================================
echo         Lunifier Windows Installer
echo ===========================================
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install_windows.ps1"
echo.
pause
