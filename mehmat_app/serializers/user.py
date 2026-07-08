"""User profile serializers."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import User


class UserSerializer(serializers.ModelSerializer):
    """Public representation of a user's profile."""

    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "telegram_id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "photo_url",
            "language_code",
            "is_admin",
            "points",
            "current_rank",
            "streak",
            "completed_tests",
            "date_joined",
            "last_login",
        )
        read_only_fields = fields


class UserUpdateSerializer(serializers.ModelSerializer):
    """Serializer for the limited set of user-editable profile fields."""

    class Meta:
        model = User
        fields = ("language_code",)


class StatisticsSerializer(serializers.Serializer):
    """Serialized user performance statistics."""

    points = serializers.IntegerField()
    current_rank = serializers.CharField()
    leaderboard_position = serializers.IntegerField()
    streak = serializers.IntegerField()
    completed_tests = serializers.IntegerField()
    official_submissions = serializers.IntegerField()
    practice_submissions = serializers.IntegerField()
    average_score = serializers.FloatField()
    best_score = serializers.FloatField()
    total_time_spent = serializers.IntegerField()
    achievements_unlocked = serializers.IntegerField()
