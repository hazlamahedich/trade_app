"""MLflow helpers.

Uses a local file store at ``mlruns/`` in project root. No server required.
"""
from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

try:
    import mlflow  # type: ignore
except ImportError:  # pragma: no cover
    mlflow = None  # type: ignore

from trade_advisor.config import MLRUNS_DIR

_INITIALIZED = False


def init_tracking(experiment: str = "default") -> None:
    global _INITIALIZED
    if mlflow is None:
        return
    mlflow.set_tracking_uri(f"file://{MLRUNS_DIR}")
    mlflow.set_experiment(experiment)
    _INITIALIZED = True


@contextmanager
def run(experiment: str = "default", run_name: str | None = None):
    """Context manager wrapping mlflow.start_run.

    No-ops silently if mlflow is not installed.
    """
    if mlflow is None:
        yield None
        return
    if not _INITIALIZED:
        init_tracking(experiment)
    with mlflow.start_run(run_name=run_name) as active:
        yield active


def log_params(params: dict) -> None:
    if mlflow is None:
        return
    mlflow.log_params({k: v for k, v in params.items() if v is not None})


def log_metrics(metrics: dict) -> None:
    if mlflow is None:
        return
    mlflow.log_metrics({k: float(v) for k, v in metrics.items()})


def log_artifact(path: str | Path) -> None:
    if mlflow is None:
        return
    mlflow.log_artifact(str(path))
