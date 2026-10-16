from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0012_pharmacy_saleline_stock_mismatch'),
        ('printers', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='printerdevice',
            name='clinic',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='printer_devices',
                to='clinics.clinic',
            ),
        ),
        migrations.AddField(
            model_name='printerdevice',
            name='pharmacy',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='printer_devices',
                to='pharmacies.pharmacy',
            ),
        ),
        migrations.AddField(
            model_name='printerdevice',
            name='pos_device',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='printer_device',
                to='pharmacies.pharmacyposdevice',
            ),
        ),
        migrations.AddIndex(
            model_name='printerdevice',
            index=models.Index(fields=['pharmacy', 'status'], name='printers_pharmacy_status_idx'),
        ),
        migrations.AlterField(
            model_name='printjob',
            name='clinic',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='print_jobs',
                to='clinics.clinic',
            ),
        ),
        migrations.AddField(
            model_name='printjob',
            name='pharmacy',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='print_jobs',
                to='pharmacies.pharmacy',
            ),
        ),
        migrations.AddField(
            model_name='printjob',
            name='sale',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='print_job',
                to='pharmacies.pharmacysale',
            ),
        ),
    ]
