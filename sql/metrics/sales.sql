-- Sales KPIs. Formulas documented in docs/kpi_definitions.md.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.orders must already exist)

CREATE OR REPLACE VIEW metrics.sales_summary AS
WITH bounds AS (
  SELECT MAX(order_date) AS as_of FROM staging.orders
),
periods AS (
  SELECT
    as_of,
    DATE_SUB(as_of, INTERVAL 29 DAY) AS current_start,
    DATE_SUB(as_of, INTERVAL 30 DAY) AS previous_end,
    DATE_SUB(as_of, INTERVAL 59 DAY) AS previous_start
  FROM bounds
),
tagged AS (
  SELECT
    o.*,
    CASE
      WHEN o.order_date BETWEEN p.current_start AND p.as_of THEN 'current'
      WHEN o.order_date BETWEEN p.previous_start AND p.previous_end THEN 'previous'
    END AS period
  FROM staging.orders o
  CROSS JOIN periods p
)
SELECT
  period,
  COUNT(DISTINCT order_id) AS orders,
  SUM(net_sales) AS net_revenue,
  SUM(quantity) AS units_sold,
  SAFE_DIVIDE(SUM(net_sales), COUNT(DISTINCT order_id)) AS aov
FROM tagged
WHERE period IS NOT NULL
GROUP BY period;

-- Brand/channel contribution: current vs previous net revenue.
CREATE OR REPLACE VIEW metrics.sales_by_brand_channel AS
WITH bounds AS (
  SELECT MAX(order_date) AS as_of FROM staging.orders
),
periods AS (
  SELECT
    as_of,
    DATE_SUB(as_of, INTERVAL 29 DAY) AS current_start,
    DATE_SUB(as_of, INTERVAL 30 DAY) AS previous_end,
    DATE_SUB(as_of, INTERVAL 59 DAY) AS previous_start
  FROM bounds
),
tagged AS (
  SELECT
    o.*,
    CASE
      WHEN o.order_date BETWEEN p.current_start AND p.as_of THEN 'current'
      WHEN o.order_date BETWEEN p.previous_start AND p.previous_end THEN 'previous'
    END AS period
  FROM staging.orders o
  CROSS JOIN periods p
)
SELECT
  brand,
  channel,
  SUM(IF(period = 'current', net_sales, 0)) AS current_net_revenue,
  SUM(IF(period = 'previous', net_sales, 0)) AS previous_net_revenue,
  SUM(IF(period = 'current', net_sales, 0)) - SUM(IF(period = 'previous', net_sales, 0)) AS change,
  SAFE_DIVIDE(
    SUM(IF(period = 'current', net_sales, 0)) - SUM(IF(period = 'previous', net_sales, 0)),
    SUM(IF(period = 'previous', net_sales, 0))
  ) * 100 AS pct_change
FROM tagged
WHERE period IS NOT NULL
GROUP BY brand, channel
ORDER BY ABS(change) DESC;

-- SKU-level contribution, same shape as brand/channel above.
CREATE OR REPLACE VIEW metrics.sales_by_sku AS
WITH bounds AS (
  SELECT MAX(order_date) AS as_of FROM staging.orders
),
periods AS (
  SELECT
    as_of,
    DATE_SUB(as_of, INTERVAL 29 DAY) AS current_start,
    DATE_SUB(as_of, INTERVAL 30 DAY) AS previous_end,
    DATE_SUB(as_of, INTERVAL 59 DAY) AS previous_start
  FROM bounds
),
tagged AS (
  SELECT
    o.*,
    CASE
      WHEN o.order_date BETWEEN p.current_start AND p.as_of THEN 'current'
      WHEN o.order_date BETWEEN p.previous_start AND p.previous_end THEN 'previous'
    END AS period
  FROM staging.orders o
  CROSS JOIN periods p
)
SELECT
  sku_id,
  brand,
  SUM(IF(period = 'current', net_sales, 0)) AS current_net_revenue,
  SUM(IF(period = 'previous', net_sales, 0)) AS previous_net_revenue,
  SUM(IF(period = 'current', net_sales, 0)) - SUM(IF(period = 'previous', net_sales, 0)) AS change
FROM tagged
WHERE period IS NOT NULL
GROUP BY sku_id, brand
ORDER BY ABS(change) DESC;
