"""
ETL Stage 2 — Transform
Cleans the raw DataFrame and logs every data quality issue.

Checks performed:
  NULL_CUSTOMER_ID   : CustomerID is null → exclude
  NEGATIVE_QUANTITY  : Quantity < 0 (returns) → flag
  ZERO_UNIT_PRICE    : UnitPrice is 0 → exclude
  INVALID_STOCK_CODE : Non-product codes → exclude
  DUPLICATE_LINE_ITEM: Same row twice → deduplicate
"""
import logging
import re
from dataclasses import dataclass, field
from typing import List

import pandas as pd

logger = logging.getLogger(__name__)

NON_PRODUCT_CODES = re.compile(
    r"^(POST|DOT|M|BANK CHARGES|AMAZONFEE|CRUK|C2|S|D|m|AUTO)$",
    re.IGNORECASE,
)


@dataclass
class QualityIssue:
    source_row: int
    invoice_no: str
    customer_id: str
    issue_type: str
    issue_detail: str


@dataclass
class TransformResult:
    clean_df: pd.DataFrame
    issues: List[QualityIssue] = field(default_factory=list)


def transform(raw_df: pd.DataFrame) -> TransformResult:
    issues: List[QualityIssue] = []
    df = raw_df.copy()

    # 1. Parse numeric columns
    df["Quantity"] = pd.to_numeric(df["Quantity"], errors="coerce")
    df["UnitPrice"] = pd.to_numeric(df["UnitPrice"], errors="coerce")

    # 2. Parse dates
    df["InvoiceDate"] = pd.to_datetime(df["InvoiceDate"], errors="coerce")
    bad_dates = df["InvoiceDate"].isna()
    _log_issues(issues, df, bad_dates, "UNPARSEABLE_DATE", "InvoiceDate could not be parsed")
    df = df[~bad_dates].copy()

    # 3. Strip whitespace
    for col in ["InvoiceNo", "StockCode", "Description", "CustomerID", "Country"]:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", pd.NA)
        df[col] = df[col].replace("", pd.NA)  # add this line

    # 4. Null CustomerID
    null_cust = df["CustomerID"].isna()
    _log_issues(issues, df, null_cust, "NULL_CUSTOMER_ID", "CustomerID is null")
    df = df[~null_cust].copy()

    # 5. Zero UnitPrice
    zero_price = df["UnitPrice"].isna() | (df["UnitPrice"] == 0)
    _log_issues(issues, df, zero_price, "ZERO_UNIT_PRICE", "UnitPrice is zero or null")
    df = df[~zero_price].copy()

    # 6. Non-product stock codes
    non_product = df["StockCode"].str.match(NON_PRODUCT_CODES, na=False)
    _log_issues(issues, df, non_product, "INVALID_STOCK_CODE", "Non-product StockCode")
    df = df[~non_product].copy()

    # 7. Flag returns (keep in dataset, exclude from RFM later)
    df["is_return"] = (df["Quantity"] < 0).astype(int)
    returns = df["is_return"] == 1
    _log_issues(issues, df, returns, "NEGATIVE_QUANTITY", "Quantity < 0", exclude=False)

    # 8. Deduplicate
    dup_cols = ["InvoiceNo", "StockCode", "Quantity", "UnitPrice"]
    duplicates = df.duplicated(subset=dup_cols, keep="first")
    _log_issues(issues, df, duplicates, "DUPLICATE_LINE_ITEM", "Duplicate row")
    df = df[~duplicates].copy()

    # 9. Normalise CustomerID from "17850.0" to "17850"
    df["CustomerID"] = df["CustomerID"].apply(_normalise_customer_id)

    logger.info("Transform complete: %d clean rows, %d issues logged", len(df), len(issues))
    return TransformResult(clean_df=df.reset_index(drop=True), issues=issues)


def _log_issues(issues, df, mask, issue_type, detail, exclude=True):
    for idx, row in df[mask].iterrows():
        issues.append(QualityIssue(
            source_row=int(idx),
            invoice_no=str(row.get("InvoiceNo", "")),
            customer_id=str(row.get("CustomerID", "")),
            issue_type=issue_type,
            issue_detail=detail,
        ))
    if mask.sum() > 0:
        action = "Excluding" if exclude else "Flagging"
        logger.warning("%s %d rows: %s", action, mask.sum(), issue_type)


def _normalise_customer_id(val: str) -> str:
    try:
        return str(int(float(val)))
    except (ValueError, TypeError):
        return str(val)