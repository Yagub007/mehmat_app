"""Rank-tier computation based on a user's points."""
from __future__ import annotations

from mehmat_app.constants import RANK_THRESHOLDS, RankTier


def rank_for_points(points: int) -> str:
    """Return the highest :class:`RankTier` value earned for ``points``."""
    current = RankTier.NOVICE.value
    for threshold, tier in RANK_THRESHOLDS:
        if points >= threshold:
            current = tier
        else:
            break
    return current
