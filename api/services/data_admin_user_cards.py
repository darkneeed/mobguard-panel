from __future__ import annotations

from typing import Any

from ..context import APIContainer
from .runtime_state import (
    build_user_export_payload,
    build_user_card,
    panel_client,
    resolve_user_identity,
    search_runtime_users,
)


def search_users(container: APIContainer, query: str) -> dict[str, Any]:
    items = search_runtime_users(container.store, query)
    panel_match = panel_client(container).get_user_data(query)
    return {"items": items, "panel_match": panel_match}


def get_user_card(container: APIContainer, identifier: str) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    return build_user_card(container.store, identity)


def get_user_card_export(container: APIContainer, identifier: str) -> dict[str, Any]:
    identity = resolve_user_identity(container, container.store, identifier)
    return build_user_export_payload(container.store, identifier, identity)
