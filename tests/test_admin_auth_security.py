import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException, Response

from api.context import build_container
from api.dependencies import require_permission
from api.permissions import (
    PERMISSION_DATA_READ,
    PERMISSION_DATA_WRITE,
    PERMISSION_MODULES_TOKEN_REVEAL,
    ROLE_OWNER,
    permissions_for_role,
)
from api.services import auth as auth_service
from api.services.admin_audit import record_admin_action
from mobguard_platform.admin_totp import current_totp_code


class AdminAuthSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-admin-auth-")
        self.root = Path(self.temp_dir)
        self.runtime_dir = self.root / "runtime"
        self.runtime_dir.mkdir(parents=True, exist_ok=True)
        (self.root / ".env").write_text(
            "\n".join(
                [
                    "TG_ADMIN_BOT_TOKEN=admin-token",
                    "TG_ADMIN_BOT_USERNAME=adminbot",
                    "PANEL_LOCAL_USERNAME=owner",
                    "PANEL_LOCAL_PASSWORD=secret",
                    "MOBGUARD_MODULE_SECRET_KEY=test-secret-key",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (self.runtime_dir / "config.json").write_text(
            json.dumps({"settings": {"panel_name": "MobGuard"}}, ensure_ascii=False),
            encoding="utf-8",
        )
        previous_env_file = os.environ.get("MOBGUARD_ENV_FILE")
        previous_runtime_dir = os.environ.get("BAN_SYSTEM_DIR")
        self.addCleanup(self._restore_env, previous_env_file, previous_runtime_dir)
        os.environ["MOBGUARD_ENV_FILE"] = str(self.root / ".env")
        os.environ["BAN_SYSTEM_DIR"] = str(self.runtime_dir)
        self.container = build_container(self.root)
        self.container.store.update_live_rules(
            {"admin_tg_ids": [1], "moderator_tg_ids": [2], "viewer_tg_ids": [3]},
            "bootstrap",
            1,
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _restore_env(self, previous_env_file: str | None, previous_runtime_dir: str | None):
        if previous_env_file is None:
            os.environ.pop("MOBGUARD_ENV_FILE", None)
        else:
            os.environ["MOBGUARD_ENV_FILE"] = previous_env_file
        if previous_runtime_dir is None:
            os.environ.pop("BAN_SYSTEM_DIR", None)
        else:
            os.environ["BAN_SYSTEM_DIR"] = previous_runtime_dir

    def _rebuild_container(self) -> None:
        self.container = build_container(self.root)
        self.container.store.update_live_rules(
            {"admin_tg_ids": [1], "moderator_tg_ids": [2], "viewer_tg_ids": [3]},
            "bootstrap",
            1,
        )

    def test_role_resolution_uses_owner_moderator_and_viewer_lists(self):
        self.assertEqual(self.container.store.get_admin_role_for_tg_id(1), "owner")
        self.assertEqual(self.container.store.get_admin_role_for_tg_id(2), "moderator")
        self.assertEqual(self.container.store.get_admin_role_for_tg_id(3), "viewer")
        self.assertIsNone(self.container.store.get_admin_role_for_tg_id(999))

    def test_permission_dependency_denies_viewer_write_and_allows_read(self):
        viewer_session = {
            "role": "viewer",
            "permissions": permissions_for_role("viewer"),
            "totp_verified": False,
        }
        read_dependency = require_permission(PERMISSION_DATA_READ)
        self.assertEqual(read_dependency(None, viewer_session)["role"], "viewer")
        write_dependency = require_permission(PERMISSION_DATA_WRITE)
        with self.assertRaises(HTTPException) as exc_info:
            write_dependency(None, viewer_session)
        self.assertEqual(exc_info.exception.status_code, 403)

    def test_owner_critical_permission_requires_totp_verified_session(self):
        owner_session = {
            "role": ROLE_OWNER,
            "permissions": permissions_for_role(ROLE_OWNER),
            "totp_enabled": True,
            "totp_verified": False,
        }
        dependency = require_permission(PERMISSION_MODULES_TOKEN_REVEAL, require_owner_totp=True)
        with self.assertRaises(HTTPException) as exc_info:
            dependency(None, owner_session)
        self.assertEqual(exc_info.exception.status_code, 403)

    def test_owner_critical_permission_allows_unverified_session_when_totp_disabled(self):
        owner_session = {
            "role": ROLE_OWNER,
            "permissions": permissions_for_role(ROLE_OWNER),
            "totp_enabled": False,
            "totp_verified": False,
        }
        dependency = require_permission(PERMISSION_MODULES_TOKEN_REVEAL, require_owner_totp=True)
        self.assertEqual(dependency(None, owner_session)["role"], ROLE_OWNER)

    def test_local_login_first_time_requires_totp_setup_then_issues_owner_session(self):
        challenge = auth_service.local_login(self.container, "owner", "secret", Response())
        self.assertTrue(challenge["requires_totp"])
        self.assertTrue(challenge["totp_setup_required"])
        setup_payload = auth_service.totp_setup(self.container, challenge["challenge_token"])
        session = auth_service.totp_confirm_setup(
            self.container,
            challenge["challenge_token"],
            current_totp_code(setup_payload["secret"]),
            Response(),
        )
        self.assertEqual(session["role"], ROLE_OWNER)
        self.assertTrue(session["totp_enabled"])
        self.assertTrue(session["totp_verified"])
        self.assertIn("modules.token_reveal", session["permissions"])

    def test_local_login_with_existing_totp_uses_verify_challenge(self):
        first_challenge = auth_service.local_login(self.container, "owner", "secret", Response())
        setup_payload = auth_service.totp_setup(self.container, first_challenge["challenge_token"])
        auth_service.totp_confirm_setup(
            self.container,
            first_challenge["challenge_token"],
            current_totp_code(setup_payload["secret"]),
            Response(),
        )
        verify_challenge = auth_service.local_login(self.container, "owner", "secret", Response())
        self.assertTrue(verify_challenge["requires_totp"])
        self.assertFalse(verify_challenge["totp_setup_required"])
        session = auth_service.totp_verify(
            self.container,
            verify_challenge["challenge_token"],
            current_totp_code(setup_payload["secret"]),
            Response(),
        )
        self.assertTrue(session["totp_verified"])
        self.assertEqual(session["auth_method"], "local")

    def test_local_login_ignores_process_env_totp_bypass_without_env_file_override(self):
        previous_bypass = os.environ.get("PANEL_LOCAL_BYPASS_TOTP")
        self.addCleanup(self._restore_process_env, "PANEL_LOCAL_BYPASS_TOTP", previous_bypass)
        os.environ["PANEL_LOCAL_BYPASS_TOTP"] = "true"
        self._rebuild_container()

        challenge = auth_service.local_login(self.container, "owner", "secret", Response())

        self.assertTrue(challenge["requires_totp"])
        self.assertTrue(challenge["totp_setup_required"])

    def test_local_login_bypasses_totp_when_runtime_env_file_explicitly_enables_it(self):
        env_path = self.root / ".env"
        env_path.write_text(
            "\n".join(
                [
                    "TG_ADMIN_BOT_TOKEN=admin-token",
                    "TG_ADMIN_BOT_USERNAME=adminbot",
                    "PANEL_LOCAL_USERNAME=owner",
                    "PANEL_LOCAL_PASSWORD=secret",
                    "PANEL_LOCAL_BYPASS_TOTP=true",
                    "MOBGUARD_MODULE_SECRET_KEY=test-secret-key",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        self._rebuild_container()

        session = auth_service.local_login(self.container, "owner", "secret", Response())

        self.assertEqual(session["role"], ROLE_OWNER)
        self.assertFalse(session["totp_enabled"])
        self.assertTrue(session["totp_verified"])
        self.assertEqual(session["auth_method"], "local")

    def test_disable_owner_totp_clears_identity_and_skips_future_totp_challenge(self):
        first_challenge = auth_service.local_login(self.container, "owner", "secret", Response())
        setup_payload = auth_service.totp_setup(self.container, first_challenge["challenge_token"])
        auth_service.totp_confirm_setup(
            self.container,
            first_challenge["challenge_token"],
            current_totp_code(setup_payload["secret"]),
            Response(),
        )

        disabled = auth_service.disable_owner_totp(self.container)
        session = auth_service.local_login(self.container, "owner", "secret", Response())
        identity = self.container.store.get_admin_identity("local:owner")

        self.assertFalse(disabled["totp_enabled"])
        self.assertEqual(disabled["enabled_owner_count"], 0)
        self.assertFalse(identity["totp_enabled"])
        self.assertEqual(identity["totp_secret_cipher"], "")
        self.assertEqual(session["role"], ROLE_OWNER)
        self.assertFalse(session["totp_enabled"])
        self.assertFalse(session.get("requires_totp", False))

    def test_admin_audit_records_and_lists_events(self):
        session = {
            "subject": "local:owner",
            "role": ROLE_OWNER,
            "auth_method": "local",
            "telegram_id": 0,
            "username": "owner",
            "first_name": "Local Admin",
        }
        record_admin_action(
            self.container,
            session,
            action="modules.token_reveal",
            target_type="module",
            target_id="module-1",
            details={"source": "test"},
        )
        events = self.container.store.list_admin_audit_events(limit=10)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["action"], "modules.token_reveal")
        self.assertEqual(events[0]["details"]["source"], "test")

    def _restore_process_env(self, key: str, previous_value: str | None) -> None:
        if previous_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = previous_value


if __name__ == "__main__":
    unittest.main()
