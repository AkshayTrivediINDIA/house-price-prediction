"""
Lightweight SQLite store for logged predictions.

Every estimate the application serves is recorded here so the dashboard can
report on real prediction activity. Nothing is synthesised: if no predictions
have been made, the dashboard shows an empty state rather than invented numbers.

The database is created on first use at data/predictions.db, or wherever the
PREDICTIONS_DB_PATH environment variable points (useful on hosts with an
ephemeral filesystem, where it can be aimed at a persistent disk).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import config

DEFAULT_DB_PATH = config.PREDICTIONS_DB_PATH

_CREATE_SQL = """
CREATE TABLE IF NOT EXISTS predictions (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at        TEXT    NOT NULL,
    location          TEXT,
    area_sqft         REAL,
    lot_area_sqft     REAL,
    bedrooms          REAL,
    bathrooms         REAL,
    property_age      REAL,
    floors            REAL,
    parking           TEXT,
    property_type     TEXT,
    predicted_price   REAL    NOT NULL,
    price_per_sqft    REAL,
    model_name        TEXT,
    source            TEXT    NOT NULL DEFAULT 'web'
);

CREATE INDEX IF NOT EXISTS idx_predictions_created_at
    ON predictions (created_at);
"""


def _resolve(db_path) -> Path:
    """Accept a Path/str, or None to mean "the default location"."""
    return Path(db_path) if db_path else Path(DEFAULT_DB_PATH)


def _connect(db_path: Optional[Path] = None) -> sqlite3.Connection:
    db_path = _resolve(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[Path] = None) -> None:
    """Create the predictions table and index if they do not already exist."""
    with _connect(db_path) as conn:
        conn.executescript(_CREATE_SQL)


def log_prediction(
    inputs: Dict[str, Any],
    predicted_price: float,
    price_per_sqft: Optional[float],
    model_name: str,
    source: str = "web",
    db_path: Optional[Path] = None,
) -> int:
    """Record one served estimate and return its row id."""
    init_db(db_path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    sql = """
        INSERT INTO predictions (
            created_at, location, area_sqft, lot_area_sqft, bedrooms,
            bathrooms, property_age, floors, parking, property_type,
            predicted_price, price_per_sqft, model_name, source
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    values = (
        now,
        _as_str(inputs.get("location")),
        _as_float(inputs.get("area_sqft")),
        _as_float(inputs.get("lot_area_sqft")),
        _as_float(inputs.get("bedrooms")),
        _as_float(inputs.get("bathrooms")),
        _as_float(inputs.get("property_age")),
        _as_float(inputs.get("floors")),
        _as_str(inputs.get("parking")),
        _as_str(inputs.get("property_type")),
        float(predicted_price),
        None if price_per_sqft is None else float(price_per_sqft),
        model_name,
        source,
    )

    with _connect(db_path) as conn:
        cur = conn.execute(sql, values)
        conn.commit()
        return int(cur.lastrowid)


def get_recent(limit: int = 25, db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return the most recent predictions, newest first."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM predictions ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()
    return [dict(r) for r in rows]


def get_all(db_path: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Return every logged prediction, oldest first."""
    init_db(db_path)
    with _connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM predictions ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]


def count(db_path: Optional[Path] = None) -> int:
    init_db(db_path)
    with _connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0])


def clear(db_path: Optional[Path] = None) -> int:
    """Delete every logged prediction. Returns the number of rows removed."""
    init_db(db_path)
    with _connect(db_path) as conn:
        removed = conn.execute("SELECT COUNT(*) FROM predictions").fetchone()[0]
        conn.execute("DELETE FROM predictions")
        conn.execute("DELETE FROM sqlite_sequence WHERE name='predictions'")
        conn.commit()
    return int(removed)


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _as_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == "":
            return None
        result = float(str(value).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return result if result == result and result not in (float("inf"), float("-inf")) else None


def _as_str(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


if __name__ == "__main__":
    init_db()
    print(f"Prediction store ready at {DEFAULT_DB_PATH} ({count()} rows).")
