"""
Data loading, inspection, cleaning, and Scikit-learn preprocessing pipeline
for the HomeValue House Price Prediction system.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Tuple

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

import config


def load_raw_dataset(csv_path: Path = config.RAW_DATA_PATH) -> pd.DataFrame:
    """Load the raw Ames Housing dataset from CSV."""
    if not Path(csv_path).exists():
        raise FileNotFoundError(f"Raw dataset not found at {csv_path}")
    return pd.read_csv(csv_path)


def inspect_dataset(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Inspect a DataFrame and return a structured report covering shape,
    column names, data types, missing values, duplicates, and sample rows.
    """
    missing_counts = df.isna().sum()
    missing_dict = {col: int(cnt) for col, cnt in missing_counts.items() if cnt > 0}
    return {
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "columns": list(df.columns),
        "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
        "missing_values": missing_dict,
        "total_missing_cells": int(missing_counts.sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "sample_records": df.head(5).to_dict(orient="records"),
    }


def _derive_parking_category(df: pd.DataFrame) -> pd.Series:
    """Map raw GarageType and GarageCars columns to human-readable parking categories."""
    garage_cars = pd.to_numeric(df["GarageCars"], errors="coerce").fillna(0)
    no_garage = df["GarageType"].isna() | (garage_cars <= 0)
    return pd.Series(
        np.where(
            no_garage,
            "No Garage",
            np.where(
                garage_cars >= 3,
                "3+ Car Garage",
                np.where(garage_cars == 2, "2-Car Garage", "1-Car Garage"),
            ),
        ),
        index=df.index,
    )


def clean_and_prepare_dataframe(raw_df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Clean raw dataset records, remove duplicates and documented partial-sale
    anomalies, and map raw columns into the standardized feature schema.

    Note: Missing values in numerical/categorical features (such as 0-bedroom
    records converted to NaN) are intentionally retained in the cleaned table so
    that the Scikit-learn SimpleImputer fits strictly on the training split
    without data leakage.
    """
    df = raw_df.copy()
    initial_rows = len(df)

    # 1. Remove exact duplicates (excluding Id if present)
    dedup_cols = [c for c in df.columns if c != "Id"]
    duplicates_removed = int(df.duplicated(subset=dedup_cols).sum())
    df = df.drop_duplicates(subset=dedup_cols).copy()

    # Check if input is already in standardized schema or raw Ames schema
    if "SalePrice" in df.columns and "GrLivArea" in df.columns:
        # Filter invalid non-positive area or sale price
        invalid_mask = (df["GrLivArea"] <= 0) | (df["SalePrice"] <= 0)
        # Filter the 2 documented De Cock (2011) partial-construction outlier sales
        anomaly_mask = (df["GrLivArea"] > 4000) & (df["SalePrice"] < 300000)
        outliers_removed = int((invalid_mask | anomaly_mask).sum())
        df = df[~(invalid_mask | anomaly_mask)].copy()

        total_bath = (
            df["FullBath"].fillna(0)
            + 0.5 * df["HalfBath"].fillna(0)
            + df["BsmtFullBath"].fillna(0)
            + 0.5 * df["BsmtHalfBath"].fillna(0)
        )

        # Treat 0 above-grade bedrooms or 0 bathrooms as missing to be imputed on train split
        bedrooms_series = pd.to_numeric(df["BedroomAbvGr"], errors="coerce").replace(0, np.nan)
        bathrooms_series = pd.to_numeric(total_bath, errors="coerce").replace(0, np.nan)

        cleaned = pd.DataFrame(
            {
                "location": df["Neighborhood"].map(config.NEIGHBORHOOD_MAP).fillna(df["Neighborhood"]),
                "area_sqft": pd.to_numeric(df["GrLivArea"], errors="coerce").astype(float),
                "lot_area_sqft": pd.to_numeric(df["LotArea"], errors="coerce").astype(float),
                "bedrooms": bedrooms_series.astype(float),
                "bathrooms": bathrooms_series.astype(float),
                "property_age": (
                    pd.to_numeric(df["YrSold"], errors="coerce")
                    - pd.to_numeric(df["YearBuilt"], errors="coerce")
                )
                .clip(lower=0)
                .astype(float),
                "floors": df["HouseStyle"].map(config.HOUSE_STYLE_TO_FLOORS).astype(float),
                "parking": _derive_parking_category(df),
                "property_type": df["BldgType"].map(config.BLDG_TYPE_MAP).fillna(df["BldgType"]),
                "price": pd.to_numeric(df["SalePrice"], errors="coerce").astype(float),
            }
        )
    else:
        # Input is already in standardized schema
        required = set(config.ALL_FEATURES + [config.TARGET_COLUMN])
        missing_cols = required - set(df.columns)
        if missing_cols:
            raise ValueError(f"Missing required columns: {sorted(missing_cols)}")

        invalid_mask = (
            (pd.to_numeric(df["area_sqft"], errors="coerce") <= 0)
            | (pd.to_numeric(df["price"], errors="coerce") <= 0)
        )
        outliers_removed = int(invalid_mask.sum())
        cleaned = df[~invalid_mask].copy()
        for num_col in config.NUMERICAL_FEATURES + [config.TARGET_COLUMN]:
            cleaned[num_col] = pd.to_numeric(cleaned[num_col], errors="coerce").astype(float)
        cleaned["bedrooms"] = cleaned["bedrooms"].replace(0, np.nan)
        cleaned["bathrooms"] = cleaned["bathrooms"].replace(0, np.nan)

    cleaning_summary = {
        "initial_rows": initial_rows,
        "duplicates_removed": duplicates_removed,
        "anomalies_or_invalid_removed": outliers_removed,
        "final_rows": len(cleaned),
        "remaining_missing_for_pipeline_imputation": {
            col: int(cnt) for col, cnt in cleaned.isna().sum().items() if cnt > 0
        },
    }
    return cleaned.reset_index(drop=True), cleaning_summary


def build_preprocessor() -> ColumnTransformer:
    """
    Create the Scikit-learn ColumnTransformer that imputes missing values,
    scales numerical features, and one-hot encodes categorical features.
    """
    numerical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
        ]
    )

    categorical_pipeline = Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="most_frequent")),
            ("onehot", OneHotEncoder(handle_unknown="ignore", sparse_output=False)),
        ]
    )

    preprocessor = ColumnTransformer(
        transformers=[
            ("num", numerical_pipeline, config.NUMERICAL_FEATURES),
            ("cat", categorical_pipeline, config.CATEGORICAL_FEATURES),
        ],
        remainder="drop",
    )
    return preprocessor


def prepare_and_save_processed_data(
    raw_path: Path = config.RAW_DATA_PATH,
    processed_path: Path = config.PROCESSED_DATA_PATH,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run the full raw-to-processed data preparation workflow and save the result."""
    raw_df = load_raw_dataset(raw_path)
    raw_report = inspect_dataset(raw_df)
    cleaned_df, cleaning_summary = clean_and_prepare_dataframe(raw_df)

    Path(processed_path).parent.mkdir(parents=True, exist_ok=True)
    cleaned_df.to_csv(processed_path, index=False)

    full_report = {
        "raw_inspection": raw_report,
        "cleaning_summary": cleaning_summary,
        "processed_inspection": inspect_dataset(cleaned_df),
    }
    return cleaned_df, full_report


if __name__ == "__main__":
    df_clean, report = prepare_and_save_processed_data()
    print("=== Raw Dataset Inspection ===")
    print(f"Shape: {report['raw_inspection']['shape']}")
    print(f"Missing values in raw data: {report['raw_inspection']['missing_values']}")
    print("\n=== Cleaning Summary ===")
    print(report["cleaning_summary"])
    print("\n=== Processed Dataset Sample ===")
    print(df_clean.head())
