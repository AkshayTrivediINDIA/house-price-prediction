# Training dataset — provenance, licence and format

This folder holds the exact data the House Price Prediction System is trained on,
in both its raw and model-ready form, plus a script that rebuilds it from the
public source.

| File | Rows × Cols | What it is |
| --- | --- | --- |
| `house_prices_cleaned.csv` | 1,458 × 10 | **The required format.** The model-ready schema — feed this straight to the trainer. |
| `ames_housing_raw.csv` | 1,460 × 19 | The narrow extract taken from the public source, before cleaning. |
| `fetch_dataset.py` | — | Re-downloads the source and rebuilds the cleaned file byte-for-byte. |

---

## 1. Where the dataset came from

The data was **not** downloaded manually and is **not** a private or synthetic
file. It is pulled programmatically from OpenML the first time the project is
set up:

```python
from sklearn.datasets import fetch_openml
ames = fetch_openml(name="house_prices", as_frame=True, parser="auto").frame
```

| Property | Value |
| --- | --- |
| Dataset | Ames Iowa Residential Housing Dataset |
| OpenML ID | [42165](https://www.openml.org/d/42165) |
| Compiled by | Dean De Cock, Truman State University |
| Published | *Journal of Statistics Education*, Vol. 19, No. 3 (2011) |
| Upstream home | Kaggle "House Prices — Advanced Regression Techniques" |
| Market region | Ames, Iowa, United States |
| Observation period | 2006 – 2010 |
| Currency | USD |
| Licence | Public domain / CC0 — compiled for teaching and research, distributed for unrestricted academic use |

`fetch_openml` downloads once and caches locally, so there is no manual download
step and no committed binary data file. Deleting the cached copy and re-running
`fetch_dataset.py` re-downloads from OpenML and rebuilds everything.

**Why this one:** it is a real, peer-reviewed, per-property dataset with the
exact fields the application needs (living area, lot size, bedrooms, bathrooms,
age, storeys, garage, building type, neighbourhood). Two alternatives were
checked and rejected — the California housing dataset (census-block medians, no
per-property bedroom or age counts) and the Boston housing dataset (known
ethical problems with its constructed variable).

---

## 2. The required format

`house_prices_cleaned.csv` is the schema the model trains on and the web form
collects. Ten columns, one row per property, header row included, UTF-8, comma
separated.

| # | Column | Type | Description | Example |
| --- | --- | --- | --- | --- |
| 1 | `location` | string | Neighbourhood name (25 values) | `College Creek` |
| 2 | `area_sqft` | float | Above-grade living area, sq ft | `1710.0` |
| 3 | `lot_area_sqft` | float | Lot size, sq ft | `8450.0` |
| 4 | `bedrooms` | float | Bedrooms above grade | `3.0` |
| 5 | `bathrooms` | float | Total bathrooms (half bath = 0.5, basement included) | `3.5` |
| 6 | `property_age` | float | Age in years **at the point of sale**, not today | `5.0` |
| 7 | `floors` | float | Storeys — `1.0`, `1.5`, `2.0` or `2.5` | `2.0` |
| 8 | `parking` | string | One of 4 values (below) | `2-Car Garage` |
| 9 | `property_type` | string | One of 5 values (below) | `Single-Family Detached` |
| 10 | `price` | float | **Target.** Sale price in USD | `208500.0` |

### Allowed categorical values

`parking` — `No Garage`, `1-Car Garage`, `2-Car Garage`, `3+ Car Garage`

`property_type` — `Single-Family Detached`, `Two-Family Conversion`, `Duplex`,
`Townhouse (End Unit)`, `Townhouse (Interior)`

`location` — 25 neighbourhoods: Bloomington Heights, Bluestem, Briardale,
Brookside, Clear Creek, College Creek, Crawford, Edwards, Gilbert,
Iowa DOT & Rail Road, Meadow Village, Mitchell, North Ames, Northpark Villa,
Northridge, Northridge Heights, Northwest Ames, Old Town, Sawyer, Sawyer West,
Somerset, South & West of ISU, Stone Brook, Timberland, Veenker

### Target distribution

| Statistic | USD |
| --- | --- |
| Minimum | $34,900 |
| 25th percentile | $129,925 |
| **Median** | **$163,000** |
| Mean | $180,933 |
| 75th percentile | $214,000 |
| Maximum | $755,000 |
| Std. deviation | $79,495 |

### Data quality note

There are **6 missing values** in `bedrooms`, and they are left missing on
purpose. They are filled by a `SimpleImputer` that is fitted on the training
split only, which prevents information from the test set leaking into training.
Do not pre-fill them before training.

---

## 3. How the raw file becomes the cleaned file

`fetch_dataset.py` performs both steps and delegates the cleaning to the
project's own `src/data_preprocessing.py`, so there is no second, drifting copy
of the cleaning rules.

**Step 1 — Extract (1,460 × 19).** Keep only the 19 of the 81 available source
columns that the application actually consumes.

**Step 2 — Clean (1,458 × 10).**

| Rule | Effect |
| --- | --- |
| Drop `Id` | Carries no signal |
| Remove exact duplicates | 0 found |
| Remove non-positive area or price | 0 found |
| Remove documented partial sales | **2 rows removed** |
| Rename to the readable schema | `Neighborhood` → `location`, `GrLivArea` → `area_sqft`, etc. |

The 2 removed rows are the sales over 4,000 sq ft that sold for under $300,000.
De Cock (2011) documents both as **partial sales** — incomplete construction, not
arm's-length market transactions — so they are invalid as training data.

**Step 3 — Derive.**

| New column | Rule |
| --- | --- |
| `bathrooms` | `FullBath` + 0.5 × `HalfBath` + `BsmtFullBath` + 0.5 × `BsmtHalfBath`; a 0 result becomes missing |
| `property_age` | `YrSold` − `YearBuilt`, clipped at 0 |
| `floors` | `HouseStyle` → storeys (`SFoyer` → 1.0, `SLvl` → 1.5, etc.) |
| `parking` | `GarageCars`, with a missing garage type or 0 capacity → `No Garage` |
| `property_type` | `BldgType` → plain English |
| `location` | Neighbourhood code → plain English (`NAmes` → `North Ames`) |

A bedroom count of 0 is treated as missing rather than as a real studio, for the
same imputation reason as above.

---

## 4. Reproducing it

```bash
cd house-price-prediction
python dataset_export/fetch_dataset.py
```

Output:

```
Using existing data/raw/ames_housing_raw.csv (delete it to re-download).
  initial rows      : 1460
  duplicates removed: 0
  anomalies removed : 2
  final rows        : 1458
  missing left for the pipeline imputer: bedrooms
Wrote data/processed/house_prices_cleaned.csv  (1458, 10)
Median price: $163,000
```

Verified: this rebuilds `house_prices_cleaned.csv` **byte-for-byte identical**
to the file the shipped model was trained on.

To train the model on it:

```bash
python -m src.train_model     # writes models/house_price_pipeline.joblib + metrics.json
python app.py                 # serve on http://127.0.0.1:5000/dashboard
```

---

## 5. Using your own data instead

To retrain on a different market, supply a CSV with the same 10 columns in the
same order and the same categorical vocabularies, then run
`python -m src.train_model`. Values outside the trained ranges are rejected by
the form's validation layer rather than silently extrapolated, so update the
ranges in `config.py` to match your market.

Be aware that the figures quoted throughout the documentation — R² of 0.8676,
MAE of $19,039 and every chart — describe **this** dataset and **this** trained
model. They will change the moment you retrain.
