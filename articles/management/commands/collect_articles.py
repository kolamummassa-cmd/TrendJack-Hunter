from django.core.management.base import BaseCommand

from articles.services.collector import collect_all


class Command(BaseCommand):
    help = "Fetch all configured RSS sources and save new articles to the database."

    def handle(self, *args, **options):
        self.stdout.write("Collecting articles from RSS sources...\n")

        summary = collect_all()

        total_new = 0
        total_skipped = 0

        for row in summary:
            if row["error"]:
                self.stdout.write(
                    self.style.ERROR(f"  ✗ {row['source']}: failed — {row['error']}")
                )
                continue

            total_new += row["new"]
            total_skipped += row["skipped"]
            self.stdout.write(
                f"  ✓ {row['source']}: {row['new']} new, {row['skipped']} skipped"
            )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {total_new} new articles saved, {total_skipped} skipped (duplicates/invalid)."
            )
        )
