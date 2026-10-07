-- =============================================================================
-- CORE (star schema): dimensions and facts used by every analysis and the dashboard.
-- Internal QA users/orders and bot sessions are EXCLUDED here, so no downstream
-- query can accidentally include them.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS core;

-- -----------------------------------------------------------------------------
-- dim_date — Grain: one row per calendar day in the data window.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE core.dim_date AS
SELECT
    d::DATE                                       AS date_day,
    date_trunc('week', d)::DATE                   AS week_start,
    date_trunc('month', d)::DATE                  AS month_start,
    strftime(d, '%Y-%m')                          AS year_month,
    year(d)                                       AS year,
    quarter(d)                                    AS quarter,
    dayname(d)                                    AS day_name,
    isodow(d) >= 6                                AS is_weekend,
    sc.sale_name IS NOT NULL                      AS is_sale_day,
    sc.sale_name,
    sc.sale_type,
    date_trunc('month', d)::DATE <= last_complete_month() AS is_complete_month
FROM generate_series(DATE '2024-01-01', snapshot_date(), INTERVAL 1 DAY) t(d)
LEFT JOIN seeds.sale_calendar sc ON d::DATE BETWEEN sc.start_date AND sc.end_date;

-- -----------------------------------------------------------------------------
-- dim_products — Grain: one row per product.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE core.dim_products AS
SELECT * FROM stg.stg_products;

-- -----------------------------------------------------------------------------
-- fct_sessions — Grain: one row per non-bot session.
-- Funnel stages use "reached this stage OR ANY LATER stage" (DQ-12): a Buy-Now
-- purchase that skipped the cart still counts as having passed the cart stage.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE core.fct_sessions AS
WITH first_valid_order AS (
    SELECT user_id, min(order_ts) AS first_order_ts
    FROM stg.stg_orders WHERE is_valid_order AND NOT is_internal GROUP BY user_id
),
s AS (
    SELECT s.*, coalesce(s.user_id_logged_in, m.user_id) AS user_id,
           row_number() OVER (PARTITION BY s.visitor_id ORDER BY s.session_start) AS visit_number
    FROM stg.stg_sessions s
    LEFT JOIN int.int_identity_map m USING (visitor_id)
    WHERE NOT s.is_bot
)
SELECT
    s.session_id,
    s.visitor_id,
    s.user_id,
    s.session_start,
    CAST(s.session_start AS DATE)                    AS session_date,
    date_trunc('month', s.session_start)::DATE       AS session_month,
    s.channel,
    s.device_type,
    s.browser,
    s.utm_campaign,
    s.visit_number,
    CASE WHEN f.first_order_ts < s.session_start THEN 'Existing customer'
         WHEN s.visit_number = 1                 THEN 'New visitor'
         ELSE 'Returning prospect' END               AS visitor_type,
    TRUE                                             AS reached_session,
    (s.n_product_views + s.n_add_to_cart + s.n_begin_checkout + s.n_purchase) > 0 AS reached_product_view,
    (s.n_add_to_cart + s.n_begin_checkout + s.n_purchase) > 0                     AS reached_cart,
    (s.n_begin_checkout + s.n_purchase) > 0                                       AS reached_checkout,
    s.n_purchase > 0                                                              AS purchased,
    s.n_add_to_cart = 0 AND s.n_purchase > 0                                      AS is_buy_now_purchase,
    s.order_id,
    s.n_events,
    s.duration_seconds,
    d.is_sale_day
FROM s
LEFT JOIN first_valid_order f USING (user_id)
LEFT JOIN core.dim_date d ON d.date_day = CAST(s.session_start AS DATE);

-- -----------------------------------------------------------------------------
-- fct_orders — Grain: one row per real (non-internal) order, incl. cancelled/RTO.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE core.fct_orders AS
WITH o AS (
    SELECT o.*, v.n_lines, v.units, v.gmv, v.discount_amount, v.gross_revenue,
           v.returned_revenue, v.net_revenue, v.cogs_all_lines, v.cogs_kept_lines, v.has_return, v.fully_returned
    FROM stg.stg_orders o
    JOIN int.int_order_values v USING (order_id)
    WHERE NOT o.is_internal
),
numbered AS (
    SELECT o.*,
        CASE WHEN is_valid_order THEN
            row_number() OVER (PARTITION BY user_id, is_valid_order ORDER BY order_ts) END AS customer_order_number,
        CASE WHEN is_valid_order THEN
            lag(order_ts) OVER (PARTITION BY user_id, is_valid_order ORDER BY order_ts) END AS prev_valid_order_ts
    FROM o
),
order_session AS (            -- last-click session: the session containing the purchase event
    SELECT order_id, any_value(channel) AS order_session_channel, any_value(device_type) AS order_session_device,
           any_value(session_id) AS session_id
    FROM core.fct_sessions WHERE order_id IS NOT NULL GROUP BY order_id
)
SELECT
    n.order_id,
    n.user_id,
    n.order_ts,
    n.order_date,
    date_trunc('month', n.order_ts)::DATE              AS order_month,
    n.status,
    n.payment_method,
    n.payment_type,
    n.discount_code,
    n.discount_code IS NOT NULL                        AS is_discounted,
    d.is_sale_day                                      AS is_sale_order,
    d.sale_name,
    n.is_valid_order,
    n.is_cancelled,
    n.is_rto,
    n.is_in_flight,
    n.has_return,
    n.fully_returned,
    n.n_lines,
    n.units,
    n.gmv,
    n.discount_amount,
    -- Money only counts for valid orders. Cancelled / RTO orders generate no revenue.
    CASE WHEN n.is_valid_order THEN n.gross_revenue ELSE 0 END                         AS gross_revenue,
    CASE WHEN n.is_valid_order THEN n.returned_revenue ELSE 0 END                      AS returned_revenue,
    CASE WHEN n.is_valid_order THEN n.net_revenue ELSE 0 END                           AS net_revenue,
    CASE WHEN n.is_valid_order THEN n.cogs_kept_lines ELSE 0 END                       AS cogs,
    -- Product gross margin: net revenue minus cost of goods kept by the customer.
    -- Returned goods are assumed restocked. Fulfilment/RTO logistics costs are NOT in the data.
    CASE WHEN n.is_valid_order THEN n.net_revenue - n.cogs_kept_lines ELSE 0 END      AS gross_margin,
    n.gross_revenue                                    AS gross_revenue_placed,  -- incl. cancelled/RTO (demand)
    n.shipping_fee,
    n.order_total_reported,
    abs(n.order_total_reported - (n.gross_revenue + n.shipping_fee)) > 1 AS has_total_mismatch,
    n.customer_order_number,
    n.customer_order_number = 1                        AS is_first_order,
    date_diff('day', n.prev_valid_order_ts, n.order_ts) AS days_since_prev_order,
    s.session_id,
    s.session_id IS NOT NULL                           AS is_tracked,
    coalesce(s.order_session_channel, 'Untracked')     AS order_session_channel,   -- last click
    coalesce(s.order_session_device, 'unknown')        AS order_session_device,
    a.acquisition_channel                                                          -- customer's first touch
FROM numbered n
LEFT JOIN order_session s USING (order_id)
LEFT JOIN int.int_customer_acquisition a USING (user_id)
LEFT JOIN core.dim_date d ON d.date_day = n.order_date;

-- -----------------------------------------------------------------------------
-- fct_order_items — Grain: one row per order line of a real order.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE core.fct_order_items AS
SELECT
    i.order_item_id,
    i.order_id,
    o.user_id,
    o.order_ts,
    o.order_month,
    i.product_id,
    p.category,
    p.department,
    i.quantity,
    i.gmv,
    i.discount_amount,
    i.gross_revenue,
    i.is_returned,
    i.returned_revenue,
    i.cogs,
    i.is_free_gift,
    o.is_valid_order,
    CASE WHEN o.is_valid_order THEN i.gross_revenue - i.returned_revenue ELSE 0 END AS net_revenue,
    CASE WHEN o.is_valid_order THEN i.gross_revenue - i.returned_revenue
                                    - CASE WHEN i.is_returned THEN 0 ELSE i.cogs END ELSE 0 END AS gross_margin
FROM stg.stg_order_items i
JOIN core.fct_orders o USING (order_id)
JOIN core.dim_products p USING (product_id);

-- -----------------------------------------------------------------------------
-- dim_customers — Grain: one row per real registered user (buyers and non-buyers).
-- Cohort = calendar month of FIRST VALID ORDER (not signup): retention measures
-- repeat buying, so the clock starts when someone becomes a customer.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE core.dim_customers AS
WITH ord AS (
    SELECT user_id,
        min(order_ts)                                  AS first_order_ts,
        max(order_ts)                                  AS last_order_ts,
        count(*)                                       AS valid_orders,
        sum(net_revenue)                               AS net_revenue_to_date,
        sum(gross_margin)                              AS gross_margin_to_date
    FROM core.fct_orders WHERE is_valid_order GROUP BY user_id
),
first_o AS (
    SELECT o.user_id, o.payment_type AS first_order_payment_type, o.is_discounted AS first_order_discounted,
           o.is_sale_order AS acquired_in_sale, o.net_revenue AS first_order_net_revenue,
           o.has_return AS first_order_had_return, o.order_session_channel AS first_order_session_channel
    FROM core.fct_orders o WHERE o.is_first_order
),
first_cat AS (           -- category of the highest-value line in the first order
    SELECT i.user_id, i.category AS first_order_category
    FROM core.fct_order_items i JOIN core.fct_orders o USING (order_id)
    WHERE o.is_first_order
    QUALIFY row_number() OVER (PARTITION BY i.user_id ORDER BY i.gross_revenue DESC, i.order_item_id) = 1
),
any_rto AS (
    SELECT user_id, bool_or(is_rto) AS ever_rto, count(*) FILTER (WHERE is_rto) AS rto_orders
    FROM core.fct_orders GROUP BY user_id
)
SELECT
    u.user_id,
    u.signup_ts,
    u.gender,
    u.age_band,
    u.city,
    u.state,
    u.city_tier,
    a.acquisition_channel,
    a.acquisition_device,
    a.first_visit_ts,
    a.has_tracked_first_touch,
    ord.first_order_ts IS NOT NULL                     AS is_customer,
    ord.first_order_ts,
    date_trunc('month', ord.first_order_ts)::DATE      AS cohort_month,
    ord.last_order_ts,
    date_diff('day', ord.last_order_ts, snapshot_ts()) AS days_since_last_order,
    date_diff('day', ord.first_order_ts, snapshot_ts()) AS customer_age_days,
    coalesce(ord.valid_orders, 0)                      AS valid_orders,
    coalesce(ord.valid_orders, 0) >= 2                 AS is_repeat_customer,
    coalesce(ord.net_revenue_to_date, 0)               AS net_revenue_to_date,
    coalesce(ord.gross_margin_to_date, 0)              AS gross_margin_to_date,
    fo.first_order_payment_type,
    fo.first_order_discounted,
    fo.acquired_in_sale,
    fo.first_order_net_revenue,
    fo.first_order_had_return,
    fo.first_order_session_channel,
    fc.first_order_category,
    coalesce(r.ever_rto, false)                        AS ever_rto,
    coalesce(r.rto_orders, 0)                          AS rto_orders
FROM stg.stg_users u
JOIN int.int_customer_acquisition a USING (user_id)
LEFT JOIN ord USING (user_id)
LEFT JOIN first_o fo USING (user_id)
LEFT JOIN first_cat fc USING (user_id)
LEFT JOIN any_rto r USING (user_id)
WHERE NOT u.is_internal;
