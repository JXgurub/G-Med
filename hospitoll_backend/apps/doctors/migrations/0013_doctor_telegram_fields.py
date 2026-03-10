from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0012_seed_default_specializations'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='telegram_chat_id',
            field=models.BigIntegerField(blank=True, help_text='Doktor Telegram chat id (password reset OTP uchun)', null=True, verbose_name='telegram chat id'),
        ),
        migrations.AddField(
            model_name='doctor',
            name='telegram_user_id',
            field=models.BigIntegerField(blank=True, db_index=True, help_text='Doktor Telegram user id (password reset OTP uchun)', null=True, verbose_name='telegram user id'),
        ),
    ]
