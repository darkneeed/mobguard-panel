import gzip
import os
import shutil
import tempfile
import unittest

from mobguard_platform.asn_sources import IPToASNSource, extract_asn_fields, resolve_asn_source
from mobguard_platform.runtime_paths import runtime_geoip_db_path


class ASNSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-asn-")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_extract_asn_fields_supports_multiple_mmdb_shapes(self):
        self.assertEqual(
            extract_asn_fields(
                {
                    "autonomous_system_number": 13335,
                    "autonomous_system_organization": "Cloudflare",
                }
            ),
            (13335, "cloudflare"),
        )
        self.assertEqual(
            extract_asn_fields(
                {
                    "asn": 15169,
                    "organization": {"name": "Google LLC"},
                }
            ),
            (15169, "google llc"),
        )
        self.assertEqual(
            extract_asn_fields(
                {
                    "traits": {
                        "autonomous_system_number": 8075,
                        "autonomous_system_organization": "Microsoft",
                    }
                }
            ),
            (8075, "microsoft"),
        )

    def test_iptoasn_source_looks_up_ipv4_and_ipv6(self):
        tsv_path = os.path.join(self.temp_dir, "ip2asn-combined.tsv.gz")
        with gzip.open(tsv_path, "wt", encoding="utf-8", newline="") as handle:
            handle.write("1.1.1.0\t1.1.1.255\t13335\tAU\tCloudflare\n")
            handle.write("2001:db8::\t2001:db8::ffff\t64500\tZZ\tExample IPv6 ASN\n")

        source = IPToASNSource(tsv_path)

        self.assertEqual(source.lookup("1.1.1.1"), (13335, "cloudflare"))
        self.assertEqual(source.lookup("2001:db8::1"), (64500, "example ipv6 asn"))
        self.assertEqual(source.lookup("8.8.8.8"), (None, "unknown"))

    def test_resolve_asn_source_uses_iptoasn_when_present(self):
        with gzip.open(os.path.join(self.temp_dir, "ip2asn-combined.tsv.gz"), "wt", encoding="utf-8") as handle:
            handle.write("8.8.8.0\t8.8.8.255\t15169\tUS\tGoogle LLC\n")

        source = resolve_asn_source(self.temp_dir, runtime_geoip_db_path(self.temp_dir))

        self.assertEqual(source.lookup("8.8.8.8"), (15169, "google llc"))


if __name__ == "__main__":
    unittest.main()
