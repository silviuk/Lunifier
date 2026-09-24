@echo off
if exist "%~dp0dist\windows\Lunifier.exe" (
    start "" "%~dp0dist\windows\Lunifier.exe" --minimized
) else if exist "%~dp0dist\windows\Lunifier.Windows.exe" (
    start "" "%~dp0dist\windows\Lunifier.Windows.exe" --minimized
) else (
    call "%~dp0run_gui.bat"
)
