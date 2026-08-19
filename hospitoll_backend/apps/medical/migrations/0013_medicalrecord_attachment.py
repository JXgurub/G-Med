from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('medical', '0012_alter_telegramconversationstate_action'),
    ]

    operations = [
        migrations.AddField(
            model_name='medicalrecord',
            name='attachment',
            field=models.FileField(
                blank=True,
                help_text='Tashxisga biriktirilgan fayl',
                null=True,
                upload_to='medical_records/%Y/%m/%d/',
                verbose_name='attachment',
            ),
        ),
    ]
