# Foreign-Stock Tracker KPI And Experiment Plan

## Purpose

This document defines product metrics and early experiments for a future Vietnamese-first foreign-stock tracking and intelligence platform. It is not a current implementation plan for the VN SSI dashboard.

## Activation KPIs

| KPI | Definition | Why It Matters |
| --- | --- | --- |
| Onboarding completion | Percent of new users who complete the initial flow. | Measures whether legal/context routing is usable. |
| Time-to-first-watchlist | Median time from signup to first saved ticker list. | Watchlist is the lowest-friction first value. |
| Time-to-first-portfolio | Median time from signup to confirmed portfolio record. | Measures import/manual activation for serious users. |
| Alert opt-in | Percent of activated users enabling at least one alert. | Alerts are a key retention loop for time-zone mismatch. |
| Legal-profile completion | Percent of users with a completed product-routing profile. | Critical for conservative product modes. |

## Data Quality KPIs

| KPI | Definition | Why It Matters |
| --- | --- | --- |
| Import success rate | Percent of import attempts that produce user-reviewable records. | Import reliability is core product value. |
| Reconciliation accuracy | Percent of reconciled holdings matching user-confirmed truth. | Tracker trust depends on ledger accuracy. |
| Corporate-action accuracy | Percent of splits/dividends/events processed correctly. | Corporate actions can corrupt cost basis and P/L. |
| Missing/mapping error rate | Rate of unmapped symbols, currencies, fields, or broker templates. | Shows where parser/source coverage is weak. |
| Manual correction rate | Percent of imported portfolios requiring user edits. | Measures friction after import. |

## Engagement KPIs

| KPI | Definition | Why It Matters |
| --- | --- | --- |
| DAU/MAU | Daily active users over monthly active users. | General usage frequency. |
| WAU/MAU | Weekly active users over monthly active users. | Better fit for portfolio tracking cadence. |
| D7/D30/D90 retention | Retention by cohort. | Shows whether the product becomes a habit. |
| Digest open rate | Percent of delivered digests opened. | Morning digest is a signature retention loop. |
| Alert CTR | Percent of alerts that lead to an app session. | Measures alert usefulness. |
| Research save/share rate | Percent of explainers saved or shared. | Measures usefulness of Vietnamese research content. |

## Trust KPIs

| KPI | Definition | Why It Matters |
| --- | --- | --- |
| Support tickets per 1,000 MAU | Support volume normalized by active users. | High values can signal confusion or trust gaps. |
| False-alert rate | Percent of alerts later classified as wrong or misleading. | Financial apps need low false-positive noise. |
| Trust Center views | Percent of users viewing security/legal/source pages. | Shows whether users seek confidence before deeper use. |
| Security incidents | Count and severity of security events. | Must remain near zero with transparent handling. |
| Data deletion success | Percent of deletion requests completed within policy. | Required for trust and privacy expectations. |

## Monetization KPIs

| KPI | Definition | Why It Matters |
| --- | --- | --- |
| Free-to-paid | Percent of free users converting to paid. | Core subscription health. |
| ARPU | Average revenue per user. | Revenue quality by segment. |
| CAC payback | Months to recover acquisition cost. | Marketing efficiency. |
| Premium feature usage | Usage of tax, import, digest, alert, and export premium features. | Identifies monetizable pain points. |
| Tax-season conversion | Conversion during tax/reporting periods. | Measures value of reporting and tax cockpit features. |
| Premium retention | Paid cohort retention over time. | Indicates durable product value. |

## Compliance KPIs

| KPI | Definition | Why It Matters |
| --- | --- | --- |
| User legal-profile classification completion | Percent of users who complete legal/residency routing. | Required for conservative product modes. |
| W-8/tax-doc alert completion | Percent of relevant reminders marked complete. | Tracks document workflow usefulness. |
| Escalated support/legal cases | Count and resolution status of complex cases. | Reveals compliance ambiguity and support load. |
| Read-only connection ratio | Percent of broker connections using read-only scopes. | Guardrail for product boundary. |
| Restricted-flow block rate | Number of blocked actions or unsupported-flow attempts. | Shows where users expect capabilities outside scope. |

## A/B Tests

| Test | Hypothesis | Success Metrics | Guardrails |
| --- | --- | --- | --- |
| Legal onboarding early vs short onboarding | Early legal context may reduce completion but improve trust and retention. | Completion, D7 retention, support tickets | No increase in users misunderstanding product scope. |
| Watchlist-first vs import-first | New users activate faster with watchlists; existing-account users activate faster with import. | Time-to-first-watchlist, time-to-first-portfolio | Segment by selected goal. |
| P/L today vs overnight digest home screen | Vietnam users following US markets may find morning context more valuable than raw daily P/L. | D7 retention, digest open rate, first-session depth | Do not hide portfolio truth. |
| USD-only P/L vs USD+VND P/L | Dual-currency view improves understanding and reduces support questions. | Portfolio engagement, support tickets | UI complexity must not hurt onboarding. |
| Generic alerts vs persona-based alerts | Persona-based defaults increase opt-in and reduce alert fatigue. | Alert opt-in, CTR, unsubscribe rate | No spammy default notification behavior. |
| Vietnamese research vs bilingual VI/EN | Novices prefer Vietnamese; experienced users may trust bilingual terms more. | Research engagement, saves, support questions | Keep financial terminology accurate. |
| Open social feed vs citation-only social feed | Citation-only feed improves trust even if content volume is lower. | Report rate, quality score, retention | Prevent unsourced hype from dominating. |

## Measurement Notes

- Segment metrics by persona and legal-profile branch.
- Separate watchlist-only users from imported-portfolio users.
- Track user-confirmed data quality, not only parser output.
- Do not optimize activation by weakening compliance boundaries.
- Treat trust and support metrics as product-quality metrics, not only operations metrics.
