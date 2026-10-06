from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('site_settings', '0007_webpushsubscription'),
    ]

    operations = [
        migrations.AddField(
            model_name='broadcastnotification',
            name='data',
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
