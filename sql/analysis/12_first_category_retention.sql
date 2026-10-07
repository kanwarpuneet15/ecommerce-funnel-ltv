-- =============================================================================
-- Q: Does what a customer buys first predict whether they come back?
-- Decision supported: which categories to feature in acquisition ads / welcome offers.
-- Skills: aggregation with HAVING, ranking (RANK), comparison to overall average.
-- =============================================================================
WITH c AS (
    SELECT l.*, d.first_order_category
    FROM mart.mart_customer_ltv l JOIN core.dim_customers d USING (user_id)
    WHERE l.eligible_365d
)
SELECT
    first_order_category,
    count(*)                                                    AS customers,
    round(avg((orders_365d >= 2)::int), 3)                      AS repeat_rate_365d,
    round(avg((orders_365d >= 2)::int) - (SELECT avg((orders_365d >= 2)::int) FROM c), 3) AS vs_average,
    round(avg(margin_first_order), 0)                           AS first_order_margin,
    round(avg(margin_365d), 0)                                  AS ltv_margin_365d,
    rank() OVER (ORDER BY avg(margin_365d) DESC)                AS ltv_rank
FROM c
GROUP BY first_order_category
HAVING count(*) >= 200
ORDER BY ltv_rank;
