"""Read-side helpers for categories and materials.

Categories form a tree (mirroring the imported folder hierarchy), so listings
and filtering operate over a category's whole subtree rather than only its
direct children.
"""
from __future__ import annotations

from collections import defaultdict

from django.db.models import Count, Q

from mehmat_app.models import Category


def _children_map() -> dict[int | None, list[int]]:
    """Return ``parent_id -> [child_id, …]`` for every category (one query)."""
    children: dict[int | None, list[int]] = defaultdict(list)
    for cid, pid in Category.objects.values_list("id", "parent_id"):
        children[pid].append(cid)
    return children


def subtree_ids(root_id: int, children_map: dict | None = None) -> list[int]:
    """Return ``root_id`` plus the ids of all its descendant categories."""
    children = children_map if children_map is not None else _children_map()
    collected: list[int] = []
    stack = [root_id]
    seen: set[int] = set()
    while stack:
        current = stack.pop()
        if current in seen:  # guard against accidental cycles
            continue
        seen.add(current)
        collected.append(current)
        stack.extend(children.get(current, []))
    return collected


def published_categories_with_counts() -> list[Category]:
    """Published categories, each annotated with a subtree material count.

    ``material_count`` counts published materials in the category *and all of
    its descendants*, so a top-level subject reflects everything beneath it.
    """
    direct = dict(
        Category.objects.filter(is_published=True)
        .annotate(
            n=Count(
                "materials",
                filter=Q(materials__is_published=True),
                distinct=True,
            )
        )
        .values_list("id", "n")
    )
    children = _children_map()
    categories = list(
        Category.objects.filter(is_published=True).order_by("ordering", "name")
    )
    for category in categories:
        category.material_count = sum(
            direct.get(cid, 0) for cid in subtree_ids(category.id, children)
        )
    return categories
