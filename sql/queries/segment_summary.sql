-- ============================================================
-- Segment Summary Query
-- Aggregates customer counts and revenue by RFM segment
-- ============================================================

SELECT
    rfm_segment                                              AS segment,
    COUNT(*)                                                 AS customer_count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)      AS pct_of_customers,
    ROUND(SUM(monetary), 2)                                  AS total_revenue,
    ROUND(AVG(monetary), 2)                                  AS avg_revenue_per_customer,
    ROUND(AVG(frequency), 1)                                 AS avg_frequency,
    ROUND(AVG(recency_days), 0)                              AS avg_recency_days,
    ROUND(AVG(r_score), 2)                                   AS avg_r_score,
    ROUND(AVG(f_score), 2)                                   AS avg_f_score,
    ROUND(AVG(m_score), 2)                                   AS avg_m_score,
    MIN(monetary)                                            AS min_revenue,
    MAX(monetary)                                            AS max_revenue
FROM rfm_scores
GROUP BY rfm_segment
ORDER BY total_revenue DESC;