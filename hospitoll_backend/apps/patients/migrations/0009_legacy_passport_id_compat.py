from django.db import migrations, models


def ensure_legacy_passport_column(apps, schema_editor):
    patient_model = apps.get_model('patients', 'Patient')
    table_name = patient_model._meta.db_table

    with schema_editor.connection.cursor() as cursor:
        columns = {
            column.name
            for column in schema_editor.connection.introspection.get_table_description(cursor, table_name)
        }

    if 'passport_id' in columns:
        return

    field = models.CharField(
        max_length=50,
        blank=True,
        default='',
        db_column='passport_id',
        editable=False,
    )
    field.set_attributes_from_name('legacy_passport_id')
    field.model = patient_model
    schema_editor.add_field(patient_model, field)


class Migration(migrations.Migration):
    dependencies = [
        ('patients', '0008_alter_patient_patient_number'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(ensure_legacy_passport_column, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='patient',
                    name='legacy_passport_id',
                    field=models.CharField(
                        blank=True,
                        db_column='passport_id',
                        default='',
                        editable=False,
                        max_length=50,
                        verbose_name='legacy passport ID',
                    ),
                ),
            ],
        ),
    ]