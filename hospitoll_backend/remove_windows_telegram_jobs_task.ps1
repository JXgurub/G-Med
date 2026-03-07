$ErrorActionPreference = 'Stop'

$taskName = 'HospitollTelegramJobs'

try {
  Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
} catch {}

try {
  Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop
  Write-Host "Removed scheduled task: $taskName" -ForegroundColor Green
} catch {
  try {
    schtasks.exe /Delete /TN $taskName /F 2>$null | Out-Null
    Write-Host "Removed scheduled task: $taskName" -ForegroundColor Green
  } catch {
    Write-Host "Task not found: $taskName" -ForegroundColor Yellow
  }
}
