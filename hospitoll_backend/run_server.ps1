Set-Location "C:\Hospitoll\hospitoll_backend"

$env:DEBUG = 'True'
$env:DB_ENGINE = 'sqlite'
$env:SECURE_SSL_REDIRECT = 'False'
$env:SPECTACULAR_DISABLE_WARNINGS = 'False'

if (-not $env:DJANGO_SECRET_KEY -or $env:DJANGO_SECRET_KEY -eq 'your-very-secret-key-change-in-production') {
	$env:DJANGO_SECRET_KEY = 'django-insecure-local-dev-key-change-in-production'
}

& "C:\Hospitoll\hospitoll_backend\venv\Scripts\python.exe" manage.py runserver 0.0.0.0:8000
