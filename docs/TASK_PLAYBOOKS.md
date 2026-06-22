# TASK_PLAYBOOKS.md

## Playbook: Docs-only update

Allowed:
- docs/**

Forbidden:
- runtime code
- tests unless docs tooling requires it
- commit/push unless asked

Validation:
- git diff --check

Report:
- files changed
- sections updated
- inconsistencies found

---

## Playbook: API contract change

Required:
- update backend schema
- update service response builder
- update frontend consumer
- update tests
- update docs/VN_DATA_CONTRACT.md

Validation:
- backend pytest for affected contract
- frontend tests for affected UI
- git diff --check

Forbidden:
- placeholder objects for missing list data
- public endpoint dumps in primary message

---

## Playbook: UI unavailable-state fix

Goal:
If data is missing, render section-level unavailable state. Do not render fake metric rows.

Check:
- status != ok
- object == null
- list.length === 0

Forbidden:
- `Snapshot price -`
- `SSI change - / -%`
- `Session volume unavailable` as metric row

Validation:
- frontend tests
- browser smoke

---

## Playbook: Provider investigation

Goal:
Investigate provider behavior without changing public contract prematurely.

Output:
- endpoint tried
- HTTP status
- response shape
- retryable/non-retryable
- recommendation for future implementation

Forbidden:
- claiming live support before verified
- fallbacking silently