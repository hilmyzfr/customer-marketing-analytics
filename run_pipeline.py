"""
run_pipeline.py — One-command ETL runner
Usage: python run_pipeline.py
"""
import logging
import sqlite3
import sys
import uuid
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline")

sys.path.insert(0, str(Path(__file__).parent))

from src.etl.extract import extract, ExtractionError
from src.etl.transform import transform
from src.etl.load import load

SOURCE_PATH = "data/raw/OnlineRetail.xlsx"
DB_PATH = "data/analytics.db"
SCHEMA_PATH = Path("sql/schema/star_schema.sql")


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_PATH.read_text())
    conn.commit()
    logger.info("Schema initialised")


def run_pipeline() -> None:
    run_id = str(uuid.uuid4())
    started_at = datetime.utcnow()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA foreign_keys = ON")

    init_schema(conn)

    conn.execute(
        "INSERT INTO etl_runs (run_id, started_at, status) VALUES (?, ?, 'RUNNING')",
        [run_id, started_at.isoformat()],
    )
    conn.commit()

    try:
        logger.info("=== STAGE 1: EXTRACT ===")
        raw_df = extract(SOURCE_PATH)

        logger.info("=== STAGE 2: TRANSFORM ===")
        result = transform(raw_df)

        logger.info("=== STAGE 3: LOAD ===")
        stats = load(conn, result.clean_df, result.issues, run_id)

        conn.execute(
            """
            UPDATE etl_runs
            SET status = 'SUCCESS',
                completed_at = ?,
                rows_extracted = ?,
                rows_loaded = ?,
                rows_rejected = ?
            WHERE run_id = ?
            """,
            [
                datetime.utcnow().isoformat(),
                stats["rows_extracted"],
                stats["rows_loaded"],
                stats["rows_rejected"],
                run_id,
            ],
        )
        conn.commit()

        logger.info("=== PIPELINE COMPLETE ===")
        logger.info("  Run ID     : %s", run_id)
        logger.info("  Extracted  : %d rows", stats["rows_extracted"])
        logger.info("  Loaded     : %d rows", stats["rows_loaded"])
        logger.info("  Rejected   : %d rows", stats["rows_rejected"])

    except ExtractionError as exc:
        logger.error("EXTRACT FAILED: %s", exc)
        conn.execute(
            "UPDATE etl_runs SET status='FAILED', completed_at=?, error_message=? WHERE run_id=?",
            [datetime.utcnow().isoformat(), str(exc), run_id],
        )
        conn.commit()
        sys.exit(1)

    except Exception as exc:
        logger.exception("PIPELINE FAILED")
        conn.execute(
            "UPDATE etl_runs SET status='FAILED', completed_at=?, error_message=? WHERE run_id=?",
            [datetime.utcnow().isoformat(), str(exc), run_id],
        )
        conn.commit()
        sys.exit(1)

    finally:
        conn.close()


if __name__ == "__main__":
    run_pipeline()