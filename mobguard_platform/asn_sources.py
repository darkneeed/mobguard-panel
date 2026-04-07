from __future__ import annotations

import gzip
import ipaddress
import logging
import os
import sqlite3
from pathlib import Path
from typing import Optional, Tuple

try:
    import maxminddb
except ModuleNotFoundError:  # pragma: no cover - exercised in test envs without the wheel
    maxminddb = None

from .runtime_paths import runtime_geoip_db_path


logger = logging.getLogger("mobguard.asn")

SPLIT_IPV4_MMDB_FILENAME = "GeoLite2-ASN-IPv4.mmdb"
SPLIT_IPV6_MMDB_FILENAME = "GeoLite2-ASN-IPv6.mmdb"
IPTOASN_TSV_FILENAME = "ip2asn-combined.tsv.gz"
IPTOASN_INDEX_FILENAME = "ip2asn-combined.sqlite3"


class ASNSource:
    def lookup(self, ip: str) -> Tuple[Optional[int], str]:
        return None, "unknown"


class NullASNSource(ASNSource):
    pass


class MMDBASNSource(ASNSource):
    def __init__(
        self,
        single_path: Optional[str] = None,
        ipv4_path: Optional[str] = None,
        ipv6_path: Optional[str] = None,
    ):
        self.single_reader = _open_mmdb(single_path)
        self.ipv4_reader = _open_mmdb(ipv4_path)
        self.ipv6_reader = _open_mmdb(ipv6_path)

    def lookup(self, ip: str) -> Tuple[Optional[int], str]:
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return None, "unknown"

        reader = self.single_reader
        if reader is None:
            reader = self.ipv4_reader if ip_obj.version == 4 else self.ipv6_reader
        if reader is None:
            return None, "unknown"

        try:
            data = reader.get(ip)
        except Exception:
            logger.exception("ASN MMDB lookup failed for %s", ip)
            return None, "unknown"
        return extract_asn_fields(data)


class IPToASNSource(ASNSource):
    def __init__(self, tsv_gz_path: str, index_path: Optional[str] = None):
        self.tsv_gz_path = tsv_gz_path
        self.index_path = index_path or str(
            Path(tsv_gz_path).with_name(IPTOASN_INDEX_FILENAME)
        )
        self._conn: Optional[sqlite3.Connection] = None

    def lookup(self, ip: str) -> Tuple[Optional[int], str]:
        if not os.path.exists(self.tsv_gz_path):
            return None, "unknown"

        conn = self._get_connection()
        try:
            ip_obj = ipaddress.ip_address(ip)
        except ValueError:
            return None, "unknown"

        if ip_obj.version == 4:
            value = int(ip_obj)
            row = conn.execute(
                """
                SELECT asn, org
                FROM ipv4_ranges
                WHERE start <= ? AND "end" >= ?
                ORDER BY start DESC
                LIMIT 1
                """,
                (value, value),
            ).fetchone()
        else:
            value = ip_obj.packed
            row = conn.execute(
                """
                SELECT asn, org
                FROM ipv6_ranges
                WHERE start <= ? AND "end" >= ?
                ORDER BY start DESC
                LIMIT 1
                """,
                (value, value),
            ).fetchone()

        if not row:
            return None, "unknown"
        return int(row["asn"]), (row["org"] or "unknown").lower()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._ensure_index()
            self._conn = sqlite3.connect(self.index_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _ensure_index(self) -> None:
        source_stat = os.stat(self.tsv_gz_path)
        if os.path.exists(self.index_path):
            index_stat = os.stat(self.index_path)
            if index_stat.st_mtime >= source_stat.st_mtime and index_stat.st_size > 0:
                return

        logger.info("Building IPtoASN index from %s", self.tsv_gz_path)
        tmp_path = f"{self.index_path}.tmp"
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        conn = sqlite3.connect(tmp_path)
        try:
            conn.execute(
                "CREATE TABLE ipv4_ranges (start INTEGER NOT NULL, \"end\" INTEGER NOT NULL, asn INTEGER NOT NULL, org TEXT NOT NULL)"
            )
            conn.execute(
                "CREATE TABLE ipv6_ranges (start BLOB NOT NULL, \"end\" BLOB NOT NULL, asn INTEGER NOT NULL, org TEXT NOT NULL)"
            )

            ipv4_batch = []
            ipv6_batch = []
            with gzip.open(self.tsv_gz_path, "rt", encoding="utf-8", newline="") as handle:
                for raw_line in handle:
                    line = raw_line.strip()
                    if not line:
                        continue
                    parts = line.split("\t", 4)
                    if len(parts) != 5:
                        parts = line.split(None, 4)
                    if len(parts) != 5:
                        continue

                    start, end, asn_raw, _country_code, description = parts
                    try:
                        asn = int(asn_raw)
                        start_ip = ipaddress.ip_address(start)
                        end_ip = ipaddress.ip_address(end)
                    except ValueError:
                        continue

                    if start_ip.version == 4:
                        ipv4_batch.append((int(start_ip), int(end_ip), asn, description))
                        if len(ipv4_batch) >= 5000:
                            conn.executemany(
                                "INSERT INTO ipv4_ranges (start, \"end\", asn, org) VALUES (?, ?, ?, ?)",
                                ipv4_batch,
                            )
                            ipv4_batch.clear()
                    else:
                        ipv6_batch.append((start_ip.packed, end_ip.packed, asn, description))
                        if len(ipv6_batch) >= 5000:
                            conn.executemany(
                                "INSERT INTO ipv6_ranges (start, \"end\", asn, org) VALUES (?, ?, ?, ?)",
                                ipv6_batch,
                            )
                            ipv6_batch.clear()

            if ipv4_batch:
                conn.executemany(
                    "INSERT INTO ipv4_ranges (start, \"end\", asn, org) VALUES (?, ?, ?, ?)",
                    ipv4_batch,
                )
            if ipv6_batch:
                conn.executemany(
                    "INSERT INTO ipv6_ranges (start, \"end\", asn, org) VALUES (?, ?, ?, ?)",
                    ipv6_batch,
                )

            conn.execute("CREATE INDEX idx_ipv4_ranges_start_end ON ipv4_ranges(start, \"end\")")
            conn.execute("CREATE INDEX idx_ipv6_ranges_start_end ON ipv6_ranges(start, \"end\")")
            conn.commit()
        finally:
            conn.close()

        os.replace(tmp_path, self.index_path)


def resolve_asn_source(runtime_dir: str, single_mmdb_path: Optional[str] = None) -> ASNSource:
    single_path = single_mmdb_path or runtime_geoip_db_path(runtime_dir)
    ipv4_path = os.path.join(runtime_dir, SPLIT_IPV4_MMDB_FILENAME)
    ipv6_path = os.path.join(runtime_dir, SPLIT_IPV6_MMDB_FILENAME)
    iptoasn_path = os.path.join(runtime_dir, IPTOASN_TSV_FILENAME)

    if os.path.exists(single_path):
        return MMDBASNSource(single_path=single_path)
    if os.path.exists(ipv4_path) or os.path.exists(ipv6_path):
        return MMDBASNSource(ipv4_path=ipv4_path, ipv6_path=ipv6_path)
    if os.path.exists(iptoasn_path):
        return IPToASNSource(iptoasn_path)
    return NullASNSource()


def extract_asn_fields(data: object) -> Tuple[Optional[int], str]:
    if not isinstance(data, dict):
        return None, "unknown"

    traits = data.get("traits")
    if not isinstance(traits, dict):
        traits = {}

    organization = data.get("organization")
    if not isinstance(organization, dict):
        organization = {}

    asn = _first_int(
        data.get("autonomous_system_number"),
        data.get("asn"),
        data.get("as_number"),
        traits.get("autonomous_system_number"),
        traits.get("asn"),
        organization.get("asn"),
    )
    org = _first_text(
        data.get("autonomous_system_organization"),
        data.get("autonomous_system_name"),
        data.get("as_organization"),
        data.get("as_name"),
        organization.get("name"),
        traits.get("autonomous_system_organization"),
        traits.get("organization"),
        traits.get("isp"),
    )
    return asn, org.lower() if org else "unknown"


def _first_int(*values: object) -> Optional[int]:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_text(*values: object) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _open_mmdb(path: Optional[str]):
    if not path or not os.path.exists(path):
        return None
    if maxminddb is None:
        logger.warning("maxminddb module is unavailable, MMDB ASN source %s will be skipped", path)
        return None
    try:
        return maxminddb.open_database(path)
    except Exception:
        logger.exception("Failed to open ASN MMDB %s", path)
        return None
