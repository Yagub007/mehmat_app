"""Study material & category serializers."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import Category, Material


class CategorySerializer(serializers.ModelSerializer):
    """Flat category representation; ``parent`` lets clients rebuild the tree."""

    full_path = serializers.CharField(read_only=True)
    material_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "parent",
            "full_path",
            "ordering",
            "material_count",
        )
        read_only_fields = fields


class MaterialListSerializer(serializers.ModelSerializer):
    """Lightweight representation for material listings."""

    category_name = serializers.CharField(source="category.name", default="", read_only=True)
    category_slug = serializers.CharField(source="category.slug", default="", read_only=True)
    file_type_display = serializers.CharField(
        source="get_file_type_display", read_only=True
    )
    thumbnail = serializers.SerializerMethodField()

    class Meta:
        model = Material
        fields = (
            "id",
            "title",
            "slug",
            "category",
            "category_name",
            "category_slug",
            "subject",
            "file_type",
            "file_type_display",
            "thumbnail",
            "estimated_reading_time",
            "ordering",
            "created_at",
        )
        read_only_fields = fields

    def get_thumbnail(self, obj: Material) -> str | None:
        if not obj.thumbnail:
            return None
        request = self.context.get("request")
        url = obj.thumbnail.url
        return request.build_absolute_uri(url) if request else url


class MaterialDetailSerializer(MaterialListSerializer):
    """Full representation including description and the file/open URL."""

    file = serializers.SerializerMethodField()
    open_url = serializers.SerializerMethodField()

    class Meta(MaterialListSerializer.Meta):
        fields = MaterialListSerializer.Meta.fields + (
            "description",
            "file",
            "open_url",
            "updated_at",
        )
        read_only_fields = fields

    def _absolute(self, url: str) -> str:
        request = self.context.get("request")
        return request.build_absolute_uri(url) if request else url

    def get_file(self, obj: Material) -> str | None:
        if not obj.file:
            return None
        return self._absolute(obj.file.url)

    def get_open_url(self, obj: Material) -> str:
        return self._absolute(obj.open_url) if obj.open_url else ""
