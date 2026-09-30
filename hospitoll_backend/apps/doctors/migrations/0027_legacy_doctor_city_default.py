from django.db import migrations


def ensure_legacy_city_default(apps, schema_editor):
    connection = schema_editor.connection
    if connection.vendor != 'postgresql':
        return

    with connection.cursor() as cursor:
        columns = {
            column.name
            for column in connection.introspection.get_table_description(cursor, 'doctors_doctor')
        }

    if 'city' in columns:
        schema_editor.execute('ALTER TABLE "doctors_doctor" ALTER COLUMN "city" SET DEFAULT \'\'')


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0024_doctorspecialization_custom_name'),
    ]

    operations = [
        migrations.RunPython(ensure_legacy_city_default, migrations.RunPython.noop),
    ]