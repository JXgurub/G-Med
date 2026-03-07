from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0006_clinic_staff_messages'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='working_hours',
            field=models.CharField(default='09:00 - 18:00', help_text='Masalan: 09:00 - 18:00', max_length=100, verbose_name='working hours'),
        ),
    ]
