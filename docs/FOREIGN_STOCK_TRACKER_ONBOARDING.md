# Foreign-Stock Tracker Onboarding

## Purpose

Onboarding should reduce ambiguity before it asks for sensitive data. For Vietnamese users interested in foreign assets, the safest first experience is legal context, read-only tracking, watchlist creation, and transparent explanations.

## Flow Overview

```text
Welcome
  -> Choose goal
  -> Legal/residency context
  -> Product-safe mode
  -> Start path
  -> Market/currency/language setup
  -> Alert setup
  -> Trust/legal disclaimer and escalation path
```

## Step 1: Welcome

Message:

- This is a tracking and intelligence product for foreign assets.
- It is not a broker and does not provide execution, custody, tax advice, legal advice, or trade recommendations.
- Users can start with a watchlist without connecting accounts.

Primary CTAs:

- Start with watchlist.
- Import existing portfolio.
- Learn first.

## Step 2: Choose Goal

Options:

- Follow/learn.
- Already have broker account.
- Already have portfolio data.

Routing:

- Follow/learn: prioritize watchlist, glossary, legal wizard, and digest.
- Already have broker account: prioritize legal context, read-only import, and trust center.
- Already have portfolio data: prioritize CSV/email/PDF/manual import and reconciliation.

## Step 3: Ask Residency And Legal Context

Ask only what is needed for product routing:

- Are you currently resident in Vietnam?
- Are you offshore, expat, student, foreign worker, or in another special residency situation?
- Do you have foreign employment, ESOP, or compensation-related foreign shares?
- Do you already own foreign assets through an existing account?
- Do you want to track only, or import existing records?

Rules:

- Do not present legal wizard output as legal advice.
- Use conservative copy for Vietnam resident users.
- Route unclear cases to tracking-only mode and expert/legal review escalation.

## Step 4: Resident In Vietnam Branch

If the user is resident in Vietnam:

- Show higher legal caution.
- Explain that the product begins with tracking, research, education, alerts, and recordkeeping.
- Do not suggest execution, account opening, cash movement, or funding actions.
- Offer product-safe mode:
  - Watchlist.
  - Learning.
  - Read-only record organization if the user already has records.
  - Legal/tax document checklist.

Safe-mode copy:

```text
Your current profile requires conservative handling. This product can help you track, learn, organize records, and understand source-backed information. It does not provide legal advice or instructions for moving money or placing trades.
```

## Step 5: Offshore, Expat, ESOP, Student, Or Foreign-Worker Branch

If the user indicates an offshore/expat/ESOP/student/foreign-worker profile:

- Ask follow-up questions only to choose product mode and document needs.
- Allow read-only import if the user already has an account or statements.
- Show document reminders such as W-8/tax-form status where relevant.
- Encourage professional review for complex tax/residency cases.

Product modes:

- Tracking-only.
- Existing-account read-only tracking.
- ESOP/document organization.
- Multi-account reporting.

## Step 6: Choose Start Path

Start paths:

- Watchlist.
- Read-only broker connection.
- CSV/email import.
- PDF statement import.
- Manual entry.

Rules:

- Read-only broker connection must clearly show requested permissions before connection.
- CSV/email/PDF import must show parser confidence and require user review.
- Manual entry should support cash, fees, FX rate, dividend, and withholding fields.
- If the user is unsure, default to watchlist-first.

## Step 7: Set Market, Currency, And Language

Ask:

- Markets of interest: US, Hong Kong, Singapore, global ETFs, or other.
- Base currency: VND plus optional USD/HKD/SGD/etc.
- Display preference: Vietnamese, English, or bilingual VI/EN.
- Time-zone preference: Vietnam time by default.

Product rule:

- Portfolio P/L should support native currency plus VND.
- Digest and alerts should be localized to Vietnam time.

## Step 8: Set Alerts

Alert categories:

- Price.
- Earnings.
- FX.
- Dividends.

Default behavior:

- Keep alerts low-noise.
- Suggest alert bundles by persona.
- Let users opt into digest first if they do not want real-time alerts.

## Step 9: Trust, Legal Disclaimer, And Escalation

Show:

- Product is tracking and intelligence, not execution.
- Legal wizard is educational/routing, not legal advice.
- Tax reports are estimates/export aids unless reviewed by professionals.
- Read-only imports cannot place orders or move cash.
- Data sources, security, deletion, and export controls are available in Trust Center.
- Escalation path: support, legal/tax professional referral, or expert review queue where available.

## Activation Metrics

- Onboarding completion.
- Legal-profile classification completion.
- Time-to-first-watchlist.
- Time-to-first-portfolio.
- First import started.
- First import confirmed.
- Alert opt-in.
- First digest opened.
- Trust Center viewed.

## Drop-Off Risks

- Legal step feels scary or too long.
- User does not know which legal profile applies.
- Import flow asks for too much permission.
- CSV/PDF parser produces too many unresolved items.
- USD+VND P/L is visually complex for a novice.
- Too many alert choices before the user sees value.
- Disclaimer copy feels like a dead end instead of safe routing.

## A/B Tests

| Test | Hypothesis | Primary metric | Guardrail |
| --- | --- | --- | --- |
| Short onboarding vs legal-step onboarding | Legal-step onboarding may reduce completion but increase trust and D7 retention. | Completion, D7 retention | No increase in support confusion about product capability. |
| Watchlist-first vs import-first CTA | New users prefer watchlist; existing-account users prefer import. | Time-to-first-value by persona | No broad permission requests before trust screen. |
| USD-only P/L vs USD+VND P/L | Dual-currency P/L improves understanding for Vietnamese users. | Portfolio screen engagement, support tickets | UI complexity does not reduce activation. |
| Vietnamese-only research vs bilingual VI/EN | Novices prefer Vietnamese; experienced users may prefer bilingual source terms. | Research save/share rate | Financial meaning must stay accurate. |

## Onboarding Acceptance Criteria

- A user can finish in under 10 minutes.
- A user can start without connecting a broker or entering cash movement.
- Vietnam resident users see conservative product-safe mode.
- Offshore/expat/ESOP/student/foreign-worker users see fit-for-profile branches.
- Read-only import is clearly labeled read-only.
- No onboarding screen implies trading, execution, or funding capability.
- Every legal/tax message is framed as product routing or education, not advice.
