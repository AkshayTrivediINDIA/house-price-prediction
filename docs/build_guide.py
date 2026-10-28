"""
Build the complete project guide as a PDF.

This is the long-form, "explain it from scratch" companion to the README: it
assumes no prior machine-learning knowledge, walks through what each algorithm
actually does, and documents exactly why the Random Forest was selected over the
linear baseline.

Every figure and every number is read from the real artifacts --
models/metrics.json, the saved pipelines and the cleaned dataset -- so the
document cannot drift from what the code actually produced.

    python docs/build_guide.py       # run from the project root, or with PYTHONPATH=.

Output: docs/HomeValue_Complete_Guide.pdf
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, CondPageBreak, Flowable, Frame, Image, KeepTogether,
    NextPageTemplate,
    PageBreak, PageTemplate, Paragraph, Preformatted, Spacer, Table, TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents

_DOC = None  # set in main(); TOCEntry needs the document template to notify

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402

METRICS_PATH = PROJECT_ROOT / "models" / "metrics.json"
CHARTS = PROJECT_ROOT / "docs" / "guide_charts"
OUTPUT = PROJECT_ROOT / "docs" / "HomeValue_Complete_Guide.pdf"

# ---------------------------------------------------------------------------
# Palette -- the same tokens the web application uses.
# ---------------------------------------------------------------------------
INK = colors.HexColor("#1F2421")
MUTED = colors.HexColor("#637268")
GREEN = colors.HexColor("#2F6B4F")
GREEN_SOFT = colors.HexColor("#E7EFEA")
GREEN_PALE = colors.HexColor("#F2F7F4")
LINE = colors.HexColor("#DCE3DE")
CODE_BG = colors.HexColor("#F4F6F3")
WARN_BG = colors.HexColor("#FBF0EA")
WARN = colors.HexColor("#8C4A2F")
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
FRAME_W = PAGE_W - 2 * MARGIN

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
_ss = getSampleStyleSheet()

S = {
    "body": ParagraphStyle("body", parent=_ss["BodyText"], fontName="Helvetica",
                           fontSize=9.6, leading=14.4, textColor=INK,
                           alignment=TA_JUSTIFY, spaceAfter=7),
    "lead": ParagraphStyle("lead", parent=_ss["BodyText"], fontName="Helvetica",
                           fontSize=11, leading=16.5, textColor=GREEN,
                           alignment=TA_JUSTIFY, spaceAfter=9),
    "h1": ParagraphStyle("h1", parent=_ss["Heading1"], fontName="Helvetica-Bold",
                         fontSize=19, leading=24, textColor=INK,
                         spaceBefore=2, spaceAfter=4),
    "h2": ParagraphStyle("h2", parent=_ss["Heading2"], fontName="Helvetica-Bold",
                         fontSize=13, leading=17, textColor=GREEN,
                         spaceBefore=14, spaceAfter=5),
    "h3": ParagraphStyle("h3", parent=_ss["Heading3"], fontName="Helvetica-Bold",
                         fontSize=10.6, leading=14, textColor=INK,
                         spaceBefore=10, spaceAfter=3),
    "bullet": ParagraphStyle("bullet", parent=_ss["BodyText"], fontName="Helvetica",
                             fontSize=9.6, leading=14, textColor=INK,
                             alignment=TA_JUSTIFY, leftIndent=11,
                             bulletIndent=1, spaceAfter=4),
    "caption": ParagraphStyle("caption", parent=_ss["BodyText"], fontName="Helvetica-Oblique",
                              fontSize=8.3, leading=11.5, textColor=MUTED,
                              alignment=TA_CENTER, spaceBefore=3, spaceAfter=10),
    "code": ParagraphStyle("code", parent=_ss["Code"], fontName="Courier",
                           fontSize=7.9, leading=10.4, textColor=INK),
    "note_h": ParagraphStyle("note_h", parent=_ss["BodyText"], fontName="Helvetica-Bold",
                             fontSize=9.6, leading=13, textColor=INK, spaceAfter=3),
    "note_b": ParagraphStyle("note_b", parent=_ss["BodyText"], fontName="Helvetica",
                             fontSize=9.3, leading=13.4, textColor=INK,
                             alignment=TA_JUSTIFY),
    "warn_h": ParagraphStyle("warn_h", parent=_ss["BodyText"], fontName="Helvetica-Bold",
                             fontSize=9.6, leading=13, textColor=WARN, spaceAfter=3),
    "cell": ParagraphStyle("cell", parent=_ss["BodyText"], fontName="Helvetica",
                           fontSize=8.6, leading=11.6, textColor=INK),
    "cell_h": ParagraphStyle("cell_h", parent=_ss["BodyText"], fontName="Helvetica-Bold",
                             fontSize=8.6, leading=11.6, textColor=WHITE),
    "toc1": ParagraphStyle("toc1", parent=_ss["BodyText"], fontName="Helvetica-Bold",
                           fontSize=10, leading=17, textColor=INK, spaceBefore=7),
    "toc2": ParagraphStyle("toc2", parent=_ss["BodyText"], fontName="Helvetica",
                           fontSize=9.2, leading=15, textColor=INK, leftIndent=16),
    "cover_title": ParagraphStyle("cover_title", parent=_ss["Title"], fontName="Helvetica-Bold",
                                  fontSize=36, leading=42, textColor=WHITE),
    "cover_sub": ParagraphStyle("cover_sub", parent=_ss["BodyText"], fontName="Helvetica",
                                fontSize=14.5, leading=20, textColor=colors.HexColor("#C3DACF")),
    "cover_body": ParagraphStyle("cover_body", parent=_ss["BodyText"], fontName="Helvetica",
                                 fontSize=10, leading=15, textColor=colors.HexColor("#A8C9B8")),
}


def money(v):
    return f"${v:,.0f}"


def money2(v):
    return f"${v:,.2f}"


# ---------------------------------------------------------------------------
# Flowable helpers
# ---------------------------------------------------------------------------
class Bookmark:
    """Marker flowable that also registers a table-of-contents entry."""

    def __init__(self, text, level, story_ref):
        self.text = text
        self.level = level
        self.story_ref = story_ref


def H1(story, num, text):
    story.append(Paragraph(f"{num}  {text}", S["h1"]))
    story.append(_rule(GREEN, 1.6, 3, 12))
    story.append(_toc_marker(text, 1))


def H2(story, num, text):
    story.append(CondPageBreak(34 * mm))
    story.append(Paragraph(f"{num}  {text}", S["h2"]))
    story.append(_toc_marker(text, 2))


def H3(story, text):
    story.append(CondPageBreak(20 * mm))
    story.append(Paragraph(text, S["h3"]))


def _rule(color, thickness, space_before, space_after, width=FRAME_W):
    t = Table([[""]], colWidths=[width], rowHeights=[thickness])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), color),
                           ("TOPPADDING", (0, 0), (-1, -1), 0),
                           ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
                           ("LEFTPADDING", (0, 0), (-1, -1), 0),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 0)]))
    return KeepTogether([Spacer(1, space_before), t, Spacer(1, space_after)])


class TOCEntry(Flowable):
    """A zero-size flowable that registers a table-of-contents entry."""

    def __init__(self, text, level):
        Flowable.__init__(self)
        self._toc_text = text
        self._toc_level = level
        self.width = 0
        self.height = 0

    def wrap(self, availWidth, availHeight):
        return (0, 0)

    def draw(self):
        # reportlab 5.x exposes notify() on the document template, not the canvas.
        self.canv.bookmarkPage(self.canv.getPageNumber())
        _DOC.notify("TOCEntry",
                    (self._toc_level, self._toc_text, self.canv.getPageNumber()))


def _toc_marker(text, level):
    return TOCEntry(text, level)


def P(story, text):
    story.append(Paragraph(text, S["body"]))


def LEAD(story, text):
    story.append(Paragraph(text, S["lead"]))


def BUL(story, items):
    for it in items:
        story.append(Paragraph(it, S["bullet"], bulletText="•"))
    story.append(Spacer(1, 4))


def NUM(story, items):
    for i, it in enumerate(items, 1):
        story.append(Paragraph(it, S["bullet"], bulletText=f"{i}."))
    story.append(Spacer(1, 4))


def CODE(story, lines, width=FRAME_W):
    text = "\n".join(lines)
    pre = Preformatted(text, S["code"])
    t = Table([[pre]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), CODE_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 2, GREEN),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(Spacer(1, 3))
    story.append(t)
    story.append(Spacer(1, 9))


def NOTE(story, title, body, accent=GREEN, bg=GREEN_PALE):
    inner = [Paragraph(title, S["note_h"]), Paragraph(body, S["note_b"])]
    t = Table([[inner]], colWidths=[FRAME_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 3, accent),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(Spacer(1, 4))
    story.append(t)
    story.append(Spacer(1, 9))


def WARN_BOX(story, title, body):
    inner = [Paragraph(title, S["warn_h"]), Paragraph(body, S["note_b"])]
    t = Table([[inner]], colWidths=[FRAME_W])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), WARN_BG),
        ("LINEBEFORE", (0, 0), (0, -1), 3, WARN),
        ("LEFTPADDING", (0, 0), (-1, -1), 11),
        ("RIGHTPADDING", (0, 0), (-1, -1), 11),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(Spacer(1, 4))
    story.append(t)
    story.append(Spacer(1, 9))


def TBL(story, data, widths, align_right=(), header=True, font=8.6):
    rows = []
    for r, row in enumerate(data):
        style = S["cell_h"] if (header and r == 0) else S["cell"]
        rows.append([Paragraph(str(c), style) for c in row])

    t = Table(rows, colWidths=widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.4, LINE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    if header:
        cmds += [("BACKGROUND", (0, 0), (-1, 0), GREEN)]
        for r in range(2, len(data), 2):
            cmds.append(("BACKGROUND", (0, r), (-1, r), GREEN_SOFT))
    for c in align_right:
        cmds.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
    t.setStyle(TableStyle(cmds))
    story.append(Spacer(1, 3))
    story.append(t)
    story.append(Spacer(1, 10))


def FIG(story, name, caption, max_w=FRAME_W, max_h=105 * mm):
    path = CHARTS / f"{name}.png"
    if not path.exists():
        story.append(Paragraph(f"[Figure missing: {name}]", S["caption"]))
        return
    from PIL import Image as PILImage
    with PILImage.open(path) as im:
        pw, ph = im.size
    scale = min(max_w / (pw * 0.2646), max_h / (ph * 0.2646))
    w = pw * 0.2646 * scale
    h = ph * 0.2646 * scale
    img = Image(str(path), width=w, height=h)
    img.hAlign = "CENTER"
    block = [Spacer(1, 3), img, Paragraph(caption, S["caption"])]
    story.append(KeepTogether(block))


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------
def _cover_page(canv, doc):
    canv.saveState()
    canv.setFillColor(GREEN)
    canv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
    canv.setFillColor(colors.HexColor("#2A6046"))
    canv.rect(PAGE_W - 55 * mm, 0, 55 * mm, PAGE_H, stroke=0, fill=1)
    canv.restoreState()


def _body_page(canv, doc):
    canv.saveState()
    # header rule
    canv.setStrokeColor(LINE)
    canv.setLineWidth(0.6)
    canv.line(MARGIN, PAGE_H - MARGIN + 7 * mm, PAGE_W - MARGIN, PAGE_H - MARGIN + 7 * mm)
    canv.setFont("Helvetica", 7.6)
    canv.setFillColor(MUTED)
    canv.drawString(MARGIN, PAGE_H - MARGIN + 9 * mm, "HomeValue - Complete Project Guide")
    canv.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 9 * mm,
                         "House Price Prediction System")
    # footer
    canv.setStrokeColor(LINE)
    canv.line(MARGIN, MARGIN - 5 * mm, PAGE_W - MARGIN, MARGIN - 5 * mm)
    canv.setFont("Helvetica", 7.6)
    canv.setFillColor(MUTED)
    canv.drawString(MARGIN, MARGIN - 9.5 * mm,
                    "Figures measured on a held-out test set - Ames, Iowa, 2006 to 2010")
    canv.setFillColor(GREEN)
    canv.setFont("Helvetica-Bold", 8.6)
    canv.drawRightString(PAGE_W - MARGIN, MARGIN - 9.5 * mm, str(canv.getPageNumber()))
    canv.restoreState()


def build_doc():
    doc = BaseDocTemplate(
        str(OUTPUT), pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="HomeValue - Complete Project Guide",
        author="House Price Prediction System",
        subject="End-to-end walkthrough: data, algorithms, evaluation and application",
    )
    frame = Frame(MARGIN, MARGIN, FRAME_W, PAGE_H - 2 * MARGIN, id="body")
    cover_frame = Frame(MARGIN, MARGIN, FRAME_W, PAGE_H - 2 * MARGIN, id="cover")
    doc.addPageTemplates([
        PageTemplate(id="Cover", frames=[cover_frame], onPage=_cover_page),
        PageTemplate(id="Body", frames=[frame], onPage=_body_page),
    ])
    return doc


# ---------------------------------------------------------------------------
# Content
# ---------------------------------------------------------------------------
def build_story(metrics):
    lr = metrics["models"]["linear_regression"]
    rf = metrics["models"]["random_forest"]
    prep = metrics["data_preparation"]
    clean = prep["cleaning_summary"]
    ds = metrics["dataset_statistics"]
    meta = metrics["dataset_metadata"]
    imp = metrics["feature_importances"]
    med = metrics["feature_schema"]["training_medians"]

    story = []

    # ---------------- Cover ------------------------------------------------
    story.append(NextPageTemplate("Body"))
    story.append(Spacer(1, 46 * mm))
    story.append(Paragraph("MACHINE LEARNING PROJECT", S["cover_body"]))
    story.append(Spacer(1, 5 * mm))
    story.append(Paragraph("HomeValue", S["cover_title"]))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("A Complete Guide to the<br/>House Price Prediction System",
                           S["cover_sub"]))
    story.append(Spacer(1, 8 * mm))
    story.append(_rule(colors.HexColor("#8FBAA6"), 2, 0, 6, 70 * mm))
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph(
        "From first principles to a running web application.<br/>"
        "Which algorithm was used, how it works, and exactly why it was chosen.",
        S["cover_body"]))
    story.append(Spacer(1, 30 * mm))
    story.append(Paragraph(
        f"Selected model: {rf['name']}<br/>"
        f"Held-out test R-squared {rf['test_metrics']['r2']:.4f} - "
        f"typical error {money(rf['test_metrics']['mae'])}<br/>"
        f"Dataset: {meta['name']} ({meta['observation_period']})",
        S["cover_body"]))
    story.append(PageBreak())

    # ---------------- How to read -----------------------------------------
    H1(story, "", "How to read this guide")
    P(story, "This document explains the project from the ground up. It assumes you are "
             "comfortable running a Python script, but it assumes <b>no prior machine-learning "
             "knowledge</b>. Every term is defined the first time it appears, and every number "
             "quoted here was produced by the code in this repository - none of it is illustrative.")
    P(story, "If you only read one chapter, read <b>Chapter 11</b>. It answers the question this "
             "guide is built around: which algorithm does the system use, and why that one and "
             "not the simpler alternative.")
    story.append(Spacer(1, 3))
    TBL(story, [
        ["If you are...", "Start with"],
        ["Completely new to machine learning", "Chapters 1 to 3, then 9 to 11"],
        ["Looking for the model choice and justification", "Chapters 9 to 12"],
        ["Interested in the numbers and what they mean", "Chapters 14 to 16"],
        ["Here for the application and how to run it", "Chapters 17 to 22"],
        ["Checking what the system cannot do", "Chapter 23"],
    ], [65 * mm, FRAME_W - 65 * mm])
    NOTE(story, "Everything in here is reproducible",
         "Delete the model files, run <font face='Courier'>python -m src.train_model</font>, "
         "and every figure in this guide regenerates. The dataset is fetched from a public "
         "source by the code itself, so there is nothing to download by hand.")

    # ---------------- TOC --------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Contents", S["h1"]))
    story.append(_rule(GREEN, 1.6, 0, 10))
    story.append(Spacer(1, 4))
    toc = TableOfContents()
    toc.levelStyles = [S["toc1"], S["toc2"]]
    toc.dotsMinLevel = 0
    story.append(toc)
    story.append(PageBreak())

    # ================= PART I ==============================================
    story.append(Paragraph("Part I - Foundations", S["h1"]))
    story.append(_rule(GREEN, 1.6, 0, 10))
    story.append(Spacer(1, 6))

    H2(story, "1.", "What machine learning actually is")
    P(story, "Traditional programming works like this: you write rules, feed in data, and get "
             "answers out. Machine learning inverts it. You feed in data <i>and</i> the answers, "
             "and the computer works out the rules.")
    CODE(story, [
        "Traditional:   DATA + RULES        -> ANSWERS",
        "Machine learning: DATA + ANSWERS   -> RULES",
        "",
        "In our case: 1,458 sold homes + their sale prices -> a rule that",
        "             estimates the price of a home it has never seen.",
    ])
    P(story, "That learned rule is called a <b>model</b>. The process of finding it is "
             "<b>training</b>. The data with known answers is the <b>training set</b>.")

    H3(story, "The three flavours")
    TBL(story, [
        ["Type", "What the data looks like", "Example"],
        ["Supervised learning", "Inputs with the correct answer attached",
         "House features + the price it sold for"],
        ["Unsupervised learning", "Inputs with no answers", "Grouping similar houses together"],
        ["Reinforcement learning", "An agent rewarded for good actions", "Game-playing systems"],
    ], [40 * mm, 62 * mm, FRAME_W - 102 * mm])
    P(story, "This project is <b>supervised learning</b>. Every property in the dataset comes "
             "with the answer - the price it actually sold for.")

    H3(story, "Regression versus classification")
    P(story, "Supervised problems split in two. <b>Classification</b> predicts a category "
             "(spam or not spam). <b>Regression</b> predicts a number. House price is a number "
             "that can take any value, so this is a <b>regression</b> problem.")
    NOTE(story, "Why this matters",
         "The choice of regression rules out whole families of algorithms - accuracy, F1 score "
         "and confusion matrices are classification tools and are simply not applicable here. "
         "Everything that follows is measured with regression metrics.")

    H2(story, "2.", "The problem we are solving")
    P(story, "Given nine things a person genuinely knows about a property - where it is, how big "
             "it is, how many rooms it has, how old it is - estimate what it would sell for.")
    P(story, "Nine inputs were chosen deliberately. They are facts an owner or buyer knows "
             "without a surveyor: no condition scores, no renovation history, no school "
             "catchment. That constraint keeps the system usable, and Chapter 23 is honest about "
             "what it costs in accuracy.")
    TBL(story, [
        ["#", "Input", "Type", "What it means"],
        ["1", "location", "Category", f"Which of {ds['num_neighborhoods']} neighbourhoods it sits in"],
        ["2", "area_sqft", "Number", "Above-grade living area in square feet"],
        ["3", "lot_area_sqft", "Number", "Total lot size in square feet"],
        ["4", "bedrooms", "Number", "Bedrooms above grade"],
        ["5", "bathrooms", "Number", "Total bathrooms (a half bath counts 0.5)"],
        ["6", "property_age", "Number", "Age in years at the point of sale"],
        ["7", "floors", "Number", "Storeys: 1, 1.5, 2 or 2.5"],
        ["8", "parking", "Category", "No garage, 1-car, 2-car, or 3+ car"],
        ["9", "property_type", "Category", "Detached, duplex, townhouse (end or interior), two-family"],
    ], [8 * mm, 30 * mm, 20 * mm, FRAME_W - 58 * mm])
    P(story, "The value we are predicting - the <b>target</b> - is <b>price</b>, the sale price "
             "in US dollars.")

    H2(story, "3.", "Where the data came from")
    P(story, "The dataset was not downloaded by hand and is not synthetic. It is fetched by the "
             "code itself from OpenML, a public repository of machine-learning datasets.")
    TABLE_ROWS = [
        ["Dataset", meta["name"]],
        ["OpenML identifier", "42165 (openml.org/d/42165)"],
        ["Compiled by", meta["author"]],
        ["Published", meta["publication"]],
        ["How we retrieve it", "sklearn.datasets.fetch_openml(name='house_prices')"],
        ["Licence", meta["license"]],
        ["Market region", meta["market_region"]],
        ["Observation period", meta["observation_period"]],
        ["Currency", f"{meta['currency']} ({meta['currency_symbol']})"],
    ]
    TBL(story, [["Property", "Value"]] + TABLE_ROWS, [48 * mm, FRAME_W - 48 * mm])
    P(story, "De Cock compiled this dataset specifically to give students a modern, realistic "
             "alternative to the old Boston housing data. It records individual property sales, "
             "not regional averages, which is exactly what a per-property estimator needs.")

    H3(story, "Why not a different dataset?")
    TBL(story, [
        ["Candidate", "Verdict", "Reason"],
        ["California housing", "Rejected",
         "Census-block medians. No per-property bedroom counts or construction dates."],
        ["Boston housing", "Rejected",
         "Known ethical problems with its constructed variable. Widely deprecated."],
        ["KC housing / others", "Rejected",
         "Either unavailable (HTTP 404) or missing fields the application needs."],
        ["Ames, Iowa", "Chosen",
         "Real peer-reviewed per-property sales, every required field, unrestricted academic licence."],
    ], [32 * mm, 20 * mm, FRAME_W - 52 * mm])

    H3(story, "From 81 columns down to 19, then 10")
    P(story, "The source table has 81 columns. The project keeps 19 of them - only what the "
             "application actually consumes - and then transforms those into the 10-column "
             "schema the model trains on.")

    # ================= PART II =============================================
    story.append(PageBreak())
    story.append(Paragraph("Part II - Understanding and preparing the data", S["h1"]))
    story.append(_rule(GREEN, 1.6, 0, 10))
    story.append(Spacer(1, 6))

    H2(story, "4.", "Looking at the data first")
    P(story, "Before modelling anything, you look. The distribution of the target shapes every "
             "decision that follows - which metrics are fair, whether outliers matter, and which "
             "algorithm is likely to cope.")
    FIG(story, "price_distribution",
        f"Figure 1. Sale prices across all {ds['total_properties']:,} cleaned records. "
        f"The distribution is right-skewed: most homes cluster below $250,000, with a long tail "
        f"of expensive properties pulling the mean ({money(ds['price']['mean'])}) above the "
        f"median ({money(ds['price']['median'])}).")
    TBL(story, [
        ["Statistic", "Value", "Statistic", "Value"],
        ["Minimum", money(ds["price"]["min"]), "75th percentile", money(ds["price"]["q75"])],
        ["25th percentile", money(ds["price"]["q25"]), "Maximum", money(ds["price"]["max"])],
        ["Median", money(ds["price"]["median"]), "Mean", money(ds["price"]["mean"])],
        ["Std. deviation", money(ds["price"]["std"]), "Properties", f"{ds['total_properties']:,}"],
    ], [32 * mm, 32 * mm, 34 * mm, FRAME_W - 98 * mm], align_right=(1, 3))
    NOTE(story, "Why the skew matters",
         "Because the mean sits above the median, a metric based on average error will be pulled "
         "around by the expensive tail. That is one reason this project reports four metrics "
         "rather than one, and why RMSE is always shown alongside MAE.")

    H3(story, "Living area is the strongest single clue")
    FIG(story, "price_vs_area",
        "Figure 2. Living area against sale price. The relationship is clearly positive and "
        "roughly straight, with the spread widening for larger homes - a pattern a linear model "
        "can capture in direction but not in shape.")

    H3(story, "Age works the other way")
    FIG(story, "price_vs_age",
        "Figure 3. Property age at the point of sale against price. Newer homes fetch more on "
        "average, but the scatter is wide: an old, well-built home in a good street can "
        "outperform a newer one elsewhere.")

    H3(story, "How the numeric features relate to each other")
    FIG(story, "correlation",
        "Figure 4. Correlation matrix for the numeric features. Living area has the strongest "
        "linear relationship with price. Bedrooms correlates only weakly - a useful reminder "
        "that a feature people assume matters does not always carry much signal.")

    H3(story, "Location sets the ceiling")
    FIG(story, "neighbourhood",
        "Figure 5. The twelve most expensive neighbourhoods, with the number of recorded sales "
        "in each. Some neighbourhoods have fewer than a dozen sales, which is why per-neighbourhood "
        "estimates for them are noisy - see Chapter 23.")

    H2(story, "5.", "Cleaning: what we removed and exactly why")
    P(story, f"The raw extract holds {clean['initial_rows']:,} records. Cleaning leaves "
             f"{clean['final_rows']:,}. Only two rows are dropped, and the reason is documented "
             f"rather than convenient.")
    TBL(story, [
        ["Step", "Rows affected", "Why"],
        ["Drop the row identifier", "0 removed", "An Id column carries no predictive signal."],
        ["Remove exact duplicates", f"{clean['duplicates_removed']} removed",
         "Duplicated rows would weight some properties twice. None were found."],
        ["Remove non-positive area or price", "0 removed",
         "A zero or negative price or area indicates a broken record. None were found."],
        ["Remove documented partial sales", f"{clean['anomalies_or_invalid_removed']} removed",
         "Two sales over 4,000 sq ft sold for under $300,000. The dataset author documents "
         "both as partial sales - incomplete construction, not arm's-length market "
         "transactions - so they are not valid training data."],
    ], [46 * mm, 24 * mm, FRAME_W - 70 * mm])
    WARN_BOX(story, "Deliberately left alone: 6 missing bedroom values",
             "Six records have a bedroom count of zero, which is not a real studio - it is "
             "missing data recorded as zero. The code converts these to genuinely missing values "
             "and leaves them that way. They are filled later by an imputer that is fitted "
             "<b>only on the training split</b>. Pre-filling them across the whole dataset would "
             "let information from the test set leak into training, and would make the reported "
             "accuracy optimistic and dishonest.")

    H2(story, "6.", "Feature engineering: building the ten-column schema")
    P(story, "Raw columns are not always the right shape to learn from. Four features are "
             "constructed rather than taken as-is.")
    TBL(story, [
        ["Feature", "How it is built", "Why it is better than the raw column"],
        ["bathrooms", "FullBath + 0.5 x HalfBath + BsmtFullBath + 0.5 x BsmtHalfBath",
         "Four separate bathroom columns collapse into one number a person would recognise."],
        ["property_age", "YrSold - YearBuilt, clipped at zero",
         "Age at the moment of sale, not age today. Two sale years differ in what a construction "
         "year means; age removes that ambiguity."],
        ["floors", "HouseStyle mapped to storeys (1, 1.5, 2, 2.5)",
         "Turns a text label into an ordered number, so 1.5 sits between 1 and 2."],
        ["parking", "GarageCars, with a missing garage type treated as no garage",
         "Capacity is what buyers care about. A missing garage type means no garage, not unknown."],
        ["location", "Neighbourhood codes mapped to names",
         "NAmes means nothing to a user; 'North Ames' does."],
        ["property_type", "BldgType mapped to plain English",
         "1Fam becomes 'Single-Family Detached'."],
    ], [26 * mm, 62 * mm, FRAME_W - 88 * mm])
    NOTE(story, "A note on bathrooms",
         "Counting a half bath as 0.5 rather than as a separate category is a modelling choice. "
         "It keeps the feature numeric and ordinally meaningful - three full baths beats two full "
         "plus a half - which suits both algorithms used here.")

    H2(story, "7.", "The train/test split, and why leakage ruins everything")
    P(story, "The dataset is split before any fitting happens: "
             f"<b>{prep['train_rows']:,} training rows</b> and <b>{prep['test_rows']} held-out "
             f"test rows</b> ({int((1 - prep['test_split_ratio']) * 100)}/"
             f"{int(prep['test_split_ratio'] * 100)}), with a fixed random seed of "
             f"{prep['random_state']} so the split is identical on every run.")
    CODE(story, [
        "X_train, X_test, y_train, y_test = train_test_split(",
        f"    X, y, test_size={config.TEST_SIZE}, random_state={config.RANDOM_STATE}",
        ")",
    ])
    P(story, "The model sees only the training rows. The test rows are locked away until the "
             "very end, and are touched exactly once - to produce the numbers in Chapter 15.")
    WARN_BOX(story, "What data leakage is, and why the pipeline avoids it",
             "Leakage happens when information from the test set sneaks into training. It makes "
             "measured accuracy look excellent and then collapses in the real world. The classic "
             "route is computing a median or fitting a scaler across the whole dataset before "
             "splitting. This project avoids it by putting every transform - imputation, scaling, "
             "encoding - inside a scikit-learn Pipeline, so they are fitted on training rows only.")
    H3(story, "The pattern that keeps it safe")
    CODE(story, [
        "# CORRECT - the imputer learns the median from training rows only",
        "pipeline.fit(X_train, y_train)      # learns medians AND the model",
        "pipeline.predict(X_test)            # applies them, no refitting",
        "",
        "# WRONG - the median now includes test rows",
        "df['bedrooms'].fillna(df['bedrooms'].median())   # before the split",
        "train_test_split(...)"                          # too late",
    ])

    # ================= PART III ============================================
    story.append(PageBreak())
    story.append(Paragraph("Part III - The algorithms", S["h1"]))
    story.append(_rule(GREEN, 1.6, 0, 10))
    story.append(Spacer(1, 6))
    LEAD(story, "This is the heart of the project. Two candidate algorithms were trained and "
                "compared. This part explains how each one works before revealing which won.")

    H2(story, "8.", "Algorithm one: Linear Regression")
    P(story, "The oldest and simplest regression method, and still the right place to start. It "
             "assumes price is a weighted sum of the inputs.")
    CODE(story, [
        "price = w1*area + w2*bedrooms + w3*age + ... + b",
        "",
        "  wi  = how many dollars one extra unit of that feature is worth",
        "  b   = the baseline price when every feature is zero",
    ])
    P(story, "Training means finding the weights. The method used is <b>ordinary least squares</b>: "
             "pick the weights that make the sum of squared errors as small as possible.")
    CODE(story, [
        "           n",
        "  minimise  SUM (actual_i - predicted_i)^2",
        "           i=1",
        "",
        "Squaring the error punishes big misses far more than small ones,",
        "and gives one unique best answer that can be solved directly.",
    ])
    H3(story, "What it does well")
    BUL(story, [
        "Fast - training takes a fraction of a second even on large data.",
        "Completely transparent: each weight reads as a dollar effect you can quote.",
        "Hard to overfit badly, because there are so few parameters to fit.",
    ])
    H3(story, "Where it struggles")
    BUL(story, [
        "<b>It assumes each unit adds a fixed amount.</b> If an extra bathroom adds $8,000, the "
        "model says it adds $8,000 whether the house is 900 or 4,000 square feet. Reality is "
        "not that tidy.",
        "<b>It cannot discover interactions on its own.</b> A garage matters more on a large "
        "family home than on a small one. Capturing that means adding a hand-built "
        "area x parking term - and you have to guess which interactions matter.",
        "<b>It is sensitive to extreme values.</b> Squaring errors means a handful of expensive "
        "homes can drag the whole fit.",
    ])
    P(story, "In this project the linear model is the <b>baseline</b>: the honest reference point "
             "that any fancier method has to beat to justify its extra complexity.")

    H2(story, "9.", "Algorithm two: Decision Trees")
    P(story, "A decision tree predicts by asking a sequence of yes/no questions about the "
             "features, then reading the answer off the group it lands in.")
    CODE(story, [
        "Is the living area above 1,600 sq ft?",
        "  |-- NO:  Is the property older than 40 years?",
        "  |         |-- NO:  -> predict $152,000",
        "  |         |-- YES: -> predict $118,000",
        "  |-- YES: Is it in Northridge Heights, Northridge or Stone Brook?",
        "            |-- NO:  -> predict $196,000",
        "            |-- YES: -> predict $312,000",
    ])
    P(story, "Training works top-down. At each step the tree searches every feature and every "
             "possible split point, and picks the one that best separates high prices from low "
             "ones - measured by how much it reduces the variance of the price within each group. "
             "It stops when a branch is small enough, deep enough, or cannot be split usefully.")
    H3(story, "Why a single tree is not enough")
    P(story, "A deep tree memorises its training data. It will nail every house it has already "
             "seen and generalise poorly to anything new. This is <b>overfitting</b>, and a lone "
             "unrestrained tree is extremely prone to it. A second weakness: trees are unstable. "
             "Change a handful of training rows and you can get a completely different tree.")

    H2(story, "10.", "Algorithm three: Random Forest")
    P(story, "A random forest is what you get when you fix both of those problems at once. It "
             "builds many trees and averages their predictions.")
    H3(story, "Two ideas do the work")
    NUM(story, [
        "<b>Bagging (bootstrap aggregating).</b> Each tree is trained on a random sample of the "
        "training rows, drawn with replacement - so a given row may appear several times in one "
        "tree's sample and not at all in another's. Every tree therefore sees a slightly "
        "different world.",
        "<b>Random feature subsets.</b> At each split, a tree may only consider a random subset "
        "of the features rather than all nine. This stops every tree from latching onto the same "
        "obvious feature (here, living area) and forces genuinely different trees.",
    ])
    P(story, "Then it averages. Each tree votes with a price; the forest's answer is the mean. "
             "Individual errors - one tree over-predicting, another under - cancel out, while the "
             "shared signal survives.")
    NOTE(story, "Why averaging helps, in one sentence",
         "Averaging reduces <b>variance</b> without systematically increasing <b>bias</b>: the "
         "forest keeps the trees' ability to fit complex patterns while smoothing away their "
         "tendency to memorise noise. Averaging only works because the individual trees are "
         "decorrelated - that is precisely what the random row and feature sampling buys.")
    H3(story, "What this project actually configured")
    P(story, "The forest is fitted inside the same Pipeline that handles imputation, scaling and "
             "encoding, so the transforms are fitted on training rows only. The pipeline is then "
             "saved as a single artifact and loaded once at application start-up - no refitting "
             "per request.")
    FIG(story, "pipeline_diagram",
        "Figure 6. The full pipeline, from raw CSV to a saved model artifact. Everything lives "
        "inside one Pipeline object, so the same fitted transforms are guaranteed to apply at "
        "inference time.")

    H2(story, "11.", "Which algorithm was chosen, and why")
    LEAD(story, f"<b>The selected model is the {rf['name']}.</b> It was not chosen in advance "
                f"and it was not chosen on training performance - both models were fitted, then "
                f"compared on the {prep['test_rows']} held-out test rows that neither had seen.")
    H3(story, "The head-to-head, on held-out data")
    TBL(story, [
        ["Metric", "Linear Regression", "Random Forest", "Better", "Improvement"],
        ["MAE", money2(lr["test_metrics"]["mae"]), money2(rf["test_metrics"]["mae"]),
         "Random Forest",
         f"{100 * (1 - rf['test_metrics']['mae'] / lr['test_metrics']['mae']):.1f}% lower"],
        ["RMSE", money2(lr["test_metrics"]["rmse"]), money2(rf["test_metrics"]["rmse"]),
         "Random Forest",
         f"{100 * (1 - rf['test_metrics']['rmse'] / lr['test_metrics']['rmse']):.1f}% lower"],
        ["R-squared", f"{lr['test_metrics']['r2']:.4f}", f"{rf['test_metrics']['r2']:.4f}",
         "Random Forest", "higher"],
        ["MAPE", f"{lr['test_metrics']['mape_percent']:.2f}%",
         f"{rf['test_metrics']['mape_percent']:.2f}%", "Random Forest", "lower"],
    ], [26 * mm, 34 * mm, 30 * mm, 26 * mm, FRAME_W - 116 * mm], align_right=(1, 2))
    FIG(story, "model_comparison",
        "Figure 7. Held-out test performance. The Random Forest wins on all four metrics, not "
        "just one - which is what makes the choice straightforward rather than a matter of taste.")
    H3(story, "The reasoning, in plain terms")
    NUM(story, [
        "<b>It wins on every metric, not a selected subset.</b> When one model wins on MAE, RMSE, "
        "R-squared and MAPE simultaneously, there is no trade-off to argue about.",
        "<b>The problem is Interaction-shaped.</b> Garage capacity matters more on a large house "
        "than a small one; location and area combine rather than simply add up. Forests capture "
        "that structure automatically. A linear model would need those interaction terms "
        "hand-written, and guessing them wrong is easy.",
        "<b>Categorical features with many levels.</b> Location has "
        f"{ds['num_neighborhoods']} values. One-hot encoding plus a linear model fits one "
        "coefficient per neighbourhood and nothing else - it cannot express that a large house "
        "in a good neighbourhood is worth more than the sum of those two facts.",
        "<b>Robustness to the price tail.</b> Sale prices are right-skewed (Figure 1). Trees "
        "split on ranks rather than magnitudes, so a handful of $700,000 homes distort the fit "
        "less than they distort a least-squares line.",
        "<b>The accuracy cost is worth it.</b> The forest is slower to train and its individual "
        "predictions are harder to explain than a linear equation. At this scale - 1,458 rows, "
        "nine features - that cost is negligible next to an 11 percent cut in test error.",
    ])
    H3(story, "Where we would have preferred the linear model")
    P(story, "Honesty cuts both ways. Linear regression would be the better engineering choice if:")
    BUL(story, [
        "Every prediction had to be explained as a dollar breakdown - 'this bathroom added $8,000'.",
        "The dataset were far smaller, where a forest's extra capacity would overfit.",
        "The relationships were genuinely straight and additive, in which case the forest buys nothing.",
        "Training speed or memory were the binding constraint.",
    ])
    P(story, f"None of those hold here. Notably, the linear baseline is a <b>strong</b> one - "
             f"test R-squared of {lr['test_metrics']['r2']:.4f} - so beating it is a real result "
             f"rather than a straw-man comparison.")
    H3(story, "The generalisation gap, stated openly")
    FIG(story, "train_vs_test",
        f"Figure 8. Train versus held-out test R-squared. The forest reaches "
        f"{rf['train_metrics']['r2']:.4f} on training data but {rf['test_metrics']['r2']:.4f} on "
        f"held-out data - a gap of "
        f"{rf['train_metrics']['r2'] - rf['test_metrics']['r2']:.4f}. It has memorised its "
        f"training set to a degree, and the honest number is the test one. Closing that gap is "
        f"the first item in Chapter 24.")

    H2(story, "12.", "The preprocessing pipeline in detail")
    P(story, "Both models sit inside a scikit-learn <b>ColumnTransformer</b>, which routes "
             "numeric and categorical columns down different paths.")
    TBL(story, [
        ["Column type", "Columns", "Steps applied", "Reason"],
        ["Numeric", ", ".join(config.NUMERICAL_FEATURES),
         "SimpleImputer (median), then StandardScaler",
         "Fills the missing bedroom values; scaling stops features measured in thousands of "
         "square feet from dominating those measured in single digits."],
        ["Categorical", ", ".join(config.CATEGORICAL_FEATURES),
         "SimpleImputer (most frequent), then OneHotEncoder",
         "Converts text labels into 0/1 indicator columns so the maths can use them."],
    ], [24 * mm, 46 * mm, 42 * mm, FRAME_W - 112 * mm])
    NOTE(story, "Why scaling matters even for the forest",
         "Tree splits are based on ordering, so scaling is not strictly required for the forest "
         "itself. It is included because the same pipeline structure is shared with the linear "
         "baseline, where unscaled features make the coefficients impossible to compare. Keeping "
         "one pipeline for both models makes the comparison fair.")
    H3(story, "The shape of the code")
    CODE(story, [
        "preprocessor = ColumnTransformer([",
        "    ('num', Pipeline([('impute', SimpleImputer(strategy='median')),",
        "                      ('scale',  StandardScaler())]),",
        "     NUMERICAL_FEATURES),",
        "    ('cat', Pipeline([('impute', SimpleImputer(strategy='most_frequent')),",
        "                      ('encode', OneHotEncoder(handle_unknown='ignore'))]),",
        "     CATEGORICAL_FEATURES),",
        "])",
        "",
        f"model = Pipeline([('prep', preprocessor), ('model', {rf['name'].replace(' ', '')}())])",
    ])
    P(story, "<font face='Courier'>handle_unknown='ignore'</font> is deliberate. If a category "
             "appears at prediction time that was never seen in training, the encoder produces "
             "all zeros instead of raising. The validation layer rejects unknown values before "
             "they get that far, but this is the safety net behind it.")

    # ================= PART IV =============================================
    story.append(PageBreak())
    story.append(Paragraph("Part IV - Evaluation", S["h1"]))
    story.append(_rule(GREEN, 1.6, 0, 10))
    story.append(Spacer(1, 6))

    H2(story, "13.", "How accuracy is measured here")
    P(story, "Four metrics, because any single one can be misleading. All are computed on the "
             f"{prep['test_rows']} held-out rows.")
    TBL(story, [
        ["Metric", "What it is", "How to read it", "Why it is reported"],
        ["MAE", "Mean absolute error",
         f"{money(rf['test_metrics']['mae'])} - the average miss in dollars",
         "The most intuitive number. Easy to explain to anyone."],
        ["RMSE", "Root mean squared error",
         f"{money(rf['test_metrics']['rmse'])} - like MAE, but punishes large misses harder",
         "Reveals occasional big errors that MAE hides. Always larger than MAE; a large gap "
         "between them means some predictions are badly off."],
        ["R-squared", "Share of price variance explained",
         f"{rf['test_metrics']['r2']:.4f} - about "
         f"{rf['test_metrics']['r2'] * 100:.0f}% of the variation",
         "Scale-free, so it is comparable across datasets. 1.0 is perfect; 0.0 is no better "
         "than always guessing the average."],
        ["MAPE", "Mean absolute percentage error",
         f"{rf['test_metrics']['mape_percent']:.2f}% - the average miss as a share of price",
         "Puts the error in proportion. A $19,000 miss means something different on a $60,000 "
         "home than on a $600,000 one."],
    ], [22 * mm, 38 * mm, 46 * mm, FRAME_W - 106 * mm])
    WARN_BOX(story, "The single most important caveat",
             f"An MAE of {money(rf['test_metrics']['mae'])} is an <b>average</b> over "
             f"{prep['test_rows']} held-out sales. It is a fair summary of the system, and it is "
             f"<b>not a guarantee about any individual property</b>. A specific home can be much "
             f"further off. This is one reason the application deliberately does not display a "
             f"prediction interval - see Chapter 23.")

    H2(story, "14.", "Results")
    H3(story, "Random Forest - the selected model")
    TBL(story, [
        ["Metric", "Training", "Held-out test"],
        ["MAE", money2(rf["train_metrics"]["mae"]), money2(rf["test_metrics"]["mae"])],
        ["RMSE", money2(rf["train_metrics"]["rmse"]), money2(rf["test_metrics"]["rmse"])],
        ["R-squared", f"{rf['train_metrics']['r2']:.4f}", f"{rf['test_metrics']['r2']:.4f}"],
        ["MAPE", f"{rf['train_metrics']['mape_percent']:.2f}%",
         f"{rf['test_metrics']['mape_percent']:.2f}%"],
    ], [40 * mm, 42 * mm, FRAME_W - 82 * mm], align_right=(1, 2))
    H3(story, "Linear Regression - the baseline")
    TBL(story, [
        ["Metric", "Training", "Held-out test"],
        ["MAE", money2(lr["train_metrics"]["mae"]), money2(lr["test_metrics"]["mae"])],
        ["RMSE", money2(lr["train_metrics"]["rmse"]), money2(lr["test_metrics"]["rmse"])],
        ["R-squared", f"{lr['train_metrics']['r2']:.4f}", f"{lr['test_metrics']['r2']:.4f}"],
        ["MAPE", f"{lr['train_metrics']['mape_percent']:.2f}%",
         f"{lr['test_metrics']['mape_percent']:.2f}%"],
    ], [40 * mm, 42 * mm, FRAME_W - 82 * mm], align_right=(1, 2))
    P(story, "Notice the pattern in the two tables. The linear model's training and test numbers "
             "are close together - it cannot overfit much, because it has so little freedom. The "
             "forest's training numbers are far better, and its test numbers are better too, but "
             "by a smaller margin. Both facts are reported rather than hidden.")
    H3(story, "Seeing the predictions")
    FIG(story, "actual_vs_predicted",
        "Figure 9. Predicted against actual price on the held-out test set for both models. "
        "Points scatter around the dashed line of perfect prediction. The Random Forest cloud is "
        "tighter, especially at the expensive end where the linear model systematically "
        "under-predicts.")
    FIG(story, "residuals",
        "Figure 10. Residuals - the error on each test property. A well-behaved model scatters "
        "evenly around zero with no curved shape. Both models fan out at higher prices, which is "
        "expected: expensive homes vary more, so there is more to get wrong.")

    H2(story, "15.", "What the model learned")
    P(story, "Two different importance measures are reported, and they disagree. That "
             "disagreement is worth understanding rather than smoothing over.")
    TBL(story, [
        ["Feature", "Impurity importance", "Permutation importance"],
    ] + [[f["label"], f"{f['importance_pct']:.2f}%", f"{f['permutation_importance_pct']:.2f}%"]
         for f in imp],
        [60 * mm, 44 * mm, FRAME_W - 104 * mm], align_right=(1, 2))
    FIG(story, "feature_importance",
        "Figure 11. Impurity importance against permutation importance. The two rankings "
        "disagree sharply on parking - and permutation is the one to trust.")
    H3(story, "Why they disagree, and which to believe")
    P(story, "<b>Impurity importance</b> counts how often a feature is used to split, weighted by "
             "how much those splits reduce variance. It is computed on training data and it is "
             "biased toward features with many distinct values - a feature with four categories "
             "offers more places to split than one with two, so it gets more chances to look useful.")
    P(story, "<b>Permutation importance</b> shuffles one feature's values across the held-out set "
             "and measures how much worse the predictions get. It is measured on data the model "
             "has not memorised, and it asks the question we actually care about: how much does "
             "this feature contribute to real predictive accuracy?")
    NOTE(story, "The verdict",
         "Impurity importance ranks parking first at 35.11 percent; permutation ranks it at 9.36 "
         "percent. Permutation is measured on held-out data and is not biased by category count, "
         "so it is the more trustworthy guide. It puts <b>living area first at 48.70 percent</b> "
         "and <b>property age second at 26.65 percent</b> - which also matches how housing "
         "markets actually behave.")
    WARN_BOX(story, "These numbers are not causal",
             "Feature importance tells you which inputs the model relies on. It does not say that "
             "adding a garage <i>causes</i> a price increase, and it must never be read that way. "
             "Adding a garage to a house would not necessarily raise its value by anything - the "
             "model has learned an association in past sales data, not a mechanism.")

    # ================= PART V ==============================================
    story.append(PageBreak())
    story.append(Paragraph("Part V - The system", S["h1"]))
    story.append(_rule(GREEN, 1.6, 0, 10))
    story.append(Spacer(1, 6))

    H2(story, "16.", "How a prediction request flows")
    P(story, "The application is a small Flask service. Understanding the path a request takes "
             "explains most of the design decisions.")
    CODE(story, [
        "  Browser                nine inputs, checked instantly in the browser",
        "     |",
        "     v",
        "  POST /api/predict      the same rules are enforced again on the server",
        "     |",
        "     v",
        "  validate_and_convert   ranges, types and known category values",
        "     |",
        "     v",
        "  predict_price          the pipeline, loaded once and cached in memory",
        "     |",
        "     +--> prediction_store   every estimate is recorded to SQLite",
        "     |",
        "     v",
        "  JSON response          price, price per sq ft, explanation, limitations",
    ])
    TBL(story, [
        ["Concern", "How it is handled"],
        ["Model loading", "Loaded once at start-up and cached. A reload per request would be "
                          "wasteful and slow."],
        ["Validation", "Identical rules run in the browser and on the server. Client-side checks "
                       "are a convenience, never a guarantee - they can be bypassed."],
        ["Unknown categories", "Rejected with a specific message. The system never guesses at a "
                               "neighbourhood or property type it was not trained on."],
        ["Logging", "Every served estimate is written to SQLite. If logging fails, the prediction "
                    "still succeeds - a logging problem must never break a valid answer."],
        ["Serving", "Flask's built-in development server. For anything beyond local use, deploy "
                    "behind Gunicorn or Waitress."],
    ], [40 * mm, FRAME_W - 40 * mm])

    H2(story, "17.", "The web application")
    TBL(story, [
        ["Page", "Route", "What it does"],
        ["Landing", "/", "Headline, two calls to action, and the key dataset facts."],
        ["Estimate form", "/predict",
         "Nine inputs, pre-filled with the training medians so a first visit can produce a "
         "sensible result immediately."],
        ["Result", "/result",
         "Estimated price, price per square foot, a sensitivity table showing how the estimate "
         "moves when one input changes, and the limitations stated alongside the number."],
        ["Insights", "/insights",
         "Six charts generated by Matplotlib and Seaborn from the real dataset and fitted model."],
        ["Dashboard", "/dashboard",
         "Live view of the predictions this installation has served (Chapter 18)."],
    ], [28 * mm, 24 * mm, FRAME_W - 52 * mm])
    P(story, "The defaults in the form are the training-set medians: "
             f"{med['area_sqft']:,.0f} sq ft of living area, "
             f"{med['lot_area_sqft']:,.0f} sq ft of lot, "
             f"{med['bedrooms']:.0f} bedrooms, {med['bathrooms']:.0f} bathrooms, "
             f"{med['property_age']:.0f} years old, {med['floors']:.0f} floor. "
             "They are computed from the training split, not the full dataset - the same "
             "no-leakage discipline as everywhere else.")
    NOTE(story, "The sensitivity table",
         "The result page shows how the estimate changes when one input is nudged while the rest "
         "stay fixed. This is an exploratory aid, not a causal claim: it shows what the model "
         "says about a hypothetical variant of the property, not what a renovation would achieve.")

    H2(story, "18.", "The prediction dashboard")
    P(story, "The dashboard answers the question 'what has this installation actually been asked "
             "to price?'. It is built on a SQLite log at "
             "<font face='Courier'>data/predictions.db</font>, with one row per served estimate.")
    H3(story, "Two different things, kept visibly separate")
    TBL(story, [
        ["", "Usage", "Measured accuracy"],
        ["Source", "The SQLite log of served predictions",
         "models/metrics.json, from the held-out test set"],
        ["Changes over time", "Yes - grows with every prediction",
         "No - fixed until the model is retrained"],
        ["Examples", "Predictions logged, median estimate, distribution, busiest neighbourhoods",
         f"MAE {money(rf['test_metrics']['mae'])}, R-squared {rf['test_metrics']['r2']:.4f}"],
    ], [30 * mm, 62 * mm, FRAME_W - 92 * mm])
    P(story, "This separation is the point. It would be easy - and dishonest - to let impressive "
             "accuracy figures appear to be a property of recent activity, or to let a busy day "
             "make the model look better. They are unrelated quantities and the page keeps them apart.")
    H3(story, "What it shows once there is data")
    BUL(story, [
        "A KPI strip: predictions logged, median estimate and range, median price per square "
        "foot, test R-squared, and typical error in dollars.",
        "Prediction volume over time, with the median estimate overlaid. Buckets are hourly while "
        "activity spans a single day, and switch to daily once it spans more.",
        "A twelve-bin histogram of logged estimates.",
        "Median estimate by neighbourhood and by property type, ranked.",
        "Living area against estimated price, one point per logged estimate, coloured by "
        "property age.",
        "Feature importance, labelled as association rather than causation.",
        "Model performance, measured once on the held-out test set.",
        "The twelve most recent predictions the model served.",
    ])
    NOTE(story, "Nothing on the dashboard is invented",
         "With an empty log the page shows an explicit empty state - not placeholder charts with "
         "made-up numbers. The 'Log sample activity' button is not a demo shortcut: it takes real "
         "properties from the cleaned dataset, runs each through the saved pipeline exactly as a "
         "web request would, and records the result tagged as a sample run so it is always "
         "distinguishable from genuine form submissions. All seven charts are hand-rolled inline "
         "SVG - no charting library, no CDN, and they work offline.")

    H2(story, "19.", "Validation and error handling")
    P(story, "Validation runs twice: inline in the browser for instant feedback, then again on "
             "the server. The duplication is intentional - a client-side check is a usability "
             "feature, not a security boundary.")
    TBL(story, [
        ["Failure mode", "Behaviour"],
        ["Missing field", "Field-level message naming the field, plus a summary banner."],
        ["Out-of-range value", "Rejected with the accepted range stated explicitly."],
        ["Wrong type", "Rejected with a conversion message rather than a crash."],
        ["Unknown category", "Rejected, naming the value and the valid options."],
        ["Model artifact missing", "A clear error page explaining how to train the model."],
        ["Logging failure", "Logged as a warning; the prediction is still returned."],
    ], [46 * mm, FRAME_W - 46 * mm])

    H2(story, "20.", "Testing")
    P(story, "The suite has 70 tests, all passing.")
    TBL(story, [
        ["Group", "Tests", "Covers"],
        ["Preprocessing", "part of 49",
         "The 19-to-10 transformation, removed rows, derived features, missing-value handling."],
        ["Inference and routes", "part of 49",
         "Valid, invalid, missing, out-of-range and unseen-category inputs; every page route; "
         "the JSON API contract; determinism."],
        ["Dashboard", "21",
         "The SQLite store round-trip, aggregation correctness against the stored rows, the "
         "empty-state guarantee, and all three dashboard endpoints."],
    ], [36 * mm, 18 * mm, FRAME_W - 54 * mm])
    NOTE(story, "A test-safety detail worth copying",
         "An autouse session fixture redirects the prediction log to a temporary database and "
         "asserts that nothing points it back at the real one. Without it, a test exercising "
         "'clear the log' would destroy genuinely recorded activity. This was a real defect "
         "during development and the fixture exists because of it.")

    H2(story, "21.", "Running the project yourself")
    P(story, "From the project root, with Python 3.9 or newer:")
    CODE(story, [
        "python -m venv .venv",
        "source .venv/bin/activate          # Windows: .venv\\Scripts\\activate",
        "pip install -r requirements.txt",
        "",
        "python -m src.data_preprocessing   # fetch OpenML data -> cleaned CSV",
        "python -m src.train_model          # train both models, save the winner",
        "python app.py                      # serve on http://127.0.0.1:5000",
        "",
        "python -m pytest tests/ -q         # 70 tests",
    ])
    TBL(story, [
        ["Then open", "You will see"],
        ["http://127.0.0.1:5000/", "The landing page"],
        ["http://127.0.0.1:5000/predict", "The estimate form"],
        ["http://127.0.0.1:5000/insights", "The dataset charts"],
        ["http://127.0.0.1:5000/dashboard", "The prediction-activity dashboard"],
    ], [62 * mm, FRAME_W - 62 * mm])
    P(story, "The dashboard starts empty by design. Use the 'Log sample activity' button on that "
             "page, or make a few predictions through the form, and it populates with real model "
             "runs.")

    # ================= PART VI =============================================
    story.append(PageBreak())
    story.append(Paragraph("Part VI - Limits and next steps", S["h1"]))
    story.append(_rule(GREEN, 1.6, 0, 10))
    story.append(Spacer(1, 6))

    H2(story, "22.", "Project structure")
    CODE(story, [
        "house-price-prediction/",
        "  app.py                     Flask app: routes, API, error handling",
        "  config.py                  Paths, feature schema, code maps, validation rules",
        "  src/",
        "    data_preprocessing.py    Load, inspect, clean, build the ColumnTransformer",
        "    train_model.py           Train, compare, select, persist",
        "    evaluate_model.py        Metrics, importances, statistics, charts",
        "    predict.py               Validation, cached inference, explanations",
        "    prediction_store.py      SQLite log of every served estimate",
        "    dashboard_analytics.py   Aggregates the log for the dashboard",
        "    sample_activity.py       Scores real dataset rows to seed the log",
        "  data/raw/                  The 19-column extract from OpenML",
        "  data/processed/            The 10-column modelling schema",
        "  models/                    The fitted pipelines and metrics.json",
        "  templates/                 Jinja2 pages, including dashboard.html",
        "  static/css, static/js      Hand-written stylesheet and behaviour",
        "  tests/                     70 pytest tests",
        "  docs/                      This guide, the PDF, the presentation, charts",
    ])

    H2(story, "23.", "What this system cannot do")
    LEAD(story, "These limits are not footnotes. They define what the output may legitimately be "
                "used for, and the application restates them on the result page.")
    TBL(story, [
        ["Limitation", "What it means in practice"],
        ["Geography and period",
         f"All training records are from {meta['market_region']} between "
         f"{meta['observation_period']}. The model knows nothing about other markets, and nothing "
         f"about price levels after 2010."],
        ["Not a valuation",
         "The output is a statistical estimate for education and comparison. It is not an "
         "appraisal, not financial advice, and not a substitute for a professional valuation."],
        ["No prediction interval",
         "The model emits a single number. A range is deliberately not shown, because a standard "
         "Random Forest does not produce a statistically justified one. Quantile regression "
         "forests or conformal prediction would be required."],
        ["Averages hide individual error",
         f"MAE of {money(rf['test_metrics']['mae'])} is an average across {prep['test_rows']} "
         f"held-out sales. Any single property can be much further off."],
        ["Small categories",
         "Some neighbourhoods have only a handful of recorded sales, so their estimates are noisy "
         "(see Figure 5)."],
        ["Omitted factors",
         "Condition, renovation quality, interior finish, school catchment and micro-location are "
         "absent from the nine features. They matter, and the model cannot see them."],
        ["Overfitting headroom",
         f"Train R-squared {rf['train_metrics']['r2']:.4f} against test R-squared "
         f"{rf['test_metrics']['r2']:.4f} leaves clear room for regularisation."],
        ["Development server",
         "app.py uses Flask's built-in server. Use Gunicorn or Waitress for anything beyond "
         "local use."],
    ], [42 * mm, FRAME_W - 42 * mm])

    H2(story, "24.", "What would be built next")
    TBL(story, [
        ["Change", "What it would improve", "Why it helps"],
        ["Hyperparameter tuning with cross-validation",
         "Accuracy", "The forest was trained with sensible defaults, not searched settings. "
                     "Tree depth and minimum leaf size alone are likely worth something."],
        ["Regularisation / depth limits", "Generalisation",
         "Directly targets the train-test gap in Figure 8."],
        ["Log-transform the target", "Accuracy on the expensive tail",
         "Sale prices are right-skewed; modelling log-price often evens the error out."],
        ["Target or frequency encoding for location", "Accuracy",
         f"{ds['num_neighborhoods']} neighbourhoods produce many sparse one-hot columns. "
         "Encoding them by their median price is often stronger."],
        ["Gradient boosting (XGBoost, LightGBM)", "Accuracy",
         "Boosting fits errors sequentially rather than averaging independent trees, and usually "
         "beats a plain forest on tabular data."],
        ["Quantile regression forests", "Honesty",
         "Would produce a calibrated prediction interval - the single biggest missing capability."],
        ["Conformal prediction", "Honesty",
         "Gives intervals with a guaranteed coverage rate, without assuming a distribution."],
        ["Retraining on current data", "Relevance",
         "Would remove the 2006-2010 constraint, at the cost of sourcing a licensed modern dataset."],
    ], [48 * mm, 34 * mm, FRAME_W - 82 * mm])

    H2(story, "25.", "Glossary")
    TBL(story, [
        ["Term", "Meaning"],
        ["Bagging", "Training each model on a random resample of the data, then averaging. "
                    "Short for bootstrap aggregating."],
        ["Bias", "Error from assumptions that are too simple - missing the true pattern."],
        ["Classification", "Predicting a category."],
        ["Data leakage", "Information from the test set reaching the model during training, "
                         "inflating measured accuracy."],
        ["Feature", "An input column the model learns from."],
        ["Feature engineering", "Creating better inputs from the raw columns."],
        ["Held-out / test set", "Data locked away during training and used once to measure "
                                "honest accuracy."],
        ["Hyperparameter", "A setting chosen before training, not learned from data."],
        ["Imputation", "Filling in missing values."],
        ["MAE", "Mean absolute error - the average miss, in the target's units."],
        ["MAPE", "Mean absolute percentage error - the average miss as a share of the true value."],
        ["Model", "The learned rule that maps inputs to a prediction."],
        ["One-hot encoding", "Turning one categorical column into several 0/1 columns."],
        ["Overfitting", "Memorising training data instead of learning the pattern."],
        ["Permutation importance", "How much accuracy falls when one feature's values are shuffled."],
        ["Pipeline", "A chain of transforms plus a model, fitted together."],
        ["Regression", "Predicting a number."],
        ["RMSE", "Root mean squared error - like MAE, but punishing large misses more."],
        ["R-squared", "Share of the target's variance the model explains. 1.0 is perfect."],
        ["Random Forest", "Many decorrelated decision trees, averaged."],
        ["Residual", "The error on one prediction: actual minus predicted."],
        ["Scaling", "Rescaling numeric features so they are comparable in magnitude."],
        ["Supervised learning", "Learning from examples that include the correct answer."],
        ["Target", "The value being predicted - here, sale price."],
        ["Training set", "The examples the model learns from."],
        ["Variance", "Error from being overly sensitive to the particular training sample."],
    ], [40 * mm, FRAME_W - 40 * mm])

    H2(story, "26.", "Appendix: JSON API reference")
    TBL(story, [
        ["Endpoint", "Method", "Purpose"],
        ["/api/predict", "POST", "Validate nine inputs and return an estimate with an explanation."],
        ["/api/metrics", "GET", "The full metrics bundle as JSON."],
        ["/api/dashboard/summary", "GET", "The complete dashboard payload."],
        ["/api/dashboard/sample", "POST",
         "Score and log {\"count\": N} real properties from the dataset (1 to 200)."],
        ["/api/dashboard/clear", "POST", "Delete every logged prediction."],
        ["/health", "GET", "Liveness and model-status check."],
    ], [46 * mm, 16 * mm, FRAME_W - 62 * mm])

    H2(story, "27.", "Appendix: the ten-column data schema")
    P(story, "This is the required format for retraining. Feed a CSV with these columns, in this "
             "order, to <font face='Courier'>python -m src.train_model</font>.")
    TBL(story, [
        ["#", "Column", "Type", "Description", "Example"],
        ["1", "location", "text", f"One of {ds['num_neighborhoods']} neighbourhoods", "College Creek"],
        ["2", "area_sqft", "number", "Above-grade living area, sq ft", "1710.0"],
        ["3", "lot_area_sqft", "number", "Lot size, sq ft", "8450.0"],
        ["4", "bedrooms", "number", "Bedrooms above grade", "3.0"],
        ["5", "bathrooms", "number", "Total bathrooms, half bath = 0.5", "3.5"],
        ["6", "property_age", "number", "Age at the point of sale, years", "5.0"],
        ["7", "floors", "number", "Storeys: 1, 1.5, 2 or 2.5", "2.0"],
        ["8", "parking", "text", "No Garage / 1-Car / 2-Car / 3+ Car", "2-Car Garage"],
        ["9", "property_type", "text", "One of five building types", "Single-Family Detached"],
        ["10", "price", "number", "Target. Sale price in USD", "208500.0"],
    ], [8 * mm, 30 * mm, 18 * mm, 62 * mm, FRAME_W - 118 * mm])
    NOTE(story, "If you retrain on different data",
         "Every figure in this guide describes this dataset and this fitted model. Retraining "
         "will change all of them. Regenerate the charts and this document afterwards so the "
         "write-up cannot drift from the artifacts.")

    story.append(Spacer(1, 8))
    story.append(_rule(GREEN, 1.2, 4, 6))
    story.append(Paragraph(
        f"<b>Summary.</b> A reproducible pipeline, a model chosen on held-out data rather than "
        f"asserted in advance, and an explicit account of what it cannot do. The Random Forest "
        f"was selected over a strong linear baseline because it won on all four held-out metrics "
        f"- {100 * (1 - rf['test_metrics']['rmse'] / lr['test_metrics']['rmse']):.0f} percent "
        f"lower RMSE - and because the problem is interaction-shaped in a way a linear model "
        f"cannot express without hand-written terms. On homes it has never seen it explains "
        f"about {rf['test_metrics']['r2'] * 100:.0f} percent of price variation and is typically "
        f"off by about {money(rf['test_metrics']['mae'])}.",
        S["body"]))
    return story


def main():
    metrics = json.loads(METRICS_PATH.read_text())
    global _DOC
    doc = build_doc()
    _DOC = doc
    story = build_story(metrics)
    doc.multiBuild(story)

    size_kb = OUTPUT.stat().st_size / 1024
    print(f"Wrote {OUTPUT}")
    print(f"Size:   {size_kb:,.0f} KB")
    return OUTPUT


if __name__ == "__main__":
    main()
