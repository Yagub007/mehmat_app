"""Leaderboard serializers."""
from __future__ import annotations

from rest_framework import serializers

from mehmat_app.models import User


class LeaderboardEntrySerializer(serializers.ModelSerializer):
    """A single leaderboard row."""

    full_name = serializers.CharField(read_only=True)
    total_completion_time = serializers.IntegerField(read_only=True)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "full_name",
            "photo_url",
            "points",
            "current_rank",
            "completed_tests",
            "total_completion_time",
        )
        read_only_fields = fields


class MyRankSerializer(serializers.Serializer):
    """The requesting user's leaderboard position and headline stats."""

    position = serializers.IntegerField()
    points = serializers.IntegerField()
    current_rank = serializers.CharField()
    completed_tests = serializers.IntegerField()
