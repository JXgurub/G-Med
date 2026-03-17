from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0005_patient_profile_health_fields'),
        ('users', '0005_clinicresettelegramsession'),
    ]

    operations = [
        migrations.CreateModel(
            name='PatientResetTelegramSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('telegram_user_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('telegram_chat_id', models.BigIntegerField(blank=True, null=True)),
                ('linked_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('patient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reset_telegram_sessions', to='patients.patient')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='patient_reset_telegram_sessions', to='users.customuser')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='patientresettelegramsession',
            index=models.Index(fields=['user', 'expires_at'], name='users_patie_user_id_31fb8a_idx'),
        ),
        migrations.AddIndex(
            model_name='patientresettelegramsession',
            index=models.Index(fields=['patient', 'expires_at'], name='users_patie_patient_5bd4fe_idx'),
        ),
    ]
