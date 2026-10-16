-- Marketing KPIs as parameterized table functions. Formulas documented in
-- docs/kpi_definitions.md. Period convention: see sql/metrics/sales.sql.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.marketing/staging.customers must already exist)

DROP VIEW IF EXISTS metrics.marketing_by_segment;
DROP VIEW IF EXISTS metrics.cac_by_channel;

CREATE OR REPLACE TABLE FUNCTION metrics.marketing_by_segment(as_of DATE, window_days INT64) AS (
  WITH tagged AS (
    SELECT
      brand, marketing_channel, spend, attributed_revenue,
      CASE
        WHEN date BETWEEN DATE_SUB(as_of, INTERVAL window_days - 1 DAY) AND as_of THEN 'current'
        WHEN date BETWEEN DATE_SUB(as_of, INTERVAL 2 * window_days - 1 DAY)
                      AND DATE_SUB(as_of, INTERVAL window_days DAY) THEN 'previous'
      END AS period
    FROM staging.marketing
  ),
  agg AS (
    SELECT
      brand, marketing_channel,
      SUM(IF(period = 'current', spend, 0)) AS current_spend,
      SUM(IF(period = 'current', attributed_revenue, 0)) AS current_attributed_revenue,
      SUM(IF(period = 'previous', spend, 0)) AS previous_spend,
      SUM(IF(period = 'previous', attributed_revenue, 0)) AS previous_attributed_revenue
    FROM tagged
    WHERE period IS NOT NULL
    GROUP BY brand, marketing_channel
  ),
  roas AS (
    SELECT *,
      COALESCE(SAFE_DIVIDE(current_attributed_revenue, current_spend), 0.0) AS current_roas,
      COALESCE(SAFE_DIVIDE(previous_attributed_revenue, previous_spend), 0.0) AS previous_roas
    FROM agg
  )
  SELECT
    brand, marketing_channel,
    current_spend, current_attributed_revenue, current_roas,
    previous_spend, previous_attributed_revenue, previous_roas,
    ROUND(SAFE_DIVIDE(current_roas - previous_roas, previous_roas) * 100, 1) AS roas_change_pct
  FROM roas
);

-- CAC per marketing channel: spend(channel) / new customers acquired via
-- that channel in the current period. Channel grain only -- see
-- docs/kpi_definitions.md for why brand x channel CAC is not defensible
-- from this synthetic model.
CREATE OR REPLACE TABLE FUNCTION metrics.cac_by_channel(as_of DATE, window_days INT64) AS (
  WITH spend AS (
    SELECT marketing_channel, SUM(spend) AS spend
    FROM staging.marketing
    WHERE date BETWEEN DATE_SUB(as_of, INTERVAL window_days - 1 DAY) AND as_of
    GROUP BY marketing_channel
  ),
  acquired AS (
    SELECT acquisition_channel AS marketing_channel, COUNT(*) AS new_customers
    FROM staging.customers
    WHERE first_order_date BETWEEN DATE_SUB(as_of, INTERVAL window_days - 1 DAY) AND as_of
    GROUP BY acquisition_channel
  ),
  joined AS (
    SELECT
      COALESCE(s.marketing_channel, a.marketing_channel) AS marketing_channel,
      COALESCE(s.spend, 0.0) AS spend,
      COALESCE(a.new_customers, 0) AS new_customers
    FROM spend s
    FULL OUTER JOIN acquired a ON s.marketing_channel = a.marketing_channel
  )
  SELECT
    marketing_channel, spend, new_customers,
    ROUND(SAFE_DIVIDE(spend, new_customers), 2) AS cac
  FROM joined
);
