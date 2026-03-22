from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0008_rename_pharmacies__catego_9c59ef_idx_pharmacies__categor_0908e3_idx'),
    ]

    operations = [
        migrations.AddIndex(
            model_name='medicine',
            index=models.Index(fields=['is_active', 'name'], name='pharm_medic_act_name_idx'),
        ),
        migrations.AddIndex(
            model_name='medicine',
            index=models.Index(fields=['is_active', 'generic_name'], name='pharm_medic_act_gname_idx'),
        ),
    ]
