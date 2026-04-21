from __future__ import annotations

import base64
import copy
import csv
import io
import json
import zipfile
from datetime import datetime
from typing import Any

from fastapi import HTTPException

from ..context import APIContainer
from .runtime_state import coerce_optional_int


def _parse_export_date(value: str, *, end_of_day: bool) -> str:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid date format {value!r}, expected YYYY-MM-DD") from exc
    if end_of_day:
        parsed = parsed.replace(hour=23, minute=59, second=59)
    return parsed.replace(microsecond=0).isoformat()


def _safe_json_loads(raw: Any, fallback: Any) -> Any:
    if raw in (None, ""):
        return fallback
    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return fallback


def _latest_resolution_join_sql(store: Any, conn: Any) -> str:
    if not store._table_exists(conn, "review_resolutions"):
        return "NULL AS final_resolution, NULL AS resolution_note, NULL AS resolution_created_at"
    return """
        (
            SELECT rr.resolution
            FROM review_resolutions rr
            WHERE rr.case_id = rc.id
            ORDER BY rr.created_at DESC, rr.id DESC
            LIMIT 1
        ) AS final_resolution,
        (
            SELECT rr.note
            FROM review_resolutions rr
            WHERE rr.case_id = rc.id
            ORDER BY rr.created_at DESC, rr.id DESC
            LIMIT 1
        ) AS resolution_note,
        (
            SELECT rr.created_at
            FROM review_resolutions rr
            WHERE rr.case_id = rc.id
            ORDER BY rr.created_at DESC, rr.id DESC
            LIMIT 1
            ) AS resolution_created_at
    """


def _ground_truth_for_resolution(final_resolution: str | None) -> str:
    if final_resolution in {"HOME", "MOBILE"}:
        return final_resolution
    if final_resolution == "SKIP":
        return "unknown"
    return "pending"


def _normalize_provider_evidence(provider_evidence: dict[str, Any]) -> dict[str, Any]:
    evidence = dict(provider_evidence or {})
    return {
        "provider_key": evidence.get("provider_key"),
        "provider_classification": evidence.get("provider_classification", "unknown"),
        "service_type_hint": evidence.get("service_type_hint", "unknown"),
        "service_conflict": bool(evidence.get("service_conflict", False)),
        "review_recommended": bool(evidence.get("review_recommended", False)),
        "matched_aliases": list(evidence.get("matched_aliases", [])),
        "provider_mobile_markers": list(evidence.get("provider_mobile_markers", evidence.get("mobile_markers", []))),
        "provider_home_markers": list(evidence.get("provider_home_markers", evidence.get("home_markers", []))),
    }


def _has_provider_evidence(provider_evidence: dict[str, Any]) -> bool:
    return bool(
        provider_evidence.get("provider_key")
        or provider_evidence.get("matched_aliases")
        or provider_evidence.get("provider_mobile_markers")
        or provider_evidence.get("provider_home_markers")
        or provider_evidence.get("service_type_hint") not in (None, "", "unknown")
    )


def _reconstruct_provider_evidence(
    provider_evidence: dict[str, Any],
    *,
    reasons: list[dict[str, Any]],
    rules_snapshot: dict[str, Any],
    isp: Any,
    asn: Any,
) -> tuple[dict[str, Any], bool]:
    if provider_evidence and provider_evidence.get("provider_key"):
        return _normalize_provider_evidence(provider_evidence), False

    reconstructed: dict[str, Any] = {}
    for reason in reasons:
        if not isinstance(reason, dict):
            continue
        metadata = reason.get("metadata") if isinstance(reason.get("metadata"), dict) else {}
        if metadata.get("provider_key"):
            reconstructed["provider_key"] = str(metadata.get("provider_key"))
            reconstructed["provider_classification"] = str(metadata.get("provider_classification") or "unknown")
            reconstructed["service_type_hint"] = str(metadata.get("service_type_hint") or "unknown")
            reconstructed["matched_aliases"] = list(metadata.get("matched_aliases") or [])
            reconstructed["provider_mobile_markers"] = list(metadata.get("mobile_markers") or [])
            reconstructed["provider_home_markers"] = list(metadata.get("home_markers") or [])
            reconstructed["service_conflict"] = reconstructed.get("service_type_hint") == "conflict"
            reconstructed["review_recommended"] = bool(reason.get("code") == "provider_review_guardrail")
            return _normalize_provider_evidence(reconstructed), True

    return _normalize_provider_evidence(provider_evidence), False


def _explainability_snapshot(reasons: list[dict[str, Any]], provider_evidence: dict[str, Any]) -> dict[str, Any]:
    home_sources = sorted(
        {
            str(reason.get("source") or "")
            for reason in reasons
            if str(reason.get("direction") or "").upper() == "HOME" and int(reason.get("weight") or 0) < 0
        }
    )
    mobile_sources = sorted(
        {
            str(reason.get("source") or "")
            for reason in reasons
            if str(reason.get("direction") or "").upper() == "MOBILE" and int(reason.get("weight") or 0) > 0
        }
    )
    service_type_hint = str(provider_evidence.get("service_type_hint") or "").lower()
    supporting_sources = set(home_sources if service_type_hint == "home" else mobile_sources if service_type_hint == "mobile" else [])
    supporting_sources.discard("provider_profile")
    supporting_sources.discard("generic_keyword")
    return {
        "home_sources": home_sources,
        "mobile_sources": mobile_sources,
        "provider_signal_only": service_type_hint in {"home", "mobile"} and not supporting_sources,
        "review_recommended": bool(provider_evidence.get("review_recommended")),
    }


def _reason_pattern(reason: dict[str, Any]) -> str:
    metadata = reason.get("metadata") if isinstance(reason.get("metadata"), dict) else {}
    if metadata.get("pattern_value"):
        return str(metadata["pattern_value"])
    if metadata.get("combo_key"):
        return str(metadata["combo_key"])
    if metadata.get("provider_key") and metadata.get("service_type_hint") in {"home", "mobile", "conflict"}:
        return f"{metadata['provider_key']}:{metadata['service_type_hint']}"
    if metadata.get("provider_key"):
        return str(metadata["provider_key"])
    if metadata.get("asn") is not None:
        return f"asn:{metadata['asn']}"
    keywords = metadata.get("keywords")
    if isinstance(keywords, list) and keywords:
        return "|".join(sorted(str(item) for item in keywords))
    return ""


def _csv_string(fieldnames: list[str], rows: list[dict[str, Any]]) -> str:
    stream = io.StringIO()
    writer = csv.DictWriter(stream, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in fieldnames})
    return stream.getvalue()


def _build_export_rules_snapshot(container: APIContainer) -> tuple[dict[str, Any], list[str], str]:
    warnings: list[str] = []
    live_rules_state = container.store.get_live_rules_state()
    snapshot_source = "live_rules"
    snapshot = copy.deepcopy(live_rules_state)
    runtime_rules = None
    if getattr(container, "runtime", None) is not None:
        runtime_rules = copy.deepcopy(container.runtime.reload_config())
    if runtime_rules is not None:
        live_profiles = live_rules_state["rules"].get("provider_profiles", [])
        runtime_profiles = runtime_rules.get("provider_profiles", [])
        if (not live_profiles) and runtime_profiles:
            snapshot["rules"]["provider_profiles"] = copy.deepcopy(runtime_profiles)
            snapshot["rules"].setdefault("settings", {}).update(
                {
                    key: value
                    for key, value in runtime_rules.get("settings", {}).items()
                    if key in {"provider_mobile_marker_bonus", "provider_home_marker_penalty", "provider_conflict_review_only"}
                }
            )
            snapshot_source = "runtime_merged"
            warnings.append("live_rules_stale_or_unseeded")
    return snapshot, warnings, snapshot_source


def _build_calibration_rows(container: APIContainer, filters: dict[str, Any]) -> list[dict[str, Any]]:
    rules_snapshot_state, snapshot_warnings, _ = _build_export_rules_snapshot(container)
    rules_snapshot = rules_snapshot_state.get("rules", {})
    store = container.store
    status = str(filters.get("status") or "resolved_only").lower()
    if status not in {"resolved_only", "open_only", "all"}:
        raise HTTPException(status_code=400, detail="status must be resolved_only, open_only or all")
    clauses: list[str] = []
    params: list[Any] = []
    if filters.get("opened_from"):
        clauses.append("rc.opened_at >= ?")
        params.append(_parse_export_date(str(filters["opened_from"]), end_of_day=False))
    if filters.get("opened_to"):
        clauses.append("rc.opened_at <= ?")
        params.append(_parse_export_date(str(filters["opened_to"]), end_of_day=True))
    if filters.get("review_reason"):
        clauses.append("rc.review_reason = ?")
        params.append(str(filters["review_reason"]))
    if status == "resolved_only":
        clauses.append("rc.status IN ('RESOLVED', 'SKIPPED')")
    elif status == "open_only":
        clauses.append("rc.status = 'OPEN'")

    with store._connect() as conn:
        if not store._table_exists(conn, "review_cases") or not store._table_exists(conn, "analysis_events"):
            return []
        query = [
            f"""
            SELECT
                rc.id AS case_id,
                rc.status,
                rc.review_reason,
                rc.opened_at,
                rc.updated_at,
                rc.score AS case_score,
                rc.verdict AS case_verdict,
                rc.confidence_band AS case_confidence_band,
                rc.reason_codes_json,
                rc.latest_event_id,
                ae.bundle_json,
                ae.reasons_json,
                ae.signal_flags_json,
                ae.score AS event_score,
                ae.isp,
                ae.asn,
                {_latest_resolution_join_sql(store, conn)}
            FROM review_cases rc
            JOIN analysis_events ae ON ae.id = rc.latest_event_id
            """
        ]
        if clauses:
            query.append("WHERE " + " AND ".join(clauses))
        query.append("ORDER BY rc.updated_at DESC")
        sql = " ".join(query)
        base_rows = [dict(row) for row in conn.execute(sql, params).fetchall()]
        case_ids = [int(row["case_id"]) for row in base_rows]
        labels_map: dict[int, list[dict[str, Any]]] = {}
        if case_ids and store._table_exists(conn, "review_labels"):
            placeholders = ", ".join("?" for _ in case_ids)
            label_rows = conn.execute(
                f"""
                SELECT case_id, pattern_type, pattern_value, decision, created_at
                FROM review_labels
                WHERE case_id IN ({placeholders})
                ORDER BY created_at DESC
                """,
                case_ids,
            ).fetchall()
            for label_row in label_rows:
                payload = dict(label_row)
                labels_map.setdefault(int(payload["case_id"]), []).append(payload)

    provider_key_filter = str(filters.get("provider_key") or "").strip().lower()
    export_rows: list[dict[str, Any]] = []
    for row in base_rows:
        reasons = _safe_json_loads(row.pop("reasons_json", None), [])
        signal_flags = _safe_json_loads(row.pop("signal_flags_json", None), {})
        bundle = _safe_json_loads(row.pop("bundle_json", None), {})
        if isinstance(bundle, dict):
            reasons = bundle.get("reasons", reasons)
            signal_flags = bundle.get("signal_flags", signal_flags)
        provider_evidence = signal_flags.get("provider_evidence") if isinstance(signal_flags, dict) else {}
        if not isinstance(provider_evidence, dict):
            provider_evidence = {}

        final_resolution = row.get("final_resolution")
        ground_truth = _ground_truth_for_resolution(str(final_resolution) if final_resolution else None)
        provider_evidence, reconstructed = _reconstruct_provider_evidence(
            provider_evidence,
            reasons=reasons if isinstance(reasons, list) else [],
            rules_snapshot=rules_snapshot,
            isp=row.get("isp"),
            asn=row.get("asn"),
        )
        provider_key = str(provider_evidence.get("provider_key") or "").strip().lower()
        if provider_key_filter and provider_key != provider_key_filter:
            continue
        dataset_warning_flags = list(snapshot_warnings)
        if not final_resolution:
            dataset_warning_flags.append("pending_resolution")
        if not provider_evidence.get("provider_key"):
            dataset_warning_flags.append("provider_explainability_missing")
        export_rows.append(
            {
                "case_id": int(row["case_id"]),
                "opened_at": row.get("opened_at"),
                "updated_at": row.get("updated_at"),
                "review_reason": row.get("review_reason"),
                "score": row.get("event_score") if row.get("event_score") is not None else row.get("case_score"),
                "verdict_before_review": row.get("case_verdict"),
                "confidence_band": row.get("case_confidence_band"),
                "final_resolution": final_resolution,
                "ground_truth": ground_truth,
                "asn": row.get("asn"),
                "isp": row.get("isp"),
                "provider_evidence": provider_evidence,
                "provider_evidence_reconstructed": reconstructed,
                "reason_codes": _safe_json_loads(row.get("reason_codes_json"), []),
                "reasons": reasons if isinstance(reasons, list) else [],
                "review_labels": labels_map.get(int(row["case_id"]), []),
                "dataset_warning_flags": sorted(set(dataset_warning_flags)),
                "explainability": _explainability_snapshot(
                    reasons if isinstance(reasons, list) else [],
                    provider_evidence,
                ),
            }
        )
    return export_rows


def _build_provider_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        evidence = row.get("provider_evidence", {})
        provider_key = str(evidence.get("provider_key") or "unknown")
        service_hint = str(evidence.get("service_type_hint") or "unknown")
        key = (provider_key, service_hint)
        bucket = buckets.setdefault(
            key,
            {
                "provider_key": provider_key,
                "service_type_hint": service_hint,
                "raw_total": 0,
                "known_total": 0,
                "home": 0,
                "mobile": 0,
                "unknown": 0,
                "conflicts": 0,
                "conflict_rate": 0.0,
            },
        )
        bucket["raw_total"] += 1
        if row["ground_truth"] == "HOME":
            bucket["known_total"] += 1
            bucket["home"] += 1
        elif row["ground_truth"] == "MOBILE":
            bucket["known_total"] += 1
            bucket["mobile"] += 1
        else:
            bucket["unknown"] += 1
        if evidence.get("service_conflict"):
            bucket["conflicts"] += 1
    for bucket in buckets.values():
        bucket["conflict_rate"] = round(bucket["conflicts"] / bucket["raw_total"], 4) if bucket["raw_total"] else 0.0
    return sorted(buckets.values(), key=lambda item: (-int(item["raw_total"]), item["provider_key"], item["service_type_hint"]))


def _build_feature_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for row in rows:
        if row["ground_truth"] not in {"HOME", "MOBILE"}:
            continue
        for reason in row.get("reasons", []):
            if not isinstance(reason, dict):
                continue
            direction = str(reason.get("direction") or "").upper()
            if direction not in {"HOME", "MOBILE"}:
                continue
            key = (
                str(reason.get("code") or ""),
                str(reason.get("source") or ""),
                _reason_pattern(reason),
            )
            bucket = buckets.setdefault(
                key,
                {
                    "reason_code": key[0],
                    "source": key[1],
                    "pattern": key[2],
                    "support": 0,
                    "total": 0,
                    "precision": 0.0,
                },
            )
            bucket["total"] += 1
            if direction == row["ground_truth"]:
                bucket["support"] += 1
    for bucket in buckets.values():
        bucket["precision"] = round(bucket["support"] / bucket["total"], 4) if bucket["total"] else 0.0
    return sorted(buckets.values(), key=lambda item: (-float(item["precision"]), -int(item["support"]), item["reason_code"]))


def _build_mixed_provider_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        evidence = row.get("provider_evidence", {})
        if str(evidence.get("provider_classification") or "").lower() != "mixed":
            continue
        provider_key = str(evidence.get("provider_key") or "unknown")
        bucket = buckets.setdefault(
            provider_key,
            {
                "provider_key": provider_key,
                "raw_total": 0,
                "conflicts": 0,
                "known_total": 0,
                "correct_service_hint": 0,
                "resolved_precision": 0.0,
            },
        )
        bucket["raw_total"] += 1
        if evidence.get("service_conflict"):
            bucket["conflicts"] += 1
        service_hint = str(evidence.get("service_type_hint") or "").lower()
        if row["ground_truth"] in {"HOME", "MOBILE"} and service_hint in {"home", "mobile"}:
            bucket["known_total"] += 1
            if service_hint == row["ground_truth"].lower():
                bucket["correct_service_hint"] += 1
    for bucket in buckets.values():
        bucket["resolved_precision"] = round(
            bucket["correct_service_hint"] / bucket["known_total"], 4
        ) if bucket["known_total"] else 0.0
    return sorted(buckets.values(), key=lambda item: (-int(item["raw_total"]), -float(item["resolved_precision"]), item["provider_key"]))


def _build_review_reason_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get("review_reason") or "unknown")
        bucket = buckets.setdefault(
            key,
            {
                "review_reason": key,
                "total": 0,
                "home": 0,
                "mobile": 0,
                "unknown": 0,
            },
        )
        bucket["total"] += 1
        if row["ground_truth"] == "HOME":
            bucket["home"] += 1
        elif row["ground_truth"] == "MOBILE":
            bucket["mobile"] += 1
        else:
            bucket["unknown"] += 1
    return sorted(buckets.values(), key=lambda item: (-int(item["total"]), item["review_reason"]))


def _readiness_ratio(current: float, target: float) -> float:
    if target <= 0:
        return 1.0
    return max(0.0, min(float(current) / float(target), 1.0))


def _readiness_check(key: str, scope: str, current: float, target: float) -> dict[str, Any]:
    ratio = _readiness_ratio(current, target)
    return {
        "key": key,
        "scope": scope,
        "current": current,
        "target": target,
        "ratio": round(ratio, 4),
        "percent": int(round(ratio * 100)),
        "ready": ratio >= 1.0,
    }


def _build_calibration_artifacts(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    rules_snapshot, manifest_warnings, snapshot_source = _build_export_rules_snapshot(container)
    rows = _build_calibration_rows(container, filters)
    include_unknown = bool(filters.get("include_unknown", False))
    resolved_rows = [row for row in rows if row["ground_truth"] in {"HOME", "MOBILE", "unknown"}]
    known_rows = [row for row in rows if row["ground_truth"] in {"HOME", "MOBILE"}]
    aggregate_rows = rows if include_unknown else known_rows
    unknown_count = sum(1 for row in rows if row["ground_truth"] == "unknown")
    pending_count = sum(1 for row in rows if row["ground_truth"] == "pending")
    resolved_ratio = round(len(resolved_rows) / len(rows), 4) if rows else 0.0
    pending_ratio = round(pending_count / len(rows), 4) if rows else 0.0
    unknown_ratio = round(unknown_count / len(rows), 4) if rows else 0.0
    resolved_provider_rows = known_rows
    provider_evidence_count = sum(
        1 for row in resolved_provider_rows if _has_provider_evidence(row.get("provider_evidence", {}))
    )
    provider_key_count = sum(
        1 for row in resolved_provider_rows if (row.get("provider_evidence") or {}).get("provider_key")
    )
    provider_evidence_coverage = (
        round(provider_evidence_count / len(resolved_provider_rows), 4) if resolved_provider_rows else 0.0
    )
    provider_key_coverage = (
        round(provider_key_count / len(resolved_provider_rows), 4) if resolved_provider_rows else 0.0
    )
    provider_profiles_count = len(rules_snapshot.get("rules", {}).get("provider_profiles", []))
    provider_support_counts: dict[str, int] = {}
    for row in known_rows:
        evidence = row.get("provider_evidence", {})
        provider_key = str(evidence.get("provider_key") or "").strip().lower()
        service_hint = str(evidence.get("service_type_hint") or "").strip().lower()
        if not provider_key:
            continue
        pattern_key = f"{provider_key}:{service_hint}" if service_hint else provider_key
        provider_support_counts[pattern_key] = provider_support_counts.get(pattern_key, 0) + 1
    min_provider_support = min(provider_support_counts.values()) if provider_support_counts else 0
    warnings = list(manifest_warnings)
    if provider_profiles_count == 0:
        warnings.append("provider_profiles_missing")
    if provider_key_coverage == 0:
        warnings.append("provider_key_coverage_zero")
    if provider_evidence_coverage == 0:
        warnings.append("provider_explainability_missing")
    if resolved_ratio < 0.5:
        warnings.append("resolved_ratio_below_threshold")
    if provider_profiles_count > 0 and provider_key_coverage < 0.6:
        warnings.append("provider_key_coverage_below_target")
    if provider_support_counts and min_provider_support < 5:
        warnings.append("provider_support_below_target")
    dataset_ready = not (
        provider_profiles_count == 0 or provider_key_coverage == 0 or resolved_ratio < 0.5
    )
    tuning_ready = bool(
        provider_profiles_count > 0
        and provider_key_coverage >= 0.6
        and provider_support_counts
        and min_provider_support >= 5
    )
    dataset_checks = [
        _readiness_check(
            "provider_profiles_present",
            "dataset",
            1 if provider_profiles_count > 0 else 0,
            1,
        ),
        _readiness_check("resolved_ratio", "dataset", resolved_ratio, 0.5),
        _readiness_check("provider_evidence_coverage", "dataset", provider_evidence_coverage, 0.6),
        _readiness_check("provider_key_coverage", "dataset", provider_key_coverage, 0.6),
    ]
    tuning_checks = [
        _readiness_check(
            "provider_profiles_present",
            "tuning",
            1 if provider_profiles_count > 0 else 0,
            1,
        ),
        _readiness_check("provider_key_coverage", "tuning", provider_key_coverage, 0.6),
        _readiness_check("min_provider_support", "tuning", min_provider_support, 5),
    ]
    all_checks = dataset_checks + tuning_checks
    dataset_percent = int(round(sum(check["percent"] for check in dataset_checks) / len(dataset_checks))) if dataset_checks else 0
    tuning_percent = int(round(sum(check["percent"] for check in tuning_checks) / len(tuning_checks))) if tuning_checks else 0
    blockers = list(dict.fromkeys(check["key"] for check in all_checks if not check["ready"]))
    manifest = {
        "schema_version": 1,
        "generated_at": datetime.utcnow().replace(microsecond=0).isoformat(),
        "snapshot_source": snapshot_source,
        "dataset_ready": dataset_ready,
        "tuning_ready": tuning_ready,
        "warnings": sorted(set(warnings)),
        "readiness": {
            "overall_percent": min(dataset_percent, tuning_percent),
            "dataset_percent": dataset_percent,
            "tuning_percent": tuning_percent,
            "blockers": blockers,
            "checks": all_checks,
        },
        "filters": {
            "opened_from": filters.get("opened_from"),
            "opened_to": filters.get("opened_to"),
            "review_reason": filters.get("review_reason"),
            "provider_key": filters.get("provider_key"),
            "include_unknown": include_unknown,
            "status": filters.get("status") or "resolved_only",
        },
        "row_counts": {
            "raw_rows": len(rows),
            "resolved_known_rows": len(known_rows),
            "resolved_unknown_rows": unknown_count,
            "open_rows": pending_count,
            "known_rows": len(known_rows),
            "aggregate_rows": len(aggregate_rows),
            "unknown_rows": unknown_count,
            "unknown_ratio": unknown_ratio,
        },
        "coverage": {
            "resolved_ratio": resolved_ratio,
            "pending_ratio": pending_ratio,
            "unknown_ratio": unknown_ratio,
            "provider_evidence_coverage": provider_evidence_coverage,
            "provider_key_coverage": provider_key_coverage,
            "provider_profiles_count": provider_profiles_count,
            "provider_pattern_candidates": len(provider_support_counts),
            "min_provider_support": min_provider_support,
        },
    }
    provider_summary = _build_provider_summary(rows)
    feature_summary = _build_feature_summary(known_rows)
    mixed_provider_summary = _build_mixed_provider_summary(rows)
    review_reason_summary = _build_review_reason_summary(rows)
    return {
        "rules_snapshot": rules_snapshot,
        "rows": rows,
        "known_rows": known_rows,
        "manifest": manifest,
        "provider_summary": provider_summary,
        "feature_summary": feature_summary,
        "mixed_provider_summary": mixed_provider_summary,
        "review_reason_summary": review_reason_summary,
    }


def build_calibration_preview(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    artifacts = _build_calibration_artifacts(container, filters)
    return artifacts["manifest"]


def build_calibration_export(container: APIContainer, filters: dict[str, Any]) -> dict[str, Any]:
    artifacts = _build_calibration_artifacts(container, filters)
    rows = artifacts["rows"]
    manifest = artifacts["manifest"]
    rules_snapshot = artifacts["rules_snapshot"]
    provider_summary = artifacts["provider_summary"]
    feature_summary = artifacts["feature_summary"]
    mixed_provider_summary = artifacts["mixed_provider_summary"]
    review_reason_summary = artifacts["review_reason_summary"]

    archive_buffer = io.BytesIO()
    with io.StringIO() as jsonl_stream:
        for row in rows:
            jsonl_stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        calibration_jsonl = jsonl_stream.getvalue()

    with zipfile.ZipFile(archive_buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        archive.writestr("rules_snapshot.json", json.dumps(rules_snapshot, ensure_ascii=False, indent=2))
        archive.writestr("calibration_rows.jsonl", calibration_jsonl)
        archive.writestr(
            "provider_summary.csv",
            _csv_string(
                ["provider_key", "service_type_hint", "raw_total", "known_total", "home", "mobile", "unknown", "conflicts", "conflict_rate"],
                provider_summary,
            ),
        )
        archive.writestr(
            "feature_summary.csv",
            _csv_string(
                ["reason_code", "source", "pattern", "support", "total", "precision"],
                feature_summary,
            ),
        )
        archive.writestr(
            "mixed_provider_summary.csv",
            _csv_string(
                ["provider_key", "raw_total", "conflicts", "known_total", "correct_service_hint", "resolved_precision"],
                mixed_provider_summary,
            ),
        )
        archive.writestr(
            "review_reason_summary.csv",
            _csv_string(
                ["review_reason", "total", "home", "mobile", "unknown"],
                review_reason_summary,
            ),
        )

    filename = f"mobguard-calibration-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.zip"
    manifest_header = base64.b64encode(json.dumps(manifest, ensure_ascii=False).encode("utf-8")).decode("ascii")
    return {
        "content": archive_buffer.getvalue(),
        "filename": filename,
        "manifest": manifest,
        "manifest_header": manifest_header,
    }
