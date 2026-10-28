"""
Central configuration for the HomeValue House Price Prediction application.
Uses relative pathlib paths so the project runs cleanly on any machine.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# Data paths
DATA_DIR = BASE_DIR / "data"
RAW_DATA_PATH = DATA_DIR / "raw" / "ames_housing_raw.csv"
PROCESSED_DATA_PATH = DATA_DIR / "processed" / "house_prices_cleaned.csv"

# SQLite log of served predictions. On hosts with an ephemeral filesystem
# (such as Render's free plan) set PREDICTIONS_DB_PATH to a mounted disk,
# e.g. /var/data/predictions.db, to keep dashboard history across deploys.
PREDICTIONS_DB_PATH = Path(
    os.getenv("PREDICTIONS_DB_PATH", str(DATA_DIR / "predictions.db"))
)

# Model and evaluation artifact paths
MODELS_DIR = BASE_DIR / "models"
MODEL_PATH = MODELS_DIR / "house_price_pipeline.joblib"
BASELINE_MODEL_PATH = MODELS_DIR / "baseline_linear_pipeline.joblib"
METRICS_PATH = MODELS_DIR / "metrics.json"

# Static chart assets path
STATIC_DIR = BASE_DIR / "static"
CHARTS_DIR = STATIC_DIR / "images" / "charts"

# Reproducibility settings
RANDOM_STATE = 42
TEST_SIZE = 0.20

# Dataset metadata
DATASET_METADATA = {
    "name": "Ames Iowa Residential Housing Dataset",
    "author": "Dean De Cock (Truman State University)",
    "publication": "Journal of Statistics Education, Vol. 19, No. 3 (2011)",
    "source_url": "https://www.openml.org/d/42165",
    "license": "Public Domain / CC0 Academic Teaching & Research Dataset",
    "currency": "USD",
    "currency_symbol": "$",
    "market_region": "Ames, Iowa, United States",
    "observation_period": "2006 to 2010",
}

# Feature definitions
TARGET_COLUMN = "price"

NUMERICAL_FEATURES = [
    "area_sqft",
    "lot_area_sqft",
    "bedrooms",
    "bathrooms",
    "property_age",
    "floors",
]

CATEGORICAL_FEATURES = [
    "location",
    "parking",
    "property_type",
]

ALL_FEATURES = [
    "location",
    "area_sqft",
    "lot_area_sqft",
    "bedrooms",
    "bathrooms",
    "property_age",
    "floors",
    "parking",
    "property_type",
]

FEATURE_LABELS = {
    "location": "Neighborhood / Location",
    "area_sqft": "Living Area (sq ft)",
    "lot_area_sqft": "Lot Size (sq ft)",
    "bedrooms": "Bedrooms",
    "bathrooms": "Bathrooms",
    "property_age": "Property Age (years)",
    "floors": "Floors / Stories",
    "parking": "Parking / Garage",
    "property_type": "Property Type",
}

# Raw Ames Housing code mappings to human-readable labels
NEIGHBORHOOD_MAP = {
    "NAmes": "North Ames",
    "CollgCr": "College Creek",
    "OldTown": "Old Town",
    "Edwards": "Edwards",
    "Somerst": "Somerset",
    "Gilbert": "Gilbert",
    "NridgHt": "Northridge Heights",
    "Sawyer": "Sawyer",
    "NWAmes": "Northwest Ames",
    "SawyerW": "Sawyer West",
    "BrkSide": "Brookside",
    "Crawfor": "Crawford",
    "Mitchel": "Mitchell",
    "NoRidge": "Northridge",
    "Timber": "Timberland",
    "IDOTRR": "Iowa DOT & Rail Road",
    "ClearCr": "Clear Creek",
    "StoneBr": "Stone Brook",
    "SWISU": "South & West of ISU",
    "Blmngtn": "Bloomington Heights",
    "MeadowV": "Meadow Village",
    "BrDale": "Briardale",
    "Veenker": "Veenker",
    "NPkVill": "Northpark Villa",
    "Blueste": "Bluestem",
}

BLDG_TYPE_MAP = {
    "1Fam": "Single-Family Detached",
    "TwnhsE": "Townhouse (End Unit)",
    "Twnhs": "Townhouse (Interior)",
    "Duplex": "Duplex",
    "2fmCon": "Two-Family Conversion",
}

HOUSE_STYLE_TO_FLOORS = {
    "1Story": 1.0,
    "SFoyer": 1.0,
    "1.5Fin": 1.5,
    "1.5Unf": 1.5,
    "SLvl": 1.5,
    "2Story": 2.0,
    "2.5Fin": 2.5,
    "2.5Unf": 2.5,
}

PARKING_OPTIONS = [
    "2-Car Garage",
    "1-Car Garage",
    "3+ Car Garage",
    "No Garage",
]

PROPERTY_TYPE_OPTIONS = [
    "Single-Family Detached",
    "Townhouse (End Unit)",
    "Townhouse (Interior)",
    "Duplex",
    "Two-Family Conversion",
]

FLOOR_OPTIONS = [1.0, 1.5, 2.0, 2.5]

# Validation bounds for user form and API input
VALIDATION_RULES = {
    "area_sqft": {"min": 300.0, "max": 10000.0, "default": 1650.0, "label": "Living area (sq ft)"},
    "lot_area_sqft": {"min": 1000.0, "max": 250000.0, "default": 9500.0, "label": "Lot area (sq ft)"},
    "bedrooms": {"min": 1, "max": 10, "default": 3, "label": "Number of bedrooms"},
    "bathrooms": {"min": 1.0, "max": 8.0, "default": 2.0, "label": "Number of bathrooms"},
    "property_age": {"min": 0, "max": 160, "default": 22, "label": "Property age (years)"},
    "floors": {"min": 1.0, "max": 3.0, "default": 2.0, "label": "Number of floors"},
}
