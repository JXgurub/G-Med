from django.db import migrations, models
from apps.patients.models import generate_patient_number


class Migration(migrations.Migration):
    dependencies = [
        ('patients', '0007_patient_patient_number'),
    ]

    operations = [
        migrations.AlterField(
            model_name='patient',
            name='patient_number',
            field=models.CharField(default=generate_patient_number, max_length=20, unique=True, db_index=True),
        ),
    ]
