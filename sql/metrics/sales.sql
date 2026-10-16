-- Sales KPIs as parameterized table functions. Formulas documented in
-- docs/kpi_definitions.md. The refresh job calls these once per comparison
-- anchor: SELECT * FROM metrics.sales_summary(DATE '2026-09-21', 30).
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.orders must already exist)
--
-- Period convention (same as commerce_lab.metrics.periods): current = the
-- `window_days` days ending on `as_of`; previous = the `window_days` days
-- before that. Rounding mirrors the Python reference in
-- commerce_lab.metrics.sales so the two stay comparable.

DROP VIEW IF EXISTS metrics.sales_summary;
DROP VIEW IF EXISTS metrics.sales_by_brand_channel;
DROP VIEW IF EXISTS metrics.sales_by_sku;

-- One row: current_*/previous_*/pct_* for net revenue, orders, units, AOV.
CREATE OR REPLACE TABLE FUNCTION metrics.sales_summary(as_of DATE, window_days INT64) AS (
  WITH tagged AS (
    SELECT
      order_id, net_sales, quantity,
      CASE
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL window_days - 1 DAY) AND as_of THEN 'current'
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL 2 * window_days - 1 DAY)
                            AND DATE_SUB(as_of, INTERVAL window_days DAY) THEN 'previous'
      END AS period
    FROM staging.orders
  ),
  agg AS (
    SELECT
      ROUND(COALESCE(SUM(IF(period = 'current', net_sales, 0)), 0), 2) AS c_net_revenue,
      COUNT(DISTINCT IF(period = 'current', order_id, NULL)) AS c_orders,
      COALESCE(SUM(IF(period = 'current', quantity, 0)), 0) AS c_units_sold,
      ROUND(COALESCE(SUM(IF(period = 'previous', net_sales, 0)), 0), 2) AS p_net_revenue,
      COUNT(DISTINCT IF(period = 'previous', order_id, NULL)) AS p_orders,
      COALESCE(SUM(IF(period = 'previous', quantity, 0)), 0) AS p_units_sold
    FROM tagged
    WHERE period IS NOT NULL
  ),
  withaov AS (
    SELECT *,
      COALESCE(ROUND(SAFE_DIVIDE(c_net_revenue, c_orders), 2), 0.0) AS c_aov,
      COALESCE(ROUND(SAFE_DIVIDE(p_net_revenue, p_orders), 2), 0.0) AS p_aov
    FROM agg
  )
  SELECT
    c_net_revenue AS current_net_revenue, c_orders AS current_orders,
    c_units_sold AS current_units_sold, c_aov AS current_aov,
    p_net_revenue AS previous_net_revenue, p_orders AS previous_orders,
    p_units_sold AS previous_units_sold, p_aov AS previous_aov,
    ROUND(SAFE_DIVIDE(c_net_revenue - p_net_revenue, p_net_revenue) * 100, 1) AS pct_net_revenue,
    ROUND(SAFE_DIVIDE(c_orders - p_orders, p_orders) * 100, 1) AS pct_orders,
    ROUND(SAFE_DIVIDE(c_units_sold - p_units_sold, p_units_sold) * 100, 1) AS pct_units_sold,
    ROUND(SAFE_DIVIDE(c_aov - p_aov, p_aov) * 100, 1) AS pct_aov
  FROM withaov
);

-- Brand x channel contribution: current vs previous net revenue.
CREATE OR REPLACE TABLE FUNCTION metrics.sales_by_brand_channel(as_of DATE, window_days INT64) AS (
  WITH tagged AS (
    SELECT
      brand, channel, net_sales,
      CASE
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL window_days - 1 DAY) AND as_of THEN 'current'
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL 2 * window_days - 1 DAY)
                            AND DATE_SUB(as_of, INTERVAL window_days DAY) THEN 'previous'
      END AS period
    FROM staging.orders
  ),
  agg AS (
    SELECT
      brand, channel,
      SUM(IF(period = 'current', net_sales, 0)) AS current_net_revenue,
      SUM(IF(period = 'previous', net_sales, 0)) AS previous_net_revenue
    FROM tagged
    WHERE period IS NOT NULL
    GROUP BY brand, channel
  )
  SELECT
    brand, channel, current_net_revenue, previous_net_revenue,
    current_net_revenue - previous_net_revenue AS change,
    ROUND(SAFE_DIVIDE(current_net_revenue - previous_net_revenue, previous_net_revenue) * 100, 1) AS pct_change
  FROM agg
);

-- SKU-level contribution, same shape.
CREATE OR REPLACE TABLE FUNCTION metrics.sales_by_sku(as_of DATE, window_days INT64) AS (
  WITH tagged AS (
    SELECT
      sku_id, brand, net_sales,
      CASE
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL window_days - 1 DAY) AND as_of THEN 'current'
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL 2 * window_days - 1 DAY)
                            AND DATE_SUB(as_of, INTERVAL window_days DAY) THEN 'previous'
      END AS period
    FROM staging.orders
  ),
  agg AS (
    SELECT
      sku_id, brand,
      SUM(IF(period = 'current', net_sales, 0)) AS current_net_revenue,
      SUM(IF(period = 'previous', net_sales, 0)) AS previous_net_revenue
    FROM tagged
    WHERE period IS NOT NULL
    GROUP BY sku_id, brand
  )
  SELECT
    sku_id, brand, current_net_revenue, previous_net_revenue,
    current_net_revenue - previous_net_revenue AS change,
    ROUND(SAFE_DIVIDE(current_net_revenue - previous_net_revenue, previous_net_revenue) * 100, 1) AS pct_change
  FROM agg
);
