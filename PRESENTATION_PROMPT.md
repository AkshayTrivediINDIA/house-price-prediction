# Presentation prompt — copy everything below the line

Paste the block below into any AI (ChatGPT, Claude, Gemini, Copilot). It contains
every verified fact about the project, so the AI will not have to guess or invent
numbers. Swap the two marked options at the top to taste.

---

## ▶ COPY FROM HERE

You are a presentation designer and technical storyteller. Create a polished,
conference-ready slide deck for a university-level Machine Learning project:

**"HomeValue — A House Price Prediction System"**

**Deliverable format:** [[ OPTION A: A .pptx file I can open in PowerPoint/Google Slides.
OPTION B: A Markdown slide-by-slide script (title, bullets, speaker notes per slide)
that I can paste into Gamma/Beautiful.ai/Canva.
OPTION C: Both. ]]

**Language:** English. [[ Add: "Write all slide text and speaker notes in simple
Hinglish (Hindi in Latin script)" if you want that instead. ]]

**Length:** 16–18 slides. **Audience:** a technical evaluator who knows ML but
has not seen this project. **Tone:** confident, precise, honest. No hype, no
marketing language, no emoji.

---

### HARD RULES — violations make the deck unacceptable

1. **Never invent a number.** Use only the figures given in this brief. If a
   slide needs a number you do not have, leave it out or ask me.
2. **Never claim causation from feature importance.** Importance means
   "associated with the model's predictions", not "causes price".
3. **Never show or imply a prediction interval.** The model emits a point
   estimate only; a calibrated range is not statistically available here. Say so
   explicitly as a limitation.
4. **Never present the output as a property valuation or financial advice.**
5. **Do not add fake testimonials, fake user counts, or stock-photo people.**
6. Every metric must be labelled as train or held-out test. Never mix them.
7. If you generate a .pptx: light theme, off-white background, one restrained
   forest-green accent (#2F6B4F), dark charcoal text (#1F2421), generous white
   space, one idea per slide, max 6 lines per slide, no clip-art, no 3D, no
   gradients on text, no emoji icons. Use simple flat SVG-style shapes and
   real tables/charts instead.

---

### VERIFIED PROJECT FACTS — use these and nothing else

**The problem.** Buyers, sellers and students have no quick, transparent way to
estimate what a home is worth from its physical characteristics. Professional
valuations are slow and costly; online estimators are black boxes.

**The solution.** An end-to-end ML system: a reproducible data pipeline, two
trained and compared regression models, and a Flask web application that serves
estimates with explanations and a live dashboard of prediction activity.

**Dataset — Ames Iowa Residential Housing Dataset**
- Compiled by Dean De Cock, Truman State University; published in the *Journal
  of Statistics Education*, Vol. 19, No. 3 (2011)
- Retrieved programmatically from OpenML (dataset 42165) via
  `sklearn.datasets.fetch_openml(name="house_prices")` — no manual download
- Public domain / CC0, distributed for unrestricted academic use
- Ames, Iowa, USA · sales from **2006 to 2010** · prices in USD
- 1,460 records × 81 available columns → **19 columns extracted** (only what the
  app uses) → **1,458 records × 10 columns** after cleaning
- Median sale price **$163,000**; range $34,900 – $755,000
- Two alternatives were evaluated and rejected: California housing (census-block
  medians, no per-property bedrooms or age) and Boston housing (known ethical
  problems with its constructed variable)

**Data preparation**
- 0 duplicate rows removed
- **2 rows removed**: sales over 4,000 sq ft that sold under $300,000. De Cock
  (2011) documents both as *partial sales* (incomplete construction), not
  arm's-length market transactions, so they are invalid training data
- Derived features: total bathrooms (a half bath counts 0.5, basement baths
  included); property age = year sold − year built, clipped at 0; storeys from
  house style; parking category from garage capacity; neighbourhood codes and
  building types mapped to plain English
- A bedroom count of 0 is treated as *missing*, not as a real studio
- **6 missing bedroom values are deliberately left in place** and filled by a
  `SimpleImputer` fitted on the training split only — this prevents test-set
  information leaking into training

**Nine input features:** location (25 neighbourhoods), living area, lot size,
bedrooms, bathrooms, property age, floors, parking (4 categories), property type
(5 categories). **Target:** sale price.

**Split:** 80/20 · **1,166 training rows · 292 held-out test rows** ·
`random_state=42`. The test set was never used for fitting, tuning or imputation.

**Preprocessing:** `ColumnTransformer` — median/most-frequent imputation,
standard scaling for numeric features, one-hot encoding for categorical ones, all
inside a single `Pipeline` so the exact same transforms apply at inference.

**Model 1 — Linear Regression (baseline, interpretable reference)**

| Metric | Train | Held-out test |
| --- | --- | --- |
| MAE | $21,103.68 | **$21,974.48** |
| RMSE | $30,609.74 | **$30,378.88** |
| R² | 0.8561 | **0.8329** |
| MAPE | 12.68 % | **13.87 %** |

**Model 2 — Random Forest Regressor (selected)**

| Metric | Train | Held-out test |
| --- | --- | --- |
| MAE | $8,324.85 | **$19,039.07** |
| RMSE | $12,949.28 | **$27,040.66** |
| R² | 0.9743 | **0.8676** |
| MAPE | 4.90 % | **12.18 %** |

**Selection.** Random Forest won on every held-out metric: RMSE $27,040.66 vs
$30,378.88 (about 11 % lower), MAE $19,039.07 vs $21,974.48 (about 13 % lower),
and R² 0.8676 vs 0.8329. It also cuts test MAPE from 13.87 % to 12.18 %.

**Feature importance (Random Forest, impurity-based — association, not cause)**

| Feature | Impurity importance | Permutation importance |
| --- | --- | --- |
| Parking / Garage | 35.11 % | 9.36 % |
| Living Area (sq ft) | 30.87 % | **48.70 %** |
| Property Age (years) | 13.45 % | **26.65 %** |
| Bathrooms | 6.99 % | 3.66 % |
| Lot Size (sq ft) | 5.22 % | 3.30 % |
| Location | 3.73 % | 2.08 % |
| Bedrooms | 2.54 % | 3.25 % |
| Floors / Stories | 1.26 % | 2.22 % |
| Property Type | 0.83 % | 0.79 % |

Make the point that impurity importance and permutation importance **disagree
sharply** on parking (35.1 % vs 9.4 %) because garage capacity has many
categories; **permutation importance is the more trustworthy ranking here**, and
it puts living area and property age first. This is a good "thinking
critically" slide.

**Technology stack.** Python 3 · pandas 2.2.3 · NumPy 2.3.5 · scikit-learn
1.6.1 · Matplotlib & Seaborn (static charts) · Flask 3.1.3 · hand-written
HTML/CSS/JavaScript. **No CSS framework, no charting library, no CDN, no
external runtime dependency.** Joblib for model persistence. pytest for tests.

**Application pages**
- **Landing** — headline, two calls to action, dataset facts
- **Estimate form** — nine validated inputs pre-filled with training medians
  (1,464 sq ft · 9,549.5 sq ft lot · 3 bedrooms · 2 bathrooms · 36 years · 1 floor)
- **Result** — estimated price, price per sq ft, a sensitivity table showing how
  the estimate moves when one input changes, and stated limitations
- **Insights** — six Matplotlib/Seaborn charts generated from the real dataset
  and fitted model
- **Dashboard** — live prediction activity (see below)

**Validation and error handling.** Identical rules enforced twice: inline in the
browser for instant feedback, and again on the server, because client-side
checks can be bypassed. Invalid ranges, missing fields and unknown categorical
values all produce clear field-level messages. A failure to log a prediction
never breaks a valid prediction.

**The prediction dashboard (`/dashboard`).** Reports on estimates *this
installation actually served*, stored in SQLite (`data/predictions.db`), and
keeps two things visibly separate:
- **Usage** — counts, medians, distributions of logged predictions. Grows over time.
- **Measured accuracy** — MAE/RMSE/R²/MAPE from `metrics.json`, fixed on the
  held-out test set and **never** affected by usage.

Nothing on it is invented: with an empty log it shows an explicit empty state
rather than placeholder charts. "Log sample activity" runs real properties from
the cleaned dataset through the saved model and tags them `source='sample'` so
they are always distinguishable from form submissions. Seven charts are drawn as
hand-rolled inline SVG — volume over time, price distribution, median by
location, median by property type, area vs price coloured by age, feature
importance, and model performance.

**Testing.** 70 pytest tests, all passing: 49 covering preprocessing, inference,
validation and every route, plus 21 covering the prediction store, the
aggregation layer and the dashboard endpoints. An autouse session fixture
redirects the prediction log to a temporary database so tests can never touch
real recorded activity.

**Honest limitations — include a dedicated slide**
- Geography and time: Ames, Iowa, 2006–2010 only. Nothing about other markets or
  today's price levels.
- Not a valuation: a statistical estimate for education and comparison, not an
  appraisal and not financial advice.
- No prediction interval: point estimate only. Quantile regression forests or
  conformal prediction would be needed for a calibrated range.
- Averages hide individual error: MAE of $19,039 is an average over held-out
  sales; any single property can be much further off.
- Small categories: some neighbourhoods have only a handful of sales, so those
  estimates are noisy.
- Omitted factors: condition, renovation quality, interior finish, school
  catchment and micro-location are absent from the nine features.
- Overfitting headroom: train R² 0.9743 vs test R² 0.8676 shows room for
  regularisation.
- Development server: Flask's built-in server; use Gunicorn or Waitress beyond
  local use.

**Future work.** Hyperparameter tuning with cross-validation; gradient boosting
(XGBoost/LightGBM); quantile regression forests for calibrated intervals;
log-target transformation; target encoding for high-cardinality neighbourhoods;
retraining on current data for a live market.

---

### REQUIRED SLIDE STRUCTURE

1. **Title** — project name, one-line description, tech stack as small chips
2. **Problem** — why house-price estimation is hard and who needs it
3. **Solution at a glance** — data → model → web app, as a simple 3-stage diagram
4. **The dataset** — provenance, licence, size, time window, why this one
5. **Data preparation** — the 19 → 10 transformation, the 2 removed partial
   sales, the deliberate missing values
6. **Exploratory findings** — 2 or 3 real patterns, with the price distribution
   table
7. **Features and preprocessing** — the nine features and the
   `ColumnTransformer` pipeline
8. **Model 1 — Linear Regression** — why a baseline matters, with the table
9. **Model 2 — Random Forest** — why an ensemble, with the table
10. **Model comparison** — side-by-side held-out metrics, the selection decision
11. **Results** — R² 0.8676 and MAE $19,039 in plain language: "the model
    explains about 87 % of price variance on homes it has never seen, and is
    typically off by about $19,000"
12. **Feature importance** — the table, plus the impurity vs permutation
    disagreement and what it teaches
13. **System architecture** — request flow from browser through validation,
    cached inference, pipeline and response
14. **The web application** — the five pages, with the validation story
15. **The prediction dashboard** — usage vs measured accuracy, kept separate;
    the empty-state honesty guarantee
16. **Testing and quality** — 70 tests, what they cover
17. **Limitations and responsible use** — the bullet list above, unabridged
18. **Future work and conclusion** — what would be built next

---

### SPEAKER NOTES

For every slide write 2–4 sentences of speaker notes: what to say, what the
slide proves, and — where relevant — what a sharp evaluator might challenge and
how to answer it. Flag the two questions most likely to come up and give honest
answers:

- *"Can I use this to price my house?"* — No. It is trained on Ames, Iowa,
  2006–2010. It is an educational estimate, not a valuation.
- *"How confident are you in a single prediction?"* — An average miss of
  $19,039, and no calibrated interval is available from a standard Random
  Forest. Any single property can be much further off.

---

### BEFORE YOU FINISH

Re-read every slide and delete any claim that is not supported by the facts
above. Confirm each number appears with its train/test label. Confirm no slide
implies causation, a prediction interval, or a professional valuation.

## ▶ COPY UNTIL HERE

---

## Tips for getting the best result

| You want… | Add this line to the prompt |
| --- | --- |
| More slides | "Expand to 22 slides and add a slide on [topic]." |
| Fewer words | "Max 4 bullets per slide, max 12 words per bullet." |
| A viva / defence deck | "Add a likely-questions slide with 8 questions and model answers." |
| Hindi / Hinglish | "Write all slide text and speaker notes in Hinglish." |
| Printable handout | "Also produce a one-page PDF summary of the deck." |
| Code walkthrough | "Add 3 slides showing the key code: the ColumnTransformer, the training loop, and the prediction endpoint." |

## Where the numbers came from

Every figure above is read from `models/metrics.json`, which is written by
`python -m src.train_model` from the actual run — not hand-typed. If you
retrain, regenerate the numbers before reusing this prompt:

```bash
cd house-price-prediction
python -m src.train_model
python -c "import json;m=json.load(open('models/metrics.json'));print(json.dumps(m['models'],indent=2))"
```

Companion documents: `README.md` (full project write-up) and
`docs/HomeValue_Project_Documentation.pdf` (44-page long-form documentation).
