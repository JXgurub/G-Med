from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0013_doctor_telegram_fields'),
        ('users', '0003_codeverificationlockstate'),
    ]

    operations = [
        migrations.CreateModel(
            name='DoctorResetTelegramSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('telegram_user_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('telegram_chat_id', models.BigIntegerField(blank=True, null=True)),
                ('linked_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('doctor', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reset_telegram_sessions', to='doctors.doctor')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='doctor_reset_telegram_sessions', to='users.customuser')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='doctorresettelegramsession',
            index=models.Index(fields=['user', 'expires_at'], name='users_docto_user_id_b69a67_idx'),
        ),
        migrations.AddIndex(
            model_name='doctorresettelegramsession',
            index=models.Index(fields=['doctor', 'expires_at'], name='users_docto_doctor__1b4192_idx'),
        ),
    ]
