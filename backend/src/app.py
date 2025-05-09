from __future__ import annotations

"""
Updated Flask backend for the Financial‑Data Explorer.

Key enhancements (May 2025)
──────────────────────────
• catalogue column `file_name` is now *nullable*  → schema matches seeded DB  
• context‑manager `db_session()` to avoid boiler‑plate open/close  
• new `/api/healthz` for liveness checks  
• `/api/data/<id>` gains `start`, `end`, `frequency` query params for server‑side slicing/resample  
• minor refactor of existing routes for clarity & resilience
"""

import os
from contextlib import contextmanager

import pandas as pd
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import Column, DateTime, Float, MetaData, String, Table, create_engine, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import sessionmaker

# ──────────────────────────────────────────────────────────────────────────────
# Optional data‑processing helpers (keep fallbacks for dev)
# ──────────────────────────────────────────────────────────────────────────────
try:
    from .data_processing import normalize_series, calculate_rolling_correlation
except ImportError as e:  # pragma: no cover  – fallbacks for unit‑tests / CI
    print("Warning: data_processing import failed – using stubs", e)

    def normalize_series(df: pd.DataFrame, method: str = "index_100") -> pd.DataFrame:
        return df  # NO‑OP stub

    def calculate_rolling_correlation(
        df1: pd.DataFrame, df2: pd.DataFrame, window: int = 30
    ) -> pd.DataFrame | None:
        if df1.empty or df2.empty:
            return None
        joined = df1.join(df2, how="inner")
        if joined.shape[1] != 2:
            return None
        col1, col2 = joined.columns
        return (
            joined[col1]
            .rolling(window)
            .corr(joined[col2])
            .to_frame(name=f"corr_{col1}_{col2}")
            .dropna()
        )

# ──────────────────────────────────────────────────────────────────────────────
# Database configuration
# ──────────────────────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(__file__)
DATABASE_PATH = os.path.join(BASE_DIR, "financial_data.db")
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

try:
    engine = create_engine(DATABASE_URL, future=True, echo=False)
    with engine.connect():
        print(f"[OK] Connected to DB at {DATABASE_PATH}")
except SQLAlchemyError as err:
    print("[FATAL] Could not connect to DB:", err)
    engine = None  # routes will 500

metadata = MetaData()

# matches setup_database.py (file_name now nullable)
series_catalog_table = Table(
    "series_catalog",
    metadata,
    Column("name", String, primary_key=True),
    Column("file_name", String, nullable=True),
)

time_series_data_table = Table(
    "time_series_data",
    metadata,
    Column("id", String, primary_key=True),
    Column("series_name", String, nullable=False),
    Column("observation_date", DateTime, nullable=False),
    Column("value", Float, nullable=False),
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


@contextmanager
def db_session():
    """Yield a SQLAlchemy session, ensuring proper close."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ──────────────────────────────────────────────────────────────────────────────
# Flask application
# ──────────────────────────────────────────────────────────────────────────────
app = Flask(__name__)
CORS(app)


@app.route("/api/healthz", methods=["GET"])
def health() -> tuple:
    """Simple liveness / readiness probe."""
    if engine is None:
        return jsonify(ok=False), 500
    try:
        with engine.connect() as conn:
            conn.execute(select(1))
        return jsonify(ok=True)
    except Exception as exc:  # pragma: no cover
        print("Health‑check failed:", exc)
        return jsonify(ok=False), 500


@app.route("/api/datasets", methods=["GET"])
def list_datasets():
    if engine is None:
        return jsonify({"error": "Database connection failed"}), 500
    with db_session() as db:
        try:
            rows = db.execute(select(series_catalog_table.c.name)).scalars().all()
            return jsonify(rows)
        except SQLAlchemyError as err:
            print("DB error fetching datasets:", err)
            return jsonify({"error": "Database query failed"}), 500


@app.route("/api/data/<string:dataset>", methods=["GET"])
def get_series(dataset: str):
    """Return observations for a single series.

    Query params:
        start=YYYY‑MM‑DD  
        end=YYYY‑MM‑DD    
        frequency=[d|w|m|q|a]  
        transform=<method> (passed to normalize_series)
    """
    if engine is None:
        return jsonify({"error": "Database connection failed"}), 500

    start = request.args.get("start")
    end = request.args.get("end")
    freq = request.args.get("frequency")  # d,w,m,q,a
    transform = request.args.get("transform")

    with db_session() as db:
        # confirm catalogue entry
        if not db.execute(
            select(series_catalog_table.c.name).where(series_catalog_table.c.name == dataset)
        ).first():
            return jsonify({"error": f"Series '{dataset}' not found"}), 404

        try:
            stmt = (
                select(
                    time_series_data_table.c.observation_date,
                    time_series_data_table.c.value,
                )
                .where(time_series_data_table.c.series_name == dataset)
                .order_by(time_series_data_table.c.observation_date)
            )
            if start:
                stmt = stmt.where(time_series_data_table.c.observation_date >= start)
            if end:
                stmt = stmt.where(time_series_data_table.c.observation_date <= end)

            rows = db.execute(stmt).fetchall()
            if not rows:
                return jsonify({"error": "No data in selected range"}), 404

            df = pd.DataFrame(rows, columns=["date", dataset]).set_index("date")
            df.index = pd.to_datetime(df.index)

            if freq:
                rule = {"d": "D", "w": "W", "m": "M", "q": "Q", "a": "A"}.get(freq.lower())
                if rule is None:
                    return jsonify({"error": "Invalid frequency"}), 400
                df = df.resample(rule).last().dropna()

            if transform:
                df = normalize_series(df, method=transform) or df

            payload = (
                df.reset_index()
                .rename(columns={"date": "date"})
                .assign(date=lambda d: d["date"].dt.strftime("%Y-%m-%d"))
                .to_dict("records")
            )
            return jsonify(payload)

        except SQLAlchemyError as err:
            print("SQL error in /api/data:", err)
            return jsonify({"error": "Database query failed"}), 500
        except Exception as exc:
            print("Unhandled error in /api/data:", exc)
            return jsonify({"error": "Internal server error"}), 500


@app.route("/api/correlation", methods=["GET"])
def rolling_corr():
    if engine is None:
        return jsonify({"error": "Database connection failed"}), 500

    s1 = request.args.get("series1")
    s2 = request.args.get("series2")
    window_str = request.args.get("window", default="30")

    if not s1 or not s2:
        return jsonify({"error": "series1 and series2 are required"}), 400

    try:
        window = int(window_str)
        if window <= 1:
            return jsonify({"error": "window must be >1"}), 400
    except ValueError:
        return jsonify({"error": "window must be integer"}), 400

    with db_session() as db:
        def fetch_df(series: str) -> pd.DataFrame | None:
            rows = db.execute(
                select(
                    time_series_data_table.c.observation_date,
                    time_series_data_table.c.value,
                )
                .where(time_series_data_table.c.series_name == series)
                .order_by(time_series_data_table.c.observation_date)
            ).fetchall()
            if not rows:
                return None
            df = pd.DataFrame(rows, columns=["date", series])
            df["date"] = pd.to_datetime(df["date"])
            return df.set_index("date")

        df1, df2 = fetch_df(s1), fetch_df(s2)
        if df1 is None or df2 is None:
            return jsonify({"error": "Series not found or empty"}), 404

        corr_df = calculate_rolling_correlation(df1, df2, window)
        if corr_df is None or corr_df.empty:
            return jsonify({"error": "Could not compute correlation"}), 500

        payload = (
            corr_df.reset_index()
            .rename(columns={"index": "date"})
            .assign(date=lambda d: d["date"].dt.strftime("%Y-%m-%d"))
            .to_dict("records")
        )
        return jsonify(payload)


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry‑point (for `python -m src.app`)
# ──────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app.run(debug=True, port=5000)
