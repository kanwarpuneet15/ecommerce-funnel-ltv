-- =============================================================================
-- stg_orders
-- Grain: one row per order_id.
--   DQ-2  duplicate rows from an ETL re-load -> one row per order_id
--   DQ-9  status casing normalised
--   DQ-8  internal QA orders flagged
-- Order timestamps are already local IST (orders database), no conversion needed.
-- =============================================================================
CREATE OR REPLACE TABLE stg.stg_orders AS
WITH dedup AS (
    SELECT * FROM raw.orders
    QUALIFY row_number() OVER (PARTITION BY order_id ORDER BY created_at) = 1
)
SELECT
    o.order_id,
    o.user_id,
    o.created_at                                   AS order_ts,
    CAST(o.created_at AS DATE)                     AS order_date,
    lower(o.status)                                AS status,
    upper(o.payment_method)                        AS payment_method,
    CASE WHEN upper(o.payment_method) = 'COD' THEN 'COD' ELSE 'Prepaid' END AS payment_type,
    o.discount_code,
    o.shipping_fee,
    o.order_total                                  AS order_total_reported,   -- kept for reconciliation only
    o.shipped_at,
    o.delivered_at,
    o.rto_at,
    o.cancelled_at,
    lower(o.status) = 'cancelled'                  AS is_cancelled,
    lower(o.status) = 'rto'                        AS is_rto,                 -- returned to origin (undelivered)
    lower(o.status) IN ('processing', 'shipped')   AS is_in_flight,
    -- "Valid" order = the customer bought and it was not cancelled or refused at the door.
    -- Used for customer counts, retention and LTV.
    lower(o.status) NOT IN ('cancelled', 'rto')    AS is_valid_order,
    coalesce(u.is_internal, false)                 AS is_internal
FROM dedup o
LEFT JOIN stg.stg_users u USING (user_id);
