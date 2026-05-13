# MobGuard Panel

Central control plane for the split MobGuard architecture.

## What this repo contains

- `api/` — admin API, module ingestion API, review workflow, module registry, quality endpoints
- `web/` — operator panel for queue, modules, rules, data, and quality
- `mobguard_platform/` — storage, protocol helpers, runtime/config support
- `mobguard_core/scoring/` — panel-side scoring pipeline executed after module event ingestion

This repo is the **panel** only. Collector code lives in the separate module repo https://github.com/darkneeed/mobguard-module.git

## Clone

```bash
git clone https://github.com/darkneeed/mobguard-panel.git
cd mobguard-panel
docker compose up -d
```

## Required `.env` keys

- `TG_MAIN_BOT_TOKEN`
- `TG_ADMIN_BOT_TOKEN`
- `TG_ADMIN_BOT_USERNAME`
- `IPINFO_TOKEN`
- `REMNAWAVE_API_TOKEN`

Backward-compatible fallback for older installs is still supported:

- `PANEL_TOKEN` may be used instead of `REMNAWAVE_API_TOKEN`

## Database backend

- `MOBGUARD_DB_BACKEND=sqlite|postgres` selects the staged runtime backend path.
- `sqlite` remains the supported runtime default.
- For migration prep, provide `MOBGUARD_POSTGRES_DSN` or the discrete `MOBGUARD_POSTGRES_*` variables.
- Use `python scripts/migrate_sqlite_to_postgres.py --sqlite-path runtime/bans.db --postgres-dsn ...` to copy the current SQLite operational store into Postgres and validate table counts.

## Local dev without Docker

For real-time UI work with Vite HMR and backend auto-reload, see [docs/local-dev.md](./docs/local-dev.md).

Main entrypoints:

Windows:

```powershell
.\scripts\start-stack.ps1
.\scripts\status-stack.ps1
.\scripts\logs-stack.ps1
.\scripts\stop-stack.ps1
```

Linux/macOS:

```bash
./scripts/start-stack.sh
./scripts/status-stack.sh
./scripts/logs-stack.sh
./scripts/stop-stack.sh
```

The launcher writes merged runtime env, PID files, logs, and audit reports only into ignored `runtime/dev/`.
