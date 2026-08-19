from django.db import migrations


def restore_clinic_owned_specialties(apps, schema_editor):
    DoctorSpecialization = apps.get_model('doctors', 'DoctorSpecialization')
    # Existing rows were created by clinic doctor onboarding before ownership tracking existed.
    DoctorSpecialization.objects.filter(doctor_custom=True).update(doctor_custom=False)


class Migration(migrations.Migration):
    dependencies = [
        ('doctors', '0022_backfill_doctor_custom_specializations'),
    ]

    operations = [
        migrations.RunPython(restore_clinic_owned_specialties, migrations.RunPython.noop),
    ]
