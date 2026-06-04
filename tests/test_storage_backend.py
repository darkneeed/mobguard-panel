import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from mobguard_platform.runtime import load_runtime_context
from mobguard_platform.storage.factory import build_storage_bundle
from mobguard_platform.storage.postgres import PostgresStorage


class StorageBackendTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-storage-backend-")
        self.root = Path(self.temp_dir)
        self.runtime = self.root / "runtime"
        self.runtime.mkdir(parents=True, exist_ok=True)
        (self.root / ".env").write_text("", encoding="utf-8")
        (self.runtime / "config.json").write_text(
            json.dumps({"settings": {"threshold_mobile": 60}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_runtime_context_defaults_to_postgres_backend(self):
        previous_env_file = os.environ.get("MOBGUARD_ENV_FILE")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        try:
            context = load_runtime_context(self.root, str(self.runtime))
        finally:
            if previous_env_file is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous_env_file

        self.assertEqual(context.database.backend, "postgres")

    def test_runtime_context_loads_postgres_backend_from_env(self):
        previous_env_file = os.environ.get("MOBGUARD_ENV_FILE")
        previous_backend = os.environ.get("MOBGUARD_DB_BACKEND")
        previous_dsn = os.environ.get("MOBGUARD_POSTGRES_DSN")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        os.environ["MOBGUARD_DB_BACKEND"] = "postgres"
        os.environ["MOBGUARD_POSTGRES_DSN"] = "postgresql://mobguard:secret@db:5432/mobguard"
        try:
            context = load_runtime_context(self.root, str(self.runtime))
        finally:
            if previous_env_file is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous_env_file
            if previous_backend is None:
                os.environ.pop("MOBGUARD_DB_BACKEND", None)
            else:
                os.environ["MOBGUARD_DB_BACKEND"] = previous_backend
            if previous_dsn is None:
                os.environ.pop("MOBGUARD_POSTGRES_DSN", None)
            else:
                os.environ["MOBGUARD_POSTGRES_DSN"] = previous_dsn

        self.assertEqual(context.database.backend, "postgres")
        self.assertEqual(context.database.resolve_postgres_dsn(), "postgresql://mobguard:secret@db:5432/mobguard")

    def test_runtime_context_infers_postgres_backend_from_database_url(self):
        previous_env_file = os.environ.get("MOBGUARD_ENV_FILE")
        previous_backend = os.environ.get("MOBGUARD_DB_BACKEND")
        previous_database_url = os.environ.get("DATABASE_URL")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        os.environ.pop("MOBGUARD_DB_BACKEND", None)
        os.environ["DATABASE_URL"] = "postgresql://mobguard:secret@db:5432/mobguard"
        try:
            context = load_runtime_context(self.root, str(self.runtime))
        finally:
            if previous_env_file is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous_env_file
            if previous_backend is None:
                os.environ.pop("MOBGUARD_DB_BACKEND", None)
            else:
                os.environ["MOBGUARD_DB_BACKEND"] = previous_backend
            if previous_database_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = previous_database_url

        self.assertEqual(context.database.backend, "postgres")
        self.assertEqual(context.database.resolve_postgres_dsn(), "postgresql://mobguard:secret@db:5432/mobguard")



    def test_build_storage_bundle_builds_postgres_store_bundle(self):
        previous_env_file = os.environ.get("MOBGUARD_ENV_FILE")
        previous_backend = os.environ.get("MOBGUARD_DB_BACKEND")
        previous_dsn = os.environ.get("MOBGUARD_POSTGRES_DSN")
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        os.environ["MOBGUARD_DB_BACKEND"] = "postgres"
        os.environ["MOBGUARD_POSTGRES_DSN"] = "postgresql://mobguard:secret@db:5432/mobguard"
        try:
            context = load_runtime_context(self.root, str(self.runtime))
        finally:
            if previous_env_file is None:
                os.environ.pop("MOBGUARD_ENV_FILE", None)
            else:
                os.environ["MOBGUARD_ENV_FILE"] = previous_env_file
            if previous_backend is None:
                os.environ.pop("MOBGUARD_DB_BACKEND", None)
            else:
                os.environ["MOBGUARD_DB_BACKEND"] = previous_backend
            if previous_dsn is None:
                os.environ.pop("MOBGUARD_POSTGRES_DSN", None)
            else:
                os.environ["MOBGUARD_POSTGRES_DSN"] = previous_dsn

        bundle = build_storage_bundle(context)

        self.assertEqual(bundle.backend, "postgres")
        self.assertIsInstance(bundle.store.storage, PostgresStorage)
        self.assertIsInstance(bundle.analysis_store.storage, PostgresStorage)
        self.assertEqual(bundle.store.storage.dsn, "postgresql://mobguard:secret@db:5432/mobguard")


if __name__ == "__main__":
    unittest.main()
