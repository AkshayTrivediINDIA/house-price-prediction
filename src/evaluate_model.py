"""
Model evaluation, feature importance extraction, and real analytical chart
generation using Matplotlib and Seaborn.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.inspection import permutation_importance
from sklearn.metrics import mean_absolute_error, r2_score, root_mean_squared_error
from sklearn.pipeline import Pipeline

import config


# Consistent editorial color palette matching the UI design
PALETTE = {
    "primary": "#1B4D3E",       # Deep forest green
    "secondary": "#2E7762",     # Muted teal-green
    "accent": "#C86D3B",        # Warm terracotta
    "slate": "#4A5568",         # Muted slate grey
    "light_fill": "#DCECE6",    # Soft sage tint
    "bg": "#FFFFFF",            # Crisp white plot area
    "figure_bg": "#FAF9F6",     # Warm alabaster card background
    "grid": "#EAE7E1",          # Subtle warm border grid
    "text": "#1F2933",          # Dark charcoal text
    "muted_text": "#52606D",    # Secondary label text
}


def compute_regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> Dict[str, float]:
    """Compute MAE, RMSE, and R² score on ground-truth vs predicted prices."""
    mae = float(mean_absolute_error(y_true, y_pred))
    rmse = float(root_mean_squared_error(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    mape = float(np.mean(np.abs((y_true - y_pred) / np.maximum(y_true, 1.0))) * 100.0)
    return {
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "r2": round(r2, 4),
        "mape_percent": round(mape, 2),
    }


def extract_feature_importances(
    pipeline: Pipeline,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> List[Dict[str, Any]]:
    """
    Compute feature-level importance using both:
    1. Aggregated Random Forest impurity importance (summing one-hot sub-columns
       back to their original feature name).
    2. Permutation importance evaluated on the held-out test set.
    """
    preprocessor = pipeline.named_steps["preprocessor"]
    model = pipeline.named_steps["model"]

    # 1. Impurity-based feature importance aggregated by original column
    raw_importances = model.feature_importances_
    num_features = list(config.NUMERICAL_FEATURES)
    cat_features = list(config.CATEGORICAL_FEATURES)

    aggregated_impurity: Dict[str, float] = {}
    idx = 0
    for col in num_features:
        aggregated_impurity[col] = float(raw_importances[idx])
        idx += 1

    ohe = preprocessor.named_transformers_["cat"].named_steps["onehot"]
    for col, categories in zip(cat_features, ohe.categories_):
        n_cats = len(categories)
        aggregated_impurity[col] = float(np.sum(raw_importances[idx : idx + n_cats]))
        idx += n_cats

    # 2. Permutation importance on the held-out test set
    perm = permutation_importance(
        pipeline,
        X_test,
        y_test,
        n_repeats=10,
        random_state=config.RANDOM_STATE,
        scoring="r2",
    )
    perm_means = {
        col: max(0.0, float(perm.importances_mean[i]))
        for i, col in enumerate(X_test.columns)
    }
    perm_total = sum(perm_means.values()) or 1.0

    results = []
    for col in config.ALL_FEATURES:
        impurity_share = aggregated_impurity.get(col, 0.0)
        perm_share = perm_means.get(col, 0.0) / perm_total
        results.append(
            {
                "feature": col,
                "label": config.FEATURE_LABELS.get(col, col),
                "importance": round(impurity_share, 4),
                "importance_pct": round(impurity_share * 100.0, 2),
                "permutation_importance_pct": round(perm_share * 100.0, 2),
            }
        )

    results.sort(key=lambda item: item["importance"], reverse=True)
    return results


def compute_dataset_statistics(df: pd.DataFrame) -> Dict[str, Any]:
    """Calculate summary statistics from the cleaned dataset for the Insights view."""
    price_per_sqft = df["price"] / df["area_sqft"]

    neighborhood_stats = (
        df.groupby("location", as_index=False)
        .agg(
            count=("price", "count"),
            median_price=("price", "median"),
            mean_price=("price", "mean"),
            median_area=("area_sqft", "median"),
            median_age=("property_age", "median"),
        )
        .sort_values("median_price", ascending=False)
    )

    neighborhood_records = [
        {
            "location": str(row["location"]),
            "count": int(row["count"]),
            "median_price": round(float(row["median_price"]), 0),
            "mean_price": round(float(row["mean_price"]), 0),
            "median_area": round(float(row["median_area"]), 0),
            "median_age": round(float(row["median_age"]), 1),
        }
        for _, row in neighborhood_stats.iterrows()
    ]

    property_type_stats = (
        df.groupby("property_type", as_index=False)
        .agg(
            count=("price", "count"),
            median_price=("price", "median"),
            median_area=("area_sqft", "median"),
        )
        .sort_values("median_price", ascending=False)
    )

    return {
        "total_properties": int(len(df)),
        "num_neighborhoods": int(df["location"].nunique()),
        "price": {
            "min": round(float(df["price"].min()), 0),
            "q25": round(float(df["price"].quantile(0.25)), 0),
            "median": round(float(df["price"].median()), 0),
            "mean": round(float(df["price"].mean()), 0),
            "q75": round(float(df["price"].quantile(0.75)), 0),
            "max": round(float(df["price"].max()), 0),
            "std": round(float(df["price"].std()), 0),
        },
        "area_sqft": {
            "min": round(float(df["area_sqft"].min()), 0),
            "median": round(float(df["area_sqft"].median()), 0),
            "mean": round(float(df["area_sqft"].mean()), 0),
            "max": round(float(df["area_sqft"].max()), 0),
        },
        "lot_area_sqft": {
            "min": round(float(df["lot_area_sqft"].min()), 0),
            "median": round(float(df["lot_area_sqft"].median()), 0),
            "mean": round(float(df["lot_area_sqft"].mean()), 0),
            "max": round(float(df["lot_area_sqft"].max()), 0),
        },
        "price_per_sqft": {
            "median": round(float(price_per_sqft.median()), 2),
            "mean": round(float(price_per_sqft.mean()), 2),
            "q25": round(float(price_per_sqft.quantile(0.25)), 2),
            "q75": round(float(price_per_sqft.quantile(0.75)), 2),
        },
        "property_age": {
            "min": round(float(df["property_age"].min()), 0),
            "median": round(float(df["property_age"].median()), 0),
            "mean": round(float(df["property_age"].mean()), 1),
            "max": round(float(df["property_age"].max()), 0),
        },
        "bedrooms_median": float(df["bedrooms"].median()),
        "bathrooms_median": float(df["bathrooms"].median()),
        "neighborhood_summary": neighborhood_records,
        "property_type_summary": [
            {
                "property_type": str(r["property_type"]),
                "count": int(r["count"]),
                "median_price": round(float(r["median_price"]), 0),
                "median_area": round(float(r["median_area"]), 0),
            }
            for _, r in property_type_stats.iterrows()
        ],
    }


def _apply_chart_theme() -> None:
    """Configure Matplotlib rcParams for clean, readable light-theme charts."""
    plt.rcParams.update(
        {
            "figure.facecolor": PALETTE["figure_bg"],
            "axes.facecolor": PALETTE["bg"],
            "axes.edgecolor": "#D5D2C9",
            "axes.linewidth": 0.9,
            "axes.grid": True,
            "grid.color": PALETTE["grid"],
            "grid.linestyle": "--",
            "grid.linewidth": 0.7,
            "grid.alpha": 0.85,
            "text.color": PALETTE["text"],
            "axes.labelcolor": PALETTE["text"],
            "xtick.color": PALETTE["muted_text"],
            "ytick.color": PALETTE["muted_text"],
            "font.family": "sans-serif",
            "font.size": 10,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
        }
    )


def _currency_formatter(x: float, pos: int) -> str:
    if x >= 1_000_000:
        return f"${x / 1_000_000:.1f}M"
    return f"${int(x / 1_000):,}k"


def generate_all_charts(
    df: pd.DataFrame,
    feature_importances: List[Dict[str, Any]],
    y_test: np.ndarray,
    rf_preds: np.ndarray,
    lr_preds: np.ndarray,
    charts_dir: Path = config.CHARTS_DIR,
) -> Dict[str, str]:
    """
    Generate real analytical visualizations from the cleaned dataset and trained
    model outputs, saving high-resolution PNG files to static/images/charts/.
    """
    _apply_chart_theme()
    charts_dir = Path(charts_dir)
    charts_dir.mkdir(parents=True, exist_ok=True)
    currency_fmt = mticker.FuncFormatter(_currency_formatter)

    # 1. House Price Distribution
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=160)
    sns.histplot(
        df["price"],
        bins=36,
        kde=True,
        color=PALETTE["primary"],
        edgecolor="#FFFFFF",
        alpha=0.78,
        ax=ax,
    )
    median_price = float(df["price"].median())
    mean_price = float(df["price"].mean())
    ax.axvline(
        median_price,
        color=PALETTE["accent"],
        linestyle="--",
        linewidth=1.8,
        label=f"Median: ${median_price:,.0f}",
    )
    ax.axvline(
        mean_price,
        color=PALETTE["slate"],
        linestyle=":",
        linewidth=1.8,
        label=f"Mean: ${mean_price:,.0f}",
    )
    ax.xaxis.set_major_formatter(currency_fmt)
    ax.set_title("Distribution of Recorded Sale Prices (n = 1,458)", pad=12)
    ax.set_xlabel("Sale Price (USD)")
    ax.set_ylabel("Number of Properties")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2DFD7")
    sns.despine(top=True, right=True)
    fig.tight_layout()
    dist_path = charts_dir / "price_distribution.png"
    fig.savefig(dist_path)
    plt.close(fig)

    # 2. Price vs Living Area (sq ft)
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=160)
    top_types = ["Single-Family Detached", "Townhouse (End Unit)", "Duplex"]
    plot_df = df.copy()
    plot_df["display_type"] = np.where(
        plot_df["property_type"].isin(top_types),
        plot_df["property_type"],
        "Other Residential",
    )
    type_colors = {
        "Single-Family Detached": PALETTE["primary"],
        "Townhouse (End Unit)": PALETTE["accent"],
        "Duplex": "#4B729F",
        "Other Residential": "#8C9BA5",
    }
    for ptype, group in plot_df.groupby("display_type"):
        ax.scatter(
            group["area_sqft"],
            group["price"],
            label=ptype,
            color=type_colors.get(ptype, PALETTE["slate"]),
            alpha=0.58,
            s=26,
            edgecolors="none",
        )
    # Linear trend line across all observations
    slope, intercept = np.polyfit(df["area_sqft"], df["price"], 1)
    x_vals = np.linspace(df["area_sqft"].min(), df["area_sqft"].max(), 100)
    ax.plot(
        x_vals,
        slope * x_vals + intercept,
        color="#1F2933",
        linestyle="--",
        linewidth=1.6,
        label=f"OLS Trend (+${slope:,.0f}/sq ft)",
    )
    ax.yaxis.set_major_formatter(currency_fmt)
    ax.xaxis.set_major_formatter(mticker.StrMethodFormatter("{x:,.0f}"))
    ax.set_title("Sale Price vs. Above-Grade Living Area", pad=12)
    ax.set_xlabel("Living Area (sq ft)")
    ax.set_ylabel("Sale Price (USD)")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2DFD7", fontsize=8.5)
    sns.despine(top=True, right=True)
    fig.tight_layout()
    area_path = charts_dir / "price_vs_area.png"
    fig.savefig(area_path)
    plt.close(fig)

    # 3. Price vs Number of Bedrooms
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=160)
    bed_df = df.dropna(subset=["bedrooms"]).copy()
    bed_df["bedrooms_int"] = bed_df["bedrooms"].astype(int).clip(1, 6)
    bed_df["bedrooms_label"] = bed_df["bedrooms_int"].apply(
        lambda b: f"{b}+" if b == 6 else str(b)
    )
    order = ["1", "2", "3", "4", "5", "6+"]
    present_order = [o for o in order if o in bed_df["bedrooms_label"].unique()]
    sns.boxplot(
        data=bed_df,
        x="bedrooms_label",
        y="price",
        order=present_order,
        color=PALETTE["light_fill"],
        boxprops=dict(edgecolor=PALETTE["primary"], linewidth=1.2),
        medianprops=dict(color=PALETTE["accent"], linewidth=2.0),
        whiskerprops=dict(color=PALETTE["primary"], linewidth=1.1),
        capprops=dict(color=PALETTE["primary"], linewidth=1.1),
        flierprops=dict(marker="o", markersize=3, alpha=0.35, markerfacecolor=PALETTE["slate"]),
        ax=ax,
    )
    ax.yaxis.set_major_formatter(currency_fmt)
    ax.set_title("Sale Price Distribution by Number of Bedrooms", pad=12)
    ax.set_xlabel("Number of Bedrooms (Above Grade)")
    ax.set_ylabel("Sale Price (USD)")
    sns.despine(top=True, right=True)
    fig.tight_layout()
    bed_path = charts_dir / "price_vs_bedrooms.png"
    fig.savefig(bed_path)
    plt.close(fig)

    # 4. Price vs Property Age
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=160)
    ax.scatter(
        df["property_age"],
        df["price"],
        color=PALETTE["secondary"],
        alpha=0.38,
        s=22,
        edgecolors="none",
        label="Individual Properties",
    )
    age_bins = pd.cut(df["property_age"], bins=np.arange(0, 145, 10), include_lowest=True)
    age_medians = df.groupby(age_bins, observed=True).agg(
        age_mid=("property_age", "median"),
        median_price=("price", "median"),
    ).dropna()
    ax.plot(
        age_medians["age_mid"],
        age_medians["median_price"],
        color=PALETTE["accent"],
        marker="o",
        linewidth=2.2,
        markersize=5,
        label="10-Year Bin Median Price",
    )
    ax.yaxis.set_major_formatter(currency_fmt)
    ax.set_title("Sale Price vs. Property Age at Sale", pad=12)
    ax.set_xlabel("Property Age (Years)")
    ax.set_ylabel("Sale Price (USD)")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2DFD7")
    sns.despine(top=True, right=True)
    fig.tight_layout()
    age_path = charts_dir / "price_vs_age.png"
    fig.savefig(age_path)
    plt.close(fig)

    # 5. Random Forest Feature Importance
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=160)
    sorted_fi = sorted(feature_importances, key=lambda x: x["importance_pct"])
    labels = [item["label"] for item in sorted_fi]
    values = [item["importance_pct"] for item in sorted_fi]
    bars = ax.barh(labels, values, color=PALETTE["primary"], height=0.62, alpha=0.9)
    for bar, val in zip(bars, values):
        ax.text(
            val + 0.6,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.1f}%",
            va="center",
            ha="left",
            fontsize=9,
            color=PALETTE["text"],
            fontweight="semibold",
        )
    ax.set_xlim(0, max(values) * 1.18)
    ax.set_title("Random Forest Global Feature Importance", pad=12)
    ax.set_xlabel("Relative Contribution to Variance Reduction (%)")
    sns.despine(top=True, right=True)
    fig.tight_layout()
    fi_path = charts_dir / "feature_importance.png"
    fig.savefig(fi_path)
    plt.close(fig)

    # 6. Model Comparison: Predicted vs Actual on Held-Out Test Set
    fig, ax = plt.subplots(figsize=(7.5, 4.5), dpi=160)
    ax.scatter(
        y_test,
        lr_preds,
        color="#9AA5B1",
        alpha=0.45,
        s=24,
        label="Linear Regression (Baseline)",
    )
    ax.scatter(
        y_test,
        rf_preds,
        color=PALETTE["primary"],
        alpha=0.68,
        s=28,
        label="Random Forest Regressor (Selected)",
    )
    min_val = float(min(y_test.min(), rf_preds.min()))
    max_val = float(max(y_test.max(), rf_preds.max()))
    ax.plot(
        [min_val, max_val],
        [min_val, max_val],
        color=PALETTE["accent"],
        linestyle="--",
        linewidth=1.8,
        label="Ideal 1:1 Prediction Line",
    )
    ax.xaxis.set_major_formatter(currency_fmt)
    ax.yaxis.set_major_formatter(currency_fmt)
    ax.set_title("Held-Out Test Set: Predicted vs. Actual Sale Price (n = 292)", pad=12)
    ax.set_xlabel("Actual Recorded Sale Price (USD)")
    ax.set_ylabel("Model Predicted Price (USD)")
    ax.legend(frameon=True, facecolor="#FFFFFF", edgecolor="#E2DFD7", fontsize=8.5)
    sns.despine(top=True, right=True)
    fig.tight_layout()
    comp_path = charts_dir / "model_comparison.png"
    fig.savefig(comp_path)
    plt.close(fig)

    return {
        "price_distribution": "images/charts/price_distribution.png",
        "price_vs_area": "images/charts/price_vs_area.png",
        "price_vs_bedrooms": "images/charts/price_vs_bedrooms.png",
        "price_vs_age": "images/charts/price_vs_age.png",
        "feature_importance": "images/charts/feature_importance.png",
        "model_comparison": "images/charts/model_comparison.png",
    }
