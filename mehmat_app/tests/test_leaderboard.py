"""Tests for leaderboard ranking and updates."""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from mehmat_app.selectors.leaderboard import leaderboard_queryset, rank_for_user
from mehmat_app.services.scoring import AnswerInput, submit_test
from mehmat_app.tests.factories import (
    add_single_choice_question,
    create_test,
    create_user,
    start_session,
)


class LeaderboardSelectorTests(TestCase):
    def setUp(self) -> None:
        self.alice = create_user(telegram_id=1, username="alice", points=500)
        self.bob = create_user(telegram_id=2, username="bob", points=800)
        self.carol = create_user(telegram_id=3, username="carol", points=100)

    def test_ordering_by_points_desc(self) -> None:
        ranked = list(leaderboard_queryset("points"))
        self.assertEqual([u.username for u in ranked], ["bob", "alice", "carol"])

    def test_rank_for_user(self) -> None:
        self.assertEqual(rank_for_user(self.bob), 1)
        self.assertEqual(rank_for_user(self.alice), 2)
        self.assertEqual(rank_for_user(self.carol), 3)

    def test_ordering_by_completed_tests(self) -> None:
        self.alice.completed_tests = 10
        self.alice.save(update_fields=["completed_tests"])
        ranked = list(leaderboard_queryset("completed_tests"))
        self.assertEqual(ranked[0].username, "alice")

    def test_inactive_users_excluded(self) -> None:
        self.carol.is_active = False
        self.carol.save(update_fields=["is_active"])
        usernames = [u.username for u in leaderboard_queryset()]
        self.assertNotIn("carol", usernames)


class LeaderboardUpdateTests(TestCase):
    def test_submission_updates_leaderboard_position(self) -> None:
        leader = create_user(telegram_id=1, username="leader", points=50)
        climber = create_user(telegram_id=2, username="climber", points=0)
        self.assertEqual(rank_for_user(climber), 2)

        test = create_test(reward_points=100)
        _, correct, _ = add_single_choice_question(test)
        session = start_session(climber, test)
        submit_test(
            user=climber,
            test=test,
            session_id=session.id,
            answers=[AnswerInput(correct.question_id, [correct.id], [])],
        )
        climber.refresh_from_db()
        self.assertEqual(climber.points, 100)
        self.assertEqual(rank_for_user(climber), 1)


class LeaderboardEndpointTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(telegram_id=1, username="me", points=300)
        create_user(telegram_id=2, username="rival", points=900)
        self.client.force_authenticate(self.user)

    def test_leaderboard_list(self) -> None:
        response = self.client.get(reverse("v1:leaderboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["results"][0]["username"], "rival")

    def test_my_rank(self) -> None:
        response = self.client.get(reverse("v1:leaderboard-me"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["position"], 2)
        self.assertEqual(response.data["points"], 300)

    def test_requires_authentication(self) -> None:
        self.client.force_authenticate(None)
        response = self.client.get(reverse("v1:leaderboard"))
        self.assertEqual(response.status_code, 401)
