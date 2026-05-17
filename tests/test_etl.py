"""
Tests for ETL transform stage.
Run with: pytest tests/ -v
"""
import pandas as pd
import pytest

from src.etl.transform import transform


def make_df(rows):
    return pd.DataFrame(rows)


VALID_ROW = {
    "InvoiceNo": "536365",
    "StockCode": "85123A",
    "Description": "WHITE HANGING HEART T-LIGHT HOLDER",
    "Quantity": "6",
    "InvoiceDate": "2010-12-01 08:26:00",
    "UnitPrice": "2.55",
    "CustomerID": "17850.0",
    "Country": "United Kingdom",
}


def test_clean_row_passes_through():
    result = transform(make_df([VALID_ROW]))
    assert len(result.clean_df) == 1
    assert len(result.issues) == 0


def test_null_customer_id_excluded():
    row = {**VALID_ROW, "CustomerID": ""}
    result = transform(make_df([VALID_ROW, row]))
    assert len(result.clean_df) == 1
    assert any(i.issue_type == "NULL_CUSTOMER_ID" for i in result.issues)


def test_zero_price_excluded():
    row = {**VALID_ROW, "UnitPrice": "0"}
    result = transform(make_df([VALID_ROW, row]))
    assert len(result.clean_df) == 1
    assert any(i.issue_type == "ZERO_UNIT_PRICE" for i in result.issues)


def test_non_product_code_excluded():
    row = {**VALID_ROW, "StockCode": "POST"}
    result = transform(make_df([VALID_ROW, row]))
    assert len(result.clean_df) == 1
    assert any(i.issue_type == "INVALID_STOCK_CODE" for i in result.issues)


def test_negative_quantity_flagged_not_excluded():
    row = {**VALID_ROW, "InvoiceNo": "C536365", "Quantity": "-3"}
    result = transform(make_df([VALID_ROW, row]))
    assert len(result.clean_df) == 2
    assert result.clean_df["is_return"].sum() == 1
    assert any(i.issue_type == "NEGATIVE_QUANTITY" for i in result.issues)


def test_duplicate_excluded():
    result = transform(make_df([VALID_ROW, VALID_ROW]))
    assert len(result.clean_df) == 1
    assert any(i.issue_type == "DUPLICATE_LINE_ITEM" for i in result.issues)


def test_customer_id_normalised():
    result = transform(make_df([VALID_ROW]))
    assert result.clean_df["CustomerID"].iloc[0] == "17850"
    assert "17850.0" not in result.clean_df["CustomerID"].values