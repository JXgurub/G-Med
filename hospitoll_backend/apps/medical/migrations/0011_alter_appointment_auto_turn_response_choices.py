from django.db import migrations, models
from django.utils.translation import gettext_lazy as _


class Migration(migrations.Migration):

    dependencies = [
        ('medical', '0010_appointment_auto_queue_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='appointment',
            name='auto_turn_response',
            field=models.CharField(
                blank=True,
                choices=[
                    ('yes', _('Ha')),
                    ('wait', _('Kutyapman')),
                    ('cancel', _('Bekor qilish')),
                    ('no', _('Yo\'q (legacy)')),
                ],
                help_text='Patient response to automatic queue entry prompt',
                max_length=8,
                null=True,
                verbose_name='auto queue response',
            ),
        ),
    ]
