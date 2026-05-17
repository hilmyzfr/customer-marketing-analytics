"""
ETL Stage 1 — Extract
Reads the UCI Online Retail Excel file into a raw DataFrame.
"""
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

EXPECTED_COLUMNS = {
    "InvoiceNo", "StockCode", "Description",
    "Quantity", "InvoiceDate", "UnitPrice",
    "CustomerID", "Country",
}


class ExtractionError(Exception):
    """Raised when the source file is missing or structurally invalid."""


def extract(source_path: str) -> pd.DataFrame:
    path = Path(source_path)

    if not path.exists():
        raise ExtractionError(
            f"Source file not found: {path}\n"
            "Download from: https://archive.ics.uci.edu/ml/datasets/online+retail\n"
            "Place as: data/raw/OnlineRetail.xlsx"
        )

    logger.info("Extracting from %s", path)

    try:
        df = pd.read_excel(path, dtype=str, engine="openpyxl")
    except Exception as exc:
        raise ExtractionError(f"Failed to read {path}: {exc}") from exc

    missing_cols = EXPECTED_COLUMNS - set(df.columns)
    if missing_cols:
        raise ExtractionError(
            f"Source file missing required columns: {missing_cols}"
        )

    logger.info("Extracted %d rows", len(df))
    return df