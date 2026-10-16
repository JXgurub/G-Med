import secrets

from apps.medical.models import generate_prescription_code
from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def populate_prescription_codes(apps, schema_editor):
    MedicalRecord = apps.get_model('medical', 'MedicalRecord')
    alias = schema_editor.connection.alias
    used_codes = set()

    for record in MedicalRecord.objects.using(alias).only('pk').iterator():
        code = f'{secrets.randbelow(90_000_000) + 10_000_000}'
        while code in used_codes:
            code = f'{secrets.randbelow(90_000_000) + 10_000_000}'
        used_codes.add(code)
        MedicalRecord.objects.using(alias).filter(pk=record.pk).update(prescription_code=code)


class Migration(migrations.Migration):

    dependencies = [
        ('medical', '0020_default_unselected_payment_to_cash'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicalrecord',
            name='prescription_code',
            field=models.CharField(
                blank=True,
                max_length=8,
                null=True,
                unique=True,
                verbose_name=_('prescription code'),
            ),
        ),
        migrations.RunPython(populate_prescription_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='medicalrecord',
            name='prescription_code',
            field=models.CharField(
                default=generate_prescription_code,
                editable=False,
                help_text=_('Bemor retsept dorilarini ovoz orqali qidirishi uchun qisqa kod'),
                max_length=8,
                unique=True,
                verbose_name=_('prescription code'),
            ),
        ),
    ]
