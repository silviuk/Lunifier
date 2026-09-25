# PowerShell script to build compliant MSIX package for Windows Store submission
param (
    [string]$Version = "2.2.1.0",
    [string]$DistDir = "$PSScriptRoot\..\dist",
    [string]$SourceAppDir = "$PSScriptRoot\..\dist\windows",
    [string]$ManifestPath = "$PSScriptRoot\..\packaging\msix\AppxManifest.xml",
    [string]$IconPath = "$PSScriptRoot\..\src\windows\Lunifier.Windows\Resources\icon.png",
    [string]$OutputName = "",
    [switch]$NoBtSync
)

$ErrorActionPreference = "Stop"

$isNoBtSync = $NoBtSync -or ($SourceAppDir -match "nobtsync") -or ($OutputName -match "nobtsync")
$editionName = if ($isNoBtSync) { "No-BtSync Edition" } else { "Standard Edition" }

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host " Building Lunifier MSIX Package ($editionName $Version) " -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Cyan

if (-not (Test-Path $SourceAppDir)) {
    Write-Error "Source application directory not found: $SourceAppDir. Please compile the app first."
}

$StagingDir = Join-Path $DistDir "msix_staging"
if (Test-Path $StagingDir) {
    Remove-Item -Path $StagingDir -Recurse -Force
}
New-Item -ItemType Directory -Path $StagingDir | Out-Null
$AssetsDir = Join-Path $StagingDir "Assets"
New-Item -ItemType Directory -Path $AssetsDir | Out-Null
$AppDir = Join-Path $StagingDir "Lunifier"
New-Item -ItemType Directory -Path $AppDir | Out-Null

# 1. Copy Application Binaries
Write-Host "[1/4] Copying application binaries to staging layout..." -ForegroundColor Yellow
Copy-Item -Path "$SourceAppDir\*" -Destination $AppDir -Recurse -Force
Get-ChildItem -Path $AppDir -Filter "*.pdb" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force
Get-ChildItem -Path $AppDir -Filter ".DS_Store" -Recurse -ErrorAction SilentlyContinue | Remove-Item -Force

# 2. Copy and Update AppxManifest.xml
Write-Host "[2/4] Preparing AppxManifest.xml..." -ForegroundColor Yellow
$manifestContent = Get-Content $ManifestPath -Raw

# Strictly replace Version only within the Identity element to preserve <?xml version="1.0"?> and MinVersion
$manifestContent = [System.Text.RegularExpressions.Regex]::Replace($manifestContent, '(<Identity\b[^>]*?\bVersion=")[^"]+(")', "`${1}$Version`${2}")

if ($isNoBtSync) {
    $manifestContent = [System.Text.RegularExpressions.Regex]::Replace($manifestContent, '(<Identity\b[^>]*?\bName=")[^"]+(")', "`${1}SilviuVlasceanu.LunifierNoBtSync`${2}")
    $manifestContent = $manifestContent -replace '<DisplayName>Lunifier</DisplayName>', '<DisplayName>Lunifier (No-BtSync Edition)</DisplayName>'
    $manifestContent = $manifestContent -replace '<Description>Seamless multi-border screen switching for Logitech Easy-Switch keyboards and mice across Windows &amp; Linux.</Description>', '<Description>Seamless multi-border screen switching for Logitech Easy-Switch keyboards and mice without Bluetooth RFCOMM sync.</Description>'
}

Set-Content -Path (Join-Path $StagingDir "AppxManifest.xml") -Value $manifestContent -Encoding UTF8

# 3. Generate Visual Assets with Python PIL (including High-DPI scale variants)
Write-Host "[3/4] Generating Store and Visual Tile Assets (including High-DPI scale variants)..." -ForegroundColor Yellow
python -c "
from PIL import Image
import os

src = r'$IconPath'
out_dir = r'$AssetsDir'

img = Image.open(src).convert('RGBA')

# Base and scale variants required for Windows Store certification
sizes = {
    'Square44x44Logo.png': (44, 44),
    'Square44x44Logo.scale-100.png': (44, 44),
    'Square44x44Logo.scale-200.png': (88, 88),
    'Square44x44Logo.targetsize-44.png': (44, 44),
    'Square44x44Logo.targetsize-24.png': (24, 24),
    'Square150x150Logo.png': (150, 150),
    'Square150x150Logo.scale-100.png': (150, 150),
    'Square150x150Logo.scale-200.png': (300, 300),
    'StoreLogo.png': (50, 50),
    'StoreLogo.scale-100.png': (50, 50),
    'StoreLogo.scale-200.png': (100, 100),
}

for name, sz in sizes.items():
    resized = img.resize(sz, Image.Resampling.LANCZOS)
    resized.save(os.path.join(out_dir, name))

# Wide tile variants
wide_sizes = {
    'Wide310x150Logo.png': (310, 150, 120),
    'Wide310x150Logo.scale-100.png': (310, 150, 120),
    'Wide310x150Logo.scale-200.png': (620, 300, 240)
}

for name, (w, h, icon_sz) in wide_sizes.items():
    wide = Image.new('RGBA', (w, h), (0, 0, 0, 0))
    scaled = img.resize((icon_sz, icon_sz), Image.Resampling.LANCZOS)
    wide.paste(scaled, ((w - icon_sz) // 2, (h - icon_sz) // 2), scaled)
    wide.save(os.path.join(out_dir, name))

print('Store assets generated successfully.')
"

# 4. Locate official Microsoft MakeAppx.exe Tool
Write-Host "[4/4] Locating MakeAppx.exe and creating OPC-compliant MSIX Package..." -ForegroundColor Yellow

$cmd = Get-Command makeappx -ErrorAction SilentlyContinue
$cmdSource = if ($cmd) { $cmd.Source } else { $null }

$makeAppxCandidates = @(
    (Get-ChildItem -Path "$env:LocalAppData\Microsoft\WinGet\Packages" -Filter "MakeAppx.exe" -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1 -ExpandProperty FullName),
    (Get-ChildItem -Path "C:\Program Files (x86)\Windows Kits", "C:\Program Files\Windows Kits" -Filter "makeappx.exe" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -like "*x64*" } | Select-Object -First 1 -ExpandProperty FullName),
    $cmdSource
)

$MakeAppx = $null
foreach ($cand in $makeAppxCandidates) {
    if ($cand -and (Test-Path $cand)) {
        $MakeAppx = $cand
        break
    }
}

if (-not $MakeAppx) {
    Write-Error "MakeAppx.exe not found! Genuine MSIX packages for Windows Store submission require MakeAppx.exe to generate AppxBlockMap.xml and [Content_Types].xml. Please install Microsoft.MSIX-Toolkit or Windows SDK."
    exit 1
}

$defaultFile = if ($isNoBtSync) { "Lunifier-$Version-nobtsync.msix" } else { "Lunifier-$Version.msix" }
$OutputFile = if ($OutputName) { Join-Path $DistDir $OutputName } else { Join-Path $DistDir $defaultFile }
if (Test-Path $OutputFile) {
    Remove-Item $OutputFile -Force
}

Write-Host "Using MakeAppx: $MakeAppx" -ForegroundColor Green
& "$MakeAppx" pack /d "$StagingDir" /p "$OutputFile" /o
if ($LASTEXITCODE -ne 0) {
    Write-Error "MakeAppx failed to package MSIX!"
    exit 1
}

$Sha = (Get-FileHash $OutputFile -Algorithm SHA256).Hash
Write-Host "===================================================" -ForegroundColor Green
Write-Host " [OK] MSIX Package created: $OutputFile" -ForegroundColor Green
Write-Host " SHA256: $Sha" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
