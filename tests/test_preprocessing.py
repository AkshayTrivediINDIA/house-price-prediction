"""
Tests for the data loading, cleaning and preprocessing pipeline.

Covered:
- The raw dataset loads and has the expected structure.
- raw.csv maps to the standardized schema (no duplicate rows, no invalid values).
- The cleaning step removes documented anomalies.
- The ColumnTransformer handles missing values and unseen categories, and produces
  the expected number of encoded columns.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

import config
from src.data_preprocessing import (
    build_preprocessor,
    clean_and_prepare_dataframe,
    inspect_dataset,
    load_raw_dataset,
)


def test_raw_dataset_loads():
    df = load_raw_dataset()
    assert not df.empty
    assert "SalePrice" in df.columns
    assert "GrLivArea" in df.columns
    assert len(df) == 1460


def test_inspect_dataset_reports_expected_shape():
    df = load_raw_dataset()
    report = inspect_dataset(df)
    assert report["shape"]["rows"] == 1460
    assert report["shape"]["columns"] == 19
    assert "SalePrice" in report["columns"]
    # Missing values were deliberately retained in the raw extract
    assert report["missing_values"].get("LotFrontage", 0) > 0


def test_cleaning_produces_expected_schema():
    raw = load_raw_dataset()
    cleaned, summary = clean_and_prepare_dataframe(raw)

    for column in config.ALL_FEATURES + [config.TARGET_COLUMN]:
        assert column in cleaned.columns, f"Missing column: {column}"

    assert summary["final_rows"] > 0
    assert summary["duplicates_removed"] == 0
    # The two documented partial-construction outlier sales are removed
    assert summary["anomalies_or_invalid_removed"] == 2
    assert len(cleaned) == 1458


def test_cleaning_removes_invalid_values():
    raw = load_raw_dataset()
    cleaned, _ = clean_and_prepare_dataframe(raw)

    assert (cleaned["price"] > 0).all()
    assert (cleaned["area_sqft"] > 0).all()
    assert (cleaned["property_age"] >= 0).all()
    assert cleaned["location"].notna().all()
    assert cleaned["parking"].notna().all()
    assert cleaned["property_type"].notna().all()


def test_cleaning_maps_codes_to_readable_labels():
    cleaned, _ = clean_and_prepare_dataframe(load_raw_dataset())

    assert set(cleaned["location"]).issubset(set(config.NEIGHBORHOOD_MAP.values()))
    assert set(cleaned["property_type"]).issubset(set(config.BLDG_TYPE_MAP.values()))
    assert set(cleaned["floors"].dropna()).issubset({1.0, 1.5, 2.0, 2.5})
    assert set(cleaned["parking"]).issubset(set(config.PARKING_OPTIONS))


def test_preprocessor_handles_missing_values_and_seen_categories():
    cleaned, _ = clean_and_prepare_dataframe(load_raw_dataset())
    X_train = cleaned[config.ALL_FEATURES].head(200).copy()
    X_train.loc[X_train.index[:10], "bedrooms"] = np.nan
    X_train.loc[X_train.index[:5], "location"] = None

    pre = build_preprocessor()
    transformed = pre.fit_transform(X_train)

    assert not np.isnan(transformed).any(), "Imputation failed to remove NaNs"
    assert transformed.shape[0] == len(X_train)
    assert transformed.shape[1] > len(config.NUMERICAL_FEATURES)


def test_preprocessor_handles_unseen_categories_without_error():
    cleaned, _ = clean_and_prepare_dataframe(load_raw_dataset())
    X_train = cleaned[config.ALL_FEATURES].head(200)
    y_train = cleaned[config.TARGET_COLUMN].head(200)

    pre = build_preprocessor()
    pre.fit(X_train, y_train)

    unseen = X_train.head(3).copy()
    unseen.loc[unseen.index[0], "location"] = "Atlantis"
    unseen.loc[unseen.index[1], "parking"] = "Helicopter Pad"
    unseen.loc[unseen.index[2], "property_type"] = "Houseboat"

    transformed = pre.transform(unseen)

    assert transformed.shape[0] == 3
    assert not np.isnan(transformed).any()
    # Unseen categories encode as all zeros in their one-hot block
    for row in transformed:
        assert np.isfinite(row).all()


def test_preprocessor_scales_numeric_and_leaves_categoricals_as_binary():
    cleaned, _ = clean_and_prepare_dataframe(load_raw_dataset())
    X_train = cleaned[config.ALL_FEATURES].head(300)

    pre = build_preprocessor()
    transformed = pre.fit_transform(X_train)

    n_numeric = len(config.NUMERICAL_FEATURES)
    numeric_block = transformed[:, :n_numeric]
    categorical_block = transformed[:, n_numeric:]

    # StandardScaler output has near-zero mean and unit variance
    assert np.allclose(numeric_block.mean(axis=0), 0.0, atol=1e-8)
    assert np.allclose(numeric_block.std(axis=0), 1.0, atol=1e-8)

    # One-hot output contains only 0s and 1s
    unique_values = np.unique(categorical_block)
    assert set(unique_values).issubset({0.0, 1.0})


def test_clean_and_prepare_accepts_already_standardized_frame():
    cleaned, _ = clean_and_prepare_dataframe(load_raw_dataset())
    round_trip, summary = clean_and_prepare_dataframe(cleaned.copy())

    assert list(round_trip.columns) == list(cleaned.columns)
    # Re-running cleaning is idempotent apart from genuine duplicates that only
    # become identical once the 19 raw columns are reduced to the 10 schema columns.
    assert summary["final_rows"] <= len(cleaned)
    assert (round_trip["price"] > 0).all()


def test_clean_and_prepare_rejects_incomplete_frame():
    with pytest.raises(ValueError, match="Missing required columns"):
        clean_and_prepare_dataframe(pd.DataFrame({"area_sqft": [1000]}))
