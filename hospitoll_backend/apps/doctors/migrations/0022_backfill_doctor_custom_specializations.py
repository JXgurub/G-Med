from django.db import migrations


def mark_existing_doctor_specialties_as_doctor_owned(apps, schema_editor):
    DoctorSpecialization = apps.get_model('doctors', 'DoctorSpecialization')
    DoctorSpecialization.objects.filter(doctor_custom=False).update(doctor_custom=True)


class Migration(migrations.Migration):
    dependencies = [
        ('doctors', '0021_doctorspecialization_doctor_custom'),
    ]

    operations = [
        migrations.RunPython(mark_existing_doctor_specialties_as_doctor_owned, migrations.RunPython.noop),
    ]
