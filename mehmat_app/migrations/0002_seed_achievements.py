"""Seed the built-in achievement catalogue."""
from __future__ import annotations

from django.db import migrations

ACHIEVEMENTS = [
    ("first_test", "First Test", "Complete your very first test.", "🎯", 1),
    ("points_100", "100 Points", "Earn a total of 100 points.", "💯", 2),
    ("points_500", "500 Points", "Earn a total of 500 points.", "🔥", 3),
    ("points_1000", "1000 Points", "Earn a total of 1000 points.", "🏆", 4),
    ("tests_5", "5 Tests", "Complete 5 official tests.", "📚", 5),
    ("tests_10", "10 Tests", "Complete 10 official tests.", "🎓", 6),
    ("perfect_score", "Perfect Score", "Score 100% on a test.", "⭐", 7),
    ("streak_7", "7 Day Streak", "Stay active for 7 days in a row.", "📅", 8),
]


def seed_achievements(apps, schema_editor) -> None:
    Achievement = apps.get_model("mehmat_app", "Achievement")
    for code, title, description, icon, ordering in ACHIEVEMENTS:
        Achievement.objects.update_or_create(
            code=code,
            defaults={
                "title": title,
                "description": description,
                "icon": icon,
                "ordering": ordering,
            },
        )


def unseed_achievements(apps, schema_editor) -> None:
    Achievement = apps.get_model("mehmat_app", "Achievement")
    Achievement.objects.filter(code__in=[a[0] for a in ACHIEVEMENTS]).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("mehmat_app", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_achievements, unseed_achievements),
    ]
