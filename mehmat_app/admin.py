"""Django admin configuration for the Mehmat backend."""
from __future__ import annotations

from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from mehmat_app.models import (
    Achievement,
    Category,
    Choice,
    Material,
    Notification,
    Question,
    Submission,
    SubmissionAnswer,
    Test,
    TestSession,
    User,
    UserAchievement,
)


# ---------------------------------------------------------------------------
# Reusable bulk actions
# ---------------------------------------------------------------------------
@admin.action(description="Mark selected items as published")
def make_published(modeladmin, request: HttpRequest, queryset: QuerySet) -> None:
    queryset.update(is_published=True)


@admin.action(description="Mark selected items as unpublished")
def make_unpublished(modeladmin, request: HttpRequest, queryset: QuerySet) -> None:
    queryset.update(is_published=False)


@admin.action(description="Activate selected tests")
def make_active(modeladmin, request: HttpRequest, queryset: QuerySet) -> None:
    queryset.update(is_active=True)


@admin.action(description="Deactivate selected tests")
def make_inactive(modeladmin, request: HttpRequest, queryset: QuerySet) -> None:
    queryset.update(is_active=False)


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "telegram_id",
        "username",
        "full_name",
        "points",
        "current_rank",
        "completed_tests",
        "streak",
        "is_admin",
        "is_active",
        "date_joined",
    )
    list_filter = ("current_rank", "is_admin", "is_staff", "is_active")
    search_fields = ("telegram_id", "username", "first_name", "last_name")
    ordering = ("-points",)
    readonly_fields = (
        "telegram_id",
        "date_joined",
        "last_login",
        "points",
        "current_rank",
        "streak",
        "completed_tests",
        "last_activity_date",
    )
    fieldsets = (
        ("Telegram", {
            "fields": (
                "telegram_id", "username", "first_name", "last_name",
                "photo_url", "language_code",
            )
        }),
        ("Progress", {
            "fields": (
                "points", "current_rank", "streak", "completed_tests",
                "last_activity_date",
            )
        }),
        ("Permissions", {
            "fields": ("is_admin", "is_staff", "is_superuser", "is_active"),
        }),
        ("Important dates", {"fields": ("date_joined", "last_login")}),
    )


# ---------------------------------------------------------------------------
# Categories & materials
# ---------------------------------------------------------------------------
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("full_path", "slug", "parent", "ordering", "is_published")
    list_filter = ("is_published",)
    search_fields = ("name", "slug", "source_path")
    list_editable = ("ordering", "is_published")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("parent",)
    ordering = ("ordering", "name")
    actions = [make_published, make_unpublished]
    readonly_fields = ("source_path", "created_at", "updated_at")


@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = (
        "title", "category", "file_type", "estimated_reading_time", "ordering",
        "is_published", "created_at",
    )
    list_filter = ("file_type", "subject", "is_published")
    search_fields = ("title", "description", "source_path")
    list_editable = ("ordering", "is_published")
    autocomplete_fields = ("category",)
    ordering = ("ordering", "-created_at")
    actions = [make_published, make_unpublished]
    readonly_fields = ("source_path", "created_at", "updated_at")


# ---------------------------------------------------------------------------
# Tests / questions / choices
# ---------------------------------------------------------------------------
class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 4
    fields = ("text", "is_correct", "order")


class QuestionInline(admin.TabularInline):
    model = Question
    extra = 1
    fields = ("text", "question_type", "points", "order")
    show_change_link = True


@admin.register(Test)
class TestAdmin(admin.ModelAdmin):
    list_display = (
        "title", "difficulty", "duration", "reward_points",
        "question_count", "is_published", "is_active", "created_at",
    )
    list_filter = ("difficulty", "is_published", "is_active")
    search_fields = ("title", "description")
    inlines = [QuestionInline]
    actions = [make_published, make_unpublished, make_active, make_inactive]
    readonly_fields = ("created_at", "updated_at")

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        return super().get_queryset(request).annotate(
            _question_count=Count("questions")
        )

    @admin.display(ordering="_question_count", description="Questions")
    def question_count(self, obj: Test) -> int:
        return obj._question_count


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "test", "question_type", "points", "order")
    list_filter = ("question_type", "test")
    search_fields = ("text",)
    inlines = [ChoiceInline]
    autocomplete_fields = ("test",)


# ---------------------------------------------------------------------------
# Sessions & submissions (read-only)
# ---------------------------------------------------------------------------
@admin.register(TestSession)
class TestSessionAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "test", "started_at", "expires_at", "is_completed")
    list_filter = ("is_completed",)
    search_fields = ("user__username", "user__telegram_id", "test__title")
    readonly_fields = ("user", "test", "started_at", "expires_at", "is_completed")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


class SubmissionAnswerInline(admin.TabularInline):
    model = SubmissionAnswer
    extra = 0
    fields = ("question", "is_correct", "ordering_answer")
    readonly_fields = fields
    can_delete = False

    def has_add_permission(self, request: HttpRequest, obj=None) -> bool:
        return False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = (
        "id", "user", "test", "is_official", "score", "points_earned",
        "correct_count", "wrong_count", "completion_time", "submitted_at",
    )
    list_filter = ("is_official", "test")
    search_fields = ("user__username", "user__telegram_id", "test__title")
    date_hierarchy = "submitted_at"
    inlines = [SubmissionAnswerInline]
    readonly_fields = (
        "user", "test", "session", "is_official", "score", "points_earned",
        "correct_count", "wrong_count", "total_questions", "completion_time",
        "started_at", "submitted_at", "created_at", "updated_at",
    )

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


# ---------------------------------------------------------------------------
# Achievements
# ---------------------------------------------------------------------------
@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = ("title", "code", "icon", "ordering")
    search_fields = ("title", "code")
    ordering = ("ordering",)


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = ("user", "achievement", "unlocked_at")
    list_filter = ("achievement",)
    search_fields = ("user__username", "user__telegram_id")
    readonly_fields = ("user", "achievement", "unlocked_at")

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
@admin.action(description="Mark selected notifications as read")
def mark_notifications_read(modeladmin, request: HttpRequest, queryset: QuerySet) -> None:
    queryset.update(is_read=True)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "is_read", "created_at")
    list_filter = ("is_read",)
    search_fields = ("title", "message", "user__username", "user__telegram_id")
    date_hierarchy = "created_at"
    actions = [mark_notifications_read]
