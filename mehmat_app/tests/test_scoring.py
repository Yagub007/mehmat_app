"""Tests for the authoritative scoring service."""
from __future__ import annotations

from decimal import Decimal

from django.test import TestCase

from mehmat_app.constants import AchievementCode, RankTier
from mehmat_app.models import UserAchievement
from mehmat_app.services.scoring import AnswerInput, submit_test
from mehmat_app.tests.factories import (
    add_multiple_choice_question,
    add_ordering_question,
    add_single_choice_question,
    create_test,
    create_user,
    start_session,
)


class ScoringTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user(telegram_id=1)
        self.test = create_test(reward_points=100)

    def test_all_correct_scores_100_and_awards_points(self) -> None:
        _, correct1, _ = add_single_choice_question(self.test, order=1)
        _, correct2, _ = add_single_choice_question(self.test, order=2)
        session = start_session(self.user, self.test)

        submission = submit_test(
            user=self.user,
            test=self.test,
            session_id=session.id,
            answers=[
                AnswerInput(correct1.question_id, [correct1.id], []),
                AnswerInput(correct2.question_id, [correct2.id], []),
            ],
        )

        self.assertEqual(submission.score, Decimal("100.00"))
        self.assertEqual(submission.correct_count, 2)
        self.assertEqual(submission.wrong_count, 0)
        self.assertTrue(submission.is_official)
        self.assertEqual(submission.points_earned, 100)

        self.user.refresh_from_db()
        self.assertEqual(self.user.points, 100)
        self.assertEqual(self.user.completed_tests, 1)
        self.assertEqual(self.user.current_rank, RankTier.BRONZE)

    def test_partial_score_is_proportional(self) -> None:
        _, correct1, _ = add_single_choice_question(self.test, order=1)
        q2, _, wrong2 = add_single_choice_question(self.test, order=2)
        session = start_session(self.user, self.test)

        submission = submit_test(
            user=self.user,
            test=self.test,
            session_id=session.id,
            answers=[
                AnswerInput(correct1.question_id, [correct1.id], []),
                AnswerInput(q2.id, [wrong2.id], []),
            ],
        )
        self.assertEqual(submission.score, Decimal("50.00"))
        self.assertEqual(submission.points_earned, 50)

    def test_missing_answer_counts_as_wrong(self) -> None:
        _, correct1, _ = add_single_choice_question(self.test, order=1)
        add_single_choice_question(self.test, order=2)
        session = start_session(self.user, self.test)

        submission = submit_test(
            user=self.user,
            test=self.test,
            session_id=session.id,
            answers=[AnswerInput(correct1.question_id, [correct1.id], [])],
        )
        self.assertEqual(submission.correct_count, 1)
        self.assertEqual(submission.wrong_count, 1)
        self.assertEqual(submission.score, Decimal("50.00"))

    def test_multiple_choice_requires_exact_set(self) -> None:
        question, choices = add_multiple_choice_question(self.test)
        session = start_session(self.user, self.test)
        # Only one of the two correct choices selected -> wrong.
        submission = submit_test(
            user=self.user,
            test=self.test,
            session_id=session.id,
            answers=[AnswerInput(question.id, [choices[0].id], [])],
        )
        self.assertEqual(submission.correct_count, 0)

    def test_multiple_choice_all_correct(self) -> None:
        question, choices = add_multiple_choice_question(self.test)
        session = start_session(self.user, self.test)
        submission = submit_test(
            user=self.user,
            test=self.test,
            session_id=session.id,
            answers=[AnswerInput(question.id, [choices[0].id, choices[1].id], [])],
        )
        self.assertEqual(submission.correct_count, 1)
        self.assertEqual(submission.score, Decimal("100.00"))

    def test_ordering_question_grading(self) -> None:
        question, choices = add_ordering_question(self.test)
        session = start_session(self.user, self.test)
        correct_order = [c.id for c in choices]
        submission = submit_test(
            user=self.user,
            test=self.test,
            session_id=session.id,
            answers=[AnswerInput(question.id, [], correct_order)],
        )
        self.assertEqual(submission.correct_count, 1)

    def test_perfect_score_unlocks_achievement(self) -> None:
        _, correct, _ = add_single_choice_question(self.test)
        session = start_session(self.user, self.test)
        submit_test(
            user=self.user,
            test=self.test,
            session_id=session.id,
            answers=[AnswerInput(correct.question_id, [correct.id], [])],
        )
        codes = set(
            UserAchievement.objects.filter(user=self.user).values_list(
                "achievement__code", flat=True
            )
        )
        self.assertIn(AchievementCode.FIRST_TEST, codes)
        self.assertIn(AchievementCode.PERFECT_SCORE, codes)
        self.assertIn(AchievementCode.POINTS_100, codes)
