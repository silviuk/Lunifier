@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo  Lunifier Windows Installer & Package Builder
echo ===================================================

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."
set "VERSION=1.0.5"

echo [1/3] Compiling Python Application with PyInstaller...
cd /d "%ROOT_DIR%"
python -m PyInstaller Lunifier.spec --clean --noconfirm
if errorlevel 1 (
    echo [ERROR] PyInstaller build failed!
    exit /b 1
)

echo [2/3] Compiling Inno Setup Installer...
set "ISCC="
if exist "%LocalAppData%\Programs\Inno Setup 6\ISCC.exe" set "ISCC=%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files\Inno Setup 6\ISCC.exe"
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" set "ISCC=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"

if "%ISCC%"=="" (
    echo [ERROR] Inno Setup compiler (ISCC.exe) not found.
    exit /b 1
)

"%ISCC%" "%SCRIPT_DIR%installer.iss"
if errorlevel 1 (
    echo [ERROR] Inno Setup compilation failed!
    exit /b 1
)

echo [3/3] Creating Portable Windows ZIP...
powershell -NoProfile -Command ^
    "Compress-Archive -Path '%ROOT_DIR%\dist\Lunifier\*' -DestinationPath '%ROOT_DIR%\dist\Lunifier-Windows-%VERSION%.zip' -Force"

powershell -NoProfile -Command ^
    "$hash = (Get-FileHash '%ROOT_DIR%\dist\Lunifier-Setup-%VERSION%.exe' -Algorithm SHA256).Hash; Write-Host ' [OK] Lunifier-Setup-%VERSION%.exe SHA256:' $hash"

echo ===================================================
echo  Windows Packaging Complete!
echo  Output: %ROOT_DIR%\dist\Lunifier-Setup-%VERSION%.exe
echo ===================================================
