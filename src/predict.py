"""
Inference module for the HomeValue House Price Prediction system.

Loads the saved Joblib pipeline and its metadata, validates and converts user
input using the exact same feature schema and preprocessing assumptions used
during training, and returns a prediction with a model-derived explanation.

Design notes:
- The model artifact is loaded once and cached (no retraining per request).
- Unseen categorical values are handled by the encoder's `handle_unknown="ignore"`
  setting, which encodes them as all-zeros; we detect this and warn the user.
- Missing numerical values are imputed by the fitted SimpleImputer (median).
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

import config


class PredictionError(Exception):
    """Raised when valid input cannot be converted into a valid prediction."""


@lru_cache(maxsize=1)
def load_artifacts(
    model_path: str = str(config.MODEL_PATH),
    metrics_path: str = str(config.METRICS_PATH),
) -> Tuple[Pipeline, Dict[str, Any]]:
    """Load and cache the fitted pipeline and its metadata bundle."""
    model_file = Path(model_path)
    metrics_file = Path(metrics_path)

    if not model_file.exists():
        raise FileNotFoundError(
            f"Trained model not found at {model_file}. Run `python -m src.train_model` first."
        )
    if not metrics_file.exists():
        raise FileNotFoundError(
            f"Metrics file not found at {metrics_file}. Run `python -m src.train_model` first."
        )

    pipeline = joblib.load(model_file)

    # Prefer the metadata bundle attached to the pipeline itself, because it is
    # guaranteed to describe exactly this fitted artifact. Fall back to the
    # standalone metrics.json written by the training script.
    metadata = getattr(pipeline, "metadata_", None)
    if metadata is None:
        metadata = _read_json(metrics_file)

    return pipeline, metadata


def _read_json(path: Path) -> Dict[str, Any]:
    import json

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_and_convert_inputs(raw_input: Dict[str, Any]) -> Tuple[pd.DataFrame, List[str]]:
    """
    Validate user-provided inputs and convert them into a single-row DataFrame
    matching the exact training feature schema.

    Returns:
        (input_dataframe, list_of_validation_warnings)

    Raises:
        ValueError: if any hard validation rule is violated.
    """
    errors: List[str] = []
    warnings: List[str] = []
    row: Dict[str, Any] = {}

    # --- Categorical: location ---
    location = str(raw_input.get("location", "") or "").strip()
    known_locations = set(config.NEIGHBORHOOD_MAP.values())
    if not location:
        errors.append("Location is required.")
    elif location not in known_locations:
        errors.append(
            f"Location '{location}' is not one of the neighborhoods present in the training data."
        )
    row["location"] = location

    # --- Categorical: parking (free-text allowed, unseen values supported) ---
    parking = str(raw_input.get("parking", "") or "").strip()
    if not parking:
        errors.append("Parking availability is required.")
    elif parking not in config.PARKING_OPTIONS:
        warnings.append(
            f"Parking option '{parking}' was not seen during training. "
            "The model will fall back to learned averages for this field."
        )
    row["parking"] = parking

    # --- Categorical: property_type ---
    property_type = str(raw_input.get("property_type", "") or "").strip()
    if not property_type:
        errors.append("Property type is required.")
    elif property_type not in config.PROPERTY_TYPE_OPTIONS:
        warnings.append(
            f"Property type '{property_type}' was not seen during training. "
            "The model will fall back to learned averages for this field."
        )
    row["property_type"] = property_type

    # --- Numerical inputs with bounds checking ---
    int_fields = {"bedrooms", "property_age"}
    for field, rules in config.VALIDATION_RULES.items():
        raw_value = raw_input.get(field, None)
        if raw_value is None or (isinstance(raw_value, str) and not raw_value.strip()):
            errors.append(f"{rules['label']} is required.")
            row[field] = np.nan
            continue

        try:
            value = float(str(raw_value).replace(",", "").strip())
        except (TypeError, ValueError):
            errors.append(f"{rules['label']} must be a number.")
            row[field] = np.nan
            continue

        if not np.isfinite(value):
            errors.append(f"{rules['label']} must be a finite number.")
            row[field] = np.nan
            continue

        if value < rules["min"] or value > rules["max"]:
            errors.append(
                f"{rules['label']} must be between {rules['min']:,.0f} and {rules['max']:,.0f}."
            )
            row[field] = np.nan
            continue

        row[field] = int(value) if field in int_fields else float(value)

    # --- Cross-field sanity checks ---
    bedrooms = row.get("bedrooms")
    area = row.get("area_sqft")
    lot_area = row.get("lot_area_sqft")

    if (
        isinstance(bedrooms, (int, float))
        and isinstance(area, (int, float))
        and not pd.isna(bedrooms)
        and not pd.isna(area)
    ):
        if area < (bedrooms * 100):
            errors.append(
                f"Living area ({area:,.0f} sq ft) is unrealistically small for "
                f"{int(bedrooms)} bedrooms. Please check the values."
            )

    if (
        isinstance(lot_area, (int, float))
        and isinstance(area, (int, float))
        and not pd.isna(lot_area)
        and not pd.isna(area)
        and lot_area < area
    ):
        errors.append("Lot area cannot be smaller than the living area of the home.")

    if errors:
        raise ValueError(" ".join(errors))

    X = pd.DataFrame([row], columns=config.ALL_FEATURES)
    return X, warnings


def _local_sensitivity(
    pipeline: Pipeline,
    X_input: pd.DataFrame,
    baseline_prediction: float,
) -> List[Dict[str, Any]]:
    """
    Measure how the prediction for THIS property changes when a single feature
    is varied, with all other features held constant.

    This is a what-if sensitivity analysis on the fitted model response surface;
    it is not a causal effect and not an exact additive decomposition of the
    tree ensemble.
    """
    steps: Dict[str, List[float]] = {
        "area_sqft": [150.0],
        "lot_area_sqft": [1000.0],
        "bedrooms": [1.0],
        "bathrooms": [1.0],
        "property_age": [10.0],
    }

    results: List[Dict[str, Any]] = []

    # Floors are capped at 2.5 in the training data, so step downwards for tall
    # properties instead of extrapolating above the observed range.
    current_floors = X_input.at[0, "floors"]
    if not pd.isna(current_floors):
        steps["floors"] = [-0.5] if float(current_floors) >= 2.0 else [0.5]

    for feature, deltas in steps.items():
        current = X_input.at[0, feature]
        if pd.isna(current):
            continue
        for delta in deltas:
            perturbed = X_input.copy()
            perturbed.at[0, feature] = float(current) + delta
            try:
                new_pred = float(pipeline.predict(perturbed)[0])
            except Exception:
                continue
            results.append(
                {
                    "feature": feature,
                    "label": config.FEATURE_LABELS[feature],
                    "delta": delta,
                    "current_value": float(current),
                    "new_value": float(current) + delta,
                    "price_change": round(new_pred - baseline_prediction, 2),
                }
            )

    # Categorical what-if: what if the same home were in the median-priced neighborhood
    metadata = getattr(pipeline, "metadata_", {}) or {}
    nbh_summary = (
        metadata.get("dataset_statistics", {}).get("neighborhood_summary", []) or []
    )
    if nbh_summary:
        current_location = str(X_input.at[0, "location"])
        ordered = sorted(nbh_summary, key=lambda x: x["median_price"])
        median_location = ordered[len(ordered) // 2]["location"]
        if median_location != current_location:
            perturbed = X_input.copy()
            perturbed.at[0, "location"] = median_location
            try:
                alt_pred = float(pipeline.predict(perturbed)[0])
                results.append(
                    {
                        "feature": "location",
                        "label": config.FEATURE_LABELS["location"],
                        "delta": None,
                        "current_value": current_location,
                        "new_value": median_location,
                        "price_change": round(alt_pred - baseline_prediction, 2),
                    }
                )
            except Exception:
                pass

    results.sort(key=lambda x: abs(x["price_change"]), reverse=True)
    return results


def _build_explanation(
    metadata: Dict[str, Any],
    X_input: pd.DataFrame,
    prediction: float,
    sensitivity: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Assemble a plain-language, strictly model-derived explanation of the estimate."""
    stats = metadata.get("dataset_statistics", {})
    price_stats = stats.get("price", {})
    ppsf_stats = stats.get("price_per_sqft", {})
    medians = metadata.get("feature_schema", {}).get("training_medians", {})

    area = float(X_input.at[0, "area_sqft"])
    predicted_ppsf = prediction / area if area else float("nan")

    market_median = float(price_stats.get("median", float("nan")))
    vs_market = prediction - market_median
    percentile_note = ""
    if prediction <= price_stats.get("q25", np.inf):
        percentile_note = "within the lower quartile of recorded sale prices"
    elif prediction <= price_stats.get("median", np.inf):
        percentile_note = "below the median recorded sale price"
    elif prediction <= price_stats.get("q75", np.inf):
        percentile_note = "above the median recorded sale price"
    else:
        percentile_note = "within the upper quartile of recorded sale prices"

    # Human-readable comparison of this property against training medians
    comparisons: List[Dict[str, Any]] = []
    for feature in config.NUMERICAL_FEATURES:
        current = X_input.at[0, feature]
        if pd.isna(current):
            continue
        median_value = medians.get(feature)
        if median_value is None:
            continue
        diff = float(current) - float(median_value)
        if abs(diff) < 1e-9:
            position = "at"
        elif diff > 0:
            position = "above"
        else:
            position = "below"
        comparisons.append(
            {
                "feature": feature,
                "label": config.FEATURE_LABELS[feature],
                "value": float(current),
                "median": float(median_value),
                "difference": round(diff, 2),
                "position": position,
            }
        )

    global_top = metadata.get("feature_importances", [])[:3]

    return {
        "predicted_price_per_sqft": round(float(predicted_ppsf), 2),
        "market_median_price": round(market_median, 0),
        "market_median_price_per_sqft": ppsf_stats.get("median"),
        "difference_vs_market_median": round(float(vs_market), 0),
        "price_band": percentile_note,
        "versus_training_medians": comparisons,
        "top_global_features": global_top,
        "sensitivity": sensitivity,
    }


def predict_price(raw_input: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run the full inference path: validate → transform → predict → explain.

    Returns a JSON-serializable dictionary. Raises ValueError for invalid input
    and PredictionError when the model cannot produce a usable estimate.
    """
    pipeline, metadata = load_artifacts()

    X_input, warnings = validate_and_convert_inputs(raw_input)

    try:
        raw_prediction = pipeline.predict(X_input)[0]
    except Exception as exc:  # pragma: no cover - defensive
        raise PredictionError("The model could not process these property details.") from exc

    prediction = float(raw_prediction)
    if not np.isfinite(prediction) or prediction <= 0:
        raise PredictionError("The model returned an unusable estimate for these inputs.")

    prediction = round(prediction, 2)
    sensitivity = _local_sensitivity(pipeline, X_input, prediction)
    explanation = _build_explanation(metadata, X_input, prediction, sensitivity)

    metrics = metadata.get("models", {})
    selected_key = metadata.get("selected_model_key", "random_forest")
    test_metrics = metrics.get(selected_key, {}).get("test_metrics", {})
    feature_schema = metadata.get("feature_schema", {})

    input_summary = {}
    for feature in config.ALL_FEATURES:
        value = X_input.at[0, feature]
        if isinstance(value, (np.integer, np.floating)):
            value = float(value)
        input_summary[feature] = value if not pd.isna(value) else None

    knowledge_cutoff_issues = []
    for cat_feature in config.CATEGORICAL_FEATURES:
        value = str(X_input.at[0, cat_feature])
        known = feature_schema.get("known_categories", {}).get(cat_feature, [])
        if known and value not in known:
            knowledge_cutoff_issues.append(cat_feature)

    return {
        "success": True,
        "predicted_price": prediction,
        "currency": config.DATASET_METADATA["currency"],
        "currency_symbol": config.DATASET_METADATA["currency_symbol"],
        "model_name": metadata.get("selected_model", "Random Forest Regressor"),
        "model_metrics": test_metrics,
        "input_summary": input_summary,
        "feature_labels": config.FEATURE_LABELS,
        "explanation": explanation,
        "warnings": warnings,
        "unseen_categories": knowledge_cutoff_issues,
        "disclaimer": (
            "This estimate is generated by a machine-learning model trained on documented "
            "residential sales from the Ames, Iowa housing dataset. It is a statistical "
            "estimate for educational and comparative purposes only, not a formal property "
            "valuation, appraisal, or financial advice."
        ),
    }


def predict_from_dataframe(df: pd.DataFrame) -> np.ndarray:
    """Batch prediction helper for an already-validated DataFrame."""
    pipeline, _ = load_artifacts()
    return pipeline.predict(df[config.ALL_FEATURES])


if __name__ == "__main__":
    sample_input = {
        "location": "Northridge Heights",
        "area_sqft": 2100,
        "lot_area_sqft": 12000,
        "bedrooms": 4,
        "bathrooms": 2.5,
        "property_age": 15,
        "floors": 2,
        "parking": "2-Car Garage",
        "property_type": "Single-Family Detached",
    }
    result = predict_price(sample_input)
    print(f"Sample prediction ({config.DATASET_METADATA['currency']}):")
    print(f"  Estimated price: ${result['predicted_price']:,.2f}")
    print(f"  Price per sq ft: ${result['explanation']['predicted_price_per_sqft']:,.2f}")
    print(f"  Model: {result['model_name']}  |  Test R²: {result['model_metrics'].get('r2')}")
    print("  Top local sensitivities:")
    for item in result["explanation"]["sensitivity"][:4]:
        print(f"    {item['label']}: {item['price_change']:+,.0f}")
    print(f"  Disclaimer: {result['disclaimer']}")
