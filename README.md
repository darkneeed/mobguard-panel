# MobGuard Panel

Central control plane for the split MobGuard architecture.

## What this repo contains

- `api/` — admin API, module ingestion API, review workflow, module registry, quality endpoints
- `web/` — operator panel for queue, modules, rules, data, and quality
- `mobguard_platform/` — storage, protocol helpers, runtime/config support
- `mobguard_core/scoring/` — panel-side scoring pipeline executed after module event ingestion

This repo is the **panel** only. Collector code lives in the separate `module/` repo.

## Clone

```bash
git clone <panel-repo-url> panel
cd panel
```

## Required `.env` keys

- `TG_MAIN_BOT_TOKEN`
- `TG_ADMIN_BOT_TOKEN`
- `TG_ADMIN_BOT_USERNAME`
- `IPINFO_TOKEN`
- `REMNAWAVE_API_TOKEN`

Backward-compatible fallback for older installs is still supported:

- `PANEL_TOKEN` may be used instead of `REMNAWAVE_API_TOKEN`

## Test

Backend:

```bash
pytest -q
```

Frontend:

```bash
cd web
npm test -- --run
npm run build
```

## Build

Windows:

```powershell
.\build.ps1
```

Linux/macOS:

```bash
./build.sh
```

What the build script does:

1. creates `.env` from `.env.example` if needed
2. validates required env keys are present
3. ensures `runtime/` and `runtime/health/` exist
4. runs `docker compose build`
5. runs a short smoke-check inside the built `mobguard-api` container

## Run

```bash
docker compose up -d
```

Panel binds the web container to `127.0.0.1:8080` and expects a reverse proxy such as Caddy in front of it.
