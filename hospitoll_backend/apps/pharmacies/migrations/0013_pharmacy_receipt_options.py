from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('pharmacies', '0012_pharmacy_saleline_stock_mismatch'),
    ]

    operations = [
        migrations.AddField(
            model_name='pharmacy',
            name='receipt_show_address',
            field=models.BooleanField(default=True, help_text='Dorixona chekida manzilni chiqarish', verbose_name='show address on receipt'),
        ),
        migrations.AddField(
            model_name='pharmacy',
            name='receipt_show_phone',
            field=models.BooleanField(default=True, help_text='Dorixona chekida telefon raqamini chiqarish', verbose_name='show phone on receipt'),
        ),
        migrations.AddField(
            model_name='pharmacy',
            name='receipt_show_website',
            field=models.BooleanField(default=False, help_text='Dorixona chekida sayt havolasini chiqarish', verbose_name='show website on receipt'),
        ),
        migrations.AddField(
            model_name='pharmacy',
            name='receipt_instagram_url',
            field=models.CharField(blank=True, default='', help_text='Chekda chiqariladigan Instagram manzili yoki nomi', max_length=255, verbose_name='receipt Instagram URL'),
        ),
        migrations.AddField(
            model_name='pharmacy',
            name='receipt_show_instagram',
            field=models.BooleanField(default=False, help_text='Dorixona chekida Instagram manzilini chiqarish', verbose_name='show Instagram on receipt'),
        ),
    ]
