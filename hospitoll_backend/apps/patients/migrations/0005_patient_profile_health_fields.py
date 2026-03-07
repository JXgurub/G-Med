from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('patients', '0004_patient_no_show_count_patient_requires_deposit'),
    ]

    operations = [
        migrations.AddField(
            model_name='patient',
            name='animal_allergies',
            field=models.TextField(blank=True, help_text="Hayvonlarga allergiya haqida ma'lumot", verbose_name='animal allergies'),
        ),
        migrations.AddField(
            model_name='patient',
            name='birth_year',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Bemor tug‘ilgan yili (ixtiyoriy).', null=True, validators=[django.core.validators.MinValueValidator(1900), django.core.validators.MaxValueValidator(2100)], verbose_name='birth year'),
        ),
        migrations.AddField(
            model_name='patient',
            name='drug_allergies',
            field=models.TextField(blank=True, help_text="Dorilarga allergiya haqida ma'lumot", verbose_name='drug allergies'),
        ),
        migrations.AddField(
            model_name='patient',
            name='height_cm',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Bemor bo‘yi santimetrda (ixtiyoriy).', max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0.0)], verbose_name='height (cm)'),
        ),
        migrations.AddField(
            model_name='patient',
            name='weight_kg',
            field=models.DecimalField(blank=True, decimal_places=2, help_text='Bemor vazni kilogrammda (ixtiyoriy).', max_digits=5, null=True, validators=[django.core.validators.MinValueValidator(0.0)], verbose_name='weight (kg)'),
        ),
    ]
