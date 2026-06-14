import unittest
from types import SimpleNamespace
from unittest.mock import patch

from mobguard_platform.storage.postgres import PostgresStorage


class PostgresStorageTests(unittest.TestCase):
    def setUp(self):
        self.storage = PostgresStorage("postgresql://mobguard:secret@db:5432/mobguard")
        self.conn = SimpleNamespace(storage=self.storage, _last_changes=3)

    def test_translate_query_rewrites_placeholders_and_datetime(self):
        sql, params, table_name = self.storage.translate_query(
            self.conn,
            "SELECT COUNT(*) AS cnt FROM violations WHERE uuid = ? AND unban_time > datetime('now')",
            ("user-1",),
        )

        self.assertIn("%s", sql)
        self.assertIn("CURRENT_TIMESTAMP", sql)
        self.assertEqual(params, ("user-1",))
        self.assertIsNone(table_name)

    def test_translate_query_rewrites_insert_or_ignore(self):
        with patch.object(self.storage, "_primary_key_columns", return_value=["id"]):
            sql, _, table_name = self.storage.translate_query(
                self.conn,
                "INSERT OR IGNORE INTO review_labels (case_id, created_at) VALUES (?, ?)",
                (1, "2026-01-01T00:00:00"),
            )

        self.assertTrue(sql.startswith("INSERT INTO review_labels"))
        self.assertIn("ON CONFLICT DO NOTHING", sql)
        self.assertEqual(table_name, "review_labels")

    def test_translate_query_rewrites_insert_or_replace(self):
        with patch.object(self.storage, "_primary_key_columns", return_value=["ip"]):
            sql, _, table_name = self.storage.translate_query(
                self.conn,
                "INSERT OR REPLACE INTO ip_decisions (ip, status, confidence) VALUES (?, ?, ?)",
                ("1.2.3.4", "HOME", "HIGH_HOME"),
            )

        self.assertTrue(sql.startswith("INSERT INTO ip_decisions"))
        self.assertIn("ON CONFLICT (ip) DO UPDATE SET", sql)
        self.assertIn("status = EXCLUDED.status", sql)
        self.assertEqual(table_name, "ip_decisions")

    def test_handle_special_query_returns_changes_cursor(self):
        cursor = self.storage.handle_special_query(self.conn, "SELECT changes() AS cnt", ())

        self.assertIsNotNone(cursor)
        row = cursor.fetchone()
        self.assertEqual(row["cnt"], 3)

    def test_handle_special_query_returns_begin_immediate_noop(self):
        cursor = self.storage.handle_special_query(self.conn, "BEGIN IMMEDIATE", ())

        self.assertIsNotNone(cursor)
        self.assertIsNone(cursor.fetchone())

    def test_translate_query_escapes_percent_signs(self):
        sql, _, _ = self.storage.translate_query(
            self.conn,
            "SELECT * FROM review_cases WHERE usage_profile_soft_reasons_json LIKE '%traffic_burst%'",
            (),
        )
        self.assertIn("LIKE '%%traffic_burst%%'", sql)


if __name__ == "__main__":
    unittest.main()
