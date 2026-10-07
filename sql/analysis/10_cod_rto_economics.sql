-- =============================================================================
-- Q: What does Cash-on-Delivery cost us? How do COD-first customers compare on RTO,
--    repeat rate and LTV, by city tier?
-- Decision supported: COD policy (fees, prepaid incentives, tier-specific rules).
-- Skills: multi-dimensional GROUP BY, conditional aggregation, joins across grains.
-- =============================================================================
WITH orders AS (
    SELECT o.payment_type, c.city_tier,
           count(*) AS orders_placed,
           avg(o.is_rto::int) AS rto_rate,
           avg(o.is_cancelled::int) AS cancel_rate,
           sum(o.gross_revenue_placed) FILTER (WHERE o.is_rto) AS gross_value_lost_to_rto
    FROM core.fct_orders o JOIN core.dim_customers c USING (user_id)
    WHERE o.order_date <= DATE '2026-08-31'          -- exclude orders whose RTO may not be known yet
    GROUP BY ALL
),
cust AS (
    SELECT first_order_payment_type AS payment_type, city_tier,
           avg(margin_365d) AS ltv_margin_365d, avg((orders_365d >= 2)::int) AS repeat_rate_365d,
           count(*) AS customers
    FROM mart.mart_customer_ltv WHERE eligible_365d
    GROUP BY ALL
)
SELECT o.payment_type, o.city_tier, o.orders_placed,
       round(o.rto_rate, 3) AS rto_rate, round(o.cancel_rate, 3) AS cancel_rate,
       round(o.gross_value_lost_to_rto, 0) AS gross_value_lost_to_rto,
       c.customers AS customers_365d, round(c.repeat_rate_365d, 3) AS repeat_rate_365d,
       round(c.ltv_margin_365d, 0) AS ltv_margin_365d
FROM orders o LEFT JOIN cust c USING (payment_type, city_tier)
ORDER BY o.city_tier, o.payment_type;
