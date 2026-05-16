# Customer Marketing Analytics Platform

A Data Engineering project built on the UCI Online Retail Dataset.
Implements a full ETL pipeline, Star Schema data model, RFM analysis, churn
identification, and customer segmentation served via a FastAPI backend.

---

## Tech Stack

| Layer | Tool | Reason |
|---|---|---|
| Language | Python | ETL, analytics, and API in one ecosystem |
| Database | SQLite | Zero-config, file-based, portable |
| API | FastAPI | Auto-docs, request validation, async support |
| Data Model | Star Schema (SQL) | Optimized for analytical GROUP BY queries |
| Version Control | Git | Standard, GitHub-ready |

---

## Architecture Decision Log (ADL)

---

### ADL-001 — SQLite over PostgreSQL
No server, no setup. Just a `.db` file in the project folder. Fine for 540K
rows locally. The SQL is standard, so switching to PostgreSQL later means
changing one connection string.

Limitation: no concurrent writes.

---

### ADL-002 — Star Schema
One fact table, three dimension tables. RFM and segmentation queries do heavy
GROUP BY aggregations and star schemas are built for this. Dimensions are small
and stable, the fact table grows with every transaction.

---

### ADL-003 — Explicit data quality layer
About 25% of UCI rows have no CustomerID. Others have negative quantities or
zero prices. Instead of silently dropping them, every rejected row is logged to
`etl_quality_log` with a reason and run ID. Silent data loss is how dashboards
end up with wrong numbers.

---

### ADL-004 — FastAPI over Flask
Auto-generates API docs at `/docs` and validates requests using Python type
hints with no extra code. Flask would need both added manually.

---

### ADL-005 — RFM scoring in SQL
RFM is computed once during ETL using `NTILE(5)` and stored. API calls just
read a row. Aggregating 540K transactions on every request in pandas does not
scale.

---

### ADL-006 — Churn definition
Churn candidate: no purchase in 90+ days AND frequency >= 2. The frequency
condition filters out one-time buyers who were never retained to begin with.
The 90-day threshold is a query parameter.

This is a heuristic. A production version would train on labelled churn data.

---

## Project Structure

```
customer-marketing-analytics/
├── data/
│   ├── raw/                  <- UCI CSV goes here (gitignored)
│   └── processed/            <- intermediate cleaned files
├── sql/
│   ├── schema/               <- CREATE TABLE statements
│   └── queries/              <- RFM, churn, segmentation queries
├── src/
│   ├── etl/                  <- extract.py, transform.py, load.py
│   ├── models/               <- Pydantic response schemas
│   ├── analytics/            <- RFM, churn, segmentation logic
│   └── api/
│       ├── routers/          <- one file per endpoint group
│       ├── main.py           <- FastAPI app entry point
│       └── dependencies.py   <- DB connection factory
├── tests/
├── docs/
├── run_pipeline.py           <- single command to run ETL
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Quick Start

```bash
# 1. Clone and set up environment
git clone https://github.com/yourusername/customer-marketing-analytics
cd customer-marketing-analytics
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Download the UCI Online Retail Dataset
# https://archive.ics.uci.edu/ml/datasets/online+retail
# Place the file at: data/raw/OnlineRetail.csv

# 3. Run the ETL pipeline
python run_pipeline.py

# 4. Start the API server
uvicorn src.api.main:app --reload

# 5. Open the interactive API docs
# http://localhost:8000/docs
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/customers` | Paginated customer list |
| GET | `/customers/{id}` | Customer profile + RFM score |
| GET | `/rfm/scores` | All RFM scores, filterable by segment |
| GET | `/rfm/distribution` | Score distribution stats |
| GET | `/segments/summary` | Segment size and revenue overview |
| GET | `/segments/{segment}` | Customers within a specific segment |
| GET | `/segments/churn/candidates` | Churn risk customers |
| GET | `/health` | Latest pipeline run status |
| GET | `/health/quality` | Data quality issues from last run |

---

## Data Quality

Every rejected or flagged row is logged to `etl_quality_log`. Query it after
any pipeline run:

```sql
SELECT issue_type, COUNT(*) FROM etl_quality_log GROUP BY issue_type;
```

| Issue | Action |
|---|---|
| Null CustomerID (~25% of rows) | Excluded |
| Negative Quantity (returns) | Flagged as `is_return=1`, excluded from RFM |
| Zero UnitPrice | Excluded |
| Non-product StockCodes (POST, DOT, etc.) | Excluded |
| Duplicate line items | Deduplicated, logged |

---

## Dataset

[UCI Online Retail Dataset](https://archive.ics.uci.edu/ml/datasets/online+retail)
540K transactions from a UK-based retailer, 2010-2011. License: CC BY 4.0.