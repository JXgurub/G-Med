from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("doctors", "0018_doctor_display_order"),
    ]

    operations = [
        migrations.AlterField(
            model_name="doctor",
            name="slot_minutes",
            field=models.PositiveSmallIntegerField(
                choices=[
                    (10, "10"),
                    (20, "20"),
                    (30, "30"),
                    (40, "40"),
                    (50, "50"),
                    (60, "60"),
                    (80, "80"),
                    (120, "120"),
                ],
                default=30,
                help_text="Appointment slot duration in minutes (10/20/30/40/50/60/80/120)",
                validators=[MinValueValidator(10), MaxValueValidator(120)],
                verbose_name="slot minutes",
            ),
        ),
    ]
