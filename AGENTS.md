# AGENTS.md

## Codex continuity docs

Start with `docs/DOCS_INDEX.md` for subject ownership and the current-versus-historical documentation boundary.

When resuming work with Codex or another coding agent, read these project-management docs before changing implementation:

* `docs/PROJECT_STATE.md` for current repository and Vietnam dashboard state.
* `docs/DECISIONS.md` for active product and engineering decisions.
* `docs/RUNBOOK_VN.md` for live/fixture Vietnam dashboard operations.
* `docs/CODEX_TASK_TEMPLATE.md` for starting a scoped Codex task.
* `docs/REVIEW_CHECKLIST.md` for review and handoff checks.

For Vietnam dashboard work, SSI FastConnect V3 is the sole production market-data provider. Keep live and injected-test evidence explicit; never activate legacy fixtures as runtime fallback. Preserve Wilder/RMA RSI14, neutral labels, and missing-versus-zero integrity. Daily history, delayed sparse 1m candles, streaming quotes/trades, and provisional current foreign flow are separate contracts; read `docs/VN_DATA_CONTRACT.md` before changing their semantics.

### Evidence and completion rules

* Current code, schemas, configuration, and executable tests define implementation. Dated retained acceptance defines what was actually verified; code existence alone does not prove live provider acceptance.
* `PROJECT_STATE.md` owns capability status; the active section of `VN_DASHBOARD_ROADMAP.md` owns priorities. Historical phase sections do not authorize new work or override current contracts.
* `latest_price` normally uses validated SSI daily OHLC. The existing newer-DailyStockPrice degradation is explicitly labelled partial when history fails freshness; do not remove or broaden it based on old enrichment-only prose.
* Completed DailyStockPrice history owns accepted foreign flow. Current `ForeignRoomMessage` is provisional and never enters completed history or completed-session alerts. Use current SSI-derived membership; never fabricate constituents, fields, timestamps, zeros, or provider fallback.
* Keep provider connection ownership in the process-shared lifecycle. Routes may use existing bounded recovery/lease mechanisms; do not create clients or independent streams per request.
* Definition of Done: scoped implementation and contracts agree; relevant deterministic checks pass; required runtime/visual acceptance is evidenced or explicitly pending; docs record limitations; unrelated work and secrets are preserved. Docs-only work requires path/link, consistency, and diff checks, not provider calls or product builds.
* Inspect working/staged state first. Preserve unrelated changes. Do not stage without user authorization, and do not reset, restore, clean, or stash user work to simplify a task.

After each VN dashboard implementation or validation phase, Codex must update the relevant roadmap/docs with any newly discovered limitations, known issues, data-source caveats, validation findings, or deferred tasks. Do this before reporting the phase as complete. Prefer `docs/VN_DASHBOARD_ROADMAP.md` for roadmap/backlog issues, `docs/SSI_FASTCONNECT_INTEGRATION.md` for SSI-specific caveats, and `docs/CHANGELOG.md` for user-visible documentation changes. Do not silently leave important findings only in chat output.

Before using any `docs/resources/` provider, ask for explicit approval and summarize auth, rate-limit, timestamp, and data/price semantics.

This file defines the default development workflow for this repository. Its purpose is to reduce repeated communication, reduce rework, and keep changes aligned with the current project structure.

If this file conflicts with executable scripts, workflows, or the actual current codebase, trust the executable implementation first. When making related changes, update the documentation accordingly so the rules do not continue to drift.

## 0. Role and product lens for Vietnam dashboard work

For Vietnam dashboard tasks, Codex must act as both:

1. A senior software engineer
2. A senior frontend/web product designer

The product is a Vietnamese stock market dashboard for retail investors. Every implementation should be reviewed from three angles:

* Engineering quality: correctness, maintainability, safe fallbacks, tests, API compatibility, and clear data-source semantics.
* Web/product design quality: scanability, visual hierarchy, responsive layout, clean UI, low clutter, and understandable labels.
* Stock-market usefulness: neutral interpretation, no buy/sell hype, clear uncertainty, clear cache/live/fallback state, and practical market context.

For stock-related UI or API behavior:

* Separate fact, signal, and interpretation.
* Do not present technical indicators as standalone buy/sell recommendations.
* Prefer neutral labels such as `Strong`, `Improving`, `Neutral`, `Weakening`, `Risk elevated`, and `Data unavailable`.
* Consider VN-Index/VN30 context, sector rotation, liquidity, foreign flow when available, ex-dividend effects, and timestamp freshness.
* Avoid fake precision and avoid language that looks like financial advice.

## 1. Hard rules

* Follow the existing directory boundaries:

  * Backend logic should primarily live in `src/`, `data_provider/`, `api/`, and `bot/`.
  * Web frontend changes belong in `apps/dsa-web/`.
  * Desktop app changes belong in `apps/dsa-desktop/`.
  * Deployment and pipeline changes belong in `scripts/`, `.github/workflows/`, and `docker/`.
* Use environment variables only. Do not print env values. Do not log tokens. Do not include credentials in tests, docs, examples, errors, or output.
* Do not run `git commit`, `git tag`, or `git push` without explicit confirmation.
* Commit messages must be written in English. Do not add `Co-Authored-By`.
* Do not hardcode secrets, accounts, paths, model names, ports, or environment-specific logic.
* Prefer reusing existing modules, configuration entry points, scripts, and tests. Do not create parallel implementations unnecessarily.
* By default, prioritize stability over “convenient cleanup.” Avoid unrelated refactors, abstractions, or infrastructure migrations unless they are directly required by the current task.
* When adding a new configuration option, also update `.env.example` and the related documentation.
* When changing user-visible capabilities, CLI/API behavior, deployment methods, notification behavior, or report structure, also update the relevant documentation and `docs/CHANGELOG.md`.
* The `[Unreleased]` section in `docs/CHANGELOG.md` must use a flat format. Each item must be one standalone line using this format: `- [type] description`. Allowed types are: `new feature` / `improvement` / `fix` / `documentation` / `test` / `chore`. Do not add `### category headings` inside `[Unreleased]`, to reduce merge conflicts across concurrent PRs.
* `README.md` is only for project positioning, core capability overview, quick start, main entry points, sponsorship/cooperation, and other homepage-level information. Avoid updating README unless necessary, to prevent continuous bloat.
* More detailed module behavior, page interactions, topic-specific configuration, troubleshooting instructions, field contracts, implementation semantics, and boundary conditions should be documented in the corresponding `docs/*.md` or topic-specific documentation instead of README.
* When changing either English or Chinese bilingual documentation, evaluate whether the other version also needs to be synchronized. If it is not synchronized, explain why in the delivery notes.
* Comments, docstrings, and log messages should prioritize clarity and accuracy. English is not strictly required, but the language should stay consistent with the surrounding file context.

## 1.1 PR title convention, non-blocking recommendation

* Recommended PR title format: `<type>: <change summary>`, for example `fix: restore missing market analysis history`. Preferred types are `fix` / `feat` / `refactor` / `docs` / `chore` / `test` / `ci`.
* The title should describe the actual change. Avoid adding `[codex]`, `codex`, `autocode`, `copilot`, or other tool/agent source prefixes.
* This convention is only for collaboration readability and consistency. It should not be treated as a standalone review blocker.

## 2. AI collaboration asset governance

* `AGENTS.md` is the single source of truth for AI collaboration rules in this repository.
* `CLAUDE.md` must be a symlink pointing to `AGENTS.md`, for compatibility with the Claude ecosystem.
* `.github/copilot-instructions.md` and `.github/instructions/*.instructions.md` are mirrors or layered supplements for GitHub Copilot / Coding Agent. If they conflict with this file, `AGENTS.md` takes precedence.
* The project-specific Codex workflows live in `.agents/skills/`. Use [market-data-integrity](.agents/skills/market-data-integrity/SKILL.md) when reviewing changes or regressions in VN market-data semantics. Use [stockclock-doc-sync](.agents/skills/stockclock-doc-sync/SKILL.md) when a completed phase changes documented behavior, acceptance, or limitations, or when auditing those claims. Follow each skill's evidence checks and use [DOCS_INDEX](docs/DOCS_INDEX.md) to find the maintained authority.
* Existing issue and PR workflows live in `.claude/skills/`. Treat their `.claude/reviews/` outputs as local artifacts by default.
* The root-level `SKILL.md` and `docs/openclaw-skill-integration.md` are product or external integration documentation. They are not the source of truth for repository collaboration rules.
* When the user requests delegation or a high-risk cross-layer change warrants a separate review, use a built-in subagent for a bounded, independent check when the session permits it. Give it the scope, relevant contract, and expected evidence. Request file/line findings and checks run or pending, avoid concurrent edits to the same files, and verify its findings before incorporating them.
* When a recurring workflow, repeated failure, or specialized review need emerges, evaluate reuse first. Add or update a repository skill or agent only when repository evidence demonstrates a reusable need that current capabilities cannot meet, the scope is clear and distinct, the result can be validated, and the benefit justifies maintenance. Keep policy here and the detailed workflow in one skill. Keep user-level configuration untouched and obtain explicit approval before installing external capabilities or dependencies.
* When modifying AI collaboration governance assets, run:

```bash
python scripts/check_ai_assets.py
```

## 3. Repository overview

* StockClock's VN product is a personal, data-quality-first SSI market inspection dashboard with Foreign Flow, breadth, sectors, relative strength, and completed-session alerts. The inherited A-share/HK/US AI-report, portfolio, bot, and desktop subsystems remain in the repository; their features and provider fallbacks are not automatically VN product capabilities.
* Main flow: fetch data -> technical analysis / news retrieval -> LLM analysis -> generate report -> send notifications.
* Key entry points:

  * `main.py`: main entry point for analysis tasks
  * `server.py`: FastAPI service entry point
  * `apps/dsa-web/`: web frontend
  * `apps/dsa-desktop/`: Electron desktop app
  * `.github/workflows/`: CI, release, and daily task workflows
* Core responsibilities:

  * `src/core/`: main process orchestration
  * `src/services/`: business service layer
  * `src/repositories/`: data access layer
  * `src/reports/`: report generation
  * `src/schemas/`: schemas and data structures
  * `data_provider/`: multi-source data adapters and fallbacks
  * `api/`: FastAPI API
  * `bot/`: bot integrations
  * `scripts/`: local scripts
  * `.github/scripts/`: GitHub automation scripts
  * `tests/`: pytest tests
  * `docs/`: documentation and notes

## 4. Common commands

### Run the application

```bash
python main.py
python main.py --debug
python main.py --dry-run
python main.py --stocks 600519,hk00700,AAPL
python main.py --market-review
python main.py --schedule
python main.py --serve
python main.py --serve-only
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Backend validation

```bash
pip install -r requirements.txt
pip install flake8 pytest
./scripts/ci_gate.sh
python -m pytest -m "not network"
python -m py_compile <changed_python_files>
```

### Web / Desktop

```bash
cd apps/dsa-web
npm ci
npm run lint
npm run build

cd ../dsa-desktop
npm install
npm run build
```

### PR / CI evidence

```bash
gh pr view <pr_number>
gh pr checks <pr_number>
gh run view <run_id> --log-failed
```

## 5. Default workflow

1. First determine the task type: `fix / feat / refactor / docs / chore / test / review`.
2. Read the existing implementation, configuration, tests, scripts, workflows, and documentation before making changes.
3. Identify the change boundary: backend / API / Web / Desktop / Workflow / Docs / AI collaboration assets.
4. Check whether the task touches high-risk areas: configuration semantics, API / Schema, data-source fallback, report structure, authentication, scheduling, release process, or desktop startup flow.
5. Make the smallest change directly related to the current task. Do not bundle unrelated refactors.
6. If documentation, scripts, or workflows are inconsistent with the code, trust the actual code and workflows first, then decide whether to update documentation as part of the task.
7. After making changes, run the checks defined in the validation matrix below.
8. For Vietnam dashboard changes, additionally review the result from three angles: engineering quality, web/product design quality, and stock-market usefulness.
9. The final delivery should usually explain:

   * What changed
   * Why it changed
   * Validation status
   * Unverified items
   * Risks
   * Rollback method

## 6. Validation matrix

### CI coverage principles

The current repository CI mainly includes:

| Check           | Source                                | Description                                                                                             | Blocking             |
| --------------- | ------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------- |
| `ai-governance` | `.github/workflows/ci.yml`            | Validates the relationship among `AGENTS.md`, `CLAUDE.md`, `.github` instructions, and `.claude/skills` | Yes                  |
| `backend-gate`  | `.github/workflows/ci.yml`            | Runs `./scripts/ci_gate.sh`                                                                             | Yes                  |
| `docker-build`  | `.github/workflows/ci.yml`            | Docker build and key module import smoke checks                                                         | Yes                  |
| `web-gate`      | `.github/workflows/ci.yml`            | Runs `npm run lint` and `npm run build` when frontend changes are involved                              | Yes, when triggered  |
| `network-smoke` | `.github/workflows/network-smoke.yml` | Runs `pytest -m network` and `scripts/test.sh quick`                                                    | No, observation only |
| `pr-review`     | `.github/workflows/pr-review.yml`     | PR static checks, AI review, and auto-labeling                                                          | No, auxiliary        |

If the PR already has matching CI results, directly reference the CI conclusion. If CI does not cover the change surface, or if the local environment differs significantly from CI, explain the additional local validation and the remaining gaps.

### Checks by change surface

* Python backend changes:

  * Scope: `main.py`, `src/`, `data_provider/`, `api/`, `bot/`, `tests/`
  * Preferred check: `./scripts/ci_gate.sh`
  * Minimum requirement: `python -m py_compile <changed_python_files>`
  * If the change affects API behavior, task orchestration, report generation, notification sending, data-source fallback, authentication, or scheduling, the delivery notes must state whether the corresponding path was covered.

* Web frontend changes:

  * Scope: `apps/dsa-web/`
  * Default check: `cd apps/dsa-web && npm ci && npm run lint && npm run build`
  * If the change involves API integration, routing, state management, Markdown/chart rendering, or authentication state, the delivery notes must clearly explain the integration surface and any uncovered risks.

* Desktop app changes:

  * Scope: `apps/dsa-desktop/`, `scripts/run-desktop.ps1`, `scripts/build-desktop*.ps1`, `scripts/build-*.sh`, `docs/desktop-package.md`
  * Default check: build the Web app first, then build the desktop app.
  * If full validation is limited by platform constraints, clearly state whether the Web build output, Electron build, and Release workflow impact were validated.

* API / Schema / authentication integration changes:

  * Scope: `api/**`, `src/schemas/**`, `src/services/**`, `apps/dsa-web/**`, `apps/dsa-desktop/**`
  * At minimum, run the corresponding backend validation and affected client build validation.
  * If the change involves login, cookies, sessions, polling status, field additions/removals, or enum changes, clearly state the compatibility impact.

* Documentation and governance file changes:

  * Scope: `README.md`, `docs/**`, `AGENTS.md`, `.github/copilot-instructions.md`, `.github/instructions/**`, `.claude/skills/**`
  * Code tests are not mandatory.
  * Verify that commands, configuration names, filenames, and workflow names match the actual repository.
  * When changing AI collaboration governance assets, run `python scripts/check_ai_assets.py`.

* Workflow / script / Docker changes:

  * Scope: `.github/**`, `scripts/**`, `docker/**`
  * Run the closest local validation for the affected change surface.
  * In the delivery notes, explain which pipeline, release path, or deployment path was affected.
  * If Docker or GitHub Actions validation was not run, clearly state the reason and potential risk.

* Network or third-party dependency changes:

  * First run offline or deterministic checks.
  * Prioritize confirming that timeout, retry, fallback, error messages, and degradation paths still work.
  * If online validation was not run, clearly state the reason.

## 7. Stability guardrails

* Configuration and runtime entry points:

  * When modifying `.env` semantics, default values, CLI arguments, service startup behavior, or scheduling semantics, evaluate the impact on local runtime, Docker, GitHub Actions, API, Web, and Desktop.
  * New configuration should preferably follow this rule: “works without configuration, enhanced when configured.” Avoid stacking switches and mutually exclusive modes.

* Data sources and fallback:

  * When modifying `data_provider/`, pay attention to data-source priority, failure degradation, field normalization, cache behavior, and timeout strategy.
  * A single data-source failure should not bring down the entire analysis flow unless the requirement explicitly asks for fail-fast behavior.

* API / Web / Desktop compatibility:

  * When changing API, Schema, authentication, or report payloads, check backend, Web, and Desktop compatibility together.
  * Prefer adding fields, preserving old fields, or providing a compatibility layer. Avoid silently breaking existing clients.

* Reports / Prompts / Notifications:

  * When changing report structure, prompts, extractors, notification templates, or bot flows, check whether upstream inputs and downstream consumers remain compatible.
  * A single notification channel failure should not bring down the main analysis flow unless the requirement explicitly asks for fail-fast behavior.
  * When modifying `EXTRACT_PROMPT` in `src/services/image_stock_extractor.py`, include the complete latest prompt in the PR description.

* Workflows / Release / Packaging:

  * When modifying automatic tags, Release, Docker publishing, daily analysis, or desktop packaging flows, evaluate trigger conditions, artifact paths, permission boundaries, and rollback methods.
  * Automatic tagging should remain opt-in by default: version updates are triggered only when the commit title contains `#patch`, `#minor`, or `#major`, unless the requirement explicitly asks to change the release strategy.

## 8. Issue / PR / Skill workflow

* The repository already has the following skills. Reuse them when appropriate:

  * `.claude/skills/analyze-issue/SKILL.md`
  * `.claude/skills/analyze-pr/SKILL.md`
  * `.claude/skills/fix-issue/SKILL.md`
* If the task is clearly issue analysis, PR review, or issue fixing, follow the corresponding skill first and save outputs to `.claude/reviews/`.
* Commands, templates, validation order, and delivery structure inside skills must remain consistent with `AGENTS.md`.
* Skills must not run `git pull`, `git push`, `git tag`, `gh pr create`, or any other operation that changes the remote or current branch state by default. These operations require user confirmation.
* Default PR review order:

  1. Necessity
  2. Relevance
  3. Title suggestion, using `<type>: <change summary>` and no tool/agent prefix. This is not a hard blocker.
  4. Description completeness, checked against `.github/PULL_REQUEST_TEMPLATE.md`
  5. Validation evidence
  6. Implementation correctness
  7. Merge decision
* For `fix` PRs, explain:

  * Original issue
  * Root cause
  * Fix point
  * Regression risk
* Merge-blocking conditions:

  * Correctness or security issue
  * Blocking CI failure
  * Substantial contradiction between PR description and actual changes
  * Missing rollback plan

## 9. Delivery and release

* Default delivery structure:

  * `What changed`
  * `Why it changed`
  * `Validation status`
  * `Unverified items`
  * `Risks`
  * `Rollback method`
* For `docs` tasks, it is acceptable to write: `Docs only, tests not run`. Still explain whether commands and filenames were checked.
* Automatic tagging is not triggered by default. It only runs when the commit title contains `#patch`, `#minor`, or `#major`.
* Manual tags must use annotated tags.
* User-visible changes should preferably be merged through PRs, with labels and validation notes completed.
