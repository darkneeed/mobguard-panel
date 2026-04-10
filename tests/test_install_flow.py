import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _find_usable_shell():
    candidates = []
    shell = shutil.which("sh")
    if shell:
        candidates.append(shell)

    if os.name == "nt":
        candidates.extend(
            [
                r"C:\Program Files\Git\bin\sh.exe",
                r"C:\Program Files\Git\usr\bin\sh.exe",
            ]
        )

    for candidate in candidates:
        if not candidate or not os.path.exists(candidate):
            continue
        try:
            result = subprocess.run(
                [candidate, "-c", "exit 0"],
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if result.returncode == 0:
            return candidate
    return None


POSIX_SHELL = _find_usable_shell()


@unittest.skipUnless(POSIX_SHELL, "usable POSIX shell is unavailable")
class InstallFlowTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp(prefix="mobguard-install-")
        self.root = Path(self.temp_dir)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.command_log = self.root / "command.log"
        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir(exist_ok=True)

        shutil.copy2(PROJECT_ROOT / "install.sh", self.root / "install.sh")
        shutil.copy2(PROJECT_ROOT / ".env.example", self.root / ".env.example")
        shutil.copy2(PROJECT_ROOT / "runtime" / "config.json", runtime_dir / "config.json")

        (self.root / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
        (self.root / "mobguard.py").write_text("print('mobguard')\n", encoding="utf-8")

        self._make_executable(self.root / "install.sh")
        self._write_stub(
            "docker",
            """#!/usr/bin/env sh
set -eu
log_file="${TEST_LOG:?}"

if [ "${1:-}" = "compose" ] && [ "${2:-}" = "version" ]; then
  printf '%s\\n' 'Docker Compose version v2.0.0'
  exit 0
fi

if [ "${1:-}" = "compose" ] && [ "${2:-}" = "up" ]; then
  printf '%s\\n' 'compose up -d --build' >> "$log_file"
  exit 0
fi

if [ "${1:-}" = "compose" ] && [ "${2:-}" = "ps" ]; then
  printf '%s\\n' 'compose ps' >> "$log_file"
  exit 0
fi

printf 'unsupported docker call: %s\\n' "$*" >&2
exit 1
""",
        )
        self._write_stub(
            "caddy",
            """#!/usr/bin/env sh
set -eu
printf '%s\\n' 'v2.0.0'
""",
        )

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_existing_asn_db_allows_empty_maxmind_key(self):
        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir(exist_ok=True)
        (runtime_dir / "GeoLite2-ASN.mmdb").write_bytes(b"existing-mmdb")
        self._write_env(required_tokens=True, maxmind_key="")

        result = self._run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Найден существующий ASN-источник", result.stdout + result.stderr)
        self.assertIn("compose up -d --build", self._read_log())

    def test_missing_asn_db_downloads_when_maxmind_key_is_present(self):
        if os.name == "nt":
            self.skipTest("Git sh on Windows does not reliably resolve curl/tar test stubs")
        self._write_env(
            required_tokens=True,
            maxmind_key="test-maxmind-key",
            extra_values={"ASN_DB_PROVIDER": "maxmind"},
        )
        self._write_stub(
            "curl",
            """#!/usr/bin/env sh
set -eu
output=''

while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    output="$2"
    shift 2
    continue
  fi
  shift
done

[ -n "$output" ] || exit 1
printf '%s' 'archive' > "$output"
""",
        )
        self._write_stub(
            "tar",
            """#!/usr/bin/env sh
set -eu
dest=''

while [ "$#" -gt 0 ]; do
  if [ "$1" = "-C" ]; then
    dest="$2"
    shift 2
    continue
  fi
  shift
done

[ -n "$dest" ] || exit 1
mkdir -p "$dest/GeoLite2-ASN_FAKE"
printf '%s' 'mmdb' > "$dest/GeoLite2-ASN_FAKE/GeoLite2-ASN.mmdb"
""",
        )

        result = self._run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "runtime" / "GeoLite2-ASN.mmdb").exists())
        self.assertIn("Скачиваю GeoLite2-ASN.mmdb с MaxMind", result.stdout + result.stderr)
        self.assertIn("compose up -d --build", self._read_log())

    def test_oxl_provider_downloads_dual_mmdb_files(self):
        if os.name == "nt":
            self.skipTest("Git sh on Windows does not reliably resolve curl/unzip test stubs")
        self._write_env(
            required_tokens=True,
            maxmind_key="",
            extra_values={"ASN_DB_PROVIDER": "oxl"},
        )
        self._write_stub(
            "curl",
            """#!/usr/bin/env sh
set -eu
output=''

while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    output="$2"
    shift 2
    continue
  fi
  shift
done

[ -n "$output" ] || exit 1
printf '%s' 'zip' > "$output"
""",
        )
        self._write_stub(
            "unzip",
            """#!/usr/bin/env sh
set -eu
archive=''
dest=''

while [ "$#" -gt 0 ]; do
  case "$1" in
    -d)
      dest="$2"
      shift 2
      ;;
    -*)
      shift
      ;;
    *)
      archive="$1"
      shift
      ;;
  esac
done

[ -n "$archive" ] || exit 1
[ -n "$dest" ] || exit 1
mkdir -p "$dest"
case "$archive" in
  *ipv4.zip) printf '%s' 'ipv4-mmdb' > "$dest/source-ipv4.mmdb" ;;
  *ipv6.zip) printf '%s' 'ipv6-mmdb' > "$dest/source-ipv6.mmdb" ;;
  *) exit 1 ;;
esac
""",
        )

        result = self._run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "runtime" / "GeoLite2-ASN-IPv4.mmdb").exists())
        self.assertTrue((self.root / "runtime" / "GeoLite2-ASN-IPv6.mmdb").exists())
        self.assertIn("Скачиваю ASN-базы OXL", result.stdout + result.stderr)
        self.assertIn("compose up -d --build", self._read_log())

    def test_dbip_provider_downloads_mmdb_file(self):
        self._write_env(
            required_tokens=True,
            maxmind_key="",
            extra_values={"ASN_DB_PROVIDER": "dbip"},
        )
        self._write_stub(
            "curl",
            """#!/usr/bin/env sh
set -eu
output=''

while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    output="$2"
    shift 2
    continue
  fi
  shift
done

[ -n "$output" ] || exit 1
printf '%s' 'dbip-archive' > "$output"
""",
        )
        self._write_stub(
            "gzip",
            """#!/usr/bin/env sh
set -eu
if [ "${1:-}" = "-dc" ]; then
  printf '%s' 'dbip-mmdb'
  exit 0
fi
if [ "${1:-}" = "-t" ]; then
  exit 0
fi
exit 1
""",
        )
        self._write_stub(
            "date",
            """#!/usr/bin/env sh
set -eu
if [ "$#" -eq 2 ] && [ "$1" = "-u" ] && [ "$2" = "+%Y-%m" ]; then
  printf '%s\\n' '2026-04'
  exit 0
fi
if [ "$#" -eq 2 ] && [ "$1" = "-u" ] && [ "$2" = "+%Y-%m-01" ]; then
  printf '%s\\n' '2026-04-01'
  exit 0
fi
if [ "$#" -ge 4 ] && [ "$1" = "-u" ] && [ "$2" = "-d" ]; then
  printf '%s\\n' '2026-03'
  exit 0
fi
exit 1
""",
        )

        result = self._run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "runtime" / "GeoLite2-ASN.mmdb").exists())
        self.assertIn("Скачиваю ASN-базу DB-IP Lite", result.stdout + result.stderr)
        self.assertIn("compose up -d --build", self._read_log())

    def test_iptoasn_provider_downloads_combined_tsv(self):
        if os.name == "nt":
            self.skipTest("Git sh on Windows does not reliably resolve curl/gzip test stubs")
        self._write_env(
            required_tokens=True,
            maxmind_key="",
            extra_values={"ASN_DB_PROVIDER": "iptoasn"},
        )
        self._write_stub(
            "curl",
            """#!/usr/bin/env sh
set -eu
output=''

while [ "$#" -gt 0 ]; do
  if [ "$1" = "-o" ]; then
    output="$2"
    shift 2
    continue
  fi
  shift
done

[ -n "$output" ] || exit 1
printf '%s' 'iptoasn-gzip' > "$output"
""",
        )
        self._write_stub(
            "gzip",
            """#!/usr/bin/env sh
set -eu
if [ "${1:-}" = "-t" ]; then
  exit 0
fi
exit 1
""",
        )

        result = self._run_install()

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((self.root / "runtime" / "ip2asn-combined.tsv.gz").exists())
        self.assertIn("Скачиваю ASN-базу IPtoASN", result.stdout + result.stderr)
        self.assertIn("compose up -d --build", self._read_log())

    def test_missing_asn_db_without_key_warns_and_finishes_preparation(self):
        runtime_dir = self.root / "runtime"
        runtime_dir.mkdir(exist_ok=True)
        config_payload = '{"settings": {"shadow_mode": true}, "admin_tg_ids": [1]}\n'
        db_payload = b"sqlite-placeholder"

        (self.root / ".env").write_text(
            "\n".join(
                [
                    "TG_MAIN_BOT_TOKEN=",
                    "TG_ADMIN_BOT_TOKEN=",
                    "TG_ADMIN_BOT_USERNAME=",
                    "PANEL_TOKEN=",
                    "IPINFO_TOKEN=",
                    "MAXMIND_LICENSE_KEY=",
                    "ASN_DB_PROVIDER=manual",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        (runtime_dir / "config.json").write_text(config_payload, encoding="utf-8")
        (runtime_dir / "bans.db").write_bytes(db_payload)

        result = self._run_install()
        output = result.stdout + result.stderr

        self.assertEqual(result.returncode, 0, output)
        self.assertIn("ASN-база не найдена", output)
        self.assertIn("Подготовительный этап завершён", output)
        self.assertTrue((runtime_dir / "health").exists())
        self.assertEqual((runtime_dir / "config.json").read_text(encoding="utf-8"), config_payload)
        self.assertEqual((runtime_dir / "bans.db").read_bytes(), db_payload)
        self.assertNotIn("compose up -d --build", self._read_log())

    def _run_install(self):
        env = os.environ.copy()
        env["PATH"] = str(self.bin_dir).replace("\\", "/") + ":" + env.get("PATH", "").replace(";", ":")
        env["TEST_LOG"] = str(self.command_log)
        return subprocess.run(
            [POSIX_SHELL, str(self.root / "install.sh")],
            cwd=self.root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )

    def _write_env(self, required_tokens, maxmind_key, extra_values=None):
        values = {
            "TG_MAIN_BOT_TOKEN": "tg-main" if required_tokens else "",
            "TG_ADMIN_BOT_TOKEN": "tg-admin" if required_tokens else "",
            "TG_ADMIN_BOT_USERNAME": "adminbot" if required_tokens else "",
            "PANEL_TOKEN": "panel-token" if required_tokens else "",
            "IPINFO_TOKEN": "ipinfo-token" if required_tokens else "",
            "MAXMIND_LICENSE_KEY": maxmind_key,
        }
        if extra_values:
            values.update(extra_values)
        payload = "".join(f"{key}={value}\n" for key, value in values.items())
        (self.root / ".env").write_text(payload, encoding="utf-8")

    def _write_stub(self, name, content):
        path = self.bin_dir / name
        path.write_text(content, encoding="utf-8", newline="\n")
        self._make_executable(path)

    def _make_executable(self, path):
        mode = path.stat().st_mode
        path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    def _read_log(self):
        if not self.command_log.exists():
            return ""
        return self.command_log.read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
