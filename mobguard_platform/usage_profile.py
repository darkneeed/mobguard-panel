from __future__ import annotations

import html
import math
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from typing import Any, Mapping, Optional


DEFAULT_LOOKBACK_DAYS = 30
DEFAULT_EVENT_LIMIT = 200
GEO_COUNTRY_JUMP_WINDOW_HOURS = 24.0
IMPOSSIBLE_TRAVEL_MIN_DISTANCE_KM = 500.0
IMPOSSIBLE_TRAVEL_MAX_WINDOW_HOURS = 6.0
IMPOSSIBLE_TRAVEL_MIN_SPEED_KMH = 500.0
DEVICE_ROTATION_THRESHOLD = 2
PROVIDER_FANOUT_THRESHOLD = 3
NODE_FANOUT_THRESHOLD = 2
BURST_WINDOW_MINUTES = 30
BURST_EVENT_THRESHOLD = 5
TRAFFIC_BURST_MIN_BYTES = 512 * 1024 * 1024
TRAFFIC_BURST_MIN_POINTS = 2


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _parse_dt(value: Any) -> Optional[datetime]:
    raw = _clean_text(value)
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_float(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_loc(value: Any) -> tuple[Optional[float], Optional[float]]:
    raw = _clean_text(value)
    if not raw or "," not in raw:
        return None, None
    lat_raw, lon_raw = raw.split(",", 1)
    return _parse_float(lat_raw), _parse_float(lon_raw)


def _format_location(country: str, region: str, city: str) -> str:
    parts = [part for part in (country, region, city) if part]
    return ", ".join(parts)


def _format_duration(seconds: Any) -> str:
    if seconds in (None, "", 0):
        return ""
    try:
        total_seconds = max(int(seconds), 0)
    except (TypeError, ValueError):
        return ""
    if total_seconds <= 0:
        return ""
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, _ = divmod(remainder, 60)
    chunks: list[str] = []
    if days:
        chunks.append(f"{days}d")
    if hours:
        chunks.append(f"{hours}h")
    if minutes:
        chunks.append(f"{minutes}m")
    if not chunks:
        chunks.append(f"{total_seconds}s")
    return " ".join(chunks[:3])


def _format_bytes(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return ""
    if size <= 0:
        return ""
    units = ["B", "KB", "MB", "GB", "TB"]
    unit_index = 0
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    return f"{size:.1f} {units[unit_index]}" if unit_index > 0 else f"{int(size)} {units[unit_index]}"


def _haversine_km(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    radius_km = 6371.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = math.sin(delta_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return radius_km * c


def normalize_geo_context(raw: Any) -> dict[str, Any]:
    source = raw if isinstance(raw, Mapping) else {}
    country = _clean_text(source.get("country") or source.get("country_code") or source.get("countryCode"))
    region = _clean_text(source.get("region") or source.get("region_name") or source.get("regionName"))
    city = _clean_text(source.get("city"))
    loc = _clean_text(source.get("loc"))
    latitude = _parse_float(source.get("latitude"))
    longitude = _parse_float(source.get("longitude"))
    if latitude is None or longitude is None:
        latitude, longitude = _parse_loc(loc)
    payload = {
        "country": country,
        "region": region,
        "city": city,
        "loc": loc,
        "latitude": latitude,
        "longitude": longitude,
    }
    return {key: value for key, value in payload.items() if value not in (None, "")}


def normalize_usage_observation(
    payload: Mapping[str, Any] | None = None,
    *,
    signal_flags: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    source = payload or {}
    geo_context = normalize_geo_context((signal_flags or {}).get("geo") if isinstance(signal_flags, Mapping) else {})
    normalized = {
        **geo_context,
        "client_device_id": _clean_text(source.get("client_device_id")),
        "client_device_label": _clean_text(source.get("client_device_label")),
        "client_os_family": _clean_text(source.get("client_os_family")),
        "client_os_version": _clean_text(source.get("client_os_version")),
        "client_app_name": _clean_text(source.get("client_app_name")),
        "client_app_version": _clean_text(source.get("client_app_version")),
    }
    return {key: value for key, value in normalized.items() if value not in (None, "")}


def _identity_lookup(
    identity: Mapping[str, Any] | None,
    *,
    device_scope_key: str | None = None,
    case_scope_key: str | None = None,
) -> tuple[str, list[Any]]:
    if device_scope_key:
        return "device_scope_key = ?", [str(device_scope_key)]
    if case_scope_key:
        return "case_scope_key = ?", [str(case_scope_key)]
    source = identity or {}
    clauses: list[str] = []
    params: list[Any] = []
    if source.get("uuid"):
        clauses.append("uuid = ?")
        params.append(source["uuid"])
    if source.get("system_id") not in (None, ""):
        clauses.append("system_id = ?")
        params.append(int(source["system_id"]))
    if source.get("telegram_id") not in (None, ""):
        clauses.append("telegram_id = ?")
        params.append(str(source["telegram_id"]))
    if source.get("username"):
        clauses.append("username = ?")
        params.append(source["username"])
    return " OR ".join(clauses), params


def _store_connect(store: Any):
    if hasattr(store, "_connect"):
        return store._connect()
    if hasattr(store, "connect"):
        return store.connect()
    raise AttributeError("Store-like object does not expose a connect method")


def _store_table_exists(store: Any, conn: Any, table_name: str) -> bool:
    if hasattr(store, "_table_exists"):
        return bool(store._table_exists(conn, table_name))
    if hasattr(store, "table_exists"):
        return bool(store.table_exists(conn, table_name))
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
        (table_name,),
    ).fetchone()
    return row is not None


def _table_columns(conn: Any, table_name: str) -> set[str]:
    return {row["name"] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}


def _analysis_event_select(conn: Any, store: Any) -> str:
    if not _store_table_exists(store, conn, "analysis_events"):
        return ""
    columns = _table_columns(conn, "analysis_events")
    fields = [
        "created_at",
        "module_id" if "module_id" in columns else "NULL AS module_id",
        "module_name" if "module_name" in columns else "NULL AS module_name",
        "ip",
        "isp" if "isp" in columns else "NULL AS isp",
        "asn" if "asn" in columns else "NULL AS asn",
        "country" if "country" in columns else "NULL AS country",
        "region" if "region" in columns else "NULL AS region",
        "city" if "city" in columns else "NULL AS city",
        "loc" if "loc" in columns else "NULL AS loc",
        "latitude" if "latitude" in columns else "NULL AS latitude",
        "longitude" if "longitude" in columns else "NULL AS longitude",
        "client_device_id" if "client_device_id" in columns else "NULL AS client_device_id",
        "client_device_label" if "client_device_label" in columns else "NULL AS client_device_label",
        "client_os_family" if "client_os_family" in columns else "NULL AS client_os_family",
        "client_os_version" if "client_os_version" in columns else "NULL AS client_os_version",
        "client_app_name" if "client_app_name" in columns else "NULL AS client_app_name",
        "client_app_version" if "client_app_version" in columns else "NULL AS client_app_version",
    ]
    return ", ".join(fields)


def _review_case_select(conn: Any, store: Any) -> str:
    if not _store_table_exists(store, conn, "review_cases"):
        return ""
    columns = _table_columns(conn, "review_cases")
    fields = [
        "status",
        "review_reason",
        "opened_at" if "opened_at" in columns else "NULL AS opened_at",
        "updated_at" if "updated_at" in columns else "NULL AS updated_at",
    ]
    return ", ".join(fields)


def _event_device_entry(row: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    device_id = _clean_text(row.get("client_device_id"))
    label = _clean_text(row.get("client_device_label"))
    os_family = _clean_text(row.get("client_os_family"))
    os_version = _clean_text(row.get("client_os_version"))
    app_name = _clean_text(row.get("client_app_name"))
    app_version = _clean_text(row.get("client_app_version"))
    if not any((device_id, label, os_family, os_version, app_name, app_version)):
        return None
    return {
        "device_id": device_id,
        "label": label,
        "os_family": os_family,
        "os_version": os_version,
        "app_name": app_name,
        "app_version": app_version,
        "source": "event",
    }


def _looks_like_device_list(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    sample = value[0]
    if not isinstance(sample, Mapping):
        return False
    keys = {str(key) for key in sample.keys()}
    expected = {
        "hwid",
        "platform",
        "osVersion",
        "os_version",
        "deviceModel",
        "device_model",
        "appVersion",
        "app_version",
        "userAgent",
        "user_agent",
    }
    return bool(keys & expected)


def _collect_device_lists(payload: Any, *, depth: int = 0) -> list[list[Mapping[str, Any]]]:
    if depth > 2:
        return []
    found: list[list[Mapping[str, Any]]] = []
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            normalized_key = str(key).replace("-", "_").replace(" ", "_").lower()
            if _looks_like_device_list(value) and (
                "device" in normalized_key or "client" in normalized_key or "hwid" in normalized_key
            ):
                found.append([item for item in value if isinstance(item, Mapping)])
            elif isinstance(value, (Mapping, list)):
                found.extend(_collect_device_lists(value, depth=depth + 1))
    elif isinstance(payload, list):
        for item in payload:
            found.extend(_collect_device_lists(item, depth=depth + 1))
    return found


def _panel_device_entry(device: Mapping[str, Any]) -> Optional[dict[str, Any]]:
    device_id = _clean_text(device.get("hwid") or device.get("deviceId") or device.get("clientDeviceId"))
    label = _clean_text(device.get("deviceModel") or device.get("device_model") or device.get("label") or device.get("name"))
    os_family = _clean_text(device.get("platform") or device.get("osFamily") or device.get("os_family"))
    os_version = _clean_text(device.get("osVersion") or device.get("os_version"))
    app_name = _clean_text(device.get("appName") or device.get("app_name") or device.get("client"))
    app_version = _clean_text(device.get("appVersion") or device.get("app_version"))
    if not any((device_id, label, os_family, os_version, app_name, app_version)):
        return None
    return {
        "device_id": device_id,
        "label": label,
        "os_family": os_family,
        "os_version": os_version,
        "app_name": app_name,
        "app_version": app_version,
        "source": "panel_user",
    }


def _extract_panel_devices(panel_user: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(panel_user, Mapping):
        return []
    devices: list[dict[str, Any]] = []
    for candidate_list in _collect_device_lists(panel_user):
        for raw_device in candidate_list:
            normalized = _panel_device_entry(raw_device)
            if normalized:
                devices.append(normalized)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for device in devices:
        marker = (
            _clean_text(device.get("device_id")).lower(),
            _clean_text(device.get("label")).lower(),
            _clean_text(device.get("os_family")).lower(),
            _clean_text(device.get("app_name")).lower(),
        )
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(device)
    return deduped


def _device_key(device: Mapping[str, Any]) -> str:
    for candidate in (
        _clean_text(device.get("device_id")),
        _clean_text(device.get("label")),
        "|".join(
            part
            for part in (
                _clean_text(device.get("os_family")),
                _clean_text(device.get("os_version")),
                _clean_text(device.get("app_name")),
                _clean_text(device.get("app_version")),
            )
            if part
        ),
    ):
        if candidate:
            return candidate.lower()
    return ""


def _summarize_top_entities(counter: Counter[str], meta: dict[str, dict[str, Any]], key_name: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for name, count in counter.most_common(5):
        payload = {key_name: name, "count": count}
        payload.update(meta.get(name, {}))
        items.append(payload)
    return items


def _traffic_stats_payload(panel_user: Mapping[str, Any] | None) -> Optional[dict[str, Any]]:
    if not isinstance(panel_user, Mapping):
        return None
    for key in ("usageProfileTrafficStats", "trafficStats"):
        payload = panel_user.get(key)
        if isinstance(payload, Mapping):
            return dict(payload)
    return None


def _traffic_series_burst(payload: Mapping[str, Any] | None) -> Optional[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return None
    raw_series = payload.get("series")
    if not isinstance(raw_series, list) or not raw_series:
        return None

    points: list[tuple[datetime, int]] = []
    for entry in raw_series:
        if not isinstance(entry, Mapping):
            continue
        timestamp = _parse_dt(entry.get("timestamp") or entry.get("date"))
        if timestamp is None:
            continue
        total_value = None
        if entry.get("total") not in (None, ""):
            try:
                total_value = int(float(entry.get("total") or 0))
            except (TypeError, ValueError):
                total_value = None
        if total_value is None and entry.get("value") not in (None, ""):
            try:
                total_value = int(float(entry.get("value") or 0))
            except (TypeError, ValueError):
                total_value = None
        if total_value is None:
            total_value = 0
            for key, value in entry.items():
                if key in {"date", "timestamp", "total", "value"}:
                    continue
                try:
                    total_value += int(float(value))
                except (TypeError, ValueError):
                    continue
        if total_value > 0:
            points.append((timestamp, total_value))

    if len(points) < TRAFFIC_BURST_MIN_POINTS:
        return None

    points.sort(key=lambda item: item[0])
    left = 0
    current_sum = 0
    best = {
        "bytes": 0,
        "start": points[0][0],
        "end": points[0][0],
        "point_count": 0,
        "peak_bytes": 0,
    }

    for right, (current_ts, current_bytes) in enumerate(points):
        current_sum += current_bytes
        while left < right and (current_ts - points[left][0]).total_seconds() > BURST_WINDOW_MINUTES * 60:
            current_sum -= points[left][1]
            left += 1
        point_count = right - left + 1
        if current_sum > best["bytes"]:
            best = {
                "bytes": current_sum,
                "start": points[left][0],
                "end": current_ts,
                "point_count": point_count,
                "peak_bytes": max(bytes_value for _, bytes_value in points[left : right + 1]),
            }

    if best["bytes"] < TRAFFIC_BURST_MIN_BYTES or best["point_count"] < TRAFFIC_BURST_MIN_POINTS:
        return None

    return {
        "source": "traffic_bytes",
        "bytes": int(best["bytes"]),
        "bytes_text": _format_bytes(best["bytes"]),
        "window_minutes": BURST_WINDOW_MINUTES,
        "started_at": best["start"].replace(microsecond=0).isoformat(),
        "ended_at": best["end"].replace(microsecond=0).isoformat(),
        "point_count": int(best["point_count"]),
        "peak_bytes": int(best["peak_bytes"]),
        "peak_bytes_text": _format_bytes(best["peak_bytes"]),
    }


def _escaped_join(values: list[str], *, limit: int = 5) -> str:
    cleaned = [html.escape(_clean_text(value)) for value in values if _clean_text(value)]
    return ", ".join(cleaned[:limit])


def _escaped_top_lines(
    items: list[Mapping[str, Any]],
    *,
    key_name: str,
    value_name: str = "count",
    limit: int = 5,
) -> str:
    parts: list[str] = []
    for item in items[:limit]:
        key = html.escape(_clean_text(item.get(key_name)))
        value = _clean_text(item.get(value_name))
        country = html.escape(_clean_text(item.get("country")))
        provider = html.escape(_clean_text(item.get("provider")))
        suffix_parts = [part for part in (provider, country) if part]
        suffix = f" [{' / '.join(suffix_parts)}]" if suffix_parts else ""
        if key:
            parts.append(f"{key} ({value or '0'}){suffix}")
    return ", ".join(parts)


def build_usage_profile_priority(
    snapshot: Mapping[str, Any] | None,
    *,
    punitive_eligible: bool,
    confidence_band: str,
    repeat_count: int,
) -> dict[str, int]:
    profile = snapshot if isinstance(snapshot, Mapping) else {}
    travel_flags = profile.get("travel_flags") if isinstance(profile.get("travel_flags"), Mapping) else {}
    signal_count = int(profile.get("summary_score") or len(profile.get("soft_reasons") or []))
    ongoing_seconds = int(profile.get("ongoing_duration_seconds") or 0)
    ongoing_hours = ongoing_seconds // 3600 if ongoing_seconds > 0 else 0

    if punitive_eligible:
        base = 1000
    elif str(confidence_band or "").upper() == "HIGH_HOME":
        base = 700
    elif str(confidence_band or "").upper() == "PROBABLE_HOME":
        base = 450
    else:
        base = 200

    score = base
    score += min(max(int(repeat_count or 0), 0), 10) * 25
    score += min(max(signal_count, 0), 10) * 60
    score += min(max(ongoing_hours, 0), 72) * 2
    score += min(max(int(profile.get("node_count") or 0), 0), 5) * 20
    score += min(max(int(profile.get("provider_count") or 0), 0), 5) * 15
    score += min(max(int(profile.get("device_count") or 0), 0), 5) * 10
    if bool(travel_flags.get("geo_impossible_travel")):
        score += 160
    elif bool(travel_flags.get("geo_country_jump")):
        score += 70

    return {
        "priority": score,
        "signal_count": signal_count,
    }


def build_usage_profile_admin_lines(
    snapshot: Mapping[str, Any] | None,
    *,
    scenario: str = "",
) -> list[str]:
    profile = snapshot if isinstance(snapshot, Mapping) else {}
    if not bool(profile.get("available")):
        return []

    lines: list[str] = ["<b>Usage snapshot:</b>"]
    if scenario:
        lines.append(f"  • <b>Scenario:</b> {html.escape(_clean_text(scenario))}")
    summary = _clean_text(profile.get("usage_profile_summary"))
    if summary:
        lines.append(f"  • <b>Summary:</b> {html.escape(summary)}")
    top_ips = profile.get("top_ips") if isinstance(profile.get("top_ips"), list) else []
    if top_ips:
        lines.append(f"  • <b>IPs:</b> {_escaped_top_lines(top_ips, key_name='ip')}")
    top_providers = profile.get("top_providers") if isinstance(profile.get("top_providers"), list) else []
    if top_providers:
        lines.append(f"  • <b>Providers:</b> {_escaped_top_lines(top_providers, key_name='provider')}")
    nodes = profile.get("nodes") if isinstance(profile.get("nodes"), list) else []
    if nodes:
        lines.append(f"  • <b>Nodes:</b> {_escaped_join(nodes)}")
    device_labels = profile.get("device_labels") if isinstance(profile.get("device_labels"), list) else []
    os_families = profile.get("os_families") if isinstance(profile.get("os_families"), list) else []
    if device_labels or os_families:
        device_text = _escaped_join(device_labels)
        os_text = _escaped_join(os_families)
        combined = " / ".join(part for part in (device_text, os_text) if part)
        if combined:
            lines.append(f"  • <b>Devices:</b> {combined}")
    geo_summary = profile.get("geo_summary") if isinstance(profile.get("geo_summary"), Mapping) else {}
    countries = geo_summary.get("countries") if isinstance(geo_summary.get("countries"), list) else []
    if countries:
        lines.append(f"  • <b>Geo:</b> {html.escape(_escaped_join(countries))}")
    travel_flags = profile.get("travel_flags") if isinstance(profile.get("travel_flags"), Mapping) else {}
    impossible = travel_flags.get("impossible_travel") if isinstance(travel_flags.get("impossible_travel"), list) else []
    if impossible:
        first = impossible[0]
        path = " → ".join(
            html.escape(_clean_text(value))
            for value in (first.get("from_location"), first.get("to_location"))
            if _clean_text(value)
        )
        if path:
            lines.append(f"  • <b>Travel:</b> {path}")
    elif bool(travel_flags.get("geo_country_jump")):
        lines.append("  • <b>Travel:</b> country jump")
    burst = profile.get("traffic_burst") if isinstance(profile.get("traffic_burst"), Mapping) else {}
    if burst:
        bytes_text = _clean_text(burst.get("bytes_text"))
        event_count = _clean_text(burst.get("event_count"))
        window_minutes = _clean_text(burst.get("window_minutes"))
        if bytes_text and window_minutes:
            lines.append(f"  • <b>Traffic burst:</b> {html.escape(bytes_text)} / {window_minutes}m")
        elif event_count and window_minutes:
            lines.append(f"  • <b>Activity burst:</b> {event_count} events / {window_minutes}m")
    ongoing = _clean_text(profile.get("ongoing_duration_text"))
    if ongoing:
        lines.append(f"  • <b>Ongoing:</b> {html.escape(ongoing)}")
    return lines


def build_usage_profile_snapshot(
    store: Any,
    identity: Mapping[str, Any] | None,
    *,
    panel_user: Mapping[str, Any] | None = None,
    anchor_started_at: str | None = None,
    event_limit: int = DEFAULT_EVENT_LIMIT,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    device_scope_key: str | None = None,
    case_scope_key: str | None = None,
) -> dict[str, Any]:
    lookup_clause, lookup_params = _identity_lookup(
        identity,
        device_scope_key=device_scope_key,
        case_scope_key=case_scope_key,
    )
    if not lookup_clause:
        return {
            "available": False,
            "usage_profile_summary": "",
            "soft_reasons": [],
        }

    cutoff = (datetime.utcnow() - timedelta(days=max(int(lookback_days), 1))).replace(microsecond=0).isoformat()
    observations: list[dict[str, Any]] = []
    open_cases: list[dict[str, Any]] = []
    traffic_stats_payload = _traffic_stats_payload(panel_user)

    with _store_connect(store) as conn:
        analysis_select = _analysis_event_select(conn, store)
        if analysis_select:
            rows = conn.execute(
                f"""
                SELECT {analysis_select}
                FROM analysis_events
                WHERE ({lookup_clause}) AND created_at >= ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                [*lookup_params, cutoff, max(int(event_limit), 1)],
            ).fetchall()
            for raw_row in rows:
                row = dict(raw_row)
                occurred_at = _parse_dt(row.get("created_at"))
                if occurred_at is None:
                    continue
                latitude = _parse_float(row.get("latitude"))
                longitude = _parse_float(row.get("longitude"))
                if latitude is None or longitude is None:
                    latitude, longitude = _parse_loc(row.get("loc"))
                observations.append(
                    {
                        "created_at": occurred_at,
                        "created_at_text": _clean_text(row.get("created_at")),
                        "module_id": _clean_text(row.get("module_id")),
                        "module_name": _clean_text(row.get("module_name")),
                        "ip": _clean_text(row.get("ip")),
                        "provider": _clean_text(row.get("isp")),
                        "asn": row.get("asn"),
                        "country": _clean_text(row.get("country")),
                        "region": _clean_text(row.get("region")),
                        "city": _clean_text(row.get("city")),
                        "loc": _clean_text(row.get("loc")),
                        "latitude": latitude,
                        "longitude": longitude,
                        "device": _event_device_entry(row),
                    }
                )

        review_select = _review_case_select(conn, store)
        if review_select:
            case_rows = conn.execute(
                f"""
                SELECT {review_select}
                FROM review_cases
                WHERE ({lookup_clause}) AND status = 'OPEN'
                ORDER BY opened_at ASC
                LIMIT 50
                """,
                lookup_params,
            ).fetchall()
            open_cases = [dict(row) for row in case_rows]

    observations.sort(key=lambda item: item["created_at"])
    panel_devices = _extract_panel_devices(panel_user)
    event_devices = [item["device"] for item in observations if item.get("device")]
    device_map: dict[str, dict[str, Any]] = {}
    for device in [*event_devices, *panel_devices]:
        key = _device_key(device)
        if not key:
            continue
        if key not in device_map:
            device_map[key] = dict(device)
            continue
        current = device_map[key]
        for field in ("device_id", "label", "os_family", "os_version", "app_name", "app_version"):
            if not current.get(field) and device.get(field):
                current[field] = device[field]

    device_groups: dict[str, set[str]] = defaultdict(set)
    for device in event_devices:
        key = _device_key(device)
        os_family = _clean_text(device.get("os_family"))
        if key and os_family:
            device_groups[key].add(os_family)

    device_labels = [
        device.get("label") or device.get("os_family") or device.get("device_id")
        for device in device_map.values()
        if device.get("label") or device.get("os_family") or device.get("device_id")
    ]
    os_families = sorted(
        {
            _clean_text(device.get("os_family"))
            for device in device_map.values()
            if _clean_text(device.get("os_family"))
        }
    )
    node_names = sorted(
        {
            item["module_name"] or item["module_id"]
            for item in observations
            if item["module_name"] or item["module_id"]
        }
    )

    provider_counter: Counter[str] = Counter()
    provider_meta: dict[str, dict[str, Any]] = {}
    ip_counter: Counter[str] = Counter()
    ip_meta: dict[str, dict[str, Any]] = {}
    countries: list[str] = []
    geo_observations: list[dict[str, Any]] = []

    for item in observations:
        provider = item["provider"] or (f"AS{item['asn']}" if item.get("asn") not in (None, "") else "")
        if provider:
            provider_counter[provider] += 1
            provider_meta.setdefault(
                provider,
                {
                    "asn": item.get("asn"),
                    "last_seen": item["created_at_text"],
                },
            )
            provider_meta[provider]["last_seen"] = item["created_at_text"]
        if item["ip"]:
            ip_counter[item["ip"]] += 1
            ip_meta.setdefault(
                item["ip"],
                {
                    "country": item["country"],
                    "provider": provider,
                    "last_seen": item["created_at_text"],
                },
            )
            ip_meta[item["ip"]]["last_seen"] = item["created_at_text"]
        if item["country"]:
            countries.append(item["country"])
        if any((item["country"], item["region"], item["city"], item["latitude"], item["longitude"])):
            geo_observations.append(item)

    country_counter = Counter(countries)
    top_ips = _summarize_top_entities(ip_counter, ip_meta, "ip")
    top_providers = _summarize_top_entities(provider_counter, provider_meta, "provider")

    country_jumps: list[dict[str, Any]] = []
    impossible_travel: list[dict[str, Any]] = []
    last_geo = None
    for item in geo_observations:
        if last_geo is not None:
            delta_hours = (item["created_at"] - last_geo["created_at"]).total_seconds() / 3600.0
            if (
                item["country"]
                and last_geo["country"]
                and item["country"] != last_geo["country"]
                and delta_hours <= GEO_COUNTRY_JUMP_WINDOW_HOURS
            ):
                country_jumps.append(
                    {
                        "from_country": last_geo["country"],
                        "to_country": item["country"],
                        "from_time": last_geo["created_at_text"],
                        "to_time": item["created_at_text"],
                        "hours": round(max(delta_hours, 0.0), 2),
                    }
                )
            if (
                last_geo.get("latitude") is not None
                and last_geo.get("longitude") is not None
                and item.get("latitude") is not None
                and item.get("longitude") is not None
                and delta_hours > 0
            ):
                distance_km = _haversine_km(
                    float(last_geo["latitude"]),
                    float(last_geo["longitude"]),
                    float(item["latitude"]),
                    float(item["longitude"]),
                )
                speed_kmh = distance_km / delta_hours if delta_hours > 0 else 0.0
                if (
                    distance_km >= IMPOSSIBLE_TRAVEL_MIN_DISTANCE_KM
                    and delta_hours <= IMPOSSIBLE_TRAVEL_MAX_WINDOW_HOURS
                    and speed_kmh >= IMPOSSIBLE_TRAVEL_MIN_SPEED_KMH
                ):
                    impossible_travel.append(
                        {
                            "from_location": _format_location(
                                last_geo["country"],
                                last_geo["region"],
                                last_geo["city"],
                            ),
                            "to_location": _format_location(item["country"], item["region"], item["city"]),
                            "from_time": last_geo["created_at_text"],
                            "to_time": item["created_at_text"],
                            "distance_km": round(distance_km, 1),
                            "hours": round(delta_hours, 2),
                            "speed_kmh": round(speed_kmh, 1),
                        }
                    )
        last_geo = item

    burst = _traffic_series_burst(traffic_stats_payload)
    if burst is None and observations:
        left = 0
        timestamps = [item["created_at"] for item in observations]
        best_window = {"count": 0, "start": timestamps[0], "end": timestamps[0]}
        for right, current in enumerate(timestamps):
            while left < right and (current - timestamps[left]).total_seconds() > BURST_WINDOW_MINUTES * 60:
                left += 1
            count = right - left + 1
            if count > best_window["count"]:
                best_window = {
                    "count": count,
                    "start": timestamps[left],
                    "end": current,
                }
        if best_window["count"] >= BURST_EVENT_THRESHOLD:
            burst = {
                "source": "event_count",
                "event_count": int(best_window["count"]),
                "window_minutes": BURST_WINDOW_MINUTES,
                "started_at": best_window["start"].replace(microsecond=0).isoformat(),
                "ended_at": best_window["end"].replace(microsecond=0).isoformat(),
            }

    soft_reasons: list[str] = []
    if country_jumps:
        soft_reasons.append("geo_country_jump")
    if impossible_travel:
        soft_reasons.append("geo_impossible_travel")
    if len(device_map) >= DEVICE_ROTATION_THRESHOLD:
        soft_reasons.append("device_rotation")
    if any(len(os_values) > 1 for os_values in device_groups.values()):
        soft_reasons.append("device_os_mismatch")
    if len(node_names) >= NODE_FANOUT_THRESHOLD:
        soft_reasons.append("cross_node_fanout")
    if len(provider_counter) >= PROVIDER_FANOUT_THRESHOLD:
        soft_reasons.append("provider_fanout")
    if burst:
        soft_reasons.append("traffic_burst")

    last_seen_text = observations[-1]["created_at_text"] if observations else ""
    last_seen_dt = observations[-1]["created_at"] if observations else None

    anchor_dt = _parse_dt(anchor_started_at)
    if anchor_dt is None and open_cases:
        opened_candidates = [
            parsed
            for parsed in (_parse_dt(item.get("opened_at")) for item in open_cases)
            if parsed is not None
        ]
        if opened_candidates:
            anchor_dt = min(opened_candidates)
    if anchor_dt is None and soft_reasons and observations:
        anchor_dt = observations[0]["created_at"]

    ongoing_duration_seconds = None
    if anchor_dt is not None and last_seen_dt is not None and last_seen_dt >= anchor_dt:
        ongoing_duration_seconds = int((last_seen_dt - anchor_dt).total_seconds())

    updated_candidates = [
        parsed
        for parsed in (_parse_dt(item.get("updated_at")) for item in open_cases)
        if parsed is not None
    ]
    if last_seen_dt is not None:
        updated_candidates.append(last_seen_dt)
    updated_at_text = max(updated_candidates).replace(microsecond=0).isoformat() if updated_candidates else ""

    geo_summary = {
        "country_count": len(country_counter),
        "countries": [country for country, _ in country_counter.most_common(5)],
        "recent_locations": [
            {
                "country": item["country"],
                "region": item["region"],
                "city": item["city"],
                "ip": item["ip"],
                "timestamp": item["created_at_text"],
            }
            for item in reversed(geo_observations[-5:])
        ],
        "last_location": (
            {
                "country": geo_observations[-1]["country"],
                "region": geo_observations[-1]["region"],
                "city": geo_observations[-1]["city"],
                "loc": geo_observations[-1]["loc"],
                "timestamp": geo_observations[-1]["created_at_text"],
                "ip": geo_observations[-1]["ip"],
            }
            if geo_observations
            else None
        ),
    }

    signal_counts = {
        "geo_country_jump": len(country_jumps),
        "geo_impossible_travel": len(impossible_travel),
        "device_rotation": len(device_map),
        "device_os_mismatch": sum(1 for os_values in device_groups.values() if len(os_values) > 1),
        "cross_node_fanout": len(node_names),
        "provider_fanout": len(provider_counter),
        "traffic_burst": int((burst or {}).get("event_count") or (burst or {}).get("point_count") or 0),
    }

    summary_parts: list[str] = []
    if ip_counter:
        summary_parts.append(f"IPs {len(ip_counter)}")
    if provider_counter:
        summary_parts.append(f"providers {len(provider_counter)}")
    if node_names:
        summary_parts.append(f"nodes {len(node_names)}")
    if device_map:
        summary_parts.append(f"devices {len(device_map)}")
    if geo_summary["countries"]:
        summary_parts.append("countries " + ", ".join(geo_summary["countries"][:3]))
    if burst and _clean_text(burst.get("bytes_text")):
        summary_parts.append("traffic " + _clean_text(burst.get("bytes_text")))
    if soft_reasons:
        summary_parts.append("flags " + ", ".join(soft_reasons))
    usage_profile_summary = "; ".join(summary_parts)

    return {
        "available": bool(observations or panel_devices or traffic_stats_payload),
        "event_count": len(observations),
        "ip_count": len(ip_counter),
        "provider_count": len(provider_counter),
        "device_count": len(device_map),
        "device_labels": device_labels[:10],
        "devices": list(device_map.values())[:10],
        "os_families": os_families,
        "node_count": len(node_names),
        "nodes": node_names[:10],
        "geo_summary": geo_summary,
        "travel_flags": {
            "geo_country_jump": bool(country_jumps),
            "geo_impossible_travel": bool(impossible_travel),
            "country_jumps": country_jumps[:5],
            "impossible_travel": impossible_travel[:5],
        },
        "top_ips": top_ips,
        "top_providers": top_providers,
        "traffic_burst": burst,
        "soft_reasons": soft_reasons,
        "signal_counts": signal_counts,
        "ongoing_duration_seconds": ongoing_duration_seconds,
        "ongoing_duration_text": _format_duration(ongoing_duration_seconds),
        "last_seen": last_seen_text or None,
        "updated_at": updated_at_text or None,
        "usage_profile_summary": usage_profile_summary,
        "summary_score": len(soft_reasons),
        "summary_reason_set": list(soft_reasons),
    }


def build_usage_profile_template_context(snapshot: Mapping[str, Any] | None) -> dict[str, Any]:
    profile = snapshot if isinstance(snapshot, Mapping) else {}
    travel_flags = profile.get("travel_flags") if isinstance(profile.get("travel_flags"), Mapping) else {}
    geo_summary = profile.get("geo_summary") if isinstance(profile.get("geo_summary"), Mapping) else {}
    top_ips = profile.get("top_ips") if isinstance(profile.get("top_ips"), list) else []
    top_providers = profile.get("top_providers") if isinstance(profile.get("top_providers"), list) else []

    return {
        "usage_profile_summary": _clean_text(profile.get("usage_profile_summary")),
        "usage_profile_ip_count": int(profile.get("ip_count") or 0) or "",
        "usage_profile_provider_count": int(profile.get("provider_count") or 0) or "",
        "usage_profile_node_count": int(profile.get("node_count") or 0) or "",
        "usage_profile_device_count": int(profile.get("device_count") or 0) or "",
        "usage_profile_os_count": len(profile.get("os_families") or []) or "",
        "usage_profile_country_count": int(geo_summary.get("country_count") or 0) or "",
        "usage_profile_top_ips": ", ".join(str(item.get("ip")) for item in top_ips if item.get("ip")),
        "usage_profile_top_providers": ", ".join(
            str(item.get("provider")) for item in top_providers if item.get("provider")
        ),
        "usage_profile_countries": ", ".join(str(value) for value in geo_summary.get("countries") or []),
        "usage_profile_soft_reasons": ", ".join(str(value) for value in profile.get("soft_reasons") or []),
        "usage_profile_ongoing_duration_seconds": int(profile.get("ongoing_duration_seconds") or 0) or "",
        "usage_profile_ongoing_duration_text": _clean_text(profile.get("ongoing_duration_text")),
        "usage_profile_geo_country_jump": "yes" if bool(travel_flags.get("geo_country_jump")) else "",
        "usage_profile_geo_impossible_travel": "yes" if bool(travel_flags.get("geo_impossible_travel")) else "",
    }
