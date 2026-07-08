"""Views for reading a user's own submissions."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework import mixins, viewsets
from rest_framework.permissions import IsAuthenticated

from mehmat_app.models import Submission
from mehmat_app.permissions import IsOwner
from mehmat_app.serializers.submissions import (
    SubmissionListSerializer,
    SubmissionSerializer,
)


@extend_schema(tags=["submissions"])
class SubmissionViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List and retrieve the authenticated user's own submissions."""

    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Submission.objects.none()
        queryset = Submission.objects.filter(user=self.request.user).select_related("test")
        if self.action == "retrieve":
            queryset = queryset.prefetch_related("answers__selected_choices")
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return SubmissionSerializer
        return SubmissionListSerializer
