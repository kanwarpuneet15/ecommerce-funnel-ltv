-- =============================================================================
-- Q: Did the mobile checkout redesign (shipped 2025-08-01) improve checkout completion?
-- Decision supported: credit the redesign (and invest further) vs. look elsewhere.
-- Method: difference-in-differences. Desktop (unchanged) is the control group: it absorbs
-- seasonality and sale effects that hit both devices. 6 months before vs 6 months after.
-- Assumption to check: parallel pre-trends (see notebook 02 chart).
-- Skills: CTEs, conditional aggregation, pivoting with FILTER, simple inference (SE).
-- =============================================================================
WITH labelled AS (
    SELECT device_type, checkout_sessions, purchase_sessions,
           CASE WHEN session_date BETWEEN DATE '2025-02-01' AND DATE '2025-07-31' THEN 'pre'
                WHEN session_date BETWEEN DATE '2025-08-01' AND DATE '2026-01-31' THEN 'post' END AS period
    FROM mart.mart_funnel_daily
    WHERE device_type IN ('mobile', 'desktop')
),
base AS (
    SELECT device_type, period,
           sum(checkout_sessions)::DOUBLE AS checkouts, sum(purchase_sessions)::DOUBLE AS purchases
    FROM labelled
    WHERE period IS NOT NULL
    GROUP BY device_type, period
),
rates AS (
    SELECT *, purchases / checkouts AS rate,
           purchases / checkouts * (1 - purchases / checkouts) / checkouts AS var
    FROM base
),
p AS (
    SELECT
        max(rate) FILTER (WHERE device_type = 'mobile'  AND period = 'pre')  AS mobile_pre,
        max(rate) FILTER (WHERE device_type = 'mobile'  AND period = 'post') AS mobile_post,
        max(rate) FILTER (WHERE device_type = 'desktop' AND period = 'pre')  AS desktop_pre,
        max(rate) FILTER (WHERE device_type = 'desktop' AND period = 'post') AS desktop_post,
        sqrt(sum(var))                                                        AS se_did
    FROM rates
)
SELECT
    round(mobile_pre, 4) AS mobile_pre, round(mobile_post, 4) AS mobile_post,
    round(desktop_pre, 4) AS desktop_pre, round(desktop_post, 4) AS desktop_post,
    round(mobile_post - mobile_pre, 4)                                       AS mobile_change,
    round(desktop_post - desktop_pre, 4)                                     AS desktop_change,
    round((mobile_post - mobile_pre) - (desktop_post - desktop_pre), 4)      AS did_estimate,
    round((mobile_post - mobile_pre) - (desktop_post - desktop_pre) - 1.96 * se_did, 4) AS did_ci_low,
    round((mobile_post - mobile_pre) - (desktop_post - desktop_pre) + 1.96 * se_did, 4) AS did_ci_high
FROM p;
