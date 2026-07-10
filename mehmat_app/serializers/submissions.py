"""Serializers for submitting and reading test submissions."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import Submission, SubmissionAnswer
from mehmat_app.services.scoring import AnswerInput


class AnswerInputSerializer(serializers.Serializer):
    """One answer within a submission payload.

    Structural validation only; membership and correctness are enforced
    server-side by the scoring service.
    """

    question_id = serializers.IntegerField(min_value=1)
    choice_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        allow_empty=True,
    )
    ordering = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        default=list,
        allow_empty=True,
    )
    text_answer = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=255, trim_whitespace=False
    )
    matching = serializers.DictField(
        child=serializers.CharField(), required=False, default=dict
    )

    def validate(self, attrs: dict) -> dict:
        if not (
            attrs.get("choice_ids")
            or attrs.get("ordering")
            or attrs.get("text_answer", "").strip()
            or attrs.get("matching")
        ):
            raise serializers.ValidationError(
                "Each answer must include choice_ids, ordering, text_answer or matching."
            )
        if len(set(attrs["choice_ids"])) != len(attrs["choice_ids"]):
            raise serializers.ValidationError("choice_ids must be unique.")
        if len(set(attrs["ordering"])) != len(attrs["ordering"]):
            raise serializers.ValidationError("ordering must not contain duplicates.")
        return attrs


class SubmissionCreateSerializer(serializers.Serializer):
    """Input payload for submitting a test attempt."""

    session_id = serializers.IntegerField(min_value=1, required=False, allow_null=True)
    answers = AnswerInputSerializer(many=True, allow_empty=False)

    def validate_answers(self, value: list[dict]) -> list[dict]:
        question_ids = [a["question_id"] for a in value]
        if len(set(question_ids)) != len(question_ids):
            raise serializers.ValidationError(
                "Duplicate answers for the same question are not allowed."
            )
        return value

    def to_answer_inputs(self) -> list[AnswerInput]:
        """Convert validated data into scoring-service input objects."""
        return [
            AnswerInput(
                question_id=answer["question_id"],
                choice_ids=list(answer["choice_ids"]),
                ordering=list(answer["ordering"]),
                text_answer=answer.get("text_answer", ""),
                matching=dict(answer.get("matching") or {}),
            )
            for answer in self.validated_data["answers"]
        ]


class SubmissionAnswerReadSerializer(serializers.ModelSerializer):
    """Read representation of a single graded answer."""

    selected_choice_ids = serializers.SerializerMethodField()

    class Meta:
        model = SubmissionAnswer
        fields = (
            "id",
            "question",
            "selected_choice_ids",
            "ordering_answer",
            "text_answer",
            "matching_answer",
            "is_correct",
        )
        read_only_fields = fields

    def get_selected_choice_ids(self, obj: SubmissionAnswer) -> list[int]:
        return [choice.id for choice in obj.selected_choices.all()]


class SubmissionSerializer(serializers.ModelSerializer):
    """Read representation of a graded submission."""

    answers = SubmissionAnswerReadSerializer(many=True, read_only=True)

    class Meta:
        model = Submission
        fields = (
            "id",
            "test",
            "is_official",
            "correct_count",
            "wrong_count",
            "total_questions",
            "score",
            "points_earned",
            "completion_time",
            "started_at",
            "submitted_at",
            "answers",
        )
        read_only_fields = fields


class SubmissionListSerializer(serializers.ModelSerializer):
    """Lightweight submission representation for listings."""

    class Meta:
        model = Submission
        fields = (
            "id",
            "test",
            "is_official",
            "correct_count",
            "wrong_count",
            "total_questions",
            "score",
            "points_earned",
            "completion_time",
            "submitted_at",
        )
        read_only_fields = fields
