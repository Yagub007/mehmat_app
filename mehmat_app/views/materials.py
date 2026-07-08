"""Study material views."""
from __future__ import annotations

from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from mehmat_app.models import Material
from mehmat_app.permissions import ReadOnly
from mehmat_app.serializers.materials import (
    MaterialDetailSerializer,
    MaterialListSerializer,
)


@extend_schema(tags=["materials"])
class MaterialViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only access to published study materials.

    Supports full-text search over ``title``/``description``, filtering by
    ``category`` and ordering by ``ordering``/``created_at``.
    """

    permission_classes = [IsAuthenticated, ReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category"]
    search_fields = ["title", "description"]
    ordering_fields = ["ordering", "created_at", "estimated_reading_time"]
    ordering = ["ordering", "-created_at"]

    def get_queryset(self):
        return Material.objects.published()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return MaterialDetailSerializer
        return MaterialListSerializer
