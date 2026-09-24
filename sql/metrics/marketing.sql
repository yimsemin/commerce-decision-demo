-- Marketing KPIs. Formulas documented in docs/kpi_definitions.md.
-- Run via: bq query --use_legacy_sql=false --project_id=$GCP_PROJECT_ID < this file
-- (dataset `metrics` and staging.marketing/staging.customers must already exist)

CREATE OR REPLACE VIEW metrics.marketing_by_segment AS
WITH bounds AS (
  SELECT MAX(date) AS as_of FROM staging.marketing
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
    m.*,
    CASE
      WHEN m.date BETWEEN p.current_start AND p.as_of THEN 'current'
      WHEN m.date BETWEEN p.previous_start AND p.previous_end THEN 'previous'
    END AS period
  FROM staging.marketing m
  CROSS JOIN periods p
)
SELECT
  brand,
  marketing_channel,
  SUM(IF(period = 'current', spend, 0)) AS current_spend,
  SUM(IF(period = 'current', attributed_revenue, 0)) AS current_attributed_revenue,
  SAFE_DIVIDE(SUM(IF(period = 'current', attributed_revenue, 0)), SUM(IF(period = 'current', spend, 0))) AS current_roas,
  SUM(IF(period = 'previous', spend, 0)) AS previous_spend,
  SUM(IF(period = 'previous', attributed_revenue, 0)) AS previous_attributed_revenue,
  SAFE_DIVIDE(SUM(IF(period = 'previous', attributed_revenue, 0)), SUM(IF(period = 'previous', spend, 0))) AS previous_roas
FROM tagged
WHERE period IS NOT NULL
GROUP BY brand, marketing_channel
ORDER BY (SAFE_DIVIDE(SUM(IF(period = 'current', attributed_revenue, 0)), SUM(IF(period = 'current', spend, 0)))
          - SAFE_DIVIDE(SUM(IF(period = 'previous', attributed_revenue, 0)), SUM(IF(period = 'previous', spend, 0)))) ASC;

-- CAC per marketing channel: spend(channel) / new customers acquired via
-- that channel in the current period. Channel grain only -- see
-- docs/kpi_definitions.md for why brand x channel CAC is not defensible
-- from this synthetic model.
CREATE OR REPLACE VIEW metrics.cac_by_channel AS
WITH bounds AS (
  SELECT MAX(date) AS as_of FROM staging.marketing
),
periods AS (
  SELECT as_of, DATE_SUB(as_of, INTERVAL 29 DAY) AS current_start FROM bounds
),
current_spend AS (
  SELECT m.marketing_channel, SUM(m.spend) AS spend
  FROM staging.marketing m
  CROSS JOIN periods p
  WHERE m.date BETWEEN p.current_start AND p.as_of
  GROUP BY m.marketing_channel
),
new_customers AS (
  SELECT c.acquisition_channel AS marketing_channel, COUNT(*) AS new_customers
  FROM staging.customers c
  CROSS JOIN periods p
  WHERE c.first_order_date BETWEEN p.current_start AND p.as_of
  GROUP BY c.acquisition_channel
)
SELECT
  s.marketing_channel,
  s.spend,
  COALESCE(n.new_customers, 0) AS new_customers,
  SAFE_DIVIDE(s.spend, n.new_customers) AS cac
FROM current_spend s
LEFT JOIN new_customers n USING (marketing_channel);
