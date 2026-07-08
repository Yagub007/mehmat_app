"""Test-session lifecycle service (server-authoritative timer)."""
from __future__ import annotations

from datetime import timedelta

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied

from mehmat_app.models import Test, TestSession, User


@transaction.atomic
def start_session(*, user: User, test: Test) -> TestSession:
    """Create (or reuse) an active timer session for ``user`` on ``test``.

    Raises:
        PermissionDenied: If the test is not currently available.
    """
    if not test.is_available():
        raise PermissionDenied("This test is not currently available.")

    existing = (
        TestSession.objects.filter(user=user, test=test, is_completed=False)
        .order_by("-started_at")
        .first()
    )
    if existing and not existing.is_expired:
        return existing

    now = timezone.now()
    return TestSession.objects.create(
        user=user,
        test=test,
        started_at=now,
        expires_at=now + timedelta(seconds=test.duration_seconds),
    )
