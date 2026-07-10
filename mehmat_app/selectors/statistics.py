"""Read-side aggregation of a user's performance statistics."""
from __future__ import annotations

from typing import TypedDict

from decimal import Decimal

from django.db.models import Avg, Count, DecimalField, Max, Q, Sum, Value
from django.db.models.functions import Coalesce

from mehmat_app.models import User
from mehmat_app.selectors.leaderboard import rank_for_user

# ``Submission.score`` is a DecimalField(max_digits=5, decimal_places=2); the
# Coalesce fallback must be the same type or Django raises a mixed-type FieldError.
_SCORE_FIELD = DecimalField(max_digits=5, decimal_places=2)


class UserStatistics(TypedDict):
    """Shape of the computed statistics payload."""

    points: int
    current_rank: str
    leaderboard_position: int
    streak: int
    completed_tests: int
    official_submissions: int
    practice_submissions: int
    average_score: float
    best_score: float
    total_time_spent: int
    achievements_unlocked: int


def user_statistics(user: User) -> UserStatistics:
    """Compute aggregate statistics for ``user`` in a small number of queries."""
    aggregates = user.submissions.aggregate(
        official_submissions=Count("id", filter=Q(is_official=True)),
        practice_submissions=Count("id", filter=Q(is_official=False)),
        average_score=Coalesce(
            Avg("score", filter=Q(is_official=True)),
            Value(Decimal("0"), output_field=_SCORE_FIELD),
            output_field=_SCORE_FIELD,
        ),
        best_score=Coalesce(
            Max("score", filter=Q(is_official=True)),
            Value(Decimal("0"), output_field=_SCORE_FIELD),
            output_field=_SCORE_FIELD,
        ),
        total_time_spent=Coalesce(
            Sum("completion_time", filter=Q(is_official=True)), 0
        ),
    )
    achievements_unlocked = user.achievements.count()

    return UserStatistics(
        points=user.points,
        current_rank=user.current_rank,
        leaderboard_position=rank_for_user(user),
        streak=user.streak,
        completed_tests=user.completed_tests,
        official_submissions=aggregates["official_submissions"],
        practice_submissions=aggregates["practice_submissions"],
        average_score=round(float(aggregates["average_score"]), 2),
        best_score=round(float(aggregates["best_score"]), 2),
        total_time_spent=int(aggregates["total_time_spent"]),
        achievements_unlocked=achievements_unlocked,
    )
