-- =============================================================================
-- stg_sessions
-- Grain: one row per session_id (sessions are defined by the tracker).
-- Adds:
--   * marketing channel grouping (DQ-6) — ordered rules, first match wins
--   * bot flag (DQ-5) — user agent OR behaviour
-- Business logic (funnel stages) lives downstream in fct_sessions.
-- =============================================================================
CREATE OR REPLACE TABLE stg.stg_sessions AS
WITH s AS (
    SELECT
        session_id,
        any_value(visitor_id)                         AS visitor_id,
        max(user_id)                                  AS user_id_logged_in,
        min(event_ts)                                 AS session_start,
        max(event_ts)                                 AS session_end,
        coalesce(any_value(device_type), 'unknown')   AS device_type,
        any_value(browser)                            AS browser,
        -- session-level marketing parameters (constant within a session)
        any_value(utm_source)       AS utm_source,
        any_value(utm_medium)       AS utm_medium,
        any_value(utm_campaign)     AS utm_campaign,
        any_value(referrer_domain)  AS referrer_domain,
        count(*)                                        AS n_events,
        count(*) FILTER (WHERE event_name = 'page_view')      AS n_page_views,
        count(*) FILTER (WHERE event_name = 'product_view')   AS n_product_views,
        count(*) FILTER (WHERE event_name = 'add_to_cart')    AS n_add_to_cart,
        count(*) FILTER (WHERE event_name = 'begin_checkout') AS n_begin_checkout,
        count(*) FILTER (WHERE event_name = 'purchase')       AS n_purchase,
        max(order_id)                                   AS order_id
    FROM stg.stg_events
    GROUP BY session_id
)
SELECT
    s.*,
    date_diff('second', session_start, session_end)  AS duration_seconds,
    CASE
        -- 1. Paid search: search engines with a paid medium
        WHEN utm_source IN ('google', 'bing') AND utm_medium IN ('cpc', 'ppc')            THEN 'Paid Search'
        -- 2. Paid social: Meta sources. Checked BEFORE medium so 'facebook / cpc' is not Paid Search.
        --    Missing medium on a Meta source is still a paid click (UTM built by the ad platform).
        WHEN utm_source IN ('facebook', 'fb', 'instagram', 'ig')                          THEN 'Paid Social'
        -- 3. Email
        WHEN utm_medium IN ('email', 'e-mail') OR utm_source IN ('newsletter', 'klaviyo') THEN 'Email'
        -- 4. Affiliates
        WHEN utm_medium = 'affiliate'                                                      THEN 'Affiliate'
        -- 5. Tagged but unrecognised campaign: keep visible rather than hide in Direct
        WHEN utm_source IS NOT NULL                                                        THEN 'Other Campaign'
        -- 6-8. Untagged traffic: classify by referrer
        WHEN referrer_domain IN ('google.com', 'bing.com', 'duckduckgo.com', 'yahoo.com') THEN 'Organic Search'
        WHEN referrer_domain IN ('instagram.com', 'l.instagram.com', 'facebook.com', 'm.facebook.com',
                                 'youtube.com', 't.co', 'x.com')                           THEN 'Organic Social'
        WHEN referrer_domain IS NOT NULL                                                   THEN 'Referral'
        -- 9. No campaign, no referrer
        ELSE 'Direct'
    END AS channel,
    (
        browser = 'HeadlessChrome'
        OR (n_events >= 25 AND n_events / greatest(date_diff('second', session_start, session_end), 1) * 60 > 20)
    ) AS is_bot
FROM s;
