"""
Flask web application for the HomeValue House Price Prediction system.

Routes:
  GET  /                → Landing page
  GET  /predict         → Prediction form
  POST /api/predict     → Validate input and return a real model prediction (JSON)
  GET  /result          → Server-rendered result page (reconstructed from query params)
  GET  /insights        → Data analysis page with real charts and metrics
  GET  /api/metrics     → Saved evaluation metrics (JSON)
  GET  /health          → Simple health check (JSON)
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import HTTPException

import config
from src import dashboard_analytics, prediction_store, sample_activity
from src.predict import PredictionError, predict_price

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("homevalue")

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False
# Pick up template and static changes without a manual restart during development.
app.config["TEMPLATES_AUTO_RELOAD"] = True


# --------------------------------------------------------------------------
# Jinja template filters
# --------------------------------------------------------------------------
@app.template_filter("currency")
def currency_filter(value: Any) -> str:
    """Format a number as whole US dollars, e.g. 208500 → '$208,500'."""
    try:
        return f"${float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"


@app.template_filter("currency2")
def currency2_filter(value: Any) -> str:
    """Format a number as dollars with two decimals, e.g. 113.97 → '$113.97'."""
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


@app.template_filter("num")
def number_filter(value: Any, decimals: int = 0) -> str:
    """Format a number with thousands separators."""
    try:
        return f"{float(value):,.{int(decimals)}f}"
    except (TypeError, ValueError):
        return "—"


@app.template_filter("signed_currency")
def signed_currency_filter(value: Any) -> str:
    """Format a signed dollar delta, e.g. 12500 → '+$12,500'."""
    try:
        amount = float(value)
        sign = "+" if amount >= 0 else "−"
        return f"{sign}${abs(amount):,.0f}"
    except (TypeError, ValueError):
        return "—"


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------
def _artifacts_available() -> bool:
    return Path(config.MODEL_PATH).exists() and Path(config.METRICS_PATH).exists()


@app.context_processor
def inject_globals() -> Dict[str, Any]:
    """Make dataset metadata and model status available to every template."""
    status = {
        "model_ready": _artifacts_available(),
        "dataset": config.DATASET_METADATA,
    }
    return dict(app_globals=status)


def _form_defaults() -> Dict[str, Any]:
    """
    Sensible, dataset-grounded defaults for the prediction form.

    Any value supplied as a query parameter (for example when arriving from
    "Edit property details" on the result page) overrides the default, as long as
    it is a value the form can actually offer.
    """
    stats = _safe_metrics().get("dataset_statistics", {})
    medians = _safe_metrics().get("feature_schema", {}).get("training_medians", {})

    defaults: Dict[str, Any] = {
        "location": "North Ames",
        "area_sqft": medians.get("area_sqft", 1650) or 1650,
        "lot_area_sqft": medians.get("lot_area_sqft", 9500) or 9500,
        "bedrooms": int(medians.get("bedrooms", 3) or 3),
        "bathrooms": medians.get("bathrooms", 2) or 2,
        "property_age": int(medians.get("property_age", 20) or 20),
        "floors": medians.get("floors", 1) or 1,
        "parking": "2-Car Garage",
        "property_type": "Single-Family Detached",
        "stats": stats,
    }

    # Overlay valid incoming query parameters so "Edit property details" works.
    for field in ("location", "parking", "property_type"):
        value = (request.args.get(field) or "").strip()
        if value and (
            field != "location" or value in config.NEIGHBORHOOD_MAP.values()
        ):
            defaults[field] = value

    for field in ("bedrooms", "property_age"):
        value = _safe_number(request.args.get(field))
        if value is not None:
            rules = config.VALIDATION_RULES[field]
            if rules["min"] <= value <= rules["max"]:
                defaults[field] = int(value)

    for field in ("area_sqft", "lot_area_sqft", "bathrooms", "floors"):
        value = _safe_number(request.args.get(field))
        if value is not None:
            rules = config.VALIDATION_RULES[field]
            if rules["min"] <= value <= rules["max"]:
                defaults[field] = value

    return defaults


def _safe_number(raw: Any) -> float | None:
    """Convert a query parameter to a finite float, or return None."""
    if raw is None:
        return None
    try:
        value = float(str(raw).replace(",", "").strip())
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) else None


def _safe_metrics() -> Dict[str, Any]:
    """Load metrics.json, returning an empty dict if it is missing or corrupt."""
    if not Path(config.METRICS_PATH).exists():
        return {}
    try:
        with open(config.METRICS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Could not read metrics.json: %s", exc)
        return {}


def _api_error(message: str, status: int = 400, **extra: Any) -> Tuple[Any, int]:
    payload = {"success": False, "error": message}
    payload.update(extra)
    return jsonify(payload), status


# --------------------------------------------------------------------------
# Page routes
# --------------------------------------------------------------------------
@app.route("/")
def index() -> str:
    metrics = _safe_metrics()
    stats = metrics.get("dataset_statistics", {})
    rf_metrics = metrics.get("models", {}).get("random_forest", {}).get("test_metrics", {})
    return render_template(
        "index.html",
        active_page="home",
        stats=stats,
        rf_metrics=rf_metrics,
        model_ready=_artifacts_available(),
    )


@app.route("/predict", methods=["GET"])
def predict_page() -> str:
    return render_template(
        "predict.html",
        active_page="predict",
        defaults=_form_defaults(),
        locations=sorted(config.NEIGHBORHOOD_MAP.values()),
        parking_options=config.PARKING_OPTIONS,
        property_types=config.PROPERTY_TYPE_OPTIONS,
        floor_options=config.FLOOR_OPTIONS,
        validation_rules=config.VALIDATION_RULES,
        feature_labels=config.FEATURE_LABELS,
        model_ready=_artifacts_available(),
    )


@app.route("/result")
def result_page() -> str:
    """
    Server-rendered result page. The prediction is recomputed from the URL
    parameters so the page is shareable, bookmarkable, and never displays a
    fabricated value: if recomputation fails the user is returned to the form.
    """
    if not _artifacts_available():
        return render_template(
            "error.html",
            active_page="predict",
            title="Model not ready",
            message=(
                "The trained model has not been generated yet. "
                "Run `python -m src.train_model` from the project root, then reload this page."
            ),
        ), 503

    raw_input = {key: request.args.get(key) for key in config.ALL_FEATURES}

    if not any(raw_input.values()):
        return render_template(
            "error.html",
            active_page="predict",
            title="No property details supplied",
            message="Open the prediction form, enter the property details, and submit to see an estimate.",
        ), 400

    try:
        result = predict_price(raw_input)
    except ValueError as exc:
        return render_template(
            "error.html",
            active_page="predict",
            title="We could not validate these details",
            message=str(exc),
        ), 400
    except PredictionError as exc:
        return render_template(
            "error.html",
            active_page="predict",
            title="Prediction unavailable",
            message=str(exc),
        ), 422

    metrics = _safe_metrics()
    training_rows = int(metrics.get("data_preparation", {}).get("train_rows", 0) or 0)
    test_rows = int(metrics.get("data_preparation", {}).get("test_rows", 0) or 0)

    return render_template(
        "result.html",
        active_page="predict",
        result=result,
        dataset=config.DATASET_METADATA,
        feature_labels=config.FEATURE_LABELS,
        edit_query=request.query_string.decode("utf-8"),
        training_rows=training_rows,
        metrics_n_test=test_rows,
    )


@app.route("/dashboard")
def dashboard_page() -> str:
    """Prediction dashboard showing live activity and model performance."""
    metrics = _safe_metrics()
    try:
        summary = dashboard_analytics.build_summary(metrics)
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Could not build dashboard summary: %s", exc)
        return render_template(
            "error.html",
            active_page="dashboard",
            title="Dashboard unavailable",
            message="The dashboard could not read the prediction log. Check that "
                    "data/predictions.db is writable, then reload this page.",
        ), 500

    return render_template(
        "dashboard.html",
        active_page="dashboard",
        summary=summary,
        dataset=config.DATASET_METADATA,
        feature_labels=config.FEATURE_LABELS,
    )


@app.route("/insights")
def insights_page() -> str:
    metrics = _safe_metrics()
    if not metrics:
        return render_template(
            "error.html",
            active_page="insights",
            title="Insights unavailable",
            message=(
                "No trained-model metrics were found. Run `python -m src.train_model` "
                "to generate the dataset statistics, charts, and evaluation results."
            ),
        ), 503

    return render_template(
        "insights.html",
        active_page="insights",
        metrics=metrics,
        dataset=config.DATASET_METADATA,
        feature_labels=config.FEATURE_LABELS,
    )


# --------------------------------------------------------------------------
# API routes
# --------------------------------------------------------------------------
@app.route("/api/predict", methods=["POST"])
def api_predict() -> Tuple[Any, int]:
    """Validate submitted property details and return a real model prediction."""
    if not _artifacts_available():
        return _api_error(
            "The trained model is not available on the server. Please contact the administrator.",
            status=503,
        )

    payload = request.get_json(silent=True)
    if payload is None:
        payload = request.form.to_dict()

    if not isinstance(payload, dict) or not payload:
        return _api_error("Request body must be a non-empty JSON object.")

    # Normalise keys (accept camelCase or snake_case from the client)
    normalised: Dict[str, Any] = {}
    for key, value in payload.items():
        normalised[str(key).strip()] = value

    try:
        result = predict_price(normalised)
    except ValueError as exc:
        return _api_error(str(exc), status=400)
    except PredictionError as exc:
        return _api_error(str(exc), status=422)
    except FileNotFoundError as exc:
        logger.error("Model artifact missing: %s", exc)
        return _api_error("Model artifact is missing from the server.", status=503)
    except Exception as exc:  # pragma: no cover - defensive catch-all
        logger.exception("Unexpected prediction failure: %s", exc)
        return _api_error(
            "An unexpected error occurred while generating the estimate. "
            "Please adjust the details and try again.",
            status=500,
        )

    # Record the estimate so the dashboard reflects real served activity.
    # Failure to log must never break a valid prediction.
    try:
        prediction_store.log_prediction(
            inputs=result["input_summary"],
            predicted_price=result["predicted_price"],
            price_per_sqft=result["explanation"]["predicted_price_per_sqft"],
            model_name=result["model_name"],
            source="web",
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("Could not log prediction: %s", exc)

    logger.info(
        "Prediction served: %s %s | %s | %s",
        config.DATASET_METADATA["currency_symbol"],
        f"{result['predicted_price']:,.0f}",
        result["input_summary"].get("location"),
        result["input_summary"].get("property_type"),
    )
    return jsonify(result), 200


@app.route("/api/metrics", methods=["GET"])
def api_metrics() -> Tuple[Any, int]:
    """Return the saved evaluation metrics, dataset statistics, and feature importances."""
    metrics = _safe_metrics()
    if not metrics:
        return _api_error(
            "No evaluation metrics found. Train the model first.",
            status=404,
        )

    selected_key = metrics.get("selected_model_key", "random_forest")
    slim = {
        "success": True,
        "selected_model": metrics.get("selected_model"),
        "selection_reason": metrics.get("selection_reason"),
        "selected_test_metrics": metrics.get("models", {})
        .get(selected_key, {})
        .get("test_metrics", {}),
        "all_models": {
            key: {
                "name": value.get("name"),
                "train_metrics": value.get("train_metrics"),
                "test_metrics": value.get("test_metrics"),
            }
            for key, value in metrics.get("models", {}).items()
        },
        "feature_importances": metrics.get("feature_importances"),
        "dataset_statistics": metrics.get("dataset_statistics"),
        "data_preparation": metrics.get("data_preparation"),
        "charts": metrics.get("charts"),
        "trained_at_utc": metrics.get("trained_at_utc"),
    }
    return jsonify(slim), 200


@app.route("/api/dashboard/summary", methods=["GET"])
def api_dashboard_summary() -> Tuple[Any, int]:
    """Return the dashboard aggregations as JSON."""
    try:
        summary = dashboard_analytics.build_summary(_safe_metrics())
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Dashboard summary failed: %s", exc)
        return _api_error("Could not build the dashboard summary.", status=500)
    return jsonify({"success": True, "summary": summary}), 200


@app.route("/api/dashboard/sample", methods=["POST"])
def api_dashboard_sample() -> Tuple[Any, int]:
    """
    Run the saved model over a real sample of dataset properties and log each
    estimate. This produces genuine predictions - it does not fabricate rows.
    """
    if not _artifacts_available():
        return _api_error("The trained model is not available.", status=503)

    payload = request.get_json(silent=True) or {}
    try:
        count = int(payload.get("count", 40))
    except (TypeError, ValueError):
        count = 40
    count = max(1, min(count, 200))

    try:
        result = sample_activity.generate_sample_activity(n=count)
    except FileNotFoundError as exc:
        logger.error("Sample activity needs the processed dataset: %s", exc)
        return _api_error(
            "The processed dataset is missing. Run `python -m src.train_model` first.",
            status=500,
        )
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Sample activity failed: %s", exc)
        return _api_error("Could not generate sample activity.", status=500)

    logger.info("Logged %s sample predictions", result.get("logged"))
    return jsonify({"success": True, **result}), 200


@app.route("/api/dashboard/clear", methods=["POST"])
def api_dashboard_clear() -> Tuple[Any, int]:
    """Delete the prediction log."""
    try:
        removed = prediction_store.clear()
    except Exception as exc:  # pragma: no cover - defensive
        logger.exception("Could not clear the prediction log: %s", exc)
        return _api_error("Could not clear the prediction log.", status=500)
    logger.info("Cleared %s logged predictions", removed)
    return jsonify({"success": True, "removed": removed}), 200


@app.route("/health", methods=["GET"])
def health() -> Tuple[Any, int]:
    """Lightweight health and readiness check."""
    return jsonify(
        {
            "status": "ok" if _artifacts_available() else "model_missing",
            "model_ready": _artifacts_available(),
            "dataset": config.DATASET_METADATA["name"],
        }
    ), 200


# --------------------------------------------------------------------------
# Error handling — never leak stack traces to the user
# --------------------------------------------------------------------------
@app.errorhandler(404)
def not_found(error: HTTPException) -> Tuple[str, int]:
    return render_template(
        "error.html",
        active_page="",
        title="Page not found",
        message="The page you requested does not exist. Use the navigation above to continue.",
    ), 404


@app.errorhandler(405)
def method_not_allowed(error: HTTPException) -> Tuple[str, int]:
    return render_template(
        "error.html",
        active_page="",
        title="Method not allowed",
        message="This address does not support that type of request.",
    ), 405


@app.errorhandler(500)
def server_error(error: HTTPException) -> Tuple[str, int]:
    logger.exception("Unhandled server error: %s", error)
    return render_template(
        "error.html",
        active_page="",
        title="Something went wrong",
        message="An internal error occurred. The issue has been logged. Please try again.",
    ), 500


if __name__ == "__main__":
    if not _artifacts_available():
        logger.warning(
            "Model artifacts not found. Run `python -m src.train_model` before serving requests."
        )
    # Render (and most PaaS hosts) inject the port to bind via $PORT.
    port = int(os.getenv("PORT", "5000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
