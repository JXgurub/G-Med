from django.db import migrations, models
import django.core.validators


def backfill_employment_compensation(apps, schema_editor):
    DoctorEmployment = apps.get_model('doctors', 'DoctorEmployment')

    for employment in DoctorEmployment.objects.select_related('doctor').all().iterator():
        doctor = employment.doctor
        if not doctor:
            continue

        employment.compensation_type = getattr(doctor, 'compensation_type', 'salary') or 'salary'
        employment.compensation_value = getattr(doctor, 'compensation_value', None)
        employment.save(update_fields=['compensation_type', 'compensation_value'])


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0014_doctoremployment_history'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctoremployment',
            name='compensation_type',
            field=models.CharField(
                choices=[('salary', 'Salary'), ('percent', 'Percent')],
                default='salary',
                help_text='Employment pay model snapshot for historical reporting',
                max_length=20,
                verbose_name='compensation type',
            ),
        ),
        migrations.AddField(
            model_name='doctoremployment',
            name='compensation_value',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Employment pay value snapshot for historical reporting',
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='compensation value',
            ),
        ),
        migrations.RunPython(backfill_employment_compensation, migrations.RunPython.noop),
    ]
