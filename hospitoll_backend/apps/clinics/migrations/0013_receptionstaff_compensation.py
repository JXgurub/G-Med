from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0012_receptionstaff_lunch_break'),
    ]

    operations = [
        migrations.AddField(
            model_name='receptionstaff',
            name='compensation_type',
            field=models.CharField(
                choices=[('salary', 'Ish haqi'), ('percent', 'Foiz')],
                default='salary',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='receptionstaff',
            name='compensation_value',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
    ]