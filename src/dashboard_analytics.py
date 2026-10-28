"""
Aggregations that power the dashboard.

Every figure returned here is computed from the logged prediction rows or from
the saved model metadata. When nothing has been logged yet the module returns an
explicit empty summary, and the dashboard renders an empty state rather than
substituting illustrative numbers.
"""

from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional

import numpy as np

import config
from src import prediction_store


def _percentile(values: List[float], q: float) -> Optional[float]:
    if not values:
        return None
    return float(np.percentile(np.asarray(values, dtype=float), q))


def _round(value: Optional[float], dp: int = 2) -> Optional[float]:
    return None if value is None else round(float(value), dp)


def build_summary(
    metrics: Dict[str, Any],
    db_path=None,
) -> Dict[str, Any]:
    """
    Build the full dashboard payload.

    Returns a dict with `has_data` False when no predictions have been logged,
    so the caller can render a meaningful empty state.
    """
    # Resolve once so an explicit None never reaches sqlite3.
    db = db_path or prediction_store.DEFAULT_DB_PATH
    rows = prediction_store.get_all(db)

    model_meta = metrics or {}
    selected_key = model_meta.get("selected_model_key", "random_forest")
    test_metrics = (
        model_meta.get("models", {}).get(selected_key, {}).get("test_metrics", {})
    )
    train_medians = (
        model_meta.get("feature_schema", {}).get("training_medians", {})
    )

    base: Dict[str, Any] = {
        "model": {
            "name": model_meta.get("selected_model", "Unknown model"),
            "test_metrics": test_metrics,
            "train_medians": train_medians,
            "trained_at_utc": model_meta.get("trained_at_utc"),
            "dataset_name": config.DATASET_METADATA["name"],
            "market_region": config.DATASET_METADATA["market_region"],
            "observation_period": config.DATASET_METADATA["observation_period"],
            "currency_symbol": config.DATASET_METADATA["currency_symbol"],
        },
        "dataset_reference": model_meta.get("dataset_statistics", {}),
        "feature_importances": model_meta.get("feature_importances", []),
        "total_predictions": len(rows),
        "has_data": bool(rows),
        "timeline_granularity": "day",
    }

    if not rows:
        base.update(
            {
                "price": None,
                "price_per_sqft": None,
                "area": None,
                "age": None,
                "by_location": [],
                "by_property_type": [],
                "by_parking": [],
                "by_source": [],
                "timeline": [],
                "timeline_granularity": "day",
                "histogram": [],
                "scatter": [],
                "recent": [],
                "first_at": None,
                "last_at": None,
                "vs_training_median": None,
            }
        )
        return base

    prices = [float(r["predicted_price"]) for r in rows]
    ppsf = [
        float(r["price_per_sqft"])
        for r in rows
        if r["price_per_sqft"] is not None
    ]

    # ---- distribution -----------------------------------------------------
    hist_counts, hist_edges = np.histogram(np.asarray(prices), bins=12)
    histogram = [
        {
            "from": round(float(hist_edges[i]), 2),
            "to": round(float(hist_edges[i + 1]), 2),
            "count": int(hist_counts[i]),
        }
        for i in range(len(hist_counts))
    ]

    # ---- grouping helpers -------------------------------------------------
    def group_by(field: str) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[float]] = {}
        for row in rows:
            key = row.get(field)
            key = str(key) if key not in (None, "") else "Not supplied"
            buckets.setdefault(key, []).append(float(row["predicted_price"]))

        out = [
            {
                "name": key,
                "count": len(vals),
                "median": round(float(np.median(vals)), 2),
                "min": round(float(min(vals)), 2),
                "max": round(float(max(vals)), 2),
            }
            for key, vals in buckets.items()
        ]
        out.sort(key=lambda item: (-item["count"], -item["median"]))
        return out

    # ---- timeline ----------------------------------------------------------
    # Bucket by calendar day when activity spans more than one day, otherwise
    # by hour, so a brand-new installation still shows a meaningful shape.
    days = {str(r["created_at"])[:10] for r in rows}
    bucket_by_hour = len(days) <= 1
    key_len = 13 if bucket_by_hour else 10

    buckets: Dict[str, List[float]] = {}
    for row in rows:
        key = str(row["created_at"])[:key_len]
        buckets.setdefault(key, []).append(float(row["predicted_price"]))

    timeline = [
        {
            "date": key,
            "bucket": "hour" if bucket_by_hour else "day",
            "count": len(vals),
            "median": round(float(np.median(vals)), 2),
            "total": round(float(sum(vals)), 2),
        }
        for key, vals in sorted(buckets.items())
    ]
    timeline_granularity = "hour" if bucket_by_hour else "day"

    # ---- scatter: living area vs predicted price --------------------------
    scatter = [
        {
            "area": round(float(r["area_sqft"]), 1),
            "price": round(float(r["predicted_price"]), 2),
            "age": None if r["property_age"] is None else round(float(r["property_age"]), 1),
            "location": r["location"],
        }
        for r in rows
        if r["area_sqft"] is not None
    ]

    # ---- source mix -------------------------------------------------------
    source_counts = Counter(str(r.get("source") or "web") for r in rows)
    by_source = [
        {"name": key, "count": value}
        for key, value in source_counts.most_common()
    ]

    # ---- recent activity --------------------------------------------------
    recent = []
    for row in prediction_store.get_recent(limit=12, db_path=db):
        recent.append(
            {
                "id": row["id"],
                "created_at": row["created_at"],
                "location": row["location"],
                "property_type": row["property_type"],
                "area_sqft": _round(row["area_sqft"], 0),
                "bedrooms": _round(row["bedrooms"], 0),
                "bathrooms": _round(row["bathrooms"], 1),
                "property_age": _round(row["property_age"], 0),
                "parking": row["parking"],
                "predicted_price": round(float(row["predicted_price"]), 2),
                "price_per_sqft": _round(row["price_per_sqft"], 2),
                "source": row["source"],
            }
        )

    median_price = _percentile(prices, 50)
    ref_median = (base["dataset_reference"] or {}).get("price", {}).get("median")
    vs_training_median = (
        round(median_price - float(ref_median), 2)
        if median_price is not None and ref_median is not None
        else None
    )

    areas = [
        float(r["area_sqft"]) for r in rows if r["area_sqft"] is not None
    ]
    ages = [
        float(r["property_age"]) for r in rows if r["property_age"] is not None
    ]

    base.update(
        {
            "price": {
                "min": round(float(min(prices)), 2),
                "q25": _round(_percentile(prices, 25)),
                "median": _round(median_price),
                "mean": round(float(np.mean(prices)), 2),
                "q75": _round(_percentile(prices, 75)),
                "max": round(float(max(prices)), 2),
                "std": round(float(np.std(prices)), 2),
            },
            "price_per_sqft": {
                "median": _round(_percentile(ppsf, 50)),
                "min": _round(min(ppsf)) if ppsf else None,
                "max": _round(max(ppsf)) if ppsf else None,
            },
            "area": {
                "median": _round(_percentile(areas, 50)),
                "min": _round(min(areas)) if areas else None,
                "max": _round(max(areas)) if areas else None,
            },
            "age": {
                "median": _round(_percentile(ages, 50), 1),
                "min": _round(min(ages)) if ages else None,
                "max": _round(max(ages)) if ages else None,
            },
            "by_location": group_by("location"),
            "by_property_type": group_by("property_type"),
            "by_parking": group_by("parking"),
            "by_source": by_source,
            "timeline": timeline,
            "timeline_granularity": timeline_granularity,
            "histogram": histogram,
            "scatter": scatter,
            "recent": recent,
            "first_at": rows[0]["created_at"],
            "last_at": rows[-1]["created_at"],
            "vs_training_median": vs_training_median,
        }
    )
    return base
