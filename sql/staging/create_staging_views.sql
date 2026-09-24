-- Staging layer: thin, typed/cleaned views over `raw`.
-- Downstream metrics SQL (sql/metrics/, M3) reads from `staging`, never
-- from `raw`, so raw ingestion quirks stay isolated to one layer.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `staging` and the raw.* tables must already exist)

CREATE OR REPLACE VIEW staging.orders AS
SELECT
    order_id,
    order_date,
    TRIM(brand) AS brand,
    TRIM(channel) AS channel,
    sku_id,
    customer_id,
    is_new_customer,
    quantity,
    selling_price,
    discount,
    net_sales
FROM raw.orders
QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_date) = 1;

CREATE OR REPLACE VIEW staging.marketing AS
SELECT
    date,
    TRIM(brand) AS brand,
    TRIM(marketing_channel) AS marketing_channel,
    spend,
    impressions,
    clicks,
    attributed_orders,
    attributed_revenue,
    SAFE_DIVIDE(attributed_revenue, spend) AS roas
FROM raw.marketing;

CREATE OR REPLACE VIEW staging.inventory AS
SELECT
    date,
    sku_id,
    TRIM(brand) AS brand,
    opening_stock,
    receipts,
    units_sold,
    closing_stock
FROM raw.inventory;

CREATE OR REPLACE VIEW staging.customers AS
SELECT
    customer_id,
    TRIM(acquisition_channel) AS acquisition_channel,
    first_order_date,
    total_orders,
    total_net_sales,
    is_returning
FROM raw.customers
QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY first_order_date) = 1;

CREATE OR REPLACE VIEW staging.skus AS
SELECT
    sku_id,
    TRIM(brand) AS brand,
    base_price,
    unit_cost
FROM raw.skus
QUALIFY ROW_NUMBER() OVER (PARTITION BY sku_id ORDER BY sku_id) = 1;
