"""Reusable object builders and helpers for the test suite."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from datetime import timedelta
from urllib.parse import urlencode

from django.utils import timezone

from mehmat_app.constants import QuestionType
from mehmat_app.models import Choice, Question, Test, TestSession, User

TEST_BOT_TOKEN = "123456789:TEST-TOKEN"


def build_init_data(
    *,
    bot_token: str = TEST_BOT_TOKEN,
    telegram_id: int = 555,
    username: str = "student",
    first_name: str = "Ada",
    last_name: str = "Lovelace",
    auth_date: int | None = None,
    tamper: bool = False,
) -> str:
    """Build a correctly-signed Telegram ``initData`` query string.

    When ``tamper`` is True the signature is deliberately corrupted.
    """
    auth_date = auth_date if auth_date is not None else int(time.time())
    user_payload = {
        "id": telegram_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "language_code": "uk",
    }
    fields = {
        "auth_date": str(auth_date),
        "query_id": "AAExampleQueryId",
        "user": json.dumps(user_payload, separators=(",", ":")),
    }
    data_check_string = "\n".join(f"{k}={fields[k]}" for k in sorted(fields))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    signature = hmac.new(
        secret_key, data_check_string.encode(), hashlib.sha256
    ).hexdigest()
    fields["hash"] = "0" * 64 if tamper else signature
    return urlencode(fields)


def create_user(telegram_id: int = 1, **kwargs) -> User:
    """Create a persisted user with sensible defaults."""
    defaults = {"username": f"user{telegram_id}"}
    defaults.update(kwargs)
    return User.objects.create_user(telegram_id=telegram_id, **defaults)


def create_test(
    *,
    title: str = "Algebra Basics",
    duration: int = 30,
    reward_points: int = 100,
    is_published: bool = True,
    is_active: bool = True,
    **kwargs,
) -> Test:
    """Create a published, active test by default."""
    return Test.objects.create(
        title=title,
        duration=duration,
        reward_points=reward_points,
        is_published=is_published,
        is_active=is_active,
        **kwargs,
    )


def add_single_choice_question(
    test: Test,
    *,
    order: int = 1,
    points: int = 1,
) -> tuple[Question, Choice, Choice]:
    """Add a single-choice question with one correct and one wrong choice."""
    question = Question.objects.create(
        test=test,
        text=f"Question {order}",
        question_type=QuestionType.SINGLE,
        points=points,
        order=order,
    )
    correct = Choice.objects.create(question=question, text="Correct", is_correct=True, order=1)
    wrong = Choice.objects.create(question=question, text="Wrong", is_correct=False, order=2)
    return question, correct, wrong


def add_multiple_choice_question(
    test: Test,
    *,
    order: int = 1,
    points: int = 1,
) -> tuple[Question, list[Choice]]:
    """Add a multiple-choice question with two correct and one wrong choice."""
    question = Question.objects.create(
        test=test,
        text=f"Multi {order}",
        question_type=QuestionType.MULTIPLE,
        points=points,
        order=order,
    )
    c1 = Choice.objects.create(question=question, text="A", is_correct=True, order=1)
    c2 = Choice.objects.create(question=question, text="B", is_correct=True, order=2)
    c3 = Choice.objects.create(question=question, text="C", is_correct=False, order=3)
    return question, [c1, c2, c3]


def add_ordering_question(
    test: Test,
    *,
    order: int = 1,
    points: int = 1,
) -> tuple[Question, list[Choice]]:
    """Add an ordering question whose correct order is c1, c2, c3."""
    question = Question.objects.create(
        test=test,
        text=f"Order {order}",
        question_type=QuestionType.ORDERING,
        points=points,
        order=order,
    )
    c1 = Choice.objects.create(question=question, text="First", order=1)
    c2 = Choice.objects.create(question=question, text="Second", order=2)
    c3 = Choice.objects.create(question=question, text="Third", order=3)
    return question, [c1, c2, c3]


def start_session(user: User, test: Test, *, started_seconds_ago: int = 0) -> TestSession:
    """Create an active session, optionally back-dated for timer tests."""
    now = timezone.now()
    started = now - timedelta(seconds=started_seconds_ago)
    return TestSession.objects.create(
        user=user,
        test=test,
        started_at=started,
        expires_at=started + timedelta(seconds=test.duration_seconds),
    )
