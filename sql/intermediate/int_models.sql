-- =============================================================================
-- INTERMEDIATE LAYER: reusable building blocks with business logic.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS int;

-- -----------------------------------------------------------------------------
-- int_identity_map  (DQ-7)
-- Grain: one row per visitor_id that has ever logged in.
-- Visitors browse anonymously until they register or log in. Any event carrying both
-- ids links them, so earlier anonymous sessions can be credited to the user.
-- Limitation: one cookie = one visitor; cross-device journeys are not stitched.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE int.int_identity_map AS
SELECT
    visitor_id,
    min(user_id)          AS user_id,          -- profiling showed exactly 1 user per visitor
    count(DISTINCT user_id) AS n_users_seen,
    min(event_ts)         AS first_identified_ts
FROM stg.stg_events
WHERE user_id IS NOT NULL
GROUP BY visitor_id;

-- -----------------------------------------------------------------------------
-- int_order_values
-- Grain: one row per order. Line-level money rolled up (DQ-10: line items are the
-- source of truth, not the reported order_total).
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE int.int_order_values AS
SELECT
    order_id,
    count(*)                                              AS n_lines,
    sum(quantity)                                         AS units,
    sum(gmv)                                              AS gmv,
    sum(discount_amount)                                  AS discount_amount,
    sum(gross_revenue)                                    AS gross_revenue,
    sum(returned_revenue)                                 AS returned_revenue,
    sum(gross_revenue) - sum(returned_revenue)            AS net_revenue,
    sum(cogs)                                             AS cogs_all_lines,
    sum(CASE WHEN NOT is_returned THEN cogs ELSE 0 END)   AS cogs_kept_lines,
    max(is_returned::int)::boolean                        AS has_return,
    bool_and(is_returned)                                 AS fully_returned
FROM stg.stg_order_items
GROUP BY order_id;

-- -----------------------------------------------------------------------------
-- int_customer_acquisition
-- Grain: one row per (non-internal) user.
-- Acquisition channel = channel of the user's FIRST tracked, non-bot session that
-- happened before their first valid order (first-touch attribution).
-- If no tracked session precedes the first order (ad blocker, consent), the user is
-- 'Unattributed' (DQ-11) rather than silently assigned to Direct.
-- -----------------------------------------------------------------------------
CREATE OR REPLACE TABLE int.int_customer_acquisition AS
WITH user_sessions AS (
    SELECT coalesce(s.user_id_logged_in, m.user_id) AS user_id, s.*
    FROM stg.stg_sessions s
    LEFT JOIN int.int_identity_map m USING (visitor_id)
    WHERE NOT s.is_bot
),
first_valid_order AS (
    SELECT user_id, min(order_ts) AS first_order_ts
    FROM stg.stg_orders WHERE is_valid_order AND NOT is_internal
    GROUP BY user_id
),
first_touch AS (
    SELECT us.user_id, us.channel, us.device_type, us.session_start, us.utm_campaign
    FROM user_sessions us
    LEFT JOIN first_valid_order f USING (user_id)
    WHERE us.user_id IS NOT NULL
      AND (f.first_order_ts IS NULL OR us.session_start <= f.first_order_ts)
    QUALIFY row_number() OVER (PARTITION BY us.user_id ORDER BY us.session_start) = 1
)
SELECT
    u.user_id,
    coalesce(ft.channel, 'Unattributed')       AS acquisition_channel,
    ft.device_type                             AS acquisition_device,
    ft.utm_campaign                            AS acquisition_campaign,
    ft.session_start                           AS first_visit_ts,
    ft.user_id IS NOT NULL                     AS has_tracked_first_touch
FROM stg.stg_users u
LEFT JOIN first_touch ft USING (user_id)
WHERE NOT u.is_internal;
