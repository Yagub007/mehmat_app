"""Shared pagination classes."""
from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    """Page-number pagination with a client-tunable, capped page size."""

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class LeaderboardPagination(PageNumberPagination):
    """Larger default page size tuned for leaderboard listings."""

    page_size = 50
    page_size_query_param = "page_size"
    max_page_size = 200
