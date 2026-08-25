$ErrorActionPreference = 'Stop'

$serviceName = 'GMedPrinterService'

Write-Host "Stopping service: $serviceName"
try {
    & sc.exe stop $serviceName | Out-Null
} catch {
    Write-Host "Service was already stopped or not running."
}

Write-Host "Deleting service: $serviceName"
try {
    & sc.exe delete $serviceName | Out-Null
} catch {
    Write-Host "Service delete returned a non-fatal error; continuing."
}

Write-Host "Uninstall completed."
Write-Host "The Windows service '$serviceName' should no longer be present in Services."
