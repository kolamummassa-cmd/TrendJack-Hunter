from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('trends', '0003_trend_visible_to'),
    ]

    operations = [
        migrations.AddField(
            model_name='trend',
            name='expiry_warning_sent_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text=(
                    "When the 'this trend is about to be deleted' warning email was "
                    "sent, if it has been. Set by the expire_trends command. Trends "
                    "that already have a brief are never warned about or deleted — "
                    "this only applies to un-briefed trends approaching 3 days old."
                ),
            ),
        ),
    ]
