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
        self.container = SimpleNamespace(
            store=self.store,
            analysis_store=self.analysis_store,
            runtime=SimpleNamespace(config={"settings": {}})
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _insert_suggestion(self, pattern_type, pattern_value, suggested_decision, confidence, reasoning, errors_list, status="PENDING", provider_profile=None):
        with self.store._connect() as conn:
            conn.execute(
                """
                INSERT INTO ai_learning_suggestions (
                    pattern_type, pattern_value, current_decision, suggested_decision,
                    confidence, reasoning_ru, operator_errors_json, suggested_provider_profile_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, '2026-06-10T12:00:00', '2026-06-10T12:00:00')
                """,
                (pattern_type, pattern_value, "MOBILE", suggested_decision, confidence, reasoning, json.dumps(errors_list), json.dumps(provider_profile) if provider_profile else None, status)
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

    def test_accept_suggestion_updates_live_rules_with_operator_profile(self):
        profile = {
            "key": "test_prov",
            "classification": "mobile",
            "aliases": ["test_prov"],
            "mobile_markers": ["test_m"],
            "home_markers": [],
            "asns": [99991]
        }
        self._insert_suggestion("provider", "test_prov", "MOBILE", 0.99, "Обоснование", [], "PENDING", provider_profile=profile)
        
        suggestions = ai_learning_suggestions.get_suggestions(self.container)
        sug_id = suggestions[0]["id"]
        
        # We need to ensure live_rules is initialized so get_live_rules_state works
        with self.store._connect() as conn:
            conn.execute(
                "UPDATE live_rules SET rules_json = '{}', revision = 1 WHERE id = 1"
            )
            conn.commit()
            
        res = ai_learning_suggestions.accept_suggestion(self.container, sug_id)
        self.assertTrue(res["success"])
        
        # Verify the profile is in live rules config!
        rules_state = self.store.get_live_rules_state()
        profiles = rules_state.get("rules", {}).get("provider_profiles", [])
        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0]["key"], "test_prov")
        self.assertEqual(profiles[0]["asns"], [99991])

    def test_accept_suggestion_conflict_deletes_previous_accepted(self):
        # Insert an accepted suggestion for asn/7777
        self._insert_suggestion("asn", "7777", "HOSTING", 0.95, "Prev justification", [], "ACCEPTED")
        # Insert a pending suggestion for asn/7777
        self._insert_suggestion("asn", "7777", "HOSTING", 0.96, "New justification", [], "PENDING")

        suggestions = ai_learning_suggestions.get_suggestions(self.container)
        pending_sug = next(s for s in suggestions if s["status"] == "PENDING" and s["pattern_value"] == "7777")
        sug_id = pending_sug["id"]

        # Accept the new one: it should delete the old accepted suggestion and succeed
        res = ai_learning_suggestions.accept_suggestion(self.container, sug_id)
        self.assertTrue(res["success"])

        # Check there is exactly one accepted suggestion for asn/7777 in database
        with self.store._connect() as conn:
            rows = conn.execute(
                "SELECT id, status, suggested_decision FROM ai_learning_suggestions WHERE pattern_type = 'asn' AND pattern_value = '7777'"
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "ACCEPTED")
            self.assertEqual(rows[0]["suggested_decision"], "HOSTING")

    def test_reject_suggestion_conflict_deletes_previous_rejected(self):
        # Insert a rejected suggestion for asn/7777
        self._insert_suggestion("asn", "7777", "HOSTING", 0.95, "Prev justification", [], "REJECTED")
        # Insert a pending suggestion for asn/7777
        self._insert_suggestion("asn", "7777", "HOSTING", 0.96, "New justification", [], "PENDING")

        suggestions = ai_learning_suggestions.get_suggestions(self.container)
        pending_sug = next(s for s in suggestions if s["status"] == "PENDING" and s["pattern_value"] == "7777")
        sug_id = pending_sug["id"]

        # Reject the new one: it should delete the old rejected suggestion and succeed
        res = ai_learning_suggestions.reject_suggestion(self.container, sug_id)
        self.assertTrue(res["success"])

        # Check there is exactly one rejected suggestion for asn/7777 in database
        with self.store._connect() as conn:
            rows = conn.execute(
                "SELECT id, status, suggested_decision FROM ai_learning_suggestions WHERE pattern_type = 'asn' AND pattern_value = '7777'"
            ).fetchall()
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "REJECTED")
            self.assertEqual(rows[0]["suggested_decision"], "HOSTING")

    def test_generate_suggestions_cooldown_force(self):
        from fastapi import HTTPException
        # Set cooldown active
        self.store.set_metadata_value("last_ai_suggestions_timestamp", "2026-06-12T01:00:00")
        
        # Calling with force=False should raise HTTPException with "Cooldown in effect"
        with self.assertRaises(HTTPException) as ctx:
            ai_learning_suggestions.generate_suggestions_on_demand(self.container, {}, force=False)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Cooldown in effect", ctx.exception.detail)

        # Calling with force=True should bypass cooldown check (and raise "Gemini API key is not configured" instead of cooldown)
        with self.assertRaises(HTTPException) as ctx:
            ai_learning_suggestions.generate_suggestions_on_demand(self.container, {}, force=True)
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("Gemini API key is not configured", ctx.exception.detail)

if __name__ == "__main__":
    unittest.main()

