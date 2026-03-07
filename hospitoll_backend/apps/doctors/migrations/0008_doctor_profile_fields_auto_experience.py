from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0007_doctor_pinfl_and_nullable_clinic'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='certificate_document',
            field=models.FileField(blank=True, null=True, upload_to='doctor_certificates/%Y/%m/%d/', verbose_name='certificate document'),
        ),
        migrations.AddField(
            model_name='doctor',
            name='diploma_number',
            field=models.CharField(blank=True, help_text='Doktorning diplom raqami', max_length=100, verbose_name='diploma number'),
        ),
        migrations.AddField(
            model_name='doctor',
            name='first_work_year',
            field=models.PositiveSmallIntegerField(blank=True, help_text='Doktor ish boshlagan birinchi yil', null=True, validators=[django.core.validators.MinValueValidator(1950), django.core.validators.MaxValueValidator(2100)], verbose_name='first work year'),
        ),
    ]
