-- =============================================================================
-- Q: How concentrated is value? What share of margin comes from the top customers,
--    and who are they?
-- Decision supported: VIP/retention programme sizing; who to protect.
-- Skills: NTILE, percentiles (quantile_cont), cumulative share with window SUM.
-- Population: customers acquired Jan 2024 - Sep 2024 (>= 24 months of history).
-- =============================================================================
WITH c AS (
    SELECT user_id, margin_to_date, net_revenue_to_date, orders_to_date, acquisition_channel,
           ntile(10) OVER (ORDER BY margin_to_date DESC) AS decile
    FROM mart.mart_customer_ltv
    WHERE cohort_month BETWEEN DATE '2024-01-01' AND DATE '2024-09-01'
)
SELECT
    decile,
    count(*)                                                       AS customers,
    round(avg(orders_to_date), 2)                                  AS avg_orders,
    round(quantile_cont(margin_to_date, 0.5), 0)                   AS median_margin,
    round(sum(margin_to_date), 0)                                  AS total_margin,
    round(sum(margin_to_date) / sum(sum(margin_to_date)) OVER (), 3) AS share_of_margin,
    round(sum(sum(margin_to_date)) OVER (ORDER BY decile) / sum(sum(margin_to_date)) OVER (), 3) AS cumulative_share,
    round(avg((acquisition_channel = 'Paid Social')::int), 3)      AS paid_social_share
FROM c
GROUP BY decile
ORDER BY decile;
