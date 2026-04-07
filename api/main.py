from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, HTTPException, Query, Response
from pydantic import BaseModel, Field

from mobguard_platform import PlatformStore, validate_live_rules_patch, verify_telegram_auth
from mobguard_platform.runtime_paths import normalize_runtime_bound_settings, resolve_runtime_dir


ROOT_DIR = Path(__file__).resolve().parents[1]
BAN_SYSTEM_DIR = Path(resolve_runtime_dir(ROOT_DIR, os.getenv("BAN_SYSTEM_DIR")))
ENV_PATH = Path(os.getenv("MOBGUARD_ENV_FILE", str(BAN_SYSTEM_DIR.parent / ".env")))
TEMPLATE_CONFIG_PATH = ROOT_DIR / "config.json"

def _ensure_runtime_layout() -> None:
    BAN_SYSTEM_DIR.mkdir(parents=True, exist_ok=True)
    (BAN_SYSTEM_DIR / "health").mkdir(parents=True, exist_ok=True)
    if not (BAN_SYSTEM_DIR / "config.json").exists() and TEMPLATE_CONFIG_PATH.exists():
        shutil.copyfile(TEMPLATE_CONFIG_PATH, BAN_SYSTEM_DIR / "config.json")
    if not (BAN_SYSTEM_DIR / "bans.db").exists():
        (BAN_SYSTEM_DIR / "bans.db").touch()

_ensure_runtime_layout()
load_dotenv(ENV_PATH)

CONFIG_PATH = BAN_SYSTEM_DIR / "config.json"

with CONFIG_PATH.open("r", encoding="utf-8") as handle:
    CONFIG = normalize_runtime_bound_settings(json.load(handle), BAN_SYSTEM_DIR)

TG_ADMIN_BOT_TOKEN = os.getenv("TG_ADMIN_BOT_TOKEN", "")
TG_ADMIN_BOT_USERNAME = os.getenv("TG_ADMIN_BOT_USERNAME", "")
SESSION_COOKIE_NAME = os.getenv("MOBGUARD_SESSION_COOKIE", "mobguard_session")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "true").lower() == "true"

store = PlatformStore(CONFIG["settings"]["db_file"], CONFIG, str(CONFIG_PATH))
store.init_schema()
store.sync_runtime_config(CONFIG)

app = FastAPI(title="MobGuard Admin API", version="1.1.0")


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
    rules_state = store.get_live_rules_state()
    return {
        "bot_username": TG_ADMIN_BOT_USERNAME,
        "review_ui_base_url": rules_state["rules"].get("settings", {}).get("review_ui_base_url", ""),
        "panel_name": "MobGuard Admin",
    }


@app.post("/admin/auth/telegram/verify")
def auth_verify(body: TelegramVerifyRequest, response: Response) -> dict[str, Any]:
    if not TG_ADMIN_BOT_TOKEN:
        raise HTTPException(status_code=500, detail="TG_ADMIN_BOT_TOKEN is not configured")

    ok, reason = verify_telegram_auth(body.payload, TG_ADMIN_BOT_TOKEN)
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


@app.get("/admin/metrics/quality")
def get_quality(_: dict[str, Any] = Depends(get_session)) -> dict[str, Any]:
    return store.get_quality_metrics()
