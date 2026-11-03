# VN Task Playbooks

## Purpose

Use these playbooks to keep Codex tasks scoped and consistent with the SSI-first VN dashboard roadmap. Each playbook lists the goal, allowed files, forbidden changes, required docs, validation, and expected report format.

## Playbook: Create/Update Docs System

Goal:

- Update product, contract, design, runbook, and handoff docs without runtime changes.

Allowed files:

- `docs/**`
- `AGENTS.md` only for a small cross-reference if necessary.

Forbidden changes:

- Runtime code.
- Tests, unless docs tooling requires metadata updates.
- Commits or pushes without explicit user confirmation.

Required docs:

- Update affected topic docs and `docs/CHANGELOG.md`.
- Preserve `docs/CHANGELOG.md` flat `[Unreleased]` format.

Validation:

```powershell
git diff --check
```

Expected report:

- Files changed.
- Sections added/updated.
- Validation result.
- Unresolved inconsistencies.
- No commit/push confirmation.

## Playbook: Add Data Quality Summary

Goal:

- Implement Phase 1 Data Quality Summary for watchlist selected ticker and company detail.

Allowed files:

- API/service/schema files needed for summary fields.
- `apps/dsa-web/**` components/tests.
- Relevant backend/frontend tests.
- Docs: `VN_DATA_CONTRACT.md`, `DATA_DICTIONARY.md`, `UI_STATES.md`, `VN_COMPANY_DETAIL_DESIGN.md`, `CHANGELOG.md`.

Forbidden changes:

- Mozyfin/KBS fallback.
- Recommendation wording.
- Silent source blending.

Required docs:

- Document any new summary fields and quality classifications.

Validation:

```powershell
python -m pytest tests/test_vietnam_market_service_no_mozyfin.py -q
python -m pytest tests/test_vietnam_market_service_intraday.py -q
npm.cmd --prefix apps\dsa-web run build
npm.cmd --prefix apps\dsa-web test -- VietnamCompanyResearchPage
npm.cmd --prefix apps\dsa-web test -- VietnamDashboardPage.test.tsx
git diff --check
```

Expected report:

- Data-quality cases covered.
- Tests run.
- Remaining source/field decisions.

## Playbook: Clean Contract/Diagnostics Split

Goal:

- Implement Phase 2 public contract cleanup and diagnostics split.

Allowed files:

- Backend schema/service response builders.
- Frontend consumers/rendering for live sections.
- Contract/UI tests.
- Docs listed in the data contract.

Forbidden changes:

- Placeholder objects for missing list data.
- Endpoint dumps in public status messages.
- Raw provider errors in primary UI.

Required docs:

- `VN_DATA_CONTRACT.md`
- `API_CATALOG.md`
- `DATA_DICTIONARY.md`
- `ERROR_TAXONOMY.md`
- `UI_STATES.md`
- `TEST_STRATEGY.md`

Validation:

```powershell
python -m pytest tests/test_vietnam_market_service_realtime.py -q
python -m pytest tests/test_vietnam_market_service_intraday.py -q
npm.cmd --prefix apps\dsa-web test -- VietnamCompanyResearchPage
npm.cmd --prefix apps\dsa-web test -- VietnamDashboardPage.test.tsx
git diff --check
```

Expected report:

- Before/after contract shapes.
- Diagnostics fields added/moved.
- Backward compatibility notes.

## Playbook: Redesign Company Detail Layout

Goal:

- Implement Phase 3 company detail as a data-quality report.

Allowed files:

- `apps/dsa-web/src/pages/VietnamCompanyResearchPage.tsx`
- Related components/styles/tests.
- API/schema changes only if required by Data Quality Summary.
- Docs: `VN_COMPANY_DETAIL_DESIGN.md`, `UI_STATES.md`, `DATA_DICTIONARY.md`.

Forbidden changes:

- Backend provider changes unrelated to layout.
- Fake module data.
- Primary endpoint dumps.

Required docs:

- Update design doc if layout changes.
- Update changelog for user-visible UI changes.

Validation:

```powershell
npm.cmd --prefix apps\dsa-web run build
npm.cmd --prefix apps\dsa-web test -- VietnamCompanyResearchPage
git diff --check
```

Expected report:

- Layout sections changed.
- UI states covered.
- Screenshots/manual smoke if run.

## Playbook: Investigate SSI Realtime/Trade Tape

Goal:

- Determine whether SSI FastConnect Data can provide usable realtime snapshot and trade tape.

Allowed files:

- Diagnostic scripts/docs.
- Provider methods only if task explicitly asks for implementation.
- Tests for sanitized diagnostics if code changes.

Forbidden changes:

- FC Trading/order/account APIs.
- Silent KBS fallback.
- Claiming live support before verified data exists with status `ok`.

Required docs:

- `SSI_FASTCONNECT_INTEGRATION.md`
- `PROJECT_STATE.md`
- `OBSERVABILITY.md`
- `SECURITY_AND_SECRETS.md`

Validation:

```powershell
git diff --check
```

If runtime changes occur, add targeted backend tests.

Expected report:

- Endpoints tried.
- HTTP status and response shape.
- Retryable/non-retryable classification.
- Whether public unavailable state remains.

## Playbook: Add Provider Field

Goal:

- Add one source-labeled provider field without changing unrelated contract semantics.

Allowed files:

- Provider normalization.
- Service/schema field mapping.
- Frontend display if requested.
- Focused tests.
- `DATA_DICTIONARY.md` and relevant contract docs.

Forbidden changes:

- Parallel provider implementation.
- Hidden fallback.
- Inferred values without source support.

Validation:

```powershell
python -m py_compile <changed_python_files>
python -m pytest <relevant_tests> -q
git diff --check
```

Expected report:

- Field source.
- Nullable behavior.
- UI placement.
- Tests.

## Playbook: Fix UI Unavailable State

Goal:

- Render unavailable sections as concise state blocks instead of fake metric rows.

Allowed files:

- Affected frontend page/component/tests.
- Docs if state semantics change.

Forbidden changes:

- Placeholder metric rows.
- Raw provider error in primary UI.
- Changing provider behavior just to satisfy UI.

Validation:

```powershell
npm.cmd --prefix apps\dsa-web test -- VietnamDashboardPage.test.tsx
npm.cmd --prefix apps\dsa-web test -- VietnamCompanyResearchPage
npm.cmd --prefix apps\dsa-web run build
git diff --check
```

Expected report:

- States fixed.
- Tests updated.
- Remaining uncovered states.

## Playbook: Review API Snapshot vs Docs

Goal:

- Compare live/local API snapshots with documented contract.

Allowed files:

- `.handoff/**` for generated artifacts.
- `docs/**` for documentation updates.

Forbidden changes:

- Runtime changes.
- Test changes.
- Commit/push.
- Secret-bearing artifacts.

Required docs:

- Update `API_CATALOG.md`, `DATA_DICTIONARY.md`, `VN_DATA_CONTRACT.md`, or `PROJECT_STATE.md` if snapshot findings reveal drift.

Validation:

```powershell
git diff --check
```

Expected report:

- Snapshot files reviewed.
- Contract mismatches found.
- Docs updated or deferred.
- Security scan result if handoff artifacts are produced.
