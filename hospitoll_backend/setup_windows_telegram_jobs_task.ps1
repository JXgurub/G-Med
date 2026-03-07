$ErrorActionPreference = 'Stop'

$taskName = 'HospitollTelegramJobs'
$python = 'C:\Hospitoll\hospitoll_backend\venv\Scripts\python.exe'
$workdir = 'C:\Hospitoll\hospitoll_backend'

if (-not (Test-Path $python)) {
  throw "Python venv not found at $python"
}

# schtasks.exe doesn't support WorkingDirectory; use cmd.exe + cd.
$taskCommand = ('cmd.exe /c "cd /d {0} && ""{1}"" manage.py process_telegram_jobs"' -f $workdir, $python)

function Test-IsAdmin {
  $currentIdentity = [Security.Principal.WindowsIdentity]::GetCurrent()
  $principal = [Security.Principal.WindowsPrincipal]::new($currentIdentity)
  return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-TaskSafe([string]$name) {
  try {
    Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction Stop
  } catch {
    # ignore
  }
  try {
    schtasks.exe /Delete /TN $name /F 2>$null | Out-Null
  } catch {
    # ignore
  }
}

Remove-TaskSafe $taskName

$isAdmin = Test-IsAdmin
if ($isAdmin) {
  # SYSTEM task (no password required). Requires admin.
  schtasks.exe /Create /TN $taskName /SC MINUTE /MO 1 /RU SYSTEM /RL LIMITED /TR $taskCommand /F | Out-Null
} else {
  # Current-user task. schtasks requires password unless you run as SYSTEM.
  # It will prompt for password in the terminal.
  $userId = "{0}\\{1}" -f $env:USERDOMAIN, $env:USERNAME
  Write-Warning "Not running as Administrator. Creating task under current user: $userId"
  Write-Output "schtasks will prompt for your Windows password."
  schtasks.exe /Create /TN $taskName /SC MINUTE /MO 1 /RU $userId /RP * /RL LIMITED /TR $taskCommand /F | Out-Null
}

schtasks.exe /Run /TN $taskName | Out-Null

Write-Output "Created & started scheduled task: $taskName"
Write-Output "To remove: .\\remove_windows_telegram_jobs_task.ps1"
