# Lunifier Windows Installer & Shortcut Setup Script
param (
    [switch]$AddToStartup = $false
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$sourceDir = Join-Path $scriptDir "Lunifier"
if (-not (Test-Path $sourceDir)) {
    $sourceDir = $scriptDir
}

$exeCandidates = @(
    Join-Path $scriptDir "dist\windows\Lunifier.Windows.exe",
    Join-Path $sourceDir "Lunifier.Windows.exe",
    Join-Path $sourceDir "Lunifier.exe"
)
$exePath = $null
foreach ($cand in $exeCandidates) {
    if (Test-Path $cand) {
        $exePath = $cand
        break
    }
}
if (-not $exePath) {
    Write-Host "[ERROR] Could not locate Lunifier binary in dist\windows or root." -ForegroundColor Red
    exit 1
}

# Install target directory: %LOCALAPPDATA%\Programs\Lunifier
$installDir = Join-Path $env:LOCALAPPDATA "Programs\Lunifier"
Write-Host "Installing Lunifier to: $installDir" -ForegroundColor Cyan
New-Item -ItemType Directory -Force -Path $installDir | Out-Null

Copy-Item -Path "$sourceDir\*" -Destination $installDir -Recurse -Force
$installedExe = Join-Path $installDir "Lunifier.exe"

# Create WScript.Shell COM object for shortcuts
$wshShell = New-Object -ComObject WScript.Shell

# 1. Start Menu Shortcut
$startMenuDir = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Lunifier"
New-Item -ItemType Directory -Force -Path $startMenuDir | Out-Null
$startMenuShortcut = $wshShell.CreateShortcut((Join-Path $startMenuDir "Lunifier.lnk"))
$startMenuShortcut.TargetPath = $installedExe
$startMenuShortcut.WorkingDirectory = $installDir
$startMenuShortcut.Description = "Lunifier - Logitech Easy-Switch Screen Flow"
$startMenuShortcut.Save()
Write-Host " [OK] Created Start Menu shortcut" -ForegroundColor Green

# 2. Desktop Shortcut
$desktopPath = [System.Environment]::GetFolderPath("Desktop")
$desktopShortcut = $wshShell.CreateShortcut((Join-Path $desktopPath "Lunifier.lnk"))
$desktopShortcut.TargetPath = $installedExe
$desktopShortcut.WorkingDirectory = $installDir
$desktopShortcut.Description = "Lunifier - Logitech Easy-Switch Screen Flow"
$desktopShortcut.Save()
Write-Host " [OK] Created Desktop shortcut" -ForegroundColor Green

# 3. Optional Autostart on boot (daemon mode)
if ($AddToStartup) {
    $startupDir = [System.Environment]::GetFolderPath("Startup")
    $startupShortcut = $wshShell.CreateShortcut((Join-Path $startupDir "Lunifier Daemon.lnk"))
    $startupShortcut.TargetPath = $installedExe
    $startupShortcut.Arguments = "--daemon"
    $startupShortcut.WorkingDirectory = $installDir
    $startupShortcut.WindowStyle = 7 # Minimized
    $startupShortcut.Description = "Lunifier Background Flow Daemon"
    $startupShortcut.Save()
    Write-Host " [OK] Added Lunifier Daemon to Windows Startup" -ForegroundColor Green
}

Write-Host "`n=== Lunifier Installation Complete! ===" -ForegroundColor Green
Write-Host "You can now launch Lunifier from your Desktop or Start Menu."
