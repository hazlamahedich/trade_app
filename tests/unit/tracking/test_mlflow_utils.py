from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from trade_advisor.tracking import mlflow_utils


@pytest.fixture(autouse=True)
def _reset_initialized():
    mlflow_utils._INITIALIZED = False
    yield
    mlflow_utils._INITIALIZED = False


class TestMlflowNone:
    def test_init_tracking_noop_when_none(self):
        with patch.object(mlflow_utils, "mlflow", None):
            mlflow_utils.init_tracking("test")
            assert not mlflow_utils._INITIALIZED

    def test_run_yields_none_when_none(self):
        with patch.object(mlflow_utils, "mlflow", None), mlflow_utils.run("exp") as active:
            assert active is None

    def test_log_params_noop_when_none(self):
        with patch.object(mlflow_utils, "mlflow", None):
            mlflow_utils.log_params({"a": 1})

    def test_log_metrics_noop_when_none(self):
        with patch.object(mlflow_utils, "mlflow", None):
            mlflow_utils.log_metrics({"a": 1.0})

    def test_log_artifact_noop_when_none(self):
        with patch.object(mlflow_utils, "mlflow", None):
            mlflow_utils.log_artifact("/tmp/test.txt")


class TestInitTracking:
    def test_sets_tracking_uri_and_experiment(self):
        mock_mlflow = MagicMock()
        with patch.object(mlflow_utils, "mlflow", mock_mlflow):
            mlflow_utils.init_tracking("my-exp")
            mock_mlflow.set_tracking_uri.assert_called_once()
            mock_mlflow.set_experiment.assert_called_once_with("my-exp")
            assert mlflow_utils._INITIALIZED is True

    def test_idempotent(self):
        mock_mlflow = MagicMock()
        with patch.object(mlflow_utils, "mlflow", mock_mlflow):
            mlflow_utils.init_tracking("exp1")
            mlflow_utils.init_tracking("exp2")
            assert mock_mlflow.set_experiment.call_count == 2


class TestRun:
    def test_auto_inits_on_first_use(self):
        mock_mlflow = MagicMock()
        mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value="active_run")
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
        with patch.object(mlflow_utils, "mlflow", mock_mlflow):
            mlflow_utils._INITIALIZED = False
            with mlflow_utils.run("auto-exp", run_name="r1"):
                pass
            mock_mlflow.set_tracking_uri.assert_called_once()
            mock_mlflow.set_experiment.assert_called_once_with("auto-exp")

    def test_passes_run_name(self):
        mock_mlflow = MagicMock()
        mock_mlflow.start_run.return_value.__enter__ = MagicMock(return_value="active")
        mock_mlflow.start_run.return_value.__exit__ = MagicMock(return_value=False)
        with patch.object(mlflow_utils, "mlflow", mock_mlflow):
            mlflow_utils._INITIALIZED = True
            with mlflow_utils.run(run_name="my-run"):
                pass
            mock_mlflow.start_run.assert_called_once_with(run_name="my-run")


class TestLogParams:
    def test_filters_none_values(self):
        mock_mlflow = MagicMock()
        with patch.object(mlflow_utils, "mlflow", mock_mlflow):
            mlflow_utils.log_params({"a": 1, "b": None, "c": "x"})
            mock_mlflow.log_params.assert_called_once_with({"a": 1, "c": "x"})


class TestLogMetrics:
    def test_coerces_decimal_to_float(self):
        mock_mlflow = MagicMock()
        with patch.object(mlflow_utils, "mlflow", mock_mlflow):
            mlflow_utils.log_metrics({"sharpe": Decimal("1.5")})
            mock_mlflow.log_metrics.assert_called_once_with({"sharpe": 1.5})

    def test_coerces_int_to_float(self):
        mock_mlflow = MagicMock()
        with patch.object(mlflow_utils, "mlflow", mock_mlflow):
            mlflow_utils.log_metrics({"count": 42})
            mock_mlflow.log_metrics.assert_called_once_with({"count": 42.0})
