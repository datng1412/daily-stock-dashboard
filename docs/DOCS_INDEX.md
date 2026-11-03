# StockClock documentation index

## Reading order

1. Start with [README](../README.md) for setup and [AGENTS.md](../AGENTS.md) for engineering rules.
2. Read [Project State](PROJECT_STATE.md), [Decisions](DECISIONS.md), and the [active roadmap](VN_DASHBOARD_ROADMAP.md#active-roadmap) before changing implementation.
3. Use the [task template](CODEX_TASK_TEMPLATE.md) and [review checklist](REVIEW_CHECKLIST.md) for scoped work. Read the relevant owner below and verify against code, schemas, configuration, and tests.

## Product and engineering owners

| Subject | Maintained owner | Scope |
| --- | --- | --- |
| Product | [PRD](PRD.md) | Purpose, target users, requirements, boundaries, and proposals |
| Architecture | [Architecture](ARCHITECTURE.md) | Runtime, module ownership, persistence, jobs, and deployment topology |
| Status and acceptance | [Project State](PROJECT_STATE.md) | Capability status, evidence dates, and limitations |
| Priorities | [VN roadmap](VN_DASHBOARD_ROADMAP.md#active-roadmap) | Phase criteria and backlog. The next phase is unassigned. |
| Decisions | [Decisions](DECISIONS.md) | Rationale and active product and engineering guardrails |
| Public VN API | [API catalog](API_CATALOG.md) | Route inventory and compatibility, including VN alert routes |
| Data semantics | [VN data contract](VN_DATA_CONTRACT.md) | Source ownership, freshness, finality, coverage, and null/zero |
| Field definitions | [Data dictionary](DATA_DICTIONARY.md) | Units, field meaning, and provenance |
| Presentation | [UI states](UI_STATES.md) | Loading, freshness, partial, unavailable, and diagnostic behavior |
| SSI integration | [SSI integration](SSI_FASTCONNECT_INTEGRATION.md#current-production-contract) | Provider ownership, configuration, request budgets, and caveats |
| Local VN operations | [VN runbook](RUNBOOK_VN.md) | Live setup, injected test mode, smoke checks, and triage. See [Windows steps](RUNBOOK_LOCAL_WINDOWS.md). |
| VN deployment | [Docker and Render runbook](RUNBOOK_DOCKER_RENDER.md) | Runtime settings, health, and deployment limits |
| Configuration and security | [Security and secrets](SECURITY_AND_SECRETS.md) | Secret handling, auth, and operational boundaries |
| Diagnostics | [Observability](OBSERVABILITY.md) and [Error taxonomy](ERROR_TAXONOMY.md) | Health, failure classification, and safe diagnostics |
| Verification | [Test strategy](TEST_STRATEGY.md) and [Release checklist](RELEASE_CHECKLIST.md) | Deterministic checks, runtime acceptance, and release gates |
| Change history | [Changelog](CHANGELOG.md) | English Unreleased entries and original published release records |
| AI governance | [AGENTS.md](../AGENTS.md) | Collaboration policy, Git boundaries, and routing to the [data integrity](../.agents/skills/market-data-integrity/SKILL.md) and [documentation sync](../.agents/skills/stockclock-doc-sync/SKILL.md) skills |

## Inherited application

The inherited multi-market analysis, backtesting, portfolio, bot, and desktop capabilities have separate configuration and acceptance from StockClock's SSI workspace.

| Subject | Maintained owner |
| --- | --- |
| Setup and configuration | [Inherited configuration guide](full-guide_EN.md) |
| LLM configuration | [LLM guide](LLM_CONFIG_GUIDE_EN.md) and [provider examples](llm-providers.md) |
| Notification routing and setup | [Notifications](notifications.md) |
| Automation and server deployment | [Deployment guide](DEPLOY_EN.md) |
| Bot integration | [Bot guide](bot-command_EN.md) and [Feishu setup](bot/feishu-bot-config.md) |
| Desktop builds | [Desktop packaging](desktop-package.md) |
| Settings help metadata | [Settings help](settings-help.md) |
| Stock index and screening tools | [Tushare symbol lists](TUSHARE_STOCK_LIST_GUIDE.md) and [AlphaSift integration](alphasift-integration.md) |
| Troubleshooting | [FAQ](FAQ_EN.md) |
| Contributing | [Contributing guide](CONTRIBUTING_EN.md) |

## Evidence and history

Code, schemas, configuration, and executable tests establish what is implemented. Dated acceptance records establish what was observed at that time. A documentation review does not establish current provider, credential, entitlement, or deployment health.

For dated investigations, start with [SSI V3 migration](SSI_FASTCONNECT_V3_MIGRATION.md), [SSI capability matrix](SSI_DATA_CAPABILITY_MATRIX.md), or the [prior documentation audit](DOCUMENTATION_AUDIT.md). Prior screen designs and provider qualification records are supporting evidence. The active roadmap owns future work. The [market-data candidate notes](resources/realtime-data/README.md) and [news candidate notes](resources/news-sources/README.md) require approval before provider use.

Some frozen files remain at exact paths for application help, external integrations, or regression checks. Follow the maintained owners above. Earlier phase plans and deleted translations remain in Git history.

## Maintenance

Apply the [English-only policy](../AGENTS.md#documentation-policy). Edit the affected subject owner and link to it from summaries. Preserve dated evidence and required compatibility references. Check links, anchors, and the staged and unstaged scope before handoff.
