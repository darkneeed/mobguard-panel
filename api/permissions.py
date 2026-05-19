from __future__ import annotations

import os
from typing import Any


ROLE_OWNER = "owner"
ROLE_MODERATOR = "moderator"
ROLE_VIEWER = "viewer"
ROLE_VALUES = (ROLE_OWNER, ROLE_MODERATOR, ROLE_VIEWER)

PERMISSION_OVERVIEW_READ = "overview.read"
PERMISSION_QUALITY_READ = "quality.read"
PERMISSION_REVIEWS_READ = "reviews.read"
PERMISSION_REVIEWS_RESOLVE = "reviews.resolve"
PERMISSION_REVIEWS_RECHECK = "reviews.recheck"
PERMISSION_RULES_READ = "rules.read"
PERMISSION_RULES_WRITE = "rules.write"
PERMISSION_SETTINGS_TELEGRAM_READ = "settings.telegram.read"
PERMISSION_SETTINGS_TELEGRAM_WRITE = "settings.telegram.write"
PERMISSION_SETTINGS_ENFORCEMENT_READ = "settings.enforcement.read"
PERMISSION_SETTINGS_ENFORCEMENT_WRITE = "settings.enforcement.write"
PERMISSION_SETTINGS_ACCESS_READ = "settings.access.read"
PERMISSION_SETTINGS_ACCESS_WRITE = "settings.access.write"
PERMISSION_DATA_READ = "data.read"
PERMISSION_DATA_WRITE = "data.write"
PERMISSION_MODULES_READ = "modules.read"
PERMISSION_MODULES_WRITE = "modules.write"
PERMISSION_MODULES_TOKEN_REVEAL = "modules.token_reveal"
PERMISSION_AUDIT_READ = "audit.read"

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    ROLE_OWNER: (
        PERMISSION_OVERVIEW_READ,
        PERMISSION_QUALITY_READ,
        PERMISSION_REVIEWS_READ,
        PERMISSION_REVIEWS_RESOLVE,
        PERMISSION_REVIEWS_RECHECK,
        PERMISSION_RULES_READ,
        PERMISSION_RULES_WRITE,
        PERMISSION_SETTINGS_TELEGRAM_READ,
        PERMISSION_SETTINGS_TELEGRAM_WRITE,
        PERMISSION_SETTINGS_ENFORCEMENT_READ,
        PERMISSION_SETTINGS_ENFORCEMENT_WRITE,
        PERMISSION_SETTINGS_ACCESS_READ,
        PERMISSION_SETTINGS_ACCESS_WRITE,
        PERMISSION_DATA_READ,
        PERMISSION_DATA_WRITE,
        PERMISSION_MODULES_READ,
        PERMISSION_MODULES_WRITE,
        PERMISSION_MODULES_TOKEN_REVEAL,
        PERMISSION_AUDIT_READ,
    ),
    ROLE_MODERATOR: (
        PERMISSION_OVERVIEW_READ,
        PERMISSION_QUALITY_READ,
        PERMISSION_REVIEWS_READ,
        PERMISSION_REVIEWS_RESOLVE,
        PERMISSION_REVIEWS_RECHECK,
        PERMISSION_DATA_READ,
        PERMISSION_DATA_WRITE,
        PERMISSION_MODULES_READ,
        PERMISSION_AUDIT_READ,
    ),
    ROLE_VIEWER: (
        PERMISSION_OVERVIEW_READ,
        PERMISSION_QUALITY_READ,
        PERMISSION_REVIEWS_READ,
        PERMISSION_DATA_READ,
        PERMISSION_MODULES_READ,
        PERMISSION_AUDIT_READ,
    ),
}

SINGLE_ADMIN_MODE_DEFAULT = os.getenv("MOBGUARD_SINGLE_ADMIN_MODE", "true").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}


def normalize_role(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in ROLE_VALUES:
        return normalized
    return ROLE_VIEWER


def permissions_for_role(role: Any) -> list[str]:
    normalized = normalize_role(role)
    return list(ROLE_PERMISSIONS.get(normalized, ROLE_PERMISSIONS[ROLE_VIEWER]))


def permission_set_for_role(role: Any) -> set[str]:
    return set(permissions_for_role(role))


def role_for_telegram_id(rules: dict[str, Any], tg_id: int) -> str | None:
    numeric_id = int(tg_id)
    owner_ids = {int(value) for value in rules.get("admin_tg_ids", [])}
    moderator_ids = {int(value) for value in rules.get("moderator_tg_ids", [])}
    viewer_ids = {int(value) for value in rules.get("viewer_tg_ids", [])}
    if numeric_id in owner_ids:
        return ROLE_OWNER
    if SINGLE_ADMIN_MODE_DEFAULT:
        return None
    if numeric_id in moderator_ids:
        return ROLE_MODERATOR
    if numeric_id in viewer_ids:
        return ROLE_VIEWER
    return None


def session_has_permission(session: dict[str, Any], permission: str) -> bool:
    payload_permissions = session.get("permissions")
    if isinstance(payload_permissions, list) and permission in payload_permissions:
        return True
    role = normalize_role(session.get("role"))
    return permission in permission_set_for_role(role)
