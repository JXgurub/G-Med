from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0011_offline_pos_models'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacysaleline',
            name='stock_mismatch',
            field=models.BooleanField(default=False),
        ),
    ]
