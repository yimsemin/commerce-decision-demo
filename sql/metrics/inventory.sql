-- Inventory KPIs. Formulas and thresholds documented in docs/kpi_definitions.md.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.inventory must already exist)

CREATE OR REPLACE VIEW metrics.inventory_risk AS
WITH bounds AS (
  SELECT MAX(date) AS as_of FROM staging.inventory
),
on_hand AS (
  SELECT i.sku_id, i.brand, i.closing_stock AS on_hand
  FROM staging.inventory i
  CROSS JOIN bounds b
  WHERE i.date = b.as_of
),
velocity AS (
  SELECT i.sku_id, AVG(i.units_sold) AS velocity
  FROM staging.inventory i
  CROSS JOIN bounds b
  WHERE i.date BETWEEN DATE_SUB(b.as_of, INTERVAL 13 DAY) AND b.as_of
  GROUP BY i.sku_id
)
SELECT
  h.sku_id,
  h.brand,
  h.on_hand,
  COALESCE(v.velocity, 0) AS velocity,
  SAFE_DIVIDE(h.on_hand, v.velocity) AS days_of_cover,
  SAFE_DIVIDE(h.on_hand, v.velocity) IS NOT NULL AND SAFE_DIVIDE(h.on_hand, v.velocity) < 7 AS stockout_risk,
  h.on_hand > 0 AND (
    COALESCE(v.velocity, 0) = 0
    OR SAFE_DIVIDE(h.on_hand, v.velocity) > 60
  ) AS excess_risk
FROM on_hand h
LEFT JOIN velocity v USING (sku_id)
ORDER BY days_of_cover ASC;
