from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0013_receptionstaff_compensation'),
    ]

    operations = [
        migrations.CreateModel(
            name='ReceptionStaffWorkRecord',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('date', models.DateField()),
                ('checked_in_at', models.TimeField(blank=True, null=True)),
                ('checked_out_at', models.TimeField(blank=True, null=True)),
                ('patients_count', models.PositiveIntegerField(default=0)),
                ('revenue', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('staff', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='work_records', to='clinics.receptionstaff')),
            ],
            options={'ordering': ['-date']},
        ),
        migrations.AddConstraint(
            model_name='receptionstaffworkrecord',
            constraint=models.UniqueConstraint(fields=('staff', 'date'), name='unique_reception_staff_work_day'),
        ),
    ]