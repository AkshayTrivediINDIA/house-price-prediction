"""
Re-download the training dataset and rebuild the cleaned file from scratch.

The project does not ship a proprietary or manually-downloaded dataset. It pulls
the Ames Iowa housing data straight from OpenML, which is why the provenance is
verifiable: run this script and you will rebuild `house_prices_cleaned.csv`
exactly as the model saw it.

    python dataset_export/fetch_dataset.py

Requires pandas, numpy and scikit-learn (see requirements.txt).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
from sklearn.datasets import fetch_openml

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RAW_PATH = PROJECT_ROOT / "data" / "raw" / "ames_housing_raw.csv"
CLEAN_PATH = PROJECT_ROOT / "data" / "processed" / "house_prices_cleaned.csv"

# The 19 columns the application actually consumes, out of the 81 available.
RAW_COLUMNS = [
    "Id", "Neighborhood", "GrLivArea", "LotArea", "LotFrontage",
    "BedroomAbvGr", "FullBath", "HalfBath", "BsmtFullBath", "BsmtHalfBath",
    "YearBuilt", "YrSold", "HouseStyle", "GarageType", "GarageCars",
    "BldgType", "OverallQual", "OverallCond", "SalePrice",
]


def build_raw() -> pd.DataFrame:
    """Fetch the OpenML dataset and keep the columns this project uses."""
    print("Fetching 'house_prices' from OpenML (cached after the first call) ...")
    ames = fetch_openml(name="house_prices", as_frame=True, parser="auto").frame
    extract = ames[RAW_COLUMNS].copy()
    RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    extract.to_csv(RAW_PATH, index=False)
    print(f"Wrote {RAW_PATH.relative_to(PROJECT_ROOT)}  {extract.shape}")
    return extract


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """
    Apply the project's own cleaning rules to produce the 10-column schema.

    This deliberately calls the same function the training pipeline uses, so
    the file this script writes is identical to the one the model was trained
    on -- there is no second, drifting copy of the cleaning logic.
    """
    from src.data_preprocessing import clean_and_prepare_dataframe

    cleaned, report = clean_and_prepare_dataframe(raw)

    print(f"  initial rows      : {report['initial_rows']}")
    print(f"  duplicates removed: {report['duplicates_removed']}")
    print(f"  anomalies removed : {report['anomalies_or_invalid_removed']}")
    print(f"  final rows        : {report['final_rows']}")
    if report.get("remaining_missing_for_pipeline_imputation"):
        print("  missing left for the pipeline imputer: "
              + ", ".join(report["remaining_missing_for_pipeline_imputation"]))
    return cleaned


def main() -> int:
    raw = RAW_PATH.read_text() if RAW_PATH.exists() else None
    if raw is None:
        raw_df = build_raw()
    else:
        print(f"Using existing {RAW_PATH.relative_to(PROJECT_ROOT)} (delete it to re-download).")
        raw_df = pd.read_csv(RAW_PATH)

    cleaned = clean(raw_df)
    CLEAN_PATH.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(CLEAN_PATH, index=False)

    print(f"Wrote {CLEAN_PATH.relative_to(PROJECT_ROOT)}  {cleaned.shape}")
    print(f"Median price: ${cleaned['price'].median():,.0f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
