-- =============================================================================
-- ANALYTICS MARTS: pre-aggregated, documented tables that feed the analyses and
-- the Power BI dashboard. Each mart answers a family of business questions.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS mart;

-- -----------------------------------------------------------------------------
-- mart_funnel_daily
-- Grain: date x channel x device x visitor_type.
-- Q: How many sessions reach each stage? Where is the drop-off, by segment and time?
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.mart_funnel_daily AS
SELECT
    session_date,
    channel,
    device_type,
    visitor_type,
    is_sale_day,
    count(*)                                   AS sessions,
    count(*) FILTER (WHERE reached_product_view) AS product_view_sessions,
    count(*) FILTER (WHERE reached_cart)         AS cart_sessions,
    count(*) FILTER (WHERE reached_checkout)     AS checkout_sessions,
    count(*) FILTER (WHERE purchased)            AS purchase_sessions
FROM core.fct_sessions
GROUP BY ALL;

-- -----------------------------------------------------------------------------
-- mart_customer_ltv
-- Grain: one row per customer (user with >= 1 valid order).
-- Fixed-horizon LTV: cumulative NET REVENUE and GROSS MARGIN within H days of the
-- first order. A customer is ELIGIBLE for horizon H only if H days + the return
-- maturity window (30d) have fully elapsed before the snapshot. Averages must be
-- computed over eligible customers only (handles right-censoring).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.mart_customer_ltv AS
WITH base AS (
    SELECT c.user_id, c.first_order_ts, c.cohort_month, c.acquisition_channel, c.acquisition_device,
           c.city_tier, c.first_order_payment_type, c.first_order_category, c.acquired_in_sale,
           c.first_order_discounted, c.gender, c.age_band
    FROM core.dim_customers c WHERE c.is_customer
),
o AS (
    -- elapsed days (24h periods), not calendar-date boundaries: an order 364.9 days later counts as day 364
    SELECT b.user_id, floor(date_diff('second', b.first_order_ts, f.order_ts) / 86400) AS day_n, f.is_first_order,
           f.net_revenue, f.gross_margin
    FROM base b JOIN core.fct_orders f USING (user_id)
    WHERE f.is_valid_order
)
SELECT
    b.*,
    -- orders within horizon
    count(*) FILTER (WHERE o.day_n < 90)                              AS orders_90d,
    count(*) FILTER (WHERE o.day_n < 365)                             AS orders_365d,
    -- net revenue LTV
    coalesce(sum(o.net_revenue) FILTER (WHERE o.is_first_order), 0)  AS net_revenue_first_order,
    coalesce(sum(o.net_revenue) FILTER (WHERE o.day_n < 90), 0)       AS net_revenue_90d,
    coalesce(sum(o.net_revenue) FILTER (WHERE o.day_n < 180), 0)      AS net_revenue_180d,
    coalesce(sum(o.net_revenue) FILTER (WHERE o.day_n < 365), 0)      AS net_revenue_365d,
    coalesce(sum(o.net_revenue) FILTER (WHERE o.day_n < 730), 0)      AS net_revenue_730d,
    -- gross margin LTV (preferred: what the customer is worth before fulfilment & marketing)
    coalesce(sum(o.gross_margin) FILTER (WHERE o.is_first_order), 0) AS margin_first_order,
    coalesce(sum(o.gross_margin) FILTER (WHERE o.day_n < 90), 0)      AS margin_90d,
    coalesce(sum(o.gross_margin) FILTER (WHERE o.day_n < 180), 0)     AS margin_180d,
    coalesce(sum(o.gross_margin) FILTER (WHERE o.day_n < 365), 0)     AS margin_365d,
    coalesce(sum(o.gross_margin) FILTER (WHERE o.day_n < 730), 0)     AS margin_730d,
    sum(o.net_revenue)                                                AS net_revenue_to_date,
    sum(o.gross_margin)                                               AS margin_to_date,
    count(*)                                                          AS orders_to_date,
    -- eligibility (right-censoring)
    b.first_order_ts + INTERVAL (90  + return_maturity_days()) DAY <= snapshot_ts() AS eligible_90d,
    b.first_order_ts + INTERVAL (180 + return_maturity_days()) DAY <= snapshot_ts() AS eligible_180d,
    b.first_order_ts + INTERVAL (365 + return_maturity_days()) DAY <= snapshot_ts() AS eligible_365d,
    b.first_order_ts + INTERVAL (730 + return_maturity_days()) DAY <= snapshot_ts() AS eligible_730d
FROM base b
JOIN o USING (user_id)
GROUP BY ALL;

-- -----------------------------------------------------------------------------
-- mart_customer_monthly_activity
-- Grain: customer x calendar month in which they placed >= 1 valid order.
-- Lets the BI tool build retention for ANY customer attribute via dim_customers.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.mart_customer_monthly_activity AS
SELECT
    f.user_id,
    c.cohort_month,
    f.order_month                                                       AS activity_month,
    date_diff('month', c.cohort_month, f.order_month)                   AS month_offset,
    count(*)                                                            AS orders,
    sum(f.net_revenue)                                                  AS net_revenue,
    sum(f.gross_margin)                                                 AS gross_margin
FROM core.fct_orders f
JOIN core.dim_customers c USING (user_id)
WHERE f.is_valid_order
GROUP BY ALL;

-- -----------------------------------------------------------------------------
-- mart_cohort_retention
-- Grain: cohort_month x acquisition_channel x month_offset (complete grid, so
-- months with zero active customers are present). 'All' rows = all channels.
-- is_observable = the calendar month cohort+offset is fully inside the data window.
-- Retention definition: % of the cohort with >= 1 valid order in that month.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.mart_cohort_retention AS
WITH sizes AS (
    SELECT cohort_month, acquisition_channel, count(*) AS cohort_size
    FROM core.dim_customers WHERE is_customer GROUP BY GROUPING SETS ((cohort_month, acquisition_channel), (cohort_month))
),
sizes2 AS (SELECT cohort_month, coalesce(acquisition_channel, 'All') AS acquisition_channel, cohort_size FROM sizes),
grid AS (
    SELECT s.*, k.month_offset
    FROM sizes2 s
    CROSS JOIN range(0, 34) k(month_offset)
),
act AS (
    SELECT a.cohort_month, c.acquisition_channel, a.month_offset,
           count(DISTINCT a.user_id) AS active_customers, sum(a.orders) AS orders,
           sum(a.net_revenue) AS net_revenue, sum(a.gross_margin) AS gross_margin
    FROM mart.mart_customer_monthly_activity a JOIN core.dim_customers c USING (user_id)
    GROUP BY GROUPING SETS ((a.cohort_month, c.acquisition_channel, a.month_offset), (a.cohort_month, a.month_offset))
),
act2 AS (SELECT * REPLACE (coalesce(acquisition_channel, 'All') AS acquisition_channel) FROM act)
SELECT
    g.cohort_month,
    g.acquisition_channel,
    g.month_offset,
    g.cohort_size,
    coalesce(a.active_customers, 0)                                        AS active_customers,
    coalesce(a.orders, 0)                                                  AS orders,
    coalesce(a.net_revenue, 0)                                             AS net_revenue,
    coalesce(a.gross_margin, 0)                                            AS gross_margin,
    coalesce(a.active_customers, 0) / g.cohort_size                        AS retention_rate,
    (g.cohort_month + INTERVAL (g.month_offset) MONTH)::DATE <= last_complete_month() AS is_observable
FROM grid g
LEFT JOIN act2 a USING (cohort_month, acquisition_channel, month_offset)
WHERE (g.cohort_month + INTERVAL (g.month_offset) MONTH)::DATE <= last_complete_month();

-- -----------------------------------------------------------------------------
-- mart_channel_monthly
-- Grain: month x channel.
-- Q: Which channels bring volume, at what cost, and what is CAC?
-- CAC = total channel cost / new customers acquired (first-touch) in the month.
-- Only paid channels have cost data; unpaid channels' CAC is NULL, not zero.
-- Email platform fees are excluded from CAC (retention cost, not acquisition cost).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.mart_channel_monthly AS
WITH months AS (SELECT DISTINCT month_start FROM core.dim_date),
channels AS (
    SELECT DISTINCT channel FROM core.fct_sessions
    UNION SELECT DISTINCT acquisition_channel FROM core.dim_customers
),
sess AS (
    SELECT session_month AS month_start, channel, count(*) AS sessions,
           count(*) FILTER (WHERE visit_number = 1) AS new_visitors,
           count(*) FILTER (WHERE purchased) AS purchase_sessions
    FROM core.fct_sessions GROUP BY ALL
),
newc AS (
    SELECT cohort_month AS month_start, acquisition_channel AS channel, count(*) AS new_customers,
           sum(first_order_net_revenue) AS first_order_net_revenue
    FROM core.dim_customers WHERE is_customer GROUP BY ALL
),
lastclick AS (
    SELECT order_month AS month_start, order_session_channel AS channel,
           count(*) FILTER (WHERE is_valid_order) AS last_click_orders,
           sum(net_revenue) AS last_click_net_revenue
    FROM core.fct_orders GROUP BY ALL
),
spend AS (
    SELECT date_trunc('month', date)::DATE AS month_start, channel, sum(spend_inr) AS spend_inr,
           sum(clicks) AS paid_clicks
    FROM stg.stg_marketing_spend GROUP BY ALL
)
SELECT
    m.month_start,
    c.channel,
    coalesce(s.sessions, 0)              AS sessions,
    coalesce(s.new_visitors, 0)          AS new_visitors,
    coalesce(s.purchase_sessions, 0)     AS purchase_sessions,
    coalesce(n.new_customers, 0)         AS new_customers,
    coalesce(n.first_order_net_revenue, 0) AS first_order_net_revenue,
    coalesce(l.last_click_orders, 0)     AS last_click_orders,
    coalesce(l.last_click_net_revenue, 0) AS last_click_net_revenue,
    sp.spend_inr,
    sp.paid_clicks,
    -- Email's cost is a CRM platform fee that mostly serves existing customers: not an acquisition cost
    CASE WHEN c.channel IN ('Paid Search', 'Paid Social', 'Affiliate')
         THEN sp.spend_inr / nullif(n.new_customers, 0) END AS cac_inr
FROM months m
CROSS JOIN channels c
LEFT JOIN sess s USING (month_start, channel)
LEFT JOIN newc n USING (month_start, channel)
LEFT JOIN lastclick l USING (month_start, channel)
LEFT JOIN spend sp USING (month_start, channel)
WHERE coalesce(s.sessions, 0) + coalesce(n.new_customers, 0) + coalesce(l.last_click_orders, 0)
      + coalesce(sp.spend_inr, 0) > 0;

-- -----------------------------------------------------------------------------
-- mart_kpi_monthly
-- Grain: month. Executive KPIs with explicit definitions.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE mart.mart_kpi_monthly AS
WITH o AS (
    SELECT order_month AS month_start,
        count(*)                                       AS orders_placed,
        count(*) FILTER (WHERE is_valid_order)         AS valid_orders,
        count(*) FILTER (WHERE is_valid_order AND customer_order_number > 1) AS repeat_orders,
        count(DISTINCT user_id) FILTER (WHERE is_valid_order) AS active_customers,
        count(DISTINCT user_id) FILTER (WHERE is_first_order) AS new_customers,
        sum(gmv) FILTER (WHERE is_valid_order)         AS gmv,
        sum(gross_revenue)                             AS gross_revenue,
        sum(returned_revenue)                          AS returned_revenue,
        sum(net_revenue)                               AS net_revenue,
        sum(gross_margin)                              AS gross_margin,
        count(*) FILTER (WHERE is_cancelled)           AS cancelled_orders,
        count(*) FILTER (WHERE is_rto)                 AS rto_orders,
        count(*) FILTER (WHERE payment_type = 'COD')   AS cod_orders
    FROM core.fct_orders GROUP BY 1
),
s AS (
    SELECT session_month AS month_start, count(*) AS sessions, count(*) FILTER (WHERE purchased) AS purchase_sessions
    FROM core.fct_sessions GROUP BY 1
),
sp AS (SELECT date_trunc('month', date)::DATE AS month_start, sum(spend_inr) AS marketing_spend
       FROM stg.stg_marketing_spend GROUP BY 1)
SELECT
    o.*,
    s.sessions,
    s.purchase_sessions,
    s.purchase_sessions / s.sessions                    AS session_conversion_rate,
    o.gross_revenue / nullif(o.valid_orders, 0)         AS aov_gross,
    o.repeat_orders / nullif(o.valid_orders, 0)         AS repeat_order_share,
    o.returned_revenue / nullif(o.gross_revenue, 0)     AS return_rate_value,
    o.rto_orders / nullif(o.orders_placed, 0)           AS rto_rate,
    sp.marketing_spend,
    sp.marketing_spend / nullif(o.net_revenue, 0)       AS marketing_spend_pct_net_revenue,
    o.month_start <= last_complete_month()              AS is_complete_month
FROM o
LEFT JOIN s USING (month_start)
LEFT JOIN sp USING (month_start)
ORDER BY o.month_start;
