"""Tests for input validation and submission guard rails."""
from __future__ import annotations

from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from mehmat_app.services.scoring import AnswerInput, submit_test
from mehmat_app.tests.factories import (
    add_ordering_question,
    add_single_choice_question,
    create_test,
    create_user,
    start_session,
)


class ServiceValidationTests(TestCase):
    def setUp(self) -> None:
        self.user = create_user(telegram_id=1)
        self.test = create_test()

    def test_invalid_choice_is_rejected(self) -> None:
        question, correct, _ = add_single_choice_question(self.test)
        session = start_session(self.user, self.test)
        with self.assertRaises(ValidationError):
            submit_test(
                user=self.user,
                test=self.test,
                session_id=session.id,
                answers=[AnswerInput(question.id, [999999], [])],
            )

    def test_single_choice_multiple_selected_rejected(self) -> None:
        question, correct, wrong = add_single_choice_question(self.test)
        session = start_session(self.user, self.test)
        with self.assertRaises(ValidationError):
            submit_test(
                user=self.user,
                test=self.test,
                session_id=session.id,
                answers=[AnswerInput(question.id, [correct.id, wrong.id], [])],
            )

    def test_incomplete_ordering_rejected(self) -> None:
        question, choices = add_ordering_question(self.test)
        session = start_session(self.user, self.test)
        with self.assertRaises(ValidationError):
            submit_test(
                user=self.user,
                test=self.test,
                session_id=session.id,
                answers=[AnswerInput(question.id, [], [choices[0].id, choices[1].id])],
            )

    def test_answer_for_foreign_question_rejected(self) -> None:
        add_single_choice_question(self.test)
        other_test = create_test(title="Other")
        q_other, correct_other, _ = add_single_choice_question(other_test)
        session = start_session(self.user, self.test)
        with self.assertRaises(ValidationError):
            submit_test(
                user=self.user,
                test=self.test,
                session_id=session.id,
                answers=[AnswerInput(q_other.id, [correct_other.id], [])],
            )

    def test_empty_test_rejected(self) -> None:
        session = start_session(self.user, self.test)
        with self.assertRaises(ValidationError):
            submit_test(
                user=self.user,
                test=self.test,
                session_id=session.id,
                answers=[AnswerInput(1, [1], [])],
            )


class EndpointValidationTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(telegram_id=1)
        self.client.force_authenticate(self.user)

    def test_future_test_cannot_be_started(self) -> None:
        future = create_test(
            title="Future",
            start_datetime=timezone.now() + timedelta(days=1),
        )
        add_single_choice_question(future)
        response = self.client.post(reverse("v1:test-start", args=[future.id]))
        self.assertEqual(response.status_code, 403)

    def test_expired_test_cannot_be_started(self) -> None:
        expired = create_test(
            title="Expired",
            end_datetime=timezone.now() - timedelta(days=1),
        )
        add_single_choice_question(expired)
        response = self.client.post(reverse("v1:test-start", args=[expired.id]))
        self.assertEqual(response.status_code, 403)

    def test_duplicate_answers_rejected_by_serializer(self) -> None:
        test = create_test()
        question, correct, _ = add_single_choice_question(test)
        session = start_session(self.user, test)
        payload = {
            "session_id": session.id,
            "answers": [
                {"question_id": question.id, "choice_ids": [correct.id]},
                {"question_id": question.id, "choice_ids": [correct.id]},
            ],
        }
        response = self.client.post(
            reverse("v1:test-submit", args=[test.id]), payload, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_answer_without_choices_or_ordering_rejected(self) -> None:
        test = create_test()
        question, _, _ = add_single_choice_question(test)
        session = start_session(self.user, test)
        payload = {
            "session_id": session.id,
            "answers": [{"question_id": question.id}],
        }
        response = self.client.post(
            reverse("v1:test-submit", args=[test.id]), payload, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_full_submit_flow_via_api(self) -> None:
        test = create_test(reward_points=100)
        question, correct, _ = add_single_choice_question(test)
        start_response = self.client.post(reverse("v1:test-start", args=[test.id]))
        self.assertEqual(start_response.status_code, 201)
        session_id = start_response.data["id"]

        payload = {
            "session_id": session_id,
            "answers": [{"question_id": question.id, "choice_ids": [correct.id]}],
        }
        response = self.client.post(
            reverse("v1:test-submit", args=[test.id]), payload, format="json"
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["score"], "100.00")
        self.assertTrue(response.data["is_official"])
