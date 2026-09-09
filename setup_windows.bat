@echo off
echo === Lunifier Windows Setup ===

echo [1/2] Installing required Python dependencies...
python -m pip install --upgrade hidapi bleak customtkinter

echo [2/2] Testing Logitech device detection...
python -m lunifier.app --scan

echo.
echo === Setup Complete! ===
echo To run settings GUI:      python -m lunifier.app --gui
echo To run daemon in console: python -m lunifier.app --daemon
pause
