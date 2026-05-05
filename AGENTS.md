# Panel Agent Guide

This repository is the control plane side of MobGuard.

Start here:

1. Read `../ai-docs/README.md`
2. Read `../ai-docs/architecture.md`
3. Read `../ai-docs/workflows.md`
4. Read `../ai-docs/change-map.md`
5. Read local `README.md`
6. Reuse local docs in `docs/` when relevant

## Scope

- This repo owns the FastAPI admin and module-ingest API, SQLite-backed platform/runtime layer, scoring pipeline, and React web UI.
- The collector lives in sibling repo `../module/`.
- If you change module protocol, ingestion payloads, or remote config contract, inspect and usually update `../module/` too.

## Primary Code Paths

- `api/`
- `mobguard_platform/`
- `mobguard_core/scoring/`
- `web/src/`
- `tests/`
- `docs/`

## Service Boundary Rule

Follow `docs/admin-data-architecture.md`:

- prefer domain/service modules over growing facades blindly
- do not re-expand `web/src/pages/DataPage.tsx`, `api/services/data_admin.py`, or `mobguard_platform/store.py` with unrelated behavior unless the change truly belongs there

## Do Not Treat As Source

- `runtime/`
- `web/dist/`
- `web/node_modules/`
- `.env`
- `.env.local.dev`
- `__pycache__/`
- `.pytest_cache/`

## Verification

Backend from this directory:

```bash
pytest -q
```

Frontend from `web/`:

```bash
npm test -- --run
npm run build
```

Useful local flows:

- Windows: `.\scripts\start-stack.ps1`, `.\scripts\status-stack.ps1`, `.\scripts\logs-stack.ps1`, `.\scripts\stop-stack.ps1`
- Linux/macOS: `./scripts/start-stack.sh`, `./scripts/status-stack.sh`, `./scripts/logs-stack.sh`, `./scripts/stop-stack.sh`

## Notes

- The workspace root `mobguard/` is not a git repository.
- Run git commands inside this repo, not from the workspace root.
- `mobguard_core/app.py` is compatibility-oriented; avoid making it the new default home for primary business logic.
