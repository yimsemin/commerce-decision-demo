-- Raw layer: one table per generator CSV, schema matches
-- src/commerce_lab/datagen output exactly (no transformation at load time).
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `raw` must already exist -- see scripts/provision_gcp.sh)

CREATE TABLE IF NOT EXISTS raw.orders (
    order_id STRING NOT NULL,
    order_date DATE NOT NULL,
    brand STRING NOT NULL,
    channel STRING NOT NULL,
    sku_id STRING NOT NULL,
    customer_id STRING NOT NULL,
    is_new_customer BOOL NOT NULL,
    quantity INT64 NOT NULL,
    selling_price FLOAT64 NOT NULL,
    discount FLOAT64 NOT NULL,
    net_sales FLOAT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.marketing (
    date DATE NOT NULL,
    brand STRING NOT NULL,
    marketing_channel STRING NOT NULL,
    spend FLOAT64 NOT NULL,
    impressions INT64 NOT NULL,
    clicks INT64 NOT NULL,
    attributed_orders INT64 NOT NULL,
    attributed_revenue FLOAT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.inventory (
    date DATE NOT NULL,
    sku_id STRING NOT NULL,
    brand STRING NOT NULL,
    opening_stock INT64 NOT NULL,
    receipts INT64 NOT NULL,
    units_sold INT64 NOT NULL,
    closing_stock INT64 NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id STRING NOT NULL,
    acquisition_channel STRING NOT NULL,
    first_order_date DATE NOT NULL,
    total_orders INT64 NOT NULL,
    total_net_sales FLOAT64 NOT NULL,
    is_returning BOOL NOT NULL
);

CREATE TABLE IF NOT EXISTS raw.skus (
    sku_id STRING NOT NULL,
    brand STRING NOT NULL,
    base_price FLOAT64 NOT NULL,
    unit_cost FLOAT64 NOT NULL
);
