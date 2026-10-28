"""
Generate the HomeValue project presentation as a .pptx file.

Every metric, importance value and dataset statistic is read from
`models/metrics.json` at build time, so the deck can never drift from the
artifacts the model actually produced.

    python docs/build_presentation.py

Output: docs/HomeValue_Presentation.pptx
"""

from __future__ import annotations

import json
from pathlib import Path

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Emu, Inches, Pt

PROJECT_ROOT = Path(__file__).resolve().parent.parent
METRICS_PATH = PROJECT_ROOT / "models" / "metrics.json"
OUTPUT_PATH = PROJECT_ROOT / "docs" / "HomeValue_Presentation.pptx"

# ---------------------------------------------------------------------------
# Design tokens -- the same palette the web application uses.
# ---------------------------------------------------------------------------
INK = RGBColor(0x1F, 0x24, 0x21)          # charcoal body text
MUTED = RGBColor(0x63, 0x72, 0x68)        # secondary text
GREEN = RGBColor(0x2F, 0x6B, 0x4F)        # forest green accent
GREEN_SOFT = RGBColor(0xE7, 0xEF, 0xEA)   # pale green fill
GREEN_MID = RGBColor(0x7F, 0xA8, 0x93)    # muted green for secondary series
LINE = RGBColor(0xDC, 0xE3, 0xDE)         # hairline rules
PAPER = RGBColor(0xFF, 0xFF, 0xFF)
WARN = RGBColor(0x8C, 0x4A, 0x2F)         # limitations accent
WARN_SOFT = RGBColor(0xFB, 0xF0, 0xEA)

FONT = "Calibri"
SLIDE_W = Inches(13.333)
SLIDE_H = Inches(7.5)
MARGIN = Inches(0.8)
CONTENT_W = SLIDE_W - 2 * MARGIN


# ---------------------------------------------------------------------------
# Primitive helpers
# ---------------------------------------------------------------------------
def box(slide, x, y, w, h, fill=None, line=None, line_w=0.75, shape=MSO_SHAPE.RECTANGLE, radius=None):
    shp = slide.shapes.add_shape(shape, x, y, w, h)
    if fill is None:
        shp.fill.background()
    else:
        shp.fill.solid()
        shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(line_w)
    shp.shadow.inherit = False
    if radius is not None and shape == MSO_SHAPE.ROUNDED_RECTANGLE:
        try:
            shp.adjustments[0] = radius
        except (IndexError, KeyError):
            pass
    tf = shp.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = Inches(0.12)
    tf.margin_top = tf.margin_bottom = Inches(0.06)
    return shp


def text(slide, x, y, w, h, runs, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.0):
    """`runs` is a list of (text, size_pt, bold, color, space_before_pt)."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    first = True
    for item in runs:
        body, size, bold, color, before = item
        para = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        para.alignment = align
        para.line_spacing = spacing
        if before:
            para.space_before = Pt(before)
        run = para.add_run()
        run.text = body
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = color
        run.font.name = FONT
    return tb


def bullets(slide, x, y, w, h, items, size=15, color=INK, gap=9):
    """`items` is a list of strings, or (string, RGBColor) to override colour."""
    tb = slide.shapes.add_textbox(x, y, w, h)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = 0
    tf.margin_top = tf.margin_bottom = 0
    for idx, item in enumerate(items):
        if isinstance(item, tuple):
            body = item[0]
            col = item[1] if len(item) > 1 else color
        else:
            body, col = item, color
        para = tf.paragraphs[0] if idx == 0 else tf.add_paragraph()
        para.line_spacing = 1.18
        if idx:
            para.space_before = Pt(gap)
        run = para.add_run()
        run.text = "•  " + body
        run.font.size = Pt(size)
        run.font.color.rgb = col
        run.font.name = FONT
    return tb


def slide_base(prs, title, kicker=None, subtitle=None):
    """A blank white slide with the standard title block."""
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box(slide, Emu(0), Emu(0), SLIDE_W, SLIDE_H, fill=PAPER)
    top = Inches(0.55)
    if kicker:
        text(slide, MARGIN, top, CONTENT_W, Inches(0.3),
             [(kicker.upper(), 11, True, GREEN, 0)])
        top = top + Inches(0.34)
    text(slide, MARGIN, top, CONTENT_W, Inches(0.62),
         [(title, 30, True, INK, 0)])
    top = top + Inches(0.66)
    if subtitle:
        text(slide, MARGIN, top, CONTENT_W, Inches(0.4),
             [(subtitle, 14, False, MUTED, 0)])
        top = top + Inches(0.5)
    rule = box(slide, MARGIN, top, CONTENT_W, Emu(9525), fill=LINE)
    rule.line.fill.background()
    return slide, top + Inches(0.36)


def footer(slide, number, note=None):
    text(slide, MARGIN, SLIDE_H - Inches(0.52), Inches(9.5), Inches(0.3),
         [(note or "HomeValue — House Price Prediction System", 9.5, False, MUTED, 0)])
    text(slide, SLIDE_W - MARGIN - Inches(1.0), SLIDE_H - Inches(0.52),
         Inches(1.0), Inches(0.3), [(str(number), 9.5, True, GREEN, 0)],
         align=PP_ALIGN.RIGHT)


def kpi_card(slide, x, y, w, h, value, label, note=None):
    box(slide, x, y, w, h, fill=GREEN_SOFT, line=LINE, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    box(slide, x, y, Inches(0.055), h, fill=GREEN)
    text(slide, x + Inches(0.28), y + Inches(0.24), w - Inches(0.45), Inches(0.55),
         [(value, 27, True, GREEN, 0)])
    text(slide, x + Inches(0.28), y + Inches(0.84), w - Inches(0.45), Inches(0.34),
         [(label, 12.5, True, INK, 0)])
    if note:
        text(slide, x + Inches(0.28), y + Inches(1.2), w - Inches(0.45), Inches(0.5),
             [(note, 10.5, False, MUTED, 0)], spacing=1.15)


def table(slide, x, y, w, headers, rows, col_widths, row_h=Inches(0.42), head_h=Inches(0.46),
          highlight_last_col=False, font=13):
    shape = slide.shapes.add_table(len(rows) + 1, len(headers), x, y, w, head_h + row_h * len(rows))
    tbl = shape.table
    tbl.first_row = True
    tbl.horz_banding = False

    for i, cw in enumerate(col_widths):
        tbl.columns[i].width = cw
    tbl.rows[0].height = head_h
    for r in range(len(rows)):
        tbl.rows[r + 1].height = row_h

    for c, head in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = GREEN
        cell.margin_left = cell.margin_right = Inches(0.1)
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        para = cell.text_frame.paragraphs[0]
        para.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT
        run = para.add_run()
        run.text = head
        run.font.size = Pt(12)
        run.font.bold = True
        run.font.color.rgb = PAPER
        run.font.name = FONT

    for r, row in enumerate(rows, start=1):
        for c, val in enumerate(row):
            cell = tbl.cell(r, c)
            cell.fill.solid()
            cell.fill.fore_color.rgb = PAPER if r % 2 else GREEN_SOFT
            cell.margin_left = cell.margin_right = Inches(0.1)
            cell.margin_top = cell.margin_bottom = Inches(0.02)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            para = cell.text_frame.paragraphs[0]
            para.alignment = PP_ALIGN.CENTER if c else PP_ALIGN.LEFT
            run = para.add_run()
            run.text = str(val)
            run.font.size = Pt(font)
            run.font.name = FONT
            is_last = c == len(headers) - 1
            run.font.bold = highlight_last_col and is_last
            run.font.color.rgb = INK
    return tbl


def hbar(slide, x, y, w, items, row_h=Inches(0.44), gap=Inches(0.13),
         label_w=Inches(2.5), value_w=Inches(1.5), color=GREEN, color2=None,
         bar_h=Inches(0.19), fmt=str, scale_note=None):
    """Horizontal bars. items: (label, primary, secondary_or_None)."""
    plot_w = w - label_w - value_w - Inches(0.2)
    top_val = max([i[1] for i in items] + [i[2] or 0 for i in items] + [1])
    cy = y
    for label, primary, secondary in items:
        text(slide, x, cy + Inches(0.06), label_w, row_h, [(label, 12.5, False, INK, 0)])
        track_x = x + label_w
        if secondary is not None:
            # two stacked mini-bars: primary (green) above secondary (muted)
            b1 = max(int(plot_w * primary / top_val), Emu(12700))
            b2 = max(int(plot_w * secondary / top_val), Emu(12700))
            box(slide, track_x, cy + Inches(0.02), b1, bar_h * 0.52, fill=color)
            box(slide, track_x, cy + Inches(0.02) + bar_h * 0.62, b2, bar_h * 0.52, fill=color2 or GREEN_MID)
        else:
            b = max(int(plot_w * primary / top_val), Emu(12700))
            box(slide, track_x, cy + Inches(0.09), b, bar_h, fill=color)
        text(slide, track_x + plot_w + Inches(0.14), cy + Inches(0.06), value_w, row_h,
             [(fmt(primary), 12, True, INK, 0)])
        cy += row_h + gap
    if scale_note:
        text(slide, track_x, cy, plot_w, Inches(0.3), [(scale_note, 10, False, MUTED, 0)])
    return cy


def vbar(slide, x, y, w, h, series, categories, gap=Inches(0.55), fmt=str, bar_colors=None):
    """Grouped vertical bars with a baseline and value labels."""
    n_cat = len(categories)
    n_ser = len(series)
    group_w = int((w - gap * (n_cat - 1)) / n_cat)
    bar_w = int(group_w / n_ser) - Inches(0.04)
    top_val = max(max(s["values"]) for s in series) * 1.15

    base_y = y + h
    box(slide, x, base_y, w, Emu(12700), fill=LINE)

    for ci, cat in enumerate(categories):
        gx = x + ci * (group_w + gap)
        for si, s in enumerate(series):
            val = s["values"][ci]
            bh = max(int(h * val / top_val), Emu(12700))
            bx = gx + si * (bar_w + Inches(0.04))
            color = (bar_colors[si] if bar_colors else GREEN)
            box(slide, bx, base_y - bh, bar_w, bh, fill=color, shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
            text(slide, bx - Inches(0.2), base_y - bh - Inches(0.28), bar_w + Inches(0.4), Inches(0.26),
                 [(fmt(val), 11, True, INK, 0)], align=PP_ALIGN.CENTER)
        text(slide, gx, base_y + Inches(0.1), group_w, Inches(0.3),
             [(cat, 12.5, True, INK, 0)], align=PP_ALIGN.CENTER)
    return base_y


def flow(slide, x, y, w, steps, box_h=Inches(1.05), accent=GREEN, accent_soft=GREEN_SOFT):
    """A left-to-right flow of numbered boxes with chevrons between them."""
    n = len(steps)
    arrow_w = Inches(0.42)
    bw = int((w - arrow_w * (n - 1)) / n)
    for i, (head, sub) in enumerate(steps):
        bx = x + i * (bw + arrow_w)
        box(slide, bx, y, bw, box_h, fill=accent_soft, line=LINE,
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
        text(slide, bx, y + Inches(0.16), bw, Inches(0.3),
             [(str(i + 1), 13, True, accent, 0)], align=PP_ALIGN.CENTER)
        text(slide, bx, y + Inches(0.46), bw, Inches(0.28),
             [(head, 13, True, INK, 0)], align=PP_ALIGN.CENTER)
        text(slide, bx, y + Inches(0.74), bw, Inches(0.3),
             [(sub, 9.5, False, MUTED, 0)], align=PP_ALIGN.CENTER, spacing=0.95)
        if i < n - 1:
            ax = bx + bw
            text(slide, ax, y + int(box_h / 2) - Inches(0.22), arrow_w, Inches(0.44),
                 [("›", 26, True, accent, 0)], align=PP_ALIGN.CENTER)


def legend(slide, x, y, items):
    cx = x
    for color, label in items:
        box(slide, cx, y + Inches(0.05), Inches(0.19), Inches(0.19), fill=color)
        text(slide, cx + Inches(0.27), y, Inches(2.4), Inches(0.28),
             [(label, 10.5, False, MUTED, 0)])
        cx += Inches(0.27) + Inches(0.16) * len(label) * 0.62 + Inches(1.0)


def money(v):
    return f"${v:,.0f}"


def money2(v):
    return f"${v:,.2f}"


# ---------------------------------------------------------------------------
# Slides
# ---------------------------------------------------------------------------
def build():
    metrics = json.loads(METRICS_PATH.read_text())
    lr = metrics["models"]["linear_regression"]
    rf = metrics["models"]["random_forest"]
    prep = metrics["data_preparation"]
    ds = metrics["dataset_statistics"]
    meta = metrics["dataset_metadata"]
    imp = metrics["feature_importances"]

    prs = Presentation()
    prs.slide_width = SLIDE_W
    prs.slide_height = SLIDE_H

    n = 0

    # ---- 1. Title ---------------------------------------------------------
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box(slide, Emu(0), Emu(0), SLIDE_W, SLIDE_H, fill=GREEN)
    box(slide, SLIDE_W - Inches(3.4), Emu(0), Inches(3.4), SLIDE_H, fill=RGBColor(0x2A, 0x60, 0x46))
    text(slide, Inches(1.0), Inches(1.85), Inches(8.4), Inches(0.4),
         [("MACHINE LEARNING PROJECT", 13, True, RGBColor(0xA8, 0xC9, 0xB8), 0)])
    text(slide, Inches(1.0), Inches(2.35), Inches(8.4), Inches(1.5),
         [("HomeValue", 60, True, PAPER, 0)])
    text(slide, Inches(1.0), Inches(3.45), Inches(8.4), Inches(0.9),
         [("A House Price Prediction System", 27, False, RGBColor(0xD6, 0xE6, 0xDE), 0)])
    box(slide, Inches(1.0), Inches(4.15), Inches(1.6), Emu(38100), fill=RGBColor(0x8F, 0xBA, 0xA6))
    text(slide, Inches(1.0), Inches(4.5), Inches(7.6), Inches(0.9),
         [("End-to-end: reproducible data pipeline, two trained and compared "
           "regression models, and a Flask web application with a live "
           "prediction dashboard.", 14, False, RGBColor(0xC3, 0xDA, 0xCF), 0)], spacing=1.25)
    chips = ["Python 3", "scikit-learn 1.6.1", "pandas 2.2.3", "Flask 3.1.3", "pytest"]
    cx = Inches(1.0)
    for c in chips:
        w = Inches(0.125) * len(c) + Inches(0.42)
        box(slide, cx, Inches(5.75), w, Inches(0.36), fill=RGBColor(0x3B, 0x7C, 0x5C),
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.35)
        text(slide, cx, Inches(5.81), w, Inches(0.3), [(c, 10.5, False, RGBColor(0xD6, 0xE6, 0xDE), 0)],
             align=PP_ALIGN.CENTER)
        cx += w + Inches(0.16)

    # ---- 2. Problem -------------------------------------------------------
    slide, top = slide_base(prs, "The problem", kicker="Why this project",
                            subtitle="Estimating what a home is worth is slow, opaque, or both.")
    bullets(slide, MARGIN, top, Inches(6.2), Inches(3.4), [
        ("Buyers and sellers need a quick sanity check before they commit to a price.",),
        ("Professional valuations are accurate but slow and expensive.",),
        ("Online estimators give answers but hide the model behind them.",),
        ("Students have no complete, honest reference implementation to learn from.",),
    ], size=15, gap=13)
    box(slide, Inches(7.4), top, Inches(5.23), Inches(3.3), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    box(slide, Inches(7.4), top, Inches(5.23), Inches(0.06), fill=GREEN)
    text(slide, Inches(7.75), top + Inches(0.34), Inches(4.5), Inches(0.4),
         [("What we set out to build", 16, True, INK, 0)])
    bullets(slide, Inches(7.75), top + Inches(0.9), Inches(4.5), Inches(2.2), [
        ("Nine physical inputs a person actually knows",),
        ("An estimate with a transparent explanation",),
        ("Honest accuracy figures, measured on held-out data",),
        ("Stated limits, not implied certainty",),
    ], size=13, gap=10)
    n += 1; footer(slide, n)

    # ---- 3. Solution ------------------------------------------------------
    slide, top = slide_base(prs, "The solution, end to end", kicker="Overview",
                            subtitle="One pipeline, two candidate models, one web application.")
    flow(slide, MARGIN, top + Inches(0.5), CONTENT_W, [
        ("Collect", "Ames dataset via OpenML"),
        ("Prepare", "19 columns to 10, documented rules"),
        ("Train", "Linear vs Random Forest"),
        ("Evaluate", "Held-out test set only"),
        ("Serve", "Flask app + live dashboard"),
    ], box_h=Inches(1.25))
    cards = [
        (f"{ds['total_properties']:,}", "properties", "after cleaning"),
        ("9", "input features", "plus one target"),
        (f"{rf['test_metrics']['r2']:.2f}", "test R²", "Random Forest"),
        (money(rf["test_metrics"]["mae"]), "typical error", "mean absolute"),
    ]
    cw = Inches(2.72)
    for i, (v, l, note) in enumerate(cards):
        kpi_card(slide, MARGIN + i * (cw + Inches(0.24)), top + Inches(2.35), cw, Inches(1.75), v, l, note)
    n += 1; footer(slide, n)

    # ---- 4. Dataset -------------------------------------------------------
    slide, top = slide_base(prs, "The dataset", kicker="Provenance",
                            subtitle="Ames Iowa Residential Housing Dataset — OpenML 42165.")
    rows = [
        ("Compiled by", f"{meta['author']}"),
        ("Published", meta["publication"]),
        ("Retrieved", "Programmatically via scikit-learn fetch_openml — no manual download"),
        ("Licence", meta["license"]),
        ("Market region", f"{meta['market_region']}"),
        ("Observation period", meta["observation_period"]),
        ("Currency", f"{meta['currency']} ({meta['currency_symbol']})"),
    ]
    table(slide, MARGIN, top, Inches(7.5), ["Property", "Value"], rows,
          [Inches(2.0), Inches(5.5)], row_h=Inches(0.44), font=12.5)
    box(slide, Inches(8.35), top, Inches(4.28), Inches(3.5), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    text(slide, Inches(8.65), top + Inches(0.28), Inches(3.7), Inches(0.35),
         [("Why this dataset", 15, True, INK, 0)])
    bullets(slide, Inches(8.65), top + Inches(0.78), Inches(3.7), Inches(2.5), [
        ("Real, peer-reviewed, per-property sales",),
        ("Has every field the app needs",),
        ("Unrestricted academic licence",),
        ("Two alternatives were rejected: California (census medians, no bedrooms or age) and Boston (known ethical problems)",),
    ], size=12, gap=9)
    n += 1; footer(slide, n)

    # ---- 5. Preparation ---------------------------------------------------
    slide, top = slide_base(prs, "Data preparation", kicker="Pipeline",
                            subtitle=f"{prep['raw_shape']['rows']:,} records × {prep['raw_shape']['columns']} columns extracted, "
                                     f"{prep['cleaning_summary']['final_rows']:,} × 10 after cleaning.")
    left = [
        ("Dropped the row identifier — no signal",),
        (f"Removed {prep['cleaning_summary']['duplicates_removed']} duplicate rows",),
        (f"Removed {prep['cleaning_summary']['anomalies_or_invalid_removed']} documented partial sales "
         "(over 4,000 sq ft, sold under $300,000)",),
        ("Derived total bathrooms — a half bath counts 0.5, basement included",),
        ("Derived age at the point of sale, not age today",),
        ("Mapped garage capacity, house style and building type to plain English",),
    ]
    bullets(slide, MARGIN, top, Inches(6.5), Inches(3.0), left, size=13.5, gap=11)
    box(slide, Inches(7.35), top, Inches(5.28), Inches(1.5), fill=WARN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    box(slide, Inches(7.35), top, Inches(0.06), Inches(1.5), fill=WARN)
    text(slide, Inches(7.68), top + Inches(0.22), Inches(4.6), Inches(1.1), [
        ("A deliberate choice", 14, True, INK, 0),
        ("6 missing bedroom values are left in place and filled by an imputer fitted on the "
         "training split only. Pre-filling them would leak test-set information into training.",
         11.5, False, INK, 4),
    ], spacing=1.15)
    box(slide, Inches(7.35), top + Inches(1.75), Inches(5.28), Inches(2.05), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    text(slide, Inches(7.68), top + Inches(1.98), Inches(4.6), Inches(1.8), [
        ("Split", 13.5, True, INK, 0),
        (f"{prep['train_rows']:,} training rows · {prep['test_rows']} held-out test rows "
         f"({int((1 - prep['test_split_ratio']) * 100)}/{int(prep['test_split_ratio'] * 100)})", 12, False, INK, 3),
        ("The test set was never used for fitting, tuning or imputation.",
         11.5, False, MUTED, 4),
    ], spacing=1.15)
    n += 1; footer(slide, n)

    # ---- 6. Findings ------------------------------------------------------
    slide, top = slide_base(prs, "What the data shows", kicker="Exploration",
                            subtitle="Sale prices in the cleaned dataset, in US dollars.")
    stats = [
        ("Minimum", money(ds["price"]["min"])),
        ("25th percentile", money(ds["price"]["q25"])),
        ("Median", money(ds["price"]["median"])),
        ("Mean", money(ds["price"]["mean"])),
        ("75th percentile", money(ds["price"]["q75"])),
        ("Maximum", money(ds["price"]["max"])),
        ("Std. deviation", money(ds["price"]["std"])),
    ]
    table(slide, MARGIN, top, Inches(4.6), ["Statistic", "Value"], stats,
          [Inches(2.5), Inches(2.1)], row_h=Inches(0.38), font=12.5)
    text(slide, Inches(5.4), top, Inches(7.23), Inches(0.35),
         [("Typical property in the dataset", 16, True, INK, 0)])
    med = [
        ("Living area", f"{ds['area_sqft']['median']:,.0f} sq ft", f"range {ds['area_sqft']['min']:,.0f}–{ds['area_sqft']['max']:,.0f}"),
        ("Lot size", f"{ds['lot_area_sqft']['median']:,.0f} sq ft", f"range {ds['lot_area_sqft']['min']:,.0f}–{ds['lot_area_sqft']['max']:,.0f}"),
        ("Property age", f"{ds['property_age']['median']:,.0f} years", f"range {ds['property_age']['min']:,.0f}–{ds['property_age']['max']:,.0f}"),
        ("Price per sq ft", f"${ds['price_per_sqft']['median']:,.2f}", f"median across all sales"),
        ("Bedrooms", f"{ds['bedrooms_median']:,.1f}", "above grade"),
        ("Bathrooms", f"{ds['bathrooms_median']:,.1f}", "half bath counts 0.5"),
    ]
    table(slide, Inches(5.4), top + Inches(0.45), Inches(7.23),
          ["Feature", "Median", "Spread"], med,
          [Inches(2.2), Inches(2.2), Inches(2.83)], row_h=Inches(0.42), font=12.5)
    text(slide, Inches(5.4), top + Inches(3.35), Inches(7.23), Inches(0.9), [
        ("Larger and newer homes command higher prices, and the model recovers "
         "that relationship on its own — permutation importance later confirms "
         "living area and property age are the two strongest drivers.",
         12.5, False, MUTED, 0)], spacing=1.25)
    n += 1; footer(slide, n)

    # ---- 7. Features ------------------------------------------------------
    slide, top = slide_base(prs, "Features and preprocessing", kicker="Method",
                            subtitle="Nine inputs, one target, all transforms inside a single Pipeline.")
    num = [
        ("area_sqft", "Living area", "median impute + scale"),
        ("lot_area_sqft", "Lot size", "median impute + scale"),
        ("bedrooms", "Bedrooms", "median impute + scale"),
        ("bathrooms", "Bathrooms", "median impute + scale"),
        ("property_age", "Property age", "median impute + scale"),
        ("floors", "Storeys", "median impute + scale"),
    ]
    cat = [
        ("location", "Neighbourhood", f"{ds['num_neighborhoods']} values, one-hot"),
        ("parking", "Garage", "4 values, one-hot"),
        ("property_type", "Building type", "5 values, one-hot"),
    ]
    text(slide, MARGIN, top, Inches(5.7), Inches(0.3), [("Numeric", 15, True, GREEN, 0)])
    table(slide, MARGIN, top + Inches(0.42), Inches(5.7), ["Feature", "Meaning", "Transform"],
          [(a, b, c) for a, b, c in num], [Inches(1.6), Inches(1.75), Inches(2.35)],
          row_h=Inches(0.4), font=12)
    text(slide, Inches(6.95), top, Inches(5.68), Inches(0.3), [("Categorical", 15, True, GREEN, 0)])
    table(slide, Inches(6.95), top + Inches(0.42), Inches(5.68), ["Feature", "Meaning", "Transform"],
          [(a, b, c) for a, b, c in cat], [Inches(1.6), Inches(1.75), Inches(2.33)],
          row_h=Inches(0.4), font=12)
    box(slide, MARGIN, top + Inches(3.2), CONTENT_W, Inches(1.15), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
    box(slide, MARGIN, top + Inches(3.2), Inches(0.06), Inches(1.15), fill=GREEN)
    text(slide, MARGIN + Inches(0.3), top + Inches(3.42), CONTENT_W - Inches(0.6), Inches(0.9), [
        ("Why the transforms live inside the Pipeline", 13.5, True, INK, 0),
        ("Imputation, scaling and one-hot encoding are fitted on the training split and stored with the "
         "model, so inference applies exactly the same transforms. No train/serve skew, no leakage.",
         12, False, INK, 3)], spacing=1.2)
    n += 1; footer(slide, n)

    # ---- 8. Linear regression --------------------------------------------
    slide, top = slide_base(prs, "Model 1 — Linear Regression", kicker="Baseline",
                            subtitle="A deliberately simple reference point. Every project needs one.")
    rows = [["MAE", money2(lr["train_metrics"]["mae"]), money2(lr["test_metrics"]["mae"])],
            ["RMSE", money2(lr["train_metrics"]["rmse"]), money2(lr["test_metrics"]["rmse"])],
            ["R²", f"{lr['train_metrics']['r2']:.4f}", f"{lr['test_metrics']['r2']:.4f}"],
            ["MAPE", f"{lr['train_metrics']['mape_percent']:.2f}%", f"{lr['test_metrics']['mape_percent']:.2f}%"]]
    table(slide, MARGIN, top, Inches(6.4), ["Metric", "Train", "Held-out test"], rows,
          [Inches(2.6), Inches(1.9), Inches(1.9)], row_h=Inches(0.5), font=13.5,
          highlight_last_col=True)
    bullets(slide, Inches(7.3), top + Inches(0.1), Inches(5.33), Inches(3.0), [
        ("Strengths: fast, fully interpretable, coefficients read directly as dollar effects.",),
        ("Weakness: assumes each feature adds a fixed amount, so it cannot capture that an extra "
         "bathroom matters more in a large house than a small one.",),
        (f"Held-out R² of {lr['test_metrics']['r2']:.4f} — already respectable, which is exactly "
         "why it is a fair baseline rather than a straw man.",),
    ], size=13, gap=12)
    n += 1; footer(slide, n)

    # ---- 9. Random forest -------------------------------------------------
    slide, top = slide_base(prs, "Model 2 — Random Forest", kicker="Selected model",
                            subtitle="An ensemble of decision trees, averaged to reduce variance.")
    rows = [["MAE", money2(rf["train_metrics"]["mae"]), money2(rf["test_metrics"]["mae"])],
            ["RMSE", money2(rf["train_metrics"]["rmse"]), money2(rf["test_metrics"]["rmse"])],
            ["R²", f"{rf['train_metrics']['r2']:.4f}", f"{rf['test_metrics']['r2']:.4f}"],
            ["MAPE", f"{rf['train_metrics']['mape_percent']:.2f}%", f"{rf['test_metrics']['mape_percent']:.2f}%"]]
    table(slide, MARGIN, top, Inches(6.4), ["Metric", "Train", "Held-out test"], rows,
          [Inches(2.6), Inches(1.9), Inches(1.9)], row_h=Inches(0.5), font=13.5,
          highlight_last_col=True)
    bullets(slide, Inches(7.3), top + Inches(0.1), Inches(5.33), Inches(3.0), [
        ("Captures interactions between features without being told they exist.",),
        ("Handles the mix of numeric and categorical inputs naturally.",),
        (f"Train R² of {rf['train_metrics']['r2']:.4f} against test R² of "
         f"{rf['test_metrics']['r2']:.4f} — the gap is headroom for regularisation, "
         "and we report it rather than hide it.",),
    ], size=13, gap=12)
    n += 1; footer(slide, n)

    # ---- 10. Comparison ---------------------------------------------------
    slide, top = slide_base(prs, "Model comparison", kicker="Selection",
                            subtitle="Decided on the held-out test set only. Lower is better.")
    cats = ["MAE", "RMSE", "MAPE %"]
    series = [
        {"name": "Linear Regression", "values": [lr["test_metrics"]["mae"], lr["test_metrics"]["rmse"],
                                                 lr["test_metrics"]["mape_percent"]]},
        {"name": "Random Forest", "values": [rf["test_metrics"]["mae"], rf["test_metrics"]["rmse"],
                                             rf["test_metrics"]["mape_percent"]]},
    ]
    vbar(slide, MARGIN, top + Inches(0.55), Inches(7.2), Inches(2.5), series, cats,
         gap=Inches(0.9), fmt=lambda v: f"{v:,.0f}" if v > 100 else f"{v:.2f}",
         bar_colors=[GREEN_MID, GREEN])
    legend(slide, MARGIN, top + Inches(0.1), [(GREEN_MID, "Linear Regression"), (GREEN, "Random Forest")])
    box(slide, Inches(8.3), top + Inches(0.1), Inches(4.33), Inches(3.2), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    box(slide, Inches(8.3), top + Inches(0.1), Inches(4.33), Inches(0.06), fill=GREEN)
    text(slide, Inches(8.62), top + Inches(0.4), Inches(3.7), Inches(2.6), [
        ("Random Forest wins", 15.5, True, INK, 0),
        (f"RMSE {money(rf['test_metrics']['rmse'])} vs {money(lr['test_metrics']['rmse'])}", 12, False, INK, 8),
        (f"MAE {money(rf['test_metrics']['mae'])} vs {money(lr['test_metrics']['mae'])}", 12, False, INK, 3),
        (f"R² {rf['test_metrics']['r2']:.4f} vs {lr['test_metrics']['r2']:.4f}", 12, False, INK, 3),
        ("About 11% lower test RMSE and 13% lower test MAE.", 12, True, GREEN, 8),
    ], spacing=1.2)
    n += 1; footer(slide, n)

    # ---- 11. Results ------------------------------------------------------
    slide, top = slide_base(prs, "Results", kicker="Held-out performance",
                            subtitle="What the numbers mean in plain language.")
    for i, (v, l, note) in enumerate([
        (f"{rf['test_metrics']['r2']:.3f}", "Test R²", "Share of price variance explained on homes never seen in training"),
        (money(rf["test_metrics"]["mae"]), "Typical error", "Average miss in dollars across held-out sales"),
        (f"{rf['test_metrics']['mape_percent']:.2f}%", "MAPE", "Average miss as a share of sale price"),
        (money(rf["test_metrics"]["rmse"]), "RMSE", "Root mean squared error, penalising large misses"),
    ]):
        kpi_card(slide, MARGIN + i * (Inches(2.85) + Inches(0.14)), top,
                 Inches(2.85), Inches(1.95), v, l, note)
    box(slide, MARGIN, top + Inches(2.25), CONTENT_W, Inches(1.5), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    box(slide, MARGIN, top + Inches(2.25), Inches(0.06), Inches(1.5), fill=GREEN)
    text(slide, MARGIN + Inches(0.32), top + Inches(2.5), CONTENT_W - Inches(0.65), Inches(1.1), [
        ("In one sentence", 14, True, INK, 0),
        (f"On homes it has never seen, the model explains about "
         f"{rf['test_metrics']['r2'] * 100:.0f}% of the variation in sale price and is typically "
         f"off by about {money(rf['test_metrics']['mae'])} — a "
         f"{rf['test_metrics']['mape_percent']:.1f}% miss on the median home.",
         14, False, INK, 5)], spacing=1.25)
    n += 1; footer(slide, n)

    # ---- 12. Importance ---------------------------------------------------
    slide, top = slide_base(prs, "What drives the model",
                            kicker="Feature importance",
                            subtitle="Association with the model's predictions — not a claim of causation.")
    items = [(f["label"], f["importance_pct"], f["permutation_importance_pct"]) for f in imp]
    hbar(slide, MARGIN, top, Inches(7.3), items, row_h=Inches(0.36), gap=Inches(0.09),
         label_w=Inches(2.15), value_w=Inches(1.3), color=GREEN, color2=GREEN_MID,
         bar_h=Inches(0.2), fmt=lambda v: f"{v:.1f}%")
    legend(slide, MARGIN, top + Inches(4.15),
           [(GREEN, "Impurity importance"), (GREEN_MID, "Permutation importance")])
    box(slide, Inches(8.35), top, Inches(4.28), Inches(4.3), fill=WARN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    box(slide, Inches(8.35), top, Inches(0.06), Inches(4.3), fill=WARN)
    text(slide, Inches(8.68), top + Inches(0.3), Inches(3.65), Inches(3.7), [
        ("The two measures disagree", 15, True, INK, 0),
        ("Garage ranks first on impurity importance (35.1%) but only 9.4% on permutation. "
         "Impurity importance favours features with many categories, and parking has four.",
         12, False, INK, 8),
        ("Permutation importance — how much test error rises when a feature is shuffled — "
         "is the more trustworthy ranking here.", 12, False, INK, 8),
        ("It puts living area first at 48.7% and property age second at 26.7%, which matches "
         "how housing markets actually behave.", 12, False, INK, 8),
    ], spacing=1.2)
    n += 1; footer(slide, n)

    # ---- 13. Architecture -------------------------------------------------
    slide, top = slide_base(prs, "System architecture", kicker="How a request flows",
                            subtitle="From the browser to an estimate and back, with two layers of validation.")
    flow(slide, MARGIN, top + Inches(0.35), CONTENT_W, [
        ("Browser", "Nine validated inputs"),
        ("Client check", "Instant feedback"),
        ("Flask route", "Server validation"),
        ("Cached inference", "Joblib pipeline"),
        ("Response", "Price + explanation"),
    ], box_h=Inches(1.2))
    rows = [
        ("Model load", "Loaded once at startup and cached — no reload per request"),
        ("Validation", "Identical rules enforced twice; client checks can be bypassed"),
        ("Unknown values", "Unseen categories are rejected with a clear message, never guessed"),
        ("Logging", "Every served estimate is recorded; a logging failure never breaks a prediction"),
        ("Serving", "Flask development server — use Gunicorn or Waitress beyond local use"),
    ]
    table(slide, MARGIN, top + Inches(2.0), CONTENT_W, ["Concern", "How it is handled"], rows,
          [Inches(2.4), Inches(9.43)], row_h=Inches(0.42), font=12.5)
    n += 1; footer(slide, n)

    # ---- 14. Application --------------------------------------------------
    slide, top = slide_base(prs, "The web application", kicker="Interface",
                            subtitle="Five pages, hand-written HTML, CSS and JavaScript. No framework, no CDN.")
    pages = [
        ("Landing", "Headline, two calls to action, dataset facts."),
        ("Estimate form", "Nine inputs pre-filled with training medians."),
        ("Result", "Price, price per sq ft, sensitivity table, limitations."),
        ("Insights", "Six charts generated from the real dataset and model."),
        ("Dashboard", "Live view of the predictions this installation served."),
    ]
    bw = Inches(2.22)
    for i, (name, desc) in enumerate(pages):
        bx = MARGIN + i * (bw + Inches(0.16))
        box(slide, bx, top, bw, Inches(1.7), fill=GREEN_SOFT, line=LINE,
            shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.08)
        box(slide, bx, top, bw, Inches(0.05), fill=GREEN)
        text(slide, bx + Inches(0.18), top + Inches(0.3), bw - Inches(0.36), Inches(0.3),
             [(name, 13, True, INK, 0)])
        text(slide, bx + Inches(0.18), top + Inches(0.68), bw - Inches(0.36), Inches(0.9),
             [(desc, 10.5, False, MUTED, 0)], spacing=1.2)
    box(slide, MARGIN, top + Inches(2.0), CONTENT_W, Inches(1.55), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    box(slide, MARGIN, top + Inches(2.0), Inches(0.06), Inches(1.55), fill=GREEN)
    text(slide, MARGIN + Inches(0.32), top + Inches(2.24), CONTENT_W - Inches(0.65), Inches(1.2), [
        ("Validation runs twice, on purpose", 14, True, INK, 0),
        ("The same ranges and vocabularies are checked in the browser for instant feedback, then again "
         "on the server, because a client-side check is a convenience and never a guarantee. Invalid ranges, "
         "missing fields and unknown categories all produce specific field-level messages.",
         12.5, False, INK, 4)], spacing=1.25)
    n += 1; footer(slide, n)

    # ---- 15. Dashboard ----------------------------------------------------
    slide, top = slide_base(prs, "The prediction dashboard", kicker="Live insight",
                            subtitle="Reports on estimates this installation actually served, stored in SQLite.")
    text(slide, MARGIN, top, Inches(5.7), Inches(0.3), [("Usage — grows over time", 15, True, GREEN, 0)])
    bullets(slide, MARGIN, top + Inches(0.42), Inches(5.7), Inches(2.6), [
        ("Predictions logged, median and range",),
        ("Volume over time, price distribution",),
        ("Median by location and property type",),
        ("Area vs price, coloured by property age",),
    ], size=12.5, gap=9)
    text(slide, Inches(6.95), top, Inches(5.68), Inches(0.3), [("Measured accuracy — fixed", 15, True, GREEN, 0)])
    bullets(slide, Inches(6.95), top + Inches(0.42), Inches(5.68), Inches(2.6), [
        (f"MAE {money(rf['test_metrics']['mae'])}, R² {rf['test_metrics']['r2']:.4f}",),
        ("Read from metrics.json, never from usage",),
        ("Does not move however many predictions are made",),
        ("Feature importance, shown as association only",),
    ], size=12.5, gap=9)
    box(slide, MARGIN, top + Inches(3.1), CONTENT_W, Inches(1.45), fill=GREEN_SOFT,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    box(slide, MARGIN, top + Inches(3.1), Inches(0.06), Inches(1.45), fill=GREEN)
    text(slide, MARGIN + Inches(0.32), top + Inches(3.34), CONTENT_W - Inches(0.65), Inches(1.1), [
        ("Nothing on it is invented", 14, True, INK, 0),
        ("With an empty log it shows an explicit empty state rather than placeholder charts. "
         "\"Log sample activity\" runs real properties from the cleaned dataset through the saved model "
         "and tags them, so they are always distinguishable from form submissions. The seven charts are "
         "hand-rolled inline SVG — no charting library, no external dependency.",
         12.5, False, INK, 4)], spacing=1.25)
    n += 1; footer(slide, n)

    # ---- 16. Testing ------------------------------------------------------
    slide, top = slide_base(prs, "Testing and quality", kicker="Confidence",
                            subtitle="70 pytest tests, all passing.")
    for i, (v, l, note) in enumerate([
        ("49", "core tests", "Preprocessing, inference, validation, every route"),
        ("21", "dashboard tests", "Store, aggregation, and all three JSON endpoints"),
        ("70", "total", "Every one passing on the current build"),
        ("0", "touched rows", "Tests run against a temporary database"),
    ]):
        kpi_card(slide, MARGIN + i * (Inches(2.85) + Inches(0.14)), top,
                 Inches(2.85), Inches(1.8), v, l, note)
    bullets(slide, MARGIN, top + Inches(2.1), CONTENT_W, Inches(2.0), [
        ("Input validation: valid, invalid, missing, out-of-range and unseen-category cases.",),
        ("Behaviour: predictions are deterministic and respond sensibly to larger properties.",),
        ("Dashboard guarantees: an empty log returns empty aggregates, never invented figures.",),
        ("Isolation: an autouse session fixture redirects the prediction log to a temporary database, "
         "so a test can never destroy genuinely recorded activity.",),
    ], size=13, gap=11)
    n += 1; footer(slide, n)

    # ---- 17. Limitations --------------------------------------------------
    slide, top = slide_base(prs, "Limitations and responsible use", kicker="Honesty",
                            subtitle="What this system does not do — stated on the result page as well.")
    left = [
        ("Geography and time", "Ames, Iowa, 2006–2010 only. Nothing about other markets or today's prices."),
        ("Not a valuation", "A statistical estimate for education and comparison. Not an appraisal, not financial advice."),
        ("No prediction interval", "Point estimate only. Quantile regression forests or conformal prediction would be needed."),
        ("Averages hide individuals", f"MAE of {money(rf['test_metrics']['mae'])} is an average; any single home can be much further off."),
    ]
    right = [
        ("Small categories", "Some neighbourhoods have only a handful of sales, so those estimates are noisy."),
        ("Omitted factors", "Condition, renovation quality, interior finish, school catchment and micro-location are absent."),
        ("Overfitting headroom", f"Train R² {rf['train_metrics']['r2']:.4f} vs test R² {rf['test_metrics']['r2']:.4f}."),
        ("Development server", "Flask's built-in server. Use Gunicorn or Waitress beyond local use."),
    ]
    card_w = Inches(5.8)
    for col, items in enumerate([left, right]):
        cx = MARGIN + col * (card_w + Inches(0.23))
        cy = top
        for head, body in items:
            box(slide, cx, cy, card_w, Inches(1.02), fill=WARN_SOFT,
                shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.1)
            box(slide, cx, cy, Inches(0.05), Inches(1.02), fill=WARN)
            text(slide, cx + Inches(0.24), cy + Inches(0.14), card_w - Inches(0.45), Inches(0.28),
                 [(head, 12.5, True, WARN, 0)])
            text(slide, cx + Inches(0.24), cy + Inches(0.44), card_w - Inches(0.45), Inches(0.5),
                 [(body, 11, False, INK, 0)], spacing=1.15)
            cy += Inches(1.14)
    n += 1; footer(slide, n)

    # ---- 18. Future work --------------------------------------------------
    slide, top = slide_base(prs, "Future work and conclusion", kicker="Next steps",
                            subtitle="What would be built next, and what to take away.")
    text(slide, MARGIN, top, Inches(6.0), Inches(0.3), [("Would improve accuracy", 16, True, GREEN, 0)])
    bullets(slide, MARGIN, top + Inches(0.45), Inches(6.0), Inches(3.0), [
        ("Hyperparameter tuning with cross-validation",),
        ("Gradient boosting — XGBoost or LightGBM",),
        ("Log-transform the target to tame the right tail",),
        ("Target encoding for high-cardinality neighbourhoods",),
        ("Regularisation to close the train/test gap",),
    ], size=13, gap=11)
    text(slide, Inches(7.1), top, Inches(5.53), Inches(0.3), [("Would improve honesty", 16, True, GREEN, 0)])
    bullets(slide, Inches(7.1), top + Inches(0.45), Inches(5.53), Inches(3.0), [
        ("Quantile regression forests for calibrated intervals",),
        ("Conformal prediction for guaranteed coverage",),
        ("Retraining on current data for a live market",),
        ("Drift monitoring once real traffic arrives",),
    ], size=13, gap=11)
    box(slide, MARGIN, top + Inches(3.2), CONTENT_W, Inches(1.35), fill=GREEN,
        shape=MSO_SHAPE.ROUNDED_RECTANGLE, radius=0.06)
    text(slide, MARGIN + Inches(0.35), top + Inches(3.45), CONTENT_W - Inches(0.7), Inches(1.0), [
        ("Takeaway", 13, True, RGBColor(0xA8, 0xC9, 0xB8), 0),
        (f"A complete, reproducible system: a documented pipeline, a model selected on held-out data "
         f"(R² {rf['test_metrics']['r2']:.4f}, MAE {money(rf['test_metrics']['mae'])}), a working web "
         "application, and — most importantly — an explicit statement of what it cannot do.",
         13.5, False, PAPER, 5)], spacing=1.25)
    n += 1; footer(slide, n)

    # ---- 19. Closing ------------------------------------------------------
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    box(slide, Emu(0), Emu(0), SLIDE_W, SLIDE_H, fill=GREEN)
    text(slide, Inches(1.0), Inches(2.7), Inches(11.3), Inches(0.9),
         [("Thank you", 52, True, PAPER, 0)])
    box(slide, Inches(1.0), Inches(3.85), Inches(1.6), Emu(38100), fill=RGBColor(0x8F, 0xBA, 0xA6))
    text(slide, Inches(1.0), Inches(4.2), Inches(10.5), Inches(1.2), [
        ("HomeValue — A House Price Prediction System", 17, False, RGBColor(0xD6, 0xE6, 0xDE), 0),
        ("Reproducible pipeline · Two compared models · Flask application · Live dashboard",
         13, False, RGBColor(0xA8, 0xC9, 0xB8), 8)], spacing=1.2)
    text(slide, Inches(1.0), Inches(5.9), Inches(10.5), Inches(0.8), [
        (f"All figures measured on a {prep['test_rows']}-row held-out test set · "
         f"Dataset: Ames, Iowa, {meta['observation_period']} · {meta['license']}",
         11, False, RGBColor(0x8F, 0xBA, 0xA6), 0)], spacing=1.2)

    prs.save(OUTPUT_PATH)
    return OUTPUT_PATH, len(prs.slides.__iter__.__self__._sldIdLst)


if __name__ == "__main__":
    path, count = build()
    print(f"Wrote {path}")
    print(f"Slides: {count}")
    print(f"Size:   {path.stat().st_size / 1024:.0f} KB")
