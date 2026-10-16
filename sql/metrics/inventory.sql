-- Inventory KPIs. Formulas and thresholds documented in docs/kpi_definitions.md.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.inventory must already exist)

DROP VIEW IF EXISTS metrics.inventory_risk;

-- Per-SKU stock position on `as_of`: on-hand, trailing sales velocity,
-- days of cover and the stock-out / excess flags under the given
-- thresholds. Rounding mirrors commerce_lab.metrics.inventory.
CREATE OR REPLACE TABLE FUNCTION metrics.inventory_risk(
  as_of DATE, velocity_window_days INT64, stockout_days FLOAT64, excess_days FLOAT64
) AS (
  WITH on_hand AS (
    SELECT sku_id, brand, closing_stock AS on_hand
    FROM staging.inventory
    WHERE date = as_of
  ),
  velocity AS (
    SELECT sku_id, ROUND(AVG(units_sold), 2) AS velocity
    FROM staging.inventory
    WHERE date BETWEEN DATE_SUB(as_of, INTERVAL velocity_window_days - 1 DAY) AND as_of
    GROUP BY sku_id
  ),
  joined AS (
    SELECT h.sku_id, h.brand, h.on_hand, COALESCE(v.velocity, 0.0) AS velocity
    FROM on_hand h
    LEFT JOIN velocity v USING (sku_id)
  ),
  cover AS (
    SELECT *, IF(velocity > 0, ROUND(on_hand / velocity, 1), NULL) AS days_of_cover
    FROM joined
  )
  SELECT
    sku_id, brand, on_hand, velocity, days_of_cover,
    days_of_cover IS NOT NULL AND days_of_cover < stockout_days AS stockout_risk,
    on_hand > 0 AND (velocity = 0 OR (days_of_cover IS NOT NULL AND days_of_cover > excess_days)) AS excess_risk
  FROM cover
);
