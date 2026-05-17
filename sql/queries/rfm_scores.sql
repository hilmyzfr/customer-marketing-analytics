-- ============================================================
-- RFM Scores Query
-- Snapshot date = MAX(invoice_date) in fact_transactions
-- NTILE(5): 5 = best, 1 = worst
-- ============================================================

WITH snapshot_date AS (
    SELECT DATE(MAX(invoice_date)) AS max_date
    FROM fact_transactions
    WHERE is_return = 0
),

customer_rfm_raw AS (
    SELECT
        ft.customer_key,
        dc.customer_id,
        dc.country,
        CAST(
            JULIANDAY((SELECT max_date FROM snapshot_date))
            - JULIANDAY(MAX(DATE(ft.invoice_date)))
        AS INTEGER)                              AS recency_days,
        COUNT(DISTINCT ft.invoice_no)            AS frequency,
        ROUND(SUM(ft.quantity * ft.unit_price), 2) AS monetary
    FROM fact_transactions ft
    JOIN dim_customer dc ON ft.customer_key = dc.customer_key
    WHERE ft.is_return = 0
      AND ft.unit_price > 0
      AND ft.quantity > 0
    GROUP BY ft.customer_key, dc.customer_id, dc.country
),

rfm_ntile AS (
    SELECT
        customer_key,
        customer_id,
        country,
        recency_days,
        frequency,
        monetary,
        6 - NTILE(5) OVER (ORDER BY recency_days ASC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC)          AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC)           AS m_score
    FROM customer_rfm_raw
),

rfm_labelled AS (
    SELECT
        customer_key,
        customer_id,
        country,
        recency_days,
        frequency,
        monetary,
        r_score,
        f_score,
        m_score,
        CAST(r_score AS TEXT) 
            || CAST(f_score AS TEXT) 
            || CAST(m_score AS TEXT) AS rfm_score,
        CASE
            WHEN r_score >= 4 AND f_score >= 4 THEN 'Champions'
            WHEN r_score >= 3 AND f_score >= 3 THEN 'Loyal Customers'
            WHEN r_score >= 4 AND f_score <= 2 THEN 'Recent Customers'
            WHEN r_score >= 3 AND f_score = 1  THEN 'Promising'
            WHEN r_score = 3  AND f_score >= 3 THEN 'Need Attention'
            WHEN r_score <= 2 AND f_score >= 3 THEN 'At Risk'
            WHEN r_score <= 2 AND f_score >= 4 
             AND m_score >= 4                  THEN 'Cannot Lose Them'
            WHEN r_score = 2  AND f_score = 2  THEN 'Hibernating'
            WHEN r_score <= 1                  THEN 'Lost'
            ELSE 'About to Sleep'
        END AS rfm_segment
    FROM rfm_ntile
)

SELECT * FROM rfm_labelled
ORDER BY r_score DESC, f_score DESC, m_score DESC;