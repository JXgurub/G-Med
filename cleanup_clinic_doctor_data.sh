#!/usr/bin/env bash
set -euo pipefail

cd /root/Hospitoll
TS=$(date +%Y%m%d_%H%M%S)

# Backup full production DB before destructive cleanup.
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend sh -lc 'PGPASSWORD="$DB_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" "$DB_NAME"' > "/root/Hospitoll/db_backup_before_clinic_doctor_delete_${TS}.sql"
echo "Backup:/root/Hospitoll/db_backup_before_clinic_doctor_delete_${TS}.sql"

# Delete clinic/doctor records and related role users.
docker compose --env-file .env.production -f docker-compose.prod.yml exec -T backend python manage.py shell <<'PY'
from apps.clinics.models import Clinic
from apps.doctors.models import Doctor
from apps.users.models import CustomUser

before = {
    'clinics': Clinic.objects.count(),
    'doctors': Doctor.objects.count(),
    'clinic_users': CustomUser.objects.filter(role='clinic').count(),
    'doctor_users': CustomUser.objects.filter(role='doctor').count(),
}
print('Before:', before)

Doctor.objects.all().delete()
Clinic.objects.all().delete()
CustomUser.objects.filter(role='doctor').delete()
CustomUser.objects.filter(role='clinic').delete()

after = {
    'clinics': Clinic.objects.count(),
    'doctors': Doctor.objects.count(),
    'clinic_users': CustomUser.objects.filter(role='clinic').count(),
    'doctor_users': CustomUser.objects.filter(role='doctor').count(),
}
print('After:', after)
PY
