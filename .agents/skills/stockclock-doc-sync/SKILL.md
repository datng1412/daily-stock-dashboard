---
name: stockclock-doc-sync
description: Reconcile StockClock's maintained documentation after a completed development or validation phase changes behavior, acceptance evidence, or a known limitation, or when explicitly auditing documentation against the repository.
---

# StockClock documentation sync

Start with [repository rules](../../../AGENTS.md) and the [documentation map](../../../docs/DOCS_INDEX.md). Use the map to select the subject owners for the actual change.

1. Establish the baseline and the phase delta from the relevant diff or commit range, executable behavior, and validation record. Separate what the code supports, what deterministic checks passed, what was observed at runtime and when, and what is pending.
2. Update the owner of each affected claim. Put capability status and evidence in `PROJECT_STATE.md`, next work and deferred gates in the active roadmap, decisions in `DECISIONS.md`, and SSI-specific caveats in the SSI integration guide. Use the catalog, data contract, dictionary, and UI states for their respective route, semantic, field, and presentation changes. Update navigation when an owner or entry point changes.
3. Check neighboring summaries and applicable translations for contradictory claims. Link to the owner, preserve dated records with supersession notes where needed, and add one flat changelog entry when required. Keep prior acceptance dates attached to the original observation.
4. Verify changed paths, links, command and configuration names, and status consistency. Run `git diff --check` and use the governance checker when governance assets changed. Review the final diff for scope.

Report the owners updated, checks and outcomes, and any pending acceptance or translation follow-up.
