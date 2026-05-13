from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any, Optional

from ..auth import issue_session_token
from .base import SQLiteRepository


def utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


class AdminSecurityRepository(SQLiteRepository):
    def upsert_identity(
        self,
        *,
        subject: str,
        auth_method: str,
        role: str,
        telegram_id: int | None = None,
        username: str | None = None,
        first_name: str | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_identities (
                    subject, auth_method, role, telegram_id, username, first_name,
                    totp_secret_cipher, totp_enabled, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, '', 0, ?, ?)
                ON CONFLICT(subject) DO UPDATE SET
                    auth_method = excluded.auth_method,
                    role = excluded.role,
                    telegram_id = excluded.telegram_id,
                    username = excluded.username,
                    first_name = excluded.first_name,
                    updated_at = excluded.updated_at
                """,
                (subject, auth_method, role, telegram_id, username, first_name, now, now),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT subject, auth_method, role, telegram_id, username, first_name,
                       totp_secret_cipher, totp_enabled, created_at, updated_at
                FROM admin_identities
                WHERE subject = ?
                """,
                (subject,),
            ).fetchone()
        return dict(row) if row else {}

    def get_identity(self, subject: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT subject, auth_method, role, telegram_id, username, first_name,
                       totp_secret_cipher, totp_enabled, created_at, updated_at
                FROM admin_identities
                WHERE subject = ?
                """,
                (subject,),
            ).fetchone()
        return dict(row) if row else None

    def set_identity_totp(self, subject: str, *, secret_cipher: str, enabled: bool) -> dict[str, Any]:
        now = utcnow()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE admin_identities
                SET totp_secret_cipher = ?, totp_enabled = ?, updated_at = ?
                WHERE subject = ?
                """,
                (secret_cipher, 1 if enabled else 0, now, subject),
            )
            conn.commit()
        identity = self.get_identity(subject)
        if not identity:
            raise KeyError(f"Admin identity {subject} not found")
        return identity

    def owner_totp_summary(self) -> dict[str, Any]:
        with self.connect() as conn:
            owner_counts = conn.execute(
                """
                SELECT
                    COUNT(*) AS owner_identity_count,
                    COALESCE(SUM(CASE WHEN totp_enabled = 1 THEN 1 ELSE 0 END), 0) AS enabled_owner_count
                FROM admin_identities
                WHERE role = 'owner'
                """
            ).fetchone()
            pending_challenges = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM admin_totp_challenges
                WHERE role = 'owner'
                """
            ).fetchone()
        owner_identity_count = int(owner_counts["owner_identity_count"] or 0) if owner_counts else 0
        enabled_owner_count = int(owner_counts["enabled_owner_count"] or 0) if owner_counts else 0
        return {
            "owner_identity_count": owner_identity_count,
            "enabled_owner_count": enabled_owner_count,
            "pending_challenge_count": int(pending_challenges["cnt"] or 0) if pending_challenges else 0,
            "totp_enabled": enabled_owner_count > 0,
        }

    def disable_totp_for_role(self, role: str) -> dict[str, Any]:
        now = utcnow()
        normalized_role = str(role or "").strip().lower()
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE admin_identities
                SET totp_secret_cipher = '', totp_enabled = 0, updated_at = ?
                WHERE role = ?
                """,
                (now, normalized_role),
            )
            cleared_identity_count = int(conn.execute("SELECT changes() AS cnt").fetchone()["cnt"] or 0)
            conn.execute(
                "DELETE FROM admin_totp_challenges WHERE role = ?",
                (normalized_role,),
            )
            cleared_challenge_count = int(conn.execute("SELECT changes() AS cnt").fetchone()["cnt"] or 0)
            conn.commit()
        result = {
            "role": normalized_role,
            "cleared_identity_count": cleared_identity_count,
            "cleared_challenge_count": cleared_challenge_count,
        }
        if normalized_role == "owner":
            result.update(self.owner_totp_summary())
        return result

    def create_totp_challenge(
        self,
        *,
        subject: str,
        auth_method: str,
        role: str,
        telegram_id: int | None = None,
        username: str | None = None,
        first_name: str | None = None,
        challenge_kind: str,
        ttl_seconds: int = 300,
    ) -> dict[str, Any]:
        token = issue_session_token()
        now_dt = datetime.utcnow().replace(microsecond=0)
        expires_at = now_dt + timedelta(seconds=ttl_seconds)
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO admin_totp_challenges (
                    token, subject, auth_method, role, telegram_id, username, first_name,
                    challenge_kind, temp_secret_cipher, created_at, expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, '', ?, ?)
                """,
                (
                    token,
                    subject,
                    auth_method,
                    role,
                    telegram_id,
                    username,
                    first_name,
                    challenge_kind,
                    now_dt.isoformat(),
                    expires_at.isoformat(),
                ),
            )
            conn.commit()
        return {
            "token": token,
            "subject": subject,
            "auth_method": auth_method,
            "role": role,
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "challenge_kind": challenge_kind,
            "created_at": now_dt.isoformat(),
            "expires_at": expires_at.isoformat(),
        }

    def get_totp_challenge(self, token: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT token, subject, auth_method, role, telegram_id, username, first_name,
                       challenge_kind, temp_secret_cipher, created_at, expires_at
                FROM admin_totp_challenges
                WHERE token = ?
                """,
                (token,),
            ).fetchone()
            if not row:
                return None
            payload = dict(row)
            if payload["expires_at"] <= utcnow():
                conn.execute("DELETE FROM admin_totp_challenges WHERE token = ?", (token,))
                conn.commit()
                return None
        return payload

    def update_totp_challenge_secret(self, token: str, secret_cipher: str) -> dict[str, Any]:
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE admin_totp_challenges
                SET temp_secret_cipher = ?
                WHERE token = ?
                """,
                (secret_cipher, token),
            )
            conn.commit()
        challenge = self.get_totp_challenge(token)
        if not challenge:
            raise KeyError(f"TOTP challenge {token} not found")
        return challenge

    def delete_totp_challenge(self, token: str) -> None:
        with self.connect() as conn:
            conn.execute("DELETE FROM admin_totp_challenges WHERE token = ?", (token,))
            conn.commit()

    def record_audit_event(
        self,
        *,
        actor_subject: str,
        actor_role: str,
        actor_auth_method: str,
        actor_telegram_id: int | None,
        actor_username: str | None,
        action: str,
        target_type: str,
        target_id: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        now = utcnow()
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO admin_action_audit (
                    actor_subject, actor_role, actor_auth_method, actor_telegram_id, actor_username,
                    action, target_type, target_id, details_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    actor_subject,
                    actor_role,
                    actor_auth_method,
                    actor_telegram_id,
                    actor_username,
                    action,
                    target_type,
                    target_id,
                    json.dumps(details or {}, ensure_ascii=False),
                    now,
                ),
            )
            conn.commit()
            event_id = int(cursor.lastrowid or 0)
        return {
            "id": event_id,
            "actor_subject": actor_subject,
            "actor_role": actor_role,
            "actor_auth_method": actor_auth_method,
            "actor_telegram_id": actor_telegram_id,
            "actor_username": actor_username,
            "action": action,
            "target_type": target_type,
            "target_id": target_id,
            "details": details or {},
            "created_at": now,
        }

    def list_audit_events(self, limit: int = 200) -> list[dict[str, Any]]:
        bounded_limit = max(1, min(int(limit or 200), 500))
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT id, actor_subject, actor_role, actor_auth_method, actor_telegram_id, actor_username,
                       action, target_type, target_id, details_json, created_at
                FROM admin_action_audit
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (bounded_limit,),
            ).fetchall()
        payload: list[dict[str, Any]] = []
        for row in rows:
            item = dict(row)
            item["details"] = json.loads(item.pop("details_json"))
            payload.append(item)
        return payload
