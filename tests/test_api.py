"""
Tests for API endpoints.
Requires database to exist — run python run_pipeline.py first.
Run with: pytest tests/ -v
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path

DB_PATH = Path("data/analytics.db")

pytestmark = pytest.mark.skipif(
    not DB_PATH.exists(),
    reason="Database not found. Run: python run_pipeline.py"
)


@pytest.fixture(scope="module")
def client():
    from src.api.main import app
    return TestClient(app)


def test_root(client):
    r = client.get("/")
    assert r.status_code == 200


def test_list_customers(client):
    r = client.get("/customers?page=1&page_size=10")
    assert r.status_code == 200
    data = r.json()
    assert data["total"] > 0
    assert len(data["items"]) <= 10


def test_list_customers_country_filter(client):
    r = client.get("/customers?country=Finland")
    assert r.status_code == 200
    for item in r.json()["items"]:
        assert item["country"] == "Finland"


def test_get_customer_exists(client):
    r = client.get("/customers/17850")
    assert r.status_code == 200
    data = r.json()
    assert data["customer_id"] == "17850"
    assert data["rfm"] is not None
    assert 1 <= data["rfm"]["r_score"] <= 5


def test_get_customer_not_found(client):
    r = client.get("/customers/DOESNOTEXIST")
    assert r.status_code == 404


def test_rfm_scores(client):
    r = client.get("/rfm/scores?limit=10")
    assert r.status_code == 200
    for s in r.json():
        assert 1 <= s["r_score"] <= 5
        assert 1 <= s["f_score"] <= 5
        assert 1 <= s["m_score"] <= 5


def test_rfm_scores_segment_filter(client):
    r = client.get("/rfm/scores?segment=Champions")
    assert r.status_code == 200
    for s in r.json():
        assert s["rfm_segment"] == "Champions"


def test_rfm_distribution(client):
    r = client.get("/rfm/distribution")
    assert r.status_code == 200
    assert len(r.json()) > 0
    for d in r.json():
        assert len(d["score_bin"]) == 3


def test_segment_summary(client):
    r = client.get("/segments/summary")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_segment_customers(client):
    r = client.get("/segments/Champions")
    assert r.status_code == 200
    assert len(r.json()) > 0


def test_segment_not_found(client):
    r = client.get("/segments/FAKESEGMENT")
    assert r.status_code == 404


def test_churn_candidates(client):
    r = client.get("/segments/churn/candidates?threshold_days=90")
    assert r.status_code == 200
    for c in r.json():
        assert c["recency_days"] > 90
        assert c["frequency"] >= 2


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "SUCCESS"
    assert r.json()["rows_loaded"] > 0