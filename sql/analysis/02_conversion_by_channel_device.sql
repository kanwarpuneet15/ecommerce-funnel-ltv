-- =============================================================================
-- Q: Which acquisition channels and devices convert best (session -> purchase)?
-- Decision supported: where to send traffic; which device experience needs work.
-- Skills: GROUP BY with ROLLUP-style totals, conditional aggregation, ratios.
-- Note: conversion here is per SESSION (last-click view). Customer quality is in 07.
-- =============================================================================
SELECT
    coalesce(channel, 'ALL CHANNELS')                                        AS channel,
    count(*)                                                                 AS sessions,
    round(count(*) FILTER (WHERE device_type = 'mobile') / count(*), 3)      AS mobile_share,
    round(avg(purchased::int), 4)                                            AS conversion_all,
    round(avg(purchased::int) FILTER (WHERE device_type = 'mobile'), 4)      AS conversion_mobile,
    round(avg(purchased::int) FILTER (WHERE device_type = 'desktop'), 4)     AS conversion_desktop,
    round(avg(purchased::int) FILTER (WHERE device_type = 'tablet'), 4)      AS conversion_tablet,
    round(avg(purchased::int) FILTER (WHERE visitor_type = 'New visitor'), 4) AS conversion_new_visitors
FROM core.fct_sessions
WHERE session_date BETWEEN DATE '2025-10-01' AND DATE '2026-09-30'
GROUP BY ROLLUP (channel)
ORDER BY sessions DESC;
