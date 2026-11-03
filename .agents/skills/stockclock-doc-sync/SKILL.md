---
name: stockclock-doc-sync
description: Reconcile StockClock's maintained documentation after a completed development or validation phase changes behavior, acceptance evidence, or a known limitation, or when explicitly auditing documentation against the repository.
---

# StockClock documentation sync

Start with [repository rules](../../../AGENTS.md) and the [documentation map](../../../docs/DOCS_INDEX.md). Use the map to select the subject owners for the actual change.

1. Establish the baseline and the phase delta from the relevant diff or commit range, executable behavior, and validation record. Separate what the code supports, what deterministic checks passed, what was observed at runtime and when, and what is pending.
2. Update the owner of each affected claim. Put capability status and evidence in `PROJECT_STATE.md`, next work and deferred gates in the active roadmap, decisions in `DECISIONS.md`, and SSI-specific caveats in the SSI integration guide. Use the catalog, data contract, dictionary, and UI states for their respective route, semantic, field, and presentation changes. Update navigation when an owner or entry point changes.
3. Follow the [English documentation policy](../../../AGENTS.md#documentation-policy). Update existing owners in English when claims or evidence change. Replace repeated guidance with links. Preserve dated evidence and any exact legacy path, anchor, or text required by consumers. Keep frozen documents outside active navigation.
4. Before merging or deleting documentation, preserve unique current guidance and check references in Markdown, tests, scripts, workflows, and runtime help. Verify paths, anchors, commands, configuration names, and status consistency. Run `git diff --check` and use the governance checker when governance assets changed.

Report the owners updated, checks and outcomes, and any pending acceptance or legacy compatibility constraint.
