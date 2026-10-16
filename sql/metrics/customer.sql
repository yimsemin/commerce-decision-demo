-- Customer KPIs. Formulas documented in docs/kpi_definitions.md.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.orders/staging.customers must already exist)

DROP VIEW IF EXISTS metrics.customer_mix;

-- One row: new-customer share of orders, current vs previous period.
CREATE OR REPLACE TABLE FUNCTION metrics.customer_mix(as_of DATE, window_days INT64) AS (
  WITH tagged AS (
    SELECT
      is_new_customer,
      CASE
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL window_days - 1 DAY) AND as_of THEN 'current'
        WHEN order_date BETWEEN DATE_SUB(as_of, INTERVAL 2 * window_days - 1 DAY)
                            AND DATE_SUB(as_of, INTERVAL window_days DAY) THEN 'previous'
      END AS period
    FROM staging.orders
  ),
  shares AS (
    SELECT
      ROUND(AVG(IF(period = 'current', CAST(is_new_customer AS INT64), NULL)), 3) AS current_new_share,
      ROUND(AVG(IF(period = 'previous', CAST(is_new_customer AS INT64), NULL)), 3) AS previous_new_share
    FROM tagged
    WHERE period IS NOT NULL
  )
  SELECT
    current_new_share, previous_new_share,
    ROUND(1 - current_new_share, 3) AS current_returning_share,
    ROUND(1 - previous_new_share, 3) AS previous_returning_share
  FROM shares
);

-- Lifetime repeat purchase rate over all customers (not period-scoped).
CREATE OR REPLACE VIEW metrics.repeat_purchase_rate AS
SELECT ROUND(AVG(CAST(is_returning AS INT64)), 3) AS repeat_purchase_rate
FROM staging.customers;
