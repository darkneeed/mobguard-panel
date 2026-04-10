from __future__ import annotations

from .app import app, container
from .services.runtime_state import build_user_card, resolve_user_identity


store = container.store


def _resolve_user_identity(identifier: str):
    return resolve_user_identity(container, store, identifier)


def _get_user_card(identifier: str):
    return build_user_card(store, _resolve_user_identity(identifier))
