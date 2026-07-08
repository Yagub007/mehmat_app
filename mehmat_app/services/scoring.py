"""Authoritative test grading and submission service.

All scoring is performed server-side; the frontend never supplies a score. A
user's first in-time attempt is recorded as *official* and updates their points,
rank, streak and achievements atomically. Later attempts are graded for
practice only and never affect ranking.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Iterable

from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from mehmat_app.constants import (
    SUBMISSION_TIME_GRACE_SECONDS,
    QuestionType,
)
from mehmat_app.models import (
    Question,
    Submission,
    SubmissionAnswer,
    Test,
    TestSession,
    User,
)
from mehmat_app.services import achievements as achievement_service
from mehmat_app.services import ranking as ranking_service
from mehmat_app.services import streak as streak_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AnswerInput:
    """A normalised, structurally-validated answer for a single question."""

    question_id: int
    choice_ids: list[int]
    ordering: list[int]


def _grade_question(question: Question, answer: AnswerInput | None) -> bool:
    """Return whether ``answer`` correctly resolves ``question``."""
    if answer is None:
        return False

    choices = list(question.choices.all())
    valid_ids = {c.id for c in choices}

    if question.question_type == QuestionType.ORDERING:
        submitted = answer.ordering
        if set(submitted) != valid_ids or len(submitted) != len(valid_ids):
            # Not a full permutation of this question's choices.
            raise ValidationError(
                {"answers": f"Invalid ordering for question {question.id}."}
            )
        correct_sequence = [c.id for c in sorted(choices, key=lambda c: (c.order, c.id))]
        return submitted == correct_sequence

    selected = set(answer.choice_ids)
    if not selected <= valid_ids:
        raise ValidationError(
            {"answers": f"Invalid choice(s) for question {question.id}."}
        )

    correct = {c.id for c in choices if c.is_correct}

    if question.question_type == QuestionType.SINGLE:
        if len(selected) != 1:
            raise ValidationError(
                {"answers": f"Question {question.id} expects exactly one choice."}
            )
    elif not selected:
        raise ValidationError(
            {"answers": f"Question {question.id} expects at least one choice."}
        )

    return selected == correct


def _percentage(correct_points: int, total_points: int) -> Decimal:
    """Return the score percentage rounded to two decimal places."""
    if total_points <= 0:
        return Decimal("0.00")
    value = Decimal(correct_points) / Decimal(total_points) * Decimal(100)
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _resolve_session(
    user: User,
    test: Test,
    session_id: int | None,
) -> tuple[TestSession | None, int, bool]:
    """Return ``(session, completion_time_seconds, within_time)``."""
    if session_id is None:
        return None, 0, False

    try:
        session = TestSession.objects.get(id=session_id, user=user, test=test)
    except TestSession.DoesNotExist as exc:
        raise ValidationError({"session_id": "Invalid session for this test."}) from exc

    if session.is_completed:
        raise ValidationError({"session_id": "This session has already been used."})

    elapsed = int((timezone.now() - session.started_at).total_seconds())
    elapsed = max(elapsed, 0)
    within_time = elapsed <= test.duration_seconds + SUBMISSION_TIME_GRACE_SECONDS
    return session, elapsed, within_time


@transaction.atomic
def submit_test(
    *,
    user: User,
    test: Test,
    answers: Iterable[AnswerInput],
    session_id: int | None = None,
) -> Submission:
    """Grade a submission and persist it, updating aggregates when official."""
    # Serialise concurrent submissions for the same user.
    user = User.objects.select_for_update().get(pk=user.pk)

    questions = list(
        Question.objects.filter(test=test).prefetch_related("choices")
    )
    if not questions:
        raise ValidationError({"test": "This test has no questions."})

    question_by_id = {q.id: q for q in questions}
    answers_by_qid: dict[int, AnswerInput] = {}
    for answer in answers:
        if answer.question_id not in question_by_id:
            raise ValidationError(
                {"answers": f"Question {answer.question_id} is not part of this test."}
            )
        if answer.question_id in answers_by_qid:
            raise ValidationError(
                {"answers": f"Duplicate answer for question {answer.question_id}."}
            )
        answers_by_qid[answer.question_id] = answer

    session, completion_time, within_time = _resolve_session(user, test, session_id)

    has_official = Submission.objects.filter(
        user=user, test=test, is_official=True
    ).exists()

    now = timezone.now()
    is_official = (
        not has_official
        and session is not None
        and within_time
        and test.is_available(at=now)
    )

    # ---- Grade ----------------------------------------------------------
    correct_points = 0
    total_points = 0
    correct_count = 0
    graded: list[tuple[Question, AnswerInput | None, bool]] = []
    for question in questions:
        total_points += question.points
        answer = answers_by_qid.get(question.id)
        is_correct = _grade_question(question, answer)
        if is_correct:
            correct_points += question.points
            correct_count += 1
        graded.append((question, answer, is_correct))

    total_questions = len(questions)
    wrong_count = total_questions - correct_count
    score = _percentage(correct_points, total_points)
    perfect = score == Decimal("100.00")

    points_earned = 0
    if is_official and test.reward_points and total_points > 0:
        points_earned = int(
            (Decimal(test.reward_points) * Decimal(correct_points) / Decimal(total_points))
            .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
        )

    # ---- Persist submission --------------------------------------------
    try:
        submission = Submission.objects.create(
            user=user,
            test=test,
            session=session,
            is_official=is_official,
            correct_count=correct_count,
            wrong_count=wrong_count,
            total_questions=total_questions,
            score=score,
            points_earned=points_earned,
            started_at=session.started_at if session else None,
            submitted_at=now,
            completion_time=completion_time,
        )
    except IntegrityError as exc:
        # Race: another official submission slipped in. Fall back gracefully.
        raise ValidationError(
            {"detail": "You have already submitted an official attempt for this test."}
        ) from exc

    _persist_answers(submission, graded)

    if session is not None:
        session.is_completed = True
        session.save(update_fields=["is_completed"])

    # ---- Update aggregates (official only) ------------------------------
    if is_official:
        _apply_official_results(user, points_earned, perfect=perfect)

    return submission


def _persist_answers(
    submission: Submission,
    graded: list[tuple[Question, AnswerInput | None, bool]],
) -> None:
    """Create :class:`SubmissionAnswer` rows for every provided answer."""
    for question, answer, is_correct in graded:
        if answer is None:
            continue
        submission_answer = SubmissionAnswer.objects.create(
            submission=submission,
            question=question,
            is_correct=is_correct,
            ordering_answer=answer.ordering if answer.ordering else [],
        )
        if answer.choice_ids:
            submission_answer.selected_choices.set(answer.choice_ids)


def _apply_official_results(user: User, points_earned: int, *, perfect: bool) -> None:
    """Update the user's aggregates and unlock achievements atomically."""
    today = timezone.localdate()
    user.points += points_earned
    user.completed_tests += 1
    user.streak = streak_service.next_streak(user.streak, user.last_activity_date, today)
    user.last_activity_date = today
    user.current_rank = ranking_service.rank_for_points(user.points)
    user.save(
        update_fields=[
            "points",
            "completed_tests",
            "streak",
            "last_activity_date",
            "current_rank",
        ]
    )
    achievement_service.evaluate_achievements(user, perfect_score=perfect)
