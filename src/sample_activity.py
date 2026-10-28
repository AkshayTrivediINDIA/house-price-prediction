"""
Populate the prediction log with genuine model runs.

This exists so the dashboard has real activity to show without anyone having to
click through the form dozens of times. It takes actual properties from the
cleaned dataset, runs them through the saved pipeline exactly as a web request
would, and records the resulting estimates.

The predictions are real model outputs on real properties - nothing is invented.
They are tagged with source='sample' so the dashboard and the log can always
distinguish them from estimates requested through the form.
"""

from __future__ import annotations

import random
from typing import Any, Dict, List

import pandas as pd

import config
from src import prediction_store
from src.predict import predict_price


def load_real_properties(
    n: int = 40,
    seed: int = 7,
    processed_path=config.PROCESSED_DATA_PATH,
) -> List[Dict[str, Any]]:
    """Take a deterministic random sample of real properties from the dataset."""
    df = pd.read_csv(processed_path)
    n = max(1, min(int(n), len(df)))
    sample = df.sample(n=n, random_state=seed).reset_index(drop=True)

    properties: List[Dict[str, Any]] = []
    for _, row in sample.iterrows():
        properties.append(
            {
                "location": str(row["location"]),
                "area_sqft": float(row["area_sqft"]),
                "lot_area_sqft": float(row["lot_area_sqft"]),
                "bedrooms": float(row["bedrooms"]),
                "bathrooms": float(row["bathrooms"]),
                "property_age": float(row["property_age"]),
                "floors": float(row["floors"]),
                "parking": str(row["parking"]),
                "property_type": str(row["property_type"]),
            }
        )
    return properties


def generate_sample_activity(
    n: int = 40,
    seed: int = 7,
    db_path=None,
) -> Dict[str, Any]:
    """
    Run the saved model over a real sample of properties and log each estimate.

    Returns a summary of what was logged. Properties that fail validation
    (for example records with imputed bedrooms) are skipped and counted.
    """
    n = int(n)
    if not 1 <= n <= 200:
        raise ValueError(f"count must be between 1 and 200 (got {n})")

    properties = load_real_properties(n=n, seed=seed)

    logged = 0
    skipped = 0
    prices: List[float] = []

    for prop in properties:
        try:
            result = predict_price(prop)
        except Exception:
            skipped += 1
            continue

        prediction_store.log_prediction(
            inputs=prop,
            predicted_price=result["predicted_price"],
            price_per_sqft=result["explanation"]["predicted_price_per_sqft"],
            model_name=result["model_name"],
            source="sample",
            db_path=db_path if db_path else prediction_store.DEFAULT_DB_PATH,
        )
        logged += 1
        prices.append(result["predicted_price"])

    return {
        "success": logged > 0,
        "requested": len(properties),
        "logged": logged,
        "skipped": skipped,
        "median_price": round(float(pd.Series(prices).median()), 2) if prices else None,
        "source": "sample",
    }


if __name__ == "__main__":
    summary = generate_sample_activity()
    print(summary)
