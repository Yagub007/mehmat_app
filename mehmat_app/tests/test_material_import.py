"""Tests for the one-time material import pipeline.

Builds a temporary folder tree (mirroring a downloaded Drive folder) and imports
it into a temporary ``MEDIA_ROOT``, so hierarchy, file copying, classification
and idempotency are exercised without any network access.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from django.test import TestCase, override_settings

from mehmat_app.constants import FileType
from mehmat_app.models import Category, Material
from mehmat_app.services.material_import import MaterialImportService, classify_file_type

_MEDIA = tempfile.mkdtemp(prefix="test_media_")


def _build_tree(root: Path) -> None:
    (root / "Відео" / "Трикутники").mkdir(parents=True)
    (root / "Презентації").mkdir(parents=True)
    (root / "Відео" / "Трикутники" / "Види.mp4").write_bytes(b"fake-video")
    (root / "Презентації" / "Вектори.pptx").write_bytes(b"fake-slides")
    (root / "Презентації" / "Координати.pdf").write_bytes(b"fake-pdf" * 10_000)
    (root / ".DS_Store").write_bytes(b"junk")
    (root / "Відео" / "partial.mp4.part").write_bytes(b"incomplete")


class ClassifyTests(TestCase):
    def test_extension_classification(self) -> None:
        self.assertEqual(classify_file_type("a.pdf"), FileType.PDF)
        self.assertEqual(classify_file_type("a.MP4"), FileType.VIDEO)
        self.assertEqual(classify_file_type("a.pptx"), FileType.PRESENTATION)
        self.assertEqual(classify_file_type("a.docx"), FileType.DOCUMENT)
        self.assertEqual(classify_file_type("a.unknown"), FileType.OTHER)

    def test_folder_context_override(self) -> None:
        # A PDF (or doc) inside a "Презентації" folder is shown as a presentation.
        self.assertEqual(
            classify_file_type("Презентації/Вектори/Вектори.pdf"),
            FileType.PRESENTATION,
        )
        # But a real video is never coerced into a presentation.
        self.assertEqual(
            classify_file_type("Презентації/clip.mp4"), FileType.VIDEO
        )


@override_settings(MEDIA_ROOT=_MEDIA)
class MaterialImportTests(TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "Матеріали"
        self.root.mkdir()
        _build_tree(self.root)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _import(self, **kwargs):
        service = MaterialImportService(**kwargs)
        return service.import_tree(str(self.root), root_name="Матеріали НМТ")

    def test_imports_hierarchy_and_copies_files(self) -> None:
        stats = self._import()

        # root + Відео + Трикутники + Презентації
        self.assertEqual(Category.objects.count(), 4)
        self.assertEqual(Material.objects.count(), 3)
        self.assertEqual(stats.materials_created, 3)
        self.assertEqual(stats.errors, [])

        root = Category.objects.get(source_path=".")
        self.assertEqual(root.name, "Матеріали НМТ")
        tri = Category.objects.get(name="Трикутники")
        self.assertEqual(tri.full_path, "Матеріали НМТ / Відео / Трикутники")

        video = Material.objects.get(title="Види")
        self.assertEqual(video.file_type, FileType.VIDEO)
        self.assertEqual(video.category, tri)
        self.assertTrue(video.slug)
        self.assertTrue(video.is_published)
        # File was actually copied into MEDIA_ROOT.
        self.assertTrue(video.file)
        self.assertTrue(os.path.exists(video.file.path))
        self.assertTrue(video.open_url)

    def test_junk_and_partial_files_skipped(self) -> None:
        self._import()
        titles = set(Material.objects.values_list("title", flat=True))
        self.assertNotIn(".DS_Store", titles)
        self.assertFalse(Material.objects.filter(title__icontains="partial").exists())

    def test_rerun_is_idempotent(self) -> None:
        self._import()
        ids = set(Material.objects.values_list("id", flat=True))
        files = dict(Material.objects.values_list("id", "file"))

        # Re-import refreshes metadata in place: no new rows, ids preserved,
        # and stored files are not re-copied.
        stats = self._import()
        self.assertEqual(Material.objects.count(), 3)
        self.assertEqual(stats.materials_created, 0)
        self.assertEqual(stats.materials_updated, 3)
        self.assertEqual(set(Material.objects.values_list("id", flat=True)), ids)
        self.assertEqual(dict(Material.objects.values_list("id", "file")), files)

    def test_dry_run_writes_nothing(self) -> None:
        stats = MaterialImportService(dry_run=True).import_tree(
            str(self.root), root_name="Матеріали НМТ"
        )
        self.assertEqual(Category.objects.count(), 0)
        self.assertEqual(Material.objects.count(), 0)
        self.assertEqual(stats.materials_created, 3)
