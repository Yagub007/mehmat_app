"""Test-taking views: list/retrieve tests, start sessions, submit attempts."""
from __future__ import annotations

from django.db.models import Count, Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import filters, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from mehmat_app.models import Choice, Question, Test
from mehmat_app.serializers.submissions import (
    SubmissionCreateSerializer,
    SubmissionSerializer,
)
from mehmat_app.serializers.tests import (
    TestDetailSerializer,
    TestListSerializer,
    TestSessionSerializer,
)
from mehmat_app.services.scoring import submit_test
from mehmat_app.services.sessions import start_session
from mehmat_app.throttles import TestSubmitThrottle


@extend_schema(tags=["tests"])
class TestViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Browse published tests and take them.

    Custom actions:
      * ``POST tests/{id}/start/``  — begin a server-timed session.
      * ``POST tests/{id}/submit/`` — submit answers for authoritative grading.
    """

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["difficulty"]
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "reward_points", "duration"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Test.objects.published().annotate(
            question_count=Count("questions", distinct=True)
        )
        if self.action == "retrieve":
            choices = Choice.objects.order_by("order", "id")
            questions = Question.objects.order_by("order", "id").prefetch_related(
                Prefetch("choices", queryset=choices)
            )
            queryset = queryset.prefetch_related(
                Prefetch("questions", queryset=questions)
            )
        return queryset

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TestDetailSerializer
        return TestListSerializer

    @extend_schema(request=None, responses={201: TestSessionSerializer})
    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        """Start (or resume) a timed session for this test."""
        test = self.get_object()
        session = start_session(user=request.user, test=test)
        return Response(
            TestSessionSerializer(session).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=SubmissionCreateSerializer,
        responses={201: SubmissionSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        throttle_classes=[TestSubmitThrottle],
    )
    def submit(self, request, pk=None):
        """Submit answers for grading. Scoring is fully server-side."""
        test = self.get_object()
        serializer = SubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        submission = submit_test(
            user=request.user,
            test=test,
            answers=serializer.to_answer_inputs(),
            session_id=serializer.validated_data.get("session_id"),
        )
        return Response(
            SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED
        )
