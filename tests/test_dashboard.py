"""
Tests for the prediction-activity dashboard.

The dashboard may only report on predictions that were genuinely served by the
saved model, so these tests focus on the guarantees that make that claim safe:

- The SQLite store round-trips a logged prediction without altering it.
- With an empty log the analytics layer reports `has_data=False` and nulls
  every aggregate rather than inventing numbers to fill the charts.
- With a populated log every aggregate is recomputed from the stored rows,
  so the figures on screen match the figures in the database.
- The sample-activity generator runs the real model over real dataset rows
  (never fabricated prices) and reports how many it skipped.
- The JSON endpoints return the documented contract.

All tests write to a throwaway database in `tmp_path`; the real
`data/predictions.db` is never touched.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402
from conftest import requires_artifacts  # noqa: E402
from src import dashboard_analytics, prediction_store  # noqa: E402

REQUIRED_SUMMARY_KEYS = {
    "has_data",
    "total_predictions",
    "price",
    "price_per_sqft",
    "area",
    "age",
    "by_location",
    "by_property_type",
    "by_parking",
    "by_source",
    "timeline",
    "timeline_granularity",
    "histogram",
    "scatter",
    "recent",
    "first_at",
    "last_at",
    "vs_training_median",
    "model",
    "dataset_reference",
    "feature_importances",
}


@pytest.fixture()
def db(tmp_path):
    """An isolated, initialised prediction log."""
    path = tmp_path / "test_predictions.db"
    prediction_store.init_db(path)
    return path


def make_inputs(
    location: str = "Northridge Heights",
    area: float = 1_800.0,
    **overrides,
) -> dict:
    """A realistic property description, shaped like a form submission."""
    inputs = {
        "location": location,
        "area_sqft": area,
        "lot_area_sqft": 9_000.0,
        "bedrooms": 3,
        "bathrooms": 2.0,
        "property_age": 25,
        "floors": 2.0,
        "parking": "2-Car Garage",
        "property_type": "Single-Family Detached",
    }
    inputs.update(overrides)
    return inputs


def log_price(db, price: float, source: str = "web", **overrides) -> int:
    """Log one estimate at `price`, mirroring how app.py records a request."""
    inputs = make_inputs(**overrides)
    return prediction_store.log_prediction(
        inputs=inputs,
        predicted_price=price,
        price_per_sqft=round(price / float(inputs["area_sqft"]), 2),
        model_name="Random Forest Regressor",
        source=source,
        db_path=db,
    )


# --------------------------------------------------------------------------
# prediction_store
# --------------------------------------------------------------------------
def test_init_db_is_idempotent(db):
    prediction_store.init_db(db)
    prediction_store.init_db(db)
    assert prediction_store.count(db_path=db) == 0


def test_log_prediction_round_trips_every_field(db):
    inputs = make_inputs()
    row_id = prediction_store.log_prediction(
        inputs=inputs,
        predicted_price=180_000.0,
        price_per_sqft=100.0,
        model_name="Random Forest Regressor",
        source="web",
        db_path=db,
    )

    assert row_id >= 1
    assert prediction_store.count(db_path=db) == 1

    stored = prediction_store.get_all(db)[0]

    for key in ("location", "property_type", "parking"):
        assert stored[key] == inputs[key], f"field {key} was not stored faithfully"
    assert stored["model_name"] == "Random Forest Regressor"
    assert stored["source"] == "web"

    assert stored["predicted_price"] == pytest.approx(180_000.0)
    assert stored["area_sqft"] == pytest.approx(inputs["area_sqft"])
    assert stored["price_per_sqft"] == pytest.approx(100.0)
    assert stored["created_at"], "created_at must be populated"


def test_get_recent_returns_newest_first(db):
    for price in (100_000.0, 200_000.0, 300_000.0):
        log_price(db, price)

    recent = prediction_store.get_recent(limit=2, db_path=db)
    prices = [r["predicted_price"] for r in recent]

    assert len(recent) == 2
    assert prices == [300_000.0, 200_000.0], "most recent prediction must come first"


def test_count_and_clear(db):
    for price in (150_000.0, 250_000.0):
        log_price(db, price)

    assert prediction_store.count(db_path=db) == 2
    assert prediction_store.clear(db_path=db) == 2
    assert prediction_store.count(db_path=db) == 0


def test_helpers_tolerate_a_none_db_path(db):
    """Regression: an explicit `db_path=None` must fall back to the default."""
    prediction_store.init_db(None)  # must not raise TypeError


# --------------------------------------------------------------------------
# dashboard_analytics — empty log
# --------------------------------------------------------------------------
def test_empty_summary_reports_no_data_and_nulls_aggregates(db):
    summary = dashboard_analytics.build_summary(metrics={}, db_path=db)

    assert summary["has_data"] is False
    assert summary["total_predictions"] == 0
    assert summary["price"] is None
    assert summary["vs_training_median"] is None
    assert summary["first_at"] is None
    assert summary["last_at"] is None

    for key in ("by_location", "by_property_type", "timeline", "histogram",
                "scatter", "recent", "by_source"):
        assert summary[key] == [], f"{key} must be empty with no logged predictions"


def test_summary_contract_is_stable(db):
    summary = dashboard_analytics.build_summary(metrics={}, db_path=db)
    assert REQUIRED_SUMMARY_KEYS.issubset(summary.keys())


# --------------------------------------------------------------------------
# dashboard_analytics — populated log
# --------------------------------------------------------------------------
def test_populated_summary_matches_the_stored_rows(db):
    prices = [120_000.0, 180_000.0, 240_000.0, 300_000.0]
    for price in prices:
        log_price(db, price)

    summary = dashboard_analytics.build_summary(metrics={}, db_path=db)
    price = summary["price"]
    expected_median = sorted(prices)[1:3]
    expected_median = sum(expected_median) / 2

    assert summary["has_data"] is True
    assert summary["total_predictions"] == len(prices)
    assert price["min"] == pytest.approx(min(prices))
    assert price["max"] == pytest.approx(max(prices))
    assert price["median"] == pytest.approx(expected_median)
    assert price["mean"] == pytest.approx(sum(prices) / len(prices))
    assert price["min"] <= price["q25"] <= price["median"] <= price["q75"] <= price["max"]

    # histogram counts must add up to every logged prediction
    assert sum(bucket["count"] for bucket in summary["histogram"]) == len(prices)
    # timeline counts must add up to every logged prediction
    assert sum(day["count"] for day in summary["timeline"]) == len(prices)
    assert summary["first_at"] and summary["last_at"]


def test_by_location_median_is_computed_from_the_rows(db):
    for price in (100_000.0, 200_000.0, 300_000.0):
        log_price(db, price, location="Old Town")
    log_price(db, 900_000.0, location="Northridge")

    summary = dashboard_analytics.build_summary(metrics={}, db_path=db)
    by_location = {row["name"]: row for row in summary["by_location"]}

    assert by_location["Old Town"]["count"] == 3
    assert by_location["Old Town"]["median"] == pytest.approx(200_000.0)
    assert by_location["Northridge"]["median"] == pytest.approx(900_000.0)


def test_source_mix_distinguishes_web_from_sample_runs(db):
    log_price(db, 180_000.0, source="web")
    log_price(db, 190_000.0, source="sample")
    log_price(db, 200_000.0, source="sample")

    summary = dashboard_analytics.build_summary(metrics={}, db_path=db)
    mix = {row["name"]: row["count"] for row in summary["by_source"]}

    assert mix == {"sample": 2, "web": 1}


def test_recent_is_capped_at_twelve(db):
    for i in range(20):
        log_price(db, 100_000.0 + i)

    summary = dashboard_analytics.build_summary(metrics={}, db_path=db)
    assert len(summary["recent"]) == 12
    # newest first
    assert summary["recent"][0]["predicted_price"] > summary["recent"][-1]["predicted_price"]


# --------------------------------------------------------------------------
# sample activity
# --------------------------------------------------------------------------
@requires_artifacts
def test_sample_activity_runs_the_real_model_over_real_properties(db):
    from src import sample_activity

    result = sample_activity.generate_sample_activity(n=5, db_path=db)

    assert result["requested"] == 5
    assert result["logged"] + result["skipped"] == 5
    assert result["logged"] >= 1, "the model should score at least some real properties"
    assert result["source"] == "sample"

    rows = prediction_store.get_all(db)
    assert len(rows) == result["logged"]
    assert all(r["source"] == "sample" for r in rows)
    assert all(r["predicted_price"] > 0 for r in rows)

    if result["logged"]:
        assert result["median_price"] > 0


@requires_artifacts
def test_sample_activity_rejects_an_out_of_range_count(db):
    from src import sample_activity

    with pytest.raises(ValueError):
        sample_activity.generate_sample_activity(n=0, db_path=db)
    with pytest.raises(ValueError):
        sample_activity.generate_sample_activity(n=10_000, db_path=db)


# --------------------------------------------------------------------------
# HTTP endpoints
# --------------------------------------------------------------------------
@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A test client whose endpoints read and write a throwaway database.

    Repointing the module default keeps every route isolated without having to
    patch each one, so these tests can never touch data/predictions.db.
    """
    from app import app as flask_app

    isolated = tmp_path / "route_predictions.db"
    prediction_store.init_db(isolated)

    monkeypatch.setattr(prediction_store, "DEFAULT_DB_PATH", isolated)

    flask_app.config["TESTING"] = True
    with flask_app.test_client() as test_client:
        yield test_client, isolated


def test_dashboard_route_returns_200(client):
    test_client, _ = client
    response = test_client.get("/dashboard")
    assert response.status_code == 200
    assert b"Insights from your predictions" in response.data


def test_dashboard_shows_the_empty_state_when_nothing_is_logged(client):
    test_client, _ = client
    response = test_client.get("/dashboard")
    body = response.get_data(as_text=True)
    assert "No predictions recorded yet" in body


def test_summary_endpoint_returns_the_documented_contract(client):
    test_client, _ = client
    payload = test_client.get("/api/dashboard/summary").get_json()

    assert payload["success"] is True
    assert REQUIRED_SUMMARY_KEYS.issubset(payload["summary"].keys())
    assert payload["summary"]["has_data"] is False


def test_a_served_prediction_appears_in_the_summary(client):
    test_client, isolated = client
    log_price(isolated, 222_222.0)

    payload = test_client.get("/api/dashboard/summary").get_json()["summary"]

    assert payload["has_data"] is True
    assert payload["total_predictions"] == 1
    assert payload["price"]["median"] == pytest.approx(222_222.0)


def test_summary_endpoint_rejects_unknown_methods(client):
    test_client, _ = client
    assert test_client.post("/api/dashboard/summary").status_code == 405


def test_clear_endpoint_empties_the_log(client):
    test_client, isolated = client
    log_price(isolated, 180_000.0)

    payload = test_client.post("/api/dashboard/clear").get_json()

    assert payload["success"] is True
    assert payload["removed"] == 1
    assert prediction_store.count(db_path=isolated) == 0


@requires_artifacts
def test_sample_endpoint_logs_real_model_runs(client):
    test_client, isolated = client
    payload = test_client.post(
        "/api/dashboard/sample", data=json.dumps({"count": 3}),
        content_type="application/json",
    ).get_json()

    assert payload["success"] is True
    assert payload["logged"] >= 1
    assert payload["source"] == "sample"
    assert prediction_store.count(db_path=isolated) == payload["logged"]


def test_sample_endpoint_clamps_the_requested_count(client):
    test_client, _ = client
    payload = test_client.post(
        "/api/dashboard/sample", data=json.dumps({"count": 99_999}),
        content_type="application/json",
    ).get_json()

    # clamped to the documented ceiling rather than rejected outright
    assert payload["requested"] <= 200
