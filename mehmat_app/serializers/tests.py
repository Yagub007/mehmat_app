"""Serializers for the testing system (test-taking side)."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import Choice, Question, Test, TestSession


class ChoicePublicSerializer(serializers.ModelSerializer):
    """A choice as shown to a test-taker (never exposes ``is_correct``)."""

    class Meta:
        model = Choice
        fields = ("id", "text", "order")
        read_only_fields = fields


class QuestionPublicSerializer(serializers.ModelSerializer):
    """A question with its choices, safe for delivery to a test-taker."""

    choices = ChoicePublicSerializer(many=True, read_only=True)
    question_type_display = serializers.CharField(
        source="get_question_type_display", read_only=True
    )
    matching = serializers.SerializerMethodField()

    class Meta:
        model = Question
        fields = (
            "id",
            "text",
            "question_type",
            "question_type_display",
            "image",
            "points",
            "order",
            "choices",
            "matching",
        )
        read_only_fields = fields

    def get_matching(self, obj: Question) -> dict | None:
        """Return the matching prompt (left/right items) without the answer key."""
        data = obj.matching or {}
        if not data:
            return None
        return {"left": data.get("left", []), "right": data.get("right", [])}


class TestListSerializer(serializers.ModelSerializer):
    """Lightweight representation for test listings."""

    difficulty_display = serializers.CharField(
        source="get_difficulty_display", read_only=True
    )
    question_count = serializers.IntegerField(read_only=True)
    is_available = serializers.SerializerMethodField()

    class Meta:
        model = Test
        fields = (
            "id",
            "title",
            "description",
            "difficulty",
            "difficulty_display",
            "duration",
            "reward_points",
            "start_datetime",
            "end_datetime",
            "question_count",
            "is_available",
            "created_at",
        )
        read_only_fields = fields

    def get_is_available(self, obj: Test) -> bool:
        return obj.is_available()


class TestDetailSerializer(TestListSerializer):
    """Full test representation including questions and choices."""

    questions = QuestionPublicSerializer(many=True, read_only=True)

    class Meta(TestListSerializer.Meta):
        fields = TestListSerializer.Meta.fields + ("questions",)
        read_only_fields = fields


class TestSessionSerializer(serializers.ModelSerializer):
    """Represents a started test-taking session (server-side timer)."""

    class Meta:
        model = TestSession
        fields = ("id", "test", "started_at", "expires_at", "is_completed")
        read_only_fields = fields
