"""
Render the figures used by the complete project guide.

Every chart is produced from the real cleaned dataset and the two saved
pipelines -- nothing here is illustrative or hand-drawn.

    python docs/build_guide_charts.py

Output: docs/guide_charts/*.png
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

import config

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "docs" / "guide_charts"
METRICS_PATH = PROJECT_ROOT / "models" / "metrics.json"

GREEN = "#2F6B4F"
GREEN_MID = "#7FA893"
INK = "#1F2421"
MUTED = "#637268"
LINE = "#DCE3DE"
GRID = "#EDEFE9"

plt.rcParams.update({
    "figure.facecolor": "white",
    "axes.facecolor": "white",
    "axes.edgecolor": LINE,
    "axes.labelcolor": INK,
    "axes.titlecolor": INK,
    "axes.titlesize": 12.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 10.5,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "xtick.labelsize": 9.5,
    "ytick.labelsize": 9.5,
    "axes.grid": True,
    "grid.color": GRID,
    "grid.linewidth": 0.8,
    "axes.axisbelow": True,
    "font.family": "DejaVu Sans",
    "legend.frameon": False,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})


def finish(fig, name):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / f"{name}.png"
    fig.savefig(path, dpi=170)
    plt.close(fig)
    print(f"  {path.name}")
    return path


def load_split():
    """Rebuild the exact split the trainer used."""
    import joblib
    df = pd.read_csv(config.PROCESSED_DATA_PATH)
    X = df[config.NUMERICAL_FEATURES + config.CATEGORICAL_FEATURES]
    y = df[config.TARGET_COLUMN]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.RANDOM_STATE
    )
    rf = joblib.load(config.MODEL_PATH)
    lr = joblib.load(config.BASELINE_MODEL_PATH)
    return X_train, X_test, y_train, y_test, rf, lr


def chart_price_distribution(df):
    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.hist(df[config.TARGET_COLUMN], bins=42, color=GREEN, alpha=0.85, edgecolor="white", linewidth=0.6)
    med = df[config.TARGET_COLUMN].median()
    ax.axvline(med, color=INK, linestyle="--", linewidth=1.6)
    ax.annotate(f"median ${med:,.0f}", xy=(med, ax.get_ylim()[1] * 0.9),
                xytext=(9, -3), textcoords="offset points", fontsize=10, color=INK, fontweight="bold")
    ax.set_title("Sale prices are right-skewed — a few expensive homes pull the average up")
    ax.set_xlabel("Sale price (USD)")
    ax.set_ylabel("Number of properties")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
    return finish(fig, "price_distribution")


def chart_price_vs_area(df):
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.scatter(df["area_sqft"], df[config.TARGET_COLUMN], s=11, color=GREEN, alpha=0.42,
               edgecolors="none")
    z = np.polyfit(df["area_sqft"], df[config.TARGET_COLUMN], 1)
    xs = np.linspace(df["area_sqft"].min(), df["area_sqft"].max(), 50)
    ax.plot(xs, np.polyval(z, xs), color=INK, linewidth=1.8, linestyle="--", label="Linear trend")
    ax.set_title("Living area is the strongest single predictor of price")
    ax.set_xlabel("Living area (sq ft)")
    ax.set_ylabel("Sale price (USD)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
    ax.legend(loc="upper left", fontsize=9.5)
    return finish(fig, "price_vs_area")


def chart_price_vs_age(df):
    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.scatter(df["property_age"], df[config.TARGET_COLUMN], s=11, color=GREEN_MID, alpha=0.45,
               edgecolors="none")
    z = np.polyfit(df["property_age"], df[config.TARGET_COLUMN], 1)
    xs = np.linspace(df["property_age"].min(), df["property_age"].max(), 50)
    ax.plot(xs, np.polyval(z, xs), color=INK, linewidth=1.8, linestyle="--", label="Linear trend")
    ax.set_title("Newer homes generally sell for more, with wide variation")
    ax.set_xlabel("Property age at sale (years)")
    ax.set_ylabel("Sale price (USD)")
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
    ax.legend(loc="upper right", fontsize=9.5)
    return finish(fig, "price_vs_age")


def chart_correlation(df):
    cols = config.NUMERICAL_FEATURES + [config.TARGET_COLUMN]
    corr = df[cols].corr()
    labels = [config.FEATURE_LABELS.get(c, c) for c in cols]
    labels[-1] = "Sale price"
    fig, ax = plt.subplots(figsize=(6.6, 5.4))
    sns.heatmap(corr, annot=True, fmt=".2f", cmap="Greens", center=0,
                vmin=-1, vmax=1, square=True, linewidths=0.8, linecolor="white",
                cbar_kws={"shrink": 0.72}, ax=ax,
                annot_kws={"size": 9})
    ax.set_xticklabels(labels, rotation=42, ha="right", fontsize=9)
    ax.set_yticklabels(labels, rotation=0, fontsize=9)
    ax.set_title("Correlation among numeric features", pad=12)
    return finish(fig, "correlation")


def chart_actual_vs_predicted(y_test, rf_pred, lr_pred):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 4.3))
    lims = [min(y_test.min(), rf_pred.min()) * 0.92, max(y_test.max(), rf_pred.max()) * 1.04]
    for ax, pred, name, color in [
        (axes[0], lr_pred, "Linear Regression", GREEN_MID),
        (axes[1], rf_pred, "Random Forest", GREEN),
    ]:
        ax.scatter(y_test, pred, s=15, color=color, alpha=0.5, edgecolors="none")
        ax.plot(lims, lims, color=INK, linewidth=1.5, linestyle="--", label="Perfect prediction")
        ax.set_xlim(lims); ax.set_ylim(lims)
        ax.set_title(name)
        ax.set_xlabel("Actual sale price (USD)")
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
        ax.legend(loc="upper left", fontsize=8.5)
    axes[0].set_ylabel("Predicted price (USD)")
    fig.suptitle("Held-out test set: points closer to the dashed line are better",
                 fontsize=12.5, fontweight="bold", y=1.02)
    return finish(fig, "actual_vs_predicted")


def chart_residuals(y_test, rf_pred, lr_pred):
    fig, axes = plt.subplots(1, 2, figsize=(9.6, 3.9))
    for ax, pred, name, color in [
        (axes[0], lr_pred, "Linear Regression", GREEN_MID),
        (axes[1], rf_pred, "Random Forest", GREEN),
    ]:
        resid = y_test - pred
        ax.scatter(pred, resid, s=15, color=color, alpha=0.5, edgecolors="none")
        ax.axhline(0, color=INK, linewidth=1.4, linestyle="--")
        ax.set_title(name)
        ax.set_xlabel("Predicted price (USD)")
        ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
    axes[0].set_ylabel("Error (actual − predicted)")
    fig.suptitle("Residuals: a good model scatters evenly around zero",
                 fontsize=12.5, fontweight="bold", y=1.03)
    return finish(fig, "residuals")


def chart_model_comparison(metrics):
    lr, rf = metrics["models"]["linear_regression"], metrics["models"]["random_forest"]
    fig, axes = plt.subplots(1, 3, figsize=(9.8, 3.5))
    specs = [
        ("MAE (USD)", "mae", lambda v: f"${v:,.0f}"),
        ("RMSE (USD)", "rmse", lambda v: f"${v:,.0f}"),
        ("R² (higher is better)", "r2", lambda v: f"{v:.4f}"),
    ]
    for ax, (title, key, fmt) in zip(axes, specs):
        vals = [lr["test_metrics"][key], rf["test_metrics"][key]]
        bars = ax.bar(["Linear", "Random\nForest"], vals, color=[GREEN_MID, GREEN], width=0.56,
                      edgecolor="white", linewidth=1.2)
        for b, v in zip(bars, vals):
            ax.annotate(fmt(v), xy=(b.get_x() + b.get_width() / 2, v),
                        xytext=(0, 4), textcoords="offset points",
                        ha="center", fontsize=10, fontweight="bold", color=INK)
        ax.set_title(title)
        ax.set_ylim(0, max(vals) * 1.22)
        ax.set_xticks(range(2))
        ax.set_xticklabels(["Linear", "Random\nForest"], fontsize=9.5)
        if key in ("mae", "rmse"):
            ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
    fig.suptitle("Held-out test performance", fontsize=12.5, fontweight="bold", y=1.04)
    return finish(fig, "model_comparison")


def chart_train_vs_test(metrics):
    lr, rf = metrics["models"]["linear_regression"], metrics["models"]["random_forest"]
    fig, ax = plt.subplots(figsize=(7.4, 3.5))
    models = ["Linear Regression", "Random Forest"]
    train = [lr["train_metrics"]["r2"], rf["train_metrics"]["r2"]]
    test = [lr["test_metrics"]["r2"], rf["test_metrics"]["r2"]]
    x = np.arange(len(models))
    w = 0.34
    b1 = ax.bar(x - w / 2, train, w, label="Train R²", color=GREEN_MID, edgecolor="white", linewidth=1.2)
    b2 = ax.bar(x + w / 2, test, w, label="Held-out test R²", color=GREEN, edgecolor="white", linewidth=1.2)
    for b, v in list(zip(b1, train)) + list(zip(b2, test)):
        ax.annotate(f"{v:.3f}", xy=(b.get_x() + b.get_width() / 2, v),
                    xytext=(0, 3), textcoords="offset points", ha="center",
                    fontsize=9.5, fontweight="bold", color=INK)
    gap = rf["train_metrics"]["r2"] - rf["test_metrics"]["r2"]
    ax.annotate(f"generalisation gap {gap:.3f}",
                xy=(1, (train[1] + test[1]) / 2), xytext=(1.42, 0.94),
                fontsize=9.5, color=INK, fontweight="bold",
                arrowprops=dict(arrowstyle="->", color=INK, linewidth=1.1))
    ax.set_ylim(0, 1.13)
    ax.set_xticks(x); ax.set_xticklabels(models, fontsize=10)
    ax.set_ylabel("R²")
    ax.set_title("The Random Forest fits training data far better than it generalises")
    ax.legend(loc="lower left", fontsize=9.5, ncol=2)
    return finish(fig, "train_vs_test")


def chart_feature_importance(metrics):
    imp = metrics["feature_importances"]
    labels = [f["label"] for f in imp][::-1]
    gini = [f["importance_pct"] for f in imp][::-1]
    perm = [f["permutation_importance_pct"] for f in imp][::-1]
    y = np.arange(len(labels))
    h = 0.38
    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.barh(y + h / 2, gini, h, label="Impurity importance", color=GREEN, edgecolor="white", linewidth=1)
    ax.barh(y - h / 2, perm, h, label="Permutation importance", color=GREEN_MID, edgecolor="white", linewidth=1)
    for i, (g, p) in enumerate(zip(gini, perm)):
        ax.annotate(f"{g:.1f}", xy=(g, i + h / 2), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=INK)
        ax.annotate(f"{p:.1f}", xy=(p, i - h / 2), xytext=(4, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=INK)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=9.5)
    ax.set_xlabel("Importance (%)")
    ax.set_title("The two measures disagree — permutation is the more trustworthy ranking")
    ax.legend(loc="lower right", fontsize=9.5)
    ax.set_xlim(0, max(gini + perm) * 1.15)
    return finish(fig, "feature_importance")


def chart_pipeline_diagram():
    fig, ax = plt.subplots(figsize=(9.4, 2.5))
    ax.axis("off")
    ax.set_xlim(0, 100); ax.set_ylim(0, 26)
    steps = [
        ("Raw CSV\n1,460 × 19", GREEN_MID),
        ("Clean &\nderive", GREEN_MID),
        ("Train/test\nsplit", GREEN_MID),
        ("Column\nTransformer", GREEN_MID),
        ("Random Forest\n(300 trees)", GREEN),
        ("Saved\npipeline", GREEN),
    ]
    box_w, gap = 14.2, 1.6
    total = len(steps) * box_w + (len(steps) - 1) * gap
    x0 = (100 - total) / 2
    for i, (label, color) in enumerate(steps):
        x = x0 + i * (box_w + gap)
        ax.add_patch(plt.Rectangle((x, 7), box_w, 12, facecolor=color, alpha=0.16,
                                   edgecolor=color, linewidth=1.7,
                                   joinstyle="round", zorder=2,
                                   **{"capstyle": "round"}))
        ax.text(x + box_w / 2, 13, label, ha="center", va="center",
                fontsize=8.6, color=INK, fontweight="bold", zorder=3, linespacing=1.5)
        if i < len(steps) - 1:
            ax.annotate("", xy=(x + box_w + gap - 0.4, 13), xytext=(x + box_w + 0.4, 13),
                        arrowprops=dict(arrowstyle="->", color=GREEN, linewidth=1.6), zorder=3)
    ax.text(50, 2.2, "Everything inside one Pipeline — the same fitted transforms apply at inference",
            ha="center", fontsize=9.5, color=MUTED, style="italic")
    return finish(fig, "pipeline_diagram")


def chart_neighbourhood(metrics):
    nb = metrics["dataset_statistics"]["neighborhood_summary"]
    items = sorted(nb, key=lambda d: d["median_price"])[-12:]
    labels = [d["location"] for d in items]
    vals = [d["median_price"] for d in items]
    counts = [d["count"] for d in items]
    fig, ax = plt.subplots(figsize=(7.4, 4.5))
    ax.barh(labels, vals, color=GREEN, height=0.62, edgecolor="white", linewidth=1)
    for i, (v, c) in enumerate(zip(vals, counts)):
        ax.annotate(f"${v:,.0f}  (n={c})", xy=(v, i), xytext=(5, 0),
                    textcoords="offset points", va="center", fontsize=8.8, color=INK)
    ax.set_xlabel("Median sale price (USD)")
    ax.set_title("Twelve most expensive neighbourhoods, with the number of recorded sales")
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, p: f"${v/1000:.0f}k"))
    ax.set_xlim(0, max(vals) * 1.30)
    return finish(fig, "neighbourhood")


def main():
    print("Rendering guide figures ...")
    metrics = json.loads(METRICS_PATH.read_text())
    df = pd.read_csv(config.PROCESSED_DATA_PATH)

    chart_price_distribution(df)
    chart_price_vs_area(df)
    chart_price_vs_age(df)
    chart_correlation(df)
    chart_neighbourhood(metrics)
    chart_model_comparison(metrics)
    chart_train_vs_test(metrics)
    chart_feature_importance(metrics)
    chart_pipeline_diagram()

    X_train, X_test, y_train, y_test, rf, lr = load_split()
    chart_actual_vs_predicted(y_test, rf.predict(X_test), lr.predict(X_test))
    chart_residuals(y_test, rf.predict(X_test), lr.predict(X_test))

    print(f"\nDone — {len(list(OUT_DIR.glob('*.png')))} figures in {OUT_DIR}")


if __name__ == "__main__":
    main()
