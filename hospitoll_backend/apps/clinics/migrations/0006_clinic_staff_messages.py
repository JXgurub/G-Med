from django.db import migrations, models
import django.db.models.deletion
from uuid import uuid4
import django.utils.timezone


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0005_clinic_payment_date'),
        ('users', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='ClinicStaffMessage',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid4, editable=False, serialize=False)),
                ('body', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('clinic', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='staff_messages', to='clinics.clinic')),
                ('sender', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sent_clinic_staff_messages', to='users.customuser')),
            ],
            options={
                'ordering': ['-created_at'],
            },
        ),
        migrations.CreateModel(
            name='ClinicStaffMessageRecipient',
            fields=[
                ('id', models.UUIDField(primary_key=True, default=uuid4, editable=False, serialize=False)),
                ('is_read', models.BooleanField(default=False)),
                ('read_at', models.DateTimeField(blank=True, null=True)),
                ('delivered_at', models.DateTimeField(default=django.utils.timezone.now)),
                ('message', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='recipients', to='clinics.clinicstaffmessage')),
                ('recipient', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='clinic_staff_message_recipients', to='users.customuser')),
            ],
            options={
                'ordering': ['-delivered_at'],
            },
        ),
        migrations.AddConstraint(
            model_name='clinicstaffmessagerecipient',
            constraint=models.UniqueConstraint(fields=('message', 'recipient'), name='uniq_clinic_staff_message_recipient'),
        ),
        migrations.AddIndex(
            model_name='clinicstaffmessage',
            index=models.Index(fields=['clinic', '-created_at'], name='clinics_cli_clinic__08aa05_idx'),
        ),
        migrations.AddIndex(
            model_name='clinicstaffmessage',
            index=models.Index(fields=['sender', '-created_at'], name='clinics_cli_sender__f3df0c_idx'),
        ),
        migrations.AddIndex(
            model_name='clinicstaffmessagerecipient',
            index=models.Index(fields=['recipient', 'is_read', '-delivered_at'], name='clinics_cli_recipie_8fd2b9_idx'),
        ),
        migrations.AddIndex(
            model_name='clinicstaffmessagerecipient',
            index=models.Index(fields=['message', '-delivered_at'], name='clinics_cli_message_9d252f_idx'),
        ),
    ]
