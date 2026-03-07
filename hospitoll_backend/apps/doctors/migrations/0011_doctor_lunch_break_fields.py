from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0010_doctor_identity_and_compensation'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='lunch_break_end',
            field=models.TimeField(blank=True, help_text='Abet (tanaffus) tugash vaqti', null=True, verbose_name='lunch break end'),
        ),
        migrations.AddField(
            model_name='doctor',
            name='lunch_break_start',
            field=models.TimeField(blank=True, help_text='Abet (tanaffus) boshlanish vaqti', null=True, verbose_name='lunch break start'),
        ),
    ]
