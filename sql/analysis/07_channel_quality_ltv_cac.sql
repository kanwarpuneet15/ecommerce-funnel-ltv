-- =============================================================================
-- Q: Do the channels that bring the most customers also bring the most valuable ones?
--    What is LTV:CAC and payback by channel?
-- Decision supported: budget reallocation; max CAC bids per channel.
-- LTV = average cumulative GROSS MARGIN within 365 days of first order, over customers
--       whose 365d (+30d return window) is complete (right-censoring handled).
-- CAC = channel cost / new customers acquired (first touch), same acquisition window.
--       Window: customers acquired Jan 2024 - Aug 2025 (all have a complete 365d LTV).
-- Payback = months until cumulative margin >= CAC (from the cohort margin curve).
-- Skills: multi-CTE joins, customer-level aggregation, ratio metrics, NULL-safe division.
-- =============================================================================
WITH ltv AS (
    SELECT acquisition_channel AS channel,
           count(*)                                   AS customers,
           avg(margin_first_order)                    AS margin_first_order,
           avg(margin_90d)                            AS ltv_margin_90d,
           avg(margin_365d)                           AS ltv_margin_365d,
           avg(net_revenue_365d)                      AS ltv_revenue_365d,
           avg((orders_365d >= 2)::int)               AS repeat_rate_365d
    FROM mart.mart_customer_ltv
    WHERE eligible_365d
    GROUP BY 1
),
cac AS (
    SELECT channel, sum(spend_inr) AS spend, sum(new_customers) AS new_customers,
           sum(spend_inr) / sum(new_customers) AS cac
    FROM mart.mart_channel_monthly
    WHERE month_start BETWEEN DATE '2024-01-01' AND DATE '2025-08-01'
      AND channel IN ('Paid Search', 'Paid Social', 'Affiliate')   -- channels with acquisition cost data
    GROUP BY 1
),
curve AS (     -- cumulative margin per acquired customer by month offset
    SELECT r.acquisition_channel AS channel, r.month_offset,
           sum(sum(r.gross_margin)) OVER (PARTITION BY r.acquisition_channel ORDER BY r.month_offset)
             / max(sum(r.cohort_size)) OVER (PARTITION BY r.acquisition_channel) AS cum_margin_per_customer
    FROM mart.mart_cohort_retention r
    WHERE r.cohort_month BETWEEN DATE '2024-01-01' AND DATE '2024-09-01'   -- cohorts observable for 24 months
      AND r.month_offset <= 24
    GROUP BY 1, 2
)
SELECT
    l.channel,
    l.customers                                        AS customers_365d_eligible,
    round(l.repeat_rate_365d, 3)                       AS repeat_rate_365d,
    round(l.margin_first_order, 0)                     AS first_order_margin,
    round(l.ltv_margin_365d, 0)                        AS ltv_margin_365d,
    round(l.ltv_revenue_365d, 0)                       AS ltv_revenue_365d,
    round(c.cac, 0)                                    AS cac,
    round(l.ltv_margin_365d / c.cac, 2)                AS ltv_to_cac_365d,
    (SELECT min(month_offset) FROM curve cv WHERE cv.channel = l.channel
        AND cv.cum_margin_per_customer >= c.cac)       AS payback_months,
    round(l.ltv_margin_365d / 3, 0)                    AS max_cac_at_3x
FROM ltv l
LEFT JOIN cac c USING (channel)
ORDER BY l.customers DESC;
