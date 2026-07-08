"""Tests for submission rules: official attempts, timers, duplicates."""
from __future__ import annotations

from django.test import TestCase

from mehmat_app.models import Submission
from mehmat_app.services.scoring import AnswerInput, submit_test
from mehmat_app.tests.factories import (
    add_single_choice_question,
    create_test,
    create_user,
    start_session,
)


class SubmissionRuleTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user(telegram_id=1)
        self.test = create_test(reward_points=100)
        _, self.correct, self.wrong = add_single_choice_question(self.test)

    def _submit(self, session_id, choice_id):
        return submit_test(
            user=self.user,
            test=self.test,
            session_id=session_id,
            answers=[AnswerInput(self.correct.question_id, [choice_id], [])],
        )

    def test_only_first_attempt_is_official(self) -> None:
        first = self._submit(start_session(self.user, self.test).id, self.correct.id)
        second = self._submit(start_session(self.user, self.test).id, self.wrong.id)

        self.assertTrue(first.is_official)
        self.assertFalse(second.is_official)

        # Points reflect only the official attempt.
        self.user.refresh_from_db()
        self.assertEqual(self.user.points, 100)
        self.assertEqual(self.user.completed_tests, 1)
        self.assertEqual(
            Submission.objects.filter(test=self.test, is_official=True).count(), 1
        )

    def test_second_attempt_does_not_change_ranking(self) -> None:
        self._submit(start_session(self.user, self.test).id, self.wrong.id)
        self.user.refresh_from_db()
        points_after_official = self.user.points

        self._submit(start_session(self.user, self.test).id, self.correct.id)
        self.user.refresh_from_db()
        self.assertEqual(self.user.points, points_after_official)

    def test_submission_without_session_is_practice(self) -> None:
        submission = self._submit(None, self.correct.id)
        self.assertFalse(submission.is_official)
        self.user.refresh_from_db()
        self.assertEqual(self.user.points, 0)

    def test_over_time_submission_is_not_official(self) -> None:
        # Started well beyond the allowed duration (30 min) plus grace.
        stale_session = start_session(
            self.user, self.test, started_seconds_ago=self.test.duration_seconds + 120
        )
        submission = self._submit(stale_session.id, self.correct.id)
        self.assertFalse(submission.is_official)

    def test_completion_time_recorded(self) -> None:
        session = start_session(self.user, self.test, started_seconds_ago=45)
        submission = self._submit(session.id, self.correct.id)
        self.assertGreaterEqual(submission.completion_time, 45)

    def test_session_cannot_be_reused(self) -> None:
        from rest_framework.exceptions import ValidationError

        session = start_session(self.user, self.test)
        self._submit(session.id, self.correct.id)
        with self.assertRaises(ValidationError):
            self._submit(session.id, self.wrong.id)

    def test_unavailable_test_submission_is_not_official(self) -> None:
        session = start_session(self.user, self.test)
        self.test.is_active = False
        self.test.save(update_fields=["is_active"])
        submission = self._submit(session.id, self.correct.id)
        self.assertFalse(submission.is_official)
