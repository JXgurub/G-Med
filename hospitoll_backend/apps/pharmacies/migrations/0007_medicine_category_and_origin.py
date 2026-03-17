from django.db import migrations, models


def backfill_medicine_category(apps, schema_editor):
    Medicine = apps.get_model('pharmacies', 'Medicine')
    for medicine in Medicine.objects.all().only('id', 'description', 'category'):
        if medicine.category:
            continue
        description = (medicine.description or '').strip()
        medicine.category = description if description else 'Boshqa'
        medicine.save(update_fields=['category'])


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0006_pharmacy_owner_passport_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicine',
            name='category',
            field=models.CharField(blank=True, default='Boshqa', help_text='Dori kategoriyasi', max_length=120, verbose_name='category'),
        ),
        migrations.AddField(
            model_name='medicine',
            name='country_of_origin',
            field=models.CharField(blank=True, help_text='Dori ishlab chiqarilgan davlat', max_length=120, verbose_name='country of origin'),
        ),
        migrations.RunPython(backfill_medicine_category, migrations.RunPython.noop),
        migrations.AddIndex(
            model_name='medicine',
            index=models.Index(fields=['category'], name='pharmacies__catego_9c59ef_idx'),
        ),
    ]
