"""Custom DRF permission classes."""
from __future__ import annotations

from rest_framework.permissions import SAFE_METHODS, BasePermission


class IsAdminUser(BasePermission):
    """Allow access only to application admins or Django superusers."""

    message = "Administrator privileges are required."

    def has_permission(self, request, view) -> bool:
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_admin or user.is_superuser)
        )


class IsOwner(BasePermission):
    """Object-level permission granting access only to the owning user."""

    message = "You do not have access to this resource."

    def has_object_permission(self, request, view, obj) -> bool:
        owner_id = getattr(obj, "user_id", None)
        return owner_id is not None and owner_id == request.user.id


class ReadOnly(BasePermission):
    """Allow only safe (read-only) HTTP methods."""

    def has_permission(self, request, view) -> bool:
        return request.method in SAFE_METHODS
