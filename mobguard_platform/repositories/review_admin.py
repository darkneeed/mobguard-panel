from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Callable, Mapping, Optional

from ..models import DecisionBundle, ReviewCaseSummary
from ..review_context import (
    build_review_scope,
    clean_text,
    coerce_optional_int,
    device_display_from_identity,
    normalize_review_identity_payload,
    provider_summary_from_signal_flags,
    subject_key_from_identity,
)
from ..usage_profile import (
    build_usage_profile_priority,
    build_usage_profile_snapshot,
    normalize_usage_observation,
    shared_account_suspected_from_usage_profile,
)
from .base import SQLiteRepository


REPEAT_COUNT_MIN_GAP = timedelta(minutes=5)


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _parse_day_boundary(value: Any, *, end_of_day: bool) -> str:
    parsed = datetime.strptime(str(value), "%Y-%m-%d")
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed.isoformat()


def _resolve_review_module_name(conn: sqlite3.Connection, payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    module_name = str(normalized.get("module_name") or "").strip()
    module_id = str(normalized.get("module_id") or "").strip()
    if module_name or not module_id:
        return normalized
    row = conn.execute(
        "SELECT module_name FROM modules WHERE module_id = ?",
        (module_id,),
    ).fetchone()
    if row and str(row["module_name"] or "").strip():
        normalized["module_name"] = str(row["module_name"]).strip()
    return normalized


def _review_identity(user: Optional[dict[str, Any]]) -> dict[str, Any]:
    normalized = normalize_review_identity_payload(user or {})
    return {
        "uuid": normalized.get("uuid"),
        "username": normalized.get("username"),
        "system_id": coerce_optional_int(
            normalized.get("system_id") if normalized.get("system_id") not in (None, "") else normalized.get("id")
        ),
        "telegram_id": (
            str(normalized.get("telegram_id") or normalized.get("telegramId"))
            if normalized.get("telegram_id") not in (None, "") or normalized.get("telegramId") not in (None, "")
            else None
        ),
    }


def _device_fields_from_row(row: Mapping[str, Any] | None) -> dict[str, Any]:
    payload = dict(row or {})
    exact_device_id = clean_text(payload.get("client_device_id"))
    device_display = device_display_from_identity(payload) if exact_device_id else ""
    return {
        "client_device_id": exact_device_id or None,
        "client_device_label": clean_text(payload.get("client_device_label")) or None,
        "client_os_family": clean_text(payload.get("client_os_family")) or None,
        "client_app_name": clean_text(payload.get("client_app_name")) or None,
        "device_display": device_display or None,
        "device_link_status": "exact" if exact_device_id else "none",
        "device_link_source": clean_text(payload.get("device_link_source")) or ("module_header" if exact_device_id else None),
    }


def _normalized_module_id(value: Any) -> str:
    return clean_text(value)


def _provider_summary_payload(bundle: DecisionBundle) -> dict[str, Any]:
    return provider_summary_from_signal_flags(bundle.signal_flags)


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _extract_hwid_devices(payload: Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    for key in ("hwidDevices", "hwid_devices", "devices"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    return []


def _hwid_device_id(device: Mapping[str, Any]) -> str:
    return clean_text(
        device.get("hwid")
        or device.get("deviceId")
        or device.get("device_id")
        or device.get("clientDeviceId")
        or device.get("client_device_id")
    )


def _hwid_limit(payload: Mapping[str, Any] | None) -> int | None:
    if not isinstance(payload, Mapping):
        return None
    for key in (
        "hwidDeviceLimit",
        "hwid_device_limit",
        "hwidLimit",
        "hwid_limit",
        "maxHwidDevices",
        "max_hwid_devices",
        "deviceLimit",
        "device_limit",
    ):
        parsed = _optional_int(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _hwid_count_exact(payload: Mapping[str, Any] | None) -> int | None:
    if not isinstance(payload, Mapping):
        return None
    devices = _extract_hwid_devices(payload)
    if devices:
        exact_ids = {_hwid_device_id(device).lower() for device in devices if _hwid_device_id(device)}
        return len(exact_ids) if exact_ids else len(devices)
    for key in ("hwidDeviceCount", "hwid_device_count", "hwidCount", "hwid_count", "deviceCount", "device_count"):
        parsed = _optional_int(payload.get(key))
        if parsed is not None:
            return parsed
    return None


def _hwid_context(payload: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "hwid_device_limit": _hwid_limit(payload),
        "hwid_device_count_exact": _hwid_count_exact(payload),
    }


def _derive_hard_flags(
    bundle: DecisionBundle,
    *,
    usage_snapshot: Mapping[str, Any] | None = None,
    hwid_context: Mapping[str, Any] | None = None,
) -> list[str]:
    flags: list[str] = []
    for flag in bundle.hard_flags:
        normalized = clean_text(flag)
        if normalized and normalized not in flags:
            flags.append(normalized)

    limit = _optional_int((hwid_context or {}).get("hwid_device_limit"))
    count = _optional_int((hwid_context or {}).get("hwid_device_count_exact"))
    if limit is not None and limit >= 0 and count is not None and count > limit:
        flags.append("sharing_hwid_limit_exceeded")

    burst = usage_snapshot.get("traffic_burst") if isinstance(usage_snapshot, Mapping) else None
    if isinstance(burst, Mapping) and burst.get("source") == "traffic_bytes":
        flags.append("traffic_burst_confirmed")

    return list(dict.fromkeys(flags))


class _ConnectionContext:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self) -> sqlite3.Connection:
        return self.conn

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


class _ConnectionBackedStore:
    def __init__(self, repository: "ReviewAdminRepository", conn: sqlite3.Connection):
        self.repository = repository
        self.conn = conn

    def _connect(self) -> _ConnectionContext:
        return _ConnectionContext(self.conn)

    def _table_exists(self, conn: sqlite3.Connection, table_name: str) -> bool:
        return self.repository.table_exists(conn, table_name)


class ReviewAdminRepository(SQLiteRepository):
    def __init__(
        self,
        storage,
        *,
        base_config: dict[str, Any],
        live_rules_loader: Callable[[], dict[str, Any]],
        read_model_writer: Optional[Callable[[sqlite3.Connection, str, str, dict[str, Any], Optional[str]], None]] = None,
        read_model_loader: Optional[Callable[[sqlite3.Connection, str, str], Optional[dict[str, Any]]]] = None,
    ):
        super().__init__(storage)
        self.base_config = base_config
        self.live_rules_loader = live_rules_loader
        self.read_model_writer = read_model_writer
        self.read_model_loader = read_model_loader

    def _analysis_event_scope_context(
        self,
        conn: sqlite3.Connection,
        event_id: int,
        *,
        fallback_ip: str,
        fallback_tag: str,
        fallback_module_id: str | None,
        fallback_module_name: str | None,
    ) -> dict[str, Any]:
        row = conn.execute(
            """
            SELECT created_at, ip, tag, module_id, module_name, uuid, username, system_id, telegram_id,
                   client_device_id, client_device_label, client_os_family, client_app_name,
                   device_link_status, device_link_source
            FROM analysis_events
            WHERE id = ?
            """,
            (event_id,),
        ).fetchone()
        payload = dict(row) if row else {}
        payload["ip"] = clean_text(payload.get("ip")) or clean_text(fallback_ip)
        payload["tag"] = clean_text(payload.get("tag")) or clean_text(fallback_tag)
        payload["module_id"] = clean_text(payload.get("module_id")) or clean_text(fallback_module_id)
        payload["module_name"] = clean_text(payload.get("module_name")) or clean_text(fallback_module_name)
        scope = build_review_scope(payload, payload, ip=payload["ip"])
        return {
            "created_at": clean_text(payload.get("created_at")) or _utcnow(),
            "ip": payload["ip"],
            "tag": payload["tag"],
            "module_id": payload["module_id"] or None,
            "module_name": payload["module_name"] or None,
            **scope,
            **_device_fields_from_row(payload),
        }

    def _history_scope_filter(self, scope_key: str) -> tuple[str, tuple[Any, ...]]:
        normalized_scope = clean_text(scope_key)
        if normalized_scope.startswith("subject:"):
            return "subject_key = ?", (normalized_scope[len("subject:") :],)
        return "device_scope_key = ?", (normalized_scope,)

    def _same_device_ip_history(
        self,
        conn: sqlite3.Connection,
        *,
        device_scope_key: str,
        limit: int = 8,
    ) -> list[dict[str, Any]]:
        normalized_scope = clean_text(device_scope_key)
        if not normalized_scope:
            return []
        scope_clause, scope_params = self._history_scope_filter(normalized_scope)
        rows = conn.execute(
            f"""
            SELECT ip,
                   COUNT(*) AS hit_count,
                   MIN(created_at) AS first_seen_at,
                   MAX(created_at) AS last_seen_at
            FROM analysis_events
            WHERE {scope_clause}
            GROUP BY ip
            ORDER BY MAX(created_at) DESC, ip ASC
            LIMIT ?
            """,
            (*scope_params, max(int(limit), 1)),
        ).fetchall()
        history: list[dict[str, Any]] = []
        for row in rows:
            latest = conn.execute(
                f"""
                SELECT isp, asn, country, region, city, module_id, module_name, tag
                FROM analysis_events
                WHERE {scope_clause} AND ip = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (*scope_params, str(row["ip"])),
            ).fetchone()
            payload = dict(row)
            latest_payload = dict(latest) if latest else {}
            payload["isp"] = clean_text(latest_payload.get("isp")) or None
            payload["asn"] = latest_payload.get("asn")
            payload["country"] = clean_text(latest_payload.get("country")) or None
            payload["region"] = clean_text(latest_payload.get("region")) or None
            payload["city"] = clean_text(latest_payload.get("city")) or None
            payload["module_id"] = clean_text(latest_payload.get("module_id")) or None
            payload["module_name"] = clean_text(latest_payload.get("module_name")) or None
            payload["inbound_tag"] = clean_text(latest_payload.get("tag")) or None
            history.append(payload)
        return history

    def _batch_same_device_ip_history(
        self,
        conn: sqlite3.Connection,
        *,
        device_scope_keys: list[str],
        limit: int = 8,
    ) -> dict[str, list[dict[str, Any]]]:
        normalized_scope_keys: list[str] = []
        seen_scope_keys: set[str] = set()
        for value in device_scope_keys:
            normalized = clean_text(value)
            if not normalized or normalized in seen_scope_keys:
                continue
            seen_scope_keys.add(normalized)
            normalized_scope_keys.append(normalized)
        if not normalized_scope_keys:
            return {}

        history: dict[str, list[dict[str, Any]]] = {scope_key: [] for scope_key in normalized_scope_keys}
        direct_scope_keys = [scope_key for scope_key in normalized_scope_keys if not scope_key.startswith("subject:")]
        subject_scope_keys = [scope_key for scope_key in normalized_scope_keys if scope_key.startswith("subject:")]

        if direct_scope_keys:
            placeholders = ", ".join("?" for _ in direct_scope_keys)
            rows = conn.execute(
                f"""
                WITH per_ip AS (
                    SELECT device_scope_key,
                           ip,
                           COUNT(*) AS hit_count,
                           MIN(created_at) AS first_seen_at,
                           MAX(created_at) AS last_seen_at
                    FROM analysis_events
                    WHERE device_scope_key IN ({placeholders})
                    GROUP BY device_scope_key, ip
                ),
                latest AS (
                    SELECT ae.device_scope_key,
                           ae.ip,
                           ae.isp,
                           ae.asn,
                           ae.country,
                           ae.region,
                           ae.city,
                           ae.module_id,
                           ae.module_name,
                           ae.tag,
                           ROW_NUMBER() OVER (
                               PARTITION BY ae.device_scope_key, ae.ip
                               ORDER BY ae.created_at DESC, ae.id DESC
                           ) AS row_rank
                    FROM analysis_events ae
                    WHERE ae.device_scope_key IN ({placeholders})
                ),
                ranked AS (
                    SELECT per_ip.device_scope_key,
                           per_ip.ip,
                           per_ip.hit_count,
                           per_ip.first_seen_at,
                           per_ip.last_seen_at,
                           latest.isp,
                           latest.asn,
                           latest.country,
                           latest.region,
                           latest.city,
                           latest.module_id,
                           latest.module_name,
                           latest.tag,
                           ROW_NUMBER() OVER (
                               PARTITION BY per_ip.device_scope_key
                               ORDER BY per_ip.last_seen_at DESC, per_ip.ip ASC
                           ) AS scope_rank
                    FROM per_ip
                    LEFT JOIN latest
                        ON latest.device_scope_key = per_ip.device_scope_key
                       AND latest.ip = per_ip.ip
                       AND latest.row_rank = 1
                )
                SELECT device_scope_key,
                       ip,
                       hit_count,
                       first_seen_at,
                       last_seen_at,
                       isp,
                       asn,
                       country,
                       region,
                       city,
                       module_id,
                       module_name,
                       tag
                FROM ranked
                WHERE scope_rank <= ?
                ORDER BY device_scope_key ASC, last_seen_at DESC, ip ASC
                """,
                (*direct_scope_keys, *direct_scope_keys, max(int(limit), 1)),
            ).fetchall()

            for row in rows:
                payload = dict(row)
                scope_key = clean_text(payload.pop("device_scope_key"))
                payload["isp"] = clean_text(payload.get("isp")) or None
                payload["country"] = clean_text(payload.get("country")) or None
                payload["region"] = clean_text(payload.get("region")) or None
                payload["city"] = clean_text(payload.get("city")) or None
                payload["module_id"] = clean_text(payload.get("module_id")) or None
                payload["module_name"] = clean_text(payload.get("module_name")) or None
                payload["inbound_tag"] = clean_text(payload.pop("tag")) or None
                history.setdefault(scope_key, []).append(payload)

        for scope_key in subject_scope_keys:
            history[scope_key] = self._same_device_ip_history(conn, device_scope_key=scope_key, limit=limit)

        return history

    def _record_analysis_event(
        self,
        conn: sqlite3.Connection,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        *,
        observation: Optional[dict[str, Any]] = None,
        source_event_uid: str | None = None,
    ) -> int:
        now = _utcnow()
        module_id = str((user or {}).get("module_id") or "").strip() or None
        module_name = str((user or {}).get("module_name") or "").strip() or module_id
        subject_key = subject_key_from_identity(user, ip=ip)
        usage_observation = normalize_usage_observation(
            observation,
            signal_flags=bundle.signal_flags,
        )
        device_link_status = "exact" if clean_text(usage_observation.get("client_device_id")) else "none"
        device_link_source = (
            clean_text((observation or {}).get("device_link_source"))
            or ("module_header" if device_link_status == "exact" else "")
        )
        hwid_context = _hwid_context(user)
        event_hard_flags = _derive_hard_flags(bundle, hwid_context=hwid_context)
        bundle.hard_flags = event_hard_flags
        bundle.signal_flags["hard_flags"] = list(event_hard_flags)
        scope = build_review_scope(user, {**usage_observation, "ip": ip}, ip=ip)
        payload = bundle.to_dict()
        cursor = conn.execute(
            """
            INSERT INTO analysis_events (
                created_at, module_id, module_name, source_event_uid, decision_source, subject_key, uuid, username, system_id, telegram_id, ip, tag,
                verdict, confidence_band, score, isp, asn,
                asn_source, provider_source, hard_flags_json,
                country, region, city, loc, latitude, longitude,
                client_device_id, client_device_label, client_os_family, client_os_version,
                client_app_name, client_app_version,
                device_link_status, device_link_source, hwid_device_limit, hwid_device_count_exact,
                case_scope_key, device_scope_key, scope_type,
                punitive_eligible,
                reasons_json, signal_flags_json, bundle_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                now,
                module_id,
                module_name,
                clean_text(source_event_uid) or None,
                str(bundle.source or "rule_engine"),
                subject_key,
                (user or {}).get("uuid"),
                (user or {}).get("username"),
                coerce_optional_int((user or {}).get("id")),
                str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                ip,
                tag,
                bundle.verdict,
                bundle.confidence_band,
                bundle.score,
                bundle.isp,
                bundle.asn,
                bundle.asn_source,
                bundle.provider_source,
                json.dumps(event_hard_flags, ensure_ascii=False),
                usage_observation.get("country"),
                usage_observation.get("region"),
                usage_observation.get("city"),
                usage_observation.get("loc"),
                usage_observation.get("latitude"),
                usage_observation.get("longitude"),
                usage_observation.get("client_device_id"),
                usage_observation.get("client_device_label"),
                usage_observation.get("client_os_family"),
                usage_observation.get("client_os_version"),
                usage_observation.get("client_app_name"),
                usage_observation.get("client_app_version"),
                device_link_status,
                device_link_source or None,
                hwid_context["hwid_device_limit"],
                hwid_context["hwid_device_count_exact"],
                scope["case_scope_key"],
                scope["device_scope_key"],
                scope["scope_type"],
                int(bundle.punitive_eligible),
                json.dumps([reason.to_dict() for reason in bundle.reasons], ensure_ascii=False),
                json.dumps(bundle.signal_flags, ensure_ascii=False),
                json.dumps(payload, ensure_ascii=False),
            ),
        )
        return int(cursor.lastrowid)

    def record_analysis_event(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        *,
        observation: Optional[dict[str, Any]] = None,
        source_event_uid: str | None = None,
    ) -> int:
        with self.connect() as conn:
            event_id = self._record_analysis_event(
                conn,
                user,
                ip,
                tag,
                bundle,
                observation=observation,
                source_event_uid=source_event_uid,
            )
            conn.commit()
            return event_id

    def build_review_url(self, case_id: int) -> str:
        try:
            rules_state = self.live_rules_loader(skip_db_mirror=True)
        except TypeError:
            rules_state = self.live_rules_loader()
        base_url = str(rules_state.get("rules", {}).get("settings", {}).get("review_ui_base_url", "")).rstrip("/")
        if not base_url:
            base_url = str(self.base_config.get("settings", {}).get("review_ui_base_url", "")).rstrip("/")
        if not base_url:
            return ""
        return f"{base_url}/reviews/{case_id}"

    def _upsert_review_case_ip(
        self,
        conn: sqlite3.Connection,
        *,
        case_id: int,
        ip: str,
        isp: str | None,
        asn: int | None,
        seen_at: str,
        hit_increment: int = 1,
        first_seen_at: str | None = None,
    ) -> None:
        normalized_ip = clean_text(ip)
        if not normalized_ip:
            return
        initial_seen_at = clean_text(first_seen_at) or seen_at
        conn.execute(
            """
            INSERT INTO review_case_ips (
                case_id, ip, hit_count, first_seen_at, last_seen_at, isp, asn
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(case_id, ip) DO UPDATE SET
                hit_count = review_case_ips.hit_count + excluded.hit_count,
                first_seen_at = CASE
                    WHEN review_case_ips.first_seen_at <= excluded.first_seen_at
                    THEN review_case_ips.first_seen_at
                    ELSE excluded.first_seen_at
                END,
                last_seen_at = CASE
                    WHEN review_case_ips.last_seen_at >= excluded.last_seen_at
                    THEN review_case_ips.last_seen_at
                    ELSE excluded.last_seen_at
                END,
                isp = CASE
                    WHEN excluded.last_seen_at >= review_case_ips.last_seen_at AND excluded.isp IS NOT NULL AND excluded.isp != ''
                    THEN excluded.isp
                    ELSE review_case_ips.isp
                END,
                asn = CASE
                    WHEN excluded.last_seen_at >= review_case_ips.last_seen_at AND excluded.asn IS NOT NULL
                    THEN excluded.asn
                    ELSE review_case_ips.asn
                END
            """,
            (
                case_id,
                normalized_ip,
                max(int(hit_increment or 1), 1),
                initial_seen_at,
                seen_at,
                clean_text(isp) or None,
                asn,
            ),
        )

    def _upsert_review_case_module(
        self,
        conn: sqlite3.Connection,
        *,
        case_id: int,
        module_id: str | None,
        module_name: str | None,
        seen_at: str,
        first_seen_at: str | None = None,
    ) -> None:
        normalized_module_id = _normalized_module_id(module_id)
        initial_seen_at = clean_text(first_seen_at) or seen_at
        conn.execute(
            """
            INSERT INTO review_case_modules (
                case_id, module_id, module_name, first_seen_at, last_seen_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(case_id, module_id) DO UPDATE SET
                module_name = CASE
                    WHEN excluded.last_seen_at >= review_case_modules.last_seen_at AND excluded.module_name IS NOT NULL AND excluded.module_name != ''
                    THEN excluded.module_name
                    ELSE review_case_modules.module_name
                END,
                first_seen_at = CASE
                    WHEN review_case_modules.first_seen_at <= excluded.first_seen_at
                    THEN review_case_modules.first_seen_at
                    ELSE excluded.first_seen_at
                END,
                last_seen_at = CASE
                    WHEN review_case_modules.last_seen_at >= excluded.last_seen_at
                    THEN review_case_modules.last_seen_at
                    ELSE excluded.last_seen_at
                END
            """,
            (
                case_id,
                normalized_module_id,
                clean_text(module_name) or None,
                initial_seen_at,
                seen_at,
            ),
        )

    def _attach_case_context(
        self,
        conn: sqlite3.Connection,
        *,
        case_id: int,
        ip: str,
        isp: str | None,
        asn: int | None,
        module_id: str | None,
        module_name: str | None,
        seen_at: str,
        hit_increment: int = 1,
        first_seen_at: str | None = None,
    ) -> None:
        self._upsert_review_case_ip(
            conn,
            case_id=case_id,
            ip=ip,
            isp=isp,
            asn=asn,
            seen_at=seen_at,
            hit_increment=hit_increment,
            first_seen_at=first_seen_at,
        )
        self._upsert_review_case_module(
            conn,
            case_id=case_id,
            module_id=module_id,
            module_name=module_name,
            seen_at=seen_at,
            first_seen_at=first_seen_at,
        )

    def _case_ip_inventory(
        self,
        conn: sqlite3.Connection,
        case_ids: list[int],
        *,
        per_case_limit: int | None = None,
    ) -> dict[int, list[dict[str, Any]]]:
        if not case_ids:
            return {}
        placeholders = ", ".join("?" for _ in case_ids)
        if per_case_limit is not None:
            rows = conn.execute(
                f"""
                WITH ranked AS (
                    SELECT case_id,
                           ip,
                           hit_count,
                           first_seen_at,
                           last_seen_at,
                           isp,
                           asn,
                           ROW_NUMBER() OVER (
                               PARTITION BY case_id
                               ORDER BY last_seen_at DESC, ip ASC
                           ) AS row_rank
                    FROM review_case_ips
                    WHERE case_id IN ({placeholders})
                )
                SELECT case_id, ip, hit_count, first_seen_at, last_seen_at, isp, asn
                FROM ranked
                WHERE row_rank <= ?
                ORDER BY case_id ASC, last_seen_at DESC, ip ASC
                """,
                (*case_ids, max(int(per_case_limit), 1)),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""
                SELECT case_id, ip, hit_count, first_seen_at, last_seen_at, isp, asn
                FROM review_case_ips
                WHERE case_id IN ({placeholders})
                ORDER BY last_seen_at DESC, ip ASC
                """,
                tuple(case_ids),
            ).fetchall()
        inventory: dict[int, list[dict[str, Any]]] = {case_id: [] for case_id in case_ids}
        for row in rows:
            inventory.setdefault(int(row["case_id"]), []).append(dict(row))
        return inventory

    def _case_module_inventory(
        self,
        conn: sqlite3.Connection,
        case_ids: list[int],
    ) -> dict[int, list[dict[str, Any]]]:
        if not case_ids:
            return {}
        placeholders = ", ".join("?" for _ in case_ids)
        rows = conn.execute(
            f"""
            SELECT case_id, module_id, module_name, first_seen_at, last_seen_at
            FROM review_case_modules
            WHERE case_id IN ({placeholders})
            ORDER BY last_seen_at DESC, module_name ASC, module_id ASC
            """,
            tuple(case_ids),
        ).fetchall()
        inventory: dict[int, list[dict[str, Any]]] = {case_id: [] for case_id in case_ids}
        for row in rows:
            payload = dict(row)
            payload["module_id"] = payload.get("module_id") or None
            inventory.setdefault(int(row["case_id"]), []).append(payload)
        return inventory

    def _apply_inventory_payloads(
        self,
        item: dict[str, Any],
        *,
        ip_inventory: list[dict[str, Any]] | None = None,
        module_inventory: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        ip_payload = list(ip_inventory or [])
        if not ip_payload and clean_text(item.get("ip")):
            ip_payload = [
                {
                    "ip": clean_text(item.get("ip")),
                    "hit_count": max(int(item.get("repeat_count") or 1), 1),
                    "first_seen_at": clean_text(item.get("opened_at") or item.get("updated_at")),
                    "last_seen_at": clean_text(item.get("updated_at") or item.get("opened_at")),
                    "isp": clean_text(item.get("isp")) or None,
                    "asn": item.get("asn"),
                }
            ]
        module_payload = list(module_inventory or [])
        if not module_payload and (clean_text(item.get("module_id")) or clean_text(item.get("module_name"))):
            module_payload = [
                {
                    "module_id": clean_text(item.get("module_id")) or None,
                    "module_name": clean_text(item.get("module_name")) or None,
                    "first_seen_at": clean_text(item.get("opened_at") or item.get("updated_at")),
                    "last_seen_at": clean_text(item.get("updated_at") or item.get("opened_at")),
                }
            ]
        item["ip_inventory"] = ip_payload
        item["distinct_ip_count"] = len(ip_payload)
        item["module_inventory"] = module_payload
        item["module_count"] = len(module_payload)
        return item

    def _apply_compact_queue_payload(
        self,
        item: dict[str, Any],
        *,
        ip_inventory: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        payload = self._apply_inventory_payloads(item, ip_inventory=ip_inventory, module_inventory=None)
        payload["module_inventory"] = []
        payload["module_count"] = 0
        payload["same_device_ip_history"] = []
        payload["shared_account_suspected"] = False
        return payload

    def _usage_profile_fields(
        self,
        user: Optional[dict[str, Any]],
        *,
        bundle: DecisionBundle,
        repeat_count: int,
        anchor_started_at: str,
        device_scope_key: str,
        case_scope_key: str,
        conn: sqlite3.Connection | None = None,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        snapshot_store: Any = _ConnectionBackedStore(self, conn) if conn is not None else self
        snapshot = build_usage_profile_snapshot(
            snapshot_store,
            _review_identity(user),
            panel_user=user,
            anchor_started_at=anchor_started_at,
            device_scope_key=device_scope_key,
            case_scope_key=case_scope_key,
        )
        priority = build_usage_profile_priority(
            snapshot,
            punitive_eligible=bool(bundle.punitive_eligible),
            confidence_band=str(bundle.confidence_band or ""),
            repeat_count=repeat_count,
        )
        fields = {
            "usage_profile_summary": str(snapshot.get("usage_profile_summary") or ""),
            "usage_profile_signal_count": int(priority["signal_count"]),
            "usage_profile_priority": int(priority["priority"]),
            "usage_profile_soft_reasons_json": json.dumps(snapshot.get("soft_reasons", []), ensure_ascii=False),
            "usage_profile_ongoing_duration_seconds": snapshot.get("ongoing_duration_seconds"),
            "usage_profile_ongoing_duration_text": str(snapshot.get("ongoing_duration_text") or ""),
        }
        return fields, snapshot

    def _persist_usage_profile_snapshot(
        self,
        conn: sqlite3.Connection,
        *,
        case_id: int,
        snapshot: dict[str, Any],
        updated_at: str,
    ) -> None:
        if not self.read_model_writer:
            return
        payload = dict(snapshot)
        payload["case_id"] = int(case_id)
        payload["updated_at"] = str(payload.get("updated_at") or updated_at)
        self.read_model_writer(
            conn,
            "review_usage_profile",
            str(case_id),
            payload,
            updated_at,
        )

    def _shared_account_flags_for_items(
        self,
        conn: sqlite3.Connection,
        items: list[dict[str, Any]],
    ) -> None:
        if not items:
            return
        snapshot_store: Any = _ConnectionBackedStore(self, conn)
        shared_flags_by_scope: dict[str, bool] = {}
        for item in items:
            item["shared_account_suspected"] = "sharing_hwid_limit_exceeded" in set(item.get("hard_flags") or [])
            if item["shared_account_suspected"]:
                continue
            scope_type = clean_text(item.get("scope_type") or item.get("target_scope_type")) or "ip_only"
            if scope_type != "subject_ip":
                continue
            device_scope_key = clean_text(item.get("device_scope_key"))
            if not device_scope_key:
                continue
            if device_scope_key not in shared_flags_by_scope:
                snapshot = build_usage_profile_snapshot(
                    snapshot_store,
                    _review_identity(item),
                    device_scope_key=device_scope_key,
                    case_scope_key=clean_text(item.get("case_scope_key")),
                )
                shared_flags_by_scope[device_scope_key] = shared_account_suspected_from_usage_profile(snapshot)
            item["shared_account_suspected"] = bool(shared_flags_by_scope[device_scope_key])

    def _usage_profile_snapshot_is_stale(
        self,
        conn: sqlite3.Connection,
        case_payload: Mapping[str, Any],
        snapshot: Mapping[str, Any] | None,
    ) -> bool:
        profile = snapshot if isinstance(snapshot, Mapping) else {}
        snapshot_updated_at = clean_text(profile.get("_snapshot_updated_at") or profile.get("updated_at"))
        if not snapshot_updated_at:
            return True
        case_updated_at = clean_text(case_payload.get("updated_at"))
        if case_updated_at and case_updated_at > snapshot_updated_at:
            return True

        scope_type = clean_text(case_payload.get("target_scope_type") or case_payload.get("scope_type")) or "ip_only"
        device_scope_key = clean_text(case_payload.get("device_scope_key"))
        case_scope_key = clean_text(case_payload.get("case_scope_key"))
        if scope_type == "subject_ip" and device_scope_key.startswith("subject:"):
            row = conn.execute(
                "SELECT MAX(id) AS last_event_id, MAX(created_at) AS last_created_at FROM analysis_events WHERE subject_key = ?",
                (device_scope_key[len("subject:") :],),
            ).fetchone()
        elif device_scope_key:
            row = conn.execute(
                "SELECT MAX(id) AS last_event_id, MAX(created_at) AS last_created_at FROM analysis_events WHERE device_scope_key = ?",
                (device_scope_key,),
            ).fetchone()
        elif case_scope_key:
            row = conn.execute(
                "SELECT MAX(id) AS last_event_id, MAX(created_at) AS last_created_at FROM analysis_events WHERE case_scope_key = ?",
                (case_scope_key,),
            ).fetchone()
        else:
            return False
        latest_event_id = int(case_payload.get("latest_event_id") or 0)
        if row and int(row["last_event_id"] or 0) > latest_event_id:
            return True
        return clean_text(row["last_created_at"] if row else "") > snapshot_updated_at

    def _ensure_review_case(
        self,
        conn: sqlite3.Connection,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        event_id: int,
        review_reason: str,
    ) -> ReviewCaseSummary:
        fallback_module_id = str((user or {}).get("module_id") or "").strip()
        fallback_module_name = str((user or {}).get("module_name") or "").strip() or fallback_module_id
        reason_codes = json.dumps(bundle.reason_codes, ensure_ascii=False)
        provider_summary = _provider_summary_payload(bundle)
        event_context = self._analysis_event_scope_context(
            conn,
            event_id,
            fallback_ip=ip,
            fallback_tag=tag,
            fallback_module_id=fallback_module_id,
            fallback_module_name=fallback_module_name,
        )
        subject_key = subject_key_from_identity(user, ip=event_context["ip"])
        unique_key = f"{event_context['case_scope_key']}:{event_id}"
        event_created_at = clean_text(event_context["created_at"]) or _utcnow()
        existing = conn.execute(
            """
            SELECT id, repeat_count, opened_at, last_repeat_at
            FROM review_cases
            WHERE case_scope_key = ? AND status != 'MERGED'
            ORDER BY updated_at DESC, id DESC
            LIMIT 1
            """,
            (event_context["case_scope_key"],),
        ).fetchone()
        if existing:
            current_repeat_count = max(int(existing["repeat_count"] or 1), 1)
            repeat_anchor = clean_text(existing["last_repeat_at"] or existing["opened_at"])
            repeat_anchor_dt = datetime.fromisoformat(repeat_anchor) if repeat_anchor else None
            event_created_dt = datetime.fromisoformat(event_created_at) if event_created_at else None
            increment_repeat = True
            if repeat_anchor_dt is not None and event_created_dt is not None:
                increment_repeat = event_created_dt - repeat_anchor_dt >= REPEAT_COUNT_MIN_GAP
            next_repeat_count = current_repeat_count + (1 if increment_repeat else 0)
            last_repeat_at = event_created_at if increment_repeat else repeat_anchor
            usage_fields, usage_snapshot = self._usage_profile_fields(
                user,
                bundle=bundle,
                repeat_count=next_repeat_count,
                anchor_started_at=str(existing["opened_at"] or event_created_at),
                device_scope_key=event_context["device_scope_key"],
                case_scope_key=event_context["case_scope_key"],
                conn=conn,
            )
            hwid_context = _hwid_context(user)
            hard_flags = _derive_hard_flags(bundle, usage_snapshot=usage_snapshot, hwid_context=hwid_context)
            conn.execute(
                """
                UPDATE review_cases
                SET status = 'OPEN',
                    review_reason = ?,
                    case_scope_key = ?,
                    device_scope_key = ?,
                    scope_type = ?,
                    subject_key = ?,
                    module_id = ?,
                    module_name = ?,
                    client_device_id = ?,
                    client_device_label = ?,
                    client_os_family = ?,
                    client_app_name = ?,
                    device_link_status = ?,
                    device_link_source = ?,
                    hwid_device_limit = ?,
                    hwid_device_count_exact = ?,
                    uuid = ?,
                    username = ?,
                    system_id = ?,
                    telegram_id = ?,
                    ip = ?,
                    tag = ?,
                    verdict = ?,
                    confidence_band = ?,
                    score = ?,
                    isp = ?,
                    asn = ?,
                    asn_source = ?,
                    provider_source = ?,
                    hard_flags_json = ?,
                    provider_key = ?,
                    provider_classification = ?,
                    provider_service_hint = ?,
                    provider_conflict = ?,
                    provider_review_recommended = ?,
                    punitive_eligible = ?,
                    latest_event_id = ?,
                    repeat_count = ?,
                    last_repeat_at = ?,
                    reason_codes_json = ?,
                    usage_profile_summary = ?,
                    usage_profile_signal_count = ?,
                    usage_profile_priority = ?,
                    usage_profile_soft_reasons_json = ?,
                    usage_profile_ongoing_duration_seconds = ?,
                    usage_profile_ongoing_duration_text = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    review_reason,
                    event_context["case_scope_key"],
                    event_context["device_scope_key"],
                    event_context["scope_type"],
                    subject_key,
                    event_context["module_id"],
                    event_context["module_name"],
                    event_context["client_device_id"],
                    event_context["client_device_label"],
                    event_context["client_os_family"],
                    event_context["client_app_name"],
                    event_context["device_link_status"],
                    event_context["device_link_source"],
                    hwid_context["hwid_device_limit"],
                    hwid_context["hwid_device_count_exact"],
                    (user or {}).get("uuid"),
                    (user or {}).get("username"),
                    coerce_optional_int((user or {}).get("id")),
                    str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                    event_context["ip"],
                    event_context["tag"],
                    bundle.verdict,
                    bundle.confidence_band,
                    bundle.score,
                    bundle.isp,
                    bundle.asn,
                    bundle.asn_source,
                    bundle.provider_source,
                    json.dumps(hard_flags, ensure_ascii=False),
                    provider_summary["provider_key"],
                    provider_summary["provider_classification"],
                    provider_summary["provider_service_hint"],
                    int(provider_summary["provider_conflict"]),
                    int(provider_summary["provider_review_recommended"]),
                    int(bundle.punitive_eligible),
                    event_id,
                    next_repeat_count,
                    last_repeat_at,
                    reason_codes,
                    usage_fields["usage_profile_summary"],
                    usage_fields["usage_profile_signal_count"],
                    usage_fields["usage_profile_priority"],
                    usage_fields["usage_profile_soft_reasons_json"],
                    usage_fields["usage_profile_ongoing_duration_seconds"],
                    usage_fields["usage_profile_ongoing_duration_text"],
                    event_created_at,
                    existing["id"],
                ),
            )
            case_id = int(existing["id"])
            opened_at = str(existing["opened_at"] or event_created_at)
            repeat_count = next_repeat_count
            updated_at = event_created_at
            self._attach_case_context(
                conn,
                case_id=case_id,
                ip=event_context["ip"],
                isp=bundle.isp,
                asn=bundle.asn,
                module_id=event_context["module_id"],
                module_name=event_context["module_name"],
                seen_at=event_created_at,
                hit_increment=1,
                first_seen_at=opened_at,
            )
        else:
            usage_fields, usage_snapshot = self._usage_profile_fields(
                user,
                bundle=bundle,
                repeat_count=1,
                anchor_started_at=event_created_at,
                device_scope_key=event_context["device_scope_key"],
                case_scope_key=event_context["case_scope_key"],
                conn=conn,
            )
            hwid_context = _hwid_context(user)
            hard_flags = _derive_hard_flags(bundle, usage_snapshot=usage_snapshot, hwid_context=hwid_context)
            cursor = conn.execute(
                """
                INSERT INTO review_cases (
                    unique_key, status, review_reason, case_scope_key, device_scope_key, scope_type, subject_key,
                    module_id, module_name, client_device_id, client_device_label, client_os_family, client_app_name,
                    device_link_status, device_link_source, hwid_device_limit, hwid_device_count_exact,
                    uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn, asn_source, provider_source, hard_flags_json,
                    provider_key, provider_classification, provider_service_hint,
                    provider_conflict, provider_review_recommended, punitive_eligible, latest_event_id, repeat_count,
                    last_repeat_at,
                    reason_codes_json, usage_profile_summary, usage_profile_signal_count, usage_profile_priority,
                    usage_profile_soft_reasons_json, usage_profile_ongoing_duration_seconds, usage_profile_ongoing_duration_text,
                    opened_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    unique_key,
                    "OPEN",
                    review_reason,
                    event_context["case_scope_key"],
                    event_context["device_scope_key"],
                    event_context["scope_type"],
                    subject_key,
                    event_context["module_id"],
                    event_context["module_name"],
                    event_context["client_device_id"],
                    event_context["client_device_label"],
                    event_context["client_os_family"],
                    event_context["client_app_name"],
                    event_context["device_link_status"],
                    event_context["device_link_source"],
                    hwid_context["hwid_device_limit"],
                    hwid_context["hwid_device_count_exact"],
                    (user or {}).get("uuid"),
                    (user or {}).get("username"),
                    coerce_optional_int((user or {}).get("id")),
                    str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                    event_context["ip"],
                    event_context["tag"],
                    bundle.verdict,
                    bundle.confidence_band,
                    bundle.score,
                    bundle.isp,
                    bundle.asn,
                    bundle.asn_source,
                    bundle.provider_source,
                    json.dumps(hard_flags, ensure_ascii=False),
                    provider_summary["provider_key"],
                    provider_summary["provider_classification"],
                    provider_summary["provider_service_hint"],
                    int(provider_summary["provider_conflict"]),
                    int(provider_summary["provider_review_recommended"]),
                    int(bundle.punitive_eligible),
                    event_id,
                    1,
                    event_created_at,
                    reason_codes,
                    usage_fields["usage_profile_summary"],
                    usage_fields["usage_profile_signal_count"],
                    usage_fields["usage_profile_priority"],
                    usage_fields["usage_profile_soft_reasons_json"],
                    usage_fields["usage_profile_ongoing_duration_seconds"],
                    usage_fields["usage_profile_ongoing_duration_text"],
                    event_created_at,
                    event_created_at,
                ),
            )
            case_id = int(cursor.lastrowid)
            opened_at = event_created_at
            repeat_count = 1
            updated_at = event_created_at
            self._attach_case_context(
                conn,
                case_id=case_id,
                ip=event_context["ip"],
                isp=bundle.isp,
                asn=bundle.asn,
                module_id=event_context["module_id"],
                module_name=event_context["module_name"],
                seen_at=event_created_at,
                hit_increment=1,
                first_seen_at=event_created_at,
            )
        self._persist_usage_profile_snapshot(
            conn,
            case_id=case_id,
            snapshot=usage_snapshot,
            updated_at=updated_at,
        )
        return ReviewCaseSummary(
            id=case_id,
            status="OPEN",
            review_reason=review_reason,
            module_id=event_context.get("module_id") or "",
            module_name=event_context.get("module_name") or "",
            uuid=(user or {}).get("uuid") or "",
            username=(user or {}).get("username") or "",
            system_id=coerce_optional_int((user or {}).get("id")),
            telegram_id=str((user or {}).get("telegramId")) if (user or {}).get("telegramId") not in (None, "") else None,
            ip=event_context["ip"],
            tag=event_context.get("tag") or "",
            verdict=bundle.verdict,
            confidence_band=bundle.confidence_band,
            score=bundle.score,
            isp=bundle.isp or "",
            asn=bundle.asn,
            repeat_count=repeat_count,
            reason_codes=list(bundle.reason_codes),
            updated_at=updated_at,
            review_url=self.build_review_url(case_id),
        )

    def ensure_review_case(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        event_id: int,
        review_reason: str,
    ) -> ReviewCaseSummary:
        with self.connect() as conn:
            summary = self._ensure_review_case(conn, user, ip, tag, bundle, event_id, review_reason)
            conn.commit()
            return summary

    def recheck_review_case(
        self,
        case_id: int,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        review_reason: str | None,
        actor: str,
        actor_tg_id: Optional[int] = None,
        note: str = "",
    ) -> dict[str, Any]:
        reason_codes = json.dumps(bundle.reason_codes, ensure_ascii=False)
        fallback_module_id = str((user or {}).get("module_id") or "").strip()
        fallback_module_name = str((user or {}).get("module_name") or "").strip() or fallback_module_id

        with self.connect() as conn:
            case_row = conn.execute(
                """
                SELECT id, review_reason, repeat_count, opened_at, last_repeat_at
                FROM review_cases
                WHERE id = ?
                """,
                (case_id,),
            ).fetchone()
            if not case_row:
                raise KeyError(f"Review case {case_id} not found")
        event_id = self.record_analysis_event(
            user,
            ip,
            tag,
            bundle,
            observation={
                "client_device_id": (user or {}).get("client_device_id"),
                "client_device_label": (user or {}).get("client_device_label"),
                "client_os_family": (user or {}).get("client_os_family"),
                "client_app_name": (user or {}).get("client_app_name"),
                "device_link_source": (user or {}).get("device_link_source") if (user or {}).get("client_device_id") else None,
            },
        )
        with self.connect() as conn:
            event_context = self._analysis_event_scope_context(
                conn,
                event_id,
                fallback_ip=ip,
                fallback_tag=tag,
                fallback_module_id=fallback_module_id,
                fallback_module_name=fallback_module_name,
            )
        event_created_at = clean_text(event_context["created_at"]) or _utcnow()
        usage_fields, usage_snapshot = self._usage_profile_fields(
            user,
            bundle=bundle,
            repeat_count=max(int(case_row["repeat_count"] or 1), 1),
            anchor_started_at=str(case_row["opened_at"] or event_created_at),
            device_scope_key=event_context["device_scope_key"],
            case_scope_key=event_context["case_scope_key"],
        )
        subject_key = subject_key_from_identity(user, ip=event_context["ip"])
        provider_summary = _provider_summary_payload(bundle)
        hwid_context = _hwid_context(user)
        hard_flags = _derive_hard_flags(bundle, usage_snapshot=usage_snapshot, hwid_context=hwid_context)

        with self.connect() as conn:
            auto_resolution = bundle.verdict if not review_reason and bundle.verdict in {"HOME", "MOBILE"} else ""
            next_status = "OPEN" if review_reason else "RESOLVED" if auto_resolution else "SKIPPED"
            stored_review_reason = str(review_reason or case_row["review_reason"] or "unsure")
            conn.execute(
                """
                UPDATE review_cases
                SET status = ?,
                    review_reason = ?,
                    case_scope_key = ?,
                    device_scope_key = ?,
                    scope_type = ?,
                    subject_key = ?,
                    module_id = ?,
                    module_name = ?,
                    client_device_id = ?,
                    client_device_label = ?,
                    client_os_family = ?,
                    client_app_name = ?,
                    device_link_status = ?,
                    device_link_source = ?,
                    hwid_device_limit = ?,
                    hwid_device_count_exact = ?,
                    uuid = ?,
                    username = ?,
                    system_id = ?,
                    telegram_id = ?,
                    ip = ?,
                    tag = ?,
                    verdict = ?,
                    confidence_band = ?,
                    score = ?,
                    isp = ?,
                    asn = ?,
                    asn_source = ?,
                    provider_source = ?,
                    hard_flags_json = ?,
                    provider_key = ?,
                    provider_classification = ?,
                    provider_service_hint = ?,
                    provider_conflict = ?,
                    provider_review_recommended = ?,
                    punitive_eligible = ?,
                    latest_event_id = ?,
                    reason_codes_json = ?,
                    usage_profile_summary = ?,
                    usage_profile_signal_count = ?,
                    usage_profile_priority = ?,
                    usage_profile_soft_reasons_json = ?,
                    usage_profile_ongoing_duration_seconds = ?,
                    usage_profile_ongoing_duration_text = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    stored_review_reason,
                    event_context["case_scope_key"],
                    event_context["device_scope_key"],
                    event_context["scope_type"],
                    subject_key,
                    event_context["module_id"],
                    event_context["module_name"],
                    event_context["client_device_id"],
                    event_context["client_device_label"],
                    event_context["client_os_family"],
                    event_context["client_app_name"],
                    event_context["device_link_status"],
                    event_context["device_link_source"],
                    hwid_context["hwid_device_limit"],
                    hwid_context["hwid_device_count_exact"],
                    (user or {}).get("uuid"),
                    (user or {}).get("username"),
                    coerce_optional_int((user or {}).get("id")),
                    str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                    event_context["ip"],
                    event_context["tag"],
                    bundle.verdict,
                    bundle.confidence_band,
                    bundle.score,
                    bundle.isp,
                    bundle.asn,
                    bundle.asn_source,
                    bundle.provider_source,
                    json.dumps(hard_flags, ensure_ascii=False),
                    provider_summary["provider_key"],
                    provider_summary["provider_classification"],
                    provider_summary["provider_service_hint"],
                    int(provider_summary["provider_conflict"]),
                    int(provider_summary["provider_review_recommended"]),
                    int(bundle.punitive_eligible),
                    event_id,
                    reason_codes,
                    usage_fields["usage_profile_summary"],
                    usage_fields["usage_profile_signal_count"],
                    usage_fields["usage_profile_priority"],
                    usage_fields["usage_profile_soft_reasons_json"],
                    usage_fields["usage_profile_ongoing_duration_seconds"],
                    usage_fields["usage_profile_ongoing_duration_text"],
                    event_created_at,
                    case_id,
                ),
            )
            if next_status == "RESOLVED":
                expires_at = (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat()
                conn.execute(
                    """
                    INSERT INTO review_resolutions (case_id, event_id, resolution, actor, actor_tg_id, note, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (case_id, event_id, auto_resolution, actor, actor_tg_id, note, event_created_at),
                )
                conn.execute(
                    """
                    INSERT INTO exact_ip_overrides (ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at)
                    VALUES (?, ?, 'review_resolution', ?, ?, ?, ?, ?)
                    ON CONFLICT(ip) DO UPDATE SET
                        decision = excluded.decision,
                        source = excluded.source,
                        actor = excluded.actor,
                        actor_tg_id = excluded.actor_tg_id,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (event_context["ip"], auto_resolution, actor, actor_tg_id, event_created_at, event_created_at, expires_at),
                )
                self._record_labels_for_resolution(conn, case_id, event_id, bundle, auto_resolution)
            elif next_status == "SKIPPED":
                conn.execute(
                    """
                    INSERT INTO review_resolutions (case_id, event_id, resolution, actor, actor_tg_id, note, created_at)
                    VALUES (?, ?, 'SKIP', ?, ?, ?, ?)
                    """,
                    (case_id, event_id, actor, actor_tg_id, note, event_created_at),
                )
                conn.execute(
                    """
                    DELETE FROM exact_ip_overrides
                    WHERE ip = ? AND source = 'review_resolution'
                    """,
                    (event_context["ip"],),
                )
                conn.execute(
                    """
                    DELETE FROM review_labels
                    WHERE case_id = ?
                    """,
                    (case_id,),
                )
            self._attach_case_context(
                conn,
                case_id=case_id,
                ip=event_context["ip"],
                isp=bundle.isp,
                asn=bundle.asn,
                module_id=event_context["module_id"],
                module_name=event_context["module_name"],
                seen_at=event_created_at,
                hit_increment=1,
                first_seen_at=str(case_row["opened_at"] or event_created_at),
            )
            self._persist_usage_profile_snapshot(
                conn,
                case_id=case_id,
                snapshot=usage_snapshot,
                updated_at=event_created_at,
            )
            conn.commit()

        if auto_resolution:
            self.promote_learning_patterns()
        return self.get_review_case(case_id)

    def _hydrate_review_list_item(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row | dict[str, Any],
    ) -> dict[str, Any]:
        item = _resolve_review_module_name(conn, normalize_review_identity_payload(dict(row)))
        if "reason_codes_json" in item:
            item["reason_codes"] = json.loads(item.pop("reason_codes_json"))
        if "usage_profile_soft_reasons_json" in item:
            item["usage_profile_soft_reasons"] = json.loads(item.pop("usage_profile_soft_reasons_json"))
        if "hard_flags_json" in item:
            item["hard_flags"] = json.loads(item.pop("hard_flags_json"))
        item.setdefault("hard_flags", [])
        item["provider_conflict"] = bool(item.get("provider_conflict"))
        item["provider_review_recommended"] = bool(item.get("provider_review_recommended"))
        item["inbound_tag"] = clean_text(item.get("tag")) or None
        item["target_ip"] = clean_text(item.get("ip")) or None
        item["target_scope_type"] = clean_text(item.get("scope_type")) or "ip_only"
        item["device_link_status"] = clean_text(item.get("device_link_status")) or ("exact" if clean_text(item.get("client_device_id")) else "none")
        item["device_link_source"] = clean_text(item.get("device_link_source")) or None
        item["device_display"] = device_display_from_identity(item) if item["device_link_status"] == "exact" else None
        item["shared_account_suspected"] = bool(item.get("shared_account_suspected"))
        item["review_url"] = self.build_review_url(int(item["id"]))
        return item

    def _decode_analysis_event_payload(self, event_row: sqlite3.Row | None) -> dict[str, Any]:
        event_payload = dict(event_row) if event_row else {}
        if event_payload:
            event_payload["reasons"] = json.loads(event_payload.pop("reasons_json"))
            event_payload["signal_flags"] = json.loads(event_payload.pop("signal_flags_json"))
            event_payload["bundle"] = json.loads(event_payload.pop("bundle_json"))
            if "hard_flags_json" in event_payload:
                event_payload["hard_flags"] = json.loads(event_payload.pop("hard_flags_json"))
            event_payload.setdefault("hard_flags", [])
            event_payload["inbound_tag"] = clean_text(event_payload.get("tag")) or None
            event_payload["target_ip"] = clean_text(event_payload.get("ip")) or None
            event_payload["target_scope_type"] = clean_text(event_payload.get("scope_type")) or "ip_only"
            event_payload["device_link_status"] = clean_text(event_payload.get("device_link_status")) or ("exact" if clean_text(event_payload.get("client_device_id")) else "none")
            event_payload["device_link_source"] = clean_text(event_payload.get("device_link_source")) or None
            event_payload["device_display"] = device_display_from_identity(event_payload) if event_payload["device_link_status"] == "exact" else None
            event_payload["shared_account_suspected"] = bool(event_payload.get("shared_account_suspected"))
        return event_payload

    def list_review_cases(
        self,
        filters: Optional[dict[str, Any]] = None,
        *,
        timeout: float | None = None,
        busy_timeout_ms: int | None = None,
        query_time_limit_ms: int | None = None,
    ) -> dict[str, Any]:
        filters = filters or {}
        view = str(filters.get("view") or "full").strip().lower()
        if view not in {"full", "compact"}:
            raise ValueError("view must be 'full' or 'compact'")
        page = max(int(filters.get("page", 1) or 1), 1)
        page_size = min(max(int(filters.get("page_size", 25) or 25), 1), 100)
        sort = str(filters.get("sort", "updated_desc") or "updated_desc")
        sort_map = {
            "priority_desc": "usage_profile_priority DESC, updated_at DESC",
            "priority_asc": "usage_profile_priority ASC, updated_at DESC",
            "updated_desc": "updated_at DESC",
            "updated_asc": "updated_at ASC",
            "score_desc": "score DESC",
            "score_asc": "score ASC",
            "repeat_desc": "repeat_count DESC",
            "repeat_asc": "repeat_count ASC",
        }
        order_by = sort_map.get(sort, "updated_at DESC")
        query = [
            """SELECT id, status, review_reason, case_scope_key, device_scope_key, scope_type, subject_key,
               module_id, module_name, client_device_id, client_device_label, client_os_family, client_app_name,
               device_link_status, device_link_source, hwid_device_limit, hwid_device_count_exact,
               uuid, username, system_id, telegram_id, ip, tag, verdict, confidence_band,
               score, isp, asn, asn_source, provider_source, hard_flags_json, punitive_eligible, repeat_count, reason_codes_json,
               provider_key, provider_classification, provider_service_hint, provider_conflict, provider_review_recommended,
               usage_profile_summary, usage_profile_signal_count, usage_profile_priority,
               usage_profile_soft_reasons_json, usage_profile_ongoing_duration_seconds, usage_profile_ongoing_duration_text,
               opened_at, updated_at, last_repeat_at,
               CASE
                   WHEN punitive_eligible = 1 THEN 'critical'
                   WHEN confidence_band = 'HIGH_HOME' THEN 'high'
                   WHEN confidence_band = 'PROBABLE_HOME' THEN 'medium'
                   ELSE 'low'
               END AS severity
               FROM review_cases"""
        ]
        clauses = []
        params: list[Any] = []
        if filters.get("status"):
            clauses.append("status = ?")
            params.append(filters["status"])
        if filters.get("confidence_band"):
            clauses.append("confidence_band = ?")
            params.append(filters["confidence_band"])
        if filters.get("asn") not in (None, ""):
            clauses.append("asn = ?")
            params.append(int(filters["asn"]))
        if filters.get("username"):
            clauses.append("username LIKE ?")
            params.append(f"%{filters['username']}%")
        if filters.get("module_id"):
            clauses.append(
                """
                EXISTS (
                    SELECT 1
                    FROM review_case_modules rcm
                    WHERE rcm.case_id = review_cases.id AND rcm.module_id = ?
                )
                """
            )
            params.append(str(filters["module_id"]))
        if filters.get("system_id") not in (None, ""):
            clauses.append("system_id = ?")
            params.append(int(filters["system_id"]))
        if filters.get("telegram_id") not in (None, ""):
            clauses.append("telegram_id = ?")
            params.append(str(filters["telegram_id"]))
        if filters.get("review_reason"):
            clauses.append("review_reason = ?")
            params.append(filters["review_reason"])
        if filters.get("severity"):
            severity = str(filters["severity"])
            if severity == "critical":
                clauses.append("punitive_eligible = 1")
            elif severity == "high":
                clauses.append("punitive_eligible = 0 AND confidence_band = 'HIGH_HOME'")
            elif severity == "medium":
                clauses.append("confidence_band = 'PROBABLE_HOME'")
            elif severity == "low":
                clauses.append("confidence_band = 'UNSURE'")
        if filters.get("punitive_eligible") not in (None, ""):
            clauses.append("punitive_eligible = ?")
            params.append(1 if str(filters["punitive_eligible"]).lower() in {"1", "true", "yes"} else 0)
        if filters.get("repeat_count_min") not in (None, ""):
            clauses.append("repeat_count >= ?")
            params.append(int(filters["repeat_count_min"]))
        if filters.get("repeat_count_max") not in (None, ""):
            clauses.append("repeat_count <= ?")
            params.append(int(filters["repeat_count_max"]))
        if filters.get("opened_from"):
            clauses.append("opened_at >= ?")
            params.append(_parse_day_boundary(filters["opened_from"], end_of_day=False))
        if filters.get("opened_to"):
            clauses.append("opened_at <= ?")
            params.append(_parse_day_boundary(filters["opened_to"], end_of_day=True))
        if filters.get("q"):
            search = f"%{filters['q']}%"
            clauses.append(
                "(ip LIKE ? OR username LIKE ? OR isp LIKE ? OR uuid LIKE ? OR telegram_id LIKE ? OR CAST(system_id AS TEXT) LIKE ? OR client_device_id LIKE ? OR client_device_label LIKE ?)"
            )
            params.extend([search] * 8)
        if clauses:
            query.append("WHERE " + " AND ".join(clauses))
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        count_sql = f"SELECT COUNT(*) AS cnt FROM review_cases{where_sql}"
        query.append(f"ORDER BY {order_by} LIMIT ? OFFSET ?")
        sql = " ".join(query)
        with self.storage.connect(
            timeout=timeout,
            busy_timeout_ms=busy_timeout_ms,
            query_time_limit_ms=query_time_limit_ms,
        ) as conn:
            total = conn.execute(count_sql, params).fetchone()["cnt"]
            rows = conn.execute(sql, [*params, page_size, (page - 1) * page_size]).fetchall()
            items = [self._hydrate_review_list_item(conn, row) for row in rows]
            case_ids = [int(item["id"]) for item in items]
            compact_view = view == "compact"
            ip_inventory = self._case_ip_inventory(conn, case_ids, per_case_limit=4 if compact_view else None)
            if compact_view:
                items = [
                    self._apply_compact_queue_payload(
                        item,
                        ip_inventory=ip_inventory.get(int(item["id"]), []),
                    )
                    for item in items
                ]
            else:
                module_inventory = self._case_module_inventory(conn, case_ids)
                items = [
                    self._apply_inventory_payloads(
                        item,
                        ip_inventory=ip_inventory.get(int(item["id"]), []),
                        module_inventory=module_inventory.get(int(item["id"]), []),
                    )
                    for item in items
                ]
                same_device_history = self._batch_same_device_ip_history(
                    conn,
                    device_scope_keys=[clean_text(item.get("device_scope_key")) for item in items],
                    limit=6,
                )
                for item in items:
                    item["same_device_ip_history"] = same_device_history.get(
                        clean_text(item.get("device_scope_key")),
                        [],
                    )
                self._shared_account_flags_for_items(conn, items)
        return {
            "items": items,
            "count": total,
            "page": page,
            "page_size": page_size,
        }

    def list_review_case_teasers(
        self,
        *,
        status: str = "OPEN",
        limit: int = 6,
        timeout: float | None = None,
        busy_timeout_ms: int | None = None,
    ) -> list[dict[str, Any]]:
        with self.storage.connect(timeout=timeout, busy_timeout_ms=busy_timeout_ms) as conn:
            rows = conn.execute(
                """
                SELECT id, review_reason, username, uuid, system_id, telegram_id, ip, updated_at
                FROM review_cases
                WHERE status = ?
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (status, max(int(limit), 1)),
            ).fetchall()
        items: list[dict[str, Any]] = []
        for row in rows:
            payload = normalize_review_identity_payload(dict(row))
            display_name = (
                clean_text(payload.get("username"))
                or clean_text(payload.get("uuid"))
                or (str(payload.get("system_id")) if payload.get("system_id") not in (None, "") else "")
                or clean_text(payload.get("telegram_id"))
                or clean_text(payload.get("ip"))
            )
            items.append(
                {
                    "id": int(payload["id"]),
                    "display_name": display_name or clean_text(payload.get("ip")),
                    "review_reason": clean_text(payload.get("review_reason")),
                    "ip": clean_text(payload.get("ip")),
                    "updated_at": clean_text(payload.get("updated_at")),
                }
            )
        return items

    def get_review_case(self, case_id: int) -> dict[str, Any]:
        with self.connect() as conn:
            case_row = conn.execute(
                """
                SELECT * FROM review_cases WHERE id = ?
                """,
                (case_id,),
            ).fetchone()
            if not case_row:
                raise KeyError(f"Review case {case_id} not found")
            event_row = conn.execute(
                "SELECT * FROM analysis_events WHERE id = ?",
                (case_row["latest_event_id"],),
            ).fetchone()
            resolutions = conn.execute(
                """
                SELECT id, resolution, actor, actor_tg_id, note, created_at
                FROM review_resolutions
                WHERE case_id = ?
                ORDER BY created_at DESC
                """,
                (case_id,),
            ).fetchall()
            case_subject_key = clean_text(case_row["subject_key"]) or subject_key_from_identity(case_row, ip=case_row["ip"])
            related_cases = conn.execute(
                """
                SELECT id, status, subject_key, module_id, module_name, ip, verdict, confidence_band, updated_at, username, uuid, system_id, telegram_id
                FROM review_cases
                WHERE id != ? AND status != 'MERGED' AND subject_key = ?
                ORDER BY updated_at DESC
                LIMIT 10
                """,
                (case_id, case_subject_key),
            ).fetchall()
            enforcement_jobs = []
            if self.table_exists(conn, "enforcement_jobs"):
                enforcement_jobs = conn.execute(
                    """
                    SELECT id, event_uid, job_type, status, attempt_count, last_error, last_error_at,
                           applied_at, created_at, updated_at, payload_json
                    FROM enforcement_jobs
                    WHERE review_case_id = ? OR analysis_event_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (case_id, case_row["latest_event_id"]),
                ).fetchall()
            case = self._hydrate_review_list_item(conn, case_row)
            case = self._apply_inventory_payloads(
                case,
                ip_inventory=self._case_ip_inventory(conn, [case_id]).get(case_id, []),
                module_inventory=self._case_module_inventory(conn, [case_id]).get(case_id, []),
            )
            case["same_device_ip_history"] = self._same_device_ip_history(
                conn,
                device_scope_key=clean_text(case.get("device_scope_key")),
            )
            usage_profile = (
                self.read_model_loader(conn, "review_usage_profile", str(case_id))
                if self.read_model_loader
                else None
            )
            if usage_profile is None or self._usage_profile_snapshot_is_stale(conn, case, usage_profile):
                usage_profile = build_usage_profile_snapshot(
                    _ConnectionBackedStore(self, conn),
                    _review_identity(case),
                    anchor_started_at=case.get("opened_at"),
                    device_scope_key=clean_text(case.get("device_scope_key")),
                    case_scope_key=clean_text(case.get("case_scope_key")),
                )
                self._persist_usage_profile_snapshot(
                    conn,
                    case_id=case_id,
                    snapshot=usage_profile,
                    updated_at=clean_text(case.get("updated_at")) or _utcnow(),
                )
            case["shared_account_suspected"] = "sharing_hwid_limit_exceeded" in set(case.get("hard_flags") or [])
            case["latest_event"] = self._decode_analysis_event_payload(event_row)
            if case["latest_event"]:
                case["latest_event"]["shared_account_suspected"] = (
                    bool(case["shared_account_suspected"])
                    if clean_text(case["latest_event"].get("target_scope_type")) == "subject_ip"
                    else False
                )
            case["resolutions"] = [dict(row) for row in resolutions]
            case["usage_profile"] = usage_profile
            case["enforcement"] = [
                {
                    **{
                        key: value
                        for key, value in dict(row).items()
                        if key != "payload_json"
                    },
                    "payload": json.loads(str(row["payload_json"] or "{}")),
                }
                for row in enforcement_jobs
            ]
            related_items = [self._hydrate_review_list_item(conn, row) for row in related_cases]
            related_case_ids = [int(item["id"]) for item in related_items]
            related_ip_inventory = self._case_ip_inventory(conn, related_case_ids)
            related_module_inventory = self._case_module_inventory(conn, related_case_ids)
            self._shared_account_flags_for_items(conn, related_items)
            case["related_cases"] = [
                self._apply_inventory_payloads(
                    item,
                    ip_inventory=related_ip_inventory.get(int(item["id"]), []),
                    module_inventory=related_module_inventory.get(int(item["id"]), []),
                )
                for item in related_items
            ]
            conn.commit()
            return case

    def rebuild_review_case_usage_profiles(self, conn: sqlite3.Connection) -> int:
        rows = conn.execute(
            """
            SELECT id, uuid, username, system_id, telegram_id, case_scope_key, device_scope_key,
                   scope_type, opened_at, repeat_count, confidence_band, punitive_eligible
            FROM review_cases
            WHERE latest_event_id IS NOT NULL
            """
        ).fetchall()
        if not rows:
            return 0

        snapshot_store: Any = _ConnectionBackedStore(self, conn)
        updated = 0
        for row in rows:
            payload = dict(row)
            snapshot = build_usage_profile_snapshot(
                snapshot_store,
                _review_identity(payload),
                anchor_started_at=clean_text(payload.get("opened_at")),
                device_scope_key=clean_text(payload.get("device_scope_key")),
                case_scope_key=clean_text(payload.get("case_scope_key")),
            )
            priority = build_usage_profile_priority(
                snapshot,
                punitive_eligible=bool(payload.get("punitive_eligible")),
                confidence_band=clean_text(payload.get("confidence_band")),
                repeat_count=max(int(payload.get("repeat_count") or 1), 1),
            )
            conn.execute(
                """
                UPDATE review_cases
                SET usage_profile_summary = ?,
                    usage_profile_signal_count = ?,
                    usage_profile_priority = ?,
                    usage_profile_soft_reasons_json = ?,
                    usage_profile_ongoing_duration_seconds = ?,
                    usage_profile_ongoing_duration_text = ?
                WHERE id = ?
                """,
                (
                    str(snapshot.get("usage_profile_summary") or ""),
                    int(priority["signal_count"]),
                    int(priority["priority"]),
                    json.dumps(snapshot.get("soft_reasons", []), ensure_ascii=False),
                    snapshot.get("ongoing_duration_seconds"),
                    str(snapshot.get("ongoing_duration_text") or ""),
                    int(payload["id"]),
                ),
            )
            updated += 1
        return updated

    def backfill_review_subjects_and_contexts(self, conn: sqlite3.Connection) -> None:
        case_rows = conn.execute(
            """
            SELECT id, subject_key, case_scope_key, device_scope_key, scope_type, client_device_id,
                   client_device_label, client_os_family, client_app_name, latest_event_id,
                   module_id, module_name, uuid, username, system_id, telegram_id,
                   ip, isp, asn, opened_at, updated_at, repeat_count, last_repeat_at
            FROM review_cases
            """
        ).fetchall()
        for row in case_rows:
            payload = dict(row)
            subject_key = subject_key_from_identity(payload, ip=payload.get("ip"))
            latest_event_id = int(payload.get("latest_event_id") or 0)
            event_context = self._analysis_event_scope_context(
                conn,
                latest_event_id,
                fallback_ip=clean_text(payload.get("ip")),
                fallback_tag="",
                fallback_module_id=clean_text(payload.get("module_id")),
                fallback_module_name=clean_text(payload.get("module_name")),
            ) if latest_event_id else build_review_scope(payload, payload, ip=payload.get("ip"))
            if clean_text(payload.get("subject_key")) != subject_key:
                conn.execute(
                    "UPDATE review_cases SET subject_key = ? WHERE id = ?",
                    (subject_key, int(row["id"])),
                )
            conn.execute(
                """
                UPDATE review_cases
                SET case_scope_key = ?,
                    device_scope_key = ?,
                    scope_type = ?,
                    client_device_id = ?,
                    client_device_label = ?,
                    client_os_family = ?,
                    client_app_name = ?,
                    last_repeat_at = COALESCE(NULLIF(last_repeat_at, ''), updated_at, opened_at)
                WHERE id = ?
                """,
                (
                    event_context.get("case_scope_key"),
                    event_context.get("device_scope_key"),
                    event_context.get("scope_type"),
                    event_context.get("client_device_id"),
                    event_context.get("client_device_label"),
                    event_context.get("client_os_family"),
                    event_context.get("client_app_name"),
                    int(row["id"]),
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO review_case_ips (
                    case_id, ip, hit_count, first_seen_at, last_seen_at, isp, asn
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(row["id"]),
                    clean_text(row["ip"]),
                    max(int(row["repeat_count"] or 1), 1),
                    clean_text(row["opened_at"] or row["updated_at"]) or _utcnow(),
                    clean_text(row["updated_at"] or row["opened_at"]) or _utcnow(),
                    clean_text(row["isp"]) or None,
                    row["asn"],
                ),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO review_case_modules (
                    case_id, module_id, module_name, first_seen_at, last_seen_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    int(row["id"]),
                    _normalized_module_id(row["module_id"]),
                    clean_text(row["module_name"]) or None,
                    clean_text(row["opened_at"] or row["updated_at"]) or _utcnow(),
                    clean_text(row["updated_at"] or row["opened_at"]) or _utcnow(),
                ),
            )
        event_rows = conn.execute(
            """
            SELECT id, subject_key, case_scope_key, device_scope_key, scope_type,
                   uuid, username, system_id, telegram_id, ip,
                   client_device_id, client_device_label, client_os_family, client_app_name
            FROM analysis_events
            """
        ).fetchall()
        for row in event_rows:
            payload = dict(row)
            subject_key = subject_key_from_identity(payload, ip=payload.get("ip"))
            scope = build_review_scope(payload, payload, ip=payload.get("ip"))
            if clean_text(payload.get("subject_key")) != subject_key:
                conn.execute(
                    "UPDATE analysis_events SET subject_key = ? WHERE id = ?",
                    (subject_key, int(row["id"])),
                )
            conn.execute(
                """
                UPDATE analysis_events
                SET case_scope_key = ?,
                    device_scope_key = ?,
                    scope_type = ?
                WHERE id = ?
                """,
                (
                    scope.get("case_scope_key"),
                    scope.get("device_scope_key"),
                    scope.get("scope_type"),
                    int(row["id"]),
                ),
            )

    def collapse_open_subject_duplicates(self, conn: sqlite3.Connection) -> int:
        rows = conn.execute(
            """
            SELECT id, subject_key, case_scope_key, device_scope_key, ip, module_id, module_name,
                   repeat_count, opened_at, updated_at, last_repeat_at,
                   latest_event_id, verdict, confidence_band, score, isp, asn, punitive_eligible
            FROM review_cases
            WHERE status = 'OPEN' AND case_scope_key IS NOT NULL AND case_scope_key != ''
            ORDER BY case_scope_key ASC, updated_at DESC, id DESC
            """
        ).fetchall()
        grouped: dict[str, list[sqlite3.Row]] = {}
        for row in rows:
            grouped.setdefault(str(row["case_scope_key"]), []).append(row)

        merged_count = 0
        for case_scope_key, bucket in grouped.items():
            if len(bucket) < 2:
                continue
            survivor = bucket[0]
            duplicate_rows = bucket[1:]
            earliest_opened = min(clean_text(row["opened_at"]) or clean_text(row["updated_at"]) for row in bucket)
            total_repeat_count = sum(max(int(row["repeat_count"] or 0), 0) for row in bucket)
            last_repeat_at = max(
                clean_text(row["last_repeat_at"] or row["updated_at"] or row["opened_at"])
                for row in bucket
            )
            for duplicate in duplicate_rows:
                duplicate_ip_rows = conn.execute(
                    """
                    SELECT ip, hit_count, first_seen_at, last_seen_at, isp, asn
                    FROM review_case_ips
                    WHERE case_id = ?
                    """,
                    (int(duplicate["id"]),),
                ).fetchall()
                for ip_row in duplicate_ip_rows:
                    self._upsert_review_case_ip(
                        conn,
                        case_id=int(survivor["id"]),
                        ip=str(ip_row["ip"]),
                        isp=ip_row["isp"],
                        asn=ip_row["asn"],
                        seen_at=str(ip_row["last_seen_at"]),
                        hit_increment=int(ip_row["hit_count"] or 1),
                        first_seen_at=str(ip_row["first_seen_at"]),
                    )
                duplicate_module_rows = conn.execute(
                    """
                    SELECT module_id, module_name, first_seen_at, last_seen_at
                    FROM review_case_modules
                    WHERE case_id = ?
                    """,
                    (int(duplicate["id"]),),
                ).fetchall()
                for module_row in duplicate_module_rows:
                    self._upsert_review_case_module(
                        conn,
                        case_id=int(survivor["id"]),
                        module_id=str(module_row["module_id"] or ""),
                        module_name=module_row["module_name"],
                        seen_at=str(module_row["last_seen_at"]),
                        first_seen_at=str(module_row["first_seen_at"]),
                    )
                conn.execute("DELETE FROM review_case_ips WHERE case_id = ?", (int(duplicate["id"]),))
                conn.execute("DELETE FROM review_case_modules WHERE case_id = ?", (int(duplicate["id"]),))
                conn.execute(
                    """
                    UPDATE review_cases
                    SET status = 'MERGED',
                        review_reason = 'merged_subject_key',
                        case_scope_key = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (case_scope_key, clean_text(survivor["updated_at"]) or _utcnow(), int(duplicate["id"])),
                )
                merged_count += 1
            conn.execute(
                """
                UPDATE review_cases
                SET repeat_count = ?,
                    opened_at = ?,
                    last_repeat_at = ?
                WHERE id = ?
                """,
                (
                    max(total_repeat_count, 1),
                    earliest_opened,
                    last_repeat_at,
                    int(survivor["id"]),
                ),
            )
        return merged_count

    def _record_labels_for_resolution(
        self,
        conn: sqlite3.Connection,
        case_id: int,
        event_id: int,
        bundle: DecisionBundle,
        decision: str,
    ) -> None:
        labels: set[tuple[str, str]] = set()
        if bundle.asn:
            labels.add(("asn", str(bundle.asn)))
        provider_evidence = bundle.signal_flags.get("provider_evidence")
        if isinstance(provider_evidence, dict):
            provider_key = str(provider_evidence.get("provider_key") or "").strip().lower()
            service_type_hint = str(provider_evidence.get("service_type_hint") or "").strip().lower()
            if provider_key:
                labels.add(("provider", provider_key))
                if service_type_hint and service_type_hint != "unknown":
                    labels.add(("provider_service", f"{provider_key}:{service_type_hint}"))
        for reason in bundle.reasons:
            metadata = reason.metadata or {}
            for keyword in metadata.get("keywords", []):
                labels.add(("keyword", str(keyword)))
            if metadata.get("combo_key"):
                labels.add(("combo", str(metadata["combo_key"])))
            if metadata.get("ptr_domain"):
                labels.add(("ptr_domain", str(metadata["ptr_domain"])))
            if metadata.get("subnet"):
                labels.add(("subnet", str(metadata["subnet"])))

        now = _utcnow()
        for pattern_type, pattern_value in labels:
            conn.execute(
                """
                INSERT OR IGNORE INTO review_labels (case_id, event_id, pattern_type, pattern_value, decision, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (case_id, event_id, pattern_type, pattern_value, decision, now),
            )

    def promote_learning_patterns(self) -> None:
        live_rules = self.live_rules_loader()
        settings = live_rules.get("rules", {}).get("settings", {})
        asn_min_support = int(settings.get("learning_promote_asn_min_support", 10))
        asn_min_precision = float(settings.get("learning_promote_asn_min_precision", 0.95))
        combo_min_support = int(settings.get("learning_promote_combo_min_support", 5))
        combo_min_precision = float(settings.get("learning_promote_combo_min_precision", 0.90))

        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT pattern_type, pattern_value, decision, COUNT(*) AS support
                FROM review_labels
                GROUP BY pattern_type, pattern_value, decision
                """
            ).fetchall()
            stats: dict[tuple[str, str], dict[str, int]] = {}
            for row in rows:
                key = (row["pattern_type"], row["pattern_value"])
                stats.setdefault(key, {})
                stats[key][row["decision"]] = int(row["support"])

            conn.execute("DELETE FROM learning_pattern_stats")
            conn.execute("DELETE FROM learning_patterns_active")
            now = _utcnow()
            for (pattern_type, pattern_value), decision_counts in stats.items():
                total = sum(decision_counts.values())
                best_decision = None
                best_support = -1
                best_precision = -1.0
                ambiguous = False
                for decision, support in decision_counts.items():
                    precision = support / total if total else 0.0
                    conn.execute(
                        """
                        INSERT INTO learning_pattern_stats (
                            pattern_type, pattern_value, decision, support, total, precision, updated_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pattern_type,
                            pattern_value,
                            decision,
                            support,
                            total,
                            precision,
                            now,
                            json.dumps({"counts": decision_counts}, ensure_ascii=False),
                        ),
                    )
                    if support > best_support or (
                        support == best_support and precision > best_precision
                    ):
                        best_decision = decision
                        best_support = support
                        best_precision = precision
                        ambiguous = False
                    elif support == best_support and abs(precision - best_precision) < 1e-9:
                        ambiguous = True

                if ambiguous or not best_decision:
                    continue
                if pattern_type == "asn":
                    min_support = asn_min_support
                    min_precision = asn_min_precision
                else:
                    min_support = combo_min_support
                    min_precision = combo_min_precision

                if best_support >= min_support and best_precision >= min_precision:
                    conn.execute(
                        """
                        INSERT INTO learning_patterns_active (
                            pattern_type, pattern_value, decision, support, precision, promoted_at, metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            pattern_type,
                            pattern_value,
                            best_decision,
                            best_support,
                            best_precision,
                            now,
                            json.dumps({"total": total}, ensure_ascii=False),
                        ),
                    )
            conn.commit()

    def get_promoted_pattern(self, pattern_type: str, pattern_value: str) -> Optional[dict[str, Any]]:
        with self.connect() as conn:
            row = conn.execute(
                """
                SELECT pattern_type, pattern_value, decision, support, precision, metadata_json
                FROM learning_patterns_active
                WHERE pattern_type = ? AND pattern_value = ?
                """,
                (pattern_type, pattern_value),
            ).fetchone()
        if not row:
            return None
        payload = dict(row)
        payload["metadata"] = json.loads(payload.pop("metadata_json"))
        return payload

    def resolve_review_case(
        self,
        case_id: int,
        resolution: str,
        actor: str,
        actor_tg_id: Optional[int] = None,
        note: str = "",
    ) -> dict[str, Any]:
        if resolution not in {"MOBILE", "HOME", "SKIP"}:
            raise ValueError("Resolution must be MOBILE, HOME or SKIP")

        with self.connect() as conn:
            case_row = conn.execute(
                "SELECT * FROM review_cases WHERE id = ?",
                (case_id,),
            ).fetchone()
            if not case_row:
                raise KeyError(f"Review case {case_id} not found")
            event_row = conn.execute(
                "SELECT bundle_json, ip FROM analysis_events WHERE id = ?",
                (case_row["latest_event_id"],),
            ).fetchone()
            now = _utcnow()
            conn.execute(
                """
                INSERT INTO review_resolutions (case_id, event_id, resolution, actor, actor_tg_id, note, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (case_id, case_row["latest_event_id"], resolution, actor, actor_tg_id, note, now),
            )
            status = "RESOLVED" if resolution in {"MOBILE", "HOME"} else "SKIPPED"
            conn.execute(
                """
                UPDATE review_cases
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, now, case_id),
            )
            if resolution == "SKIP":
                conn.execute(
                    """
                    DELETE FROM exact_ip_overrides
                    WHERE ip = ? AND source = 'review_resolution'
                    """,
                    (event_row["ip"],),
                )
                conn.execute(
                    """
                    DELETE FROM review_labels
                    WHERE case_id = ?
                    """,
                    (case_id,),
                )
            else:
                expires_at = (datetime.utcnow() + timedelta(days=7)).replace(microsecond=0).isoformat()
                conn.execute(
                    """
                    INSERT INTO exact_ip_overrides (ip, decision, source, actor, actor_tg_id, created_at, updated_at, expires_at)
                    VALUES (?, ?, 'review_resolution', ?, ?, ?, ?, ?)
                    ON CONFLICT(ip) DO UPDATE SET
                        decision = excluded.decision,
                        source = excluded.source,
                        actor = excluded.actor,
                        actor_tg_id = excluded.actor_tg_id,
                        updated_at = excluded.updated_at,
                        expires_at = excluded.expires_at
                    """,
                    (event_row["ip"], resolution, actor, actor_tg_id, now, now, expires_at),
                )
                bundle = DecisionBundle.from_dict(json.loads(event_row["bundle_json"]))
                self._record_labels_for_resolution(conn, case_id, case_row["latest_event_id"], bundle, resolution)
            conn.commit()

        if resolution in {"HOME", "MOBILE"}:
            self.promote_learning_patterns()
        return self.get_review_case(case_id)
