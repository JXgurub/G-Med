from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0006_doctor_slot_minutes'),
        ('clinics', '0006_clinic_staff_messages'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='pinfl',
            field=models.CharField(blank=True, db_index=True, help_text='Doktorning yagona PINFL raqami', max_length=20, null=True, unique=True, verbose_name='pinfl'),
        ),
        migrations.AlterField(
            model_name='doctor',
            name='clinic',
            field=models.ForeignKey(blank=True, help_text='Doktor tegishli klinika', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='doctors', to='clinics.clinic', verbose_name='clinic'),
        ),
    ]
