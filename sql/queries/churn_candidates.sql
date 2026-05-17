-- ============================================================
-- Churn Candidates Query
-- Definition: last purchase > 90 days ago AND frequency >= 2
-- :threshold parameter is replaced by the API at query time
-- ============================================================

WITH customer_activity AS (
    SELECT
        dc.customer_id,
        dc.country,
        COUNT(DISTINCT ft.invoice_no)                        AS frequency,
        ROUND(SUM(ft.quantity * ft.unit_price), 2)           AS total_revenue,
        MIN(DATE(ft.invoice_date))                           AS first_purchase_date,
        MAX(DATE(ft.invoice_date))                           AS last_purchase_date,
        CAST(
            JULIANDAY((SELECT DATE(MAX(invoice_date)) 
                       FROM fact_transactions WHERE is_return = 0))
            - JULIANDAY(MAX(DATE(ft.invoice_date)))
        AS INTEGER)                                          AS recency_days,
        ROUND(
            CAST(
                JULIANDAY(MAX(DATE(ft.invoice_date)))
                - JULIANDAY(MIN(DATE(ft.invoice_date)))
            AS REAL)
            / NULLIF(COUNT(DISTINCT ft.invoice_no) - 1, 0)
        , 1)                                                 AS avg_days_between_orders
    FROM fact_transactions ft
    JOIN dim_customer dc ON ft.customer_key = dc.customer_key
    WHERE ft.is_return = 0
      AND ft.unit_price > 0
      AND ft.quantity > 0
    GROUP BY dc.customer_id, dc.country
)

SELECT
    customer_id,
    country,
    frequency,
    total_revenue,
    first_purchase_date,
    last_purchase_date,
    recency_days,
    avg_days_between_orders,
    CASE
        WHEN recency_days > 180 THEN 'High'
        WHEN recency_days > 120 THEN 'Medium'
        ELSE 'Low'
    END AS churn_risk_tier
FROM customer_activity
WHERE recency_days > 90
  AND frequency >= 2
ORDER BY
    CASE churn_risk_tier 
        WHEN 'High' THEN 1 
        WHEN 'Medium' THEN 2 
        ELSE 3 
    END,
    total_revenue DESC;