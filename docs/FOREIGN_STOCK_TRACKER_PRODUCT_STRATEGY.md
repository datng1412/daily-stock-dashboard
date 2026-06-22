# Foreign-Stock Tracker Product Strategy

## Product Thesis

Vietnamese demand for exposure to foreign assets is real, but broad retail execution and cross-border asset safekeeping are legally and operationally sensitive. The first product layer should therefore be a Vietnamese-first tracking and intelligence platform, not an execution product.

The product should reduce ambiguity for users who want to understand foreign stocks, ETFs, dividends, FX impact, documents, and portfolio movement. Its first promise is not "more trading access"; its first promise is "less ambiguity."

Core user questions:

- Am I allowed to do this in my current legal/residency situation?
- Where did my money go, and what costs or FX effects changed the result?
- Why did my portfolio move while I was asleep?
- What tax, withholding, or documents should I keep?
- Which source explains the event, and can I export an audit trail later?

## Why Vietnam Is Different

Vietnam already has a large and increasingly digital retail investor base. The foreign-stock use case is different from domestic VN stock tracking because each user journey adds cross-border complexity:

- Legal uncertainty for residents, offshore users, ESOP holders, students, expats, and foreign workers.
- Funding and FX friction before a user can even form a reliable portfolio record.
- Dividend withholding, cost basis, tax residence, and year-end documentation.
- English-language filings, news, transcripts, and broker documents.
- US market time-zone mismatch with Vietnam morning routines.
- Multiple brokers, statements, emails, PDFs, and manual imports.
- Low trust in generic international explanations that do not reflect Vietnamese context.

The product opportunity is to localize the intelligence layer without pretending that cross-border execution is simple or universally available.

## Why Start With Tracking And Intelligence Before Execution

Execution and regulated asset safekeeping sit at the highest-risk layer of the value chain. They require licensing, capital flow controls, bank workflows, KYC/AML, tax handling, consumer protection, and broker/custodian partnerships.

Tracking and intelligence can create value earlier and more safely:

- Watchlists, education, and research do not require transaction capability.
- Imports can be read-only and user-confirmed.
- Portfolio analytics can separate price movement, FX movement, fees, dividends, and withholding.
- Legal wizard output can route users to safe product modes instead of pushing a universal path.
- Tax exports can be estimate/export aids rather than professional filings.

The strategy is to win trust first, then consider regulated partnerships only when product-market fit, compliance review, and licensing paths are clear.

## Core Value Proposition

An investment tracking and intelligence platform for Vietnamese users interested in foreign assets.

User-facing value:

- A legal and residency-aware starting point.
- Vietnamese explanations for foreign stocks, ETFs, filings, events, and market movement.
- Multi-currency portfolio truth in both original currency and VND.
- Import and reconciliation from CSV, email, PDF, and manual entry.
- Overnight digest for events that happened during Vietnam sleeping hours.
- Dividend, withholding, tax-document, and cost-basis organization.
- Evidence and source links behind every important explanation.

Business value:

- Starts in a lower-risk non-execution category.
- Builds trust and data depth before monetizing advanced features.
- Creates a long-term moat through localized compliance context, import templates, reconciliation quality, Vietnamese explanations, and audit trails.

## Non-Goals

- No foreign-stock trading, execution, account opening, custody, or order placement in MVP.
- No instructions to bypass capital controls, bank rules, KYC, tax, or FX regulations.
- No legal advice, tax advice, or personalized financial advice.
- No trade recommendation labels, target-price calls, or portfolio action instructions.
- No claim that any funding route is lawful for every user.
- No automatic movement of cash or assets.
- No social feed that encourages unsourced hype or opaque calls.

## Strategic Moat

The moat should not be a generic price chart. International platforms already have charts, quotes, and execution.

Durable differentiation for Vietnamese users:

- Legal-context routing: classify user profile and product-safe mode before encouraging account import.
- Import/reconciliation library: broker statement templates, email parsing, PDF parsing, manual corrections, and audit history.
- Multi-currency ledger: USD/HKD/SGD/etc plus VND view, with FX impact separated from asset impact.
- Tax and dividend recordkeeping: withholding, W-8/tax document reminders, cost-basis lots, and export packs.
- Vietnamese explainability: plain-language summaries at multiple depth levels with citations.
- Morning digest habit: personalized overnight summary aligned with Vietnam time.
- Trust center: read-only scopes, data encryption, source coverage, retention, deletion, and incident transparency.
- Evidence-based community: content ranked by cited evidence and track record rather than volume.

## Relationship To Current VN SSI Dashboard

The current VN dashboard remains a data-quality-first VN ticker inspection workspace backed by SSI market-data contracts and VN-specific diagnostics.

The foreign-stock tracker is a separate future product strategy:

- It is not part of the current VN SSI market-data contract.
- It does not change existing VN dashboard APIs, runtime behavior, or data-source ownership.
- It should reuse product principles where useful: source transparency, no fake realtime, diagnostics separation, neutral language, and no trading advice.
- It will need its own future data contracts for foreign assets, imports, multi-currency ledgers, broker statements, legal profile, tax lots, alerts, and digest content.

## Product Principles

### Legal Clarity First

Every activation path should first understand the user's residency/legal context and route them to an appropriate product-safe mode. The product must be conservative for users resident in Vietnam.

### Read-Only First

Imports and broker connections should be read-only. Users should always approve reconciled holdings before the product treats them as portfolio truth.

### Multi-Currency Truth

Show portfolio value and P/L in native asset currency and VND. Separate asset movement, FX movement, fees, dividends, withholding, and cash movements.

### Source Transparency

Every major number, explanation, alert, and digest item should expose source, timestamp, currency, and confidence/quality when available.

### No Trading Advice

The product can explain facts, events, scenarios, risks, and portfolio changes. It must not issue trade recommendations, target prices, or portfolio action instructions.

### No Illegal Or Unclear Funding Guidance

Funding and FX content must be framed as cost/fee/ETA scenarios plus compliance caveats. It must not provide workaround steps for unclear or prohibited flows.

### Explainability In Vietnamese

Vietnamese explanations are a core feature, not a marketing add-on. The product should translate the hard parts: filings, transcripts, dividend mechanics, tax forms, FX, and risk language.

### Auditability And Exportability

Users should be able to export transactions, statements, tax-lot summaries, dividend records, fee records, FX history, and source evidence. Serious investors need records they can review later.
