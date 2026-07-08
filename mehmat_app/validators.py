"""Reusable validators for models, serializers and file uploads."""
from __future__ import annotations

from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.utils.deconstruct import deconstructible

MAX_PDF_SIZE_MB = 25
MAX_IMAGE_SIZE_MB = 5

validate_pdf_extension = FileExtensionValidator(allowed_extensions=["pdf"])
validate_image_extension = FileExtensionValidator(
    allowed_extensions=["jpg", "jpeg", "png", "webp"]
)


@deconstructible
class FileSizeValidator:
    """Validate that an uploaded file does not exceed ``max_mb`` megabytes."""

    def __init__(self, max_mb: int) -> None:
        self.max_mb = max_mb

    def __call__(self, value) -> None:
        limit = self.max_mb * 1024 * 1024
        if value.size and value.size > limit:
            raise ValidationError(
                f"File too large. Maximum size is {self.max_mb} MB."
            )

    def __eq__(self, other) -> bool:
        return isinstance(other, FileSizeValidator) and self.max_mb == other.max_mb


validate_pdf_size = FileSizeValidator(MAX_PDF_SIZE_MB)
validate_image_size = FileSizeValidator(MAX_IMAGE_SIZE_MB)
