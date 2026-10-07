# Data Dictionary

All money is in **INR**. All timestamps are in **IST** (events are converted from UTC in staging).
Layers: `raw` (as received) → `stg` (cleaned) → `int` (building blocks) → `core` (star schema) → `mart` (aggregates for analysis and BI).

## Metric glossary (single source of truth)

| Metric | Definition | Where |
|---|---|---|
| **Valid order** | Order not cancelled and not RTO (returned to origin / refused at the door). Used for customers, retention and LTV | `stg_orders.is_valid_order` |
| **GMV** | List price × quantity, before discounts | `fct_orders.gmv` |
| **Gross revenue** | GMV − discounts, valid orders only. Excludes shipping fees (pass-through) | `fct_orders.gross_revenue` |
| **Net revenue** | Gross revenue − revenue of returned items | `fct_orders.net_revenue` |
| **Gross margin** | Net revenue − cost of goods the customer kept (returned goods assumed restocked). Excludes fulfilment, payment and RTO logistics costs (not in data) | `fct_orders.gross_margin` |
| **AOV** | Gross revenue / valid orders | `mart_kpi_monthly.aov_gross` |
| **Session conversion** | Non-bot sessions with a purchase / non-bot sessions | `fct_sessions.purchased` |
| **Funnel stage reached** | Session reached this stage **or any later stage** (so Buy-Now purchases count as passing the cart) | `fct_sessions.reached_*` |
| **Customer** | Registered user with ≥ 1 valid order | `dim_customers.is_customer` |
| **Cohort** | Calendar month of the customer's first valid order | `dim_customers.cohort_month` |
| **Monthly retention (k)** | % of a cohort with ≥ 1 valid order in calendar month cohort + k (observable months only) | `mart_cohort_retention.retention_rate` |
| **Repeat rate (H)** | % of customers with ≥ 2 valid orders within H days of the first order (eligible customers only) | `mart_customer_ltv.orders_365d >= 2` |
| **Acquisition channel** | Channel of the customer's first tracked, non-bot session before their first order (first touch). `Unattributed` if none was tracked | `int_customer_acquisition` |
| **Order session channel** | Channel of the session containing the purchase (last click). `Untracked` if the session was not captured | `fct_orders.order_session_channel` |
| **Fixed-horizon LTV (H)** | Avg cumulative gross margin (or net revenue) within H days of the first order, over customers whose H + 30-day return window has fully elapsed (`eligible_Hd`) | `mart_customer_ltv` |
| **CAC** | Paid acquisition cost (Google Ads, Meta Ads, affiliate commission) / new customers acquired by that channel (first touch). Email platform fees are excluded | `mart_channel_monthly.cac_inr` |
| **Marginal CAC** | Extra spend / extra customers between two periods | `sql/analysis/08` |
| **LTV:CAC** | 12-month margin LTV / CAC (same acquisition window) | `sql/analysis/07` |
| **Predicted margin next 12m** | MBG/NBD expected repeat orders × Gamma-Gamma expected margin per order | `mart_customer_clv_predictions` |

## Core tables (star schema)

### `core.dim_customers`: one row per real registered user (buyers and non-buyers)
| Column | Description |
|---|---|
| user_id (PK) | Customer id |
| signup_ts | Account creation time |
| gender, age_band, city, state, city_tier | Profile; city tier from `seeds/city_tiers.csv` |
| acquisition_channel, acquisition_device, first_visit_ts | First-touch attribution (see glossary) |
| has_tracked_first_touch | False → `Unattributed` |
| is_customer | Has ≥ 1 valid order |
| first_order_ts, cohort_month | First valid order; cohort = its month |
| last_order_ts, days_since_last_order, customer_age_days | Recency and tenure at snapshot (30 Sep 2026) |
| valid_orders, is_repeat_customer | Order count; ≥ 2 valid orders |
| net_revenue_to_date, gross_margin_to_date | Historical value (censored) |
| first_order_payment_type, first_order_discounted, acquired_in_sale, first_order_net_revenue, first_order_had_return, first_order_session_channel, first_order_category | First-order attributes used for segmentation. Category = highest-value line |
| ever_rto, rto_orders | Any undelivered order |

### `core.fct_orders`: one row per real order (including cancelled and RTO)
| Column | Description |
|---|---|
| order_id (PK), user_id (FK) | |
| order_ts, order_date, order_month | IST |
| status | delivered / shipped / processing / cancelled / rto (normalised) |
| payment_method, payment_type | UPI / CARD / WALLET / COD → Prepaid / COD |
| discount_code, is_discounted, is_sale_order, sale_name | Promotion context |
| is_valid_order, is_cancelled, is_rto, is_in_flight | Status flags |
| has_return, fully_returned | Item returns on the order |
| n_lines, units, gmv, discount_amount | Line roll-up |
| gross_revenue, returned_revenue, net_revenue, cogs, gross_margin | Money (zero for invalid orders) |
| gross_revenue_placed | Demand value, including cancelled/RTO orders |
| shipping_fee, order_total_reported, has_total_mismatch | Reconciliation against the source system (DQ-10) |
| customer_order_number, is_first_order, days_since_prev_order | Sequence among the customer's valid orders |
| session_id, is_tracked, order_session_channel, order_session_device | Link to the purchase session (last click) |
| acquisition_channel | Customer's first-touch channel (denormalised for convenience) |

### `core.fct_order_items`: one row per order line
order_item_id (PK), order_id (FK), user_id, order_ts, order_month, product_id (FK), category, department, quantity, gmv, discount_amount, gross_revenue, is_returned, returned_revenue, cogs, is_free_gift, is_valid_order, net_revenue, gross_margin.

### `core.fct_sessions`: one row per non-bot web session
| Column | Description |
|---|---|
| session_id (PK), visitor_id, user_id | user_id via login or identity stitching |
| session_start, session_date, session_month | IST |
| channel | Channel grouping rule (DQ-6) |
| device_type, browser, utm_campaign | |
| visit_number, visitor_type | New visitor / Returning prospect / Existing customer |
| reached_session, reached_product_view, reached_cart, reached_checkout, purchased | Funnel flags (stage or later) |
| is_buy_now_purchase | Purchase without an add-to-cart event |
| order_id, n_events, duration_seconds, is_sale_day | |

### `core.dim_products` (product_id PK; category, department, list_price, unit_cost, list_margin_pct) and `core.dim_date` (date_day PK; week/month/quarter, is_weekend, is_sale_day, sale_name, is_complete_month).

## Marts

| Table | Grain | Purpose |
|---|---|---|
| `mart_funnel_daily` | date × channel × device × visitor_type | Funnel counts per stage |
| `mart_customer_ltv` | customer | Fixed-horizon revenue/margin LTV (first order, 90/180/365/730 d) with eligibility flags |
| `mart_customer_monthly_activity` | customer × active month | Flexible retention by any customer attribute |
| `mart_cohort_retention` | cohort month × acquisition channel (incl. `All`) × month offset | Complete retention grid with revenue and margin |
| `mart_channel_monthly` | month × channel | Sessions, new customers, last-click orders, spend, CAC |
| `mart_kpi_monthly` | month | Executive KPIs |
| `mart_customer_clv_predictions` | customer | P(alive), expected orders, predicted 12-month margin, value segment (written by notebook 04) |

## Raw sources (as received)

| File | Grain | Notes |
|---|---|---|
| `events.csv.gz` | tracked event | UTC timestamps; UTM strings; anonymous `visitor_id` + `user_id` after login |
| `orders.csv` | order (with duplicate rows) | Local IST time; messy status casing |
| `order_items.csv` | order line | List price, discount, return timestamp |
| `users.csv` | registered user | Includes internal QA accounts |
| `products.csv` | product | Price and unit cost |
| `marketing_spend.csv` | date × platform × campaign type | One week of Meta rows in USD |
| `seeds/*.csv` | reference | Sale calendar, city tiers, FX rate, platform→channel map |
