-- =============================================================================
-- stg_order_items
-- Grain: one row per order line.
-- Revenue definitions (INR, excluding shipping fees, which are pass-through):
--   gmv            = list price x quantity (before discount)
--   gross_revenue  = gmv - discount
--   returned_revenue = gross_revenue of lines the customer sent back
--   cogs           = unit cost x quantity
-- Free-gift lines (100% discount) are legitimate and kept: revenue 0, cost > 0.
-- =============================================================================
CREATE OR REPLACE TABLE stg.stg_order_items AS
SELECT
    i.order_item_id,
    i.order_id,
    i.product_id,
    i.quantity,
    i.unit_price,
    i.discount_amount,
    i.unit_price * i.quantity                                       AS gmv,
    i.unit_price * i.quantity - i.discount_amount                   AS gross_revenue,
    p.unit_cost * i.quantity                                        AS cogs,
    i.returned_at,
    i.returned_at IS NOT NULL                                       AS is_returned,
    CASE WHEN i.returned_at IS NOT NULL
         THEN i.unit_price * i.quantity - i.discount_amount ELSE 0 END AS returned_revenue,
    i.discount_amount = i.unit_price * i.quantity AND i.unit_price > 1 AS is_free_gift
FROM raw.order_items i
LEFT JOIN raw.products p USING (product_id);
