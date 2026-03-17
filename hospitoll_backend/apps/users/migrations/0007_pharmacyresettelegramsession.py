from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0006_pharmacy_owner_passport_id'),
        ('users', '0006_patientresettelegramsession'),
    ]

    operations = [
        migrations.CreateModel(
            name='PharmacyResetTelegramSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('token', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('telegram_user_id', models.BigIntegerField(blank=True, db_index=True, null=True)),
                ('telegram_chat_id', models.BigIntegerField(blank=True, null=True)),
                ('linked_at', models.DateTimeField(blank=True, null=True)),
                ('expires_at', models.DateTimeField(db_index=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('pharmacy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reset_telegram_sessions', to='pharmacies.pharmacy')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pharmacy_reset_telegram_sessions', to='users.customuser')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='pharmacyresettelegramsession',
            index=models.Index(fields=['user', 'expires_at'], name='users_pharm_user_id_2a87d8_idx'),
        ),
        migrations.AddIndex(
            model_name='pharmacyresettelegramsession',
            index=models.Index(fields=['pharmacy', 'expires_at'], name='users_pharm_pharmac_fa65af_idx'),
        ),
    ]
