from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0007_clinic_working_hours'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='owner_passport_id',
            field=models.CharField(
                blank=True,
                db_index=True,
                help_text='Klinika egasining pasport yoki ID raqami',
                max_length=50,
                null=True,
                verbose_name='owner passport id',
            ),
        ),
    ]
