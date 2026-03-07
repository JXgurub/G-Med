$ErrorActionPreference = 'Stop'

Write-Host "== Hosptol Telegram webhook (ngrok) setup ==" -ForegroundColor Cyan

# 1) Detect ngrok public URL
try {
  $tunnels = Invoke-RestMethod -UseBasicParsing http://127.0.0.1:4040/api/tunnels
  $publicUrl = $tunnels.tunnels[0].public_url
} catch {
  throw "ngrok local API not reachable on http://127.0.0.1:4040. Start ngrok first: ngrok http 8000"
}

if (-not $publicUrl) {
  throw "ngrok tunnel not found. Start ngrok first: ngrok http 8000"
}

# 2) Read TELEGRAM_WEBHOOK_SECRET from .env
$envPath = Join-Path $PSScriptRoot '.env'
if (-not (Test-Path $envPath)) {
  throw ".env not found at $envPath"
}

$envLines = Get-Content $envPath
function Get-EnvValue([string]$key) {
  $line = $envLines | Where-Object { $_ -match "^$key=" } | Select-Object -First 1
  if (-not $line) { return $null }
  return ($line -split "=", 2)[1]
}

$secret = Get-EnvValue 'TELEGRAM_WEBHOOK_SECRET'
$username = Get-EnvValue 'TELEGRAM_BOT_USERNAME'
if (-not $username) { $username = 'GMed1_bot' }

if (-not $secret) {
  throw "TELEGRAM_WEBHOOK_SECRET is missing in .env"
}

# 3) Ask for bot token (DO NOT PRINT)
$secure = Read-Host "Paste TELEGRAM_BOT_TOKEN (won't be printed)" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
  $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if (-not $token) {
  throw "Token is empty"
}

# Optionally persist token to .env for convenience (local only)
$persist = Read-Host "Persist token to .env for this machine? (y/N)"
if ($persist -match '^(y|yes)$') {
  $updated = $false
  for ($i = 0; $i -lt $envLines.Count; $i++) {
    if ($envLines[$i] -match '^TELEGRAM_BOT_TOKEN=') {
      $envLines[$i] = "TELEGRAM_BOT_TOKEN=$token"
      $updated = $true
      break
    }
  }
  if (-not $updated) {
    $envLines += "TELEGRAM_BOT_TOKEN=$token"
  }
  Set-Content -Path $envPath -Value $envLines -Encoding UTF8
  Write-Host "Saved TELEGRAM_BOT_TOKEN to .env (DO NOT COMMIT)" -ForegroundColor Yellow
}

# 4) Run the management command with env vars only for this process
$env:TELEGRAM_BOT_TOKEN = $token
$env:TELEGRAM_BOT_USERNAME = $username
$env:TELEGRAM_WEBHOOK_SECRET = $secret

Write-Host "Setting webhook to: $publicUrl" -ForegroundColor Green
Write-Host "Bot: @$username" -ForegroundColor Green

& "C:\Hospitoll\hospitoll_backend\venv\Scripts\python.exe" manage.py set_telegram_webhook --base-url $publicUrl --drop-pending-updates

Write-Host "Done. Now open the bot and send /myappointments" -ForegroundColor Cyan
