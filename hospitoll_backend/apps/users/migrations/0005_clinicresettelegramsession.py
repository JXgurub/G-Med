from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0008_clinic_owner_passport_id'),
        ('users', '0004_doctorresettelegramsession'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicResetTelegramSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('telegram_user_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('telegram_chat_id', models.BigIntegerField(blank=True, null=True)),
                ('linked_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('clinic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reset_telegram_sessions', to='clinics.clinic')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clinic_reset_telegram_sessions', to='users.customuser')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='clinicresettelegramsession',
            index=models.Index(fields=['user', 'expires_at'], name='users_clini_user_id_1d2a89_idx'),
        ),
        migrations.AddIndex(
            model_name='clinicresettelegramsession',
            index=models.Index(fields=['clinic', 'expires_at'], name='users_clini_clinic__d7fa72_idx'),
        ),
    ]
