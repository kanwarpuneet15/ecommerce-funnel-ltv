# Data Quality Report

**Scope:** raw extracts in `data/raw/` (snapshot taken 30 Sep 2026, data from 1 Jan 2024).
**Method:** each issue is **detected** in `notebooks/01_data_profiling.ipynb`, **handled** in the staging SQL layer, and **guarded** by an automated test in `sql/tests/data_tests.sql`.
Nothing is cleaned silently. Every row removed or reclassified is counted below.

> The dataset is synthetic (see `docs/generator_assumptions.md`). The issues were planted to mirror common real-world defects. The analyst workflow below does not rely on knowing that.

## Impact summary

| Stage | Before | After | Removed or flagged |
|---|---:|---:|---|
| Events | 3,987,538 | 3,967,671 | 19,867 duplicates/future-dated removed |
| Sessions | 1,143,608 | 1,140,053 | 3,555 bot sessions (257,609 events, 6.5% of all events) excluded |
| Order rows | 33,748 | 33,658 | 90 duplicate rows removed |
| Orders | 33,658 | 33,499 | 159 internal QA orders excluded |
| Customers with unknown first touch | — | 638 of 20,304 (3.1%) | labelled `Unattributed` |

## Issue log

| # | Issue | Evidence | Why it matters | Decision | Where |
|---|---|---|---|---|---|
| DQ-1 | **Duplicate events.** Client retries re-send the same `event_id`, and some are re-sent with a new id | 15,871 extra rows with the same `event_id`; 3,979 more with identical content but a new id | Inflates funnel stage counts and conversion | Dedupe on `event_id`, then on (session, event, timestamp, product, order) | `stg_events` |
| DQ-2 | **Duplicate order rows** from an ETL re-load | 90 `order_id`s appear twice; all fully identical | Double-counts revenue | Keep one row per `order_id` | `stg_orders` |
| DQ-3 | **Mixed time zones.** Events are logged in UTC, orders stored in IST | Order timestamp − purchase event = exactly +5.5 h for every one of the 32,182 purchases with a valid timestamp | Late-evening orders (the peak shopping hours) fall into the wrong day/month, which breaks daily funnels and cohort month boundaries | Convert events to IST | `stg_events` |
| DQ-4 | **Clock skew.** Events dated in the future | 27 events dated after the snapshot, up to Oct 2027 | Phantom future activity | Exclude | `stg_events` |
| DQ-5 | **Bot / scraper sessions** | A separate population: median 74 events/session at ~56 events/min, desktop only; only 41% identify as `HeadlessChrome` | Inflates traffic and product-view counts. A user-agent filter alone misses 59% of them | Bot if `HeadlessChrome` OR (≥ 25 events AND > 20 events/min) | `stg_sessions` |
| DQ-6 | **No channel field; messy UTMs** | `facebook / fb / Facebook / ig / Instagram`; `cpc / CPC / ppc`; `email / Email / e-mail`; Meta clicks tagged `cpc`; 1.5% of tagged sessions have no medium | Naive rules misclassify Meta `cpc` as Paid Search and organic Instagram posts as paid | Ordered rule set: source → medium → referrer → Direct. Unknown tags become `Other Campaign` rather than `Direct` | `stg_sessions` |
| DQ-7 | **Anonymous events** | 92% of events have no `user_id`. Each visitor maps to exactly 1 user | Acquisition channel needs the visitor's first, pre-login visit | Visitor→user identity stitching | `int_identity_map` |
| DQ-8 | **Internal QA orders in production** | 35 users on the company domain `threadline.in`, ₹1 orders, code `QA100` | Fake customers and orders | Flag `is_internal`; excluded from all core tables | `stg_users`, `stg_orders` |
| DQ-9 | **Inconsistent status casing** | `delivered` / `DELIVERED`, `rto` / `RTO` | Splits categories in group-bys | `lower()` | `stg_orders` |
| DQ-10 | **`order_total` ≠ sum of line items** | 63 orders (0.2%) mismatch by more than ₹1 | Two different revenue figures | Line items are the source of truth (they also carry cost). Mismatch flagged `has_total_mismatch` | `fct_orders` |
| DQ-11 | **Untracked orders** | 1,468 real orders (4.4%) have no purchase event (ad blockers / consent) | Event-based conversion is understated; attribution has gaps | Orders table = truth for orders and revenue; events = truth for funnel *rates*. No tracked visit before first order → `Unattributed` (not Direct) | `fct_orders`, `int_customer_acquisition` |
| DQ-12 | **Purchases without add-to-cart** | 5.0% of purchasing sessions (Buy Now button) | A naive funnel would show more purchases than cart sessions at some grains | Stage = "reached this stage **or any later** stage" | `fct_sessions` |
| DQ-13 | **Spend exported in the wrong currency** | 14 Meta rows (10–16 Feb 2025) in USD; CPC drops ~87× | That week's spend would be understated ~87×, which flatters Paid Social CAC | Convert at ₹87.0/USD (documented seed `fx_rates.csv`) | `stg_marketing_spend` |
| DQ-14 | **Orders still in flight at snapshot** | 260 orders `processing`/`shipped`; recent returns not yet known | Recent cohorts look better than they are (returns still to come) | LTV only counts customers whose horizon + a 30-day return window has fully elapsed | `mart_customer_ltv` |

## Accepted as legitimate (not cleaned)

- **Free-gift lines:** 165 lines (0.32%) at 100% discount. Real promotions. Revenue ₹0, cost kept.
- **Right-skewed order values:** mean ₹2,142 vs median ₹1,798, max ₹13,896, with no impossible values. The median is reported alongside AOV.
- **Cancelled/RTO orders:** kept in `fct_orders` for operational metrics (RTO rate) with revenue forced to 0.
- **Bots barely move conversion** (2.801% → 2.810%) because they are only 0.3% of sessions. They do inflate raw traffic and product-view volumes by 6.5% of events, which matters for top-of-funnel reporting.

## Known limitations that cannot be fixed with this data

1. **Cross-device journeys are not stitched.** A customer who browses on mobile and buys on desktop looks like two visitors until login.
2. **First-touch attribution only.** Multi-touch credit (e.g. Paid Social assisting an Email conversion) is not modelled.
3. **No fulfilment cost data** (shipping, RTO reverse logistics, payment gateway fees). Margin here is *product* gross margin, so true contribution margin is lower, especially for COD/RTO-heavy segments.
4. **Unpaid channels have no cost data.** SEO, content and brand costs exist but aren't recorded, so their CAC is unknown, **not zero**.
