"""One-time import of study materials from a public Google Drive folder.

The public folder is downloaded with :mod:`gdown` (no API key, credentials or
service account required); this module then walks the downloaded tree and, for
each folder, upserts a :class:`Category` (preserving hierarchy) and, for each
file, upserts a :class:`Material` whose file is copied into ``MEDIA_ROOT``.

The import is idempotent: folders/files are keyed by their path relative to the
import root, so re-running never duplicates and preserves existing primary keys.
Per-item errors are collected rather than raised, so one bad file never aborts
the migration.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from django.core.files import File
from django.db import transaction

from mehmat_app.constants import FileType, MaterialCategory
from mehmat_app.models import Category, Material
from mehmat_app.models.materials import _unique_slug

logger = logging.getLogger(__name__)


# --- File-type classification by extension -----------------------------------
_EXT_TO_TYPE: dict[str, str] = {
    ".pdf": FileType.PDF,
    ".mp4": FileType.VIDEO,
    ".mov": FileType.VIDEO,
    ".m4v": FileType.VIDEO,
    ".avi": FileType.VIDEO,
    ".mkv": FileType.VIDEO,
    ".webm": FileType.VIDEO,
    ".ppt": FileType.PRESENTATION,
    ".pptx": FileType.PRESENTATION,
    ".key": FileType.PRESENTATION,
    ".odp": FileType.PRESENTATION,
    ".doc": FileType.DOCUMENT,
    ".docx": FileType.DOCUMENT,
    ".odt": FileType.DOCUMENT,
    ".rtf": FileType.DOCUMENT,
    ".txt": FileType.DOCUMENT,
    ".xls": FileType.SPREADSHEET,
    ".xlsx": FileType.SPREADSHEET,
    ".csv": FileType.SPREADSHEET,
    ".ods": FileType.SPREADSHEET,
    ".png": FileType.IMAGE,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".gif": FileType.IMAGE,
    ".webp": FileType.IMAGE,
    ".svg": FileType.IMAGE,
    ".heic": FileType.IMAGE,
    ".mp3": FileType.AUDIO,
    ".wav": FileType.AUDIO,
    ".ogg": FileType.AUDIO,
    ".m4a": FileType.AUDIO,
    ".zip": FileType.ARCHIVE,
    ".rar": FileType.ARCHIVE,
    ".7z": FileType.ARCHIVE,
}

# Keyword → legacy subject, keeps the coarse subject label meaningful.
_SUBJECT_KEYWORDS: tuple[tuple[str, str], ...] = (
    ("алгебр", MaterialCategory.ALGEBRA),
    ("algebra", MaterialCategory.ALGEBRA),
    ("геометр", MaterialCategory.GEOMETRY),
    ("трикутник", MaterialCategory.GEOMETRY),
    ("вектор", MaterialCategory.GEOMETRY),
    ("geometr", MaterialCategory.GEOMETRY),
    ("функц", MaterialCategory.FUNCTIONS),
    ("графік", MaterialCategory.FUNCTIONS),
    ("function", MaterialCategory.FUNCTIONS),
    ("похідн", MaterialCategory.DERIVATIVES),
    ("derivativ", MaterialCategory.DERIVATIVES),
    ("ймовірн", MaterialCategory.PROBABILITY),
    ("статистик", MaterialCategory.PROBABILITY),
    ("probab", MaterialCategory.PROBABILITY),
)

# Files gdown may leave behind on interrupted downloads; never imported.
_SKIP_NAMES = {".ds_store"}
_SKIP_SUFFIXES = (".part", ".tmp", ".crdownload")

_BYTES_PER_MINUTE = 60_000

# Folder-name keywords that force a file type regardless of extension, so a
# section stays coherent (e.g. a PDF exported from a slide deck, sitting in the
# "Презентації" folder, is shown as a presentation — not a PDF).
_FOLDER_TYPE_OVERRIDES: tuple[tuple[str, str], ...] = (
    ("презентац", FileType.PRESENTATION),
    ("presentation", FileType.PRESENTATION),
    ("відео", FileType.VIDEO),
    ("video", FileType.VIDEO),
)
# Extension-based types that a folder-context override is allowed to replace.
# (We never override an actual video/image/audio into a presentation.)
_OVERRIDABLE_TYPES = {FileType.PDF, FileType.DOCUMENT, FileType.OTHER}


def classify_file_type(path: str) -> str:
    """Classify by extension, then apply folder-context overrides.

    ``path`` may be a bare filename or a relative path; when it includes a
    parent folder such as "Презентації", the override makes every file there a
    presentation even if it is a PDF export.
    """
    base = _EXT_TO_TYPE.get(Path(path).suffix.lower(), FileType.OTHER)
    if base in _OVERRIDABLE_TYPES:
        lowered = path.lower()
        for keyword, forced in _FOLDER_TYPE_OVERRIDES:
            if keyword in lowered:
                return forced
    return base


def _clean_title(filename: str) -> str:
    return Path(filename).stem.strip() or filename


def _infer_subject(path: str) -> str:
    lowered = path.lower()
    for keyword, subject in _SUBJECT_KEYWORDS:
        if keyword in lowered:
            return subject
    return MaterialCategory.OTHER


def _estimate_reading_time(file_type: str, size_bytes: int) -> int:
    # A size-based estimate is only meaningful for text documents; for slides,
    # video, audio and images it is misleading, so we don't show one.
    if file_type not in {FileType.PDF, FileType.DOCUMENT} or not size_bytes:
        return 0
    # Cap the estimate so a large scanned PDF never shows an absurd duration.
    return max(1, min(90, round(size_bytes / _BYTES_PER_MINUTE)))


def _should_skip(name: str) -> bool:
    lowered = name.lower()
    return lowered in _SKIP_NAMES or lowered.endswith(_SKIP_SUFFIXES)


@dataclass
class ImportStats:
    categories_created: int = 0
    materials_created: int = 0
    materials_updated: int = 0
    materials_skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "categories_created": self.categories_created,
            "materials_created": self.materials_created,
            "materials_updated": self.materials_updated,
            "materials_skipped": self.materials_skipped,
            "errors": len(self.errors),
        }


class MaterialImportService:
    """Downloads a public Drive folder and imports its tree into the database."""

    def __init__(self, *, publish: bool = True, dry_run: bool = False) -> None:
        self._publish = publish
        self._dry_run = dry_run
        self.stats = ImportStats()

    # -- download ----------------------------------------------------------
    @staticmethod
    def download_folder(
        url: str, dest: str, *, quiet: bool = True, retries: int = 4
    ) -> list[str]:
        """Download a public Drive folder into ``dest`` resiliently.

        Enumerates the whole tree first, then downloads each file individually
        with retries/backoff and resume, so a single rate-limited or blocked
        file (Google throttles anonymous downloads) never aborts the rest.
        Already-present files are skipped, making the download itself resumable.

        Returns the list of relative paths that could not be downloaded (empty
        on full success) so the caller can report and safely re-run later.
        """
        import time

        import gdown  # imported lazily; only needed when downloading

        os.makedirs(dest, exist_ok=True)
        manifest = gdown.download_folder(
            url=url, output=dest, skip_download=True, use_cookies=False, quiet=quiet
        )
        if not manifest:
            raise RuntimeError(
                "Could not read the folder. Make sure the link is a public "
                "'Anyone with the link' Drive folder."
            )

        failures: list[str] = []
        for item in manifest:
            local_path = item.local_path
            if os.path.exists(local_path) and os.path.getsize(local_path) > 0:
                continue
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            output = (
                local_path
                if os.path.splitext(local_path)[1]
                else os.path.dirname(local_path) + os.sep
            )
            for attempt in range(retries):
                try:
                    result = gdown.download(
                        id=item.id, output=output, quiet=quiet,
                        use_cookies=False, resume=True,
                    )
                    if result:
                        break
                except Exception as exc:  # noqa: BLE001 - retry then give up
                    logger.warning("Download error for %s: %s", item.path, exc)
                if attempt < retries - 1:
                    time.sleep(min(3 * 2 ** attempt, 60))
            else:
                failures.append(item.path)
                logger.warning("Giving up on %s after %s attempts", item.path, retries)

        if failures:
            logger.warning("%s file(s) could not be downloaded", len(failures))
        return failures

    # -- import ------------------------------------------------------------
    def import_tree(
        self,
        root_dir: str,
        *,
        root_name: str | None = None,
        exclude: set[str] | None = None,
    ) -> ImportStats:
        """Walk ``root_dir`` and upsert categories + materials.

        ``root_name`` names the top-level category that wraps the whole tree;
        when omitted the folder's basename is used. ``exclude`` is a set of
        folder names to skip entirely (e.g. ``{"Тести"}`` — tests are handled
        separately as structured JSON, not imported as file materials).
        """
        root = Path(root_dir).resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Import source directory not found: {root}")

        excluded = {name.casefold() for name in (exclude or set())}
        root_name = root_name or root.name
        # Map a folder's relative path -> Category (root uses ".").
        cache: dict[str, Category] = {}
        cache["."] = self._upsert_category(root_name, ".", parent=None, order=0)

        for dirpath, dirnames, filenames in os.walk(root):
            # Prune excluded folders in-place so os.walk never descends into them.
            dirnames[:] = [d for d in dirnames if d.casefold() not in excluded]
            dirnames.sort()
            filenames.sort()
            rel_dir = os.path.relpath(dirpath, root)
            category = cache.get(rel_dir)
            if category is None:  # pragma: no cover - defensive
                continue

            for order, dirname in enumerate(dirnames):
                child_rel = os.path.normpath(os.path.join(rel_dir, dirname))
                try:
                    cache[child_rel] = self._upsert_category(
                        dirname, child_rel, parent=category, order=order
                    )
                except Exception as exc:  # noqa: BLE001
                    self.stats.errors.append(f"folder '{child_rel}': {exc}")
                    logger.exception("Failed to import folder %s", child_rel)

            for order, filename in enumerate(filenames):
                if _should_skip(filename):
                    continue
                abs_path = os.path.join(dirpath, filename)
                rel_path = os.path.normpath(os.path.join(rel_dir, filename))
                try:
                    self._upsert_material(abs_path, rel_path, category, order)
                except Exception as exc:  # noqa: BLE001
                    self.stats.errors.append(f"file '{rel_path}': {exc}")
                    logger.exception("Failed to import file %s", rel_path)

        logger.info("Material import finished: %s", self.stats.as_dict())
        return self.stats

    # -- helpers -----------------------------------------------------------
    def _upsert_category(
        self, name: str, source_path: str, *, parent: Category | None, order: int
    ) -> Category:
        if self._dry_run:
            existing = Category.objects.filter(source_path=source_path).first()
            if existing:
                return existing
            self.stats.categories_created += 1
            return Category(name=name, source_path=source_path, parent=parent)

        with transaction.atomic():
            category, created = Category.objects.get_or_create(
                source_path=source_path,
                defaults={
                    "name": name,
                    "parent": parent,
                    "ordering": order,
                    "is_published": self._publish,
                },
            )
            if created:
                self.stats.categories_created += 1
            elif category.name != name or category.parent_id != (parent.id if parent else None):
                category.name = name
                category.parent = parent
                category.save(update_fields=["name", "parent", "updated_at"])
        return category

    def _upsert_material(
        self, abs_path: str, source_path: str, category: Category, order: int
    ) -> None:
        size = os.path.getsize(abs_path)
        file_type = classify_file_type(source_path)
        title = _clean_title(os.path.basename(abs_path))

        if self._dry_run:
            if Material.objects.filter(source_path=source_path).exists():
                self.stats.materials_skipped += 1
            else:
                self.stats.materials_created += 1
            return

        existing = Material.objects.filter(source_path=source_path).first()
        material = existing or Material(source_path=source_path)

        # Refresh metadata on every run (cheap; lets re-imports pick up changed
        # classification/titles) while preserving the file, id, slug and the
        # publish state chosen by an admin.
        material.title = title
        material.category = category
        material.subject = _infer_subject(source_path)
        material.file_type = file_type
        material.ordering = order
        material.estimated_reading_time = _estimate_reading_time(file_type, size)
        if existing is None:
            material.is_published = self._publish
            material.slug = _unique_slug(Material, title)

        # Only copy the file when it is not already stored (never re-download).
        need_copy = not (material.file and material.file.storage.exists(material.file.name))
        with transaction.atomic():
            if need_copy:
                with open(abs_path, "rb") as handle:
                    material.file.save(
                        os.path.basename(abs_path), File(handle), save=False
                    )
            material.save()

        if existing is None:
            self.stats.materials_created += 1
        else:
            self.stats.materials_updated += 1
