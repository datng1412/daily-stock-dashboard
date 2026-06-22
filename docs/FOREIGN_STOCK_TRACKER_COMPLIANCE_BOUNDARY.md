# Foreign-Stock Tracker Compliance Boundary

## Purpose

This document is product and compliance design guidance. It is not legal advice or tax advice. Any implementation that touches legal, tax, broker, funding, FX, or account workflows must receive professional compliance review before release.

## Product Positioning

The product should present itself as:

```text
An investment tracking and intelligence platform for Vietnamese users interested in foreign assets.
```

It should not present itself as enabling unlawful foreign investment or as a universal path for Vietnam residents to access foreign securities.

## MVP Boundary

MVP includes:

- Watchlists.
- Research and Vietnamese explanations.
- Legal-context routing.
- Read-only imports.
- CSV/email/PDF/manual portfolio records.
- Multi-currency P/L.
- Alerts.
- Dividends, withholding, and tax-document organization.
- Export and audit aids.

MVP excludes:

- Brokerage.
- Execution.
- Custody.
- Order placement.
- Account opening.
- Cash transfer.
- Asset transfer.
- Funding instructions.
- Legal advice.
- Tax advice.
- Trade recommendations.

## Legal Wizard Boundary

The legal wizard is educational and routing-oriented:

- It can ask profile questions.
- It can show conservative product-safe modes.
- It can explain why the product is read-only for certain profiles.
- It can suggest professional review for unclear cases.

It must not:

- Decide legality for the user.
- Guarantee eligibility.
- Give instructions for capital movement.
- Tell users how to bypass or circumvent laws, bank rules, KYC, FX rules, tax rules, or capital controls.

## Funding And FX Estimator Boundary

If built, the funding/FX estimator must be a scenario tool, not a workaround guide.

Allowed:

- Show reference-only cost, fee, spread, FX-rate, and ETA scenarios.
- Show compliance caveats.
- Explain that availability depends on user profile, bank, broker, country, account type, and regulation.
- Link to official institution or partner disclosures where appropriate.

Not allowed:

- Step-by-step instructions for prohibited or unclear flows.
- Claims that a route is lawful for all users.
- Advice to misstate purpose, identity, residency, or source of funds.
- Instructions to avoid KYC, tax, bank, or FX controls.

## Broker Import Boundary

Broker integrations must be read-only:

- Request the narrowest available permissions.
- Show permissions before connection.
- Do not request trading, cash movement, transfer, or margin permissions.
- Store tokens securely.
- Let users disconnect and delete data.
- Require user review before imported data becomes portfolio truth.

## Order And Account Boundary

The product must not include:

- Order placement.
- Account or cash transfer functions.
- Securities transfer functions.
- Margin or derivative enablement flows.
- Trading buttons.
- Universal broker account-opening instructions.

## Tax Boundary

Tax features are estimates and export aids unless reviewed by qualified professionals.

Allowed:

- Track dividends, withholding, fees, cost basis, FX rates, and source documents.
- Generate export packs for user review.
- Remind users about document status such as W-8/tax forms where relevant.
- Route complex cases to professional review.

Not allowed:

- Claim to file taxes for the user without a licensed workflow.
- Guarantee tax correctness.
- Provide personalized tax advice.
- Hide assumptions or source gaps.

## Copy Rules For Vietnam Resident Users

When user profile indicates resident in Vietnam:

- Use conservative product-safe mode by default.
- Prefer watchlist, learning, tracking, document organization, and professional review.
- Avoid copy that implies broad retail foreign-stock execution is available.
- Avoid copy that suggests a funding path.
- Keep legal/tax disclaimers visible and understandable.

## No Trading Advice

The product can show:

- Facts.
- Source-backed explanations.
- Portfolio movement decomposition.
- Risk factors.
- Events.
- Calendar items.
- User-authored notes.

The product must not show:

- Trade recommendations.
- Target-price instructions.
- Portfolio action instructions.
- Ranking copy that implies users should transact.

## Escalation Requirements

Escalate to compliance/legal review before building or releasing:

- Any broker integration.
- Any funding/FX route content.
- Any tax calculation beyond simple recordkeeping.
- Any social content ranking that could be interpreted as advice.
- Any partner/referral flow.
- Any account, cash, or asset workflow.

## Implementation Checklist

- Product copy says tracking/intelligence, not execution.
- Legal wizard says educational/routing, not legal advice.
- All imports are read-only.
- No order placement exists.
- No account/cash transfer exists.
- No funding workaround guidance exists.
- Tax output is labeled estimate/export aid.
- Vietnam resident path is conservative.
- Trust Center describes data storage, deletion, security, read-only scopes, and source limitations.
