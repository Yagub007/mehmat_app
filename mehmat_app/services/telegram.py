"""Telegram Mini App authentication service.

Implements verification of the ``initData`` payload produced by the Telegram
Web App, following the official algorithm:

    secret_key = HMAC_SHA256(key="WebAppData", msg=<bot_token>)
    expected  = HMAC_SHA256(key=secret_key, msg=<data_check_string>)

The ``data_check_string`` is the ``key=value`` pairs (excluding ``hash``),
sorted alphabetically and joined by newlines. Frontend data is never trusted;
every field is re-derived and verified server side.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import parse_qsl

from django.conf import settings
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed

from mehmat_app.models import User

logger = logging.getLogger(__name__)

_WEBAPP_DATA_KEY = b"WebAppData"


@dataclass(frozen=True)
class TelegramUser:
    """Validated user attributes extracted from Telegram ``initData``."""

    telegram_id: int
    username: str
    first_name: str
    last_name: str
    photo_url: str
    language_code: str


def _compute_hash(bot_token: str, data_check_string: str) -> str:
    """Return the expected hex digest for ``data_check_string``."""
    secret_key = hmac.new(
        _WEBAPP_DATA_KEY, bot_token.encode(), hashlib.sha256
    ).digest()
    return hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()


def verify_init_data(init_data: str) -> dict[str, str]:
    """Verify a raw ``initData`` string and return its parsed key/value pairs.

    Raises:
        AuthenticationFailed: If the bot token is not configured, the payload is
            malformed, the hash does not match, or the data has expired.
    """
    bot_token = settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN is not configured.")
        raise AuthenticationFailed("Telegram authentication is not configured.")

    if not init_data:
        raise AuthenticationFailed("Missing Telegram init data.")

    # keep_blank_values keeps empty fields so the check string matches exactly.
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = pairs.pop("hash", None)
    if not received_hash:
        raise AuthenticationFailed("Telegram init data is missing a hash.")

    data_check_string = "\n".join(
        f"{key}={pairs[key]}" for key in sorted(pairs)
    )
    expected_hash = _compute_hash(bot_token, data_check_string)

    if not hmac.compare_digest(expected_hash, received_hash):
        raise AuthenticationFailed("Invalid Telegram init data signature.")

    _validate_auth_date(pairs.get("auth_date"))
    return pairs


def _validate_auth_date(auth_date_raw: str | None) -> None:
    """Reject init data that is missing or older than the configured max age."""
    if not auth_date_raw:
        raise AuthenticationFailed("Telegram init data is missing auth_date.")
    try:
        auth_date = int(auth_date_raw)
    except (TypeError, ValueError) as exc:
        raise AuthenticationFailed("Invalid Telegram auth_date.") from exc

    age = time.time() - auth_date
    if age > settings.TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise AuthenticationFailed("Telegram init data has expired.")
    # Guard against clocks far in the future (tolerate small skew).
    if age < -settings.TELEGRAM_AUTH_MAX_AGE_SECONDS:
        raise AuthenticationFailed("Invalid Telegram auth_date.")


def parse_telegram_user(verified_data: dict[str, str]) -> TelegramUser:
    """Extract and normalise the ``user`` object from verified init data."""
    user_raw = verified_data.get("user")
    if not user_raw:
        raise AuthenticationFailed("Telegram init data is missing user data.")
    try:
        payload = json.loads(user_raw)
    except json.JSONDecodeError as exc:
        raise AuthenticationFailed("Malformed Telegram user data.") from exc

    telegram_id = payload.get("id")
    if not isinstance(telegram_id, int):
        raise AuthenticationFailed("Telegram user id is missing or invalid.")

    return TelegramUser(
        telegram_id=telegram_id,
        username=(payload.get("username") or "")[:64],
        first_name=(payload.get("first_name") or "")[:128],
        last_name=(payload.get("last_name") or "")[:128],
        photo_url=(payload.get("photo_url") or "")[:512],
        language_code=(payload.get("language_code") or "")[:16],
    )


@transaction.atomic
def authenticate_telegram_user(init_data: str) -> tuple[User, bool]:
    """Verify ``init_data`` and return the matching user, creating it if needed.

    Returns:
        A tuple of ``(user, created)``.
    """

    # --- НАЧАЛО БЭКДОРА ДЛЯ ЛОКАЛЬНОЙ РАЗРАБОТКИ ---
    # Если сервер запущен в режиме отладки и пришла секретная строка
    if settings.DEBUG and init_data == "local_dev_test":
        user, created = User.objects.get_or_create(
            telegram_id=999999999,
            defaults={
                "username": "test_developer",
                "first_name": "Local",
                "last_name": "Developer",
                "language_code": "ru",
            },
        )
        if created:
            user.set_unusable_password()
            user.save(update_fields=["password"])
        return user, created
    # --- КОНЕЦ БЭКДОРА ---

    verified = verify_init_data(init_data)
    tg_user = parse_telegram_user(verified)

    user, created = User.objects.select_for_update().get_or_create(
        telegram_id=tg_user.telegram_id,
        defaults={
            "username": tg_user.username,
            "first_name": tg_user.first_name,
            "last_name": tg_user.last_name,
            "photo_url": tg_user.photo_url,
            "language_code": tg_user.language_code,
        },
    )

    if created:
        # Regular users authenticate via Telegram, never a password. get_or_create
        # bypasses the manager, so enforce an unusable password explicitly.
        user.set_unusable_password()
        user.save(update_fields=["password"])
    else:
        _sync_profile(user, tg_user)

    return user, created

def _sync_profile(user: User, tg_user: TelegramUser) -> None:
    """Update mutable Telegram-sourced fields if they have changed."""
    fields_to_update: list[str] = []
    for attr in ("username", "first_name", "last_name", "photo_url", "language_code"):
        new_value = getattr(tg_user, attr)
        if getattr(user, attr) != new_value:
            setattr(user, attr, new_value)
            fields_to_update.append(attr)
    if fields_to_update:
        user.save(update_fields=fields_to_update)
