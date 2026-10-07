-- =============================================================================
-- Q: What is the size and health of the business over the last 12 complete months?
-- Decision supported: baseline for every other analysis; executive dashboard tiles.
-- Skills: SELECT, WHERE, aggregation, CASE, conditional aggregation.
-- Definitions:
--   Net revenue  = item revenue after discounts, minus returns; excludes cancelled/RTO and shipping
--   AOV          = gross revenue / valid orders (before returns)
--   Conversion   = sessions with a purchase / all non-bot sessions
-- =============================================================================
WITH o AS (
    SELECT * FROM core.fct_orders
    WHERE order_date BETWEEN DATE '2025-10-01' AND DATE '2026-09-30'
),
s AS (
    SELECT * FROM core.fct_sessions
    WHERE session_date BETWEEN DATE '2025-10-01' AND DATE '2026-09-30'
)
SELECT
    round(sum(o.net_revenue) / 1e5, 2)                                         AS net_revenue_lakh_inr,
    round(sum(o.gross_margin) / nullif(sum(o.net_revenue), 0), 3)              AS gross_margin_pct,
    count(*) FILTER (WHERE o.is_valid_order)                                   AS valid_orders,
    count(DISTINCT o.user_id) FILTER (WHERE o.is_valid_order)                  AS active_customers,
    count(*) FILTER (WHERE o.is_first_order)                                   AS new_customers,
    round(sum(o.gross_revenue) / count(*) FILTER (WHERE o.is_valid_order), 0)  AS aov_inr,
    round(median(o.gross_revenue) FILTER (WHERE o.is_valid_order), 0)          AS median_order_inr,
    round(count(*) FILTER (WHERE o.customer_order_number > 1)
          / count(*) FILTER (WHERE o.is_valid_order), 3)                       AS repeat_order_share,
    round(sum(o.returned_revenue) / sum(o.gross_revenue), 3)                   AS return_rate_by_value,
    round(avg(o.is_rto::int), 3)                                               AS rto_rate,
    round(avg(o.is_cancelled::int), 3)                                         AS cancel_rate,
    round(avg((o.payment_type = 'COD')::int), 3)                               AS cod_share,
    (SELECT count(*) FROM s)                                                   AS sessions,
    (SELECT round(avg(purchased::int), 4) FROM s)                              AS session_conversion
FROM o;
