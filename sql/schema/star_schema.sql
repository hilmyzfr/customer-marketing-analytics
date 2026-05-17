PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;


-------------------------------------------------------------
-- DIMENSION: Date
-- One row per calendar day across the dataset range
-- Grain: one day
-------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_date (
    date_key        INTEGER PRIMARY KEY,  -- surrogate key: YYYYMMDD e.g. 20101201
    full_date       DATE NOT NULL UNIQUE,
    year            INTEGER NOT NULL,
    quarter         INTEGER NOT NULL,     -- 1 to 4
    month           INTEGER NOT NULL,     -- 1 to 12
    month_name      TEXT NOT NULL,
    week_of_year    INTEGER NOT NULL,
    day_of_month    INTEGER NOT NULL,
    day_of_week     INTEGER NOT NULL,     -- 0=Monday, 6=Sunday
    day_name        TEXT NOT NULL,
    is_weekend      INTEGER NOT NULL DEFAULT 0  -- 0 or 1
);

CREATE INDEX IF NOT EXISTS idx_dim_date_full 
    ON dim_date(full_date);
CREATE INDEX IF NOT EXISTS idx_dim_date_year_month 
    ON dim_date(year, month);
-------------------------------------------------------------



-------------------------------------------------------------
-- DIMENSION: Customer
-- One row per unique customer
-- Grain: one customer
-------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_customer (
    customer_key    INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id     TEXT NOT NULL UNIQUE,  -- original UCI CustomerID e.g. "17850"
    country         TEXT,
    first_seen_date DATE,
    last_seen_date  DATE,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_customer_id 
    ON dim_customer(customer_id);
CREATE INDEX IF NOT EXISTS idx_dim_customer_country 
    ON dim_customer(country);
-------------------------------------------------------------



-------------------------------------------------------------
-- DIMENSION: Product
-- One row per unique product
-- Grain: one product
-------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_product (
    product_key     INTEGER PRIMARY KEY AUTOINCREMENT,
    stock_code      TEXT NOT NULL UNIQUE,
    description     TEXT,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dim_product_code
    ON dim_product(stock_code);    
-------------------------------------------------------------




-------------------------------------------------------------
-- FACT: fact_transactions
-- One row per invoice line item
-- Grain: one product within one invoice
-------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fact_transactions (
    transaction_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no      TEXT NOT NULL,
    customer_key    INTEGER NOT NULL REFERENCES dim_customer(customer_key),
    product_key     INTEGER NOT NULL REFERENCES dim_product(product_key),
    date_key        INTEGER NOT NULL REFERENCES dim_date(date_key),
    invoice_date    TIMESTAMP NOT NULL,
    quantity        INTEGER NOT NULL,
    unit_price      REAL NOT NULL,
    is_return       INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_fact_customer
    ON fact_transactions(customer_key);
CREATE INDEX IF NOT EXISTS idx_fact_date
    ON fact_transactions(date_key);
CREATE INDEX IF NOT EXISTS idx_fact_product
    ON fact_transactions(product_key);
CREATE INDEX IF NOT EXISTS idx_fact_invoice
    ON fact_transactions(invoice_no);


-- ------------------------------------------------------------
-- AUDIT: etl_quality_log
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_quality_log (
    log_id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id          TEXT NOT NULL,
    source_row      INTEGER,
    invoice_no      TEXT,
    customer_id     TEXT,
    issue_type      TEXT NOT NULL,
    issue_detail    TEXT,
    logged_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_quality_run 
    ON etl_quality_log(run_id);
CREATE INDEX IF NOT EXISTS idx_quality_type 
    ON etl_quality_log(issue_type);

-- ------------------------------------------------------------
-- AUDIT: etl_runs
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS etl_runs (
    run_id          TEXT PRIMARY KEY,
    started_at      TIMESTAMP NOT NULL,
    completed_at    TIMESTAMP,
    status          TEXT NOT NULL DEFAULT 'RUNNING',
    rows_extracted  INTEGER DEFAULT 0,
    rows_loaded     INTEGER DEFAULT 0,
    rows_rejected   INTEGER DEFAULT 0,
    error_message   TEXT
);