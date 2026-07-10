"""``python manage.py import_materials`` — one-time import from a public folder.

Downloads a public Google Drive folder (no API key/credentials required) and
imports every file into the database, copying the files into ``MEDIA_ROOT`` and
recreating the folder hierarchy as categories.

Examples
--------
    # Download the public folder and import it
    python manage.py import_materials --url "https://drive.google.com/drive/folders/<id>"

    # Import an already-downloaded folder (skips the download step)
    python manage.py import_materials --source /path/to/downloaded/folder

    # Preview without writing anything
    python manage.py import_materials --source /path/to/folder --dry-run
"""
from __future__ import annotations

import tempfile

from django.core.management.base import BaseCommand, CommandError

from mehmat_app.services.material_import import MaterialImportService


class Command(BaseCommand):
    help = "Import study materials from a public Google Drive folder (one-time)."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--url",
            help="Public Drive folder URL to download and import.",
        )
        parser.add_argument(
            "--source",
            help="Path to an already-downloaded folder to import (skips download).",
        )
        parser.add_argument(
            "--root-name",
            help="Name of the top-level category (defaults to the folder name).",
        )
        parser.add_argument(
            "--exclude",
            nargs="*",
            default=["Тести"],
            help="Folder names to skip (default: Тести — tests are imported "
            "separately as JSON via import_tests).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report what would change without writing to the database.",
        )
        parser.add_argument(
            "--no-publish",
            dest="publish",
            action="store_false",
            help="Import as unpublished (hidden until reviewed).",
        )
        parser.set_defaults(publish=True)

    def handle(self, *args, **options) -> None:
        url = options.get("url")
        source = options.get("source")
        if not url and not source:
            raise CommandError("Provide --url (to download) or --source (existing folder).")

        service = MaterialImportService(
            publish=options["publish"], dry_run=options["dry_run"]
        )

        cleanup_dir: str | None = None
        download_failures: list[str] = []
        try:
            if not source:
                source = cleanup_dir = tempfile.mkdtemp(prefix="drive_import_")
                self.stdout.write(f"Downloading {url} …")
                try:
                    download_failures = service.download_folder(url, source)
                except Exception as exc:  # noqa: BLE001 - surface as command error
                    raise CommandError(f"Download failed: {exc}") from exc
                if download_failures:
                    self.stdout.write(self.style.WARNING(
                        f"{len(download_failures)} file(s) could not be downloaded "
                        "(Drive throttling); re-run later to fetch them."
                    ))

            self.stdout.write("Importing …")
            stats = service.import_tree(
                source,
                root_name=options.get("root_name"),
                exclude=set(options.get("exclude") or []),
            )
        finally:
            # A downloaded temp dir is safe to remove once all files imported;
            # keep it if some downloads failed so a re-run can resume from it.
            # A user-supplied --source is never deleted.
            if cleanup_dir and not options["dry_run"] and not download_failures:
                import shutil

                shutil.rmtree(cleanup_dir, ignore_errors=True)
            elif cleanup_dir and download_failures:
                self.stdout.write(
                    f"Partial download kept at {cleanup_dir} — re-run with "
                    f"--source {cleanup_dir} or the same --url to resume."
                )

        self._report(stats, dry_run=options["dry_run"])

    def _report(self, stats, *, dry_run: bool) -> None:
        header = "DRY RUN — no changes written" if dry_run else "Import complete"
        self.stdout.write(self.style.MIGRATE_HEADING(header))
        rows = [
            ("Categories created", stats.categories_created),
            ("Materials created", stats.materials_created),
            ("Materials updated", stats.materials_updated),
            ("Materials skipped (existing)", stats.materials_skipped),
        ]
        for label, value in rows:
            self.stdout.write(f"  {label:<32} {value}")

        if stats.errors:
            self.stdout.write(self.style.WARNING(f"\n{len(stats.errors)} error(s):"))
            for error in stats.errors[:20]:
                self.stdout.write(self.style.WARNING(f"  - {error}"))
            if len(stats.errors) > 20:
                self.stdout.write(
                    self.style.WARNING(f"  … and {len(stats.errors) - 20} more")
                )
        else:
            self.stdout.write(self.style.SUCCESS("\nNo errors."))
