-- =============================================================================
-- Q: Are newer cohorts deteriorating? If so, is it because each channel got worse,
--    or because the MIX of channels changed?
-- Decision supported: fix retention (product/CRM) vs. fix acquisition mix (marketing).
-- Method: compare blended 3-month repeat rate by cohort quarter with the same metric
-- holding the channel mix fixed at the 2024 baseline ("mix-adjusted").
-- Skills: weighted averages, CTE chains, window functions over groups.
-- =============================================================================
WITH c AS (
    SELECT date_trunc('quarter', cohort_month)::DATE AS cohort_quarter, acquisition_channel,
           count(*) AS customers, avg((orders_90d >= 2)::int) AS repeat_90d
    FROM mart.mart_customer_ltv
    WHERE eligible_90d
    GROUP BY ALL
),
baseline_mix AS (
    SELECT acquisition_channel, sum(customers) / sum(sum(customers)) OVER () AS w
    FROM c WHERE year(cohort_quarter) = 2024 GROUP BY 1
)
SELECT
    c.cohort_quarter,
    sum(c.customers)                                                           AS customers,
    round(sum(c.customers) FILTER (WHERE c.acquisition_channel = 'Paid Social') / sum(c.customers), 3) AS paid_social_share,
    round(sum(c.customers * c.repeat_90d) / sum(c.customers), 4)               AS blended_repeat_90d,
    round(sum(b.w * c.repeat_90d) / sum(b.w), 4)                               AS mix_adjusted_repeat_90d,
    round(max(c.repeat_90d) FILTER (WHERE c.acquisition_channel = 'Paid Social'), 4) AS paid_social_repeat_90d,
    round(max(c.repeat_90d) FILTER (WHERE c.acquisition_channel = 'Paid Search'), 4) AS paid_search_repeat_90d
FROM c JOIN baseline_mix b USING (acquisition_channel)
GROUP BY c.cohort_quarter
ORDER BY c.cohort_quarter;
