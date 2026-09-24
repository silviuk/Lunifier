param (
    [string]$version = "2.2.0",
    [switch]$NoBtSync
)
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$rootDir = (Get-Item $scriptDir).Parent.FullName
$distDir = Join-Path $rootDir "dist"
$targetDirName = if ($NoBtSync) { "windows-nobtsync" } else { "windows" }
$distWindowsDir = Join-Path $distDir $targetDirName
$editionName = if ($NoBtSync) { "No-BtSync Edition" } else { "Standard Edition" }
$fileSuffix = if ($NoBtSync) { "-nobtsync" } else { "" }

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Lunifier Windows Package Builder ($editionName)" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

# 1. Build and Publish Native .NET 9 Binary
Write-Host "[1/3] Building & Publishing Native .NET 9 Binary..." -ForegroundColor Yellow
$localDotnet = Join-Path $env:LocalAppData "Microsoft\dotnet\dotnet.exe"
if (Test-Path $localDotnet) {
    $dotnetExe = $localDotnet
    $env:DOTNET_ROOT = Join-Path $env:LocalAppData "Microsoft\dotnet"
    $env:PATH = "$env:DOTNET_ROOT;$env:PATH"
} else {
    $dotnetExe = "dotnet"
}

$csprojPath = Join-Path $rootDir "src\windows\Lunifier.Windows\Lunifier.Windows.csproj"
$buildArgs = @("publish", "-c", "Release", $csprojPath, "-r", "win-x64", "--self-contained", "false", "-p:PublishSingleFile=true", "-o", $distWindowsDir)
if ($NoBtSync) {
    $buildArgs += "-p:DefineConstants=NO_BTSYNC"
}
& $dotnetExe @buildArgs
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] dotnet publish failed with exit code $LASTEXITCODE" -ForegroundColor Red
    exit 1
}

# 2. Compile Inno Setup Installer
Write-Host "[2/3] Compiling Inno Setup Installer..." -ForegroundColor Yellow
$isccCandidates = @(
    "$env:LocalAppData\Programs\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$isccExe = $null
foreach ($cand in $isccCandidates) {
    if (Test-Path $cand) {
        $isccExe = $cand
        break
    }
}

if (-not $isccExe) {
    Write-Host "[ERROR] Inno Setup compiler (ISCC.exe) not found." -ForegroundColor Red
    exit 1
}

$issPath = Join-Path $scriptDir "installer.iss"
$outBase = "Lunifier-Setup-$version$fileSuffix"
& $isccExe "/DMyAppVersion=$version" "/DOutputBaseFilename=$outBase" "/DSourceDir=$distWindowsDir" $issPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Inno Setup compilation failed!" -ForegroundColor Red
    exit 1
}

# 3. Create Portable ZIP
Write-Host "[3/3] Creating Portable Windows ZIP..." -ForegroundColor Yellow
$zipOutput = Join-Path $distDir "Lunifier-Windows-$version$fileSuffix.zip"
if (Test-Path $zipOutput) { Remove-Item $zipOutput -Force }
Get-ChildItem -Path $distWindowsDir -Filter "*.pdb" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force
Compress-Archive -Path "$distWindowsDir\*" -DestinationPath $zipOutput -Force

$installerExe = Join-Path $distDir "Lunifier-Setup-$version$fileSuffix.exe"
$installerHash = (Get-FileHash $installerExe -Algorithm SHA256).Hash
$zipHash = (Get-FileHash $zipOutput -Algorithm SHA256).Hash

Write-Host " [OK] Lunifier-Setup-$version$fileSuffix.exe SHA256: $installerHash" -ForegroundColor Green
Write-Host " [OK] Lunifier-Windows-$version$fileSuffix.zip SHA256: $zipHash" -ForegroundColor Green

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "  Windows Packaging Complete ($editionName)!" -ForegroundColor Green
Write-Host "  Installer: $installerExe"
Write-Host "  Portable:  $zipOutput"
Write-Host "===================================================" -ForegroundColor Cyan
