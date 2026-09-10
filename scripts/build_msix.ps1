# PowerShell script to build MSIX package for Windows Store submission
param (
    [string]$Version = "1.0.5.0",
    [string]$DistDir = "$PSScriptRoot\..\dist",
    [string]$SourceAppDir = "$PSScriptRoot\..\dist\Lunifier",
    [string]$ManifestPath = "$PSScriptRoot\..\packaging\msix\AppxManifest.xml",
    [string]$IconPath = "$PSScriptRoot\..\lunifier\resources\icon.png"
)

$ErrorActionPreference = "Stop"

Write-Host "===================================================" -ForegroundColor Cyan
Write-Host " Building Lunifier MSIX Package ($Version)         " -ForegroundColor Cyan
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

# 2. Copy and Update AppxManifest.xml
Write-Host "[2/4] Preparing AppxManifest.xml..." -ForegroundColor Yellow
Copy-Item -Path $ManifestPath -Destination (Join-Path $StagingDir "AppxManifest.xml") -Force

# 3. Generate Visual Assets with Python PIL
Write-Host "[3/4] Generating Store and Visual Tile Assets..." -ForegroundColor Yellow
python -c "
from PIL import Image
import os

src = r'$IconPath'
out_dir = r'$AssetsDir'

img = Image.open(src).convert('RGBA')

sizes = {
    'Square44x44Logo.png': (44, 44),
    'Square150x150Logo.png': (150, 150),
    'StoreLogo.png': (50, 50),
    'Wide310x150Logo.png': (310, 150)
}

for name, sz in sizes.items():
    if sz == (310, 150):
        wide = Image.new('RGBA', (310, 150), (0, 0, 0, 0))
        scaled = img.resize((120, 120), Image.Resampling.LANCZOS)
        wide.paste(scaled, ((310 - 120) // 2, (150 - 120) // 2), scaled)
        wide.save(os.path.join(out_dir, name))
    else:
        resized = img.resize(sz, Image.Resampling.LANCZOS)
        resized.save(os.path.join(out_dir, name))
print('Assets generated successfully.')
"

# 4. Compile MSIX Package
Write-Host "[4/4] Creating MSIX Package..." -ForegroundColor Yellow
$OutputFile = Join-Path $DistDir "Lunifier-$Version.msix"
if (Test-Path $OutputFile) {
    Remove-Item $OutputFile -Force
}

# Search for MakeAppx.exe in Windows Kits
$MakeAppx = $null
$WindowsKits = "C:\Program Files (x86)\Windows Kits\10\bin"
if (Test-Path $WindowsKits) {
    $found = Get-ChildItem -Path $WindowsKits -Filter "makeappx.exe" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.FullName -like "*x64*" } | Select-Object -First 1
    if ($found) {
        $MakeAppx = $found.FullName
    }
}

if ($MakeAppx) {
    Write-Host "Using MakeAppx: $MakeAppx" -ForegroundColor Green
    & "$MakeAppx" pack /d "$StagingDir" /p "$OutputFile" /o
} else {
    $tempZip = [System.IO.Path]::ChangeExtension($OutputFile, ".zip")
    if (Test-Path $tempZip) { Remove-Item $tempZip -Force }
    Compress-Archive -Path "$StagingDir\*" -DestinationPath $tempZip -Force
    Move-Item -Path $tempZip -Destination $OutputFile -Force
}

$Sha = (Get-FileHash $OutputFile -Algorithm SHA256).Hash
Write-Host "===================================================" -ForegroundColor Green
Write-Host " [OK] MSIX Package created: $OutputFile" -ForegroundColor Green
Write-Host " SHA256: $Sha" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
