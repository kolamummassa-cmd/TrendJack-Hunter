from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('trends', '0002_pipelinerun'),
    ]

    operations = [
        migrations.AddField(
            model_name='trend',
            name='visible_to',
            field=models.ManyToManyField(
                blank=True,
                help_text=(
                    "Users who have 'unlocked' this trend by triggering at least one "
                    "refresh since signing up. Trend data itself stays global/shared "
                    "(same real-world trends for everyone) — this field only controls "
                    "who currently sees it on their dashboard, so a brand new signup "
                    "starts with an empty dashboard until they refresh."
                ),
                related_name='visible_trends',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
