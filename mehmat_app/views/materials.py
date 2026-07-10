"""Study material & category views."""
from __future__ import annotations

import django_filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from mehmat_app.models import Category, Material
from mehmat_app.permissions import ReadOnly
from mehmat_app.selectors.materials import published_categories_with_counts, subtree_ids
from mehmat_app.serializers.materials import (
    CategorySerializer,
    MaterialDetailSerializer,
    MaterialListSerializer,
)


class MaterialFilterSet(django_filters.FilterSet):
    """Filter materials by category (slug or id), subject and file type.

    Filtering by a category includes materials in its whole subtree, so a
    top-level subject returns everything nested beneath it.
    """

    category = django_filters.CharFilter(method="filter_category")
    subject = django_filters.CharFilter(field_name="subject")
    file_type = django_filters.CharFilter(field_name="file_type")

    class Meta:
        model = Material
        fields = ["category", "subject", "file_type"]

    def filter_category(self, queryset, name, value):
        """Accept a numeric category id or slug; match the whole subtree."""
        lookup = {"pk": int(value)} if value.isdigit() else {"slug": value}
        root = Category.objects.filter(**lookup).values_list("id", flat=True).first()
        if root is None:
            return queryset.none()
        return queryset.filter(category_id__in=subtree_ids(root))


@extend_schema(tags=["materials"])
class MaterialViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only access to published study materials.

    Supports search over ``title``/``description``, filtering by
    ``category``/``subject``/``file_type`` and ordering by
    ``ordering``/``created_at``.
    """

    permission_classes = [IsAuthenticated, ReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = MaterialFilterSet
    search_fields = ["title", "description"]
    ordering_fields = ["ordering", "created_at", "estimated_reading_time"]
    ordering = ["ordering", "-created_at"]

    def get_queryset(self):
        return Material.objects.published().select_related("category")

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MaterialDetailSerializer
        return MaterialListSerializer


@extend_schema(tags=["materials"])
class CategoryViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Read-only list of published categories with subtree material counts."""

    permission_classes = [IsAuthenticated, ReadOnly]
    serializer_class = CategorySerializer
    pagination_class = None

    def get_queryset(self):
        return published_categories_with_counts()
