# backend/src/setup_database.py
import os
import sys
from typing import List

import pandas as pd
from sqlalchemy import (
    create_engine, Table, Column, String, Float, DateTime, MetaData, select
)
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.sqlite import insert as sqlite_insert  # for OR IGNORE

# ---- local imports ---------------------------------------------------------
try:
    from .data_loader import (
        get_available_datasets_from_api,
        fetch_series_observations_from_api,
    )
except ImportError as e:
    print(f"[WARN] Could not import data_loader: {e}")
    # dummy fallback prevents hard-crash in unit-tests without network
    get_available_datasets_from_api = lambda: []
    fetch_series_observations_from_api = lambda _: None

# ---- configuration ---------------------------------------------------------
HERE = os.path.dirname(__file__)
DATABASE_FILE = "financial_data.db"
DATABASE_PATH = os.path.join(HERE, DATABASE_FILE)
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

BATCH_SIZE = 100  # ~ < 999 SQLite variable limit / 4 cols

# ---- database schema -------------------------------------------------------
metadata = MetaData()

time_series_data_table = Table(
    "time_series_data",
    metadata,
    Column("id", String, primary_key=True),
    Column("series_name", String, nullable=False),
    Column("observation_date", DateTime, nullable=False),
    Column("value", Float, nullable=False),
)

series_catalog_table = Table(
    "series_catalog",
    metadata,
    Column("name", String, primary_key=True),
    Column("file_name", String, nullable=True),          # <- now NULL-able
)

# ---- engine ----------------------------------------------------------------
try:
    engine = create_engine(DATABASE_URL, echo=False)
    with engine.connect():
        print(f"[OK] Connected to DB at {DATABASE_PATH}")
except SQLAlchemyError as err:
    sys.exit(f"[FATAL] DB connection failed: {err}")

# ---- helpers ---------------------------------------------------------------
def create_tables() -> None:
    """Create tables if they don't already exist."""
    try:
        metadata.create_all(engine)
        print("[OK] Tables ensured.")
    except SQLAlchemyError as err:
        sys.exit(f"[FATAL] Table creation failed: {err}")

def safe_insert_catalog(conn, series_id: str) -> None:
    """Idempotent insert into series_catalog (SQLite flavour)."""
    stmt = (
        sqlite_insert(series_catalog_table)
        .values(name=series_id, file_name=None)
        .prefix_with("OR IGNORE")
    )
    conn.execute(stmt)

def load_series_from_api_to_db(series_id: str) -> None:
    """Fetch one series via FRED API and load into SQLite."""
    # quick existence test — if catalog entry present, skip
    with engine.connect() as conn:
        if conn.execute(
            select(series_catalog_table.c.name).where(series_catalog_table.c.name == series_id)
        ).first():
            print(f"[SKIP] {series_id} already catalogued.")
            return

    print(f"[GET ] FRED → {series_id}")
    df = fetch_series_observations_from_api(series_id)
    if df is None or df.empty:
        print(f"[WARN] No data for {series_id}; skipping.")
        return

    value_col = df.columns[0]
    to_insert = [
        {
            "id": f"{series_id}_{idx.strftime('%Y-%m-%d')}",
            "series_name": series_id,
            "observation_date": idx,
            "value": row[value_col],
        }
        for idx, row in df.iterrows()
    ]

    try:
        with engine.begin() as conn:               # → transaction
            safe_insert_catalog(conn, series_id)

            print(f"[LOAD] {series_id}: {len(to_insert)} rows → DB")
            for i in range(0, len(to_insert), BATCH_SIZE):
                conn.execute(time_series_data_table.insert(), to_insert[i : i + BATCH_SIZE])

    except SQLAlchemyError as err:
        print(f"[ERR ] DB issue while loading {series_id}: {err}")

def load_datasets_from_api_to_db(series_ids: List[str]) -> None:
    if not series_ids:
        print("[INFO] No series IDs supplied.")
        return
    for sid in series_ids:
        load_series_from_api_to_db(sid)
    print("[DONE] All requested series processed.")

# ---- main ------------------------------------------------------------------
if __name__ == "__main__":
    print("=== Financial-Data DB Seeder ===")
    create_tables()

    SERIES_IDS = [
        "UNRATE",
        "CPIAUCSL",
        "DFF",
        "GDP",
        "FEDFUNDS",
        "INDPRO",
        "PAYEMS",
        "CSUSHPISA",
        "T10YFFM",
        "DGS10",
        "MORTGAGE30US",
        "VIXCLS",
        "DCOILWTICO",
        "DCOILBRENTEU",
    ]

    load_datasets_from_api_to_db(SERIES_IDS)

    # ---- quick sanity check -------------------------------------------------
    from sqlalchemy import func

    with engine.connect() as conn:
        total = conn.execute(select(func.count()).select_from(time_series_data_table)).scalar()
        catalog_n = conn.execute(select(func.count()).select_from(series_catalog_table)).scalar()
        print(f"[INFO] time_series_data rows   : {total}")
        print(f"[INFO] series_catalog entries : {catalog_n}")