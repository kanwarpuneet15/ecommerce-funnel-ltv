-- =============================================================================
-- Q: When do customers come back? How long after the first order should a
--    second-purchase campaign fire?
-- Decision supported: CRM journey timing (e.g. email on day X).
-- Skills: self-join via window (order 1 vs order 2), percentiles, survival-style shares.
-- Population: customers acquired Jan 2024 - Sep 2025 (>= 12 months observable).
-- =============================================================================
WITH second AS (
    SELECT c.user_id, c.acquisition_channel, o.days_since_prev_order AS days_to_second
    FROM core.dim_customers c
    LEFT JOIN core.fct_orders o ON o.user_id = c.user_id AND o.customer_order_number = 2
    WHERE c.is_customer AND c.cohort_month BETWEEN DATE '2024-01-01' AND DATE '2025-09-01'
)
SELECT
    coalesce(acquisition_channel, 'ALL')                                     AS acquisition_channel,
    count(*)                                                                 AS customers,
    round(avg(coalesce(days_to_second <= 30, false)::int), 3)                               AS repeat_within_30d,
    round(avg(coalesce(days_to_second <= 90, false)::int), 3)                               AS repeat_within_90d,
    round(avg(coalesce(days_to_second <= 180, false)::int), 3)                              AS repeat_within_180d,
    round(avg(coalesce(days_to_second <= 365, false)::int), 3)                              AS repeat_within_365d,
    round(quantile_cont(days_to_second, 0.25) FILTER (WHERE days_to_second <= 365), 0) AS p25_days,
    round(quantile_cont(days_to_second, 0.50) FILTER (WHERE days_to_second <= 365), 0) AS median_days,
    round(quantile_cont(days_to_second, 0.75) FILTER (WHERE days_to_second <= 365), 0) AS p75_days
FROM second
GROUP BY ROLLUP (acquisition_channel)
ORDER BY customers DESC;
