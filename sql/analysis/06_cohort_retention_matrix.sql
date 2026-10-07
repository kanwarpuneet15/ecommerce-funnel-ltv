-- =============================================================================
-- Q: How does repeat-purchase retention evolve by acquisition month?
-- Decision supported: are newer cohorts better or worse? Is retention a growth lever?
-- Retention(k) = % of the cohort with >= 1 valid order in calendar month cohort+k.
-- Only fully observed months are shown (the triangle), so recent cohorts are not
-- penalised for months that have not happened yet.
-- Skills: cohort assignment, retention matrix, PIVOT.
-- =============================================================================
PIVOT (
    SELECT strftime(cohort_month, '%Y-%m') AS cohort, cohort_size,
           'M' || lpad(month_offset::varchar, 2, '0') AS m, round(100 * retention_rate, 1) AS retention_pct
    FROM mart.mart_cohort_retention
    WHERE acquisition_channel = 'All' AND month_offset BETWEEN 0 AND 12
)
ON m USING first(retention_pct)
ORDER BY cohort;
