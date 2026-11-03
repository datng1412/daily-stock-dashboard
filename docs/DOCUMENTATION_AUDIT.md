# Repository documentation audit

> Dated baseline. The findings below describe the original audit. Use [DOCS_INDEX](DOCS_INDEX.md) for current ownership and scope.

Review date: 2026-11-02. Baseline: clean `main`, `0bf5f90f` (`fix(vn-alerts): finalize live runtime acceptance`, committed 2026-08-14). Review used local tracked code, tests, deployment/workflows, and retained documentation evidence. No builds, live provider calls, credential tests, or deployment inspection were performed. Runtime acceptance retained in the repository is dated through 2026-08-12.

## Coverage matrix

`COMPLETE` means sufficient for the current scoped documentation subject, not exhaustive certification of the application. Score uses COMPLETE=2, PARTIAL=1, MISSING/OUTDATED/CONTRADICTORY=0; it is a navigation/coverage rubric, not a production-quality score.

| Area | Before | After | Evidence / action and remaining boundary |
| --- | --- | --- | --- |
| Problem statement | PARTIAL | COMPLETE | VN_PRODUCT_SPEC states source-quality inspection; DOCS_INDEX distinguishes personal VN scope from inherited AI analysis. |
| Target users | PARTIAL | COMPLETE | AGENTS and product spec identify personal/retail VN inspection; no claim of licensed public redistribution. |
| MVP/product scope | CONTRADICTORY | COMPLETE | README_VN incorrectly said V2 active and only historical flow; aligned with services and current PROJECT_STATE. Phase-specific specs remain historical. |
| Tech stack | PARTIAL | COMPLETE | Requirements, web package manifest and Docker establish pinned SSI 3.0.5, React/TS/Vite, charts, Python image; DOCS_INDEX maps these. |
| Architecture | PARTIAL | COMPLETE | Added compact layer/owner map, API/startup versus scheduler ownership, cache and streaming process boundaries. |
| Data model | PARTIAL | PARTIAL | Dictionary covers VN DTOs; `src/storage.py` enumerates SQLAlchemy entities. Whole-app ER relationships, migration/version policy and retention inventory remain incomplete. |
| Sources/API contracts | CONTRADICTORY | PARTIAL | Corrected V2/price/news/channel onboarding; catalog and data contract cover active semantics. Long historical sections still need a section-level archival pass. |
| AI coding rules | CONTRADICTORY | COMPLETE | Corrected stale Mozyfin/1H instructions, evidence hierarchy, missing/zero/finality, Definition of Done, and Copilot changelog type drift. Host symlink validation remains a checkout concern. |
| Git strategy | COMPLETE | COMPLETE | AGENTS defines authorization, preservation and English commit rules; no new branching/release policy inferred. |
| Testing/acceptance | OUTDATED | PARTIAL | Current strategy/reading priority added; historical V2-test paragraphs are explicitly non-executable. Some older test/command inventories remain to be reconciled. |
| Security/configuration | COMPLETE | COMPLETE | Existing SECURITY_AND_SECRETS, config registry and environment example; no secret values inspected or new auth claim. |
| Deployment plan | CONTRADICTORY | PARTIAL | Docker/Render runbook matches current image; runbook now warns Compose lacks SSI credential forwarding and retains old Mozyfin configuration. Runtime files unchanged. Hosted deployment remains unverified here. |
| Logging/monitoring | PARTIAL | PARTIAL | Startup stage tracing, health, service observability and freshness paths exist. No unified SLO/alert ownership, rotation/retention or incident policy. |
| Cost/API limits | PARTIAL | PARTIAL | Bounded concurrency/cache and 42-call cold RS cost documented; no verified commercial quota, budget or monthly cost model. |
| Roadmap/state | OUTDATED | COMPLETE | Retained PRODUCTION_READY milestones preserved; review date separated from runtime evidence; no next implementation task assigned. |
| Navigation | PARTIAL | COMPLETE | DOCS_INDEX owns current authority/read order; bilingual indexes and READMEs point to it. |

Coverage: before **12/32 (38%)**; after **26/32 (81%)** under this rubric. Six areas remain PARTIAL. These ratings reflect the inspected entry points and relevant subsystem samples, not a line-by-line certification of every document or endpoint.

## Main contradictions resolved

- README_VN said V2 remained active while `ssi_provider_router.py` routes exclusively to V3. It also used literal V2 subscription examples and omitted the accepted current room-flow product.
- AGENTS/task template/review checklist instructed Mozyfin diagnostics and fixed 1H semantics, contradicting V3 routing and the sparse delayed `1m` chart.
- Enrichment-only prose prohibited the already implemented newer-DailyStockPrice partial-price degradation (`vietnam_market_service.py` daily freshness branch).
- DECISIONS still called Phase 4.0A next, and treated all news as unimplemented. Sequencing is historical; optional local news adapters are explicitly distinguished from default disabled and hosted usage.
- State/roadmap headers dated August 11 already contained August 12 alert acceptance. Review metadata now distinguishes current audit date, baseline commit, and retained runtime evidence.
- Copilot allowed translated changelog type tags while AGENTS required English tags. The supplement now follows the canonical rule.
- Docker Compose still forwards a Mozyfin key, not SSI V3 credentials. Documentation flags the executable mismatch; changing deployment behavior is outside this task.

## Evidence anchors

- `data_provider/ssi_provider_router.py`: sole-V3 capability routing, shared lazy adapter, no fallback.
- `src/services/vietnam_market_service.py`: daily freshness/canonical source, intraday `1m`, source-specific optional status.
- `data_provider/ssi_v3_streaming.py` and current-flow services: process ownership and room snapshot handling.
- `src/services/vietnam_watchlist_alerts.py`, `alert_worker.py`, `alert_service.py`: completed-only gates, cycle cache, persistence/dedup and safe JSON provenance.
- `api/v1/endpoints/stocks.py`, `api/v1/schemas/stocks.py`, generic alert endpoints/schemas: executable signatures; API_CATALOG is the descriptive map.
- Web `App.tsx`, package manifest and VN/Foreign Flow/Alerts pages: routes, chart dependencies and product boundaries.
- `src/storage.py`: persistent entities; `src/config.py` / registry: opt-in defaults for streaming/news/corporate actions and alert scheduling.
- `docker/Dockerfile`, entrypoint, Compose, `api/app.py`, `main.py`, CI and `scripts/check_ai_assets.py`: deployment/startup/test and governance boundaries.
- `0bf5f90f` and current PROJECT_STATE/roadmap: retained alert firing/dedup/API/browser acceptance; broader flow/breadth/sector/RS milestones remain dated evidence.

## Prioritized remaining gaps

| Priority | Gap | Next scoped action |
| --- | --- | --- |
| P0 | None discovered requiring product edits or withdrawal of retained acceptance | Do not treat this documentation review as a fresh provider/deployment certificate. |
| P1 | Compose does not match SSI production setup | Separately authorize deployment-template repair and validate credential forwarding by names/presence only; preserve secrets. |
| P1 | Windows checkout materializes CLAUDE.md as ordinary link text | Restore proper symlink materialization in an appropriately configured checkout, then run the full governance checker; Git already records mode `120000`, so no content or checker change is needed. |
| P1 | Long contracts, dictionary and test strategy mix current paragraphs with early-phase limits | Archive/relabel obsolete section-level instructions, check current schema/route/test inventories, and preserve dated evidence without copying contracts. |
| P1 | Readiness versus data health and multi-process operating limits need an operator acceptance checklist | Extend existing runbooks with SLO/incident ownership, bounded process cleanup, cache restart, and one-worker deployment acceptance. |
| P2 | Whole-app persistence/retention/migrations lack a compact maintained inventory | Extend an existing data/architecture reference from SQLAlchemy models; distinguish local cache files from durable business state. |
| P2 | Commercial API quotas/cost are unverified | Record only approved provider terms and measured route budgets; no guessed free-tier or redistribution claims. |
| P2 | General translated docs and static OpenAPI artifacts can drift | Audit language pairs and generated API inventory separately; no mass rewrite of inherited guides in this phase. |

Recommended next documentation phase: reconcile active API/schema/field and test inventories with the existing contract documents, archiving obsolete V2/early-phase instructions at section boundaries. Do not start a new product implementation phase automatically.

## Validation record

Validation on 2026-11-02:

- `git diff --check`: passed (Git emitted only existing Windows line-ending conversion notices).
- Added relative Markdown links: 59 checked across 21 changed/new Markdown files; zero missing file targets. Existing external URLs and historical anchors were not remotely crawled.
- Scope check: only Markdown documentation/governance changed; no production, schema, dependency, environment, or deployment files changed.
- Added-line credential-pattern scan: zero possible credential assignments/bearer values; configuration names and placeholders are not credentials.
- `python scripts/check_ai_assets.py`: failed at `CLAUDE.md must be a symlink to AGENTS.md`. Git records mode `120000` with target `AGENTS.md`, while this Windows worktree materializes a regular link-text file. The full checker is not reported as passing.
- All five remaining governance checks were invoked independently and passed: Copilot entry, layered instruction inventory, repository skill assets, ignore rules, and tracked artifact exclusions. The checker itself was not modified.
- No product tests/builds, provider calls, credential checks, servers, installs, or deployment probes were run. Starting branch main tracked origin/main with 0/0 divergence; no staging, commit, or push occurred.

## Phase 7 — AI capability audit

Reviewed 2026-11-03 from clean `main` at `4dc1b175`. This section covers repository development capabilities. The earlier documentation coverage score and dated product acceptance use their original baselines.

### Existing capabilities and evidence

- [AGENTS.md](../AGENTS.md) is the only repository instruction file of that name. The tracked `CLAUDE.md` points to it, and [Copilot](../.github/copilot-instructions.md) adds backend, client, and governance instructions. The Windows checkout limitation is recorded below.
- The three [Claude workflows](../.claude/skills/README.md), `analyze-issue`, `analyze-pr`, and `fix-issue`, are readable instruction documents without Codex skill metadata. The existing checker verifies their presence and rule-source references. Slash-command registration and GitHub execution were outside this audit. The root [stock_analyzer](../SKILL.md) describes inherited product behavior.
- The repository started with empty `.agents/` and `.codex/` directories. No repository skill, agent TOML, or project Codex configuration was present in those directories. Installed system skills include Skill Creator. Codex's documented built-ins are `default`, `worker`, and `explorer`. [OpenAI skill conventions](https://learn.chatgpt.com/docs/build-skills), [OpenAI subagent conventions](https://learn.chatgpt.com/docs/agent-configuration/subagents).
- The [task template](CODEX_TASK_TEMPLATE.md), [review checklist](REVIEW_CHECKLIST.md), and [test strategy](TEST_STRATEGY.md) already cover delivery and acceptance. [CI](../.github/workflows/ci.yml) runs the governance and backend gates, Docker build, and frontend lint/build when triggered. [Network smoke](../.github/workflows/network-smoke.yml) and [PR review](../.github/workflows/pr-review.yml) supply supplementary checks. Workflow definitions establish what is configured. This phase did not execute GitHub jobs.

### Skill decisions

| Candidate | Decision and evidence | Trigger and reusable workflow |
| --- | --- | --- |
| [stockclock-doc-sync](../.agents/skills/stockclock-doc-sync/SKILL.md) | Created. The prior audit repaired stale provider, pricing, and acceptance claims across multiple owners. The index identifies those owners and the checklist covers the handoff. The skill adds an evidence-to-owner pass over the phase delta. | Use for an explicit docs audit or when a completed phase changes maintained behavior, acceptance evidence, or limitations. Map changed claims to their owners, reconcile related summaries, and verify links, scope, and evidence dates. |
| [market-data-integrity](../.agents/skills/market-data-integrity/SKILL.md) | Created. Daily price degradation, provisional flow, and completed-session alerts repeatedly depend on lineage across provider, cache, and consumers. Existing contracts and tests define the rules. The skill adds a trace and case-selection procedure. | Use when a VN change or regression affects source, normalization, freshness, finality, coverage, anomalies, or ownership. Trace the affected data and failure path, select deterministic cases, and report the evidence tier. |
| `feature-delivery` | Skipped. AGENTS, the task template, the checklist, and the issue-fix workflow cover this sequence. | Use the existing process for implementation, acceptance, and handoff. Reassess a narrower skill when a repeated delivery gap has concrete evidence. |

### Agent decisions

No custom agent or agent TOML was added. For market-data reviews, `default` can apply the integrity skill to a bounded contract. For architecture reviews, `explorer` can trace ownership and dependencies. For independent acceptance, `worker` can run assigned deterministic checks within the parent session's permissions. For documentation consistency, `default` can use the documentation map and sync skill. The parent sets scope and evidence expectations and reconciles the findings. [AGENTS.md](../AGENTS.md#2-ai-collaboration-asset-governance) owns delegation and future capability criteria.

### Phase 7 validation

- The installed Skill Creator validator accepted both manifests. The local Codex app server (`0.166.0-alpha.5.1`) returned both as enabled repository skills via `skills/list` from the root and `apps/dsa-web`. This was a local discovery probe. Model selection and subagent execution remain unverified.
- Read-only workflow samples separated the triggers. The integrity sample traced fresh DailyOhlc versus explicitly partial newer DailyStockPrice through the watchlist service and API fields, using the existing freshness test assertions as case references. The sync sample mapped the retained VN-ALERT-1 acceptance to PROJECT_STATE, the roadmap, the data contract, and the changelog while preserving its original date. A generic feature or issue handoff uses the existing template and checklist.
- The full AI asset checker reproduced the Windows `CLAUDE.md` symlink failure with `core.symlinks=false`. Git still records mode `120000` with target `AGENTS.md`. The other five checks passed independently.
- All 29 added relative links and their anchors resolved. `git diff --check`, manifest metadata, and the added-line credential-pattern scan passed. The nine-file diff covers AI instructions, the two manifests, and audit/navigation/changelog documentation. Product builds, tests, and live provider acceptance were outside scope.

### Follow-up

Repeat the full governance checker in a symlink-capable checkout. During the next qualifying documentation or market-data task, record whether Codex selects the right skill and produces the expected evidence. Use a concrete review or routing gap to justify any further capability change.

## Frozen compatibility and historical references

The active English index excludes these entries. Keep them where their consumers or retained evidence require them.

| Frozen reference | Reason |
| --- | --- |
| `docs/full-guide.md`, `docs/INDEX.md`, `docs/INDEX_EN.md`, `docs/DEPLOY.md`, `docs/alerts.md`, and `docs/analysis-context-pack.md` | Documentation regression tests check these paths, command strings, or original-language text. Inherited settings also publish links into the old full guide. |
| `docs/LLM_CONFIG_GUIDE.md` | Legacy settings and editor help use its path and anchor IDs. The compatibility page directs readers to the English guide. |
| `SKILL.md` | Original external stock-analysis skill bundle. Preserve its instructions and examples as shipped. |
| `docs/openclaw-skill-integration.md` | Original external skill setup and copyable bundle example. The current external client and authentication integration were outside this review. |
| `docs/docker/zeabur-deployment.md` | Platform-specific deployment record. No current Zeabur acceptance is recorded in this review. |
| Published release entries and pre-policy notes in `docs/CHANGELOG.md` | Release automation and regression tests use the existing release history. Maintained Unreleased entries use English. |

### Consolidation follow-up

- The Windows checkout still materializes `CLAUDE.md` as ordinary link text. The full governance check requires a worktree with symlink support. Git records mode `120000` and target `AGENTS.md`.
- The inherited configuration registry coverage test still reports active `.env.example` keys absent from the registry or its explicit hidden set. The environment template, registry, and test were outside the documentation refactor.
- The maintained SSI integration guide still carries older phase sections. Its current production section and the dated acceptance owners establish the evidence boundary.
