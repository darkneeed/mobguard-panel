import base64
import io
import json
import shutil
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace

from api.services import data_admin as data_admin_service
from mobguard_platform.models import DecisionBundle
from mobguard_platform.store import PlatformStore


class CalibrationExportTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-calibration-export-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.db_path = self.root / "test.sqlite3"
        self.base_config = {
            "mixed_asns": [3216, 12389],
            "provider_profiles": [
                {
                    "key": "beeline",
                    "classification": "mixed",
                    "aliases": ["beeline", "vimpelcom"],
                    "mobile_markers": ["lte", "mobile"],
                    "home_markers": ["gpon", "fiber", "home"],
                    "asns": [3216],
                },
                {
                    "key": "mts",
                    "classification": "mixed",
                    "aliases": ["mts"],
                    "mobile_markers": ["lte", "mobile"],
                    "home_markers": ["gpon", "fiber"],
                    "asns": [12389],
                },
            ],
            "settings": {
                "threshold_mobile": 60,
                "threshold_home": 15,
                "threshold_probable_home": 30,
                "threshold_probable_mobile": 50,
                "learning_promote_asn_min_support": 1,
                "learning_promote_asn_min_precision": 1.0,
                "learning_promote_combo_min_support": 1,
                "learning_promote_combo_min_precision": 1.0,
                "review_ui_base_url": "https://mobguard.example.com",
            },
        }
        self.store = PlatformStore(str(self.db_path), self.base_config, str(self.config_path))
        self.store.init_schema()
        self.container = SimpleNamespace(
            store=self.store,
            runtime=SimpleNamespace(reload_config=lambda: json.loads(json.dumps(self.base_config))),
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_case(self, *, user: dict[str, object], bundle: DecisionBundle, review_reason: str, resolution: str):
        event_id = self.store.record_analysis_event(user, bundle.ip, "TAG", bundle)
        summary = self.store.ensure_review_case(user, bundle.ip, "TAG", bundle, event_id, review_reason)
        self.store.resolve_review_case(summary.id, resolution, "admin", 1001, f"resolved as {resolution}")

    def test_calibration_export_builds_zip_and_preserves_unknown_rows(self):
        home_bundle = DecisionBundle(
            ip="10.0.0.10",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-18,
            asn=3216,
            isp="Beeline GPON",
        )
        home_bundle.add_reason(
            "provider_home_marker",
            "provider_profile",
            -18,
            "soft",
            "HOME",
            "Provider beeline matched HOME service markers",
            {
                "provider_key": "beeline",
                "provider_classification": "mixed",
                "service_type_hint": "home",
                "home_markers": ["gpon"],
            },
        )
        home_bundle.add_reason(
            "behavior_lifetime",
            "behavior",
            -5,
            "soft",
            "HOME",
            "Long session lifetime",
            {"lifetime_hours": 18.0},
        )
        home_bundle.signal_flags["provider_evidence"] = {
            "provider_key": "beeline",
            "provider_classification": "mixed",
            "service_type_hint": "home",
            "service_conflict": False,
            "review_recommended": True,
        }
        self._create_case(
            user={"uuid": "uuid-home", "username": "alice", "telegramId": "1001", "id": 42},
            bundle=home_bundle,
            review_reason="provider_conflict",
            resolution="HOME",
        )

        unknown_bundle = DecisionBundle(
            ip="10.0.0.11",
            verdict="UNSURE",
            confidence_band="UNSURE",
            score=0,
            asn=12389,
            isp="MTS",
        )
        unknown_bundle.add_reason(
            "provider_conflict",
            "provider_profile",
            0,
            "soft",
            "NEUTRAL",
            "Mixed provider mts exposes both HOME and MOBILE service markers",
            {
                "provider_key": "mts",
                "provider_classification": "mixed",
                "service_type_hint": "conflict",
                "mobile_markers": ["lte"],
                "home_markers": ["gpon"],
            },
        )
        unknown_bundle.signal_flags["provider_evidence"] = {
            "provider_key": "mts",
            "provider_classification": "mixed",
            "service_type_hint": "conflict",
            "service_conflict": True,
            "review_recommended": True,
        }
        self._create_case(
            user={"uuid": "uuid-unknown", "username": "bob", "telegramId": "2002", "id": 77},
            bundle=unknown_bundle,
            review_reason="provider_conflict",
            resolution="SKIP",
        )

        payload = data_admin_service.build_calibration_export(
            self.container,
            {"status": "resolved_only", "include_unknown": False},
        )

        manifest_from_header = json.loads(base64.b64decode(payload["manifest_header"]).decode("utf-8"))
        self.assertEqual(manifest_from_header["row_counts"]["raw_rows"], 2)
        self.assertEqual(manifest_from_header["row_counts"]["aggregate_rows"], 1)
        self.assertEqual(manifest_from_header["row_counts"]["unknown_rows"], 1)
        self.assertTrue(manifest_from_header["dataset_ready"])
        self.assertFalse(manifest_from_header["tuning_ready"])
        self.assertIn("provider_support_below_target", manifest_from_header["warnings"])

        archive = zipfile.ZipFile(io.BytesIO(payload["content"]))
        self.assertEqual(
            sorted(archive.namelist()),
            sorted(
                [
                    "calibration_rows.jsonl",
                    "feature_summary.csv",
                    "manifest.json",
                    "mixed_provider_summary.csv",
                    "provider_summary.csv",
                    "review_reason_summary.csv",
                    "rules_snapshot.json",
                ]
            ),
        )

        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
        self.assertEqual(manifest["row_counts"]["known_rows"], 1)
        self.assertEqual(manifest["row_counts"]["unknown_rows"], 1)
        self.assertEqual(manifest["row_counts"]["resolved_known_rows"], 1)
        self.assertEqual(manifest["row_counts"]["resolved_unknown_rows"], 1)
        self.assertEqual(manifest["coverage"]["provider_profiles_count"], 2)
        self.assertEqual(manifest["coverage"]["provider_key_coverage"], 1.0)

        calibration_rows = [
            json.loads(line)
            for line in archive.read("calibration_rows.jsonl").decode("utf-8").splitlines()
            if line.strip()
        ]
        self.assertEqual(len(calibration_rows), 2)
        self.assertEqual({row["ground_truth"] for row in calibration_rows}, {"HOME", "unknown"})
        self.assertTrue(calibration_rows[0]["provider_evidence"]["provider_key"] in {"beeline", "mts"})
        self.assertIn("provider_evidence_reconstructed", calibration_rows[0])

        provider_summary = archive.read("provider_summary.csv").decode("utf-8")
        self.assertIn("beeline", provider_summary)
        self.assertIn("mts", provider_summary)
        self.assertIn("raw_total", provider_summary)

    def test_calibration_export_warns_when_provider_profiles_are_missing_and_runtime_is_merged(self):
        container = SimpleNamespace(
            store=self.store,
            runtime=SimpleNamespace(
                reload_config=lambda: {
                    **self.base_config,
                    "provider_profiles": [
                        {
                            "key": "beeline",
                            "classification": "mixed",
                            "aliases": ["beeline"],
                            "mobile_markers": ["lte"],
                            "home_markers": ["gpon"],
                            "asns": [3216],
                        }
                    ],
                }
            ),
        )
        self.store.update_live_rules({"provider_profiles": []}, "admin", 1001)

        payload = data_admin_service.build_calibration_export(
            container,
            {"status": "resolved_only", "include_unknown": False},
        )
        manifest = json.loads(base64.b64decode(payload["manifest_header"]).decode("utf-8"))

        self.assertEqual(manifest["snapshot_source"], "runtime_merged")
        self.assertIn("live_rules_stale_or_unseeded", manifest["warnings"])
        self.assertFalse(manifest["dataset_ready"])

    def test_calibration_export_flags_missing_provider_explainability_on_resolved_rows(self):
        bundle = DecisionBundle(
            ip="10.0.0.12",
            verdict="HOME",
            confidence_band="HIGH_HOME",
            score=-20,
            asn=3216,
            isp="Beeline GPON",
        )
        bundle.add_reason(
            "keyword_home",
            "generic_keyword",
            -20,
            "soft",
            "HOME",
            "HOME keywords found",
            {"keywords": ["gpon"]},
        )
        self._create_case(
            user={"uuid": "uuid-no-provider", "username": "charlie", "telegramId": "3003", "id": 99},
            bundle=bundle,
            review_reason="home_requires_review",
            resolution="HOME",
        )

        payload = data_admin_service.build_calibration_export(
            self.container,
            {"status": "resolved_only", "include_unknown": False},
        )
        manifest = json.loads(base64.b64decode(payload["manifest_header"]).decode("utf-8"))
        self.assertIn("provider_key_coverage_zero", manifest["warnings"])
        self.assertIn("provider_explainability_missing", manifest["warnings"])
        self.assertFalse(manifest["dataset_ready"])


if __name__ == "__main__":
    unittest.main()
