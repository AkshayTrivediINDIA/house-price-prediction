# Deploying HomeValue on Render

This project is already wired for [Render](https://render.com). The repository
contains everything the platform needs:

| File | Purpose |
| --- | --- |
| `render.yaml` | Blueprint: build command, start command, health check, free plan |
| `Procfile` | Same start command, for hosts that read a Procfile instead |
| `.python-version` | Pins Python 3.13.1 so the runtime matches the trained model |
| `requirements.txt` | Pins `scikit-learn==1.6.1`, the version that produced `models/*.joblib` |
| `app.py` | Binds to `$PORT` when run directly; Gunicorn serves it in production |

The trained model (`models/house_price_pipeline.joblib`, ~16 MB), the metrics
and the generated charts are committed, so no training step is required during
the build.

---

## 1. Push the project to GitHub

Render deploys from a Git repository. From the project root:

```bash
git init
git add .
git commit -m "HomeValue: house price prediction app ready for Render"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

> The 16 MB model file is well below GitHub's 100 MB per-file limit, so Git LFS
> is not needed. Confirm `models/*.joblib` and `models/metrics.json` are
> actually committed — the app serves a 503 without them.

---

## 2. Deploy with the Blueprint (recommended)

1. Sign in to <https://dashboard.render.com>.
2. Click **New +** → **Blueprint**.
3. Connect GitHub and select the repository.
4. Give the blueprint a name and click **Apply**.
5. Render creates the web service from `render.yaml` and starts the first build.

When the deploy finishes, the service URL looks like:

```text
https://homevalue-house-price.onrender.com
```

Service names are globally unique on `onrender.com`; Render may append a suffix
if the name is taken. Use the URL shown in the dashboard.

---

## 3. Deploy manually (alternative)

If you prefer not to use the Blueprint:

1. **New +** → **Web Service** → connect the repository.
2. Set:

   | Setting | Value |
   | --- | --- |
   | Language / Runtime | Python 3 |
   | Build command | `pip install --upgrade pip && pip install -r requirements.txt` |
   | Start command | `gunicorn app:app --bind 0.0.0.0:$PORT --workers 1 --threads 4 --timeout 120 --access-logfile - --error-logfile -` |
   | Health check path | `/health` |
   | Instance type | Free |

3. Add environment variable `PYTHON_VERSION=3.13.1` (only needed if the
   `.python-version` file is not picked up).
4. Click **Create Web Service**.

---

## 4. Verify the deployment

Replace `<service>` with your Render URL.

```bash
curl https://<service>.onrender.com/health
```

Expected response:

```json
{"status": "ok", "model_ready": true, "dataset": "Ames Iowa Residential Housing Dataset"}
```

Then check the pages:

| URL | Expected |
| --- | --- |
| `/` | Landing page with dataset stats |
| `/predict` | Estimate form with pre-filled training medians |
| `/insights` | Charts and held-out metrics |
| `/dashboard` | Empty state until predictions are logged |
| `/health` | `model_ready: true` |

Test a real prediction through the API:

```bash
curl -X POST https://<service>.onrender.com/api/predict \
  -H "Content-Type: application/json" \
  -d '{
        "location": "Northridge Heights",
        "area_sqft": 2100,
        "lot_area_sqft": 12000,
        "bedrooms": 4,
        "bathrooms": 2.5,
        "property_age": 15,
        "floors": 2,
        "parking": "2-Car Garage",
        "property_type": "Single-Family Detached"
      }'
```

To populate the dashboard with genuine model runs (the dashboard has a button
for this too):

```bash
curl -X POST https://<service>.onrender.com/api/dashboard/sample \
  -H "Content-Type: application/json" -d '{"count": 40}'
```

---

## 5. Free-plan behaviour (important)

| Behaviour | Consequence |
| --- | --- |
| Spins down after ~15 minutes of inactivity | The next request takes 30–60 s while the container and model load. The first page view after idle can look slow; refresh once. |
| 512 MB RAM | Keep **one** Gunicorn worker. Each worker loads its own copy of scikit-learn and the 16 MB model; two workers can exhaust memory and get the service killed. |
| Ephemeral filesystem | `data/predictions.db` (the prediction log behind `/dashboard`) is wiped on every deploy and restart. Pages themselves are unaffected. |
| Free HTTPS + custom domains | Available; add a custom domain in **Settings → Custom Domains** if needed. |

### Keeping dashboard history across deploys

Persistence requires a paid instance with a disk:

1. Upgrade the service to a paid plan.
2. **Settings → Disks → Add Disk**: name `homevalue-data`, mount path `/var/data`, 1 GB.
3. Add environment variable `PREDICTIONS_DB_PATH=/var/data/predictions.db`.
4. Redeploy. The SQLite file is now created on the disk and survives restarts.

`render.yaml` already contains this disk block, commented out — uncomment it and
add the env var if you move to a paid plan.

---

## 6. Environment variables

| Variable | Required | Default | Notes |
| --- | --- | --- | --- |
| `PORT` | Set by Render | `5000` | Gunicorn and `python app.py` both read it |
| `PYTHON_VERSION` | Optional | from `.python-version` | Use `3.13.1` unless you retrain |
| `PREDICTIONS_DB_PATH` | Optional | `data/predictions.db` | Point at a disk for persistence |

No secrets, API keys or database credentials are required — the app is fully
self-contained.

---

## 7. Troubleshooting

**`InconsistentVersionWarning` or prediction errors after deploy**
The pickled pipeline must be loaded with scikit-learn 1.6.1. `requirements.txt`
pins it; do not loosen the pin unless you retrain with
`python -m src.train_model`.

**Build fails resolving `scikit-learn==1.6.1`**
The runtime Python version is too new. Confirm `.python-version` contains
`3.13.1` (or set `PYTHON_VERSION=3.13.1` in the dashboard). Python 3.15 has no
wheels for scikit-learn 1.6.1.

**`gunicorn: command not found`**
The build did not install `requirements.txt`. Check the build logs and re-run
the deploy with **Manual Deploy → Clear build cache & deploy**.

**`/health` returns `"model_ready": false`**
`models/house_price_pipeline.joblib` or `models/metrics.json` is missing from
the repository. They are intentionally committed; check `.gitignore` and
`git ls-files models/`.

**502 / request timeout on the first visit**
Free instances sleep. Wait for the cold start; if it consistently exceeds 120 s,
raise `--timeout` in the start command or move to a paid instance.

**Dashboard returns 500 / `unable to open database file`**
The configured `PREDICTIONS_DB_PATH` is not writable. Remove the variable (use
the default project-local path) or attach a disk at the path you configured.

**Service runs out of memory**
Use exactly `--workers 1`. Threads (`--threads 4`) give concurrency without
duplicating the model in memory.

---

## 8. Local production check

On Linux/macOS you can reproduce the Render start command:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
gunicorn app:app --bind 127.0.0.1:8000 --workers 1 --threads 4
```

Open <http://127.0.0.1:8000/health>. Gunicorn does not run on Windows — use
`python app.py` there instead.
