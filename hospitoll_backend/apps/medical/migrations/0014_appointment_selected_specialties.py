from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medical', '0013_medicalrecord_attachment'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='selected_specialties',
            field=models.JSONField(blank=True, default=list, help_text="Reception tanlagan yo'nalishlar va narxlar", verbose_name='selected treatment directions'),
        ),
    ]
