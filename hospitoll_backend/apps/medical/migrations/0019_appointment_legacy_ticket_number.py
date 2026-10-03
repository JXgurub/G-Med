from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


def add_ticket_number_column_if_missing(apps, schema_editor):
    appointment_model = apps.get_model('medical', 'Appointment')
    table_name = appointment_model._meta.db_table
    with schema_editor.connection.cursor() as cursor:
        columns = schema_editor.connection.introspection.get_table_description(cursor, table_name)
    if any(column.name == 'ticket_number' for column in columns):
        return

    field = models.PositiveIntegerField(
        _('legacy ticket number'),
        db_column='ticket_number',
        null=True,
        blank=True,
        default=0,
    )
    field.set_attributes_from_name('ticket_number')
    field.model = appointment_model
    schema_editor.add_field(appointment_model, field)


class Migration(migrations.Migration):
    dependencies = [
        ('medical', '0018_appointment_payment_method'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(add_ticket_number_column_if_missing, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='appointment',
                    name='ticket_number',
                    field=models.PositiveIntegerField(
                        blank=True,
                        db_column='ticket_number',
                        default=0,
                        null=True,
                        verbose_name=_('legacy ticket number'),
                    ),
                ),
            ],
        ),
    ]