"""Testing system models: tests, questions, choices, sessions, submissions."""
from __future__ import annotations

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from mehmat_app.constants import QuestionType, TestDifficulty
from mehmat_app.models.base import TimeStampedModel


class TestQuerySet(models.QuerySet):
    """Custom queryset for :class:`Test`."""

    def published(self) -> "TestQuerySet":
        """Return only published tests."""
        return self.filter(is_published=True)

    def available(self) -> "TestQuerySet":
        """Return tests that are published, active and within their window."""
        now = timezone.now()
        return self.filter(
            is_published=True,
            is_active=True,
        ).filter(
            models.Q(start_datetime__isnull=True) | models.Q(start_datetime__lte=now)
        ).filter(
            models.Q(end_datetime__isnull=True) | models.Q(end_datetime__gte=now)
        )


class Test(TimeStampedModel):
    """An examination composed of questions and awarding reward points."""

    title = models.CharField(max_length=200, db_index=True)
    description = models.TextField(blank=True)
    difficulty = models.CharField(
        max_length=10,
        choices=TestDifficulty.choices,
        default=TestDifficulty.MEDIUM,
        db_index=True,
    )
    duration = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
        help_text="Allowed time to complete the test, in minutes.",
    )
    start_datetime = models.DateTimeField(null=True, blank=True)
    end_datetime = models.DateTimeField(null=True, blank=True)
    reward_points = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True, db_index=True)
    is_published = models.BooleanField(default=False, db_index=True)

    objects = TestQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=["is_published", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def duration_seconds(self) -> int:
        """Return the allowed duration in seconds."""
        return self.duration * 60

    def is_available(self, *, at=None) -> bool:
        """Return whether the test can currently be taken officially."""
        moment = at or timezone.now()
        if not (self.is_published and self.is_active):
            return False
        if self.start_datetime and moment < self.start_datetime:
            return False
        if self.end_datetime and moment > self.end_datetime:
            return False
        return True


class Question(models.Model):
    """A single question belonging to a test."""

    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="questions",
    )
    text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=QuestionType.choices,
        default=QuestionType.SINGLE,
    )
    image = models.ImageField(
        upload_to="questions/%Y/%m/",
        blank=True,
        null=True,
    )
    explanation = models.TextField(blank=True)
    points = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Relative weight of the question when scoring.",
    )
    order = models.PositiveIntegerField(default=0)

    # Expected value for short-answer questions (compared after normalisation).
    correct_answer = models.CharField(max_length=255, blank=True)
    # Matching questions: {"left": [{"id", "text"}], "right": [{"id", "text"}],
    # "answer": {"<left id>": "<right id>"}}. Empty for other types.
    matching = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ("order", "id")
        indexes = [
            models.Index(fields=["test", "order"]),
        ]

    def __str__(self) -> str:
        return f"Q{self.order}: {self.text[:50]}"


class Choice(models.Model):
    """An answer option for a question.

    For ordering questions ``order`` encodes the correct position; for single
    and multiple choice questions ``is_correct`` marks correct options.
    """

    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    text = models.CharField(max_length=500)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ("order", "id")

    def __str__(self) -> str:
        return self.text[:50]


class TestSession(models.Model):
    """A server-authoritative timer for a user's attempt at a test.

    Created when the user starts a test; used at submission time to validate
    that the answers arrived within the allowed duration.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="test_sessions",
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="sessions",
    )
    started_at = models.DateTimeField(default=timezone.now)
    expires_at = models.DateTimeField()
    is_completed = models.BooleanField(default=False)

    class Meta:
        ordering = ("-started_at",)
        indexes = [
            models.Index(fields=["user", "test", "is_completed"]),
        ]

    def __str__(self) -> str:
        return f"Session u={self.user_id} t={self.test_id}"

    @property
    def is_expired(self) -> bool:
        """Return whether the session's allotted time has elapsed."""
        return timezone.now() > self.expires_at


class Submission(TimeStampedModel):
    """A graded attempt at a test.

    Only the first in-time attempt is *official* and affects ranking; further
    attempts are stored for practice with ``is_official=False``.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    test = models.ForeignKey(
        Test,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    session = models.ForeignKey(
        TestSession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submissions",
    )
    is_official = models.BooleanField(default=False, db_index=True)

    correct_count = models.PositiveIntegerField(default=0)
    wrong_count = models.PositiveIntegerField(default=0)
    total_questions = models.PositiveIntegerField(default=0)
    score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        help_text="Percentage of correctly answered questions (0-100).",
    )
    points_earned = models.PositiveIntegerField(default=0)

    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(default=timezone.now)
    completion_time = models.PositiveIntegerField(
        default=0,
        help_text="Time taken to complete the test, in seconds.",
    )

    class Meta:
        ordering = ("-submitted_at",)
        constraints = [
            # Enforce at most one official submission per (user, test).
            models.UniqueConstraint(
                fields=["user", "test"],
                condition=models.Q(is_official=True),
                name="unique_official_submission_per_user_test",
            ),
        ]
        indexes = [
            models.Index(fields=["user", "test"]),
            models.Index(fields=["test", "is_official"]),
        ]

    def __str__(self) -> str:
        return f"Submission u={self.user_id} t={self.test_id} score={self.score}"


class SubmissionAnswer(models.Model):
    """A user's answer to a single question within a submission."""

    submission = models.ForeignKey(
        Submission,
        on_delete=models.CASCADE,
        related_name="answers",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="submission_answers",
    )
    selected_choices = models.ManyToManyField(
        Choice,
        blank=True,
        related_name="submission_answers",
    )
    # For ordering questions: the ordered list of choice ids the user submitted.
    ordering_answer = models.JSONField(default=list, blank=True)
    # For short-answer questions: the raw text the user submitted.
    text_answer = models.CharField(max_length=255, blank=True)
    # For matching questions: the submitted {"<left id>": "<right id>"} map.
    matching_answer = models.JSONField(default=dict, blank=True)
    is_correct = models.BooleanField(default=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["submission", "question"],
                name="unique_answer_per_question_in_submission",
            ),
        ]

    def __str__(self) -> str:
        return f"Answer q={self.question_id} correct={self.is_correct}"
