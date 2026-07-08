"""Notification views."""
from __future__ import annotations

from drf_spectacular.utils import extend_schema, inline_serializer
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from mehmat_app.models import Notification
from mehmat_app.permissions import IsOwner
from mehmat_app.serializers.notifications import NotificationSerializer


@extend_schema(tags=["notifications"])
class NotificationViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """List the user's notifications and manage their read state."""

    serializer_class = NotificationSerializer
    permission_classes = [IsAuthenticated, IsOwner]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Notification.objects.none()
        return Notification.objects.filter(user=self.request.user)

    @extend_schema(
        request=None,
        responses={200: NotificationSerializer},
        summary="Mark a single notification as read",
    )
    @action(detail=True, methods=["post"], url_path="read")
    def mark_read(self, request, pk=None):
        notification = self.get_object()
        if not notification.is_read:
            notification.is_read = True
            notification.save(update_fields=["is_read"])
        return Response(NotificationSerializer(notification).data)

    @extend_schema(
        request=None,
        responses={200: inline_serializer(
            "MarkAllReadResponse", {"updated": serializers.IntegerField()}
        )},
        summary="Mark all notifications as read",
    )
    @action(detail=False, methods=["post"], url_path="mark-all-read")
    def mark_all_read(self, request):
        updated = self.get_queryset().filter(is_read=False).update(is_read=True)
        return Response({"updated": updated})

    @extend_schema(
        responses={200: inline_serializer(
            "UnreadCountResponse", {"unread": serializers.IntegerField()}
        )},
        summary="Count unread notifications",
    )
    @action(detail=False, methods=["get"], url_path="unread-count")
    def unread_count(self, request):
        count = self.get_queryset().filter(is_read=False).count()
        return Response({"unread": count})
