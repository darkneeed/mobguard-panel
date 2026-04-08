from __future__ import annotations

import json
import os
import secrets
import shutil
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from mobguard_platform import PlatformStore, validate_live_rules_patch, verify_telegram_auth
from mobguard_platform.configfile import read_json_file, update_json_file
from mobguard_platform.envfile import env_field_payload, get_env_file_status, read_env_file, update_env_file
from mobguard_platform.panel_client import PanelClient
from mobguard_platform.runtime_admin_defaults import (
    ENFORCEMENT_SETTINGS_DEFAULTS,
    ENFORCEMENT_TEMPLATE_DEFAULTS,
    TELEGRAM_RUNTIME_SETTINGS_DEFAULTS,
    normalize_telegram_runtime_settings,
)
from mobguard_platform.runtime_paths import normalize_runtime_bound_settings, resolve_runtime_dir


ROOT_DIR = Path(__file__).resolve().parents[1]
BAN_SYSTEM_DIR = Path(resolve_runtime_dir(ROOT_DIR, os.getenv("BAN_SYSTEM_DIR")))
ENV_PATH = Path(os.getenv("MOBGUARD_ENV_FILE", str(BAN_SYSTEM_DIR.parent / ".env")))

def _ensure_runtime_layout() -> None:
    BAN_SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    (BAN_SYSTEM_DIR / "health").mkdir(parents=True, exist_ok=True)
    if not (BAN_SYSTEM_DIR / "bans.db").exists():
        (BAN_SYSTEM_DIR / "bans.db").touch()

_ensure_runtime_layout()
load_dotenv(ENV_PATH)

CONFIG_PATH = BAN_SYSTEM_DIR / "config.json"

try:
    with CONFIG_PATH.open("r", encoding="utf-8") as handle:
        CONFIG = normalize_runtime_bound_settings(json.load(handle), BAN_SYSTEM_DIR)
except FileNotFoundError as exc:
    raise RuntimeError(f"Required runtime config not found: {CONFIG_PATH}") from exc

TG_ADMIN_BOT_TOKEN = os.getenv("TG_ADMIN_BOT_TOKEN", "")
TG_ADMIN_BOT_USERNAME = os.getenv("TG_ADMIN_BOT_USERNAME", "")
SESSION_COOKIE_NAME = os.getenv("MOBGUARD_SESSION_COOKIE", "mobguard_session")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"

store = PlatformStore(CONFIG["settings"]["db_file"], CONFIG, str(CONFIG_PATH))
store.init_schema()
store.sync_runtime_config(CONFIG)

app = FastAPI(title="MobGuard Admin API", version="1.1.0")

DETECTION_LIST_KEYS = (
    "pure_mobile_asns",
    "pure_home_asns",
    "mixed_asns",
    "allowed_isp_keywords",
    "home_isp_keywords",
    "exclude_isp_keywords",
)
ACCESS_LIST_KEYS = ("admin_tg_ids", "exempt_tg_ids", "exempt_ids")
TELEGRAM_ENV_FIELDS = {
    "TG_MAIN_BOT_TOKEN": True,
    "TG_ADMIN_BOT_TOKEN": True,
    "TG_ADMIN_BOT_USERNAME": False,
}
ACCESS_ENV_FIELDS = {
    "PANEL_LOCAL_USERNAME": False,
    "PANEL_LOCAL_PASSWORD": True,
}
TELEGRAM_CONFIG_KEYS = tuple(TELEGRAM_RUNTIME_SETTINGS_DEFAULTS.keys())
ENFORCEMENT_CONFIG_KEYS = tuple(ENFORCEMENT_SETTINGS_DEFAULTS.keys()) + tuple(
    ENFORCEMENT_TEMPLATE_DEFAULTS.keys()
)


class LocalLoginRequest(BaseModel):
    username: str
    password: str


class SettingsSectionUpdateRequest(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)
    lists: dict[str, list[Any]] = Field(default_factory=dict)
    env: dict[str, Any] = Field(default_factory=dict)
    revision: Optional[int] = None
    updated_at: Optional[str] = None


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_list(values: list[Any]) -> list[int]:
    result: list[int] = []
    for value in values:
        coerced = _coerce_optional_int(value)
        if coerced is not None:
            result.append(coerced)
    return result


class UserBanRequest(BaseModel):
    minutes: int = Field(default=15, gt=0)


class UserStrikesRequest(BaseModel):
    action: str = Field(default="set")
    count: int = Field(default=1, ge=0)


class UserWarningsRequest(BaseModel):
    action: str = Field(default="clear")
    count: int = Field(default=1, ge=0)


class UserExemptRequest(BaseModel):
    kind: str
    enabled: bool = True


class OverrideUpsertRequest(BaseModel):
    decision: str
    ttl_days: int = Field(default=7, ge=1, le=3650)


class CachePatchRequest(BaseModel):
    status: Optional[str] = None
    confidence: Optional[str] = None
    details: Optional[str] = None
    asn: Optional[int] = None
    expires: Optional[str] = None
    log_json: Optional[str] = None
    bundle_json: Optional[str] = None


class LegacyLearningPatchRequest(BaseModel):
    decision: Optional[str] = None
    confidence: Optional[int] = Field(default=None, ge=0)


def _load_runtime_config() -> dict[str, Any]:
    return normalize_runtime_bound_settings(read_json_file(str(CONFIG_PATH)), BAN_SYSTEM_DIR)


def _load_env_values() -> dict[str, str]:
    return read_env_file(str(ENV_PATH))


def _get_auth_capabilities(env_values: Optional[dict[str, str]] = None) -> dict[str, Any]:
    values = env_values or _load_env_values()
    telegram_enabled = bool(values.get("TG_ADMIN_BOT_TOKEN") and values.get("TG_ADMIN_BOT_USERNAME"))
    local_enabled = bool(values.get("PANEL_LOCAL_USERNAME") and values.get("PANEL_LOCAL_PASSWORD"))
    return {
        "telegram_enabled": telegram_enabled,
        "bot_username": values.get("TG_ADMIN_BOT_USERNAME", "") if telegram_enabled else "",
        "local_enabled": local_enabled,
        "local_username_hint": values.get("PANEL_LOCAL_USERNAME", "") if local_enabled else "",
    }


def _serialize_env_fields(field_map: dict[str, bool], env_values: Optional[dict[str, str]] = None) -> dict[str, Any]:
    values = env_values or _load_env_values()
    return {
        key: env_field_payload(key, values, masked=masked, restart_required=True)
        for key, masked in field_map.items()
    }


def _normalize_runtime_settings(config: dict[str, Any], defaults: dict[str, Any], aliases: Optional[dict[str, str]] = None) -> dict[str, Any]:
    aliases = aliases or {}
    settings = config.get("settings", {})
    normalized: dict[str, Any] = {}
    for key, default in defaults.items():
        if key in settings:
            normalized[key] = settings[key]
            continue
        alias_candidates = [legacy for legacy, canonical in aliases.items() if canonical == key]
        alias_value = next((settings.get(alias) for alias in alias_candidates if alias in settings), default)
        normalized[key] = alias_value
    return normalized


def _write_runtime_settings(settings_updates: dict[str, Any], *, remove_keys: Optional[list[str]] = None) -> dict[str, Any]:
    runtime_config = read_json_file(str(CONFIG_PATH))
    runtime_config.setdefault("settings", {})
    for key, value in settings_updates.items():
        runtime_config["settings"][key] = value
    for key in remove_keys or []:
        runtime_config["settings"].pop(key, None)
    return update_json_file(str(CONFIG_PATH), {"settings": runtime_config["settings"]})


def _panel_client() -> PanelClient:
    runtime_config = _load_runtime_config()
    env_values = _load_env_values()
    panel_url = str(runtime_config.get("settings", {}).get("panel_url", "")).strip()
    panel_token = env_values.get("PANEL_TOKEN", "")
    return PanelClient(panel_url, panel_token)


def _build_local_session_payload(username: str) -> dict[str, Any]:
    return {
        "id": 0,
        "username": username,
        "first_name": "Local Admin",
        "auth_method": "local",
    }


def _get_runtime_user_match(identifier: str) -> Optional[dict[str, Any]]:
    query = identifier.strip()
    if not query:
        return None
    with store._connect() as conn:
        exact = conn.execute(
            """
            SELECT uuid, username, system_id, telegram_id, updated_at
            FROM review_cases
            WHERE uuid = ? OR username = ? OR telegram_id = ? OR CAST(system_id AS TEXT) = ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (query, query, query, query),
        ).fetchone()
        if exact:
            return dict(exact)
        like = f"%{query}%"
        row = conn.execute(
            """
            SELECT uuid, username, system_id, telegram_id, updated_at
            FROM review_cases
            WHERE uuid LIKE ? OR username LIKE ? OR telegram_id LIKE ? OR CAST(system_id AS TEXT) LIKE ?
            ORDER BY updated_at DESC
            LIMIT 1
            """,
            (like, like, like, like),
        ).fetchone()
    return dict(row) if row else None


def _search_runtime_users(query: str) -> list[dict[str, Any]]:
    search = f"%{query.strip()}%"
    if not query.strip():
        return []
    with store._connect() as conn:
        rows = conn.execute(
            """
            SELECT uuid, username, system_id, telegram_id, MAX(updated_at) AS updated_at
            FROM review_cases
            WHERE uuid LIKE ? OR username LIKE ? OR telegram_id LIKE ? OR CAST(system_id AS TEXT) LIKE ?
            GROUP BY uuid, username, system_id, telegram_id
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            (search, search, search, search),
        ).fetchall()
    return [dict(row) for row in rows]


def _resolve_user_identity(identifier: str) -> dict[str, Any]:
    runtime_match = _get_runtime_user_match(identifier)
    panel_user = _panel_client().get_user_data(identifier)

    uuid = (panel_user or {}).get("uuid") or (runtime_match or {}).get("uuid")
    username = (panel_user or {}).get("username") or (runtime_match or {}).get("username")
    system_id = (
        (panel_user or {}).get("id")
        if (panel_user or {}).get("id") is not None
        else (runtime_match or {}).get("system_id")
    )
    telegram_id = (
        (panel_user or {}).get("telegramId")
        if (panel_user or {}).get("telegramId") is not None
        else (runtime_match or {}).get("telegram_id")
    )
    if not any(value not in (None, "") for value in (uuid, username, system_id, telegram_id)):
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "uuid": uuid,
        "username": username,
        "system_id": system_id,
        "telegram_id": telegram_id,
        "panel_user": panel_user,
    }


def _build_user_lookup_clause(identity: dict[str, Any]) -> tuple[str, list[Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if identity.get("uuid"):
        clauses.append("uuid = ?")
        params.append(identity["uuid"])
    if identity.get("system_id") not in (None, ""):
        clauses.append("system_id = ?")
        params.append(int(identity["system_id"]))
    if identity.get("telegram_id") not in (None, ""):
        clauses.append("telegram_id = ?")
        params.append(str(identity["telegram_id"]))
    if identity.get("username"):
        clauses.append("username = ?")
        params.append(identity["username"])
    if not clauses:
        raise HTTPException(status_code=404, detail="User lookup fields are unavailable")
    return " OR ".join(clauses), params


def _get_user_card(identifier: str) -> dict[str, Any]:
    identity = _resolve_user_identity(identifier)
    lookup_clause, lookup_params = _build_user_lookup_clause(identity)
    rules_state = store.get_live_rules_state()
    with store._connect() as conn:
        has_violations = store._table_exists(conn, "violations")
        has_violation_history = store._table_exists(conn, "violation_history")
        has_active_trackers = store._table_exists(conn, "active_trackers")
        has_ip_history = store._table_exists(conn, "ip_history")
        violation = conn.execute(
            "SELECT uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count FROM violations WHERE uuid = ?",
            (identity.get("uuid"),),
        ).fetchone() if identity.get("uuid") and has_violations else None
        history = conn.execute(
            """
            SELECT uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp
            FROM violation_history
            WHERE uuid = ?
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            (identity.get("uuid"),),
        ).fetchall() if identity.get("uuid") and has_violation_history else []
        trackers = conn.execute(
            """
            SELECT key, start_time, last_seen
            FROM active_trackers
            WHERE key LIKE ?
            ORDER BY last_seen DESC
            LIMIT 20
            """,
            (f"{identity.get('uuid')}:%",),
        ).fetchall() if identity.get("uuid") and has_active_trackers else []
        ip_history = conn.execute(
            """
            SELECT ip, timestamp
            FROM ip_history
            WHERE uuid = ?
            ORDER BY timestamp DESC
            LIMIT 20
            """,
            (identity.get("uuid"),),
        ).fetchall() if identity.get("uuid") and has_ip_history else []
        review_cases = conn.execute(
            f"""
            SELECT id, status, review_reason, ip, verdict, confidence_band, opened_at, updated_at
            FROM review_cases
            WHERE {lookup_clause}
            ORDER BY updated_at DESC
            LIMIT 20
            """,
            lookup_params,
        ).fetchall()
        recent_events = conn.execute(
            f"""
            SELECT id, created_at, ip, tag, verdict, confidence_band, score, isp, asn
            FROM analysis_events
            WHERE {lookup_clause}
            ORDER BY created_at DESC
            LIMIT 20
            """,
            lookup_params,
        ).fetchall()
        active_ban_count = conn.execute(
            "SELECT COUNT(*) AS cnt FROM violations WHERE uuid = ? AND unban_time > ?",
            (identity.get("uuid"), datetime.utcnow().isoformat()),
        ).fetchone()["cnt"] if identity.get("uuid") and has_violations else 0

    exempt_system_ids = set(_coerce_int_list(rules_state["rules"].get("exempt_ids", [])))
    exempt_tg_ids = set(_coerce_int_list(rules_state["rules"].get("exempt_tg_ids", [])))
    system_id = identity.get("system_id")
    telegram_id = identity.get("telegram_id")
    return {
        "identity": {
            "uuid": identity.get("uuid"),
            "username": identity.get("username"),
            "system_id": _coerce_optional_int(system_id),
            "telegram_id": str(telegram_id) if telegram_id not in (None, "") else None,
        },
        "panel_user": identity.get("panel_user"),
        "violation": dict(violation) if violation else None,
        "history": [dict(row) for row in history],
        "active_trackers": [dict(row) for row in trackers],
        "ip_history": [dict(row) for row in ip_history],
        "review_cases": [dict(row) for row in review_cases],
        "analysis_events": [dict(row) for row in recent_events],
        "flags": {
            "exempt_system_id": _coerce_optional_int(system_id) in exempt_system_ids if system_id not in (None, "") else False,
            "exempt_telegram_id": _coerce_optional_int(telegram_id) in exempt_tg_ids if telegram_id not in (None, "") else False,
            "active_ban": bool(active_ban_count),
            "active_warning": bool(violation and violation["warning_time"]),
        },
    }


class TelegramVerifyRequest(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class ReviewResolutionRequest(BaseModel):
    resolution: str
    note: str = ""


class RulesUpdateRequest(BaseModel):
    rules: dict[str, Any] = Field(default_factory=dict)
    revision: Optional[int] = None
    updated_at: Optional[str] = None


def _set_session_cookie(response: Response, token: str, max_age_seconds: int = 86400) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        httponly=True,
        secure=SESSION_COOKIE_SECURE,
        samesite="strict",
        path="/",
    )


def get_session(
    session_token: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
) -> dict[str, Any]:
    if not session_token:
        raise HTTPException(status_code=401, detail="Missing session cookie")
    session = store.get_admin_session(session_token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return session


@app.get("/health")
def health() -> dict[str, Any]:
    return store.get_health_snapshot()


@app.post("/admin/auth/telegram/start")
def auth_start() -> dict[str, Any]:
    env_values = _load_env_values()
    rules_state = store.get_live_rules_state()
    return {
        **_get_auth_capabilities(env_values),
        "review_ui_base_url": rules_state["rules"].get("settings", {}).get("review_ui_base_url", ""),
        "panel_name": "MobGuard Admin",
    }


@app.post("/admin/auth/telegram/verify")
def auth_verify(body: TelegramVerifyRequest, response: Response) -> dict[str, Any]:
    env_values = _load_env_values()
    telegram_bot_token = env_values.get("TG_ADMIN_BOT_TOKEN", "")
    telegram_bot_username = env_values.get("TG_ADMIN_BOT_USERNAME", "")
    if not telegram_bot_token or not telegram_bot_username:
        raise HTTPException(status_code=400, detail="Telegram auth is not configured")

    ok, reason = verify_telegram_auth(body.payload, telegram_bot_token)
    if not ok:
        raise HTTPException(status_code=401, detail=reason)

    tg_id = int(body.payload.get("id", 0) or 0)
    if not tg_id or not store.is_admin_tg_id(tg_id):
        raise HTTPException(status_code=403, detail="Telegram account is not allowed")

    session = store.create_admin_session(body.payload)
    _set_session_cookie(response, session["token"])
    return {
        "telegram_id": session["telegram_id"],
        "username": session.get("username"),
        "first_name": session.get("first_name"),
        "expires_at": session["expires_at"],
    }


@app.post("/admin/auth/local/login")
def local_login(body: LocalLoginRequest, response: Response) -> dict[str, Any]:
    env_values = _load_env_values()
    expected_username = env_values.get("PANEL_LOCAL_USERNAME", "")
    expected_password = env_values.get("PANEL_LOCAL_PASSWORD", "")
    if not expected_username or not expected_password:
        raise HTTPException(status_code=400, detail="Local auth is not configured")
    if not secrets.compare_digest(body.username, expected_username) or not secrets.compare_digest(
        body.password, expected_password
    ):
        raise HTTPException(status_code=401, detail="Invalid local credentials")

    session = store.create_admin_session(_build_local_session_payload(expected_username))
    _set_session_cookie(response, session["token"])
    return {
        "telegram_id": session["telegram_id"],
        "username": session.get("username"),
        "first_name": session.get("first_name"),
        "expires_at": session["expires_at"],
        "payload": {"auth_method": "local"},
    }


@app.post("/admin/logout")
def logout(response: Response, session: dict[str, Any] = Depends(get_session)) -> dict[str, bool]:
    store.delete_admin_session(session["token"])
    _clear_session_cookie(response)
    return {"ok": True}


@app.get("/admin/me")
def get_me(session: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    return {
        "telegram_id": session["telegram_id"],
        "username": session.get("username"),
        "first_name": session.get("first_name"),
        "expires_at": session["expires_at"],
        "payload": session.get("payload", {}),
    }


@app.get("/admin/reviews")
def list_reviews(
    status: Optional[str] = None,
    confidence_band: Optional[str] = None,
    review_reason: Optional[str] = None,
    severity: Optional[str] = None,
    punitive_eligible: Optional[bool] = None,
    asn: Optional[int] = None,
    q: Optional[str] = None,
    username: Optional[str] = None,
    system_id: Optional[int] = None,
    telegram_id: Optional[str] = None,
    opened_from: Optional[str] = None,
    opened_to: Optional[str] = None,
    repeat_count_min: Optional[int] = None,
    repeat_count_max: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort: str = Query(default="updated_desc"),
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    try:
        return store.list_review_cases(
            {
                "status": status,
                "confidence_band": confidence_band,
                "review_reason": review_reason,
                "severity": severity,
                "punitive_eligible": punitive_eligible,
                "asn": asn,
                "q": q,
                "username": username,
                "system_id": system_id,
                "telegram_id": telegram_id,
                "opened_from": opened_from,
                "opened_to": opened_to,
                "repeat_count_min": repeat_count_min,
                "repeat_count_max": repeat_count_max,
                "page": page,
                "page_size": page_size,
                "sort": sort,
            }
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/admin/reviews/{case_id}")
def get_review(case_id: int, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    try:
        return store.get_review_case(case_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/admin/reviews/{case_id}/resolve")
def resolve_review(
    case_id: int,
    body: ReviewResolutionRequest,
    session: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    try:
        return store.resolve_review_case(
            case_id,
            body.resolution.upper(),
            session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
            session["telegram_id"],
            body.note,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/admin/rules")
def get_rules(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    return store.get_live_rules_state()


@app.put("/admin/rules")
def put_rules(
    payload: RulesUpdateRequest,
    session: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    try:
        validate_live_rules_patch(payload.rules)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    try:
        return store.update_live_rules(
            payload.rules,
            session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
            session["telegram_id"],
            expected_revision=payload.revision,
            expected_updated_at=payload.updated_at,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/admin/settings/detection")
def get_detection_settings(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    state = store.get_live_rules_state()
    return {
        "revision": state["revision"],
        "updated_at": state["updated_at"],
        "updated_by": state["updated_by"],
        "rules": state["rules"],
    }


@app.put("/admin/settings/detection")
def put_detection_settings(
    payload: RulesUpdateRequest,
    session: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    return put_rules(payload, session)


@app.get("/admin/settings/access")
def get_access_settings(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    state = store.get_live_rules_state()
    env_values = _load_env_values()
    env_status = get_env_file_status(str(ENV_PATH))
    return {
        "revision": state["revision"],
        "updated_at": state["updated_at"],
        "updated_by": state["updated_by"],
        "lists": {key: state["rules"].get(key, []) for key in ACCESS_LIST_KEYS},
        "env": _serialize_env_fields(ACCESS_ENV_FIELDS, env_values),
        "auth": _get_auth_capabilities(env_values),
        "env_file_path": env_status["path"],
        "env_file_writable": env_status["writable"],
    }


@app.put("/admin/settings/access")
def put_access_settings(
    payload: SettingsSectionUpdateRequest,
    session: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    rules_payload = {key: payload.lists[key] for key in ACCESS_LIST_KEYS if key in payload.lists}
    if rules_payload:
        try:
            store.update_live_rules(
                rules_payload,
                session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
                session["telegram_id"],
                expected_revision=payload.revision,
                expected_updated_at=payload.updated_at,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    env_updates = {key: payload.env.get(key) for key in ACCESS_ENV_FIELDS if key in payload.env}
    if env_updates:
        try:
            update_env_file(str(ENV_PATH), env_updates)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return get_access_settings(session)


@app.get("/admin/settings/telegram")
def get_telegram_settings(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    runtime_config = _load_runtime_config()
    env_values = _load_env_values()
    env_status = get_env_file_status(str(ENV_PATH))
    settings = normalize_telegram_runtime_settings(runtime_config.get("settings", {}))
    return {
        "settings": settings,
        "env": _serialize_env_fields(TELEGRAM_ENV_FIELDS, env_values),
        "capabilities": {
            "admin_bot_enabled": bool(env_values.get("TG_ADMIN_BOT_TOKEN") and env_values.get("TG_ADMIN_BOT_USERNAME")),
            "user_bot_enabled": bool(env_values.get("TG_MAIN_BOT_TOKEN")),
        },
        "env_file_path": env_status["path"],
        "env_file_writable": env_status["writable"],
    }


@app.put("/admin/settings/telegram")
def put_telegram_settings(
    payload: SettingsSectionUpdateRequest,
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    settings_updates = {
        key: payload.settings[key] for key in TELEGRAM_CONFIG_KEYS if key in payload.settings
    }
    if settings_updates:
        _write_runtime_settings(settings_updates)

    env_updates = {key: payload.env.get(key) for key in TELEGRAM_ENV_FIELDS if key in payload.env}
    if env_updates:
        try:
            update_env_file(str(ENV_PATH), env_updates)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    return get_telegram_settings(_)


@app.get("/admin/settings/enforcement")
def get_enforcement_settings(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    runtime_config = _load_runtime_config()
    enforcement_settings = _normalize_runtime_settings(
        runtime_config,
        ENFORCEMENT_SETTINGS_DEFAULTS,
        aliases={"warning_timeout": "warning_timeout_seconds"},
    )
    templates = {
        key: runtime_config.get("settings", {}).get(key, default)
        for key, default in ENFORCEMENT_TEMPLATE_DEFAULTS.items()
    }
    return {
        "settings": {**enforcement_settings, **templates},
    }


@app.put("/admin/settings/enforcement")
def put_enforcement_settings(
    payload: SettingsSectionUpdateRequest,
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    settings_updates = {
        key: payload.settings[key] for key in ENFORCEMENT_CONFIG_KEYS if key in payload.settings
    }
    if settings_updates:
        _write_runtime_settings(settings_updates, remove_keys=["warning_timeout"])
    return get_enforcement_settings(_)


@app.get("/admin/data/users/search")
def search_users(query: str = Query(min_length=1), _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    items = _search_runtime_users(query)
    panel_match = _panel_client().get_user_data(query)
    return {"items": items, "panel_match": panel_match}


@app.get("/admin/data/users/{identifier}")
def get_user_card(identifier: str, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    return _get_user_card(identifier)


@app.post("/admin/data/users/{identifier}/ban")
def ban_user(
    identifier: str,
    body: UserBanRequest,
    session: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    identity = _resolve_user_identity(identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to ban a user")

    now = datetime.utcnow().replace(microsecond=0)
    with store._connect() as conn:
        row = conn.execute(
            "SELECT strikes FROM violations WHERE uuid = ?",
            (uuid,),
        ).fetchone()
        strikes = max(int(row["strikes"]) if row else 0, 1)
        unban_time = now + timedelta(minutes=body.minutes)
        conn.execute(
            """
            INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
            VALUES (?, ?, ?, ?, ?, NULL, 0)
            ON CONFLICT(uuid) DO UPDATE SET
                strikes = excluded.strikes,
                unban_time = excluded.unban_time,
                last_forgiven = excluded.last_forgiven,
                last_strike_time = excluded.last_strike_time,
                warning_time = NULL,
                warning_count = 0
            """,
            (uuid, strikes, unban_time.isoformat(), now.isoformat(), now.isoformat()),
        )
        conn.execute(
            """
            INSERT INTO violation_history (uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                uuid,
                "",
                "",
                None,
                "manual_data_admin",
                strikes,
                body.minutes,
                now.isoformat(),
            ),
        )
        conn.commit()

    panel = _panel_client()
    remote_updated = panel.toggle_user(uuid, False) if panel.enabled else False
    card = _get_user_card(identifier)
    card["remote_updated"] = remote_updated
    return card


@app.post("/admin/data/users/{identifier}/unban")
def unban_user(identifier: str, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    identity = _resolve_user_identity(identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to unban a user")

    with store._connect() as conn:
        conn.execute("DELETE FROM violations WHERE uuid = ?", (uuid,))
        conn.commit()

    panel = _panel_client()
    remote_updated = panel.toggle_user(uuid, True) if panel.enabled else False
    card = _get_user_card(identifier)
    card["remote_updated"] = remote_updated
    return card


@app.post("/admin/data/users/{identifier}/warnings")
def update_user_warnings(
    identifier: str,
    body: UserWarningsRequest,
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    identity = _resolve_user_identity(identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to update warnings")

    now = datetime.utcnow().replace(microsecond=0).isoformat()
    action = body.action.lower()
    with store._connect() as conn:
        row = conn.execute("SELECT strikes FROM violations WHERE uuid = ?", (uuid,)).fetchone()
        strikes = int(row["strikes"]) if row else 0
        if action == "clear":
            conn.execute(
                """
                INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
                VALUES (?, ?, NULL, NULL, NULL, NULL, 0)
                ON CONFLICT(uuid) DO UPDATE SET warning_time = NULL, warning_count = 0
                """,
                (uuid, strikes),
            )
        elif action == "set":
            conn.execute(
                """
                INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
                VALUES (?, ?, NULL, NULL, NULL, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET warning_time = excluded.warning_time, warning_count = excluded.warning_count
                """,
                (uuid, strikes, now, body.count),
            )
        else:
            raise HTTPException(status_code=400, detail="Unsupported warning action")
        conn.commit()
    return _get_user_card(identifier)


@app.post("/admin/data/users/{identifier}/strikes")
def update_user_strikes(
    identifier: str,
    body: UserStrikesRequest,
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    identity = _resolve_user_identity(identifier)
    uuid = identity.get("uuid")
    if not uuid:
        raise HTTPException(status_code=400, detail="UUID is required to update strikes")

    action = body.action.lower()
    with store._connect() as conn:
        row = conn.execute(
            "SELECT strikes, unban_time, warning_time, warning_count FROM violations WHERE uuid = ?",
            (uuid,),
        ).fetchone()
        current_strikes = int(row["strikes"]) if row else 0
        if action == "add":
            next_strikes = current_strikes + body.count
        elif action == "remove":
            next_strikes = max(current_strikes - body.count, 0)
        elif action == "set":
            next_strikes = body.count
        else:
            raise HTTPException(status_code=400, detail="Unsupported strike action")

        if next_strikes == 0:
            conn.execute("DELETE FROM violations WHERE uuid = ?", (uuid,))
        else:
            conn.execute(
                """
                INSERT INTO violations (uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count)
                VALUES (?, ?, ?, NULL, NULL, ?, ?)
                ON CONFLICT(uuid) DO UPDATE SET strikes = excluded.strikes
                """,
                (
                    uuid,
                    next_strikes,
                    row["unban_time"] if row else None,
                    row["warning_time"] if row else None,
                    int(row["warning_count"]) if row else 0,
                ),
            )
        conn.commit()
    return _get_user_card(identifier)


@app.post("/admin/data/users/{identifier}/exempt")
def update_user_exemptions(
    identifier: str,
    body: UserExemptRequest,
    session: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    identity = _resolve_user_identity(identifier)
    kind = body.kind.lower()
    if kind == "system":
        key = "exempt_ids"
        value = _coerce_optional_int(identity.get("system_id"))
    elif kind == "telegram":
        key = "exempt_tg_ids"
        value = _coerce_optional_int(identity.get("telegram_id"))
    else:
        raise HTTPException(status_code=400, detail="Unsupported exemption kind")
    if value is None:
        raise HTTPException(status_code=400, detail="Resolved user has no matching identifier for this exemption")

    state = store.get_live_rules_state()
    current_values = _coerce_int_list(state["rules"].get(key, []))
    if body.enabled and value not in current_values:
        current_values.append(value)
    if not body.enabled:
        current_values = [item for item in current_values if item != value]

    store.update_live_rules(
        {key: current_values},
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
    )
    return _get_user_card(identifier)


@app.get("/admin/data/violations")
def list_violations(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        if not store._table_exists(conn, "violations") or not store._table_exists(conn, "violation_history"):
            return {"active": [], "history": []}
        active = conn.execute(
            """
            SELECT uuid, strikes, unban_time, last_forgiven, last_strike_time, warning_time, warning_count
            FROM violations
            ORDER BY COALESCE(unban_time, warning_time, last_strike_time) DESC
            LIMIT 200
            """
        ).fetchall()
        history = conn.execute(
            """
            SELECT id, uuid, ip, isp, asn, tag, strike_number, punishment_duration, timestamp
            FROM violation_history
            ORDER BY timestamp DESC
            LIMIT 200
            """
        ).fetchall()
    return {
        "active": [dict(row) for row in active],
        "history": [dict(row) for row in history],
    }


@app.get("/admin/data/overrides")
def list_overrides(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        if not store._table_exists(conn, "unsure_patterns"):
            unsure = []
        else:
            unsure = conn.execute(
                """
                SELECT ip_pattern, decision, timestamp
                FROM unsure_patterns
                ORDER BY timestamp DESC
                """
            ).fetchall()
        exact_ip = conn.execute(
            """
            SELECT ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at
            FROM exact_ip_overrides
            ORDER BY updated_at DESC
            """
        ).fetchall()
    return {
        "exact_ip": [dict(row) for row in exact_ip],
        "unsure_patterns": [dict(row) for row in unsure],
    }


@app.put("/admin/data/overrides/ip/{ip}")
def upsert_exact_ip_override(
    ip: str,
    body: OverrideUpsertRequest,
    session: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    store.set_ip_override(
        ip,
        body.decision.upper(),
        "data_admin",
        session.get("username") or session.get("first_name") or f"tg:{session['telegram_id']}",
        session["telegram_id"],
        ttl_days=body.ttl_days,
    )
    return {"ok": True, "ip": ip, "decision": body.decision.upper()}


@app.delete("/admin/data/overrides/ip/{ip}")
def delete_exact_ip_override(ip: str, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        conn.execute("DELETE FROM exact_ip_overrides WHERE ip = ?", (ip,))
        conn.commit()
    return {"ok": True}


@app.put("/admin/data/overrides/unsure/{ip}")
def upsert_unsure_override(
    ip: str,
    body: OverrideUpsertRequest,
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    now = datetime.utcnow().replace(microsecond=0).isoformat()
    with store._connect() as conn:
        if not store._table_exists(conn, "unsure_patterns"):
            raise HTTPException(status_code=400, detail="unsure_patterns table is unavailable")
        conn.execute(
            """
            INSERT INTO unsure_patterns (ip_pattern, decision, timestamp)
            VALUES (?, ?, ?)
            ON CONFLICT(ip_pattern) DO UPDATE SET decision = excluded.decision, timestamp = excluded.timestamp
            """,
            (ip, body.decision.upper(), now),
        )
        conn.commit()
    return {"ok": True, "ip": ip, "decision": body.decision.upper()}


@app.delete("/admin/data/overrides/unsure/{ip}")
def delete_unsure_override(ip: str, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        if not store._table_exists(conn, "unsure_patterns"):
            return {"ok": True}
        conn.execute("DELETE FROM unsure_patterns WHERE ip_pattern = ?", (ip,))
        conn.commit()
    return {"ok": True}


@app.get("/admin/data/cache")
def list_cache(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        if not store._table_exists(conn, "ip_decisions"):
            return {"items": []}
        rows = conn.execute(
            """
            SELECT ip, status, confidence, details, asn, expires, log_json, bundle_json
            FROM ip_decisions
            ORDER BY expires DESC
            LIMIT 200
            """
        ).fetchall()
    return {"items": [dict(row) for row in rows]}


@app.patch("/admin/data/cache/{ip}")
def patch_cache(ip: str, body: CachePatchRequest, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    updates = {
        key: value
        for key, value in body.model_dump().items()
        if value is not None
    }
    if not updates:
        raise HTTPException(status_code=400, detail="No cache fields provided")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with store._connect() as conn:
        if not store._table_exists(conn, "ip_decisions"):
            raise HTTPException(status_code=400, detail="ip_decisions table is unavailable")
        conn.execute(
            f"UPDATE ip_decisions SET {assignments} WHERE ip = ?",
            [*updates.values(), ip],
        )
        conn.commit()
        row = conn.execute(
            "SELECT ip, status, confidence, details, asn, expires, log_json, bundle_json FROM ip_decisions WHERE ip = ?",
            (ip,),
        ).fetchone()
    return dict(row) if row else {"ok": False}


@app.delete("/admin/data/cache/{ip}")
def delete_cache(ip: str, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        if not store._table_exists(conn, "ip_decisions"):
            return {"ok": True}
        conn.execute("DELETE FROM ip_decisions WHERE ip = ?", (ip,))
        conn.commit()
    return {"ok": True}


@app.get("/admin/data/learning")
def get_learning_admin(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        if not store._table_exists(conn, "unsure_learning"):
            return {"promoted_active": [], "promoted_stats": [], "legacy": []}
        promoted_active = conn.execute(
            """
            SELECT pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
            FROM learning_patterns_active
            ORDER BY support DESC, precision DESC
            LIMIT 200
            """
        ).fetchall()
        promoted_stats = conn.execute(
            """
            SELECT pattern_type, pattern_value, decision, support, total, precision, updated_at, metadata_json
            FROM learning_pattern_stats
            ORDER BY total DESC, precision DESC
            LIMIT 200
            """
        ).fetchall()
        legacy = conn.execute(
            """
            SELECT id, pattern_type, pattern_value, decision, confidence, timestamp
            FROM unsure_learning
            ORDER BY confidence DESC, timestamp DESC
            LIMIT 200
            """
        ).fetchall()
    return {
        "promoted_active": [dict(row) for row in promoted_active],
        "promoted_stats": [dict(row) for row in promoted_stats],
        "legacy": [dict(row) for row in legacy],
    }


@app.patch("/admin/data/learning/legacy/{row_id}")
def patch_legacy_learning(
    row_id: int,
    body: LegacyLearningPatchRequest,
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    updates = {key: value for key, value in body.model_dump().items() if value is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No legacy learning fields provided")
    assignments = ", ".join(f"{key} = ?" for key in updates)
    with store._connect() as conn:
        if not store._table_exists(conn, "unsure_learning"):
            raise HTTPException(status_code=400, detail="unsure_learning table is unavailable")
        conn.execute(
            f"UPDATE unsure_learning SET {assignments} WHERE id = ?",
            [*updates.values(), row_id],
        )
        conn.commit()
        row = conn.execute(
            "SELECT id, pattern_type, pattern_value, decision, confidence, timestamp FROM unsure_learning WHERE id = ?",
            (row_id,),
        ).fetchone()
    return dict(row) if row else {"ok": False}


@app.delete("/admin/data/learning/legacy/{row_id}")
def delete_legacy_learning(row_id: int, _: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    with store._connect() as conn:
        if not store._table_exists(conn, "unsure_learning"):
            return {"ok": True}
        conn.execute("DELETE FROM unsure_learning WHERE id = ?", (row_id,))
        conn.commit()
    return {"ok": True}


@app.get("/admin/data/cases")
def list_cases(
    status: Optional[str] = None,
    confidence_band: Optional[str] = None,
    review_reason: Optional[str] = None,
    severity: Optional[str] = None,
    punitive_eligible: Optional[bool] = None,
    asn: Optional[int] = None,
    q: Optional[str] = None,
    username: Optional[str] = None,
    system_id: Optional[int] = None,
    telegram_id: Optional[str] = None,
    opened_from: Optional[str] = None,
    opened_to: Optional[str] = None,
    repeat_count_min: Optional[int] = None,
    repeat_count_max: Optional[int] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    sort: str = Query(default="updated_desc"),
    _: dict[str, Any] = Depends(get_session),
) -> dict[str, Any]:
    return list_reviews(
        status=status,
        confidence_band=confidence_band,
        review_reason=review_reason,
        severity=severity,
        punitive_eligible=punitive_eligible,
        asn=asn,
        q=q,
        username=username,
        system_id=system_id,
        telegram_id=telegram_id,
        opened_from=opened_from,
        opened_to=opened_to,
        repeat_count_min=repeat_count_min,
        repeat_count_max=repeat_count_max,
        page=page,
        page_size=page_size,
        sort=sort,
        _=_,
    )


@app.get("/admin/metrics/quality")
def get_quality(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    return store.get_quality_metrics()
