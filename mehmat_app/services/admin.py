"""Administrator actions on users, each recorded to the audit log.

All mutating helpers funnel through :func:`record_action` so that every change
made through the admin API leaves a traceable audit trail (who, what, target,
before/after). Point changes keep the denormalised ``current_rank`` in sync.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from mehmat_app.models import AdminAuditLog, User
from mehmat_app.services.ranking import rank_for_points


def record_action(
    *,
    admin: User,
    action: str,
    target: User | None = None,
    changes: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> AdminAuditLog:
    """Append an immutable audit-log entry for an administrator action."""
    return AdminAuditLog.objects.create(
        admin=admin,
        action=action,
        target_type="user" if target is not None else "",
        target_id=str(target.id) if target is not None else "",
        target_label=(target.username or target.full_name or f"tg:{target.telegram_id}")
        if target is not None
        else "",
        changes=changes or {},
        ip_address=ip_address,
    )


def _sync_rank(user: User) -> None:
    """Recompute the cached rank tier from the user's current points."""
    user.current_rank = rank_for_points(user.points)


@transaction.atomic
def set_points(admin: User, target: User, points: int, *, ip: str | None = None) -> User:
    """Set a user's points to an absolute value and re-derive their rank."""
    before = target.points
    target.points = max(0, int(points))
    _sync_rank(target)
    target.save(update_fields=["points", "current_rank"])
    record_action(
        admin=admin,
        action="user.set_points",
        target=target,
        changes={"points": {"from": before, "to": target.points}},
        ip_address=ip,
    )
    return target


@transaction.atomic
def adjust_points(admin: User, target: User, delta: int, *, ip: str | None = None) -> User:
    """Add (or subtract, for a negative delta) points, flooring at zero."""
    before = target.points
    target.points = max(0, before + int(delta))
    _sync_rank(target)
    target.save(update_fields=["points", "current_rank"])
    record_action(
        admin=admin,
        action="user.adjust_points",
        target=target,
        changes={"delta": int(delta), "points": {"from": before, "to": target.points}},
        ip_address=ip,
    )
    return target


@transaction.atomic
def reset_field(
    admin: User, target: User, field: str, *, ip: str | None = None
) -> User:
    """Reset one numeric counter (``points``/``streak``/``completed_tests``) to 0."""
    if field not in {"points", "streak", "completed_tests"}:
        raise ValueError(f"Unsupported reset field: {field}")
    before = getattr(target, field)
    setattr(target, field, 0)
    update_fields = [field]
    if field == "points":
        _sync_rank(target)
        update_fields.append("current_rank")
    target.save(update_fields=update_fields)
    record_action(
        admin=admin,
        action=f"user.reset_{field}",
        target=target,
        changes={field: {"from": before, "to": 0}},
        ip_address=ip,
    )
    return target


@transaction.atomic
def set_active(admin: User, target: User, active: bool, *, ip: str | None = None) -> User:
    """Ban (deactivate) or unban (reactivate) a user."""
    before = target.is_active
    target.is_active = bool(active)
    target.save(update_fields=["is_active"])
    record_action(
        admin=admin,
        action="user.unban" if active else "user.ban",
        target=target,
        changes={"is_active": {"from": before, "to": target.is_active}},
        ip_address=ip,
    )
    return target


@transaction.atomic
def set_admin(admin: User, target: User, is_admin: bool, *, ip: str | None = None) -> User:
    """Grant or revoke application-admin rights."""
    before = target.is_admin
    target.is_admin = bool(is_admin)
    target.save(update_fields=["is_admin"])
    record_action(
        admin=admin,
        action="user.grant_admin" if is_admin else "user.revoke_admin",
        target=target,
        changes={"is_admin": {"from": before, "to": target.is_admin}},
        ip_address=ip,
    )
    return target


@transaction.atomic
def apply_edits(
    admin: User, target: User, edits: dict[str, Any], *, ip: str | None = None
) -> User:
    """Apply a validated set of profile edits, recording each changed field."""
    changed: dict[str, Any] = {}
    for field, value in edits.items():
        before = getattr(target, field)
        if before == value:
            continue
        setattr(target, field, value)
        changed[field] = {"from": before, "to": value}
    if not changed:
        return target
    if "points" in changed:
        _sync_rank(target)
    target.save()
    record_action(
        admin=admin,
        action="user.edit",
        target=target,
        changes=changed,
        ip_address=ip,
    )
    return target


def delete_user(admin: User, target: User, *, ip: str | None = None) -> None:
    """Delete a user, recording the action before the row disappears."""
    record_action(
        admin=admin,
        action="user.delete",
        target=target,
        changes={"telegram_id": target.telegram_id, "username": target.username},
        ip_address=ip,
    )
    target.delete()
