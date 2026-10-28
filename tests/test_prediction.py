"""
Tests for inference, the Flask routes and the prediction API.

Covered:
- The saved Joblib pipeline loads and carries its metadata.
- Valid inputs produce a finite, positive, numeric prediction.
- Invalid, missing and out-of-range inputs are rejected with clear errors.
- Unseen categorical values are handled gracefully.
- Predictions are deterministic and respond sensibly to larger properties.
- Every page route returns 200 and the API returns consistent JSON.
"""

from __future__ import annotations

import json
import math

import pandas as pd
import pytest

import config
from conftest import requires_artifacts
from src.predict import load_artifacts, predict_price, validate_and_convert_inputs


# ---------------------------------------------------------------------------
# Artifact loading
# ---------------------------------------------------------------------------
@requires_artifacts
def test_saved_model_loads_successfully():
    pipeline, metadata = load_artifacts()
    assert pipeline is not None
    assert hasattr(pipeline, "predict")
    assert metadata["selected_model"]
    assert set(metadata["feature_schema"]["all_features"]) == set(config.ALL_FEATURES)


@requires_artifacts
def test_metrics_file_contains_real_measured_values():
    with open(config.METRICS_PATH, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    rf = metrics["models"]["random_forest"]["test_metrics"]
    lr = metrics["models"]["linear_regression"]["test_metrics"]

    for model_metrics in (rf, lr):
        assert model_metrics["mae"] > 0
        assert model_metrics["rmse"] > 0
        assert model_metrics["rmse"] >= model_metrics["mae"]
        assert 0.0 < model_metrics["r2"] <= 1.0

    # The selected model must be the one with the lower test RMSE
    selected = metrics["selected_model_key"]
    assert metrics["models"][selected]["test_metrics"]["rmse"] == min(rf["rmse"], lr["rmse"])


@requires_artifacts
def test_training_and_test_rows_are_reported():
    with open(config.METRICS_PATH, "r", encoding="utf-8") as f:
        metrics = json.load(f)

    prep = metrics["data_preparation"]
    assert prep["train_rows"] + prep["test_rows"] == prep["cleaning_summary"]["final_rows"]
    assert prep["test_rows"] < prep["train_rows"]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------
@requires_artifacts
def test_valid_input_converts_to_expected_schema(sample_input):
    X, warnings = validate_and_convert_inputs(sample_input)

    assert isinstance(X, pd.DataFrame)
    assert list(X.columns) == config.ALL_FEATURES
    assert len(X) == 1
    assert warnings == []


@requires_artifacts
def test_missing_required_field_raises_error():
    with pytest.raises(ValueError, match="required"):
        validate_and_convert_inputs({"location": "North Ames"})


@requires_artifacts
def test_out_of_range_values_raise_error(sample_input):
    bad = dict(sample_input, area_sqft=10)
    with pytest.raises(ValueError, match="must be between"):
        validate_and_convert_inputs(bad)


@requires_artifacts
def test_non_numeric_values_raise_error(sample_input):
    bad = dict(sample_input, bedrooms="many")
    with pytest.raises(ValueError, match="must be a number"):
        validate_and_convert_inputs(bad)


@requires_artifacts
def test_unknown_location_is_rejected(sample_input):
    bad = dict(sample_input, location="Atlantis")
    with pytest.raises(ValueError, match="not one of the neighborhoods"):
        validate_and_convert_inputs(bad)


@requires_artifacts
def test_unseen_parking_and_property_type_warn_but_pass(sample_input):
    modified = dict(sample_input, parking="Helicopter Pad", property_type="Houseboat")
    X, warnings = validate_and_convert_inputs(modified)

    assert len(warnings) == 2
    assert X.at[0, "parking"] == "Helicopter Pad"


@requires_artifacts
def test_lot_area_smaller_than_living_area_is_rejected(sample_input):
    bad = dict(sample_input, area_sqft=3000, lot_area_sqft=2000)
    with pytest.raises(ValueError, match="Lot area cannot be smaller"):
        validate_and_convert_inputs(bad)


@requires_artifacts
def test_implausible_area_for_bedroom_count_is_rejected(sample_input):
    bad = dict(sample_input, bedrooms=8, area_sqft=400)
    with pytest.raises(ValueError, match="unrealistically small"):
        validate_and_convert_inputs(bad)


@requires_artifacts
def test_comma_separated_numbers_are_accepted(sample_input):
    modified = dict(sample_input, area_sqft="2,100", lot_area_sqft="12,000")
    X, _ = validate_and_convert_inputs(modified)
    assert X.at[0, "area_sqft"] == 2100.0


@requires_artifacts
def test_string_numbers_are_accepted(sample_input):
    modified = dict(sample_input, bedrooms="3", property_age="10", floors="2", bathrooms="2")
    X, _ = validate_and_convert_inputs(modified)
    assert int(X.at[0, "bedrooms"]) == 3
    assert int(X.at[0, "property_age"]) == 10


# ---------------------------------------------------------------------------
# Prediction behaviour
# ---------------------------------------------------------------------------
@requires_artifacts
def test_prediction_is_numeric_finite_and_positive(sample_input):
    result = predict_price(sample_input)
    price = result["predicted_price"]

    assert isinstance(price, float)
    assert math.isfinite(price)
    assert price > 0
    assert result["success"] is True


@requires_artifacts
def test_prediction_is_deterministic(sample_input):
    first = predict_price(sample_input)["predicted_price"]
    second = predict_price(sample_input)["predicted_price"]
    assert first == second


@requires_artifacts
def test_larger_area_predicts_higher_price(sample_input):
    base = predict_price(sample_input)["predicted_price"]
    larger = predict_price(dict(sample_input, area_sqft=3000))["predicted_price"]
    assert larger > base


@requires_artifacts
def test_newer_property_predicts_higher_than_much_older(sample_input):
    new = predict_price(dict(sample_input, property_age=2))["predicted_price"]
    old = predict_price(dict(sample_input, property_age=110))["predicted_price"]
    assert new > old


@requires_artifacts
def test_result_contains_expected_explanation_structure(sample_input):
    result = predict_price(sample_input)

    assert result["currency"] == "USD"
    assert result["model_metrics"]["r2"] > 0
    assert set(result["input_summary"].keys()) == set(config.ALL_FEATURES)
    assert "disclaimer" in result and len(result["disclaimer"]) > 50

    explanation = result["explanation"]
    assert explanation["predicted_price_per_sqft"] > 0
    assert explanation["market_median_price"] > 0
    assert len(explanation["sensitivity"]) > 0
    assert len(explanation["top_global_features"]) == 3

    for item in explanation["sensitivity"]:
        assert math.isfinite(item["price_change"])


@requires_artifacts
def test_price_per_sqft_matches_prediction(sample_input):
    result = predict_price(sample_input)
    expected = result["predicted_price"] / sample_input["area_sqft"]
    assert abs(result["explanation"]["predicted_price_per_sqft"] - expected) < 0.01


@requires_artifacts
def test_unseen_categories_are_flagged_in_result(sample_input):
    modified = dict(sample_input, parking="Helicopter Pad")
    result = predict_price(modified)
    assert "parking" in result["unseen_categories"]
    assert result["predicted_price"] > 0


@requires_artifacts
def test_prediction_with_all_numerics_as_none_raises():
    with pytest.raises(ValueError):
        predict_price({"location": "North Ames", "parking": "No Garage",
                       "property_type": "Duplex"})


@requires_artifacts
def test_batch_prediction_matches_single_prediction(sample_input):
    from src.predict import predict_from_dataframe

    X, _ = validate_and_convert_inputs(sample_input)
    batch = predict_from_dataframe(X)
    single = predict_price(sample_input)["predicted_price"]
    assert abs(float(batch[0]) - single) < 0.01


# ---------------------------------------------------------------------------
# Flask application routes
# ---------------------------------------------------------------------------
@pytest.fixture()
def client():
    import app as flask_app

    flask_app.app.config["TESTING"] = True
    with flask_app.app.test_client() as test_client:
        yield test_client


def test_home_page_returns_200(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Estimate Your Home" in response.data


def test_predict_page_returns_200(client):
    response = client.get("/predict")
    assert response.status_code == 200
    assert b"Predict Price" in response.data


def test_insights_page_returns_200(client):
    response = client.get("/insights")
    assert response.status_code == 200


def test_unknown_route_returns_404(client):
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert b"Page not found" in response.data


def test_all_navigation_links_resolve(client):
    for route in ["/", "/predict", "/insights"]:
        assert client.get(route).status_code == 200


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.get_json()
    assert "model_ready" in payload


@requires_artifacts
def test_api_metrics_returns_consistent_payload(client):
    response = client.get("/api/metrics")
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["selected_model"]
    assert "mae" in payload["selected_test_metrics"]
    assert "rmse" in payload["selected_test_metrics"]
    assert "r2" in payload["selected_test_metrics"]
    assert len(payload["feature_importances"]) == len(config.ALL_FEATURES)


@requires_artifacts
def test_api_predict_valid_request(client, sample_input):
    response = client.post("/api/predict", json=sample_input)
    assert response.status_code == 200

    payload = response.get_json()
    assert payload["success"] is True
    assert payload["predicted_price"] > 0


@requires_artifacts
def test_api_predict_invalid_request_returns_400(client):
    response = client.post("/api/predict", json={"location": "Atlantis"})
    assert response.status_code == 400

    payload = response.get_json()
    assert payload["success"] is False
    assert "error" in payload


@requires_artifacts
def test_api_predict_empty_body_returns_400(client):
    response = client.post("/api/predict", json={})
    assert response.status_code == 400


@requires_artifacts
def test_api_predict_no_json_returns_400(client):
    response = client.post("/api/predict", data="not json",
                           content_type="text/plain")
    assert response.status_code == 400


@requires_artifacts
def test_api_predict_accepts_form_encoded_body(client, sample_input):
    response = client.post("/api/predict", data=sample_input)
    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_api_predict_rejects_get_method(client):
    response = client.get("/api/predict")
    assert response.status_code == 405


@requires_artifacts
def test_result_page_renders_for_valid_query(client, sample_input):
    response = client.get("/result", query_string=sample_input)
    assert response.status_code == 200
    assert b"Estimated market value" in response.data


@requires_artifacts
def test_result_page_rejects_invalid_query(client):
    response = client.get("/result", query_string={"location": "Atlantis"})
    assert response.status_code == 400
    assert b"could not validate" in response.data


def test_result_page_without_parameters_returns_400(client):
    response = client.get("/result")
    assert response.status_code == 400
    assert b"No property details supplied" in response.data


@requires_artifacts
def test_no_stack_trace_exposed_on_bad_input(client):
    response = client.post("/api/predict", json={"location": "Atlantis", "area_sqft": -5})
    body = response.get_data(as_text=True)
    assert "Traceback" not in body
    assert "File \"" not in body
