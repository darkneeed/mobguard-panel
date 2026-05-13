from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Response

from mobguard_platform import verify_telegram_auth
from mobguard_platform.admin_totp import generate_totp_secret, provisioning_uri, verify_totp_code
from mobguard_platform.module_secrets import (
    ModuleSecretError,
    decrypt_secret_value,
    encrypt_secret_value,
)
from mobguard_platform.runtime import read_env_file_only

from ..context import APIContainer
from ..permissions import ROLE_OWNER, permissions_for_role
from .runtime_state import get_auth_capabilities, load_env_values


BRANDING_DEFAULTS = {
    "panel_name": "MobGuard",
    "panel_logo_url": "",
}
CHALLENGE_TTL_SECONDS = 300


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _display_name(payload: dict[str, Any]) -> str:
    return str(payload.get("username") or payload.get("first_name") or payload.get("subject") or "admin")


def _build_identity_payload(
    *,
    subject: str,
    auth_method: str,
    role: str,
    telegram_id: int | None,
    username: str | None,
    first_name: str | None,
    totp_enabled: bool,
    totp_verified: bool,
    totp_verified_at: str | None = None,
) -> dict[str, Any]:
    return {
        "id": int(telegram_id or 0),
        "telegram_id": int(telegram_id or 0),
        "subject": subject,
        "auth_method": auth_method,
        "role": role,
        "username": username,
        "first_name": first_name,
        "permissions": permissions_for_role(role),
        "totp_enabled": bool(totp_enabled),
        "totp_verified": bool(totp_verified),
        "totp_verified_at": totp_verified_at or "",
    }


def _session_response(session: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "telegram_id": int(payload.get("telegram_id") or session.get("telegram_id") or 0),
        "username": payload.get("username"),
        "first_name": payload.get("first_name"),
        "expires_at": session["expires_at"],
        "subject": payload.get("subject", ""),
        "auth_method": payload.get("auth_method", ""),
        "role": payload.get("role", ""),
        "permissions": list(payload.get("permissions") or []),
        "totp_enabled": bool(payload.get("totp_enabled")),
        "totp_verified": bool(payload.get("totp_verified")),
        "totp_verified_at": payload.get("totp_verified_at", ""),
        "payload": payload,
    }


def _challenge_response(challenge: dict[str, Any], *, setup_required: bool) -> dict[str, Any]:
    return {
        "requires_totp": True,
        "totp_setup_required": bool(setup_required),
        "challenge_token": challenge["token"],
        "telegram_id": int(challenge.get("telegram_id") or 0),
        "username": challenge.get("username"),
        "first_name": challenge.get("first_name"),
        "subject": challenge.get("subject"),
        "auth_method": challenge.get("auth_method"),
        "role": challenge.get("role"),
        "permissions": permissions_for_role(challenge.get("role")),
        "totp_enabled": not setup_required,
        "totp_verified": False,
        "totp_verified_at": "",
    }


def _issue_session(container: APIContainer, response: Response, payload: dict[str, Any]) -> dict[str, Any]:
    session = container.store.create_admin_session(payload)
    set_session_cookie(container, response, session["token"])
    return _session_response(session, payload)


def _identity_record(
    container: APIContainer,
    *,
    subject: str,
    auth_method: str,
    role: str,
    telegram_id: int | None,
    username: str | None,
    first_name: str | None,
) -> dict[str, Any]:
    return container.store.upsert_admin_identity(
        subject=subject,
        auth_method=auth_method,
        role=role,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
    )


def _secret_key(container: APIContainer) -> str:
    env_values = read_env_file_only(str(container.runtime.env_path))
    secret_key = str(env_values.get("MOBGUARD_MODULE_SECRET_KEY") or "").strip()
    if not secret_key:
        raise HTTPException(status_code=409, detail="MOBGUARD_MODULE_SECRET_KEY is not configured")
    return secret_key


def _challenge_for_identity(
    container: APIContainer,
    *,
    subject: str,
    auth_method: str,
    role: str,
    telegram_id: int | None,
    username: str | None,
    first_name: str | None,
    setup_required: bool,
) -> dict[str, Any]:
    challenge = container.store.create_admin_totp_challenge(
        subject=subject,
        auth_method=auth_method,
        role=role,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        challenge_kind="setup" if setup_required else "verify",
        ttl_seconds=CHALLENGE_TTL_SECONDS,
    )
    return _challenge_response(challenge, setup_required=setup_required)


def _owner_totp_policy(
    container: APIContainer,
    subject: str,
) -> tuple[str, dict[str, Any] | None, dict[str, Any]]:
    identity = container.store.get_admin_identity(subject)
    summary = container.store.get_owner_totp_summary()
    if identity and bool(identity.get("totp_enabled")):
        return "verify", identity, summary
    if int(summary.get("owner_identity_count") or 0) == 0:
        return "setup", identity, summary
    if int(summary.get("enabled_owner_count") or 0) == 0:
        return "disabled", identity, summary
    return "setup", identity, summary


def _resolve_success_or_totp(
    container: APIContainer,
    response: Response,
    *,
    subject: str,
    auth_method: str,
    role: str,
    telegram_id: int | None,
    username: str | None,
    first_name: str | None,
) -> dict[str, Any]:
    owner_totp_mode = "disabled"
    existing_identity: dict[str, Any] | None = None
    if role == ROLE_OWNER:
        owner_totp_mode, existing_identity, _ = _owner_totp_policy(
            container,
            subject,
        )
    identity = _identity_record(
        container,
        subject=subject,
        auth_method=auth_method,
        role=role,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
    )
    if role == ROLE_OWNER:
        if owner_totp_mode in {"setup", "verify"}:
            return _challenge_for_identity(
                container,
                subject=subject,
                auth_method=auth_method,
                role=role,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                setup_required=owner_totp_mode == "setup",
            )
        payload = _build_identity_payload(
            subject=subject,
            auth_method=auth_method,
            role=role,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            totp_enabled=False,
            totp_verified=False,
        )
        return _issue_session(container, response, payload)
    payload = _build_identity_payload(
        subject=subject,
        auth_method=auth_method,
        role=role,
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        totp_enabled=bool((existing_identity or identity).get("totp_enabled")),
        totp_verified=False,
    )
    return _issue_session(container, response, payload)


def set_session_cookie(container: APIContainer, response: Response, token: str, max_age_seconds: int = 86400) -> None:
    response.set_cookie(
        key=container.session_cookie_name,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=container.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def clear_session_cookie(container: APIContainer, response: Response) -> None:
    response.delete_cookie(
        key=container.session_cookie_name,
        httponly=True,
        secure=container.session_cookie_secure,
        samesite="strict",
        path="/",
    )


def auth_start_payload(container: APIContainer) -> dict[str, Any]:
    env_values = load_env_values(container)
    rules_state = container.store.get_live_rules_state()
    runtime_settings = getattr(getattr(container, "runtime", None), "config", {}) or {}
    settings = runtime_settings.get("settings", {}) if isinstance(runtime_settings, dict) else {}
    return {
        **get_auth_capabilities(container, env_values),
        "review_ui_base_url": rules_state["rules"].get("settings", {}).get("review_ui_base_url", ""),
        "panel_name": str(settings.get("panel_name") or BRANDING_DEFAULTS["panel_name"]),
        "panel_logo_url": str(settings.get("panel_logo_url") or BRANDING_DEFAULTS["panel_logo_url"]),
    }


def verify_telegram_login(container: APIContainer, payload: dict[str, Any], response: Response) -> dict[str, Any]:
    env_values = load_env_values(container)
    telegram_bot_token = env_values.get("TG_ADMIN_BOT_TOKEN", "")
    telegram_bot_username = env_values.get("TG_ADMIN_BOT_USERNAME", "")
    if not telegram_bot_token or not telegram_bot_username:
        raise HTTPException(status_code=400, detail="Telegram auth is not configured")
    ok, reason = verify_telegram_auth(payload, telegram_bot_token)
    if not ok:
        raise HTTPException(status_code=401, detail=reason)
    tg_id = int(payload.get("id", 0) or 0)
    role = container.store.get_admin_role_for_tg_id(tg_id) if tg_id else None
    if not tg_id or not role:
        raise HTTPException(status_code=403, detail="Telegram account is not allowed")
    username = str(payload.get("username") or "").strip() or None
    first_name = str(payload.get("first_name") or "").strip() or username or f"tg:{tg_id}"
    return _resolve_success_or_totp(
        container,
        response,
        subject=f"tg:{tg_id}",
        auth_method="telegram",
        role=role,
        telegram_id=tg_id,
        username=username,
        first_name=first_name,
    )


def local_login(container: APIContainer, username: str, password: str, response: Response) -> dict[str, Any]:
    env_values = load_env_values(container)
    expected_username = env_values.get("PANEL_LOCAL_USERNAME", "")
    expected_password = env_values.get("PANEL_LOCAL_PASSWORD", "")
    bypass_totp = str(env_values.get("PANEL_LOCAL_BYPASS_TOTP", "")).strip().lower() in {"1", "true", "yes", "on"}
    if not expected_username or not expected_password:
        raise HTTPException(status_code=400, detail="Local auth is not configured")
    if not secrets.compare_digest(username, expected_username) or not secrets.compare_digest(password, expected_password):
        raise HTTPException(status_code=401, detail="Invalid local credentials")
    if bypass_totp:
        payload = _build_identity_payload(
            subject=f"local:{expected_username}",
            auth_method="local",
            role=ROLE_OWNER,
            telegram_id=None,
            username=expected_username,
            first_name="Local Admin",
            totp_enabled=False,
            totp_verified=True,
            totp_verified_at=_utcnow(),
        )
        return _issue_session(container, response, payload)
    return _resolve_success_or_totp(
        container,
        response,
        subject=f"local:{expected_username}",
        auth_method="local",
        role=ROLE_OWNER,
        telegram_id=None,
        username=expected_username,
        first_name="Local Admin",
    )


def totp_setup(container: APIContainer, challenge_token: str) -> dict[str, Any]:
    challenge = container.store.get_admin_totp_challenge(challenge_token)
    if not challenge:
        raise HTTPException(status_code=404, detail="TOTP challenge not found or expired")
    if str(challenge.get("challenge_kind")) != "setup":
        raise HTTPException(status_code=409, detail="TOTP setup is not available for this challenge")
    secret_key = _secret_key(container)
    temp_secret_cipher = str(challenge.get("temp_secret_cipher") or "").strip()
    if temp_secret_cipher:
        try:
            secret = decrypt_secret_value(
                secret_key,
                temp_secret_cipher,
                missing_error="Pending TOTP secret is unavailable",
                invalid_error="Pending TOTP secret cannot be decrypted with the configured secret key",
            )
        except ModuleSecretError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    else:
        secret = generate_totp_secret()
        try:
            temp_secret_cipher = encrypt_secret_value(
                secret_key,
                secret,
                empty_error="Pending TOTP secret is empty",
            )
        except ModuleSecretError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        container.store.update_admin_totp_challenge_secret(challenge_token, temp_secret_cipher)
    runtime_settings = getattr(getattr(container, "runtime", None), "config", {}) or {}
    settings = runtime_settings.get("settings", {}) if isinstance(runtime_settings, dict) else {}
    issuer = str(settings.get("panel_name") or BRANDING_DEFAULTS["panel_name"])
    account_name = _display_name(challenge)
    return {
        "challenge_token": challenge_token,
        "secret": secret,
        "provisioning_uri": provisioning_uri(secret, account_name, issuer=issuer),
        "account_name": account_name,
        "issuer": issuer,
    }


def _verify_challenge_code(
    container: APIContainer,
    *,
    challenge: dict[str, Any],
    secret: str,
    code: str,
    response: Response,
    totp_enabled: bool,
) -> dict[str, Any]:
    if not verify_totp_code(secret, code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code")
    verified_at = _utcnow()
    payload = _build_identity_payload(
        subject=str(challenge.get("subject") or ""),
        auth_method=str(challenge.get("auth_method") or ""),
        role=str(challenge.get("role") or ROLE_OWNER),
        telegram_id=int(challenge.get("telegram_id") or 0) or None,
        username=challenge.get("username"),
        first_name=challenge.get("first_name"),
        totp_enabled=totp_enabled,
        totp_verified=True,
        totp_verified_at=verified_at,
    )
    container.store.delete_admin_totp_challenge(str(challenge["token"]))
    return _issue_session(container, response, payload)


def totp_confirm_setup(container: APIContainer, challenge_token: str, code: str, response: Response) -> dict[str, Any]:
    challenge = container.store.get_admin_totp_challenge(challenge_token)
    if not challenge:
        raise HTTPException(status_code=404, detail="TOTP challenge not found or expired")
    if str(challenge.get("challenge_kind")) != "setup":
        raise HTTPException(status_code=409, detail="TOTP setup confirmation is unavailable for this challenge")
    secret_cipher = str(challenge.get("temp_secret_cipher") or "").strip()
    if not secret_cipher:
        raise HTTPException(status_code=400, detail="Call TOTP setup before confirming")
    secret_key = _secret_key(container)
    try:
        secret = decrypt_secret_value(
            secret_key,
            secret_cipher,
            missing_error="Pending TOTP secret is unavailable",
            invalid_error="Pending TOTP secret cannot be decrypted with the configured secret key",
        )
    except ModuleSecretError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    container.store.set_admin_identity_totp(str(challenge["subject"]), secret_cipher=secret_cipher, enabled=True)
    return _verify_challenge_code(
        container,
        challenge=challenge,
        secret=secret,
        code=code,
        response=response,
        totp_enabled=True,
    )


def totp_verify(container: APIContainer, challenge_token: str, code: str, response: Response) -> dict[str, Any]:
    challenge = container.store.get_admin_totp_challenge(challenge_token)
    if not challenge:
        raise HTTPException(status_code=404, detail="TOTP challenge not found or expired")
    if str(challenge.get("challenge_kind")) != "verify":
        raise HTTPException(status_code=409, detail="TOTP verification is unavailable for this challenge")
    identity = container.store.get_admin_identity(str(challenge["subject"]))
    if not identity or not bool(identity.get("totp_enabled")):
        raise HTTPException(status_code=409, detail="TOTP is not configured for this admin identity")
    secret_cipher = str(identity.get("totp_secret_cipher") or "").strip()
    secret_key = _secret_key(container)
    try:
        secret = decrypt_secret_value(
            secret_key,
            secret_cipher,
            missing_error="Stored TOTP secret is unavailable",
            invalid_error="Stored TOTP secret cannot be decrypted with the configured secret key",
        )
    except ModuleSecretError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return _verify_challenge_code(
        container,
        challenge=challenge,
        secret=secret,
        code=code,
        response=response,
        totp_enabled=True,
    )


def disable_owner_totp(container: APIContainer) -> dict[str, Any]:
    return container.store.disable_owner_totp()
