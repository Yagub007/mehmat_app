"""Study material models."""
from __future__ import annotations

from django.core.validators import MinValueValidator
from django.db import models

from mehmat_app.constants import MaterialCategory
from mehmat_app.models.base import TimeStampedModel


class MaterialQuerySet(models.QuerySet):
    """Custom queryset for :class:`Material`."""

    def published(self) -> "MaterialQuerySet":
        """Return only published materials."""
        return self.filter(is_published=True)


class Material(TimeStampedModel):
    """A downloadable study material (PDF) with an optional thumbnail.

    Files are stored on the configured storage backend (filesystem by default);
    only their paths are persisted in the database.
    """

    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    category = models.CharField(
        max_length=20,
        choices=MaterialCategory.choices,
        default=MaterialCategory.OTHER,
        db_index=True,
    )
    pdf_file = models.FileField(upload_to="materials/pdf/%Y/%m/")
    thumbnail = models.ImageField(
        upload_to="materials/thumbnails/%Y/%m/",
        blank=True,
        null=True,
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
        ]

    def __str__(self) -> str:
        return self.title
