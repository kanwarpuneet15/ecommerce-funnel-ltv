-- =============================================================================
-- stg_events
-- Grain: one row per unique tracked event.
-- Cleaning decisions (see docs/data_quality_report.md):
--   DQ-1  duplicate events: keep one row per event_id, then one per natural key
--   DQ-3  timestamps: UTC -> IST (business time zone, matches the orders system)
--   DQ-4  drop events dated after the snapshot (device clock skew)
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS stg;

CREATE OR REPLACE TABLE stg.stg_events AS
WITH parsed AS (
    SELECT
        event_id,
        strptime(event_ts_utc, '%Y-%m-%dT%H:%M:%S.%gZ')                       AS event_ts_utc,
        strptime(event_ts_utc, '%Y-%m-%dT%H:%M:%S.%gZ') + INTERVAL 330 MINUTE AS event_ts,   -- IST
        lower(trim(event_name))   AS event_name,
        session_id,
        visitor_id,
        user_id,
        lower(device_type)        AS device_type,
        browser,
        nullif(lower(trim(utm_source)), '')   AS utm_source,
        nullif(lower(trim(utm_medium)), '')   AS utm_medium,
        nullif(lower(trim(utm_campaign)), '') AS utm_campaign,
        nullif(lower(trim(referrer_domain)), '') AS referrer_domain,
        page_path,
        product_id,
        order_id
    FROM raw.events
),
dedup_id AS (                      -- DQ-1a: client retries re-send the same event_id
    SELECT * FROM parsed
    QUALIFY row_number() OVER (PARTITION BY event_id ORDER BY event_ts_utc) = 1
),
dedup_content AS (                 -- DQ-1b: same event re-sent with a fresh id
    SELECT * FROM dedup_id
    QUALIFY row_number() OVER (
        PARTITION BY session_id, event_name, event_ts_utc, coalesce(product_id, -1), coalesce(order_id, -1)
        ORDER BY event_id) = 1
)
SELECT *
FROM dedup_content
WHERE event_ts <= snapshot_ts();   -- DQ-4
