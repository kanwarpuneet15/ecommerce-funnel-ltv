-- =============================================================================
-- Q: Meta spend was ramped ~2.2x from Mar-Jun 2025. Did the extra spend buy customers
--    as efficiently as before, and were they as valuable?
-- Decision supported: should Paid Social budget stay at the new level?
-- Average CAC hides diminishing returns; MARGINAL CAC (extra spend / extra customers)
-- is the number that matters for the next rupee.
-- Skills: period bucketing with CASE, comparing periods, marginal vs average metrics.
-- =============================================================================
WITH periods AS (
    SELECT *,
        CASE WHEN month_start BETWEEN DATE '2024-03-01' AND DATE '2025-02-01' THEN 'A: before ramp (Mar24-Feb25)'
             WHEN month_start BETWEEN DATE '2025-06-01' AND DATE '2026-05-01' THEN 'B: after ramp (Jun25-May26)'
        END AS period
    FROM mart.mart_channel_monthly
    WHERE channel = 'Paid Social'
),
agg AS (
    SELECT period, sum(spend_inr) AS spend, sum(new_customers) AS new_customers,
           sum(paid_clicks) AS clicks, sum(spend_inr) / sum(paid_clicks) AS cpc
    FROM periods WHERE period IS NOT NULL GROUP BY 1
),
quality AS (
    SELECT CASE WHEN cohort_month BETWEEN DATE '2024-03-01' AND DATE '2025-02-01' THEN 'A: before ramp (Mar24-Feb25)'
                WHEN cohort_month BETWEEN DATE '2025-06-01' AND DATE '2026-05-01' THEN 'B: after ramp (Jun25-May26)' END AS period,
           avg(margin_90d) FILTER (WHERE eligible_90d)                 AS ltv_margin_90d,
           avg((orders_90d >= 2)::int) FILTER (WHERE eligible_90d)     AS repeat_rate_90d,
           avg((first_order_payment_type = 'COD')::int)                AS cod_share
    FROM mart.mart_customer_ltv
    WHERE acquisition_channel = 'Paid Social'
    GROUP BY 1
)
SELECT
    a.period,
    round(a.spend, 0)                       AS spend,
    a.new_customers,
    round(a.cpc, 2)                         AS cpc,
    round(a.spend / a.new_customers, 0)     AS average_cac,
    round((a.spend - lag(a.spend) OVER (ORDER BY a.period))
        / (a.new_customers - lag(a.new_customers) OVER (ORDER BY a.period)), 0) AS marginal_cac,
    round(q.ltv_margin_90d, 0)              AS ltv_margin_90d,
    round(q.repeat_rate_90d, 3)             AS repeat_rate_90d,
    round(q.cod_share, 3)                   AS cod_share
FROM agg a JOIN quality q USING (period)
ORDER BY a.period;
