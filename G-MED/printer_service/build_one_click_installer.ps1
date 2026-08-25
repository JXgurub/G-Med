$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }

$distDir = Join-Path $scriptDir 'dist_installer'
$buildDir = Join-Path $scriptDir 'build_installer'
$serviceDistDir = Join-Path $scriptDir 'service_build_dist'
$serviceBuildDir = Join-Path $scriptDir 'service_build'

if (Get-Process -Name 'GMedPrinterInstaller' -ErrorAction SilentlyContinue) {
    Stop-Process -Name 'GMedPrinterInstaller' -Force -ErrorAction SilentlyContinue
}

if (Test-Path $distDir) {
    try {
        Remove-Item $distDir -Recurse -Force
    }
    catch {
        Write-Warning "dist_installer lock not released yet. Retrying after close..."
        Start-Sleep -Seconds 2
        Remove-Item $distDir -Recurse -Force -ErrorAction Stop
    }
}
if (Test-Path $buildDir) {
    try {
        Remove-Item $buildDir -Recurse -Force
    }
    catch {
        Write-Warning "build_installer lock not released yet. Retrying after close..."
        Start-Sleep -Seconds 2
        Remove-Item $buildDir -Recurse -Force -ErrorAction Stop
    }
}
if (Test-Path $serviceDistDir) { Remove-Item $serviceDistDir -Recurse -Force }
if (Test-Path $serviceBuildDir) { Remove-Item $serviceBuildDir -Recurse -Force }

Write-Host 'Ensuring PyInstaller is installed...'
& $pythonCmd -m pip install --upgrade pyinstaller

Write-Host 'Building the Windows printer service executable...'
& $pythonCmd -m PyInstaller --onefile --noconsole --name GMedPrinterService `
    --hidden-import win32event `
    --hidden-import win32service `
    --hidden-import win32serviceutil `
    --hidden-import servicemanager `
    --hidden-import win32timezone `
    --hidden-import pywintypes `
    --hidden-import pythoncom `
    --hidden-import win32api `
    --hidden-import win32con `
    --collect-submodules win32 `
    --distpath $serviceDistDir --workpath $serviceBuildDir --specpath $serviceBuildDir `
    --add-data "$(Join-Path $scriptDir 'printer_service.py')$([IO.Path]::PathSeparator)." `
    (Join-Path $scriptDir 'windows_service.py')

if (-not (Test-Path (Join-Path $serviceDistDir 'GMedPrinterService.exe'))) {
    throw 'GMedPrinterService.exe build failed.'
}

& $pythonCmd -m PyInstaller --onefile --windowed --name GMedPrinterInstaller --distpath $distDir --workpath $buildDir --specpath $buildDir `
    --hidden-import win32service `
    --hidden-import win32serviceutil `
    --hidden-import win32api `
    --hidden-import win32con `
    --hidden-import pywintypes `
    --hidden-import pythoncom `
    --hidden-import servicemanager `
    --add-data "$(Join-Path $scriptDir 'windows_service.py')$([IO.Path]::PathSeparator)." `
    --add-data "$(Join-Path $scriptDir 'printer_service.py')$([IO.Path]::PathSeparator)." `
    --add-data "$(Join-Path $serviceDistDir 'GMedPrinterService.exe')$([IO.Path]::PathSeparator)." `
    (Join-Path $scriptDir 'one_click_installer.py')

Write-Host 'One-click installer built successfully.'
Write-Host 'Use the generated EXE in dist_installer and copy the whole printer_service folder to the clinic PC.'
