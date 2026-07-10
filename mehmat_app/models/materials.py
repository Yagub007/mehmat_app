"""Study material models.

Materials are organised through the hierarchical :class:`Category` model, which
mirrors the source folder tree. Each material's file is stored locally under
``MEDIA_ROOT`` and served through Django/whitenoise; only the relative path is
persisted in the database. See ``mehmat_app.services.material_import`` for the
one-time import pipeline that populates these tables from a public Drive folder.
"""
from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models
from django.utils.text import slugify

from mehmat_app.constants import FileType, MaterialCategory
from mehmat_app.models.base import TimeStampedModel


def _unique_slug(model: type[models.Model], value: str, *, instance_pk=None) -> str:
    """Return a slug for ``value`` guaranteed unique within ``model``.

    Falls back to the model name when ``value`` slugifies to an empty string
    (e.g. non-latin titles) and appends an incrementing suffix on collision.
    """
    base = slugify(value, allow_unicode=True) or model.__name__.lower()
    slug = base
    index = 2
    qs = model.objects.all()
    if instance_pk is not None:
        qs = qs.exclude(pk=instance_pk)
    while qs.filter(slug=slug).exists():
        slug = f"{base}-{index}"
        index += 1
    return slug


class Category(TimeStampedModel):
    """A study-material category, forming a tree that mirrors source folders.

    ``source_path`` (the folder's path relative to the import root) is the stable
    natural key, so re-running the import is idempotent and preserves IDs.
    """

    name = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True, allow_unicode=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        related_name="children",
        blank=True,
        null=True,
    )
    source_path = models.CharField(
        max_length=1000,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="Folder path relative to the import root (natural key).",
    )
    ordering = models.IntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=True, db_index=True)

    class Meta:
        verbose_name_plural = "categories"
        ordering = ("ordering", "name")
        indexes = [models.Index(fields=["parent", "is_published"])]

    def __str__(self) -> str:
        return self.full_path

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = _unique_slug(Category, self.name, instance_pk=self.pk)
        super().save(*args, **kwargs)

    @property
    def full_path(self) -> str:
        """Breadcrumb path from the root category, e.g. ``Root / Algebra``."""
        parts, node, guard = [], self, 0
        while node is not None and guard < 50:
            parts.append(node.name)
            node = node.parent
            guard += 1
        return " / ".join(reversed(parts))


class MaterialQuerySet(models.QuerySet):
    """Custom queryset for :class:`Material`."""

    def published(self) -> "MaterialQuerySet":
        """Return only published materials in published categories."""
        return self.filter(is_published=True).exclude(
            category__is_published=False
        )


class Material(TimeStampedModel):
    """A study material backed by a locally stored file of any type.

    Files (PDF, video, presentation, document, …) are downloaded once into
    ``MEDIA_ROOT`` and referenced by their relative path; the client opens them
    directly from the app's media host.
    """

    title = models.CharField(max_length=200, db_index=True)
    slug = models.SlugField(max_length=220, unique=True, allow_unicode=True, blank=True)
    description = models.TextField(blank=True)

    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        related_name="materials",
        blank=True,
        null=True,
    )
    # Coarse legacy subject kept for backward-compatible labels/filtering.
    subject = models.CharField(
        max_length=20,
        choices=MaterialCategory.choices,
        default=MaterialCategory.OTHER,
        db_index=True,
    )
    file_type = models.CharField(
        max_length=20,
        choices=FileType.choices,
        default=FileType.OTHER,
        db_index=True,
    )
    file = models.FileField(upload_to="materials/files/%Y/%m/", blank=True, null=True)
    thumbnail = models.ImageField(
        upload_to="materials/thumbnails/%Y/%m/", blank=True, null=True
    )
    source_path = models.CharField(
        max_length=1000,
        unique=True,
        blank=True,
        null=True,
        db_index=True,
        help_text="File path relative to the import root (natural key).",
    )

    estimated_reading_time = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Estimated reading time in minutes.",
    )
    ordering = models.IntegerField(default=0, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)

    objects = MaterialQuerySet.as_manager()

    class Meta:
        ordering = ("ordering", "-created_at")
        indexes = [
            models.Index(fields=["category", "is_published"]),
            models.Index(fields=["file_type", "is_published"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:
        if not self.slug:
            self.slug = _unique_slug(Material, self.title, instance_pk=self.pk)
        super().save(*args, **kwargs)

    @property
    def open_url(self) -> str:
        """URL for opening the material (its stored media file)."""
        if self.file:
            try:
                return self.file.url
            except ValueError:  # pragma: no cover - unsaved file
                return ""
        return ""
