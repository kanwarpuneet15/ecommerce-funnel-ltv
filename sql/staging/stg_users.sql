-- =============================================================================
-- stg_users
-- Grain: one row per registered user.
--   DQ-8  internal QA accounts (company email domain) flagged, excluded downstream
-- =============================================================================
CREATE OR REPLACE TABLE stg.stg_users AS
SELECT
    u.user_id,
    u.created_at                                   AS signup_ts,
    lower(u.email_domain)                          AS email_domain,
    u.gender,
    u.birth_year,
    year(snapshot_date()) - u.birth_year           AS age_at_snapshot,
    CASE
        WHEN year(snapshot_date()) - u.birth_year < 25 THEN '18-24'
        WHEN year(snapshot_date()) - u.birth_year < 35 THEN '25-34'
        WHEN year(snapshot_date()) - u.birth_year < 45 THEN '35-44'
        ELSE '45+'
    END                                            AS age_band,
    u.city,
    u.state,
    coalesce(t.city_tier, 'Unknown')               AS city_tier,
    lower(u.email_domain) = 'threadline.in'        AS is_internal
FROM raw.users u
LEFT JOIN seeds.city_tiers t USING (city);
