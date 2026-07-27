from django.db import migrations


def expand_specialization_catalog(apps, schema_editor):
    Specialization = apps.get_model('doctors', 'Specialization')

    defaults = [
        ('Allergologiya va Immunologiya', 'ALLERGY_IMMUNO'),
        ('Andrologiya', 'ANDRO'),
        ('Gastroenterologiya', 'GASTRO'),
        ('Gematologiya', 'HEMATO'),
        ('Ginekologiya va Akusherlik', 'GYNE'),
        ('Dermatologiya', 'DERMA'),
        ('Diabetologiya', 'DIABETO'),
        ('Endokrinologiya', 'ENDO'),
        ('Kardiologiya', 'CARDIO'),
        ('Mammologiya', 'MAMMO'),
        ('Nefrologiya', 'NEPHRO'),
        ('Nevrologiya', 'NEURO'),
        ('Narkologiya', 'NARCO'),
        ('Onkologiya', 'ONCO'),
        ('Ortopediya va Travmatologiya', 'ORTHO'),
        ('Otorinolaringologiya (LOR)', 'ENT'),
        ('Oftalmologiya', 'OPHTH'),
        ('Pediatriya', 'PEDI'),
        ('Proktologiya', 'PROCTO'),
        ('Psixiatriya va Psixoterapiya', 'PSYCH'),
        ('Pulmonologiya', 'PULMO'),
        ('Reabilitatologiya', 'REHAB'),
        ('Revmatologiya', 'RHEUM'),
        ('Stomatologiya', 'DENT'),
        ('Terapiya', 'THERAPY'),
        ('Urologiya', 'URO'),
        ('Flebologiya', 'PHLEBO'),
        ('Xirurgiya', 'SURGERY'),
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
            if not existing.description:
                existing.description = 'Default seeded specialization'
                updates.append('description')
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
        ('doctors', '0016_rename_doctors_doc_doctor__4c2317_idx_doctors_doc_doctor__b70c1a_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(expand_specialization_catalog, noop_reverse),
    ]
