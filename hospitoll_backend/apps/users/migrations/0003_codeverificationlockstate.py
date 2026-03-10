from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0002_passwordresetcode'),
    ]

    operations = [
        migrations.CreateModel(
            name='CodeVerificationLockState',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('channel', models.CharField(choices=[('patient_password_reset', 'Patient password reset'), ('doctor_password_reset', 'Doctor password reset')], max_length=64)),
                ('lock_stage', models.PositiveSmallIntegerField(default=1)),
                ('failed_attempts', models.PositiveSmallIntegerField(default=0)),
                ('blocked_until', models.DateTimeField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='code_verification_lock_states', to='users.customuser')),
            ],
            options={
                'unique_together': {('user', 'channel')},
            },
        ),
        migrations.AddIndex(
            model_name='codeverificationlockstate',
            index=models.Index(fields=['channel', 'blocked_until'], name='users_codev_channel_8c9952_idx'),
        ),
        migrations.AddIndex(
            model_name='codeverificationlockstate',
            index=models.Index(fields=['user', 'channel'], name='users_codev_user_id_6c0e19_idx'),
        ),
    ]
