-- =============================================================================
-- DATA TESTS. Each query returns the rows that VIOLATE an expectation.
-- A test passes when it returns zero rows. Run with: python src/run_pipeline.py
-- =============================================================================

-- test: fct_sessions.session_id is unique
SELECT session_id FROM core.fct_sessions GROUP BY 1 HAVING count(*) > 1;

-- test: fct_orders.order_id is unique
SELECT order_id FROM core.fct_orders GROUP BY 1 HAVING count(*) > 1;

-- test: fct_order_items.order_item_id is unique
SELECT order_item_id FROM core.fct_order_items GROUP BY 1 HAVING count(*) > 1;

-- test: dim_customers.user_id is unique
SELECT user_id FROM core.dim_customers GROUP BY 1 HAVING count(*) > 1;

-- test: stg_events has no duplicate event_id
SELECT event_id FROM stg.stg_events GROUP BY 1 HAVING count(*) > 1;

-- test: no events after the snapshot
SELECT * FROM stg.stg_events WHERE event_ts > snapshot_ts();

-- test: every session has exactly one known channel
SELECT session_id FROM core.fct_sessions
WHERE channel IS NULL OR channel NOT IN ('Paid Search', 'Paid Social', 'Email', 'Affiliate', 'Other Campaign',
                                         'Organic Search', 'Organic Social', 'Referral', 'Direct');

-- test: no bot sessions in fct_sessions
SELECT f.session_id FROM core.fct_sessions f JOIN stg.stg_sessions s USING (session_id) WHERE s.is_bot;

-- test: funnel is monotonic for every session (purchase => checkout => cart => product view)
SELECT session_id FROM core.fct_sessions
WHERE (purchased AND NOT reached_checkout) OR (reached_checkout AND NOT reached_cart)
   OR (reached_cart AND NOT reached_product_view);

-- test: funnel mart is monotonic at every grain
SELECT * FROM mart.mart_funnel_daily
WHERE NOT (sessions >= product_view_sessions AND product_view_sessions >= cart_sessions
           AND cart_sessions >= checkout_sessions AND checkout_sessions >= purchase_sessions);

-- test: funnel mart reconciles to fct_sessions (no sessions lost in aggregation)
SELECT * FROM (SELECT (SELECT sum(sessions) FROM mart.mart_funnel_daily) AS a,
                      (SELECT count(*) FROM core.fct_sessions) AS b) WHERE a <> b;

-- test: no internal QA users or orders in core tables
SELECT user_id FROM core.fct_orders WHERE user_id IN (SELECT user_id FROM stg.stg_users WHERE is_internal)
UNION ALL
SELECT user_id FROM core.dim_customers WHERE user_id IN (SELECT user_id FROM stg.stg_users WHERE is_internal);

-- test: every order line belongs to an order and a product (referential integrity)
SELECT i.order_item_id FROM core.fct_order_items i
LEFT JOIN core.fct_orders o USING (order_id) LEFT JOIN core.dim_products p USING (product_id)
WHERE o.order_id IS NULL OR p.product_id IS NULL;

-- test: every order belongs to a known customer
SELECT o.order_id FROM core.fct_orders o LEFT JOIN core.dim_customers c USING (user_id) WHERE c.user_id IS NULL;

-- test: revenue reconciles from line items -> orders -> monthly KPIs (within 1 INR)
SELECT * FROM (
    SELECT (SELECT sum(net_revenue) FROM core.fct_order_items) AS items,
           (SELECT sum(net_revenue) FROM core.fct_orders)      AS orders,
           (SELECT sum(net_revenue) FROM mart.mart_kpi_monthly) AS kpi
) WHERE abs(items - orders) > 1 OR abs(orders - kpi) > 1;

-- test: valid orders (non-internal, deduplicated) reconcile from staging to fct_orders
SELECT * FROM (
    SELECT (SELECT count(*) FROM stg.stg_orders WHERE NOT is_internal) AS stg_n,
           (SELECT count(*) FROM core.fct_orders) AS fct_n
) WHERE stg_n <> fct_n;

-- test: invalid (cancelled / RTO) orders carry zero revenue
SELECT order_id FROM core.fct_orders WHERE NOT is_valid_order AND (net_revenue <> 0 OR gross_margin <> 0);

-- test: net revenue never exceeds gross revenue and is never negative
SELECT order_id FROM core.fct_orders WHERE net_revenue > gross_revenue + 0.01 OR net_revenue < -0.01;

-- test: customer_order_number is a gapless 1..n sequence per customer
SELECT user_id FROM core.fct_orders WHERE is_valid_order
GROUP BY user_id HAVING max(customer_order_number) <> count(*) OR min(customer_order_number) <> 1;

-- test: every customer has exactly one first order
SELECT user_id FROM core.fct_orders GROUP BY user_id HAVING count(*) FILTER (WHERE is_first_order) > 1;

-- test: customer count is consistent between dim_customers and the LTV mart
SELECT * FROM (SELECT (SELECT count(*) FROM core.dim_customers WHERE is_customer) AS a,
                      (SELECT count(*) FROM mart.mart_customer_ltv) AS b) WHERE a <> b;

-- test: cohort sizes in the retention mart sum to the number of customers
SELECT * FROM (
    SELECT (SELECT sum(cohort_size) FROM mart.mart_cohort_retention
            WHERE month_offset = 0 AND acquisition_channel = 'All') AS a,
           (SELECT count(*) FROM core.dim_customers WHERE is_customer) AS b
) WHERE a <> b;

-- test: month-0 retention is 100% for every cohort (everyone ordered in their cohort month)
SELECT * FROM mart.mart_cohort_retention WHERE month_offset = 0 AND abs(retention_rate - 1) > 1e-9;

-- test: retention rates are within [0, 1]
SELECT * FROM mart.mart_cohort_retention WHERE retention_rate < 0 OR retention_rate > 1;

-- test: LTV is non-decreasing over longer horizons for every customer
SELECT user_id FROM mart.mart_customer_ltv
WHERE net_revenue_90d > net_revenue_180d + 0.01 OR net_revenue_180d > net_revenue_365d + 0.01
   OR net_revenue_365d > net_revenue_730d + 0.01 OR net_revenue_first_order > net_revenue_90d + 0.01;

-- test: LTV eligibility flags are nested (eligible for 365d => eligible for 90d)
SELECT user_id FROM mart.mart_customer_ltv
WHERE (eligible_730d AND NOT eligible_365d) OR (eligible_365d AND NOT eligible_180d) OR (eligible_180d AND NOT eligible_90d);

-- test: marketing spend has no non-INR rows left unconverted (all rows matched an FX rate)
SELECT * FROM (SELECT (SELECT count(*) FROM raw.marketing_spend) AS a,
                      (SELECT count(*) FROM stg.stg_marketing_spend) AS b) WHERE a <> b;

-- test: total spend in the channel mart equals staging spend
SELECT * FROM (SELECT (SELECT sum(spend_inr) FROM mart.mart_channel_monthly) AS a,
                      (SELECT sum(spend_inr) FROM stg.stg_marketing_spend) AS b) WHERE abs(a - b) > 1;

-- test: no order is dated before its customer's signup
SELECT o.order_id FROM core.fct_orders o JOIN core.dim_customers c USING (user_id) WHERE o.order_ts < c.signup_ts;
