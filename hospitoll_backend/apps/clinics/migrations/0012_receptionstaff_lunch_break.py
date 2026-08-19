from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0011_receptionstaff'),
    ]

    operations = [
        migrations.AddField(
            model_name='receptionstaff',
            name='lunch_break_start',
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='receptionstaff',
            name='lunch_break_end',
            field=models.TimeField(blank=True, null=True),
        ),
    ]