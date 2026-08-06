from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("medical", "0009_appointment_telegram_one_left_notified_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="appointment",
            name="auto_turn_last_reminder_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Last reminder timestamp for unanswered automatic queue prompt",
                null=True,
                verbose_name="auto queue last reminder at",
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="auto_turn_prompt_sent_at",
            field=models.DateTimeField(
                blank=True,
                help_text='When patient received "did you enter" prompt from automatic queue',
                null=True,
                verbose_name="auto queue prompt sent at",
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="auto_turn_responded_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When patient answered automatic queue entry prompt",
                null=True,
                verbose_name="auto queue responded at",
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="auto_turn_response",
            field=models.CharField(
                blank=True,
                choices=[("yes", "Ha"), ("no", "Yo'q")],
                help_text="Patient response to automatic queue entry prompt",
                max_length=8,
                null=True,
                verbose_name="auto queue response",
            ),
        ),
        migrations.AddField(
            model_name="appointment",
            name="auto_turn_started_at",
            field=models.DateTimeField(
                blank=True,
                help_text="When this appointment became the active patient in automatic queue mode",
                null=True,
                verbose_name="auto queue turn started at",
            ),
        ),
    ]
