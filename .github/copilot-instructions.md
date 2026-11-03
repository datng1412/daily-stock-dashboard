# Repository Instructions

Canonical source: [`AGENTS.md`](../AGENTS.md).

Documentation ownership and reading order: [`docs/DOCS_INDEX.md`](../docs/DOCS_INDEX.md). Use current implementation and dated acceptance evidence; historical phase prose does not override current VN contracts.

If any instruction in this file conflicts with `AGENTS.md`, follow `AGENTS.md`.

## Core Rules

- Respect directory boundaries:
  - Backend: `src/`, `data_provider/`, `api/`, `bot/`
  - Web: `apps/dsa-web/`
  - Desktop: `apps/dsa-desktop/`
  - Deployment/workflows: `scripts/`, `.github/workflows/`, `docker/`
- Do not run `git commit`, `git tag`, or `git push` without explicit user confirmation.
- PR titles should use `<type>: <change summary>` such as `fix: 修复大盘分析历史记录丢失`; use `fix`/`feat`/`refactor`/`docs`/`chore`/`test`/`ci` where possible, and avoid `[codex]`, `codex`, `autocode`, `copilot`, or other tool/agent source prefixes. Treat this as process guidance and do not use title format mismatches as a hard review blocker.
- Do not hardcode secrets, accounts, ports, model names, absolute environment-specific paths, or environment-specific branches.
- Reuse existing modules, configuration entrypoints, scripts, and tests instead of adding parallel implementations.
- For user-visible behavior changes, CLI/API changes, deployment changes, notification changes, or report-structure changes, update the relevant docs and `docs/CHANGELOG.md`.
- In `docs/CHANGELOG.md`, `[Unreleased]` uses one standalone `- [type] description` line per entry. Allowed types are `new feature` / `improvement` / `fix` / `documentation` / `test` / `chore`; do not add category headings.
- Use `README.md` only for project positioning, high-level capabilities, quick start, main entrypoints, and sponsorship/cooperation information; avoid updating README unless the change is homepage-level.
- Put detailed module behavior, page interaction, topic configuration, troubleshooting, field contracts, implementation semantics, and edge cases in the appropriate `docs/*.md` file instead of README.
- When config semantics change, sync `.env.example` and assess impact on local runs, Docker, GitHub Actions, API, Web, and Desktop.

## Validation

- Backend changes: prefer `./scripts/ci_gate.sh`; at minimum run `python -m py_compile` on changed Python files and the closest deterministic tests.
- Web changes: run `cd apps/dsa-web && npm ci && npm run lint && npm run build`.
- Desktop changes: build web first, then desktop if feasible.
- Review work should prioritize CI evidence (`gh pr checks`, workflow logs) before re-running local validation.
- AI governance changes: run `python scripts/check_ai_assets.py`.

## AI Asset Governance

- `AGENTS.md` is the single source of truth for repository AI collaboration rules.
- `CLAUDE.md` must remain a symlink to `AGENTS.md`.
- Use `.github/instructions/*.instructions.md` for path-specific guidance.
- Issue and PR workflows live in `.claude/skills/`. StockClock's Codex skills live in `.agents/skills/`; see [AGENTS.md](../AGENTS.md#2-ai-collaboration-asset-governance) for routing and governance.
