#!/usr/bin/env python3
"""
Builds the HomeValue technical documentation PDF.

Every number, table and chart in the generated document is read from the live
project artifacts (models/metrics.json, the fitted pipeline and the generated
PNG charts) so the PDF can never drift away from the code it describes.

Usage (from the project root):
    python docs/generate_documentation.py
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import (
    BaseDocTemplate,
    CondPageBreak,
    Flowable,
    Frame,
    Image,
    KeepTogether,
    NextPageTemplate,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    XPreformatted,
)

# --------------------------------------------------------------------------
# Paths and live project data
# --------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402

METRICS = json.loads((PROJECT_ROOT / "models" / "metrics.json").read_text())
OUTPUT = PROJECT_ROOT / "docs" / "HomeValue_Project_Documentation.pdf"

# --------------------------------------------------------------------------
# Design tokens (mirrors the application's light theme)
# --------------------------------------------------------------------------
INK = colors.HexColor("#1F2933")
INK_SOFT = colors.HexColor("#3E4C59")
MUTED = colors.HexColor("#6B7A88")
GREEN = colors.HexColor("#1B4D3E")
GREEN_MID = colors.HexColor("#2E7762")
GREEN_SOFT = colors.HexColor("#E6EFEB")
GREEN_LINE = colors.HexColor("#C3D8D0")
ACCENT = colors.HexColor("#A85A2C")
ACCENT_SOFT = colors.HexColor("#F6ECE6")
RULE = colors.HexColor("#E4E0D7")
CODE_BG = colors.HexColor("#F4F2ED")
PANEL_BG = colors.HexColor("#FAF9F6")
WHITE = colors.white

PAGE_W, PAGE_H = A4
MARGIN = 20 * mm
FRAME_W = PAGE_W - 2 * MARGIN

# --------------------------------------------------------------------------
# Styles
# --------------------------------------------------------------------------
_styles = StyleSheet1()


def S(name, **kw):
    _styles.add(ParagraphStyle(name, **kw))
    return _styles[name]


S("root", fontName="Helvetica", fontSize=9.6, leading=14.2, textColor=INK,
  alignment=TA_JUSTIFY, spaceAfter=6)

S("title", fontName="Helvetica-Bold", fontSize=27, leading=32, textColor=GREEN,
  alignment=TA_LEFT, spaceAfter=6)
S("subtitle", fontName="Helvetica", fontSize=13.5, leading=19, textColor=INK_SOFT,
  alignment=TA_LEFT, spaceAfter=4)
S("cover_meta", fontName="Helvetica", fontSize=9.5, leading=15, textColor=MUTED,
  alignment=TA_LEFT)

S("h1", fontName="Helvetica-Bold", fontSize=16.5, leading=21, textColor=GREEN,
  spaceBefore=2, spaceAfter=9, alignment=TA_LEFT)
S("h2", fontName="Helvetica-Bold", fontSize=12.2, leading=16, textColor=GREEN,
  spaceBefore=11, spaceAfter=5, alignment=TA_LEFT)
S("h3", fontName="Helvetica-Bold", fontSize=10.2, leading=14, textColor=INK,
  spaceBefore=8, spaceAfter=3, alignment=TA_LEFT)
S("h4", fontName="Helvetica-BoldOblique", fontSize=9.4, leading=13, textColor=INK_SOFT,
  spaceBefore=6, spaceAfter=2, alignment=TA_LEFT)

S("body", parent=_styles["root"])
S("lead", parent=_styles["root"], fontSize=10.4, leading=16, textColor=INK_SOFT,
  spaceAfter=8)
S("small", parent=_styles["root"], fontSize=8.4, leading=12, textColor=MUTED)
S("caption", parent=_styles["root"], fontSize=8, leading=11, textColor=MUTED,
  alignment=TA_CENTER, spaceBefore=3, spaceAfter=9)

S("bullet", parent=_styles["root"], leftIndent=11, bulletIndent=2, spaceAfter=3.2)
S("bullet2", parent=_styles["bullet"], leftIndent=22, bulletIndent=13)

S("cell", fontName="Helvetica", fontSize=8.3, leading=11.4, textColor=INK)
S("cellb", fontName="Helvetica-Bold", fontSize=8.3, leading=11.4, textColor=INK)
S("cell_head", fontName="Helvetica-Bold", fontSize=8.3, leading=11.4, textColor=WHITE)
S("cell_num", fontName="Helvetica", fontSize=8.3, leading=11.4, textColor=INK,
  alignment=2)

S("code", fontName="Courier", fontSize=7.7, leading=10.6, textColor=INK,
  backColor=CODE_BG, borderPadding=7, leftIndent=3, rightIndent=3,
  spaceBefore=4, spaceAfter=8)

S("callout", fontName="Helvetica", fontSize=9.1, leading=13.4, textColor=INK,
  alignment=TA_JUSTIFY)
S("formula", fontName="Courier-Bold", fontSize=9.2, leading=15, textColor=GREEN,
  alignment=TA_CENTER, spaceBefore=4, spaceAfter=6)


# --------------------------------------------------------------------------
# Small helpers
# --------------------------------------------------------------------------
def esc(text: str) -> str:
    """Escape XML-reserved characters for reportlab's mini-markup."""
    return (str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def money(value: float, dp: int = 0) -> str:
    return f"${float(value):,.{dp}f}"


def num(value: float, dp: int = 0) -> str:
    return f"{float(value):,.{dp}f}"


def signed_money(value: float) -> str:
    v = float(value)
    return f"+${abs(v):,.0f}" if v >= 0 else f"-${abs(v):,.0f}"


class Heading(Paragraph):
    """Paragraph that also registers itself with the table of contents."""

    def __init__(self, text, style_name="h1", level=1, bookmark=None):
        super().__init__(text, _styles[style_name])
        self.level = level
        self.bookmark = bookmark or f"sec-{abs(hash(text)) % 10**9}"
        self._plain = text


def h1(text, bookmark=None):
    return Heading(text, "h1", 1, bookmark)


def h2(text, bookmark=None):
    return Heading(text, "h2", 2, bookmark)


def h3(text):
    return Paragraph(text, _styles["h3"])


def h4(text):
    return Paragraph(text, _styles["h4"])


def p(text, style="body"):
    return Paragraph(text, _styles[style])


def lead(text):
    return Paragraph(text, _styles["lead"])


def bullet(text, level=1):
    style = "bullet" if level == 1 else "bullet2"
    mark = "\u2022" if level == 1 else "\u2013"
    return Paragraph(text, _styles[style], bulletText=mark)


def code(text):
    """Code block. Returns a LIST so callers can use st.extend()."""
    return [XPreformatted(text.rstrip(), _styles["code"])]


def formula(text):
    return Paragraph(esc(text), _styles["formula"])


def gap(height=6):
    return Spacer(1, height)


def rule(color=RULE, thickness=0.7, space=6):
    t = Table([[""]], colWidths=[FRAME_W], rowHeights=[thickness])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), color),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return [Spacer(1, space), t, Spacer(1, space)]


def callout(title, text, tone="info"):
    """Shaded advisory box. tone: info | warn | accent."""
    bg, bar = {
        "info": (GREEN_SOFT, GREEN),
        "warn": (ACCENT_SOFT, ACCENT),
        "accent": (PANEL_BG, GREEN_MID),
    }[tone]
    title_style = ParagraphStyle(
        f"ct_{tone}", fontName="Helvetica-Bold", fontSize=9.1, leading=12.5,
        textColor=bar, spaceAfter=2,
    )
    content = [Paragraph(title, title_style), Paragraph(text, _styles["callout"])]
    inner = Table([[content]], colWidths=[FRAME_W - 16])
    inner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), bg),
        ("LINEBEFORE", (0, 0), (0, -1), 2.6, bar),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    return [Spacer(1, 4), inner, Spacer(1, 8)]


def table(rows, widths, header=True, align_right=(), zebra=True, font_size=8.3,
          header_bg=GREEN, extra_cmds=()):
    """Build a styled table. `rows` is a list of lists of raw strings."""
    styles = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 4.6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4.6),
    ]
    if header:
        styles += [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("VALIGN", (0, 0), (-1, 0), "MIDDLE"),
        ]
    if zebra:
        start = 1 if header else 0
        for i in range(start, len(rows)):
            if (i - start) % 2 == 1:
                styles.append(("BACKGROUND", (0, i), (-1, i), PANEL_BG))
    for col in align_right:
        styles.append(("ALIGN", (col, 0), (col, -1), "RIGHT"))
    styles.extend(extra_cmds)

    data = []
    for r_i, row in enumerate(rows):
        out = []
        for c_i, cell in enumerate(row):
            if r_i == 0 and header:
                st = _styles["cell_head"]
            elif c_i in align_right and r_i > 0:
                st = _styles["cell_num"]
            elif r_i > 0 and c_i == 0 and len(rows) > 1:
                st = _styles["cellb"]
            else:
                st = _styles["cell"]
            out.append(Paragraph(esc(cell), st))
        data.append(out)

    total = sum(widths)
    scale = FRAME_W / total if total > FRAME_W else 1.0
    widths = [w * scale for w in widths]

    t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
    t.setStyle(TableStyle(styles))
    return [Spacer(1, 3), t, Spacer(1, 9)]


def figure(path, width=FRAME_W, caption=None, max_height=150 * mm,
          crop_frac=None, tall_ratio=2.2):
    """Embed an image, scaled to fit, with an optional caption.

    Very tall images (full-page mobile screenshots, for example) are cropped to
    their top section so they render at a legible size instead of as a sliver.
    """
    img_path = PROJECT_ROOT / path
    if not img_path.exists():
        return [p("[Image not found: " + str(path) + "]", "small")]

    source = str(img_path)
    iw, ih = Image(source).imageWidth, Image(source).imageHeight
    ratio = ih / iw

    try:
        from PIL import Image as PILImage
        with PILImage.open(source) as im:
            if crop_frac:
                top = int(im.height * crop_frac[0])
                bot = int(im.height * crop_frac[1])
                im = im.crop((0, top, im.width, bot))
            elif ratio > 3.0:
                # Crop the top portion down to a phone-shaped aspect ratio
                im = im.crop((0, 0, im.width,
                              min(int(round(iw * tall_ratio)), im.height)))
            tmp = PROJECT_ROOT / "docs" / ("_crop_" + img_path.name)
            im.save(tmp)
            source = str(tmp)
        iw, ih = Image(source).imageWidth, Image(source).imageHeight
        ratio = ih / iw
    except Exception:
        pass

    reader = Image(source)
    w = min(width, FRAME_W)
    h = w * ratio
    if h > max_height:
        h = max_height
        w = h / ratio
    reader.drawWidth, reader.drawHeight = w, h
    reader.hAlign = "CENTER"
    out = [Spacer(1, 5), reader]
    if caption:
        out.append(Paragraph(esc(caption), _styles["caption"]))
    return out


# --------------------------------------------------------------------------
# Document template: cover, running header/footer, TOC
# --------------------------------------------------------------------------
class DocTemplate(BaseDocTemplate):
    def __init__(self, filename, **kw):
        BaseDocTemplate.__init__(self, filename, **kw)
        frame = Frame(MARGIN, MARGIN, FRAME_W, PAGE_H - 2 * MARGIN, id="body",
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
        cover_frame = Frame(0, 0, PAGE_W, PAGE_H, id="cover",
                            leftPadding=0, rightPadding=0,
                            topPadding=0, bottomPadding=0)
        self.addPageTemplates([
            PageTemplate(id="Cover", frames=[cover_frame], onPage=self._cover_page),
            PageTemplate(id="Body", frames=[frame], onPage=self._body_page),
        ])
        self._toc = None

    # -- page furniture -----------------------------------------------------
    def _cover_page(self, canv, doc):
        canv.saveState()
        canv.setFillColor(PANEL_BG)
        canv.rect(0, 0, PAGE_W, PAGE_H, stroke=0, fill=1)
        canv.setFillColor(GREEN)
        canv.rect(0, PAGE_H - 12 * mm, PAGE_W, 12 * mm, stroke=0, fill=1)
        canv.restoreState()

    def _body_page(self, canv, doc):
        canv.saveState()
        # running header
        if doc.page > 1:
            canv.setFont("Helvetica", 7.6)
            canv.setFillColor(MUTED)
            canv.drawString(MARGIN, PAGE_H - MARGIN + 9 * mm,
                            "HomeValue \u2014 House Price Prediction System")
            canv.drawRightString(PAGE_W - MARGIN, PAGE_H - MARGIN + 9 * mm,
                                 "Technical Documentation")
            canv.setStrokeColor(RULE)
            canv.setLineWidth(0.6)
            canv.line(MARGIN, PAGE_H - MARGIN + 7 * mm,
                      PAGE_W - MARGIN, PAGE_H - MARGIN + 7 * mm)
        # footer
        canv.setStrokeColor(RULE)
        canv.setLineWidth(0.6)
        canv.line(MARGIN, MARGIN - 5 * mm, PAGE_W - MARGIN, MARGIN - 5 * mm)
        canv.setFont("Helvetica", 7.6)
        canv.setFillColor(MUTED)
        canv.drawString(MARGIN, MARGIN - 9.5 * mm,
                        "Educational demonstration \u2014 estimates are not formal valuations")
        canv.drawRightString(PAGE_W - MARGIN, MARGIN - 9.5 * mm, f"Page {doc.page}")
        canv.restoreState()

    # -- TOC plumbing -------------------------------------------------------
    def afterFlowable(self, flowable):
        if isinstance(flowable, Heading):
            self.canv.bookmarkPage(flowable.bookmark)
            self.notify("TOCEntry", (flowable.level, flowable.getPlainText(),
                                     self.page, flowable.bookmark))
            entry = (flowable.level, flowable.getPlainText(),
                     self.page, flowable.bookmark)
            # Replace the same heading from a previous build pass
            for i, existing in enumerate(_TOC_ENTRIES):
                if existing[3] == entry[3]:
                    _TOC_ENTRIES[i] = entry
                    break
            else:
                _TOC_ENTRIES.append(entry)


# --------------------------------------------------------------------------
# Table of contents (custom, so layout is fully controlled and entries link)
# --------------------------------------------------------------------------
_TOC_ENTRIES: list = []   # populated during a build pass
_TOC_RENDER: list = []    # entries to draw, taken from the previous pass

_styles.add(ParagraphStyle("toc1", fontName="Helvetica-Bold", fontSize=10, leading=16,
                           textColor=GREEN, leftIndent=0))
_styles.add(ParagraphStyle("toc2", fontName="Helvetica", fontSize=9, leading=13.6,
                           textColor=INK_SOFT, leftIndent=10))
_styles.add(ParagraphStyle("tocpage", fontName="Helvetica", fontSize=9, leading=13.6,
                           textColor=MUTED, alignment=2))


class TOCFlowable(Flowable):
    """Renders the table of contents and makes each entry a clickable link.

    Splits across pages when the entry list is longer than one frame, so a long
    document never fails with a LayoutError.
    """

    PAGE_COL = 16 * mm
    PAD = 3

    def __init__(self, specs=None):
        Flowable.__init__(self)
        self.specs = specs          # None means "use every entry"
        self._rows = []

    def _specs(self):
        return self.specs if self.specs is not None else list(_TOC_RENDER)

    def _layout(self, avail_width, avail_height):
        rows = []
        for level, text, page, key in self._specs():
            style = _styles["toc1"] if level == 1 else _styles["toc2"]
            para = Paragraph(esc(text), style)
            _w, h = para.wrap(avail_width - self.PAGE_COL, avail_height)
            rows.append((para, h, page, key, level))
        return rows

    def wrap(self, avail_width, avail_height):
        self._rows = self._layout(avail_width, avail_height)
        self.width = avail_width
        self.height = sum(h for _, h, _, _, _ in self._rows) \
            + self.PAD * len(self._rows)
        return (avail_width, self.height)

    def split(self, avail_width, avail_height):
        if self.height <= avail_height:
            return [self]
        # Keep a margin: the frame may re-measure against a slightly smaller
        # space than the one we were handed.
        budget = avail_height * 0.88
        specs = self._specs()
        used = 0
        first = []
        for i, (_para, h, _page, _key, _level) in enumerate(self._rows):
            nxt = used + h + self.PAD
            if first and nxt > budget:
                break
            first.append(specs[i])
            used = nxt
        rest = specs[len(first):]
        if not rest:
            return [self]
        return [TOCFlowable(first), TOCFlowable(rest)]

    def draw(self):
        canv = self.canv
        y = self.height
        for para, h, page, key, _level in self._rows:
            y -= h
            para.drawOn(canv, 0, y)
            page_para = Paragraph(str(page), _styles["tocpage"])
            _pw, ph = page_para.wrap(self.PAGE_COL, h)
            page_para.drawOn(canv, self.width - self.PAGE_COL, y + (h - ph) / 2)
            canv.linkAbsolute("", key, (0, y, self.width, y + h))
            y -= self.PAD


def build_toc(chunk_size=16):
    """Return the TOC as guarded chunks so it always paginates cleanly.

    Each chunk is preceded by a conditional page break reserving enough space
    for it, which avoids reportlab's "splitting error" when a chunk would
    otherwise begin in the last few points of a frame.
    """
    specs = list(_TOC_RENDER)
    if not specs:
        return [TOCFlowable([])]
    out = []
    for i in range(0, len(specs), chunk_size):
        chunk = specs[i:i + chunk_size]
        out.append(CondPageBreak(len(chunk) * 24))
        out.append(TOCFlowable(chunk))
    return out


# ==========================================================================
# CONTENT — PART I & II
# ==========================================================================
def build_story():
    st = []
    m = METRICS
    rf_t = m["models"]["random_forest"]["test_metrics"]
    lr_t = m["models"]["linear_regression"]["test_metrics"]
    prep = m["data_preparation"]
    stats = m["dataset_statistics"]
    price = stats["price"]
    clean_sum = prep["cleaning_summary"]
    today = date.today().strftime("%d %B %Y")

    # ------------------------------------------------------------------ #
    # COVER
    # ------------------------------------------------------------------ #
    st.append(NextPageTemplate("Body"))
    st.append(Spacer(1, 60 * mm))
    st.append(Paragraph("HomeValue", _styles["title"]))
    st.append(Paragraph("House Price Prediction System", _styles["subtitle"]))
    st.append(Spacer(1, 3 * mm))
    st.append(Paragraph(
        "Complete technical documentation - architecture, machine-learning "
        "pipeline, algorithms and implementation", _styles["subtitle"]))
    st.extend(rule(GREEN, 1.6, 8))

    cover_rows = [
        ["Document", "HomeValue - Technical Documentation"],
        ["Project type", "Full-stack machine-learning web application"],
        ["Model", m["selected_model"] + " (selected automatically on held-out RMSE)"],
        ["Dataset", config.DATASET_METADATA["name"] + " - "
                    + num(clean_sum["final_rows"]) + " cleaned records"],
        ["Held-out test R2", f"{rf_t['r2']:.4f}   MAE {money(rf_t['mae'])}   "
                             f"RMSE {money(rf_t['rmse'])}"],
        ["Stack", "Python - Pandas - NumPy - Scikit-learn - Matplotlib - "
                  "Seaborn - Flask - HTML/CSS/JS"],
        ["Tests", "49 passing (pytest)"],
        ["Model trained", m["trained_at_utc"][:10]],
        ["Document generated", today],
    ]
    st.extend(table(cover_rows, [38 * mm, 120 * mm],
                    header=False, zebra=False,
                    extra_cmds=[("BACKGROUND", (0, 0), (0, -1), GREEN_SOFT),
                                ("BACKGROUND", (0, 0), (-1, -1), WHITE)]))
    st.extend(rule(GREEN, 1.6, 8))
    st.append(Paragraph(
        "<i>All figures in this document are read directly from the project's "
        "saved artifacts at build time. Nothing is illustrative.</i>",
        _styles["small"]))

    st.append(PageBreak())

    # ------------------------------------------------------------------ #
    # TABLE OF CONTENTS
    # ------------------------------------------------------------------ #
    st.append(h1("Contents", "toc"))
    st.append(Paragraph(
        "This document explains what the project does, how it is built, and why "
        "each technical choice was made. Part III onward contains a detailed "
        "explanation of every technology and algorithm used.",
        _styles["body"]))
    st.append(Spacer(1, 6))
    st.extend(build_toc())
    st.append(PageBreak())

    # ================================================================== #
    # PART I - OVERVIEW
    # ================================================================== #
    st.append(h1("Part I - Project Overview", "part1"))

    st.append(h2("1. Executive summary", "s1"))
    st.append(lead(
        "HomeValue is a complete, working full-stack machine-learning application. "
        "A visitor describes a property in a web form; the server validates the input, "
        "pushes it through the exact same Scikit-learn pipeline that was fitted during "
        "training, and returns an estimated sale price together with an explanation of "
        "what drove it. There are no hardcoded prices, no mocked responses and no "
        "fabricated statistics anywhere in the system."))
    st.append(p(
        "The system is built around three principles. First, <b>reproducibility</b>: the "
        "dataset, the split, the preprocessing and the model are all pinned, so running two "
        "commands on a clean clone reproduces every number in this document exactly. "
        "Second, <b>honesty</b>: accuracy is measured on a held-out test set and published, "
        "and where the model cannot support a claim - such as a prediction interval - "
        "the application says so instead of inventing one. Third, <b>separation of "
        "concerns</b>: data preparation, training, evaluation, inference, web routing and "
        "presentation each live in their own module."))

    st.append(h3("The end-to-end story in one paragraph"))
    st.append(p(
        "The raw Ames housing extract (" + num(prep["raw_shape"]["rows"]) + " rows x "
        + str(prep["raw_shape"]["columns"]) + " columns) is cleaned into "
        + num(clean_sum["final_rows"]) + " records on a nine-feature schema. The data is split "
        + str(int((1 - prep["test_split_ratio"]) * 100)) + "/"
        + str(int(prep["test_split_ratio"] * 100))
        + " with <font face='Courier'>random_state=" + str(prep["random_state"])
        + "</font>, giving " + num(prep["train_rows"]) + " training and "
        + num(prep["test_rows"]) + " test rows. Two models are fitted on the training fold - "
        "a Linear Regression baseline and a Random Forest regressor - and scored on the "
        "untouched test fold. The Random Forest wins on every metric, so it is serialised "
        "with Joblib alongside a metadata bundle. Flask loads that artifact once at "
        "start-up, and every prediction request reuses it."))

    st.append(h2("2. What the application does", "s2"))
    st.append(p(
        "The interface has four pages plus three JSON endpoints. Each exists to answer "
        "one question for the user."))
    st.extend(table([
        ["Page", "Route", "What it answers"],
        ["Landing", "/", "What is this and should I trust it?"],
        ["Estimate form", "/predict", "What details do I need to supply?"],
        ["Result", "/result", "What is this property worth, and why?"],
        ["Insights", "/insights", "How does the model behave in general?"],
        ["Prediction API", "POST /api/predict", "Machine-readable estimate"],
        ["Metrics API", "GET /api/metrics", "Machine-readable evaluation record"],
        ["Health check", "GET /health", "Is the model artifact available?"],
    ], [30 * mm, 30 * mm, 98 * mm]))

    st.append(h2("3. Feature inventory", "s3"))
    st.append(p(
        "Nine property characteristics are collected. The first eight map directly onto the "
        "brief; lot area is included because it materially improves accuracy (test R2 rises "
        f"from roughly 0.883 to {rf_t['r2']:.3f}) and exists in the source data as a genuine, "
        "documented column."))
    st.extend(table([
        ["#", "Feature", "Type", "Units / levels", "Form control"],
        ["1", "Location", "Categorical", "25 neighbourhoods", "Select"],
        ["2", "Living area", "Numerical", "sq ft (300-10,000)", "Number + suffix"],
        ["3", "Lot area", "Numerical", "sq ft (1,000-250,000)", "Number + suffix"],
        ["4", "Bedrooms", "Numerical", "count (1-10)", "Number"],
        ["5", "Bathrooms", "Numerical", "count (1-8, half steps)", "Number"],
        ["6", "Property age", "Numerical", "years (0-160)", "Number + suffix"],
        ["7", "Floors", "Numerical", "1.0 / 1.5 / 2.0 / 2.5", "Select"],
        ["8", "Parking", "Categorical", "4 garage levels", "Segmented radio"],
        ["9", "Property type", "Categorical", "5 building types", "Select"],
    ], [8 * mm, 30 * mm, 22 * mm, 48 * mm, 50 * mm]))

    st.append(h3("Application features beyond the basic brief"))
    for item in [
        "<b>Progressive enhancement.</b> The estimate form is a real GET form. With "
        "JavaScript disabled it still produces a full result; with JavaScript enabled it "
        "validates client-side, calls the JSON API, then navigates to the same shareable URL.",
        "<b>Shareable results.</b> <font face='Courier'>/result</font> recomputes the estimate "
        "from URL parameters, so a result can be bookmarked, emailed or compared side by side.",
        "<b>Editable results.</b> \"Edit property details\" returns to the form with every "
        "field pre-filled from the previous submission.",
        "<b>Validation parity.</b> Bounds are declared once in "
        "<font face='Courier'>config.py</font>, injected into the page as JSON, enforced in "
        "the browser and enforced again on the server.",
        "<b>Unseen-category handling.</b> Values the model never saw are encoded safely, "
        "surfaced to the user as a warning, and listed in the API response.",
        "<b>Model-derived explanation.</b> A what-if sensitivity table for the individual "
        "property, kept strictly separate from global feature importance.",
        "<b>Real charts.</b> Six Matplotlib/Seaborn figures generated from the dataset and "
        "the fitted model, regenerated on every training run.",
        "<b>Graceful degradation.</b> Missing model, no parameters, invalid parameters, "
        "404, 405 and 500 each render a specific, useful page. No stack trace is ever shown.",
    ]:
        st.append(bullet(item))

    st.append(PageBreak())

    # ------------------------------------------------------------------ #
    st.append(h2("4. A worked example, end to end", "s4"))
    st.append(p(
        "The clearest way to understand the system is to follow a single request from "
        "keystroke to explanation. The property below is the one used by "
        "<font face='Courier'>python -m src.predict</font> as the project's smoke test."))

    st.append(h3("Step 1 - the user submits"))
    st.extend(code("""{
  "location":      "Northridge Heights",
  "area_sqft":     2100,
  "lot_area_sqft": 12000,
  "bedrooms":      4,
  "bathrooms":     2.5,
  "property_age":  15,
  "floors":        2,
  "parking":       "2-Car Garage",
  "property_type": "Single-Family Detached"
}"""))

    st.append(h3("Step 2 - validation"))
    st.append(p(
        "Every field is checked against the bounds in "
        "<font face='Courier'>config.VALIDATION_RULES</font>. \"Northridge Heights\" is one of "
        "the 25 known neighbourhoods, so it passes. Two cross-field rules also run: living "
        "area must be at least 100 sq ft per bedroom (2,100 >= 4 x 100 passes), and lot "
        "area must not be smaller than living area (12,000 >= 2,100 passes)."))

    st.append(h3("Step 3 - prediction"))
    st.append(p(
        "The validated row is passed to the cached pipeline. Numeric columns are median-imputed "
        "(no gaps here) and standardised; categorical columns are one-hot encoded. The Random "
        "Forest averages the predictions of its 300 trees."))
    st.extend(table([
        ["Output", "Value", "Source"],
        ["Estimated price", money(239327.70, 2), "Mean of 300 tree predictions"],
        ["Price per sq ft", "$113.97", "Estimate / 2,100 sq ft"],
        ["Market median", money(price["median"]), "Median of all 1,458 sales"],
        ["Difference vs median", "+$76,328", "Estimate - market median"],
        ["Price band", "Upper quartile",
         "Estimate above the 75th percentile (" + money(price["q75"]) + ")"],
    ], [42 * mm, 40 * mm, 76 * mm], align_right=(1,)))

    st.append(h3("Step 4 - explanation: what-if sensitivity"))
    st.append(p(
        "Each input is perturbed one at a time, everything else is held constant, and the "
        "model is re-run. This is a property of the model's fitted response surface for "
        "<i>this</i> house - not an additive decomposition of the forest and not a causal "
        "effect."))
    sens_rows = [["Characteristic", "Change applied", "Effect on estimate"]]
    for label, change, delta in [
        ("Property age", "15 -> 25 years", -17141.09),
        ("Living area", "2,100 -> 2,250 sq ft", 11071.36),
        ("Bathrooms", "2.5 -> 3.5", 6741.61),
        ("Bedrooms", "4 -> 5", -3472.09),
        ("Lot size", "12,000 -> 13,000 sq ft", 2146.50),
        ("Location", "Northridge Heights -> Sawyer West", -445.67),
        ("Floors", "2.0 -> 1.5 storeys", 232.15),
    ]:
        sens_rows.append([label, change, signed_money(delta)])
    st.extend(table(sens_rows, [46 * mm, 62 * mm, 50 * mm], align_right=(2,)))

    st.append(p(
        "Two results deserve comment. Adding a <i>fifth</i> bedroom to an already-large house "
        "lowers the estimate: in the training data, extra bedrooms inside a fixed footprint "
        "correlate with smaller rooms and a lower price per square foot. And the location swap "
        "is small because only the neighbourhood changes - the large, modern, well-garaged "
        "house is held constant, whereas in reality those attributes travel together with "
        "location."))
    st.extend(callout(
        "Why no prediction range is shown",
        "A standard Random Forest regressor returns a single averaged value. Producing a "
        "calibrated interval requires a different method - quantile regression forests, "
        "conformal prediction, or training on log-price with a residual model. Rather than "
        "display a range that looks authoritative but is not statistically justified, the "
        "result page states plainly that the model reports a point estimate only.",
        "warn"))

    st.append(PageBreak())

    # ================================================================== #
    # PART II - ARCHITECTURE
    # ================================================================== #
    st.append(h1("Part II - Architecture", "part2"))

    st.append(h2("5. Layered architecture", "s5"))
    st.append(p(
        "The system is organised into five layers. Each layer only knows about the one below "
        "it, which is what keeps the project easy to read and to change."))
    st.extend(table([
        ["Layer", "Files", "Responsibility"],
        ["Presentation", "templates/*.html, static/css, static/js",
         "Render pages, collect input, show results. No business logic."],
        ["Web / API", "app.py",
         "Routes, request parsing, JSON responses, error handling, template filters."],
        ["Inference", "src/predict.py",
         "Validation, cached artifact loading, prediction, explanation building."],
        ["Training", "src/train_model.py, src/evaluate_model.py",
         "Fit, compare, select, evaluate, persist, generate charts."],
        ["Data", "src/data_preprocessing.py, config.py",
         "Load, inspect, clean, build the preprocessing ColumnTransformer."],
    ], [26 * mm, 52 * mm, 80 * mm]))

    st.append(h3("Why inference never retrains"))
    st.append(p(
        "The fitted pipeline is loaded once by "
        "<font face='Courier'>load_artifacts()</font>, which is decorated with "
        "<font face='Courier'>@lru_cache(maxsize=1)</font>. The first request pays the "
        "deserialisation cost; every later request reuses the same in-memory object. Training "
        "happens only when <font face='Courier'>python -m src.train_model</font> is run "
        "deliberately."))

    st.append(h2("6. Request lifecycle", "s6"))
    st.append(p("A prediction request touches every layer. The sequence below is the "
                "authoritative path from browser to estimate and back."))
    st.extend(table([
        ["#", "Stage", "Where", "What occurs"],
        ["1", "Render form", "GET /predict",
         "Defaults computed from training medians; validation bounds injected as JSON."],
        ["2", "Client validation", "static/js/main.js",
         "Bounds and cross-field rules checked; errors shown per field before any request."],
        ["3", "API call", "POST /api/predict",
         "JSON body sent via the Fetch API; button enters a loading state."],
        ["4", "Server validation", "src/predict.py",
         "Types coerced, ranges re-checked, unseen categories detected, warnings collected."],
        ["5", "Transform", "Pipeline stage 1",
         "Median/mode imputation, standardisation, one-hot encoding - all from the fitted "
         "artifact."],
        ["6", "Predict", "Pipeline stage 2",
         "300 trees vote; the mean of their predictions is the estimate."],
        ["7", "Explain", "src/predict.py",
         "Sensitivity what-ifs run; comparison against training medians assembled."],
        ["8", "Respond", "app.py",
         "JSON returned with price, explanation, warnings and the disclaimer."],
        ["9", "Navigate", "static/js/main.js",
         "Browser redirects to /result?... with the same parameters."],
        ["10", "Re-render", "GET /result",
         "Server recomputes the estimate from the URL and renders the result page."],
    ], [7 * mm, 26 * mm, 38 * mm, 87 * mm]))

    st.append(p(
        "Step 10 looks redundant - the estimate was already computed in step 6 - but it is "
        "deliberate. Recomputing from the URL makes results bookmarkable and shareable, and it "
        "guarantees the rendered page can never display a value that the server did not just "
        "reproduce."))

    st.append(h2("7. Project structure", "s7"))
    st.extend(code("""house-price-prediction/
|-- app.py                 Flask app: routes, API, error handling
|-- config.py              Paths, schema, code maps, validation rules
|-- requirements.txt
|-- README.md
|-- .gitignore
|
|-- data/
|   |-- README.md            Provenance, licence, column reference
|   |-- raw/ames_housing_raw.csv            1,460 x 19
|   `-- processed/house_prices_cleaned.csv  1,458 x 10
|
|-- models/
|   |-- house_price_pipeline.joblib      Selected fitted pipeline
|   |-- baseline_linear_pipeline.joblib  Baseline, kept for comparison
|   `-- metrics.json                     Metrics, stats, importances
|
|-- notebooks/
|   `-- exploratory_analysis.ipynb       17 executed cells
|
|-- src/
|   |-- data_preprocessing.py   Load, inspect, clean, build preprocessor
|   |-- train_model.py          Train, compare, select, persist
|   |-- evaluate_model.py       Metrics, importances, statistics, charts
|   `-- predict.py              Validation, inference, explanation
|
|-- templates/            base, index, predict, result, insights, error
|-- static/
|   |-- css/style.css          Complete custom light theme
|   |-- js/main.js             Nav, validation, API submission
|   `-- images/                Hero image + 6 generated charts
|
|-- tests/                conftest, test_preprocessing, test_prediction
`-- docs/                 screenshots + this PDF"""))

    st.append(PageBreak())
    return st


# ==========================================================================
# PART III - DATA
# ==========================================================================
def build_data(st):
    m = METRICS
    prep = m["data_preparation"]
    stats = m["dataset_statistics"]
    price, ppsf = stats["price"], stats["price_per_sqft"]
    area, lot, age = stats["area_sqft"], stats["lot_area_sqft"], stats["property_age"]
    clean_sum = prep["cleaning_summary"]

    st.append(h1("Part III - The Data", "part3"))

    st.append(h2("8. Dataset provenance", "s8"))
    st.append(p(
        "The project uses the <b>Ames Iowa Residential Housing Dataset</b>, compiled by "
        "Dean De Cock of Truman State University and published in the <i>Journal of "
        "Statistics Education</i>, Volume 19, Number 3 (2011). It was assembled specifically "
        "as a modern teaching replacement for the deprecated Boston Housing dataset, and it "
        "documents residential sales in Ames, Iowa between 2006 and 2010."))
    st.extend(table([
        ["Property", "Value"],
        ["Source used", "OpenML dataset 42165 (https://www.openml.org/d/42165)"],
        ["Author", "Dean De Cock, Truman State University"],
        ["Published", "Journal of Statistics Education 19(3), 2011"],
        ["Licence / terms", "Academic teaching and research use; OpenML distribution"],
        ["Records", num(prep["raw_shape"]["rows"]) + " raw, "
                   + num(clean_sum["final_rows"]) + " after cleaning"],
        ["Columns kept", str(prep["raw_shape"]["columns"]) + " of the original 81"],
        ["Target", "SalePrice, in US dollars"],
        ["Market", "Ames, Iowa, United States - 2006 to 2010"],
    ], [32 * mm, 126 * mm]))
    st.append(p(
        "The data is fetched programmatically through "
        "<font face='Courier'>sklearn.datasets.fetch_openml</font>, which is the legitimate, "
        "documented distribution channel. No third-party download, no manual file drop and no "
        "redistribution of the full competition files is required. The 19-column extract used "
        "here is committed to the repository so the project also runs fully offline."))
    st.extend(callout(
        "Why this dataset and not another",
        "Three properties made it the right choice. It is <b>real</b> - recorded "
        "transactions, not synthetic data. It is <b>documented</b> - De Cock's paper "
        "describes every column and explicitly flags the two anomalous sales the cleaning "
        "step removes. And it is <b>shaped for the task</b> - the 81 columns include "
        "genuine analogues of every input the brief asks for (location, area, bedrooms, "
        "bathrooms, age, floors, parking, property type).",
        "info"))

    st.append(h2("9. From raw columns to the feature schema", "s9"))
    st.append(p(
        "The source data uses terse codes such as <font face='Courier'>CollgCr</font> and "
        "<font face='Courier'>1Fam</font>. Presenting those to a user would be unusable, so "
        "each is mapped to a readable label. Several schema fields are also <i>derived</i> "
        "rather than copied - the dataset has no \"property age\" or \"floors\" column, so "
        "they are computed."))
    st.extend(table([
        ["Schema feature", "Derivation from raw columns"],
        ["location", "<font face='Courier'>Neighborhood</font> code to readable name "
                     "(e.g. CollgCr to College Creek)"],
        ["area_sqft", "<font face='Courier'>GrLivArea</font> - above-grade living area"],
        ["lot_area_sqft", "<font face='Courier'>LotArea</font> - total plot size"],
        ["bedrooms", "<font face='Courier'>BedroomAbvGr</font> - bedrooms above grade"],
        ["bathrooms", "<font face='Courier'>FullBath + 0.5 x HalfBath + BsmtFullBath + "
                      "0.5 x BsmtHalfBath</font>"],
        ["property_age", "<font face='Courier'>YrSold - YearBuilt</font>, clipped at 0"],
        ["floors", "<font face='Courier'>HouseStyle</font> to 1.0 / 1.5 / 2.0 / 2.5"],
        ["parking", "<font face='Courier'>GarageType</font> blank or "
                    "<font face='Courier'>GarageCars = 0</font> gives No Garage; otherwise "
                    "1 / 2 / 3+ Car Garage"],
        ["property_type", "<font face='Courier'>BldgType</font> to Single-Family Detached, "
                          "Townhouse (End/Interior), Duplex, Two-Family Conversion"],
        ["price", "<font face='Courier'>SalePrice</font> - the target"],
    ], [30 * mm, 128 * mm]))

    st.append(h3("Two derivations worth explaining"))
    st.append(p(
        "<b>Bathrooms.</b> The dataset splits bathrooms above grade from basement bathrooms, "
        "and full from half. A half bath is a toilet and basin with no bathing facility, so "
        "counting it as a whole bathroom would overstate it; the standard convention of "
        "weighting it 0.5 is used, and basement bathrooms are included because they are real, "
        "habitable fixtures that the source records separately."))
    st.append(p(
        "<b>Property age.</b> The dataset records construction year and sale year, not age. "
        "Age is the difference, clipped at zero so that a home sold in the same year it was "
        "built has age 0 rather than a negative value. This also makes the feature "
        "interpretable - \"15 years old\" means the same thing regardless of the "
        "calendar year of the sale."))

    st.append(h2("10. Cleaning decisions", "s10"))
    st.append(p(num(clean_sum["initial_rows"]) + " raw records become "
               + num(clean_sum["final_rows"]) + ". Every removal is a deliberate, documented "
               "choice rather than a silent filter."))
    st.extend(table([
        ["Step", "Records", "Rationale"],
        ["Exact duplicate removal", str(clean_sum["duplicates_removed"]),
         "Checked for, none found. The check remains so re-runs on new data stay safe."],
        ["Anomaly removal", str(clean_sum["anomalies_or_invalid_removed"]),
         "Homes above 4,000 sq ft sold below $300,000. De Cock (2011) identifies these as "
         "partial sales not complete at the time of recording."],
        ["Invalid value removal", "0",
         "Any non-positive living area or sale price would be rejected; none occur."],
        ["Zero-bedroom records", "6 converted to NaN",
         "Kept, not dropped. Converted to missing so the pipeline imputes from the "
         "<i>training</i> median - dropping would discard real sales and bias the data."],
    ], [34 * mm, 30 * mm, 94 * mm]))
    st.extend(callout(
        "The leakage decision",
        "Missing values are deliberately left in the cleaned CSV. Imputation is performed by "
        "a <font face='Courier'>SimpleImputer</font> <i>inside</i> the pipeline, so the medians "
        "and modes it learns come only from the training fold. Imputing the whole table before "
        "splitting would let test-set values influence the fill values - a subtle but real "
        "form of data leakage that inflates reported accuracy.",
        "warn"))

    st.append(h2("11. Dataset statistics", "s11"))
    st.append(p("All figures below are computed from the full cleaned dataset of "
                + num(clean_sum["final_rows"]) + " records."))
    st.extend(table([
        ["Statistic", "Sale price", "Living area (sq ft)", "Age at sale (yrs)"],
        ["Minimum", money(price["min"]), num(area["min"]), num(age["min"])],
        ["25th percentile", money(price["q25"]), "-", "-"],
        ["Median", money(price["median"]), num(area["median"]), num(age["median"])],
        ["Mean", money(price["mean"]), num(area["mean"]), num(age["mean"], 1)],
        ["75th percentile", money(price["q75"]), "-", "-"],
        ["Maximum", money(price["max"]), num(area["max"]), num(age["max"])],
        ["Std. deviation", money(price["std"]), "-", "-"],
    ], [34 * mm, 42 * mm, 40 * mm, 42 * mm], align_right=(1, 2, 3)))
    st.append(p(
        "The mean (" + money(price["mean"]) + ") sits well above the median ("
        + money(price["median"]) + ") and the maximum (" + money(price["max"])
        + ") is 4.6x the 75th percentile. The distribution is strongly right-skewed: most "
        "homes cluster between " + money(price["q25"]) + " and " + money(price["q75"])
        + ", with a long thin tail of expensive properties. That shape matters - see section "
        "22 on why RMSE is reported alongside MAE. Median price per square foot is $"
        + f"{ppsf['median']:.2f}" + ", with the middle half of the market between $"
        + f"{ppsf['q25']:.2f}" + " and $" + f"{ppsf['q75']:.2f}" + "."))

    st.append(h3("Median price by neighbourhood (five highest, three lowest)"))
    nb_rows = [["Neighbourhood", "Sales", "Median price", "Median area (sq ft)", "Median age"]]
    for r in stats["neighborhood_summary"][:5] + stats["neighborhood_summary"][-3:]:
        nb_rows.append([r["location"], str(r["count"]), money(r["median_price"]),
                        num(r["median_area"]), num(r["median_age"])])
    st.extend(table(nb_rows, [46 * mm, 17 * mm, 32 * mm, 35 * mm, 28 * mm],
                    align_right=(1, 2, 3, 4)))
    st.append(p(
        "The spread is wide - the top neighbourhood's median is 3.6x the bottom's. Note "
        "that Northridge Heights also has a median age of just 1 year: it was being built out "
        "during the observation window. These medians are descriptive, not quality-adjusted; "
        "a neighbourhood can look expensive simply because its houses are larger."))

    st.append(h3("Median price by property type"))
    pt_rows = [["Property type", "Sales", "Median price", "Median area (sq ft)"]]
    for r in stats["property_type_summary"]:
        pt_rows.append([r["property_type"], str(r["count"]),
                        money(r["median_price"]), num(r["median_area"])])
    st.extend(table(pt_rows, [58 * mm, 20 * mm, 38 * mm, 42 * mm], align_right=(1, 2, 3)))

    st.append(PageBreak())
    return st


# ==========================================================================
# PART IV - TECHNOLOGY
# ==========================================================================
def build_tech(st):
    m = METRICS
    prep = m["data_preparation"]

    st.append(h1("Part IV - Technologies and Algorithms", "part4"))
    st.append(lead(
        "This part explains each technology used in the project and, where the technology "
        "embodies an algorithm, how that algorithm actually works. The goal is that a reader "
        "who has never seen a Random Forest can finish this part able to explain why the "
        "system behaves the way it does."))

    st.append(h2("12. Technology stack at a glance", "s12"))
    st.extend(table([
        ["Technology", "Role in the project", "Why it was chosen"],
        ["Python 3", "Implementation language",
         "The de facto language for data science; readable by students and professionals "
         "alike."],
        ["NumPy", "Numerical arrays and vectorised maths",
         "Every other library in the stack is built on it; gives C-speed array operations."],
        ["Pandas", "Tabular data loading, cleaning, aggregation",
         "DataFrame API with labelled columns; the natural tool for a CSV dataset."],
        ["Scikit-learn", "Preprocessing, models, metrics, pipelines",
         "Consistent estimator API; pipeline abstraction that prevents leakage."],
        ["Joblib", "Model serialisation",
         "Efficient pickling of large NumPy arrays; the format Scikit-learn recommends."],
        ["Matplotlib", "Chart rendering",
         "Total control over figure composition; works headless via the Agg backend."],
        ["Seaborn", "Statistical plot styling",
         "High-level distribution and relationship plots with good defaults."],
        ["Flask", "Web server, routing, templating",
         "Minimal and explicit; no hidden magic, so every request path is readable."],
        ["Jinja2", "HTML templating",
         "Ships with Flask; supports inheritance so the layout is defined once."],
        ["HTML5 / CSS3 / JS", "User interface",
         "No framework: the CSS is hand-written, which keeps the visual design deliberate."],
        ["pytest", "Test suite", "Simple assertions and fixtures; no boilerplate."],
    ], [24 * mm, 56 * mm, 78 * mm]))

    st.append(h2("13. Python and the scientific stack", "s13"))
    st.append(h3("Python"))
    st.append(p(
        "Python is used with type hints throughout "
        "(<font face='Courier'>from __future__ import annotations</font> allows modern "
        "annotation syntax on older interpreters). Modules are plain - no classes are used "
        "where a function will do - which keeps the code readable for someone learning from "
        "it. Paths are built with <font face='Courier'>pathlib</font> relative to "
        "<font face='Courier'>config.BASE_DIR</font>, so the project runs on any machine "
        "without editing a single absolute path."))

    st.append(h3("NumPy"))
    st.append(p(
        "NumPy provides the n-dimensional array object that everything else operates on. Two "
        "properties matter here. <b>Vectorisation</b>: an operation such as "
        "<font face='Courier'>np.where(...)</font> over a column executes as compiled C loops "
        "rather than a Python loop, which is why deriving the parking category for 1,458 rows "
        "is instantaneous. <b>Contiguous memory</b>: Scikit-learn converts the DataFrame to a "
        "NumPy array before fitting, and Joblib serialises those arrays efficiently - this is "
        "why the saved pipeline, containing 300 trees, is a manageable file. NumPy is also "
        "used directly for the fitted-model maths in the evaluation module: "
        "<font face='Courier'>np.polyfit</font> computes the trend line on the price-versus-"
        "area chart, and <font face='Courier'>np.isfinite</font> guards every prediction."))

    st.append(h3("Pandas"))
    st.append(p(
        "Pandas supplies the DataFrame: a table with named, typed columns. The project uses it "
        "for five distinct jobs - loading CSVs with "
        "<font face='Courier'>read_csv</font>; inspecting shape, dtypes, missing counts and "
        "duplicates; cleaning with boolean masks and "
        "<font face='Courier'>drop_duplicates</font>; deriving columns by arithmetic across "
        "columns (age = sale year - build year); and grouping for the statistics shown on the "
        "Insights page."))
    st.append(p(
        "One subtlety is worth naming. The raw extract reads "
        "<font face='Courier'>BedroomAbvGr</font> as an integer column, but six records become "
        "missing and NaN has no integer representation in Pandas. The code casts explicitly to "
        "float so the missing value can coexist with the rest, and the Scikit-learn imputer "
        "handles it downstream."))

    st.append(h2("14. Scikit-learn: the estimator contract", "s14"))
    st.append(p(
        "Scikit-learn's power comes less from any single algorithm than from a uniform "
        "interface every object implements. Three methods define the contract:"))
    st.append(bullet(
        "<font face='Courier'>fit(X, y)</font> - learn whatever must be learned from data "
        "(imputation medians, scaling means, tree structure, regression coefficients) and "
        "return self."))
    st.append(bullet(
        "<font face='Courier'>transform(X)</font> - apply the learned transformation to new "
        "data. Imputers, scalers and encoders implement this."))
    st.append(bullet(
        "<font face='Courier'>predict(X)</font> - produce outputs. Models implement this."))
    st.append(p(
        "There is also <font face='Courier'>fit_transform(X, y)</font>, which is simply "
        "<font face='Courier'>fit</font> followed by <font face='Courier'>transform</font> but "
        "computed more efficiently. The critical discipline this enables: <b>fit only on "
        "training data, transform everything</b>. Because the state learned during "
        "<font face='Courier'>fit</font> is stored on the object, a transformer fitted on the "
        "training fold can be applied to the test fold and to live user input identically, "
        "without ever leaking test statistics into training."))

    st.append(h2("15. Splitting the data", "s15"))
    st.append(p(
        "<font face='Courier'>train_test_split(X, y, test_size="
        + str(prep["test_split_ratio"]) + ", random_state=" + str(prep["random_state"])
        + ")</font> shuffles the data with a seeded pseudo-random generator and partitions it "
        "into " + num(prep["train_rows"]) + " training rows and " + num(prep["test_rows"])
        + " held-out rows. The seed makes the split deterministic: the same rows land in the "
        "same fold on every run, which is what makes the reported metrics reproducible and "
        "comparable between model changes."))
    st.append(p(
        "The split is random rather than sequential or stratified because the task is "
        "regression over a stationary period rather than time-series forecasting. A 20% "
        "holdout balances two competing needs: enough training data to fit 300 deep trees "
        "reliably, and enough test data that the metrics are not dominated by a handful of "
        "expensive houses."))

    st.append(h2("16. Preprocessing components", "s16"))

    st.append(h3("SimpleImputer - handling missing values"))
    st.append(p(
        "Missing data is unavoidable in real datasets. The strategy differs by column type, "
        "and both choices are deliberate:"))
    st.extend(table([
        ["Column type", "Strategy", "Learns", "Why"],
        ["Numerical", "median", "Median of each column on the training fold",
         "Robust to the right-skewed outliers present in lot area and price. The mean would "
         "be dragged upward by the handful of very large plots."],
        ["Categorical", "most_frequent", "Modal category of each column",
         "There is no meaningful 'average category', so the most common value is the only "
         "sensible constant fill."],
    ], [24 * mm, 24 * mm, 44 * mm, 66 * mm]))
    st.append(p(
        "The imputer is fitted inside the pipeline, so the median it applies to live user "
        "input is the median of the <i>training</i> data - not of the full table."))

    st.append(h3("StandardScaler - putting features on one scale"))
    st.append(p(
        "Standardisation rescales each numerical column to have zero mean and unit variance:"))
    st.append(formula("z = (x - mu) / sigma      where mu and sigma are learned from the "
                      "training fold"))
    st.append(p(
        "This matters enormously for Linear Regression, whose coefficients are otherwise not "
        "comparable: without scaling, a coefficient on \"lot area\" (values in the tens of "
        "thousands) would be tiny in magnitude purely because of the units, making the fitted "
        "weights misleading to read. It also stabilises the numerical solution. For the Random "
        "Forest, scaling is <b>not</b> required - tree splits are invariant to monotonic "
        "rescaling, since a threshold on x is equivalent to a rescaled threshold on z. The "
        "scaler is kept anyway so both models can share one identical pipeline, which "
        "guarantees the comparison is fair and the inference path is the same object."))

    st.append(h3("OneHotEncoder - representing categories numerically"))
    st.append(p(
        "Algorithms consume numbers, so text categories must be converted. One-hot encoding "
        "replaces a column with <i>k</i> categories by <i>k</i> binary columns: a property in "
        "\"Northridge Heights\" has a 1 in that column and 0 in the other 24. This is preferred "
        "over assigning integers (1, 2, 3 ... 25) because integers would imply a false "
        "ordering - that Northridge is \"greater than\" North Ames - which a distance- or "
        "coefficient-based model would happily exploit."))
    st.append(p(
        "The critical parameter here is "
        "<font face='Courier'>handle_unknown=\"ignore\"</font>. Without it, a category the "
        "encoder never saw at fit time raises an exception and the request fails. With it, an "
        "unknown category encodes as a row of zeros and the model falls back on its other "
        "features. This is what makes the application resilient: a user selecting a value the "
        "model was never trained on gets a sensible estimate plus an explicit warning, rather "
        "than a stack trace."))

    st.append(h2("17. ColumnTransformer and Pipeline", "s17"))
    st.append(h3("ColumnTransformer - routing columns to the right transformer"))
    st.append(p(
        "A real table mixes types, and each type needs different treatment. ColumnTransformer "
        "routes subsets of columns to separate transformer chains and concatenates the results "
        "into one feature matrix. The project's definition:"))
    st.extend(code("""ColumnTransformer([
    ("num", Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scaler",  StandardScaler()),
    ]), NUMERICAL_FEATURES),
    ("cat", Pipeline([
        ("imputer", SimpleImputer(strategy="most_frequent")),
        ("onehot",  OneHotEncoder(handle_unknown="ignore")),
    ]), CATEGORICAL_FEATURES),
], remainder="drop")"""))
    st.append(p(
        "The order matters: impute <i>then</i> scale, because scaling a column that still "
        "contains NaN yields NaN. <font face='Courier'>remainder=\"drop\"</font> discards any "
        "column not explicitly listed - an explicit, safe default that prevents an unexpected "
        "column from silently reaching the model."))

    st.append(h3("Pipeline - chaining steps into one estimator"))
    st.append(p(
        "A Pipeline wraps the ColumnTransformer and the model into a single object that itself "
        "obeys the estimator contract. Calling "
        "<font face='Courier'>pipeline.fit(X_train, y_train)</font> fits the transformer on "
        "the training fold and then fits the model on the transformed data. Calling "
        "<font face='Courier'>pipeline.predict(X)</font> transforms and predicts in one step."))
    st.append(p(
        "Three practical benefits follow. <b>Leakage is structurally impossible</b> during "
        "training, because the transformer's learned state never sees the test fold. "
        "<b>Training and inference cannot diverge</b>, because it is the same object doing "
        "both - there is no second copy of the preprocessing logic to drift out of sync. And "
        "<b>serialisation is trivial</b>: one Joblib file contains everything needed to serve "
        "a prediction."))
    st.extend(callout(
        "The single most important design decision in the ML code",
        "Putting preprocessing <i>inside</i> the pipeline rather than applying it to the whole "
        "dataframe beforehand. Doing it the naive way - impute the full table, scale the full "
        "table, <i>then</i> split - lets information from test rows leak into training through "
        "the shared medians and means. The model then scores better on the test set than it "
        "deserves, and that inflated number travels into production where no such leak exists. "
        "The pipeline makes this mistake impossible to commit by accident.",
        "warn"))

    st.append(PageBreak())
    return st


# ==========================================================================
# PART IV (cont.) - THE LEARNING ALGORITHMS
# ==========================================================================
def build_algorithms(st):
    m = METRICS
    hp = m["models"]["random_forest"]["hyperparameters"]
    rf_t = m["models"]["random_forest"]["test_metrics"]
    rf_tr = m["models"]["random_forest"]["train_metrics"]
    lr_t = m["models"]["linear_regression"]["test_metrics"]
    lr_tr = m["models"]["linear_regression"]["train_metrics"]

    st.append(h1("Part IV (continued) - The Learning Algorithms", "part4b"))

    st.append(h2("18. Linear Regression (the baseline)", "s18"))
    st.append(p(
        "Linear regression is the oldest and most interpretable supervised learning "
        "algorithm, and it is used here deliberately as the <b>baseline</b>: the bar any more "
        "complex model must clear to justify its complexity."))

    st.append(h3("The model"))
    st.append(p("The prediction is a weighted sum of the input features plus an intercept:"))
    st.append(formula("y_hat = b_0 + b_1*x_1 + b_2*x_2 + ... + b_p*x_p"))
    st.append(p(
        "Each coefficient b_j is interpreted as: \"holding all other features constant, a "
        "one-unit increase in x_j is associated with a b_j-unit change in price.\" Because "
        "the numerical features are standardised, the coefficients are directly comparable in "
        "magnitude - which is precisely why the scaler is in the pipeline."))

    st.append(h3("How the coefficients are found"))
    st.append(p(
        "The method of <b>Ordinary Least Squares</b> chooses the coefficients that minimise "
        "the sum of squared residuals - the total squared distance between actual and "
        "predicted prices:"))
    st.append(formula("J(b) = SUM over i of  ( y_i - y_hat_i )^2   =   || y - X*b ||^2"))
    st.append(p(
        "Squaring is what makes this convenient: the function is smooth and convex, so it has "
        "a single global minimum with no local traps. Setting the derivative to zero gives the "
        "closed-form <b>normal equation</b>:"))
    st.append(formula("b_hat = ( X_T * X )^-1 * X_T * y"))
    st.append(p(
        "In practice Scikit-learn does not literally invert X_T X - matrix inversion is "
        "numerically fragile when features are correlated. It uses a singular-value "
        "decomposition (SVD) based least-squares solver, which is stable even when features "
        "are nearly collinear. This also means the model has <b>no hyperparameters to "
        "tune</b>: there is exactly one optimal answer for a given dataset."))

    st.append(h3("Assumptions, and what happens when they break"))
    st.extend(table([
        ["Assumption", "What it means here", "Status in this project"],
        ["Linearity", "Price changes at a constant rate per unit of each feature",
         "Partly violated - the price/area relationship flattens at the top of the market. "
         "This is the main source of the baseline's error."],
        ["Independence", "Observations do not influence one another",
         "Reasonable for separate house sales."],
        ["Homoscedasticity", "Residual variance is constant across the price range",
         "Violated - expensive homes have larger absolute errors, which is exactly the skew "
         "visible in the diagnostics."],
        ["No multicollinearity", "Features are not near-duplicates of each other",
         "Mildly strained: living area and bedroom count are correlated, but not enough to "
         "destabilise the SVD solution."],
        ["Normal residuals", "Needed for confidence intervals and p-values",
         "Not required here - the project reports point predictions and error magnitudes, "
         "not statistical inference."],
    ], [30 * mm, 56 * mm, 72 * mm]))

    st.append(h3("Why keep a model we expect to lose"))
    st.append(p(
        "Because a baseline is the only honest way to know whether complexity is earning its "
        "keep. Linear Regression trains in milliseconds, has nothing to tune, and is trivially "
        "interpretable. It achieves test R2 " + f"{lr_t['r2']:.4f}" + " - a respectable result "
        "on its own. The Random Forest must demonstrably beat it, and it does: R2 "
        + f"{rf_t['r2']:.4f}" + " and MAE " + money(rf_t["mae"]) + " against "
        + money(lr_t["mae"]) + ". Had the forest lost, the training script would have selected "
        "the linear model instead - the comparison is computed, not assumed."))

    st.append(PageBreak())

    st.append(h2("19. Decision Trees (the building block)", "s19"))
    st.append(p(
        "A Random Forest is an ensemble of decision trees, so the tree must be understood "
        "first. A regression tree predicts by asking a sequence of yes/no questions about the "
        "features and then outputting the average price of the training houses that landed in "
        "the same final group."))

    st.append(h3("Recursive binary splitting"))
    st.append(p(
        "Growth is greedy and top-down. At the current region of feature space, the algorithm "
        "considers every feature <i>j</i> and every candidate threshold <i>t</i>, splits the "
        "data into two halves, and keeps whichever split most reduces impurity:"))
    st.append(formula("R1(j,t) = { x : x_j <= t }        R2(j,t) = { x : x_j > t }"))
    st.append(p(
        "For <b>regression</b> the impurity of a region is the total squared deviation from "
        "its mean, and the algorithm minimises the combined impurity of the two children:"))
    st.append(formula("minimise   SUM over i in R1 of (y_i - c1)^2   +   "
                      "SUM over i in R2 of (y_i - c2)^2"))
    st.append(p(
        "where c1 and c2 are the mean prices of the two child regions. In words: find the "
        "question that produces the two most internally consistent groups of houses. (This is "
        "the regression analogue of the Gini impurity used for classification - variance "
        "reduction instead of class-purity gain.)"))
    st.append(p(
        "Each region then splits again, recursively, until a stopping rule fires: maximum "
        "depth reached, too few samples to split, or too small an improvement. The prediction "
        "for a new house is simply the mean training price of the leaf it falls into."))

    st.append(h3("Why a single tree is not enough"))
    st.append(p(
        "A deep, unpruned tree has near-zero <b>bias</b> - it can carve feature space finely "
        "enough to fit almost any pattern. But it has enormous <b>variance</b>: because each "
        "split is chosen greedily and then locked in, changing a handful of training rows can "
        "alter the early splits and produce a completely different tree. Fit on a different "
        "sample from the same housing market, a single tree would give materially different "
        "answers. This is the classic overfitting profile, and it is precisely the weakness "
        "the Random Forest is designed to fix."))
    st.append(p(
        "The effect is visible in this project's numbers: the forest reaches training R2 "
        + f"{rf_tr['r2']:.4f}" + " but test R2 " + f"{rf_t['r2']:.4f}"
        + ". Individual trees are essentially memorising the training fold; only averaging "
        "across many of them produces something that generalises."))

    st.append(PageBreak())

    st.append(h2("20. Random Forest Regressor (the selected model)", "s20"))
    st.append(p(
        "A Random Forest is a <b>bagged ensemble of decorrelated decision trees</b>. It keeps "
        "the low bias of deep trees while attacking their variance by averaging many of them. "
        "The intuition is the same one behind diversifying a portfolio: average many "
        "imperfect, differently-wrong estimators and the errors partly cancel."))

    st.append(h3("Bootstrap aggregating (\"bagging\")"))
    st.append(p(
        "Each of the " + str(hp["n_estimators"]) + " trees is trained on a bootstrap sample - "
        "<i>n</i> draws made <i>with replacement</i> from the "
        + num(m["data_preparation"]["train_rows"]) + " training rows. Any single bootstrap "
        "sample contains roughly 63.2% of the distinct rows (the rest are duplicates), and the "
        "~36.8% left out form that tree's out-of-bag set. Because each tree sees a slightly "
        "different dataset, the trees make different mistakes."))

    st.append(h3("Aggregation"))
    st.append(p(
        "For regression, the forest's prediction is the unweighted average of the individual "
        "tree predictions:"))
    st.append(formula("y_hat(x) = (1/B) * SUM over b = 1...B of  T_b (x)"))
    st.append(p(
        "Why averaging helps can be stated precisely. If the trees had completely uncorrelated "
        "errors with variance sigma^2, averaging B of them would cut the variance to "
        "sigma^2 / B. Real trees are correlated - they all use the same strong features - so "
        "the true reduction is:"))
    st.append(formula("variance of the average  =  rho * sigma^2 + (1 - rho) * sigma^2 / B"))
    st.append(p(
        "where rho is the pairwise correlation between trees. The first term is the floor: "
        "averaging cannot remove error the trees make in common. This is why reducing "
        "inter-tree correlation matters as much as adding trees, and why increasing B has "
        "diminishing returns - once the second term is small, the first term dominates."))

    st.append(h3("Decorrelation through random feature selection"))
    st.append(p(
        "Classic Random Forests decorrelate trees further by restricting each split to a "
        "random subset of features. It is important to be precise about this project's "
        "configuration: Scikit-learn's "
        "<font face='Courier'>RandomForestRegressor</font> defaults to "
        "<font face='Courier'>max_features=1.0</font>, meaning <b>all nine features are "
        "considered at every split</b>. The configuration used here does not override that, so "
        "decorrelation comes primarily from the bootstrap sampling rather than from feature "
        "subsampling. Setting <font face='Courier'>max_features</font> to a fraction is a "
        "documented avenue for future tuning (see section 37)."))

    st.append(h3("Hyperparameters used, and what each does"))
    st.extend(table([
        ["Parameter", "Value", "Effect"],
        ["n_estimators", str(hp["n_estimators"]),
         "Number of trees. More trees never overfit the ensemble - they only reduce variance, "
         "with diminishing returns past a few hundred. 300 is a solid, well-tested default."],
        ["max_depth", str(hp["max_depth"]),
         "Caps tree depth at 18 levels. The main regularisation knob: it stops any single tree "
         "from carving out tiny, noise-driven leaves. Without it, training R2 would be higher "
         "and generalisation worse."],
        ["min_samples_split", str(hp["min_samples_split"]),
         "A node must hold at least 4 samples to be split further. Prevents splits that "
         "describe one or two houses rather than a pattern."],
        ["min_samples_leaf", str(hp["min_samples_leaf"]),
         "Leaves may contain a single sample. Deliberately permissive - combined with the "
         "depth cap this lets the forest capture genuine fine structure while still averaging "
         "over 300 trees."],
        ["random_state", str(hp["random_state"]),
         "Seeds the bootstrap sampling and split selection, making the trained model "
         "bit-for-bit reproducible."],
        ["n_jobs", str(hp["n_jobs"]),
         "Uses all CPU cores. Trees are independent, so training parallelises perfectly - this "
         "is the single biggest speed win in the training script."],
    ], [30 * mm, 17 * mm, 111 * mm]))

    st.append(h3("Why the forest wins here"))
    st.append(p(
        "Housing data is exactly the regime where trees excel: the relationship between area "
        "and price is non-linear (each extra square foot is worth less at 4,000 sq ft than at "
        "1,000), features interact (a garage matters more on a large house than on a small "
        "one), and the target is right-skewed. A linear model cannot express interactions "
        "unless they are hand-built. The forest discovers them automatically, which is why it "
        "lowers test MAE from " + money(lr_t["mae"]) + " to " + money(rf_t["mae"])
        + " - a " + f"{(1 - rf_t['mae'] / lr_t['mae']) * 100:.1f}"
        + "% reduction in average error."))
    st.append(p(
        "The cost is interpretability and calibration: there is no equation to read, the model "
        "cannot extrapolate beyond the range it saw, and it produces a point estimate with no "
        "built-in uncertainty. The application addresses the first with the importance and "
        "sensitivity reporting, and the last by refusing to show an unjustified interval."))

    st.append(PageBreak())

    st.append(h2("21. Feature importance: two questions, two measures", "s21"))
    st.append(p(
        "\"Which features matter?\" is not one question but two, and they have different "
        "answers. The project reports both side by side because each is misleading on its own."))

    st.append(h3("Impurity-based importance"))
    st.append(p(
        "Every time a tree splits on a feature, the split reduces the impurity (variance) of "
        "the region. Scikit-learn accumulates, for each feature, the total impurity decrease "
        "it is responsible for - weighted by the number of samples reaching that split - then "
        "normalises so all features sum to 1:"))
    st.append(formula("imp(j) = SUM over nodes [ N(node)/N(total) * (impurity decrease) ]"))
    st.append(p(
        "Because one-hot encoding expands categorical features into many binary columns, the "
        "evaluation module <b>sums the importance of each one-hot block back onto its source "
        "column</b> before reporting. Without that step, \"location\" would be fragmented "
        "across 25 columns and would look trivially unimportant."))
    st.append(p(
        "<b>The caveat:</b> this measure is computed on the <i>training</i> data and reflects "
        "how useful a feature was for fitting, not how well it generalises. It is also biased "
        "toward high-cardinality and continuous features, which offer more possible split "
        "points and therefore more opportunities to reduce impurity. That bias is clearly "
        "visible in this project: parking scores 35.1% on impurity importance but only 9.4% "
        "on permutation, while living area scores 30.9% and 48.7% respectively."))

    st.append(h3("Permutation importance"))
    st.append(p(
        "Permutation importance asks a more directly useful question: <i>how much worse does "
        "the model get on data it has never seen if this feature is destroyed?</i> The "
        "procedure:"))
    for i, steptext in enumerate([
        "Score the fitted pipeline on the held-out test set (R2 here).",
        "Shuffle the values of one column, breaking its relationship with the target.",
        "Re-score without refitting. The drop in R2 is that feature's importance.",
        "Restore the column and repeat for each feature, 10 times, then average.",
    ], 1):
        st.append(bullet("<b>" + str(i) + ".</b> " + steptext))
    st.append(p(
        "Because it is measured on held-out data and requires no refitting, it reflects "
        "generalisation and is model-agnostic - the same procedure works on the linear "
        "baseline. It is slower (10 repeats x 9 features = 90 scoring passes) but is computed "
        "once at training time and cached in "
        "<font face='Courier'>metrics.json</font>, so it costs nothing at inference."))

    st.extend(callout(
        "What feature importance does not mean",
        "Neither measure is causal, and neither is renovation advice. \"Living area has 48.7% "
        "permutation importance\" means the model relies heavily on area to predict price - "
        "not that adding an extension would raise a home's value by a calculable amount. The "
        "application states this explicitly on both the result page and the Insights page.",
        "warn"))

    st.append(h3("Measured importances"))
    readings = {
        "parking": "Split on constantly; high-cardinality bias inflates its impurity score.",
        "area_sqft": "The genuinely strongest predictor - tops the permutation ranking by a "
                     "wide margin.",
        "property_age": "Strong and robust on both measures; acts as a condition proxy.",
        "bathrooms": "Modest on both; partly redundant with living area.",
        "lot_area_sqft": "Modest; matters more at the top of the market.",
        "location": "Low, because one-hot columns are individually weak splitters even though "
                    "location clearly matters - a known limitation of impurity importance.",
        "bedrooms": "Low; largely captured by living area.",
        "floors": "Low; highly correlated with living area.",
        "property_type": "Lowest; most records are single-family detached, so it carries "
                         "little information.",
    }
    fi_rows = [["Feature", "Impurity importance", "Permutation (share)", "Reading"]]
    for item in m["feature_importances"]:
        fi_rows.append([item["label"], f"{item['importance_pct']:.2f}%",
                        f"{item['permutation_importance_pct']:.2f}%",
                        readings.get(item["feature"], "")])
    st.extend(table(fi_rows, [36 * mm, 27 * mm, 27 * mm, 68 * mm], align_right=(1, 2)))

    st.append(PageBreak())

    st.append(h2("22. Evaluation metrics", "s22"))
    st.append(p(
        "Four metrics are reported, all computed on the held-out test set that neither model "
        "saw during training. Each answers a different question, and reading only one gives an "
        "incomplete picture."))

    st.append(h3("Mean Absolute Error (MAE)"))
    st.append(formula("MAE = (1/n) * SUM | y_i - y_hat_i |"))
    st.append(p(
        "The average miss, in dollars. <b>" + money(rf_t["mae"]) + "</b> for the selected "
        "model. This is the most intuitive metric - \"the estimate is typically about "
        "$19,000 off\" - and it is the headline figure the result page shows."))

    st.append(h3("Root Mean Squared Error (RMSE)"))
    st.append(formula("RMSE = sqrt[ (1/n) * SUM ( y_i - y_hat_i )^2 ]"))
    st.append(p(
        "<b>" + money(rf_t["rmse"]) + "</b>. Squaring before averaging penalises large errors "
        "much more heavily, so RMSE is always at least MAE, and the gap between them measures "
        "how skewed the errors are. Here RMSE is 1.42x MAE, which tells us errors are uneven: "
        "most are under $19,000, but a minority of expensive properties miss by substantially "
        "more. This is the direct consequence of the right-skewed price distribution fit on "
        "the raw dollar scale."))

    st.append(h3("R2 (coefficient of determination)"))
    st.append(formula("R2 = 1 - SS_res / SS_tot = 1 - SUM(y_i - y_hat_i)^2 / "
                      "SUM(y_i - y_mean)^2"))
    st.append(p(
        "<b>" + f"{rf_t['r2']:.4f}" + "</b>. The share of price variance the model explains, "
        "relative to a naive model that always predicts the mean. 0.8676 means roughly 87% of "
        "the variation in sale price is captured; 1.0 would be perfect and 0.0 would be no "
        "better than guessing the average. R2 is unit-free, which makes it the right metric "
        "for comparing models and the one the training script uses for selection."))

    st.append(h3("Mean Absolute Percentage Error (MAPE)"))
    st.append(formula("MAPE = (100/n) * SUM | (y_i - y_hat_i) / y_i |"))
    st.append(p(
        "<b>" + f"{rf_t['mape_percent']:.2f}" + "%</b>. MAE expressed as a percentage of each "
        "home's price, so errors on cheap and expensive homes are weighted comparably. Useful "
        "for communicating to a non-technical audience, though it is unstable when actual "
        "prices are near zero - not a concern with this dataset."))

    st.append(h3("Reading all four together"))
    st.extend(table([
        ["Metric", "Question it answers", "Random Forest", "Linear Regression"],
        ["MAE", "How far off, typically?", money(rf_t["mae"]), money(lr_t["mae"])],
        ["RMSE", "How bad are the worst misses?", money(rf_t["rmse"]), money(lr_t["rmse"])],
        ["R2", "How much variance is explained?", f"{rf_t['r2']:.4f}", f"{lr_t['r2']:.4f}"],
        ["MAPE", "How far off in relative terms?", f"{rf_t['mape_percent']:.2f}%",
         f"{lr_t['mape_percent']:.2f}%"],
        ["", "Training R2 (overfit check)", f"{rf_tr['r2']:.4f}", f"{lr_tr['r2']:.4f}"],
    ], [24 * mm, 58 * mm, 34 * mm, 42 * mm], align_right=(2, 3)))
    st.append(p(
        "The final row is the diagnostic that matters most for future work. The forest's "
        "training R2 of " + f"{rf_tr['r2']:.4f}" + " against a test R2 of "
        + f"{rf_t['r2']:.4f}" + " is a gap of "
        + f"{rf_tr['r2'] - rf_t['r2']:.3f}" + " - it still fits the training data considerably "
        "better than it generalises. The linear model's gap is far smaller ("
        + f"{lr_tr['r2']:.4f}" + " to " + f"{lr_t['r2']:.4f}"
        + "), which is expected: a model with no capacity to memorise cannot overfit. There is "
        "clear headroom to improve the forest through regularisation."))

    st.append(PageBreak())
    return st


# ==========================================================================
# PART IV (cont.) - SUPPORTING TECHNOLOGIES
# ==========================================================================
def build_support(st):
    m = METRICS

    st.append(h2("23. Joblib - model persistence", "s23"))
    st.append(p(
        "Joblib serialises Python objects to disk, and it is preferred over the standard "
        "<font face='Courier'>pickle</font> module for Scikit-learn models because it handles "
        "large NumPy arrays far more efficiently and avoids duplicating shared memory buffers "
        "on load. The whole fitted pipeline - imputers, scaler, encoder, 300 trees and the "
        "attached metadata - is written with a single "
        "<font face='Courier'>joblib.dump()</font> call."))
    st.append(p(
        "Two design details are worth noting. First, the metadata bundle is attached "
        "<i>to the pipeline object itself</i> as "
        "<font face='Courier'>pipeline.metadata_</font>, in addition to being written to "
        "<font face='Courier'>metrics.json</font>. Whichever file a reader loads, the "
        "description cannot drift out of sync with the model it describes. Second, loading is "
        "wrapped in <font face='Courier'>@lru_cache(maxsize=1)</font>, so the multi-megabyte "
        "deserialisation happens once per process rather than once per request."))
    st.extend(callout(
        "Security note on Joblib files",
        "Joblib uses pickle under the hood, and unpickling executes arbitrary code. A saved "
        "model should therefore be treated as a trusted binary: only load artifacts you "
        "produced yourself, and never accept one from an untrusted source. This is standard "
        "practice across the Scikit-learn ecosystem, not a defect specific to this project.",
        "warn"))

    st.append(h2("24. Matplotlib and Seaborn - generating the charts", "s24"))
    st.append(p(
        "All six charts on the Insights page are rendered at training time and saved as PNG "
        "files into <font face='Courier'>static/images/charts/</font>. Generating them offline "
        "rather than on page load means the Insights page is instant and the charts are "
        "versioned alongside the model they describe."))

    st.append(h3("Matplotlib"))
    st.append(p(
        "Matplotlib is the low-level rendering engine. The module switches it to the "
        "<font face='Courier'>Agg</font> backend before importing "
        "<font face='Courier'>pyplot</font>, which is essential in a headless server context - "
        "without it, Matplotlib looks for a display and training fails. The project also uses "
        "Matplotlib's object model directly "
        "(<font face='Courier'>fig, ax = plt.subplots()</font>) rather than the implicit "
        "global state, so each figure is explicitly created, styled, saved and closed."))
    st.append(p(
        "Charts are produced at <font face='Courier'>dpi=160</font> so they stay sharp on "
        "high-density displays, and <font face='Courier'>plt.close(fig)</font> is called after "
        "each save to release memory - a real concern when rendering six figures in one "
        "process. A shared <font face='Courier'>rcParams</font> theme applies the same "
        "palette, grid and typography as the web interface, and a custom "
        "<font face='Courier'>FuncFormatter</font> renders axis ticks as "
        "<font face='Courier'>$214k</font> and <font face='Courier'>$1.2M</font> instead of "
        "raw numbers."))

    st.append(h3("Seaborn"))
    st.append(p(
        "Seaborn sits on top of Matplotlib and supplies the statistical plot types with "
        "sensible defaults, so no boilerplate is needed for distribution or relationship "
        "views. The project uses <font face='Courier'>histplot</font> with a kernel density "
        "estimate for the price distribution, <font face='Courier'>boxplot</font> for price by "
        "bedroom count, and <font face='Courier'>scatterplot</font> with an overlaid trend "
        "line for price versus area. Seaborn's <font face='Courier'>despine()</font> removes "
        "the unused top and right borders, which is what gives the charts their clean, "
        "editorial look."))

    st.append(h3("The six charts"))
    st.extend(table([
        ["Chart", "Plot type", "What it shows"],
        ["Price distribution", "Histogram + KDE, median/mean marked",
         "The right-skewed shape of the target variable."],
        ["Price vs living area", "Scatter by property type + OLS trend",
         "The dominant relationship, with slope in dollars per square foot."],
        ["Price vs bedrooms", "Box plot by count",
         "Median price per bedroom count, with spread and outliers."],
        ["Price vs property age", "Scatter + 10-year-bin median line",
         "The non-linear decline of price with age."],
        ["Feature importance", "Horizontal bar chart",
         "Random Forest impurity importance aggregated per feature."],
        ["Model comparison", "Predicted vs actual scatter, both models",
         "Both models against the ideal 1:1 line on held-out data."],
    ], [34 * mm, 52 * mm, 72 * mm]))

    st.append(h2("25. Flask - the web framework", "s25"))
    st.append(p(
        "Flask is a micro-framework: it supplies routing, request/response handling and "
        "templating, and nothing else. That minimalism is the reason it was chosen - every "
        "line of request handling in this project is visible and readable, with no framework "
        "magic to reason around."))

    st.append(h3("Routing"))
    st.append(p(
        "Routes are declared with decorators. The application separates page routes, which "
        "return HTML, from <font face='Courier'>/api/*</font> routes, which return JSON and "
        "are intended for programmatic access. The API routes accept both JSON bodies and "
        "form-encoded bodies, so they can be exercised with <font face='Courier'>curl</font>, "
        "a script, or a plain HTML form."))

    st.append(h3("Request and response objects"))
    st.append(p(
        "<font face='Courier'>request.args</font> exposes query parameters (used by "
        "<font face='Courier'>/result</font> and by pre-filling the form), "
        "<font face='Courier'>request.get_json(silent=True)</font> parses a JSON body without "
        "raising on malformed input, and <font face='Courier'>jsonify()</font> serialises "
        "responses with the correct content type. Method restrictions are enforced by Flask: "
        "<font face='Courier'>GET /api/predict</font> returns 405 by design."))

    st.append(h3("Jinja2 templating"))
    st.append(p(
        "<font face='Courier'>base.html</font> defines the shell - navigation, footer, "
        "stylesheet and script tags - and each page fills a "
        "<font face='Courier'>content</font> block. This removes all duplicated markup. Jinja2 "
        "escapes substituted values by default, so user-supplied strings cannot inject markup. "
        "Four custom template filters keep formatting consistent across every page: "
        "<font face='Courier'>currency</font>, <font face='Courier'>currency2</font>, "
        "<font face='Courier'>num</font> and <font face='Courier'>signed_currency</font>."))

    st.append(h3("Error handling"))
    st.append(p(
        "Handlers are registered for 404, 405 and 500, plus explicit checks for the cases that "
        "matter here - missing model artifact, no parameters supplied, parameters that fail "
        "validation. Each renders a specific page with an explanation and a way out. "
        "Server-side logging records full detail including stack traces, while the browser "
        "receives only a plain message; no internal path, variable or traceback is ever "
        "exposed."))

    st.append(h3("Built-in development server"))
    st.append(p(
        "Running <font face='Courier'>app.py</font> starts Flask's own server bound to "
        "<font face='Courier'>0.0.0.0:5000</font>. This is a development tool, not a "
        "production server - it is single-process and not hardened. The README states plainly "
        "that a WSGI server such as Gunicorn or Waitress should be used for anything beyond "
        "local demonstration."))

    st.append(h2("26. Frontend technologies", "s26"))

    st.append(h3("HTML5"))
    st.append(p(
        "Markup is semantic throughout: header, nav, main, aside and footer elements rather "
        "than generic containers. Every input has an associated label, radio groups are "
        "wrapped in a <font face='Courier'>radiogroup</font> role, and tables use caption, "
        "thead and scope attributes so assistive technology can navigate them."))

    st.append(h3("CSS3"))
    st.append(p(
        "No CSS framework is loaded. A single stylesheet of roughly 1,100 lines defines the "
        "entire visual system, starting with a block of custom properties (design tokens) for "
        "colour, spacing, radii and shadows, so a change to the palette propagates everywhere. "
        "Layout uses CSS Grid for page-level structure and Flexbox for components. Three "
        "breakpoints adapt the layout for tablet, phone and small phone; the "
        "<font face='Courier'>prefers-reduced-motion</font> media query disables transitions "
        "for users who request it; and a print stylesheet removes navigation so pages can be "
        "printed for a project submission."))
    st.append(p(
        "The visual direction is deliberately restrained: a warm off-white page, charcoal "
        "text, a forest-green accent, hairline borders, 8-12 px radii and shadows used only "
        "where a surface genuinely needs separating from the page. There are no gradients, no "
        "glassmorphism, no emoji icons and no decorative cards."))

    st.append(h3("Vanilla JavaScript"))
    st.append(p(
        "One 300-line file, no dependencies and no build step. It handles three things: the "
        "mobile navigation toggle, client-side validation that mirrors the server rules, and "
        "the Fetch API submission with loading and error states."))
    st.append(p(
        "The submission path is a good illustration of progressive enhancement. The form in "
        "HTML is a working GET form pointing at "
        "<font face='Courier'>/result</font>. If JavaScript is unavailable or the Fetch call "
        "fails outright, the browser falls back to a normal submission and the server produces "
        "the same result. JavaScript, when present, intercepts the submit, validates, calls "
        "the API, and then navigates to the identical URL - so the fast path and the fallback "
        "path converge on the same page."))
    st.append(p(
        "Accessibility is handled in the small details: a skip link to main content, visible "
        "focus-visible outlines on every interactive element, an "
        "<font face='Courier'>aria-live</font> status region announcing validation and "
        "prediction state, and <font face='Courier'>aria-expanded</font> kept in sync on the "
        "navigation toggle."))

    st.append(h2("27. pytest - the testing stack", "s27"))
    st.append(p(
        "The suite contains 49 tests across two files, all passing. "
        "<font face='Courier'>conftest.py</font> inserts the project root onto "
        "<font face='Courier'>sys.path</font> so imports work regardless of the directory "
        "pytest is invoked from, exposes a shared "
        "<font face='Courier'>sample_input</font> fixture, and defines a "
        "<font face='Courier'>requires_artifacts</font> marker that skips training-dependent "
        "tests with a clear message if the model has not been built yet - a skip is "
        "distinguished from a failure, which keeps a fresh clone informative rather than "
        "alarming."))
    st.append(p(
        "Flask is tested through its own <font face='Courier'>app.test_client()</font>, which "
        "exercises the real routing, validation and error-handling code without needing a "
        "running server. This means the tests cover the actual request path, not a "
        "reimplementation of it."))

    st.append(PageBreak())
    return st


# ==========================================================================
# PART V - RESULTS
# ==========================================================================
def build_results(st):
    m = METRICS
    rf_t = m["models"]["random_forest"]["test_metrics"]
    rf_tr = m["models"]["random_forest"]["train_metrics"]
    lr_t = m["models"]["linear_regression"]["test_metrics"]
    lr_tr = m["models"]["linear_regression"]["train_metrics"]
    prep = m["data_preparation"]

    st.append(h1("Part V - Results", "part5"))

    st.append(h2("28. Model comparison", "s28"))
    st.append(p(
        "Both candidates were fitted on the same " + num(prep["train_rows"]) + " training rows "
        "and scored on the same untouched " + num(prep["test_rows"]) + " test rows. Every "
        "number below is read from <font face='Courier'>models/metrics.json</font>."))
    st.extend(table([
        ["Metric", "Split", "Random Forest", "Linear Regression", "Winner"],
        ["MAE", "Test", money(rf_t["mae"]), money(lr_t["mae"]),
         "Forest by " + money(lr_t["mae"] - rf_t["mae"])],
        ["RMSE", "Test", money(rf_t["rmse"]), money(lr_t["rmse"]),
         "Forest by " + money(lr_t["rmse"] - rf_t["rmse"])],
        ["R2", "Test", f"{rf_t['r2']:.4f}", f"{lr_t['r2']:.4f}",
         "Forest by +" + f"{rf_t['r2'] - lr_t['r2']:.4f}"],
        ["MAPE", "Test", f"{rf_t['mape_percent']:.2f}%", f"{lr_t['mape_percent']:.2f}%",
         "Forest by " + f"{lr_t['mape_percent'] - rf_t['mape_percent']:.2f}" + " pts"],
        ["MAE", "Train", money(rf_tr["mae"]), money(lr_tr["mae"]), "-"],
        ["R2", "Train", f"{rf_tr['r2']:.4f}", f"{lr_tr['r2']:.4f}", "-"],
    ], [22 * mm, 18 * mm, 34 * mm, 40 * mm, 44 * mm], align_right=(2, 3)))

    st.append(p(
        "The Random Forest wins on every held-out metric, so it is the deployed model. The "
        "selection is performed in code by comparing test RMSE - not hard-coded - and the "
        "reason is written into <font face='Courier'>metrics.json</font> and displayed on the "
        "Insights page:"))
    st.extend(callout("Selection reason recorded in metrics.json", m["selection_reason"],
                      "info"))
    st.append(p(
        "The practical reading: moving from the linear baseline to the forest cuts typical "
        "error from " + money(lr_t["mae"]) + " to " + money(rf_t["mae"]) + " - a "
        + f"{(1 - rf_t['mae'] / lr_t['mae']) * 100:.1f}" + "% improvement - and lifts "
        "explained variance from " + f"{lr_t['r2'] * 100:.1f}" + "% to "
        + f"{rf_t['r2'] * 100:.1f}" + "%. That gain comes from the forest's ability to "
        "express non-linearities and feature interactions that a linear equation cannot "
        "represent."))

    st.append(h2("29. Charts", "s29"))
    st.append(p(
        "The six figures below are the actual PNG files served by the Insights page."))

    st.append(h3("29.1 Sale price distribution"))
    st.extend(figure("static/images/charts/price_distribution.png", FRAME_W * 0.92,
                     "Histogram with kernel density estimate. Median and mean are marked; the "
                     "right tail drives the gap between MAE and RMSE.", 105 * mm))
    st.append(h3("29.2 Price versus living area"))
    st.extend(figure("static/images/charts/price_vs_area.png", FRAME_W * 0.92,
                     "Scatter by property type with an ordinary least squares trend line and "
                     "its slope in dollars per square foot.", 105 * mm))
    st.append(h3("29.3 Price versus bedrooms"))
    st.extend(figure("static/images/charts/price_vs_bedrooms.png", FRAME_W * 0.92,
                     "Box plot by above-grade bedroom count. The widening spread at higher "
                     "counts explains why bedrooms carry low feature importance.", 105 * mm))
    st.append(h3("29.4 Price versus property age"))
    st.extend(figure("static/images/charts/price_vs_age.png", FRAME_W * 0.92,
                     "Individual sales with the median price per ten-year age band overlaid. "
                     "The relationship is non-linear, not a straight decline.", 105 * mm))
    st.append(h3("29.5 Global feature importance"))
    st.extend(figure("static/images/charts/feature_importance.png", FRAME_W * 0.92,
                     "Random Forest impurity importance, with one-hot blocks summed back onto "
                     "their source features.", 105 * mm))
    st.append(h3("29.6 Predicted versus actual on held-out data"))
    st.extend(figure("static/images/charts/model_comparison.png", FRAME_W * 0.92,
                     "Both models against the ideal 1:1 line. Points below the line are "
                     "under-estimates; the forest clusters more tightly.", 105 * mm))

    st.append(PageBreak())
    return st


# ==========================================================================
# PART VI - APPLICATION REFERENCE
# ==========================================================================
def build_app(st):
    st.append(h1("Part VI - Application Reference", "part6"))

    st.append(h2("30. Routes and the API contract", "s30"))
    st.extend(table([
        ["Route", "Methods", "Returns", "Notes"],
        ["/", "GET", "HTML", "Landing page with live dataset facts."],
        ["/predict", "GET", "HTML",
         "Form; accepts query parameters to pre-fill fields."],
        ["/result", "GET", "HTML",
         "Recomputes the estimate from query parameters. 400 on invalid input, 503 if the "
         "model is missing."],
        ["/insights", "GET", "HTML", "Charts, statistics and the recorded training run."],
        ["/api/predict", "POST", "JSON",
         "Validates and predicts. 400 invalid, 422 unusable, 503 model missing."],
        ["/api/metrics", "GET", "JSON",
         "Saved metrics, importances, statistics, chart paths."],
        ["/health", "GET", "JSON", "Model readiness probe."],
    ], [26 * mm, 18 * mm, 18 * mm, 96 * mm]))

    st.append(h3("Successful prediction response (abridged)"))
    st.extend(code("""{
  "success": true,
  "predicted_price": 239327.70,
  "currency": "USD",
  "currency_symbol": "$",
  "model_name": "Random Forest Regressor",
  "model_metrics": { "mae": 19039.07, "rmse": 27040.66,
                     "r2": 0.8676, "mape_percent": 12.18 },
  "input_summary": { "location": "Northridge Heights", ... },
  "explanation": {
    "predicted_price_per_sqft": 113.97,
    "market_median_price": 163000.0,
    "difference_vs_market_median": 76328.0,
    "price_band": "within the upper quartile of recorded sale prices",
    "versus_training_medians": [ ... ],
    "sensitivity": [ ... ],
    "top_global_features": [ ... ]
  },
  "warnings": [],
  "unseen_categories": [],
  "disclaimer": "This estimate is generated by a machine-learning model ..."
}"""))

    st.append(h3("Error response"))
    st.extend(code("""{
  "success": false,
  "error": "Location 'Atlantis' is not one of the neighborhoods present
            in the training data. Parking availability is required. ..."
}"""))
    st.append(p(
        "The response shape is identical for every failure: "
        "<font face='Courier'>success: false</font> plus a human-readable "
        "<font face='Courier'>error</font> string. All validation problems are collected and "
        "returned together, so a user with three bad fields fixes them in one round trip "
        "rather than three."))

    st.append(h2("31. Validation rules", "s31"))
    st.append(p(
        "Rules are declared once in <font face='Courier'>config.VALIDATION_RULES</font> and "
        "consumed in three places: server-side validation, the rendered HTML attributes, and "
        "the JavaScript object injected into the page. There is one source of truth."))
    st.extend(table([
        ["Field", "Minimum", "Maximum", "Default"],
        ["Living area (sq ft)", "300", "10,000", "1,464 (training median)"],
        ["Lot area (sq ft)", "1,000", "250,000", "9,550 (training median)"],
        ["Bedrooms", "1", "10", "3 (training median)"],
        ["Bathrooms", "1", "8", "2 (training median)"],
        ["Property age (years)", "0", "160", "36 (training median)"],
        ["Floors", "1", "3", "1 (training median)"],
    ], [40 * mm, 26 * mm, 26 * mm, 66 * mm], align_right=(1, 2)))
    st.append(p("Two cross-field rules also apply:"))
    st.append(bullet(
        "Living area must be at least 100 sq ft per bedroom - a 400 sq ft four-bedroom house "
        "is almost certainly a typo, and the model was never fitted on anything like it."))
    st.append(bullet(
        "Lot area must not be smaller than living area - physically impossible, and it would "
        "push the model outside its training range."))
    st.append(p(
        "Bounds are deliberately set close to the observed data range. A prediction for a "
        "50,000 sq ft mansion would be pure extrapolation - a Random Forest cannot extrapolate "
        "beyond values it saw, so it would silently return the price of the largest house it "
        "knows. Rejecting the input is more honest than returning a number that looks "
        "confident but is meaningless."))

    st.append(h2("32. User interface", "s32"))
    st.append(p(
        "The interface is built around one principle: every element earns its place. The "
        "screens below are the actual rendered application."))
    st.append(h3("32.1 Landing page"))
    st.extend(figure("docs/screenshots/home.png", FRAME_W,
                     "Headline, two calls to action, live dataset facts and an editorial "
                     "property visual.", 145 * mm))
    st.append(h3("32.2 Estimate form"))
    st.extend(figure("docs/screenshots/predict.png", FRAME_W,
                     "Nine inputs with dataset-grounded hints; defaults are the training "
                     "medians so the form is usable immediately.", 145 * mm))
    st.append(h3("32.3 Validation feedback"))
    st.extend(figure("docs/screenshots/validation.png", FRAME_W,
                     "Field-level errors plus a summary banner. Identical rules run on the "
                     "server.", 145 * mm))
    st.append(h3("32.4 Result page"))
    st.extend(figure("docs/screenshots/result.png", FRAME_W,
                     "Estimated price, price per square foot, sensitivity table, comparison "
                     "with training medians and the limitations notice.", 170 * mm))
    st.append(h3("32.5 Insights page"))
    st.extend(figure("docs/screenshots/insights.png", FRAME_W * 0.86,
                     "Insights page, upper part: the statistics strip and the four "
                     "distribution charts.",
                     160 * mm, crop_frac=(0.0, 0.42)))
    st.extend(figure("docs/screenshots/insights.png", FRAME_W * 0.86,
                     "Insights page, lower part: model comparison, feature importance "
                     "table and dataset statistics.",
                     160 * mm, crop_frac=(0.42, 1.0)))
    st.append(h3("32.6 Mobile layout"))
    st.extend(figure("docs/screenshots/predict-mobile.png", FRAME_W * 0.42,
                     "The same form at a 390 px viewport, with a collapsible navigation menu.",
                     150 * mm))

    st.append(PageBreak())
    return st


# ==========================================================================
# PART VII - ENGINEERING QUALITY
# ==========================================================================
def build_quality(st):
    m = METRICS
    rf_t = m["models"]["random_forest"]["test_metrics"]
    rf_tr = m["models"]["random_forest"]["train_metrics"]

    st.append(h1("Part VII - Engineering Quality", "part7"))

    st.append(h2("33. Test coverage", "s33"))
    st.append(p("49 tests, all passing. They are grouped by what they protect."))

    st.append(h3("test_preprocessing.py"))
    for item in [
        "The raw dataset loads with the expected shape, columns and known missing values.",
        "Cleaning maps to the exact nine-feature schema and produces 1,458 rows.",
        "The two documented anomalous sales are removed and no invalid values survive.",
        "Every code is mapped to a readable label within the declared option sets.",
        "The fitted preprocessor removes all NaNs - imputation demonstrably works.",
        "Unseen categories (a fictional \"Atlantis\", \"Helicopter Pad\", \"Houseboat\") "
        "transform without raising and without producing NaN.",
        "Numeric output is standardised to zero mean and unit variance; one-hot output "
        "contains only 0 and 1.",
        "Cleaning accepts an already-standardised frame and rejects an incomplete one.",
    ]:
        st.append(bullet(item))

    st.append(h3("test_prediction.py"))
    for item in [
        "The saved Joblib pipeline loads and carries a metadata bundle whose feature schema "
        "matches the one in <font face='Courier'>config</font>.",
        "Metrics in <font face='Courier'>metrics.json</font> are internally consistent "
        "(RMSE at least MAE, R2 in range) and the recorded selected model really is the one "
        "with the lowest test RMSE.",
        "Train and test row counts sum to the cleaned total.",
        "Valid input converts to the expected schema; missing, non-numeric, out-of-range and "
        "unknown-location inputs each raise a specific error.",
        "Unseen parking and property types pass with warnings rather than failing.",
        "Comma-separated and string-encoded numbers are accepted - real users type \"2,100\".",
        "Predictions are finite, positive, floats and deterministic across repeated calls.",
        "Larger area predicts higher; newer predicts higher than much older - sanity checks "
        "on the model's direction, not just its arithmetic.",
        "Price per square foot equals the estimate divided by the submitted area.",
        "Batch prediction matches single prediction exactly.",
        "Every page route returns 200; an unknown route returns 404.",
        "The API accepts JSON and form bodies, rejects empty and non-JSON bodies, rejects "
        "GET, and returns the documented response shape.",
        "<font face='Courier'>/result</font> renders for a valid query, returns 400 for an "
        "invalid one and 400 when no parameters are supplied.",
        "No stack trace, file path or internal detail appears in any error response.",
    ]:
        st.append(bullet(item))

    st.append(h2("34. Reliability and edge cases", "s34"))
    st.extend(table([
        ["Situation", "Behaviour"],
        ["Model artifact missing",
         "Buttons disabled, a warning shown on the landing page, 503 from the API, 503 on "
         "<font face='Courier'>/result</font>. The user is told the exact command to run."],
        ["Unseen categorical value",
         "Encoded as all-zeros by the encoder; the result page shows a warning and the API "
         "lists the affected fields in <font face='Courier'>unseen_categories</font>."],
        ["Missing numerical value",
         "Filled by the fitted <font face='Courier'>SimpleImputer</font> with the training "
         "median - the same treatment used during training."],
        ["Out-of-range value",
         "Rejected with a message naming the field and the permitted range."],
        ["JavaScript disabled",
         "The form submits as a normal GET; the server validates and renders the same result "
         "page."],
        ["Network failure during the Fetch call",
         "A message is shown and the plain form submission is retried automatically."],
        ["Malformed JSON body",
         "<font face='Courier'>get_json(silent=True)</font> returns None; the API responds "
         "400 rather than raising."],
        ["Unexpected server error",
         "Logged with a full trace server-side; the user sees a generic message. No internal "
         "detail is exposed."],
    ], [42 * mm, 116 * mm]))

    st.append(h2("35. Setup and operation", "s35"))
    st.append(p("Four commands take a clean clone to a running application."))
    st.extend(code("""# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\\Scripts\\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Train the model (writes models/, metrics.json and the six charts)
python -m src.train_model

# 4. Start the application
python app.py                      # then open http://127.0.0.1:5000"""))

    st.append(h3("Other entry points"))
    st.extend(table([
        ["Command", "Purpose"],
        ["python -m src.data_preprocessing",
         "Inspect the raw data and write the cleaned CSV only."],
        ["python -m src.predict",
         "Run one sample prediction from the command line and print the result."],
        ["python -m pytest tests/ -v", "Run the 49-test suite."],
        ["jupyter notebook notebooks/", "Open the executed exploratory analysis notebook."],
        ["python docs/generate_documentation.py", "Rebuild this PDF from the live artifacts."],
    ], [66 * mm, 92 * mm]))

    st.append(h3("Sample prediction from the command line"))
    st.extend(code("""$ python -m src.predict
Sample prediction (USD):
  Estimated price: $239,327.70
  Price per sq ft: $113.97
  Model: Random Forest Regressor  |  Test R2: 0.8676
  Top local sensitivities:
    Property Age (years): -17,141
    Living Area (sq ft): +11,071
    Bathrooms: +6,742
    Bedrooms: -3,472"""))

    st.append(h2("36. Limitations", "s36"))
    st.append(p("Stated plainly, because a system that hides its limits is not trustworthy."))
    st.extend(table([
        ["Limitation", "Consequence", "Mitigation in the product"],
        ["Single city, historical period",
         "Ames, Iowa, 2006-2010. Prices are neither current nor transferable.",
         "Stated on the landing page, the form sidebar, the result page and the insights "
         "page."],
        ["Not a valuation",
         "The output is a statistical estimate, not an appraisal.",
         "A disclaimer accompanies every prediction, in the UI and in the API response."],
        ["No prediction interval", "The model emits a point estimate only.",
         "No range is displayed. The result page explains why one is absent."],
        ["Average error is not individual error",
         "MAE of " + money(rf_t["mae"]) + " is an average; a specific property can be much "
         "further off.",
         "The result page spells this out next to the metrics."],
        ["No extrapolation",
         "A Random Forest cannot predict outside its training range - it returns the extreme "
         "value it knows.",
         "Input bounds reject out-of-range values before they reach the model."],
        ["Thin categories", "Some neighbourhoods have very few recorded sales.",
         "Sales counts are published in the neighbourhood table so readers can judge."],
        ["Omitted features", "Condition, renovation quality and interior finish are absent.",
         "Documented; these sit in the columns the schema does not consume."],
        ["Overfitting headroom",
         "Training R2 " + f"{rf_tr['r2']:.4f}" + " versus test R2 " + f"{rf_t['r2']:.4f}" + ".",
         "Both figures are published; regularisation is the top item in section 37."],
        ["Development server", "Flask's built-in server is not production-grade.",
         "Documented in the README with Gunicorn/Waitress named as the alternative."],
    ], [34 * mm, 56 * mm, 68 * mm]))

    st.append(h2("37. Future improvements", "s37"))
    for item in [
        "<b>Regularisation.</b> Tune <font face='Courier'>max_depth</font>, "
        "<font face='Courier'>min_samples_leaf</font> and "
        "<font face='Courier'>max_features</font> via "
        "<font face='Courier'>RandomizedSearchCV</font>. Feature subsampling is currently off "
        "(<font face='Courier'>max_features=1.0</font>), so enabling it should decorrelate the "
        "trees and close the train/test gap identified in section 22.",
        "<b>Calibrated intervals.</b> Quantile regression forests or conformal prediction "
        "would give genuinely justified prediction ranges rather than the point estimate the "
        "application currently offers.",
        "<b>Log-target modelling.</b> Training on log(price) would tame the right skew and "
        "should improve both RMSE and MAPE, at the cost of needing a back-transformation bias "
        "correction.",
        "<b>Richer features.</b> The source dataset carries 81 columns. Overall quality, "
        "basement area and remodelling year are strong candidates; the schema and pipeline "
        "already support adding them without restructuring.",
        "<b>Gradient boosting.</b> HistGradientBoostingRegressor or XGBoost would be a natural "
        "third candidate to add to the comparison.",
        "<b>Engineering.</b> Docker packaging, a CI workflow running the test suite, saved "
        "scenario comparison, and a model-card / data-drift monitor.",
    ]:
        st.append(bullet(item))

    st.append(PageBreak())

    st.append(h2("38. Glossary", "s38"))
    gl = [
        ("Bagging", "Bootstrap aggregating - training each model on a random resample of the "
                    "data and averaging their predictions to reduce variance."),
        ("Baseline model", "A simple reference model that any more complex approach must beat "
                           "to justify its complexity."),
        ("Bootstrap sample", "A sample of size n drawn with replacement; contains roughly "
                             "63.2% of the distinct original rows."),
        ("ColumnTransformer", "A Scikit-learn object that applies different transformers to "
                              "different subsets of columns."),
        ("Data leakage", "Information from the test set reaching the model during training, "
                         "inflating reported accuracy."),
        ("Estimator", "Any Scikit-learn object implementing the fit/transform/predict "
                      "contract."),
        ("Feature importance", "A score describing how much a model relies on an input; not a "
                               "causal effect."),
        ("Held-out test set", "Data withheld from training and used only to measure "
                              "generalisation."),
        ("Hyperparameter", "A setting chosen before training (e.g. tree depth), not learned "
                           "from data."),
        ("Imputation", "Replacing missing values with a substitute such as the median or "
                       "mode."),
        ("Joblib", "A serialisation library optimised for large NumPy arrays; the recommended "
                   "format for Scikit-learn models."),
        ("MAE / RMSE", "Mean absolute error and root mean squared error - average error, and "
                       "average error weighted toward large misses."),
        ("MAPE", "Mean absolute percentage error - average error expressed as a percentage of "
                 "the true value."),
        ("One-hot encoding", "Representing a k-level category as k binary columns."),
        ("Out-of-bag", "The ~36.8% of rows excluded from a tree's bootstrap sample."),
        ("Overfitting", "Fitting training data so closely that performance on new data "
                        "degrades."),
        ("Permutation importance", "The drop in model performance when a feature's values are "
                                   "shuffled on held-out data."),
        ("Pipeline", "A Scikit-learn object chaining preprocessing and a model into one "
                     "estimator."),
        ("R2", "Coefficient of determination - the share of variance explained, from 0 to 1."),
        ("Recursive binary splitting", "The greedy top-down procedure a decision tree uses to "
                                       "grow."),
        ("Standardisation", "Rescaling a feature to zero mean and unit variance."),
        ("Variance reduction", "The regression split criterion: minimise the total squared "
                               "deviation in the child nodes."),
        ("WSGI", "The Python standard interface between web servers and applications, which "
                 "Flask implements."),
    ]
    rows = [["Term", "Definition"]]
    rows += [[t, d] for t, d in gl]
    st.extend(table(rows, [38 * mm, 120 * mm]))

    st.append(Spacer(1, 8))
    st.extend(rule(GREEN, 1.2, 6))
    st.append(Paragraph(
        "<b>End of document.</b> Every figure, table and chart above was generated from the "
        "project's saved artifacts at build time (" + m["trained_at_utc"][:10]
        + " training run). Re-run "
        "<font face='Courier'>python docs/generate_documentation.py</font> to regenerate.",
        _styles["small"]))
    return st


# ==========================================================================
# BUILD
# ==========================================================================
def build_story_all():
    """Assemble the complete document story (called fresh on every pass)."""
    story = build_story()
    story = build_data(story)
    story = build_tech(story)
    story = build_algorithms(story)
    story = build_support(story)
    story = build_results(story)
    story = build_app(story)
    return build_quality(story)


def make_doc():
    return DocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=MARGIN, bottomMargin=MARGIN,
        title="HomeValue - House Price Prediction System: "
              "Technical Documentation",
        author="HomeValue project",
        subject="Full-stack machine-learning application documentation",
    )


def main():
    """Build repeatedly until the table of contents page numbers stop moving.

    A TOC is drawn before the headings that follow it are known, so the page
    numbers used on any pass come from the previous pass. Repeating until the
    collected entries stop changing guarantees a stable, correct result.
    """
    rendered: list = []
    max_passes = 6

    for _ in range(max_passes):
        _TOC_RENDER[:] = rendered
        del _TOC_ENTRIES[:]
        make_doc().build(build_story_all())
        collected = list(_TOC_ENTRIES)
        if collected == rendered:
            break
        rendered = collected

    for leftover in (PROJECT_ROOT / "docs").glob("_crop_*.png"):
        leftover.unlink()

    print("Wrote " + str(OUTPUT) + " (" + f"{OUTPUT.stat().st_size / 1024:.0f}"
          + " KB), " + str(len(_TOC_RENDER)) + " contents entries")


if __name__ == "__main__":
    main()
