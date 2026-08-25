$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serviceName = 'GMedPrinterService'
$exeName = 'GMedPrinterService.exe'
$distDir = Join-Path $scriptDir 'dist'
$exePath = Join-Path $distDir $exeName
$configPath = Join-Path $scriptDir 'config.json'

if (-not (Test-Path $configPath)) {
    Write-Error "config.json not found at $configPath. Copy the clinic config and rerun."
    exit 1
}

if (-not (Get-Command py -ErrorAction SilentlyContinue) -and -not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Error 'Python 3.10+ is not installed or not on PATH. Install Python and rerun.'
    exit 1
}

$pythonCmd = if (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }

Write-Host 'Installing local printer service dependencies...'
& $pythonCmd -m pip install --upgrade pip
& $pythonCmd -m pip install requests pywin32 pyinstaller

Write-Host 'Building Windows service executable...'
$workDir = Join-Path $scriptDir '__pyinstaller__'
$specDir = Join-Path $scriptDir '__pyinstaller__'
& $pythonCmd -m PyInstaller --onefile --name $exeName --noconsole --distpath $distDir --workpath $workDir --specpath $specDir (Join-Path $scriptDir 'windows_service.py')

if (-not (Test-Path $exePath)) {
    Write-Error "Build failed: $exePath was not created."
    exit 1
}

$distConfigPath = Join-Path $distDir 'config.json'
if (Test-Path $configPath) {
    Copy-Item $configPath $distConfigPath -Force
}

$serviceExists = Get-CimInstance Win32_Service -Filter "Name = '$serviceName'" -ErrorAction SilentlyContinue
if ($serviceExists) {
    Write-Host "Removing existing service: $serviceName"
    & sc.exe stop $serviceName | Out-Null
    & sc.exe delete $serviceName | Out-Null
}

$binPath = '"' + $exePath + '"'
Write-Host "Registering Windows service: $serviceName"
& sc.exe create $serviceName binPath= $binPath start= auto obj= LocalSystem DisplayName= "G-MED Printer Service" | Out-Null
& sc.exe description $serviceName "Local Windows printer polling service for G-MED queue tickets" | Out-Null

Write-Host 'Starting service...'
& sc.exe start $serviceName | Out-Null

Write-Host 'Installation finished.'
Write-Host "Service Name : $serviceName"
Write-Host "Executable   : $exePath"
Write-Host "Config File : $configPath"
Write-Host 'Use the printed token from the reception dashboard in config.json as device_token.'
Write-Host 'If the service exits immediately, run the EXE manually to inspect errors.'
