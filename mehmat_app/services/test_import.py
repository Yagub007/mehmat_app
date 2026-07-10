"""Import tests from structured JSON into the Test/Question/Choice models.

Tests are authored as JSON (not Word documents) and loaded with the
``import_tests`` management command. The importer validates each test, is
idempotent (tests are keyed by title — re-importing updates in place), and
collects per-test errors rather than aborting the whole batch.

Expected JSON shape (a single object, or a list of them)::

    {
      "title": "НМТ · Пробний тест 1",
      "description": "…",
      "difficulty": "medium",          # easy | medium | hard  (default medium)
      "duration": 30,                  # minutes  (required, > 0)
      "reward_points": 20,             # default 0
      "is_published": true,            # default true
      "is_active": true,               # default true
      "questions": [
        {
          "text": "2 + 2 = ?",
          "type": "single",            # single | multiple | ordering
          "points": 1,                 # default 1
          "explanation": "…",          # optional
          "choices": [
            {"text": "3", "is_correct": false},
            {"text": "4", "is_correct": true}
          ]
        },
        {
          "text": "Розташуйте за зростанням",
          "type": "ordering",
          "choices": [                  # `order` encodes the correct position
            {"text": "1", "order": 0},
            {"text": "2", "order": 1}
          ]
        },
        {
          "text": "34 + 34 = ?",
          "type": "short_answer",       # free-text/numeric answer
          "correct_answer": "68"        # compared after normalising spaces/°
        },
        {
          "text": "Match the pairs",
          "type": "matching",
          "matching": {
            "left":  [{"id": "1", "text": "∠5"}, {"id": "2", "text": "∠3"}],
            "right": [{"id": "А", "text": "74°"}, {"id": "Б", "text": "127°"}],
            "answer": {"1": "Б", "2": "А"}  # left id → right id
          }
        }
      ]
    }

The importer also accepts the exam-style shape (``question`` instead of
``text``, ``single_choice`` type, and ``answers`` + a ``correct_answer`` letter),
so exported question banks can be loaded with minimal transformation.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from django.db import transaction

from mehmat_app.constants import QuestionType, TestDifficulty
from mehmat_app.models import Choice, Question, Test

logger = logging.getLogger(__name__)

_VALID_DIFFICULTY = {c.value for c in TestDifficulty}
_VALID_QTYPE = {c.value for c in QuestionType}


class TestValidationError(Exception):
    """Raised when a single test payload is structurally invalid."""


@dataclass
class TestImportStats:
    created: int = 0
    updated: int = 0
    questions: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "created": self.created,
            "updated": self.updated,
            "questions": self.questions,
            "errors": len(self.errors),
        }


class TestImportService:
    """Validates and upserts tests from JSON payloads."""

    def __init__(self, *, publish: bool | None = None, dry_run: bool = False) -> None:
        self._publish = publish  # None → use each payload's value
        self._dry_run = dry_run
        self.stats = TestImportStats()

    # -- entry points ------------------------------------------------------
    def import_path(self, path: str) -> TestImportStats:
        """Import a single ``.json`` file or every ``.json`` in a directory."""
        target = Path(path)
        if target.is_dir():
            files = sorted(target.glob("*.json"))
            if not files:
                raise FileNotFoundError(f"No .json files found in {target}")
        elif target.is_file():
            files = [target]
        else:
            raise FileNotFoundError(f"Path not found: {target}")

        for file in files:
            try:
                data = json.loads(file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError) as exc:
                self.stats.errors.append(f"{file.name}: invalid JSON ({exc})")
                continue
            self.import_data(data, source=file.name)
        return self.stats

    def import_data(self, data, *, source: str = "<data>") -> TestImportStats:
        """Import a test dict or a list of test dicts."""
        payloads = data if isinstance(data, list) else [data]
        for index, payload in enumerate(payloads):
            label = f"{source}[{index}]"
            try:
                self._upsert_test(payload, label)
            except TestValidationError as exc:
                self.stats.errors.append(f"{label}: {exc}")
            except Exception as exc:  # noqa: BLE001 - collect and continue
                self.stats.errors.append(f"{label}: {exc}")
                logger.exception("Failed to import test %s", label)
        return self.stats

    # -- upsert ------------------------------------------------------------
    def _upsert_test(self, payload: dict, label: str) -> None:
        if not isinstance(payload, dict):
            raise TestValidationError("expected a JSON object")
        title = str(payload.get("title", "")).strip()
        if not title:
            raise TestValidationError("missing 'title'")

        duration = payload.get("duration")
        if not isinstance(duration, int) or duration <= 0:
            raise TestValidationError("'duration' must be a positive integer (minutes)")

        difficulty = str(payload.get("difficulty", TestDifficulty.MEDIUM)).lower()
        if difficulty not in _VALID_DIFFICULTY:
            raise TestValidationError(
                f"invalid difficulty '{difficulty}' (use {sorted(_VALID_DIFFICULTY)})"
            )

        questions = payload.get("questions") or []
        if not questions:
            raise TestValidationError("test has no questions")

        # Validate all questions up front so we never write a partial test.
        parsed = [self._parse_question(q, i) for i, q in enumerate(questions)]

        is_published = self._publish if self._publish is not None else bool(
            payload.get("is_published", True)
        )
        fields = {
            "description": str(payload.get("description", "")),
            "difficulty": difficulty,
            "duration": duration,
            "reward_points": int(payload.get("reward_points", 0)),
            "is_active": bool(payload.get("is_active", True)),
            "is_published": is_published,
        }

        if self._dry_run:
            if Test.objects.filter(title=title).exists():
                self.stats.updated += 1
            else:
                self.stats.created += 1
            self.stats.questions += len(parsed)
            return

        with transaction.atomic():
            test, created = Test.objects.update_or_create(title=title, defaults=fields)
            if not created:
                # Replace questions wholesale so edits/removals take effect.
                test.questions.all().delete()

            for q_index, question in enumerate(parsed):
                q_obj = Question.objects.create(
                    test=test,
                    text=question["text"],
                    question_type=question["type"],
                    explanation=question["explanation"],
                    points=question["points"],
                    order=q_index,
                    correct_answer=question.get("correct_answer", ""),
                    matching=question.get("matching", {}),
                )
                if question["choices"]:
                    Choice.objects.bulk_create([
                        Choice(
                            question=q_obj,
                            text=choice["text"],
                            is_correct=choice["is_correct"],
                            order=choice["order"],
                        )
                        for choice in question["choices"]
                    ])
                self.stats.questions += 1

        if created:
            self.stats.created += 1
        else:
            self.stats.updated += 1

    # -- validation --------------------------------------------------------
    @staticmethod
    def _parse_question(raw: dict, index: int) -> dict:
        if not isinstance(raw, dict):
            raise TestValidationError(f"question {index}: expected an object")
        # Accept both the canonical `text` and the exam-style `question` key.
        text = str(raw.get("text") or raw.get("question") or "").strip()
        if not text:
            raise TestValidationError(f"question {index}: missing 'text'")

        qtype = str(raw.get("type", QuestionType.SINGLE)).lower()
        # Alias the exam-format type names onto canonical ones.
        qtype = {"single_choice": "single", "multiple_choice": "multiple"}.get(qtype, qtype)
        if qtype not in _VALID_QTYPE:
            raise TestValidationError(
                f"question {index}: invalid type '{qtype}' (use {sorted(_VALID_QTYPE)})"
            )

        parsed = {
            "text": text,
            "type": qtype,
            "explanation": str(raw.get("explanation", "")),
            "points": max(1, int(raw.get("points", 1))),
            "choices": [],
            "correct_answer": "",
            "matching": {},
        }

        if qtype == QuestionType.SHORT_ANSWER:
            answer = str(raw.get("correct_answer", "")).strip()
            if not answer:
                raise TestValidationError(
                    f"question {index}: short-answer needs a 'correct_answer'"
                )
            parsed["correct_answer"] = answer
            return parsed

        if qtype == QuestionType.MATCHING:
            parsed["matching"] = TestImportService._parse_matching(raw, index)
            return parsed

        parsed["choices"] = TestImportService._parse_choices(raw, index, qtype)
        return parsed

    @staticmethod
    def _parse_choices(raw: dict, index: int, qtype: str) -> list[dict]:
        raw_choices = raw.get("choices") or []
        if len(raw_choices) < 2:
            raise TestValidationError(f"question {index}: needs at least 2 choices")

        choices = []
        for c_index, choice in enumerate(raw_choices):
            if not isinstance(choice, dict) or not str(choice.get("text", "")).strip():
                raise TestValidationError(
                    f"question {index}: choice {c_index} missing 'text'"
                )
            choices.append({
                "text": str(choice["text"]).strip(),
                "is_correct": bool(choice.get("is_correct", False)),
                "order": int(choice.get("order", c_index)),
            })

        if qtype in (QuestionType.SINGLE, QuestionType.MULTIPLE):
            correct = [c for c in choices if c["is_correct"]]
            if not correct:
                raise TestValidationError(f"question {index}: no correct choice marked")
            if qtype == QuestionType.SINGLE and len(correct) > 1:
                raise TestValidationError(
                    f"question {index}: single-choice has multiple correct answers"
                )
        return choices

    @staticmethod
    def _parse_matching(raw: dict, index: int) -> dict:
        matching = raw.get("matching") or {}
        left = matching.get("left") or []
        right = matching.get("right") or []
        answer = matching.get("answer") or {}
        if len(left) < 2 or len(right) < 2:
            raise TestValidationError(
                f"question {index}: matching needs at least 2 left and right items"
            )
        if not answer:
            raise TestValidationError(f"question {index}: matching needs an 'answer' map")

        left_ids = {str(item["id"]) for item in left}
        right_ids = {str(item["id"]) for item in right}
        answer_map = {str(k): str(v) for k, v in answer.items()}
        if set(answer_map) != left_ids:
            raise TestValidationError(
                f"question {index}: matching answer must map every left item"
            )
        if not set(answer_map.values()) <= right_ids:
            raise TestValidationError(
                f"question {index}: matching answer references unknown right item"
            )
        return {
            "left": [{"id": str(i["id"]), "text": str(i["text"]).strip()} for i in left],
            "right": [{"id": str(i["id"]), "text": str(i["text"]).strip()} for i in right],
            "answer": answer_map,
        }
