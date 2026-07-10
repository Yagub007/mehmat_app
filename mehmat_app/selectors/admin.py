"""Read-side aggregation powering the admin dashboard."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncDate
from django.utils import timezone

from mehmat_app.models import (
    Achievement,
    Material,
    Question,
    Submission,
    Test,
    User,
)


def _timeseries(queryset, *, days: int, date_field: str) -> list[dict[str, Any]]:
    """Return a dense ``[{date, count}]`` series for the last ``days`` days."""
    since = timezone.now() - timedelta(days=days - 1)
    rows = (
        queryset.filter(**{f"{date_field}__gte": since})
        .annotate(day=TruncDate(date_field))
        .values("day")
        .annotate(count=Count("id"))
    )
    counts = {row["day"].isoformat(): row["count"] for row in rows if row["day"]}
    today = timezone.now().date()
    series: list[dict[str, Any]] = []
    for offset in range(days - 1, -1, -1):
        day = (today - timedelta(days=offset)).isoformat()
        series.append({"date": day, "count": counts.get(day, 0)})
    return series


def dashboard_overview(*, days: int = 14) -> dict[str, Any]:
    """Aggregate the headline stats, charts and recent activity for the dashboard."""
    now = timezone.now()
    active_since = now - timedelta(days=7)

    user_totals = User.objects.aggregate(
        total=Count("id"),
        points=Coalesce(Sum("points"), 0),
    )
    active_users = User.objects.filter(last_login__gte=active_since).count()

    submissions = Submission.objects.all()

    totals = {
        "users": user_totals["total"],
        "active_users": active_users,
        "materials": Material.objects.count(),
        "tests": Test.objects.count(),
        "published_tests": Test.objects.filter(is_published=True).count(),
        "questions": Question.objects.count(),
        "submissions": submissions.count(),
        "official_submissions": submissions.filter(is_official=True).count(),
        "achievements": Achievement.objects.count(),
        "total_points": user_totals["points"],
    }

    charts = {
        "registrations": _timeseries(User.objects.all(), days=days, date_field="date_joined"),
        "submissions": _timeseries(submissions, days=days, date_field="submitted_at"),
    }

    latest_registrations = [
        {
            "id": u.id,
            "username": u.username,
            "full_name": u.full_name,
            "photo_url": u.photo_url,
            "points": u.points,
            "date_joined": u.date_joined,
        }
        for u in User.objects.order_by("-date_joined")[:8]
    ]

    latest_submissions = [
        {
            "id": s.id,
            "user_id": s.user_id,
            "user_name": s.user.username or s.user.full_name,
            "test_title": s.test.title,
            "score": float(s.score),
            "points_earned": s.points_earned,
            "is_official": s.is_official,
            "submitted_at": s.submitted_at,
        }
        for s in submissions.select_related("user", "test").order_by("-submitted_at")[:8]
    ]

    return {
        "totals": totals,
        "charts": charts,
        "latest_registrations": latest_registrations,
        "latest_submissions": latest_submissions,
    }
