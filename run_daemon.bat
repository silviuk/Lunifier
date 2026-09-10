@echo off
if exist "%~dp0dist\windows\Lunifier.Windows.exe" (
    start "" "%~dp0dist\windows\Lunifier.Windows.exe"
) else (
    call "%~dp0run_gui.bat"
)
