from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0008_clinic_owner_passport_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='attendance_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Doktor ishga kelish va ketishini belgilashi mumkin',
                verbose_name='doctor attendance enabled',
            ),
        ),
        migrations.AddField(
            model_name='clinic',
            name='diagnosis_entry_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Bemor qabul qilinganda tashxis formasini avtomatik ochish',
                verbose_name='diagnosis entry enabled',
            ),
        ),
    ]
