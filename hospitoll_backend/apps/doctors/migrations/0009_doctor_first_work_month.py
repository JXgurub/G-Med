from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0008_doctor_profile_fields_auto_experience'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='first_work_month',
            field=models.PositiveSmallIntegerField(
                blank=True,
                null=True,
                validators=[django.core.validators.MinValueValidator(1), django.core.validators.MaxValueValidator(12)],
                verbose_name='first work month',
                help_text='Doktor ish boshlagan birinchi oy (1-12)'
            ),
        ),
    ]
