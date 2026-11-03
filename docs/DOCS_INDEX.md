# StockClock documentation map

Reviewed 2026-11-02 against clean `main` baseline `0bf5f90f`. This is the navigation and subject-ownership map, not another API contract or roadmap. Start here when entering the repository.

## Reading order for an AI coding task

1. Read [AGENTS.md](../AGENTS.md): scope, security, source integrity, tests, and git boundaries.
2. Read [PROJECT_STATE](PROJECT_STATE.md), active [roadmap](VN_DASHBOARD_ROADMAP.md), and [DECISIONS](DECISIONS.md): accepted capabilities, limitations, and product constraints.
3. Use [task template](CODEX_TASK_TEMPLATE.md), [review checklist](REVIEW_CHECKLIST.md), and the relevant runbook below.
4. Inspect the actual implementation, schema, configuration, and nearby tests for the requested change. Read only relevant topic documents next.

## Subject owners

| Subject | Maintained authority | Supporting reference / boundary |
| --- | --- | --- |
| Product purpose and users | [VN_PRODUCT_SPEC](VN_PRODUCT_SPEC.md) | Personal VN market inspection; neutral facts/signals, no trading advice. [Product offering](VN_PRODUCT_OFFERING.md) is a user overview. |
| Capability status and evidence | [PROJECT_STATE](PROJECT_STATE.md) | Keep implementation, deterministic verification, retained runtime acceptance, and current deployment availability distinct. |
| Next work and deferred work | Active [VN_DASHBOARD_ROADMAP](VN_DASHBOARD_ROADMAP.md) | Its historical phase archive is evidence, not priority. Next product phase is unassigned. |
| Engineering/product decisions | [DECISIONS](DECISIONS.md) | Superseded phase sequencing is marked historical. |
| Architecture and persistence | Current architecture below | Code owners: `api/app.py`, `src/services/`, `data_provider/`, `src/storage.py`. |
| API surface | [API_CATALOG](API_CATALOG.md) | Executable `api/v1/endpoints/` and `api/v1/schemas/` settle signatures; generic alerts use [alerts](alerts.md). Static OpenAPI artifacts may lag. |
| Data semantics | [VN_DATA_CONTRACT](VN_DATA_CONTRACT.md) | [DATA_DICTIONARY](DATA_DICTIONARY.md) owns field meanings/units; schemas and normalization code settle exact shapes. |
| Provider ownership/limitations | Current section of [SSI integration](SSI_FASTCONNECT_INTEGRATION.md) | [Capability matrix](SSI_DATA_CAPABILITY_MATRIX.md) and [remaining audit](SSI_REMAINING_DATA_AUDIT.md) contain dated investigations. |
| UI behavior | [UI_STATES](UI_STATES.md) | Implemented state flow and frontend tests settle behavior; preserve null, stale, partial, and unavailable states. |
| Local setup | [README_VN](README_VN.md), [RUNBOOK_VN](RUNBOOK_VN.md) | [Windows runbook](RUNBOOK_LOCAL_WINDOWS.md); check script signatures before copied commands. |
| Production deployment | [Docker/Render runbook](RUNBOOK_DOCKER_RENDER.md) | `docker/Dockerfile`, `docker/entrypoint.sh`, launcher and CI are executable authority. Compose is not a complete SSI production template. |
| Configuration/security | [SECURITY_AND_SECRETS](SECURITY_AND_SECRETS.md) | `src/config.py`, `src/core/config_registry.py`, `.env.example`; never read out local secret values. |
| Validation and acceptance | [TEST_STRATEGY](TEST_STRATEGY.md), [REVIEW_CHECKLIST](REVIEW_CHECKLIST.md) | `AGENTS.md`, `.github/workflows/ci.yml`, `scripts/ci_gate.sh`, and relevant tests. Historical command names require path checks. |
| Logs and health | [Docker/Render runbook](RUNBOOK_DOCKER_RENDER.md), [SSI integration](SSI_FASTCONNECT_INTEGRATION.md) | `/api/health` proves HTTP readiness, not market-data availability; route-specific health/observability and source freshness are separate. |
| API budgets | [SSI integration](SSI_FASTCONNECT_INTEGRATION.md), [alerts](alerts.md) | Service bounds are not entitlement or contractual rate limits. Cold RS can use 42 exact-date index reads; configure exact scopes and reuse caches. No verified monthly cost model exists. |
| Git and AI governance | [AGENTS.md](../AGENTS.md) | `CLAUDE.md` is the tracked symlink; Copilot instructions are layered supplements. Preserve work, use scoped English commit descriptions, and obtain explicit commit/push authorization. |
| General inherited app | [README](../README.md), [English index](INDEX_EN.md), [Chinese index](INDEX.md) | Multi-market analysis, bots, portfolio, desktop, and AI-report capabilities are not implied VN provider capabilities. |
| Audit findings and remaining gaps | [DOCUMENTATION_AUDIT](DOCUMENTATION_AUDIT.md) | Sixteen-area assessment, evidence scope, limitations, and P0/P1/P2 follow-ups. |

## Current architecture

| Layer | Implementation and responsibility |
| --- | --- |
| Web | `apps/dsa-web/`: React 19, TypeScript 5.9, Vite 7, Tailwind 4; Lightweight Charts 5.2.0 for VN candles, Recharts for analytical views. Routes include `/vietnam`, `/vietnam/company/:ticker`, `/foreign-flow`, `/alerts`. |
| HTTP/startup | `main.py --serve-only` launches FastAPI through `api/app.py`; `server.py` is the ASGI entry. Local required initialization precedes readiness; optional stock-index/SSI startup runs in the background. |
| Application | `src/services/` owns normalization, source/session quality, caches, analytics, and alerts. `api/v1/endpoints/` binds schemas and delegates service work. |
| SSI | `ssi_provider_router.py` selects only `ssi_v3_adapter.py`; `ssi-sdk==3.0.5` is pinned. REST is lazy/process-shared. Streaming has one process-owned lifecycle; bounded existing route recovery does not transfer connection ownership. |
| Alert evaluation | `AlertWorker` invokes completed-data evaluators, persists through the existing repository/storage, deduplicates by session, and uses the existing notification pipeline. Enabling API/UI rule management does not itself schedule evaluation; `main.py` schedule mode wires the worker. |
| Persistence | SQLAlchemy/SQLite in `src/storage.py`: daily rows, news/history, reports, portfolio, conversations, usage, and alert rules/triggers/notifications/cooldowns. Accepted completed foreign-flow files live under `DATA_CACHE_DIR`; provisional room flow and aggregates stay process-local. Optional last-known streaming persistence has a separate stale snapshot contract. |
| Deployment | Multi-stage Docker builds the web app with Node 20 and runs Python 3.11 as `dsa`; FastAPI serves `static/`. `HOME`, database/cache/log paths and `PORT` must be writable/consistent. Use one backend worker for coherent process-local current state. |

The production image Python version is 3.11; inherited Python 3.10 badges are not a certified SSI V3 deployment matrix. Optional legacy Longbridge dependencies are separate and do not authorize VN integration work.

## Evidence and history policy

Implementation is checked in code/schema/config/tests first. Dated retained acceptance establishes what was verified at that time; neither code presence nor documentation review proves current credentials, entitlement, provider uptime, or deployed state. This audit makes no new network/deployment acceptance claim.

The roadmap's archive, V3 migration documents, `VIETNAM_REALTIME_ARCHITECTURE.md`, and named early-phase sections preserve historical designs and failed gates. Read the current production summaries first. Do not execute obsolete V2 commands or restore former Mozyfin/KBS routing from history.

## Maintenance

Edit the subject owner and link to it instead of copying a new contract. When changing fields, update schema/normalizer/tests plus the catalog, contract, and dictionary as applicable; UI state changes also update UI_STATES. Record evidence dates and outstanding gates in PROJECT_STATE/roadmap, and add one flat changelog line. Do not change acceptance status on the strength of prose edits. Check added links/paths and `git diff --check`; run the AI asset checker for governance edits. Preserve dated history with explicit supersession notes.
