from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0020_alter_doctor_options_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctorspecialization',
            name='doctor_custom',
            field=models.BooleanField(default=False, help_text="Doktorning o'zi qo'shgan yo'nalish"),
        ),
    ]