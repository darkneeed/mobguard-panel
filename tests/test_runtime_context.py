import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from mobguard_platform.runtime import load_runtime_context


class RuntimeContextTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-runtime-context-")
        self.root = Path(self.temp_dir)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)
        (self.root / ".env").write_text("IPINFO_TOKEN=test-token\n", encoding="utf-8")
        (self.runtime / "config.json").write_text(
            json.dumps({"settings": {"threshold_mobile": 60}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_runtime_context_bootstraps_shared_paths(self):
        previous = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            context = load_runtime_context(self.root, str(self.runtime))
        finally:
            if previous is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous

        self.assertEqual(context.runtime_dir, self.runtime)
        self.assertEqual(context.env_path, self.root / ".env")
        self.assertEqual(context.settings["db_file"], str(self.runtime / "bans.db"))
        self.assertEqual(context.settings["geoip_db"], str(self.runtime / "GeoLite2-ASN.mmdb"))
        self.assertTrue((self.runtime / "health").exists())
        self.assertTrue((self.runtime / "bans.db").exists())
