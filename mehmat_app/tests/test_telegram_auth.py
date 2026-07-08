"""Tests for Telegram Mini App authentication."""
from __future__ import annotations

import time

from django.test import TestCase, override_settings
from django.urls import reverse
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.test import APIClient

from mehmat_app.models import User
from mehmat_app.services.telegram import authenticate_telegram_user, verify_init_data
from mehmat_app.tests.factories import TEST_BOT_TOKEN, build_init_data


@override_settings(TELEGRAM_BOT_TOKEN=TEST_BOT_TOKEN)
class TelegramServiceTests(TestCase):
    """Unit tests for the verification service."""

    def test_valid_init_data_creates_user(self) -> None:
        init_data = build_init_data(telegram_id=42, username="neo")
        user, created = authenticate_telegram_user(init_data)
        self.assertTrue(created)
        self.assertEqual(user.telegram_id, 42)
        self.assertEqual(user.username, "neo")
        self.assertFalse(user.has_usable_password())

    def test_second_login_updates_not_duplicates(self) -> None:
        authenticate_telegram_user(build_init_data(telegram_id=42, username="old"))
        user, created = authenticate_telegram_user(
            build_init_data(telegram_id=42, username="new")
        )
        self.assertFalse(created)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(user.username, "new")

    def test_tampered_hash_is_rejected(self) -> None:
        init_data = build_init_data(telegram_id=42, tamper=True)
        with self.assertRaises(AuthenticationFailed):
            verify_init_data(init_data)

    def test_wrong_bot_token_is_rejected(self) -> None:
        init_data = build_init_data(bot_token="999:OTHER", telegram_id=42)
        with self.assertRaises(AuthenticationFailed):
            verify_init_data(init_data)

    def test_expired_auth_date_is_rejected(self) -> None:
        stale = int(time.time()) - 90_000  # older than the 24h default
        init_data = build_init_data(telegram_id=42, auth_date=stale)
        with self.assertRaises(AuthenticationFailed):
            verify_init_data(init_data)

    def test_missing_hash_is_rejected(self) -> None:
        with self.assertRaises(AuthenticationFailed):
            verify_init_data("auth_date=123&user=%7B%7D")


@override_settings(TELEGRAM_BOT_TOKEN=TEST_BOT_TOKEN)
class TelegramAuthEndpointTests(TestCase):
    """Integration tests for the authentication endpoint."""

    def setUp(self) -> None:
        self.client = APIClient()
        self.url = reverse("v1:telegram-auth")

    def test_returns_jwt_pair(self) -> None:
        response = self.client.post(
            self.url, {"init_data": build_init_data(telegram_id=7)}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)
        self.assertTrue(response.data["created"])
        self.assertEqual(response.data["user"]["telegram_id"], 7)

    def test_invalid_payload_returns_401(self) -> None:
        response = self.client.post(
            self.url, {"init_data": build_init_data(tamper=True)}, format="json"
        )
        self.assertEqual(response.status_code, 401)

    def test_missing_init_data_returns_400(self) -> None:
        response = self.client.post(self.url, {}, format="json")
        self.assertEqual(response.status_code, 400)
