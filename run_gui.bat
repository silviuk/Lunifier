@echo off
if exist "%~dp0dist\windows\Lunifier.Windows.exe" (
    start "" "%~dp0dist\windows\Lunifier.Windows.exe"
) else if exist "%~dp0src\windows\Lunifier.Windows\bin\Release\net9.0-windows\Lunifier.Windows.exe" (
    start "" "%~dp0src\windows\Lunifier.Windows\bin\Release\net9.0-windows\Lunifier.Windows.exe"
) else if exist "%~dp0src\windows\Lunifier.Windows\bin\Debug\net9.0-windows\Lunifier.Windows.exe" (
    start "" "%~dp0src\windows\Lunifier.Windows\bin\Debug\net9.0-windows\Lunifier.Windows.exe"
) else (
    echo Building Lunifier 2.0 native Windows binary...
    dotnet build -c Release "%~dp0src\windows\Lunifier.sln"
    start "" "%~dp0src\windows\Lunifier.Windows\bin\Release\net9.0-windows\Lunifier.Windows.exe"
)
