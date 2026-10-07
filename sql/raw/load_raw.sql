-- =============================================================================
-- RAW LAYER: load source files exactly as received.
-- Principle: no cleaning here. Timestamps stay as text where the source format
-- is ambiguous (events are UTC strings with a 'Z'; orders are local IST time),
-- so every transformation is explicit and auditable in the staging layer.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS raw;

CREATE OR REPLACE TABLE raw.events AS
SELECT * FROM read_csv('data/raw/events.csv.gz', header = true, columns = {
    'event_id': 'VARCHAR', 'event_ts_utc': 'VARCHAR', 'event_name': 'VARCHAR',
    'session_id': 'VARCHAR', 'visitor_id': 'VARCHAR', 'user_id': 'BIGINT',
    'device_type': 'VARCHAR', 'browser': 'VARCHAR', 'utm_source': 'VARCHAR',
    'utm_medium': 'VARCHAR', 'utm_campaign': 'VARCHAR', 'referrer_domain': 'VARCHAR',
    'page_path': 'VARCHAR', 'product_id': 'BIGINT', 'order_id': 'BIGINT'});

CREATE OR REPLACE TABLE raw.orders AS
SELECT * FROM read_csv('data/raw/orders.csv', header = true, columns = {
    'order_id': 'BIGINT', 'user_id': 'BIGINT', 'created_at': 'TIMESTAMP', 'status': 'VARCHAR',
    'payment_method': 'VARCHAR', 'discount_code': 'VARCHAR', 'shipping_fee': 'DECIMAL(10,2)',
    'order_total': 'DECIMAL(12,2)', 'shipped_at': 'TIMESTAMP', 'delivered_at': 'TIMESTAMP',
    'rto_at': 'TIMESTAMP', 'cancelled_at': 'TIMESTAMP'});

CREATE OR REPLACE TABLE raw.order_items AS
SELECT * FROM read_csv('data/raw/order_items.csv', header = true, columns = {
    'order_item_id': 'BIGINT', 'order_id': 'BIGINT', 'product_id': 'BIGINT', 'quantity': 'INTEGER',
    'unit_price': 'DECIMAL(10,2)', 'discount_amount': 'DECIMAL(10,2)', 'returned_at': 'TIMESTAMP'});

CREATE OR REPLACE TABLE raw.users AS
SELECT * FROM read_csv('data/raw/users.csv', header = true, columns = {
    'user_id': 'BIGINT', 'created_at': 'TIMESTAMP', 'email_domain': 'VARCHAR', 'gender': 'VARCHAR',
    'birth_year': 'INTEGER', 'city': 'VARCHAR', 'state': 'VARCHAR'});

CREATE OR REPLACE TABLE raw.products AS
SELECT * FROM read_csv('data/raw/products.csv', header = true, columns = {
    'product_id': 'BIGINT', 'product_name': 'VARCHAR', 'category': 'VARCHAR', 'department': 'VARCHAR',
    'list_price': 'DECIMAL(10,2)', 'unit_cost': 'DECIMAL(10,2)'});

CREATE OR REPLACE TABLE raw.marketing_spend AS
SELECT * FROM read_csv('data/raw/marketing_spend.csv', header = true, columns = {
    'date': 'DATE', 'platform': 'VARCHAR', 'campaign_type': 'VARCHAR', 'spend': 'DECIMAL(12,2)',
    'impressions': 'BIGINT', 'clicks': 'BIGINT', 'currency': 'VARCHAR'});
