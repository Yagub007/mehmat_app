"""Tests for endpoint permissions and object-level access control."""
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from mehmat_app.models import Notification, Submission
from mehmat_app.tests.factories import create_test, create_user


class AuthenticationRequiredTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_protected_endpoints_require_auth(self) -> None:
        for name in ["v1:profile", "v1:leaderboard", "v1:achievements"]:
            response = self.client.get(reverse(name))
            self.assertEqual(response.status_code, 401, msg=name)

    def test_material_list_requires_auth(self) -> None:
        response = self.client.get(reverse("v1:material-list"))
        self.assertEqual(response.status_code, 401)


class OwnershipTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.owner = create_user(telegram_id=1)
        self.other = create_user(telegram_id=2)
        self.test = create_test()

    def test_user_cannot_read_others_submission(self) -> None:
        submission = Submission.objects.create(user=self.owner, test=self.test)
        self.client.force_authenticate(self.other)
        response = self.client.get(
            reverse("v1:submission-detail", args=[submission.id])
        )
        # Not in the other user's queryset -> 404.
        self.assertEqual(response.status_code, 404)

    def test_user_only_sees_own_submissions(self) -> None:
        Submission.objects.create(user=self.owner, test=self.test)
        Submission.objects.create(user=self.other, test=self.test)
        self.client.force_authenticate(self.owner)
        response = self.client.get(reverse("v1:submission-list"))
        self.assertEqual(response.data["count"], 1)

    def test_user_only_sees_own_notifications(self) -> None:
        Notification.objects.create(user=self.owner, title="mine")
        Notification.objects.create(user=self.other, title="theirs")
        self.client.force_authenticate(self.owner)
        response = self.client.get(reverse("v1:notification-list"))
        titles = [n["title"] for n in response.data["results"]]
        self.assertIn("mine", titles)
        self.assertNotIn("theirs", titles)


class ReadOnlyMaterialTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = create_user(telegram_id=1)
        self.client.force_authenticate(self.user)

    def test_materials_are_read_only(self) -> None:
        # Write methods are rejected by the ReadOnly permission (403).
        response = self.client.post(reverse("v1:material-list"), {}, format="json")
        self.assertEqual(response.status_code, 403)
