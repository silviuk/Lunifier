@echo off
echo === Lunifier 2.0 Native Windows Setup ===

where dotnet >nul 2>nul
if %errorlevel% neq 0 (
    if exist "%LocalAppData%\Microsoft\dotnet\dotnet.exe" (
        set "PATH=%LocalAppData%\Microsoft\dotnet;%PATH%"
    ) else (
        echo [.NET SDK not found on PATH. Installing .NET 9 SDK via winget...]
        winget install Microsoft.DotNet.SDK.9 --silent --accept-package-agreements --accept-source-agreements
        set "PATH=%LocalAppData%\Microsoft\dotnet;%ProgramFiles%\dotnet;%PATH%"
    )
)

echo [1/2] Building Lunifier 2.0 Native Solution (.NET 9)...
dotnet build -c Release "%~dp0src\windows\Lunifier.sln"

echo [2/2] Publishing standalone native executable to dist\windows\...
dotnet publish -c Release "%~dp0src\windows\Lunifier.Windows\Lunifier.Windows.csproj" -r win-x64 --self-contained false -p:PublishSingleFile=true -o "%~dp0dist\windows"

echo.
echo === Setup Complete! ===
echo Output Binary: %~dp0dist\windows\Lunifier.Windows.exe
echo Run GUI:       run_gui.bat
echo.
pause
