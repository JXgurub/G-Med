from django.db import migrations, models
import secrets


def migration_patient_number():
    return f'GM{secrets.randbelow(90000000) + 10000000}'


def populate_patient_numbers(apps, schema_editor):
    Patient = apps.get_model('patients', 'Patient')
    for patient in Patient.objects.filter(patient_number__isnull=True):
        number = migration_patient_number()
        while Patient.objects.filter(patient_number=number).exists():
            number = migration_patient_number()
        patient.patient_number = number
        patient.save(update_fields=['patient_number'])


class Migration(migrations.Migration):
    dependencies = [('patients', '0006_remove_patient_national_id')]
    operations = [
        migrations.AddField(
            model_name='patient',
            name='patient_number',
            field=models.CharField(blank=True, max_length=20, null=True),
        ),
        migrations.RunPython(populate_patient_numbers, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='patient',
            name='patient_number',
            field=models.CharField(default=migration_patient_number, max_length=20, unique=True),
        ),
    ]