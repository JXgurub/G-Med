from django.db import migrations, models
from django.db.models import Q
from django.utils import timezone
import django.db.models.deletion
import uuid


def backfill_active_employments(apps, schema_editor):
    Doctor = apps.get_model('doctors', 'Doctor')
    DoctorEmployment = apps.get_model('doctors', 'DoctorEmployment')

    doctors = Doctor.objects.exclude(clinic_id__isnull=True)
    for doctor in doctors.iterator():
        DoctorEmployment.objects.get_or_create(
            doctor_id=doctor.id,
            ended_at=None,
            defaults={
                'clinic_id': doctor.clinic_id,
                'started_at': doctor.created_at or timezone.now(),
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0013_doctor_telegram_fields'),
        ('users', '0007_pharmacyresettelegramsession'),
    ]

    operations = [
        migrations.CreateModel(
            name='DoctorEmployment',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('started_at', models.DateTimeField(db_index=True, default=timezone.now, verbose_name='started at')),
                ('ended_at', models.DateTimeField(blank=True, db_index=True, null=True, verbose_name='ended at')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='created at')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='updated at')),
                ('clinic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='doctor_employments', to='clinics.clinic')),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='employment_history', to='doctors.doctor')),
                ('terminated_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='terminated_doctor_employments', to='users.customuser')),
            ],
            options={
                'verbose_name': 'Doctor Employment',
                'verbose_name_plural': 'Doctor Employments',
                'ordering': ['-started_at'],
                'indexes': [
                    models.Index(fields=['doctor', 'clinic'], name='doctors_doc_doctor__4c2317_idx'),
                    models.Index(fields=['clinic', '-started_at'], name='doctors_doc_clinic__c69c44_idx'),
                    models.Index(fields=['doctor', 'ended_at'], name='doctors_doc_doctor__f2a1bf_idx'),
                ],
                'constraints': [
                    models.UniqueConstraint(condition=Q(('ended_at__isnull', True)), fields=('doctor',), name='unique_active_employment_per_doctor'),
                ],
            },
        ),
        migrations.RunPython(backfill_active_employments, migrations.RunPython.noop),
    ]
