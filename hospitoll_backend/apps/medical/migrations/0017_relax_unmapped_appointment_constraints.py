from django.db import migrations


def relax_unmapped_appointment_constraints(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return

    appointment_model = apps.get_model('medical', 'Appointment')
    table_name = appointment_model._meta.db_table
    mapped_columns = {field.column for field in appointment_model._meta.local_fields}

    with connection.cursor() as cursor:
        columns = connection.introspection.get_table_description(cursor, table_name)
        unmapped_required_columns = [
            column.name
            for column in columns
            if not column.null_ok and column.name not in mapped_columns
        ]

        quote = connection.ops.quote_name
        for column_name in unmapped_required_columns:
            cursor.execute(
                f'ALTER TABLE {quote(table_name)} '
                f'ALTER COLUMN {quote(column_name)} DROP NOT NULL'
            )


class Migration(migrations.Migration):
    dependencies = [
        ('medical', '0016_relax_legacy_appointment_ticket_number'),
    ]

    operations = [
        migrations.RunPython(relax_unmapped_appointment_constraints, migrations.RunPython.noop),
    ]