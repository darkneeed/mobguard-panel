import os
import tempfile
import unittest

from mobguard_platform.runtime_paths import (
    canonicalize_runtime_bound_settings,
    normalize_runtime_bound_settings,
    resolve_runtime_dir,
)


class RuntimePathTests(unittest.TestCase):
    def test_normalize_runtime_bound_settings_overrides_legacy_paths(self):
        config = {
            "settings": {
                "db_file": "/opt/ban_system/bans.db",
                "geoip_db": "/opt/ban_system/GeoLite2-ASN.mmdb",
            }
        }

        normalized = normalize_runtime_bound_settings(config, "/opt/mobguard/runtime")

        self.assertEqual(normalized["settings"]["db_file"], "/opt/mobguard/runtime/bans.db")
        self.assertEqual(
            normalized["settings"]["geoip_db"],
            "/opt/mobguard/runtime/GeoLite2-ASN.mmdb",
        )
        self.assertEqual(config["settings"]["db_file"], "/opt/ban_system/bans.db")

    def test_normalize_runtime_bound_settings_sets_missing_values(self):
        normalized = normalize_runtime_bound_settings({}, "/opt/ban_system")

        self.assertEqual(normalized["settings"]["db_file"], "/opt/ban_system/bans.db")
        self.assertEqual(normalized["settings"]["geoip_db"], "/opt/ban_system/GeoLite2-ASN.mmdb")

    def test_canonicalize_runtime_bound_settings_uses_relative_project_paths(self):
        canonical = canonicalize_runtime_bound_settings({}, "/opt/mobguard/runtime")
        self.assertEqual(canonical["settings"]["db_file"], "runtime/bans.db")
        self.assertEqual(canonical["settings"]["geoip_db"], "runtime/GeoLite2-ASN.mmdb")

    def test_canonicalize_runtime_bound_settings_keeps_legacy_runtime_relative(self):
        canonical = canonicalize_runtime_bound_settings({}, "/opt/ban_system")
        self.assertEqual(canonical["settings"]["db_file"], "bans.db")
        self.assertEqual(canonical["settings"]["geoip_db"], "GeoLite2-ASN.mmdb")

    def test_resolve_runtime_dir_prefers_workspace_runtime(self):
        with tempfile.TemporaryDirectory(prefix="mobguard-runtime-") as temp_dir:
            runtime_dir = os.path.join(temp_dir, "runtime")
            os.makedirs(runtime_dir)

            resolved = resolve_runtime_dir(temp_dir)

            self.assertEqual(resolved, runtime_dir)


if __name__ == "__main__":
    unittest.main()
