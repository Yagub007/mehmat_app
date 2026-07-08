"""Read-side queries for the leaderboard."""
from __future__ import annotations

from django.db.models import Count, IntegerField, Q, QuerySet, Sum
from django.db.models.functions import Coalesce

from mehmat_app.models import User

# Whitelist of orderings a client may request, mapped to safe ORM expressions.
LEADERBOARD_ORDERINGS: dict[str, tuple[str, ...]] = {
    "points": ("-points", "total_completion_time", "id"),
    "completion_time": ("total_completion_time", "-points", "id"),
    "completed_tests": ("-completed_tests", "-points", "id"),
}
DEFAULT_ORDERING = "points"


def leaderboard_queryset(ordering: str = DEFAULT_ORDERING) -> QuerySet[User]:
    """Return active users annotated for leaderboard display and ordered safely."""
    order_by = LEADERBOARD_ORDERINGS.get(ordering, LEADERBOARD_ORDERINGS[DEFAULT_ORDERING])
    return (
        User.objects.filter(is_active=True)
        .annotate(
            total_completion_time=Coalesce(
                Sum(
                    "submissions__completion_time",
                    filter=Q(submissions__is_official=True),
                ),
                0,
                output_field=IntegerField(),
            ),
            official_tests=Coalesce(
                Count(
                    "submissions",
                    filter=Q(submissions__is_official=True),
                ),
                0,
                output_field=IntegerField(),
            ),
        )
        .order_by(*order_by)
    )


def rank_for_user(user: User) -> int:
    """Return the 1-based leaderboard position of ``user`` (ranked by points)."""
    ahead = User.objects.filter(is_active=True).filter(
        Q(points__gt=user.points) | Q(points=user.points, id__lt=user.id)
    ).count()
    return ahead + 1
