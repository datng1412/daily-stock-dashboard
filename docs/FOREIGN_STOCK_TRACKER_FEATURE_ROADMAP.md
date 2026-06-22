# Foreign-Stock Tracker Feature Roadmap

## Purpose

This roadmap describes a future Vietnamese-first foreign-stock tracking and intelligence platform. It does not describe implemented runtime behavior in the current VN SSI dashboard.

## MVP Phase

Goal:
Create time-to-first-value under 10 minutes while staying read-only, conservative, and useful without execution capability.

MVP deliverables:

- Legal wizard.
- Watchlist.
- CSV/email/PDF/manual import.
- Multi-currency P/L in original currency and VND.
- Basic earnings and dividend alerts.
- Basic overnight digest.
- VI/EN glossary.
- Trust/security center.

Expected validation:

- User can complete onboarding and either create a watchlist or import a portfolio in the first session.
- Legal/residency context is captured before sensitive product paths.
- Portfolio value and P/L show both asset movement and FX movement.
- Every digest and explanation has source/timestamp references.

## 6-12 Month Phase

Goal:
Become a reliable daily-use portfolio tracking layer for serious users.

Deliverables:

- Read-only broker import for selected supported brokers.
- Tax-lot engine.
- Dividend withholding tracker.
- Fee analytics.
- Stronger mobile alerts.
- Deeper web dashboard.

Expected validation:

- Most imported portfolio data can sync without manual correction.
- Dividend and fee records reconcile with source statements.
- Users can export useful year-end summaries.
- Alerts remain useful without causing notification fatigue.

## 1-3 Year Phase

Goal:
Build a moat through data quality, trust, localized explainability, and partner workflows.

Deliverables:

- Advanced tax cockpit.
- FX/funding route estimator.
- Explain-this-stock with cited sources.
- Evidence-based social layer.
- Family/friends portfolio view.
- API/white-label options for broker, advisor, and accountant partners.

Expected validation:

- Premium churn declines as more data is reconciled.
- Serious investors use the product during tax/document seasons.
- Partner workflows have measurable retention or revenue expansion.
- Social content quality stays high because citation and evidence requirements are enforced.

## P0 Feature Priority

P0 features are required for the first credible product:

- Legal wizard and product-safe mode.
- Watchlist and simple research workspace.
- Manual, CSV, email, and PDF import.
- Portfolio ledger with USD and VND views.
- Basic alerts for price, earnings, FX, and dividends.
- Basic overnight digest in Vietnamese.
- Source-linked explanations and glossary.
- Trust/security center.
- Data deletion and export controls.

## P1 Feature Priority

P1 features improve trust, retention, and monetization after MVP:

- Read-only broker import.
- Inbox-to-portfolio reconciliation.
- Tax-lot engine.
- Dividend withholding tracker.
- Fee analytics.
- Document reminders.
- Deeper web dashboard.
- Advanced mobile notifications.
- Portfolio notes and thesis history.

## P2 Feature Priority

P2 features become strategic differentiators after the core data layer works:

- Advanced tax cockpit.
- FX/funding route estimator with compliance caveats.
- Explain-this-stock in short, medium, and deep modes with citations.
- Evidence-based social layer.
- Family/friends portfolio view.
- Partner API and white-label flows.
- Advisor/accountant collaboration.

## Feature Dependencies

| Feature | Depends On | Reason |
| --- | --- | --- |
| Legal wizard | Reviewed compliance knowledge base | Must route users conservatively and avoid legal advice claims. |
| CSV/email/PDF/manual import | Import templates, parser confidence, user review flow | Portfolio truth must not be silently created from uncertain data. |
| Multi-currency P/L | FX source, ledger schema, currency metadata | Users need USD/native and VND views with FX impact separated. |
| Overnight digest | Watchlist/portfolio data, events, news/filing sources, citation layer | Digest must explain what changed while users were offline. |
| Read-only broker import | OAuth/API permissions, broker coverage, read-only scope | Must avoid account actions and risky permissions. |
| Tax-lot engine | Confirmed transactions, corporate actions, FX history | Tax lots are unreliable without complete reconciled records. |
| Dividend withholding tracker | Dividend feed, broker cash records, tax-form status | Withholding and net dividends require cashflow evidence. |
| FX/funding estimator | Fee tables, FX rates, compliance review | Must show scenarios and caveats, not workaround guidance. |
| Explain-this-stock | Fundamentals, filings, transcripts, news, glossary, citation quality | AI explanations must be source-backed and reviewable. |
| Evidence-based social layer | Citation enforcement, moderation, quality scoring | Avoid turning community content into unsourced hype. |

## Do Not Build Yet

Do not build these until legal, licensing, compliance, and operational requirements are explicitly solved:

- Foreign-stock execution.
- Order placement.
- Account opening.
- Cash transfer.
- Asset transfer.
- Custody.
- Margin, derivatives, or leveraged product flows.
- Funding workaround flows.
- Universal legal eligibility claims.
- Tax filing submission without professional/legal review.
- Open social posting without citation and moderation controls.

## Product Sequencing Rationale

The report prioritizes three early moves:

1. Legal map because it solves the Vietnam-specific trust gap.
2. Inbox-to-portfolio reconciliation because it shortens time-to-first-value for existing users.
3. Vietnamese overnight digest because it creates a daily habit around the US time-zone mismatch.

After product-market fit, tax/dividend and FX/funding features can deepen monetization. Long-term, explain-this-stock and evidence-based social can become brand and data moats if the underlying data quality is strong.
