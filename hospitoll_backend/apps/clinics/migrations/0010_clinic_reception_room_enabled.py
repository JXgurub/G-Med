from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0009_clinic_feature_toggles'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='reception_room_enabled',
            field=models.BooleanField(
                default=False,
                help_text='Qabul xonasi navbat logikasini yoqish',
                verbose_name='reception room enabled',
            ),
        ),
    ]