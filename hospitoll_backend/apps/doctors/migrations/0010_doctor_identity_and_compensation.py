from django.db import migrations, models
import django.core.validators


class Migration(migrations.Migration):

    dependencies = [
        ('doctors', '0009_doctor_first_work_month'),
    ]

    operations = [
        migrations.AddField(
            model_name='doctor',
            name='compensation_type',
            field=models.CharField(
                choices=[('salary', 'Salary'), ('percent', 'Percent')],
                default='salary',
                help_text='Ish haqi turi: salary yoki percent',
                max_length=20,
                verbose_name='compensation type',
            ),
        ),
        migrations.AddField(
            model_name='doctor',
            name='compensation_value',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                help_text='Ish haqi summasi yoki foiz qiymati',
                max_digits=12,
                null=True,
                validators=[django.core.validators.MinValueValidator(0)],
                verbose_name='compensation value',
            ),
        ),
        migrations.AddField(
            model_name='doctor',
            name='date_of_birth',
            field=models.DateField(blank=True, help_text="Doktor tug'ilgan sanasi", null=True, verbose_name='date of birth'),
        ),
        migrations.AddField(
            model_name='doctor',
            name='passport_id',
            field=models.CharField(blank=True, db_index=True, help_text='Doktorning pasport yoki ID raqami', max_length=50, null=True, verbose_name='passport id'),
        ),
    ]
