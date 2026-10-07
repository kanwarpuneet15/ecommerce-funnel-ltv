-- =============================================================================
-- stg_products — Grain: one row per product.
-- =============================================================================
CREATE OR REPLACE TABLE stg.stg_products AS
SELECT
    product_id,
    product_name,
    category,
    department,
    list_price,
    unit_cost,
    round(1 - unit_cost / list_price, 4) AS list_margin_pct
FROM raw.products;

-- =============================================================================
-- stg_marketing_spend — Grain: date x platform x campaign_type.
--   DQ-13  one week of Meta rows exported in USD -> converted to INR (seeds.fx_rates)
-- =============================================================================
CREATE OR REPLACE TABLE stg.stg_marketing_spend AS
SELECT
    s.date,
    s.platform,
    m.channel,
    m.cost_type,
    s.campaign_type,
    s.currency                                   AS original_currency,
    round(s.spend * fx.inr_per_unit, 2)          AS spend_inr,
    s.impressions,
    s.clicks
FROM raw.marketing_spend s
JOIN seeds.channel_platform_map m USING (platform)
JOIN seeds.fx_rates fx
  ON fx.currency = s.currency AND s.date BETWEEN fx.valid_from AND fx.valid_to;
