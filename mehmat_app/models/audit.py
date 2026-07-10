"""Audit logging for administrator actions."""
from __future__ import annotations

from django.conf import settings
from django.db import models


class AdminAuditLog(models.Model):
    """An immutable record of a single administrator action.

    Every mutating action performed through the admin API appends a row here so
    that changes are traceable: who did what, to which object, when, and how the
    value changed. Rows are never edited or deleted through the application.
    """

    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_actions",
    )
    action = models.CharField(max_length=64, db_index=True)
    target_type = models.CharField(max_length=64, blank=True, db_index=True)
    target_id = models.CharField(max_length=64, blank=True)
    target_label = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["target_type", "target_id"]),
            models.Index(fields=["admin", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.action} by {self.admin_id} @ {self.created_at:%Y-%m-%d %H:%M}"
