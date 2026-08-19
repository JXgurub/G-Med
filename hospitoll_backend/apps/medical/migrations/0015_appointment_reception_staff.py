from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('clinics', '0014_receptionstaff_work_record'),
        ('medical', '0014_appointment_selected_specialties'),
    ]

    operations = [
        migrations.AddField(
            model_name='appointment',
            name='reception_staff',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='appointments', to='clinics.receptionstaff'),
        ),
    ]