from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('clinics', '0016_clinic_queue_ticket_number_size'),
    ]

    operations = [
        migrations.AddField(
            model_name='clinic',
            name='queue_ticket_show_address',
            field=models.BooleanField(default=True, help_text='Navbat qog‘ozida klinika manzilini chiqarish', verbose_name='show address on queue ticket'),
        ),
        migrations.AddField(
            model_name='clinic',
            name='queue_ticket_show_phone',
            field=models.BooleanField(default=False, help_text='Navbat qog‘ozida klinika telefon raqamini chiqarish', verbose_name='show phone on queue ticket'),
        ),
        migrations.AddField(
            model_name='clinic',
            name='queue_ticket_show_contact',
            field=models.BooleanField(default=True, help_text='Navbat qog‘ozida ijtimoiy tarmoq yoki sayt havolasini chiqarish', verbose_name='show contact on queue ticket'),
        ),
    ]
