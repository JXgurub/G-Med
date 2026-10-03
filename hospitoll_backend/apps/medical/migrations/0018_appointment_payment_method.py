from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def add_payment_method_column_if_missing(apps, schema_editor):
    appointment_model = apps.get_model('medical', 'Appointment')
    table_name = appointment_model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        columns = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    if any(column.name == 'payment_method' for column in columns):
        return

    field = models.CharField(
        blank=True,
        choices=[
            ('', _('Ko‘rsatilmagan')),
            ('card', _('Plastik')),
            ('click', 'Click'),
            ('cash', _('Naqd')),
        ],
        default='',
        max_length=10,
        verbose_name=_('payment method'),
    )
    field.set_attributes_from_name('payment_method')
    field.model = appointment_model
    schema_editor.add_field(appointment_model, field)


class Migration(migrations.Migration):

    dependencies = [
        ('medical', '0017_relax_unmapped_appointment_constraints'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_payment_method_column_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
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
                        default='',
                        max_length=10,
                        verbose_name=_('payment method'),
                    ),
                ),
            ],
        ),
    ]
