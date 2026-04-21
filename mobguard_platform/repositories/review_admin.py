from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from typing import Any, Callable, Optional

from ..models import DecisionBundle, ReviewCaseSummary
from .base import SQLiteRepository


def _utcnow() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _coerce_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _parse_day_boundary(value: Any, *, end_of_day: bool) -> str:
    parsed = datetime.strptime(str(value), "%Y-%m-%d")
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed.isoformat()


def _normalize_review_identity_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    raw_uuid = normalized.get("uuid")
    if normalized.get("system_id") in (None, "") and raw_uuid not in (None, ""):
        raw_uuid_text = str(raw_uuid).strip()
        if raw_uuid_text.isdigit():
            normalized["system_id"] = int(raw_uuid_text)
            normalized["uuid"] = None
    return normalized


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


class ReviewAdminRepository(SQLiteRepository):
    def __init__(
        self,
        storage,
        *,
        base_config: dict[str, Any],
        live_rules_loader: Callable[[], dict[str, Any]],
    ):
        super().__init__(storage)
        self.base_config = base_config
        self.live_rules_loader = live_rules_loader

    def record_analysis_event(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
    ) -> int:
        now = _utcnow()
        payload = bundle.to_dict()
        module_id = str((user or {}).get("module_id") or "").strip() or None
        module_name = str((user or {}).get("module_name") or "").strip() or module_id
        with self.connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO analysis_events (
                    created_at, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                    verdict, confidence_band, score, isp, asn, punitive_eligible,
                    reasons_json, signal_flags_json, bundle_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    now,
                    module_id,
                    module_name,
                    (user or {}).get("uuid"),
                    (user or {}).get("username"),
                    _coerce_optional_int((user or {}).get("id")),
                    str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                    ip,
                    tag,
                    bundle.verdict,
                    bundle.confidence_band,
                    bundle.score,
                    bundle.isp,
                    bundle.asn,
                    int(bundle.punitive_eligible),
                    json.dumps([reason.to_dict() for reason in bundle.reasons], ensure_ascii=False),
                    json.dumps(bundle.signal_flags, ensure_ascii=False),
                    json.dumps(payload, ensure_ascii=False),
                ),
            )
            conn.commit()
            return int(cursor.lastrowid)

    def build_review_url(self, case_id: int) -> str:
        rules_state = self.live_rules_loader()
        base_url = str(rules_state.get("rules", {}).get("settings", {}).get("review_ui_base_url", "")).rstrip("/")
        if not base_url:
            base_url = str(self.base_config.get("settings", {}).get("review_ui_base_url", "")).rstrip("/")
        if not base_url:
            return ""
        return f"{base_url}/reviews/{case_id}"

    def ensure_review_case(
        self,
        user: Optional[dict[str, Any]],
        ip: str,
        tag: str,
        bundle: DecisionBundle,
        event_id: int,
        review_reason: str,
    ) -> ReviewCaseSummary:
        now = _utcnow()
        module_id = str((user or {}).get("module_id") or "").strip()
        module_name = str((user or {}).get("module_name") or "").strip() or module_id
        unique_key = f"{module_id or 'legacy'}:{(user or {}).get('uuid', 'unknown')}:{ip}:{tag}"
        reason_codes = json.dumps(bundle.reason_codes, ensure_ascii=False)
        with self.connect() as conn:
            existing = conn.execute(
                "SELECT id, repeat_count FROM review_cases WHERE unique_key = ? AND module_id = ?",
                (unique_key, module_id),
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE review_cases
                    SET status = 'OPEN',
                        review_reason = ?,
                        module_name = ?,
                        username = ?,
                        system_id = ?,
                        telegram_id = ?,
                        verdict = ?,
                        confidence_band = ?,
                        score = ?,
                        isp = ?,
                        asn = ?,
                        punitive_eligible = ?,
                        latest_event_id = ?,
                        repeat_count = ?,
                        reason_codes_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        review_reason,
                        module_name,
                        (user or {}).get("username"),
                        _coerce_optional_int((user or {}).get("id")),
                        str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                        bundle.verdict,
                        bundle.confidence_band,
                        bundle.score,
                        bundle.isp,
                        bundle.asn,
                        int(bundle.punitive_eligible),
                        event_id,
                        int(existing["repeat_count"]) + 1,
                        reason_codes,
                        now,
                        existing["id"],
                    ),
                )
                case_id = int(existing["id"])
            else:
                cursor = conn.execute(
                    """
                    INSERT INTO review_cases (
                        unique_key, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag,
                        verdict, confidence_band, score, isp, asn, punitive_eligible, latest_event_id, repeat_count,
                        reason_codes_json, opened_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        unique_key,
                        "OPEN",
                        review_reason,
                        module_id,
                        module_name,
                        (user or {}).get("uuid"),
                        (user or {}).get("username"),
                        _coerce_optional_int((user or {}).get("id")),
                        str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                        ip,
                        tag,
                        bundle.verdict,
                        bundle.confidence_band,
                        bundle.score,
                        bundle.isp,
                        bundle.asn,
                        int(bundle.punitive_eligible),
                        event_id,
                        1,
                        reason_codes,
                        now,
                        now,
                    ),
                )
                case_id = int(cursor.lastrowid)
            conn.commit()
        summary = self.get_review_case(case_id)
        return ReviewCaseSummary(
            id=summary["id"],
            status=summary["status"],
            review_reason=summary["review_reason"],
            module_id=summary.get("module_id") or "",
            module_name=summary.get("module_name") or "",
            uuid=summary.get("uuid") or "",
            username=summary.get("username") or "",
            system_id=summary.get("system_id"),
            telegram_id=summary.get("telegram_id"),
            ip=summary["ip"],
            tag=summary.get("tag") or "",
            verdict=summary["verdict"],
            confidence_band=summary["confidence_band"],
            score=summary["score"],
            isp=summary.get("isp") or "",
            asn=summary.get("asn"),
            repeat_count=summary["repeat_count"],
            reason_codes=summary.get("reason_codes", []),
            updated_at=summary.get("updated_at", ""),
            review_url=summary.get("review_url", ""),
        )

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
        now = _utcnow()
        reason_codes = json.dumps(bundle.reason_codes, ensure_ascii=False)

        with self.connect() as conn:
            case_row = conn.execute(
                "SELECT id, review_reason, repeat_count FROM review_cases WHERE id = ?",
                (case_id,),
            ).fetchone()
            if not case_row:
                raise KeyError(f"Review case {case_id} not found")
        event_id = self.record_analysis_event(user, ip, tag, bundle)

        with self.connect() as conn:
            next_status = "OPEN" if review_reason else "SKIPPED"
            stored_review_reason = str(review_reason or case_row["review_reason"] or "unsure")
            conn.execute(
                """
                UPDATE review_cases
                SET status = ?,
                    review_reason = ?,
                    module_id = ?,
                    module_name = ?,
                    uuid = ?,
                    username = ?,
                    system_id = ?,
                    telegram_id = ?,
                    tag = ?,
                    verdict = ?,
                    confidence_band = ?,
                    score = ?,
                    isp = ?,
                    asn = ?,
                    punitive_eligible = ?,
                    latest_event_id = ?,
                    reason_codes_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status,
                    stored_review_reason,
                    str((user or {}).get("module_id") or "").strip(),
                    str((user or {}).get("module_name") or "").strip() or str((user or {}).get("module_id") or "").strip(),
                    (user or {}).get("uuid"),
                    (user or {}).get("username"),
                    _coerce_optional_int((user or {}).get("id")),
                    str((user or {}).get("telegramId")) if (user or {}).get("telegramId") is not None else None,
                    tag,
                    bundle.verdict,
                    bundle.confidence_band,
                    bundle.score,
                    bundle.isp,
                    bundle.asn,
                    int(bundle.punitive_eligible),
                    event_id,
                    reason_codes,
                    now,
                    case_id,
                ),
            )
            if next_status == "SKIPPED":
                conn.execute(
                    """
                    INSERT INTO review_resolutions (case_id, event_id, resolution, actor, actor_tg_id, note, created_at)
                    VALUES (?, ?, 'SKIP', ?, ?, ?, ?)
                    """,
                    (case_id, event_id, actor, actor_tg_id, note, now),
                )
                conn.execute(
                    """
                    DELETE FROM exact_ip_overrides
                    WHERE ip = ? AND source = 'review_resolution'
                    """,
                    (ip,),
                )
                conn.execute(
                    """
                    DELETE FROM review_labels
                    WHERE case_id = ?
                    """,
                    (case_id,),
                )
            conn.commit()

        return self.get_review_case(case_id)

    def _hydrate_review_list_item(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row | dict[str, Any],
    ) -> dict[str, Any]:
        item = _resolve_review_module_name(conn, _normalize_review_identity_payload(dict(row)))
        if "reason_codes_json" in item:
            item["reason_codes"] = json.loads(item.pop("reason_codes_json"))
        item["review_url"] = self.build_review_url(int(item["id"]))
        return item

    def _decode_analysis_event_payload(self, event_row: sqlite3.Row | None) -> dict[str, Any]:
        event_payload = dict(event_row) if event_row else {}
        if event_payload:
            event_payload["reasons"] = json.loads(event_payload.pop("reasons_json"))
            event_payload["signal_flags"] = json.loads(event_payload.pop("signal_flags_json"))
            event_payload["bundle"] = json.loads(event_payload.pop("bundle_json"))
        return event_payload

    def list_review_cases(self, filters: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        filters = filters or {}
        page = max(int(filters.get("page", 1) or 1), 1)
        page_size = min(max(int(filters.get("page_size", 25) or 25), 1), 100)
        sort = str(filters.get("sort", "updated_desc") or "updated_desc")
        sort_map = {
            "updated_desc": "updated_at DESC",
            "updated_asc": "updated_at ASC",
            "score_desc": "score DESC",
            "score_asc": "score ASC",
            "repeat_desc": "repeat_count DESC",
            "repeat_asc": "repeat_count ASC",
        }
        order_by = sort_map.get(sort, "updated_at DESC")
        query = [
            """SELECT id, status, review_reason, module_id, module_name, uuid, username, system_id, telegram_id, ip, tag, verdict, confidence_band,
               score, isp, asn, punitive_eligible, repeat_count, reason_codes_json, opened_at, updated_at,
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
            clauses.append("module_id = ?")
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
                "(ip LIKE ? OR username LIKE ? OR isp LIKE ? OR uuid LIKE ? OR telegram_id LIKE ? OR CAST(system_id AS TEXT) LIKE ?)"
            )
            params.extend([search] * 6)
        if clauses:
            query.append("WHERE " + " AND ".join(clauses))
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        count_sql = f"SELECT COUNT(*) AS cnt FROM review_cases{where_sql}"
        query.append(f"ORDER BY {order_by} LIMIT ? OFFSET ?")
        sql = " ".join(query)
        with self.connect() as conn:
            total = conn.execute(count_sql, params).fetchone()["cnt"]
            rows = conn.execute(sql, [*params, page_size, (page - 1) * page_size]).fetchall()
            items = [self._hydrate_review_list_item(conn, row) for row in rows]
        return {
            "items": items,
            "count": total,
            "page": page,
            "page_size": page_size,
        }

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
            related_cases = conn.execute(
                """
                SELECT id, status, module_id, module_name, ip, verdict, confidence_band, updated_at, username, uuid, system_id, telegram_id
                FROM review_cases
                WHERE id != ? AND (uuid = ? OR ip = ?)
                ORDER BY updated_at DESC
                LIMIT 10
                """,
                (case_id, case_row["uuid"], case_row["ip"]),
            ).fetchall()
            case = self._hydrate_review_list_item(conn, case_row)
            case["latest_event"] = self._decode_analysis_event_payload(event_row)
            case["resolutions"] = [dict(row) for row in resolutions]
            case["related_cases"] = [self._hydrate_review_list_item(conn, row) for row in related_cases]
            return case

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
