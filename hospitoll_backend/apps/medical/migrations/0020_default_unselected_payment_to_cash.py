from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def backfill_unselected_payments_as_cash(apps, schema_editor):
    Appointment = apps.get_model('medical', 'Appointment')
    alias = schema_editor.connection.alias
    Appointment.objects.using(alias).filter(payment_method='').update(payment_method='cash')


class Migration(migrations.Migration):

    dependencies = [
        ('medical', '0019_appointment_legacy_ticket_number'),
    ]

    operations = [
        migrations.RunPython(backfill_unselected_payments_as_cash, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='appointment',
            name='payment_method',
            field=models.CharField(
                blank=True,
                choices=[
                    ('', _('Ko‘rsatilmagan')),
                    ('card', _('Plastik')),
                    ('click', 'Click'),
                    ('cash', _('Naqd')),
                ],
                default='cash',
                max_length=10,
                verbose_name=_('payment method'),
            ),
        ),
    ]