from django.db import migrations


def seed_default_specializations(apps, schema_editor):
    Specialization = apps.get_model('doctors', 'Specialization')

    defaults = [
        ('Kardiologiya', 'CARDIO'),
        ('Nevrologiya', 'NEURO'),
        ('Pediatriya', 'PEDI'),
        ('Terapiya', 'THERAPY'),
        ('Ginekologiya', 'GYNE'),
        ('Urologiya', 'URO'),
        ('Dermatologiya', 'DERMA'),
        ('Otorinolaringologiya', 'ENT'),
        ('Oftalmologiya', 'OPHTH'),
        ('Travmatologiya', 'TRAUMA'),
        ('Ortopediya', 'ORTHO'),
        ('Endokrinologiya', 'ENDO'),
        ('Gastroenterologiya', 'GASTRO'),
        ('Pulmonologiya', 'PULMO'),
        ('Nefrologiya', 'NEPHRO'),
        ('Reabilitatsiya', 'REHAB'),
        ('Onkologiya', 'ONCO'),
        ('Psixiatriya', 'PSYCH'),
    ]

    for name, code in defaults:
        existing = Specialization.objects.filter(code=code).first()
        if not existing:
            existing = Specialization.objects.filter(name__iexact=name).first()

        if existing:
            updates = []
            if existing.name != name:
                existing.name = name
                updates.append('name')
            if existing.code != code:
                existing.code = code
                updates.append('code')
            if not existing.is_active:
                existing.is_active = True
                updates.append('is_active')
            if updates:
                existing.save(update_fields=updates)
            continue

        Specialization.objects.create(
            name=name,
            code=code,
            description='Default seeded specialization',
            is_active=True,
        )


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0011_doctor_lunch_break_fields'),
    ]

    operations = [
        migrations.RunPython(seed_default_specializations, noop_reverse),
    ]
