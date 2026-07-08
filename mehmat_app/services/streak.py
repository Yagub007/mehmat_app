"""Daily activity streak computation."""
from __future__ import annotations

from datetime import date, timedelta


def next_streak(previous_streak: int, last_activity: date | None, today: date) -> int:
    """Return the updated streak given the last activity date and today.

    - Same day as last activity: streak unchanged (min 1).
    - Consecutive day: streak increments.
    - Gap of two or more days (or no history): streak resets to 1.
    """
    if last_activity is None:
        return 1
    if last_activity == today:
        return max(previous_streak, 1)
    if last_activity == today - timedelta(days=1):
        return previous_streak + 1
    return 1
