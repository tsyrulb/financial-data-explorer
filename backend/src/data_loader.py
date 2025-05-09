"""
data_loader.py  ·  FRED + local-CSV helpers
────────────────────────────────────────────
Call from setup_database.py or anywhere else you need FRED data.

Env:
    • .env one directory above this file (backend/.env) must contain FRED_API_KEY.
"""

from __future__ import annotations

import os
import time
from typing import Dict, List, Optional

import pandas as pd
import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ────────────────────────────────────────────────────────────────────────────────
# Environment variables
# ────────────────────────────────────────────────────────────────────────────────
BACKEND_DIR = os.path.dirname(os.path.dirname(__file__))
dotenv_path = os.path.join(BACKEND_DIR, ".env")
load_dotenv(dotenv_path)

FRED_API_KEY = os.getenv("FRED_API_KEY") or ""
FRED_API_BASE_URL = "https://api.stlouisfed.org/fred/"

if not FRED_API_KEY:
    raise RuntimeError(
        "FRED_API_KEY not found in environment (.env). "
        "Sign up at https://fred.stlouisfed.org/docs/api/api_key.html "
        "and add `FRED_API_KEY=...` to backend/.env"
    )

# ────────────────────────────────────────────────────────────────────────────────
# Logging helper – defers to root logger if configured, else prints
# ────────────────────────────────────────────────────────────────────────────────
import logging

_log = logging.getLogger("data_loader")
if not _log.handlers:
    # configure a fallback only if the user hasn't set up logging
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    _log.addHandler(handler)
    _log.setLevel(logging.INFO)

# ────────────────────────────────────────────────────────────────────────────────
# requests Session with retries
# ────────────────────────────────────────────────────────────────────────────────
_RETRY_STRATEGY = Retry(
    total=4,
    backoff_factor=0.5,
    status_forcelist=(429, 500, 502, 503, 504),
    allowed_methods=("GET",),
)

_session = requests.Session()
_session.mount("https://", HTTPAdapter(max_retries=_RETRY_STRATEGY))

# ────────────────────────────────────────────────────────────────────────────────
# Local CSV helpers (still useful for offline mode / tests)
# ────────────────────────────────────────────────────────────────────────────────
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "public_datasets")


def load_fred_csv(file_name: str) -> Optional[pd.DataFrame]:
    """
    Load a single-column FRED csv into a DataFrame with DatetimeIndex.
    """
    file_path = os.path.join(DATA_DIR, file_name)
    series_id = file_name.replace(".csv", "")

    try:
        df = pd.read_csv(file_path, parse_dates=["observation_date"]).set_index(
            "observation_date"
        )
    except FileNotFoundError:
        _log.error("Local file not found: %s", file_path)
        return None
    except Exception as exc:
        _log.error("Error reading %s: %s", file_path, exc)
        return None

    if df.shape[1] != 1:
        _log.warning("%s has %s columns – expected 1. Skipping.", file_name, df.shape[1])
        return None

    col = df.columns[0]
    if col != series_id:
        _log.debug("Renaming column '%s' → '%s'", col, series_id)
        df.rename(columns={col: series_id}, inplace=True)

    return df.dropna()


def get_available_datasets_from_files() -> List[str]:
    """
    List series IDs available as CSVs under data/public_datasets.
    """
    try:
        return [
            f.replace(".csv", "")
            for f in os.listdir(DATA_DIR)
            if f.endswith(".csv")
        ]
    except FileNotFoundError:
        _log.warning("Local data directory not found: %s", DATA_DIR)
        return []
    except Exception as exc:
        _log.error("Error listing CSVs: %s", exc)
        return []


# ────────────────────────────────────────────────────────────────────────────────
# FRED API helpers
# ────────────────────────────────────────────────────────────────────────────────
def _fred_api(
    endpoint: str, params: Optional[Dict[str, str | int]] = None
) -> Optional[Dict]:
    """
    Low-level GET wrapper with retries + logging.
    """
    url = f"{FRED_API_BASE_URL}{endpoint}"
    payload = {"api_key": FRED_API_KEY, "file_type": "json", **(params or {})}

    try:
        r = _session.get(url, params=payload, timeout=15)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.HTTPError as exc:
        if r.status_code == 400:
            _log.warning("FRED 400 for %s (%s)", endpoint, payload.get("series_id"))
        else:
            _log.error("FRED HTTP %s: %s", r.status_code, exc)
        return None
    except requests.exceptions.RequestException as exc:
        _log.error("Network error calling FRED: %s", exc)
        return None


def get_available_datasets_from_api(
    category_id: int = 329, limit: int = 100
) -> List[str]:
    """
    Return series IDs in a FRED category (defaults to 'Monetary Data': 329).
    """
    _log.info("Fetching FRED series list for category=%s (limit=%s)", category_id, limit)
    data = _fred_api(
        "category/series",
        {"category_id": category_id, "limit": limit},
    )

    return [s["id"] for s in data.get("series", [])] if data else []


def fetch_series_observations_from_api(
    series_id: str,
    start: str | None = None,
    end: str | None = None,
    frequency: str | None = None,
) -> Optional[pd.DataFrame]:
    """
    Fetch a FRED series as a tidy DataFrame (index=date, column=series_id).
    All numeric values are float64.
    """
    params: Dict[str, str] = {"series_id": series_id}
    if start:
        params["observation_start"] = start
    if end:
        params["observation_end"] = end
    if frequency:
        params["frequency"] = frequency  # 'd','w','m','q','a'

    _log.debug("FRED GET series/observations %s", params)
    data = _fred_api("series/observations", params)
    if not data or "observations" not in data:
        _log.warning("No observations payload for %s", series_id)
        return None

    df = (
        pd.DataFrame(data["observations"])
        .query("value != '.'")  # drop missing markers
        .assign(date=lambda d: pd.to_datetime(d["date"]))
        .set_index("date")
        .drop(columns=["realtime_start", "realtime_end"], errors="ignore")
        .assign(value=lambda d: pd.to_numeric(d["value"]))
        .rename(columns={"value": series_id})
    )
    return df if not df.empty else None


# ────────────────────────────────────────────────────────────────────────────────
# CLI test harness
# ────────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    t0 = time.perf_counter()

    ids = get_available_datasets_from_api(limit=5)
    print("API series sample:", ids)

    demo = "UNRATE"
    df_demo = fetch_series_observations_from_api(demo)
    if df_demo is not None:
        print(df_demo.head())
        print(df_demo.info())

    print(f"Done in {time.perf_counter() - t0:0.2f}s")
