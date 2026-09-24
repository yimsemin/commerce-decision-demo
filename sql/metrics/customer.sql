-- Customer KPIs. Formulas documented in docs/kpi_definitions.md.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.orders/staging.customers must already exist)

CREATE OR REPLACE VIEW metrics.customer_mix AS
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
  AVG(CAST(is_new_customer AS INT64)) AS new_customer_share,
  1 - AVG(CAST(is_new_customer AS INT64)) AS returning_customer_share
FROM tagged
WHERE period IS NOT NULL
GROUP BY period;

-- Lifetime repeat purchase rate, as of the latest data (not period-scoped).
CREATE OR REPLACE VIEW metrics.repeat_purchase_rate AS
SELECT AVG(CAST(is_returning AS INT64)) AS repeat_purchase_rate
FROM staging.customers;
