"""
Reproducible model training script for the HomeValue House Price Prediction system.
Trains and compares a Linear Regression baseline and a Random Forest Regressor,
selects the best model based on held-out test metrics, saves the fitted pipeline
with Joblib, writes evaluation metrics to JSON, and generates analytical charts.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict

import joblib
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

import config
from src.data_preprocessing import build_preprocessor, prepare_and_save_processed_data
from src.evaluate_model import (
    compute_dataset_statistics,
    compute_regression_metrics,
    extract_feature_importances,
    generate_all_charts,
)


def train_and_evaluate(
    raw_path: Path = config.RAW_DATA_PATH,
    processed_path: Path = config.PROCESSED_DATA_PATH,
    model_path: Path = config.MODEL_PATH,
    baseline_model_path: Path = config.BASELINE_MODEL_PATH,
    metrics_path: Path = config.METRICS_PATH,
    charts_dir: Path = config.CHARTS_DIR,
) -> Dict[str, Any]:
    """Execute the end-to-end training, evaluation, and artifact persistence workflow."""
    # Step 1 & 2: Load, inspect, clean, and save processed dataset
    cleaned_df, prep_report = prepare_and_save_processed_data(raw_path, processed_path)

    X = cleaned_df[config.ALL_FEATURES].copy()
    y = cleaned_df[config.TARGET_COLUMN].copy()

    # Step 3: Reproducible train/test split (fitting preprocessors ONLY on X_train)
    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=config.TEST_SIZE,
        random_state=config.RANDOM_STATE,
    )

    # Candidate 1: Linear Regression Baseline
    linear_pipeline = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("model", LinearRegression()),
        ]
    )
    linear_pipeline.fit(X_train, y_train)
    lr_train_preds = linear_pipeline.predict(X_train)
    lr_test_preds = linear_pipeline.predict(X_test)

    lr_train_metrics = compute_regression_metrics(y_train.to_numpy(), lr_train_preds)
    lr_test_metrics = compute_regression_metrics(y_test.to_numpy(), lr_test_preds)

    # Candidate 2: Random Forest Regressor
    rf_params = {
        "n_estimators": 300,
        "max_depth": 18,
        "min_samples_split": 4,
        "min_samples_leaf": 1,
        "random_state": config.RANDOM_STATE,
        "n_jobs": -1,
    }
    rf_pipeline = Pipeline(
        steps=[
            ("preprocessor", build_preprocessor()),
            ("model", RandomForestRegressor(**rf_params)),
        ]
    )
    rf_pipeline.fit(X_train, y_train)
    rf_train_preds = rf_pipeline.predict(X_train)
    rf_test_preds = rf_pipeline.predict(X_test)

    rf_train_metrics = compute_regression_metrics(y_train.to_numpy(), rf_train_preds)
    rf_test_metrics = compute_regression_metrics(y_test.to_numpy(), rf_test_preds)

    # Step 4: Model Selection based on held-out test set RMSE and R²
    if rf_test_metrics["rmse"] <= lr_test_metrics["rmse"]:
        selected_model_name = "Random Forest Regressor"
        selected_model_key = "random_forest"
        selected_pipeline = rf_pipeline
        selection_reason = (
            f"Random Forest Regressor achieved lower held-out test error "
            f"(RMSE ${rf_test_metrics['rmse']:,.2f} vs. ${lr_test_metrics['rmse']:,.2f}, "
            f"MAE ${rf_test_metrics['mae']:,.2f} vs. ${lr_test_metrics['mae']:,.2f}) "
            f"and higher explained variance (R² {rf_test_metrics['r2']:.4f} vs. {lr_test_metrics['r2']:.4f})."
        )
    else:
        selected_model_name = "Linear Regression"
        selected_model_key = "linear_regression"
        selected_pipeline = linear_pipeline
        selection_reason = "Linear Regression achieved lower test RMSE on the held-out split."

    # Step 5: Feature Importance & Dataset Analytics
    feature_importances = extract_feature_importances(rf_pipeline, X_test, y_test)
    dataset_stats = compute_dataset_statistics(cleaned_df)
    chart_paths = generate_all_charts(
        df=cleaned_df,
        feature_importances=feature_importances,
        y_test=y_test.to_numpy(),
        rf_preds=rf_test_preds,
        lr_preds=lr_test_preds,
        charts_dir=charts_dir,
    )

    # Record training medians and known categories for inference-time context
    training_medians = {
        col: round(float(X_train[col].median()), 2) for col in config.NUMERICAL_FEATURES
    }
    known_categories = {
        col: sorted([str(v) for v in X_train[col].dropna().unique()])
        for col in config.CATEGORICAL_FEATURES
    }

    metadata_bundle = {
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "selected_model": selected_model_name,
        "selected_model_key": selected_model_key,
        "selection_reason": selection_reason,
        "dataset_metadata": config.DATASET_METADATA,
        "data_preparation": {
            "raw_shape": prep_report["raw_inspection"]["shape"],
            "raw_missing_values": prep_report["raw_inspection"]["missing_values"],
            "cleaning_summary": prep_report["cleaning_summary"],
            "train_rows": int(len(X_train)),
            "test_rows": int(len(X_test)),
            "test_split_ratio": config.TEST_SIZE,
            "random_state": config.RANDOM_STATE,
        },
        "feature_schema": {
            "all_features": config.ALL_FEATURES,
            "numerical_features": config.NUMERICAL_FEATURES,
            "categorical_features": config.CATEGORICAL_FEATURES,
            "target_column": config.TARGET_COLUMN,
            "feature_labels": config.FEATURE_LABELS,
            "training_medians": training_medians,
            "known_categories": known_categories,
        },
        "models": {
            "linear_regression": {
                "name": "Linear Regression (Baseline)",
                "train_metrics": lr_train_metrics,
                "test_metrics": lr_test_metrics,
            },
            "random_forest": {
                "name": "Random Forest Regressor",
                "hyperparameters": rf_params,
                "train_metrics": rf_train_metrics,
                "test_metrics": rf_test_metrics,
            },
        },
        "feature_importances": feature_importances,
        "dataset_statistics": dataset_stats,
        "charts": chart_paths,
    }

    # Attach metadata directly to the pipeline object and save via Joblib
    selected_pipeline.metadata_ = metadata_bundle
    Path(model_path).parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(selected_pipeline, model_path)
    joblib.dump(linear_pipeline, baseline_model_path)

    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metadata_bundle, f, indent=2)

    return metadata_bundle


if __name__ == "__main__":
    summary = train_and_evaluate()
    print("=== Model Training & Evaluation Complete ===")
    print(f"Selected Model: {summary['selected_model']}")
    print(f"Reason: {summary['selection_reason']}")
    print("\n--- Held-Out Test Metrics ---")
    for key, m in summary["models"].items():
        tm = m["test_metrics"]
        print(f"  {m['name']}: MAE=${tm['mae']:,.2f} | RMSE=${tm['rmse']:,.2f} | R²={tm['r2']:.4f}")
    print("\n--- Top Global Feature Importances (Random Forest) ---")
    for item in summary["feature_importances"][:5]:
        print(
            f"  {item['label']}: {item['importance_pct']:.1f}% "
            f"(Permutation: {item['permutation_importance_pct']:.1f}%)"
        )
