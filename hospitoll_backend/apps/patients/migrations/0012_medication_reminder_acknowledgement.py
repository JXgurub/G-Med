from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0011_patientmedicationreminder'),
    ]

    operations = [
        migrations.AddField(
            model_name='patientmedicationreminder',
            name='pending_dose_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='patientmedicationreminder',
            name='next_nudge_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='patientmedicationreminder',
            name='acknowledgement_token',
            field=models.UUIDField(blank=True, editable=False, null=True, unique=True),
        ),
    ]
