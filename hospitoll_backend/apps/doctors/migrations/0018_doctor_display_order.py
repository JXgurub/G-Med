from django.db import migrations, models


def backfill_display_order(apps, schema_editor):
    Doctor = apps.get_model('doctors', 'Doctor')

    clinic_ids = Doctor.objects.exclude(clinic_id__isnull=True).values_list('clinic_id', flat=True).distinct()
    for clinic_id in clinic_ids:
        doctors = Doctor.objects.filter(clinic_id=clinic_id).order_by('created_at', 'id')
        for index, doctor in enumerate(doctors, start=1):
            if doctor.display_order != index:
                doctor.display_order = index
                doctor.save(update_fields=['display_order'])


def noop_reverse(apps, schema_editor):
    return


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0017_expand_specialization_catalog'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='display_order',
            field=models.PositiveIntegerField(default=0, db_index=True, help_text='Klinikadagi ko‘rinish tartibi', verbose_name='display order'),
        ),
        migrations.AddIndex(
            model_name='doctor',
            index=models.Index(fields=['clinic', 'display_order'], name='doc_clinic_disp_ord_idx'),
        ),
        migrations.RunPython(backfill_display_order, noop_reverse),
    ]
