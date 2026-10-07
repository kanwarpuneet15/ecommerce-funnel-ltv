-- =============================================================================
-- Q: How are revenue, orders and conversion trending, net of seasonality noise?
-- Decision supported: is growth real or sale-driven; year-on-year health check.
-- Skills: window functions (LAG, rolling AVG over frames), date functions.
-- =============================================================================
SELECT
    month_start,
    round(net_revenue, 0)                                                     AS net_revenue,
    valid_orders,
    new_customers,
    round(session_conversion_rate, 4)                                         AS conversion,
    round(net_revenue / lag(net_revenue) OVER w - 1, 3)                       AS mom_growth,
    round(net_revenue / lag(net_revenue, 12) OVER w - 1, 3)                   AS yoy_growth,
    round(avg(net_revenue) OVER (w ROWS BETWEEN 2 PRECEDING AND CURRENT ROW), 0) AS net_revenue_3m_avg,
    round(sum(net_revenue) OVER (w ROWS BETWEEN 11 PRECEDING AND CURRENT ROW), 0) AS net_revenue_ttm,
    round(marketing_spend_pct_net_revenue, 3)                                 AS marketing_pct_revenue
FROM mart.mart_kpi_monthly
WHERE is_complete_month
WINDOW w AS (ORDER BY month_start)
ORDER BY month_start;
