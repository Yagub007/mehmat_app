"""Study material serializers."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import Material


class MaterialListSerializer(serializers.ModelSerializer):
    """Lightweight representation for material listings."""

    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )

    class Meta:
        model = Material
        fields = (
            "id",
            "title",
            "category",
            "category_display",
            "thumbnail",
            "estimated_reading_time",
            "ordering",
            "created_at",
        )
        read_only_fields = fields


class MaterialDetailSerializer(serializers.ModelSerializer):
    """Full representation including the description and PDF file."""

    category_display = serializers.CharField(
        source="get_category_display", read_only=True
    )

    class Meta:
        model = Material
        fields = (
            "id",
            "title",
            "description",
            "category",
            "category_display",
            "pdf_file",
            "thumbnail",
            "estimated_reading_time",
            "ordering",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields
