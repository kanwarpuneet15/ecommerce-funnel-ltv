-- =============================================================================
-- SEEDS: small, hand-maintained reference tables (business knowledge, not source data)
-- plus project-wide constants.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS seeds;

CREATE OR REPLACE TABLE seeds.sale_calendar AS
SELECT * FROM read_csv('data/seeds/sale_calendar.csv', header = true,
    columns = {'sale_name': 'VARCHAR', 'start_date': 'DATE', 'end_date': 'DATE', 'sale_type': 'VARCHAR'});

CREATE OR REPLACE TABLE seeds.city_tiers AS
SELECT * FROM read_csv('data/seeds/city_tiers.csv', header = true,
    columns = {'city': 'VARCHAR', 'city_tier': 'VARCHAR'});

CREATE OR REPLACE TABLE seeds.fx_rates AS
SELECT * FROM read_csv('data/seeds/fx_rates.csv', header = true,
    columns = {'currency': 'VARCHAR', 'valid_from': 'DATE', 'valid_to': 'DATE', 'inr_per_unit': 'DOUBLE', 'note': 'VARCHAR'});

CREATE OR REPLACE TABLE seeds.channel_platform_map AS
SELECT * FROM read_csv('data/seeds/channel_platform_map.csv', header = true,
    columns = {'platform': 'VARCHAR', 'channel': 'VARCHAR', 'cost_type': 'VARCHAR'});

-- Project constants -----------------------------------------------------------
-- Snapshot = the moment the data was extracted. Everything after it is unknown.
CREATE OR REPLACE MACRO snapshot_ts() AS TIMESTAMP '2026-09-30 23:59:59';
CREATE OR REPLACE MACRO snapshot_date() AS DATE '2026-09-30';
-- Last fully observed calendar month (used to exclude partial months from trends)
CREATE OR REPLACE MACRO last_complete_month() AS DATE '2026-09-01';
-- Returns arrive up to ~4 weeks after delivery; LTV windows must wait for them to mature
CREATE OR REPLACE MACRO return_maturity_days() AS 30;
