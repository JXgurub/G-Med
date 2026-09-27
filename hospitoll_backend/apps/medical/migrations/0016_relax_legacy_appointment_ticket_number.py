from django.db import migrations


def relax_legacy_ticket_number_constraint(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return

    table_name = 'medical_appointment'
    column_name = 'ticket_number'
    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, table_name)
        if not any(column.name == column_name for column in columns):
            return

        quote = connection.ops.quote_name
        cursor.execute(
            f'ALTER TABLE {quote(table_name)} '
            f'ALTER COLUMN {quote(column_name)} DROP NOT NULL'
        )


class Migration(migrations.Migration):
    dependencies = [
        ('medical', '0015_appointment_reception_staff'),
    ]

    operations = [
        migrations.RunPython(relax_legacy_ticket_number_constraint, migrations.RunPython.noop),
    ]