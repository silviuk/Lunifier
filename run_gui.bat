@echo off
if exist "%~dp0dist\windows\Lunifier.exe" (
    start "" "%~dp0dist\windows\Lunifier.exe"
) else if exist "%~dp0dist\windows\Lunifier.Windows.exe" (
    start "" "%~dp0dist\windows\Lunifier.Windows.exe"
) else (
    echo Building Lunifier native Windows binary...
    where dotnet >nul 2>nul
    if %errorlevel% neq 0 (
        if exist "%LocalAppData%\Microsoft\dotnet\dotnet.exe" (
            set "PATH=%LocalAppData%\Microsoft\dotnet;%PATH%"
        )
    )
    dotnet build -c Release "%~dp0src\windows\Lunifier.sln"
    start "" "%~dp0src\windows\Lunifier.Windows\bin\Release\net9.0-windows10.0.19041.0\win-x64\Lunifier.exe"
)
