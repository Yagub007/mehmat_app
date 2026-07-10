"""Enumerations and domain constants shared across the app."""
from __future__ import annotations

from django.db import models


class MaterialCategory(models.TextChoices):
    """Legacy fixed subject categories.

    Retained for backward compatibility and as sensible defaults. Study
    materials are now organised through the hierarchical :class:`Category`
    model, which is populated automatically from the Google Drive folder tree.
    """

    ALGEBRA = "algebra", "Algebra"
    GEOMETRY = "geometry", "Geometry"
    FUNCTIONS = "functions", "Functions"
    DERIVATIVES = "derivatives", "Derivatives"
    PROBABILITY = "probability", "Probability"
    OTHER = "other", "Other"


class FileType(models.TextChoices):
    """High-level type of a study material's underlying file.

    Derived from the source MIME type so the frontend can pick an appropriate
    icon and "open" behaviour without parsing MIME strings itself.
    """

    PDF = "pdf", "PDF"
    VIDEO = "video", "Video"
    PRESENTATION = "presentation", "Presentation"
    DOCUMENT = "document", "Document"
    SPREADSHEET = "spreadsheet", "Spreadsheet"
    IMAGE = "image", "Image"
    AUDIO = "audio", "Audio"
    ARCHIVE = "archive", "Archive"
    LINK = "link", "Link"
    OTHER = "other", "Other"


class TestDifficulty(models.TextChoices):
    """Difficulty levels for tests."""

    EASY = "easy", "Easy"
    MEDIUM = "medium", "Medium"
    HARD = "hard", "Hard"


class QuestionType(models.TextChoices):
    """Supported question types."""

    SINGLE = "single", "Single choice"
    MULTIPLE = "multiple", "Multiple choice"
    ORDERING = "ordering", "Ordering"
    SHORT_ANSWER = "short_answer", "Short answer"
    MATCHING = "matching", "Matching"


class RankTier(models.TextChoices):
    """Gamification rank tiers derived from a user's points."""

    NOVICE = "novice", "Novice"
    BRONZE = "bronze", "Bronze"
    SILVER = "silver", "Silver"
    GOLD = "gold", "Gold"
    PLATINUM = "platinum", "Platinum"
    DIAMOND = "diamond", "Diamond"


# Ordered ascending by required points. Used by the ranking service to map a
# points total onto a tier. Keep this ordered from highest threshold to lowest
# is handled in the service; here we keep ascending for readability.
RANK_THRESHOLDS: tuple[tuple[int, str], ...] = (
    (0, RankTier.NOVICE),
    (100, RankTier.BRONZE),
    (300, RankTier.SILVER),
    (700, RankTier.GOLD),
    (1500, RankTier.PLATINUM),
    (3000, RankTier.DIAMOND),
)


class AchievementCode(models.TextChoices):
    """Stable identifiers for automatically unlocked achievements."""

    FIRST_TEST = "first_test", "First Test"
    POINTS_100 = "points_100", "100 Points"
    POINTS_500 = "points_500", "500 Points"
    POINTS_1000 = "points_1000", "1000 Points"
    TESTS_5 = "tests_5", "5 Tests"
    TESTS_10 = "tests_10", "10 Tests"
    PERFECT_SCORE = "perfect_score", "Perfect Score"
    STREAK_7 = "streak_7", "7 Day Streak"


# Grace period (seconds) added to a test's duration to tolerate network latency
# when validating the server-side timer on submission.
SUBMISSION_TIME_GRACE_SECONDS = 10
