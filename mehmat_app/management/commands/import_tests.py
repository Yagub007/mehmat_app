"""``python manage.py import_tests`` — import tests from JSON.

Tests are authored as JSON (not Word documents) and loaded into the Test /
Question / Choice models used by the app's testing system.

Examples
--------
    python manage.py import_tests path/to/tests.json
    python manage.py import_tests path/to/tests_dir/          # every *.json
    python manage.py import_tests tests.json --dry-run
    python manage.py import_tests tests.json --no-publish

See ``mehmat_app/services/test_import.py`` for the JSON schema, and
``sample_tests.json`` in the project root for a worked example.
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from mehmat_app.services.test_import import TestImportService


class Command(BaseCommand):
    help = "Import tests from a JSON file or a directory of JSON files."

    def add_arguments(self, parser) -> None:
        parser.add_argument("path", help="JSON file or directory of .json files.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and report without writing to the database.",
        )
        publish = parser.add_mutually_exclusive_group()
        publish.add_argument(
            "--publish", dest="publish", action="store_true", default=None,
            help="Force-publish all imported tests.",
        )
        publish.add_argument(
            "--no-publish", dest="publish", action="store_false",
            help="Import all tests as unpublished (overrides the JSON value).",
        )

    def handle(self, *args, **options) -> None:
        service = TestImportService(
            publish=options["publish"], dry_run=options["dry_run"]
        )
        try:
            stats = service.import_path(options["path"])
        except FileNotFoundError as exc:
            raise CommandError(str(exc)) from exc

        header = "DRY RUN — no changes written" if options["dry_run"] else "Import complete"
        self.stdout.write(self.style.MIGRATE_HEADING(header))
        self.stdout.write(f"  Tests created                    {stats.created}")
        self.stdout.write(f"  Tests updated                    {stats.updated}")
        self.stdout.write(f"  Questions imported               {stats.questions}")

        if stats.errors:
            self.stdout.write(self.style.WARNING(f"\n{len(stats.errors)} error(s):"))
            for error in stats.errors[:30]:
                self.stdout.write(self.style.WARNING(f"  - {error}"))
            if len(stats.errors) > 30:
                self.stdout.write(
                    self.style.WARNING(f"  … and {len(stats.errors) - 30} more")
                )
        else:
            self.stdout.write(self.style.SUCCESS("\nNo errors."))
