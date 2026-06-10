import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mobguard_platform import AnalysisStore, PlatformStore
from api.services import ai_learning_suggestions

class AILearningSuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-ai-learning-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.runtime_dir / "config.json"
        self.config_path.write_text(
            json.dumps(
                {
                    "settings": {
                        "threshold_mobile": 60,
                        "learning_promote_asn_min_support": 10,
                        "learning_promote_asn_min_precision": 0.95
                    },
                    "_meta": {"revision": 1, "updated_at": "2026-04-11T10:00:00", "updated_by": "system"},
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        self.db_path = str(self.runtime_dir / "bans.db")
        self.store = PlatformStore(self.db_path, {"settings": {}}, str(self.config_path))
        self.analysis_store = AnalysisStore(self.db_path)
        self.analysis_store.init_schema()
        self.store.init_schema()
        self.store.sync_runtime_config(json.loads(self.config_path.read_text(encoding="utf-8")))
        self.container = SimpleNamespace(store=self.store, analysis_store=self.analysis_store)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_suggestion(self, pattern_type, pattern_value, suggested_decision, confidence, reasoning, errors_list, status="PENDING"):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_learning_suggestions (
                    pattern_type, pattern_value, current_decision, suggested_decision,
                    confidence, reasoning_ru, operator_errors_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, '2026-06-10T12:00:00', '2026-06-10T12:00:00')
                """,
                (pattern_type, pattern_value, "MOBILE", suggested_decision, confidence, reasoning, json.dumps(errors_list), status)
            )
            conn.commit()

    def _insert_mock_case(self, case_id, reason, priority):
        with self.store._connect() as conn:
            # We insert minimal fields to satisfy NOT NULL constraints
            conn.execute(
                """
                INSERT INTO review_cases (
                    id, unique_key, status, review_reason, verdict, confidence_band,
                    latest_event_id, reason_codes_json, opened_at, updated_at, ip, usage_profile_priority
                ) VALUES (?, ?, 'RESOLVED', ?, 'MOBILE', 'HIGH_HOME', 1, '[]', 'now', 'now', '1.1.1.1', ?)
                """,
                (case_id, f"case_{case_id}", reason, priority)
            )
            conn.commit()

    def test_get_suggestions_returns_empty_when_no_records(self):
        res = ai_learning_suggestions.get_suggestions(self.container)
        self.assertEqual(res, [])

    def test_get_suggestions_returns_populated_records(self):
        self._insert_suggestion("asn", "12345", "HOSTING", 0.99, "Объяснение", [101], "PENDING")
        res = ai_learning_suggestions.get_suggestions(self.container)
        self.assertEqual(len(res), 1)
        self.assertEqual(res[0]["pattern_value"], "12345")
        self.assertEqual(res[0]["status"], "PENDING")

    def test_reject_suggestion_updates_status(self):
        self._insert_suggestion("asn", "12345", "HOSTING", 0.99, "Объяснение", [101], "PENDING")
        suggestions = ai_learning_suggestions.get_suggestions(self.container)
        sug_id = suggestions[0]["id"]
        
        res = ai_learning_suggestions.reject_suggestion(self.container, sug_id)
        self.assertTrue(res["success"])
        
        # Verify status is updated to REJECTED
        suggestions_after = ai_learning_suggestions.get_suggestions(self.container)
        self.assertEqual(suggestions_after[0]["status"], "REJECTED")

    def test_accept_suggestion_updates_status_promotes_pattern_and_reopens_cases(self):
        self._insert_suggestion("asn", "8888", "HOSTING", 0.95, "Обоснование ИИ", [4432, 4435], "PENDING")
        self._insert_mock_case(4432, "Regular check", 100)
        self._insert_mock_case(4435, "Another check", 250)
        
        suggestions = ai_learning_suggestions.get_suggestions(self.container)
        sug_id = suggestions[0]["id"]
        
        res = ai_learning_suggestions.accept_suggestion(self.container, sug_id)
        self.assertTrue(res["success"])
        self.assertIn(4432, res["reopened_cases"])
        self.assertIn(4435, res["reopened_cases"])
        
        # Verify status in database is ACCEPTED
        with self.store._connect() as conn:
            sug_row = conn.execute("SELECT status FROM ai_learning_suggestions WHERE id = ?", (sug_id,)).fetchone()
            self.assertEqual(sug_row["status"], "ACCEPTED")
            
            # Verify it's in learning_patterns_active
            active_row = conn.execute(
                "SELECT decision, support FROM learning_patterns_active WHERE pattern_value = '8888'"
            ).fetchone()
            self.assertIsNotNone(active_row)
            self.assertEqual(active_row["decision"], "HOSTING")
            self.assertEqual(active_row["support"], 999)
            
            # Verify cases reopened and prioritized
            case_4432 = conn.execute("SELECT status, review_reason, usage_profile_priority FROM review_cases WHERE id = 4432").fetchone()
            self.assertEqual(case_4432["status"], "OPEN")
            self.assertEqual(case_4432["review_reason"], "[AI Recheck] Regular check")
            self.assertEqual(case_4432["usage_profile_priority"], 10100)
            
            case_4435 = conn.execute("SELECT status, review_reason, usage_profile_priority FROM review_cases WHERE id = 4435").fetchone()
            self.assertEqual(case_4435["status"], "OPEN")
            self.assertEqual(case_4435["review_reason"], "[AI Recheck] Another check")
            self.assertEqual(case_4435["usage_profile_priority"], 10250)

    def test_promote_learning_patterns_preserves_accepted_suggestions(self):
        # Insert accepted suggestion
        self._insert_suggestion("asn", "9999", "HOSTING", 0.98, "Hetzner cloud", [], "ACCEPTED")
        
        # Run promote_learning_patterns
        self.store.review_admin.promote_learning_patterns()
        
        # Verify that it is in active learning patterns even though there is no training data for it
        with self.store._connect() as conn:
            active_row = conn.execute(
                "SELECT decision, support FROM learning_patterns_active WHERE pattern_value = '9999'"
            ).fetchone()
            self.assertIsNotNone(active_row)
            self.assertEqual(active_row["decision"], "HOSTING")
            self.assertEqual(active_row["support"], 999)

if __name__ == "__main__":
    unittest.main()
