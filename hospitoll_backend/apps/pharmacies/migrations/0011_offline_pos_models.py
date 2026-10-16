import uuid

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0010_remove_medicine_pharm_medic_act_name_idx_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='PharmacyPosDevice',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('name', models.CharField(max_length=120)),
                ('activation_code_hash', models.CharField(blank=True, max_length=64)),
                ('activation_code_created_at', models.DateTimeField(blank=True, null=True)),
                ('client_id', models.UUIDField(blank=True, null=True, unique=True)),
                ('is_active', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('activated_at', models.DateTimeField(blank=True, null=True)),
                ('last_seen_at', models.DateTimeField(blank=True, null=True)),
                ('pharmacy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pos_devices', to='pharmacies.pharmacy')),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.CreateModel(
            name='PharmacySale',
            fields=[
                ('id', models.UUIDField(editable=False, primary_key=True, serialize=False)),
                ('sold_at', models.DateTimeField()),
                ('total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('synced_at', models.DateTimeField(auto_now_add=True)),
                ('has_stock_discrepancy', models.BooleanField(default=False)),
                ('device', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='sales', to='pharmacies.pharmacyposdevice')),
                ('pharmacy', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='pos_sales', to='pharmacies.pharmacy')),
            ],
            options={
                'ordering': ['-sold_at'],
                'indexes': [
                    models.Index(fields=['pharmacy', 'sold_at'], name='pharm_pos_pharm_sold_idx'),
                    models.Index(fields=['device', 'sold_at'], name='pharm_pos_device_sold_idx'),
                ],
            },
        ),
        migrations.CreateModel(
            name='PharmacySaleLine',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('medicine_name', models.CharField(max_length=255)),
                ('quantity', models.PositiveIntegerField()),
                ('unit_price', models.DecimalField(decimal_places=2, max_digits=10)),
                ('line_total', models.DecimalField(decimal_places=2, max_digits=12)),
                ('stock_shortfall', models.PositiveIntegerField(default=0)),
                ('inventory', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pos_sale_lines', to='pharmacies.pharmacymarchandise')),
                ('medicine', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='pos_sale_lines', to='pharmacies.medicine')),
                ('sale', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lines', to='pharmacies.pharmacysale')),
            ],
        ),
    ]
