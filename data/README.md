# Data directory

## `raw/ames_housing_raw.csv`

A deliberately narrow extract of the **Ames Iowa Residential Housing Dataset**, containing only the
19 columns the application actually consumes.

| Property | Value |
| --- | --- |
| Rows | 1,460 |
| Columns | 19 |
| Target column | `SalePrice` (US dollars) |
| Author | Dean De Cock, Truman State University |
| Published | *Journal of Statistics Education*, Volume 19, Number 3 (2011) |
| Source | [OpenML dataset 42165](https://www.openml.org/d/42165) |
| Upstream home | [Kaggle: House Prices — Advanced Regression Techniques](https://www.kaggle.com/c/house-prices-advanced-regression-techniques) |
| Licence / terms | The dataset was compiled by De Cock specifically for teaching and research and is distributed for unrestricted academic use. The original Kaggle competition carried its own competition rules; this project uses the **OpenML distribution** of the data for educational purposes only and does not redistribute the full 81-column competition files. |

### How the raw file was produced

```python
from sklearn.datasets import fetch_openml

ames = fetch_openml(name="house_prices", as_frame=True, parser="auto").frame
cols = [
    "Id", "Neighborhood", "GrLivArea", "LotArea", "LotFrontage",
    "BedroomAbvGr", "FullBath", "HalfBath", "BsmtFullBath", "BsmtHalfBath",
    "YearBuilt", "YrSold", "HouseStyle", "GarageType", "GarageCars",
    "BldgType", "OverallQual", "OverallCond", "SalePrice",
]
ames[cols].to_csv("data/raw/ames_housing_raw.csv", index=False)
```

`fetch_openml` downloads from OpenML the first time it is called and caches the result locally, so no
manual download step or committed binary data file is required to reproduce this project.

### Raw column reference

| Column | Meaning |
| --- | --- |
| `Id` | Row identifier (dropped during cleaning) |
| `Neighborhood` | Geographic neighbourhood code within Ames, Iowa |
| `GrLivArea` | Above-grade living area in square feet |
| `LotArea` | Lot size in square feet |
| `LotFrontage` | Linear feet of street connected to the property (unused; retained to show missingness) |
| `BedroomAbvGr` | Bedrooms above grade |
| `FullBath` / `HalfBath` | Full and half bathrooms above grade |
| `BsmtFullBath` / `BsmtHalfBath` | Full and half bathrooms in the basement |
| `YearBuilt` | Original construction year |
| `YrSold` | Year of sale |
| `HouseStyle` | Style of dwelling (mapped to a floor count) |
| `GarageType` | Garage location type (blank means no garage) |
| `GarageCars` | Garage capacity in car units |
| `BldgType` | Dwelling type (mapped to a property type label) |
| `OverallQual` / `OverallCond` | Overall material/finish and condition ratings (unused) |
| `SalePrice` | Sale price in US dollars — the prediction target |

## `processed/house_prices_cleaned.csv`

Written by `src/data_preprocessing.py` (`prepare_and_save_processed_data`). 1,458 rows and 10 columns
in the application's standardized schema:

`location`, `area_sqft`, `lot_area_sqft`, `bedrooms`, `bathrooms`, `property_age`, `floors`,
`parking`, `property_type`, `price`

Missing values are **intentionally retained** in this file. Imputation happens inside the fitted
Scikit-learn pipeline so that the medians used to fill gaps come only from the training split, which
avoids leakage into the test set.

### Cleaning decisions

| Step | Detail |
| --- | --- |
| Duplicate removal | 0 exact duplicates found and removed |
| Anomaly removal | 2 records removed: homes above 4,000 sq ft sold under $300,000, flagged by De Cock (2011) as partial sales not complete at the time of recording |
| Invalid removal | Any record with non-positive living area or sale price |
| Bedroom handling | 6 records with zero above-grade bedrooms converted to `NaN` for median imputation |
| Bathroom handling | Full baths + 0.5 × half baths, including basement bathrooms |
| Age derivation | `YrSold − YearBuilt`, clipped at zero |
| Floors derivation | `HouseStyle` mapped to 1.0 / 1.5 / 2.0 / 2.5 |
| Parking derivation | `GarageType` blank or `GarageCars = 0` → *No Garage*; otherwise 1 / 2 / 3+ car garage |
| Code mapping | Neighbourhood and building-type codes replaced with readable labels |

## Caveats

- The data covers a single mid-western US city between 2006 and 2010. Price levels are historical and
  local; the model must not be used to value homes elsewhere or today.
- `LotFrontage` is present in the raw file but is **not** used by the model. It is kept only because it
  is one of the genuinely incomplete columns in the source data and illustrates the missing-value
  inspection step.
