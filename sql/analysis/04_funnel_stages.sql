-- =============================================================================
-- Q: How many sessions reach each funnel stage, and where is the largest drop-off?
-- Decision supported: which stage to prioritise for CRO / product investment.
-- Skills: funnel construction, UNPIVOT, window functions (LAG, FIRST_VALUE).
-- Stage logic: "reached this stage or any later stage" (see DQ-12).
-- =============================================================================
WITH totals AS (
    SELECT device_type,
           sum(sessions) AS s1, sum(product_view_sessions) AS s2, sum(cart_sessions) AS s3,
           sum(checkout_sessions) AS s4, sum(purchase_sessions) AS s5
    FROM mart.mart_funnel_daily
    WHERE session_date BETWEEN DATE '2025-10-01' AND DATE '2026-09-30'
    GROUP BY ROLLUP (device_type)
),
long AS (
    UNPIVOT totals ON s1, s2, s3, s4, s5 INTO NAME stage_key VALUE sessions
)
SELECT
    coalesce(device_type, 'all devices')                                    AS device_type,
    CASE stage_key WHEN 's1' THEN '1. Session' WHEN 's2' THEN '2. Product view'
                   WHEN 's3' THEN '3. Add to cart' WHEN 's4' THEN '4. Checkout'
                   ELSE '5. Purchase' END                                   AS stage,
    sessions,
    round(sessions / lag(sessions) OVER w, 4)                               AS step_conversion,
    lag(sessions) OVER w - sessions                                         AS sessions_lost_at_step,
    round(sessions / first_value(sessions) OVER w, 4)                       AS conversion_from_start
FROM long
WINDOW w AS (PARTITION BY device_type ORDER BY stage_key)
ORDER BY device_type NULLS FIRST, stage;
