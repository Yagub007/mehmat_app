"""Tests for the JSON test importer."""
from __future__ import annotations

from django.test import TestCase

from mehmat_app.constants import QuestionType
from mehmat_app.models import Choice, Question, Test
from mehmat_app.services.test_import import TestImportService

_VALID = {
    "title": "Пробний тест",
    "duration": 20,
    "difficulty": "medium",
    "reward_points": 10,
    "questions": [
        {
            "text": "2 + 2 = ?",
            "type": "single",
            "choices": [
                {"text": "4", "is_correct": True},
                {"text": "5", "is_correct": False},
            ],
        },
        {
            "text": "Порядок",
            "type": "ordering",
            "choices": [
                {"text": "a", "order": 0},
                {"text": "b", "order": 1},
            ],
        },
    ],
}


class TestImportServiceTests(TestCase):
    def test_creates_test_with_questions_and_choices(self) -> None:
        stats = TestImportService().import_data(_VALID)
        self.assertEqual(stats.created, 1)
        self.assertEqual(stats.errors, [])

        test = Test.objects.get(title="Пробний тест")
        self.assertEqual(test.duration, 20)
        self.assertEqual(test.questions.count(), 2)
        q1 = test.questions.get(order=0)
        self.assertEqual(q1.question_type, QuestionType.SINGLE)
        self.assertEqual(q1.choices.filter(is_correct=True).count(), 1)
        self.assertEqual(Choice.objects.filter(question__test=test).count(), 4)

    def test_reimport_updates_in_place(self) -> None:
        TestImportService().import_data(_VALID)
        test_id = Test.objects.get(title="Пробний тест").id

        changed = {**_VALID, "duration": 45, "questions": _VALID["questions"][:1]}
        stats = TestImportService().import_data(changed)

        self.assertEqual(stats.updated, 1)
        self.assertEqual(Test.objects.count(), 1)
        test = Test.objects.get(title="Пробний тест")
        self.assertEqual(test.id, test_id)  # preserves PK
        self.assertEqual(test.duration, 45)
        self.assertEqual(test.questions.count(), 1)  # old questions replaced

    def test_list_and_validation_errors_collected(self) -> None:
        payloads = [
            _VALID,
            {"title": "", "duration": 10, "questions": []},          # no title
            {"title": "X", "duration": 0, "questions": []},          # bad duration
            {"title": "Y", "duration": 5, "questions": [
                {"text": "q", "type": "single", "choices": [
                    {"text": "a", "is_correct": False},
                    {"text": "b", "is_correct": False},
                ]},
            ]},                                                       # no correct answer
        ]
        stats = TestImportService().import_data(payloads)
        self.assertEqual(stats.created, 1)
        self.assertEqual(len(stats.errors), 3)
        self.assertEqual(Test.objects.count(), 1)

    def test_dry_run_writes_nothing(self) -> None:
        stats = TestImportService(dry_run=True).import_data(_VALID)
        self.assertEqual(stats.created, 1)
        self.assertEqual(Test.objects.count(), 0)
        self.assertEqual(Question.objects.count(), 0)

    def test_no_publish_override(self) -> None:
        TestImportService(publish=False).import_data(_VALID)
        self.assertFalse(Test.objects.get(title="Пробний тест").is_published)
