"""Achievement evaluation and unlocking service."""
from __future__ import annotations

import logging
from typing import Callable

from mehmat_app.constants import AchievementCode
from mehmat_app.models import Achievement, Notification, User, UserAchievement

logger = logging.getLogger(__name__)


def _rules(user: User, *, perfect_score: bool) -> dict[str, bool]:
    """Return, per achievement code, whether the unlock condition is met."""
    return {
        AchievementCode.FIRST_TEST: user.completed_tests >= 1,
        AchievementCode.TESTS_5: user.completed_tests >= 5,
        AchievementCode.TESTS_10: user.completed_tests >= 10,
        AchievementCode.POINTS_100: user.points >= 100,
        AchievementCode.POINTS_500: user.points >= 500,
        AchievementCode.POINTS_1000: user.points >= 1000,
        AchievementCode.PERFECT_SCORE: perfect_score,
        AchievementCode.STREAK_7: user.streak >= 7,
    }


def evaluate_achievements(
    user: User,
    *,
    perfect_score: bool = False,
) -> list[Achievement]:
    """Unlock any newly earned achievements for ``user``.

    Must be called inside the same transaction that mutated the user's
    aggregates. Returns the list of achievements unlocked in this call.
    """
    satisfied_codes = {code for code, ok in _rules(user, perfect_score=perfect_score).items() if ok}
    if not satisfied_codes:
        return []

    already_unlocked = set(
        UserAchievement.objects.filter(user=user).values_list(
            "achievement__code", flat=True
        )
    )
    codes_to_unlock = satisfied_codes - already_unlocked
    if not codes_to_unlock:
        return []

    achievements = list(Achievement.objects.filter(code__in=codes_to_unlock))
    if not achievements:
        return []

    UserAchievement.objects.bulk_create(
        [UserAchievement(user=user, achievement=a) for a in achievements],
        ignore_conflicts=True,
    )
    Notification.objects.bulk_create(
        [
            Notification(
                user=user,
                title="Achievement unlocked!",
                message=f"You unlocked “{a.title}”.",
            )
            for a in achievements
        ]
    )
    logger.info(
        "User %s unlocked achievements: %s",
        user.pk,
        [a.code for a in achievements],
    )
    return achievements
