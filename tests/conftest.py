"""Shared pytest fixtures for the HomeValue test suite.

Tests run against the artifacts produced by `python -m src.train_model`.
If the artifacts are missing, training-dependent tests are skipped with a clear
message so the suite stays informative on a fresh clone.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import config  # noqa: E402


def artifacts_ready() -> bool:
    return config.MODEL_PATH.exists() and config.METRICS_PATH.exists()


requires_artifacts = pytest.mark.skipif(
    not artifacts_ready(),
    reason="Model artifacts missing — run `python -m src.train_model` first.",
)


@pytest.fixture(scope="session")
def project_root() -> Path:
    return PROJECT_ROOT


@pytest.fixture(scope="session", autouse=True)
def _isolate_prediction_log(tmp_path_factory):
    """Point the prediction store at a throwaway database for the whole session.

    This is autouse and session-scoped on purpose: without it, any test that
    reaches the store through a default argument would read and write the real
    data/predictions.db, and a test that clears the log would destroy genuine
    recorded activity. Repointing the module default once, before any test
    imports the app, keeps every test -- including sloppy ones -- off the real
    database.
    """
    from src import prediction_store

    real_path = prediction_store.DEFAULT_DB_PATH
    scratch = tmp_path_factory.mktemp("prediction_log") / "predictions.db"
    prediction_store.init_db(scratch)

    prediction_store.DEFAULT_DB_PATH = scratch
    yield scratch
    prediction_store.DEFAULT_DB_PATH = real_path


@pytest.fixture(scope="session", autouse=True)
def _assert_log_is_isolated(_isolate_prediction_log):
    """Fail loudly if anything re-points the store back at the real database."""
    from src import prediction_store

    assert prediction_store.DEFAULT_DB_PATH != Path(config.DATA_DIR) / "predictions.db", (
        "The prediction store is pointing at the real database during tests."
    )
    yield
    assert prediction_store.DEFAULT_DB_PATH != Path(config.DATA_DIR) / "predictions.db", (
        "A test restored the real prediction database path."
    )


@pytest.fixture(scope="session")
def sample_input() -> dict:
    """A realistic, in-range property description used across tests."""
    return {
        "location": "Northridge Heights",
        "area_sqft": 2100,
        "lot_area_sqft": 12000,
        "bedrooms": 4,
        "bathrooms": 2.5,
        "property_age": 15,
        "floors": 2,
        "parking": "2-Car Garage",
        "property_type": "Single-Family Detached",
    }
