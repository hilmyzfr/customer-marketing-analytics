"""
ETL Stage 3 — Load
Inserts cleaned data into the star schema.
Order: dim_date → dim_customer → dim_product → fact_transactions
All inserts run inside a single transaction — if anything fails, 
everything rolls back.
"""
import logging
import sqlite3
from datetime import timedelta
from pathlib import Path
from typing import List

import pandas as pd

from src.etl.transform import QualityIssue

logger = logging.getLogger(__name__)


def load(
    conn: sqlite3.Connection,
    clean_df: pd.DataFrame,
    issues: List[QualityIssue],
    run_id: str,
) -> dict:
    stats = {
        "rows_extracted": len(clean_df) + len(issues),
        "rows_loaded": 0,
        "rows_rejected": len(issues),
    }

    with conn:
        _load_dim_date(conn, clean_df)
        _load_dim_customer(conn, clean_df)
        _load_dim_product(conn, clean_df)
        rows_loaded = _load_fact_transactions(conn, clean_df)
        _load_rfm_scores(conn)
        _log_quality_issues(conn, issues, run_id)

    stats["rows_loaded"] = rows_loaded
    logger.info("Load complete: %d rows inserted", rows_loaded)
    return stats


def _load_dim_date(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    min_date = df["InvoiceDate"].dt.date.min()
    max_date = df["InvoiceDate"].dt.date.max()

    rows = []
    current = min_date
    while current <= max_date:
        rows.append({
            "date_key": int(current.strftime("%Y%m%d")),
            "full_date": current.isoformat(),
            "year": current.year,
            "quarter": (current.month - 1) // 3 + 1,
            "month": current.month,
            "month_name": current.strftime("%B"),
            "week_of_year": current.isocalendar()[1],
            "day_of_month": current.day,
            "day_of_week": current.weekday(),
            "day_name": current.strftime("%A"),
            "is_weekend": int(current.weekday() >= 5),
        })
        current += timedelta(days=1)

    conn.executemany(
        """
        INSERT OR IGNORE INTO dim_date
            (date_key, full_date, year, quarter, month, month_name,
             week_of_year, day_of_month, day_of_week, day_name, is_weekend)
        VALUES
            (:date_key, :full_date, :year, :quarter, :month, :month_name,
             :week_of_year, :day_of_month, :day_of_week, :day_name, :is_weekend)
        """,
        rows,
    )
    logger.info("dim_date: %d rows inserted", len(rows))


def _load_dim_customer(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    customers = (
        df.groupby("CustomerID")
        .agg(
            country=("Country", "first"),
            first_seen_date=("InvoiceDate", "min"),
            last_seen_date=("InvoiceDate", "max"),
        )
        .reset_index()
    )
    customers["first_seen_date"] = customers["first_seen_date"].dt.date.astype(str)
    customers["last_seen_date"] = customers["last_seen_date"].dt.date.astype(str)

    rows = customers.rename(
        columns={"CustomerID": "customer_id"}
    ).to_dict("records")

    conn.executemany(
        """
        INSERT INTO dim_customer (customer_id, country, first_seen_date, last_seen_date)
        VALUES (:customer_id, :country, :first_seen_date, :last_seen_date)
        ON CONFLICT(customer_id) DO UPDATE SET
            last_seen_date = excluded.last_seen_date,
            updated_at = CURRENT_TIMESTAMP
        """,
        rows,
    )
    logger.info("dim_customer: %d rows upserted", len(rows))


def _load_dim_product(conn: sqlite3.Connection, df: pd.DataFrame) -> None:
    products = (
        df.drop_duplicates("StockCode")[["StockCode", "Description"]]
        .rename(columns={"StockCode": "stock_code", "Description": "description"})
    )

    conn.executemany(
        """
        INSERT INTO dim_product (stock_code, description)
        VALUES (:stock_code, :description)
        ON CONFLICT(stock_code) DO UPDATE SET
            description = COALESCE(excluded.description, dim_product.description)
        """,
        products.to_dict("records"),
    )
    logger.info("dim_product: %d rows upserted", len(products))


def _load_fact_transactions(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    customer_map = dict(
        conn.execute("SELECT customer_id, customer_key FROM dim_customer").fetchall()
    )
    product_map = dict(
        conn.execute("SELECT stock_code, product_key FROM dim_product").fetchall()
    )

    rows = []
    skipped = 0

    for _, row in df.iterrows():
        ckey = customer_map.get(row["CustomerID"])
        pkey = product_map.get(row["StockCode"])
        dkey = int(row["InvoiceDate"].strftime("%Y%m%d"))

        if ckey is None or pkey is None:
            skipped += 1
            continue

        rows.append({
            "invoice_no": row["InvoiceNo"],
            "customer_key": ckey,
            "product_key": pkey,
            "date_key": dkey,
            "invoice_date": row["InvoiceDate"].isoformat(),
            "quantity": int(row["Quantity"]),
            "unit_price": float(row["UnitPrice"]),
            "is_return": int(row["is_return"]),
        })

    conn.executemany(
        """
        INSERT INTO fact_transactions
            (invoice_no, customer_key, product_key, date_key,
             invoice_date, quantity, unit_price, is_return)
        VALUES
            (:invoice_no, :customer_key, :product_key, :date_key,
             :invoice_date, :quantity, :unit_price, :is_return)
        """,
        rows,
    )

    if skipped:
        logger.warning("fact_transactions: %d rows skipped", skipped)

    return len(rows)


def _log_quality_issues(
    conn: sqlite3.Connection,
    issues: List[QualityIssue],
    run_id: str,
) -> None:
    rows = [
        {
            "run_id": run_id,
            "source_row": i.source_row,
            "invoice_no": i.invoice_no,
            "customer_id": i.customer_id,
            "issue_type": i.issue_type,
            "issue_detail": i.issue_detail,
        }
        for i in issues
    ]
    conn.executemany(
        """
        INSERT INTO etl_quality_log
            (run_id, source_row, invoice_no, customer_id, issue_type, issue_detail)
        VALUES
            (:run_id, :source_row, :invoice_no, :customer_id, :issue_type, :issue_detail)
        """,
        rows,
    )
    logger.info("etl_quality_log: %d issues recorded", len(rows))



def _load_rfm_scores(conn: sqlite3.Connection) -> None:
    sql_path = Path(__file__).parents[2] / "sql" / "queries" / "rfm_scores.sql"
    rfm_sql = sql_path.read_text()

    conn.execute("DELETE FROM rfm_scores")
    conn.execute(
        f"INSERT INTO rfm_scores "
        f"(customer_key, customer_id, country, recency_days, frequency, monetary, "
        f"r_score, f_score, m_score, rfm_score, rfm_segment) "
        f"{rfm_sql}"
    )
    count = conn.execute("SELECT COUNT(*) FROM rfm_scores").fetchone()[0]
    logger.info("rfm_scores: %d rows materialised", count)

