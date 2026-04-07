import os
import shutil
import tempfile
import unittest

from mobguard_platform.envfile import get_env_file_status, read_env_file, update_env_file


class EnvFileTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-envfile-")
        self.env_path = os.path.join(self.temp_dir, ".env")

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_read_env_file_falls_back_to_process_env(self):
        previous = os.environ.get("TG_ADMIN_BOT_TOKEN")
        os.environ["TG_ADMIN_BOT_TOKEN"] = "process-value"
        try:
            values = read_env_file(self.env_path)
            self.assertEqual(values["TG_ADMIN_BOT_TOKEN"], "process-value")
        finally:
            if previous is None:
                os.environ.pop("TG_ADMIN_BOT_TOKEN", None)
            else:
                os.environ["TG_ADMIN_BOT_TOKEN"] = previous

    def test_read_env_file_prefers_file_values_over_process_env(self):
        previous = os.environ.get("TG_ADMIN_BOT_TOKEN")
        os.environ["TG_ADMIN_BOT_TOKEN"] = "process-value"
        try:
            with open(self.env_path, "w", encoding="utf-8") as handle:
                handle.write("TG_ADMIN_BOT_TOKEN=file-value\n")
            values = read_env_file(self.env_path)
            self.assertEqual(values["TG_ADMIN_BOT_TOKEN"], "file-value")
        finally:
            if previous is None:
                os.environ.pop("TG_ADMIN_BOT_TOKEN", None)
            else:
                os.environ["TG_ADMIN_BOT_TOKEN"] = previous

    def test_update_env_file_requires_existing_writable_file(self):
        with self.assertRaises(ValueError):
            update_env_file(self.env_path, {"PANEL_LOCAL_USERNAME": "admin"})

        with open(self.env_path, "w", encoding="utf-8") as handle:
            handle.write("PANEL_LOCAL_USERNAME=\n")
        update_env_file(self.env_path, {"PANEL_LOCAL_USERNAME": "admin"})

        values = read_env_file(self.env_path)
        self.assertEqual(values["PANEL_LOCAL_USERNAME"], "admin")

    def test_get_env_file_status_reports_writability(self):
        status = get_env_file_status(self.env_path)
        self.assertFalse(status["exists"])
        self.assertFalse(status["writable"])

        with open(self.env_path, "w", encoding="utf-8") as handle:
            handle.write("A=B\n")
        status = get_env_file_status(self.env_path)
        self.assertTrue(status["exists"])
        self.assertTrue(status["writable"])


if __name__ == "__main__":
    unittest.main()
