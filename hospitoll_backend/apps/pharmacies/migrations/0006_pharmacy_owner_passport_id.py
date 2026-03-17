from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0005_pharmacy_payment_date'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacy',
            name='owner_passport_id',
            field=models.CharField(blank=True, default='', help_text="Dorixona egasining pasport IDsi", max_length=32, verbose_name='owner passport id'),
        ),
    ]
