from __future__ import annotations

import warnings

import pytest


class TestApiDeprecation:
    @pytest.mark.test_id("1.0-UNIT-016")
    @pytest.mark.p3
    def test_app_is_same_as_main_app(self):
        from trade_advisor.main import app as main_app

        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            from trade_advisor.api import app
        assert app is main_app

    @pytest.mark.test_id("1.0-UNIT-017")
    @pytest.mark.p3
    def test_import_emits_deprecation_warning(self):
        import importlib

        import trade_advisor.api

        with pytest.warns(DeprecationWarning, match="Use trade_advisor.main"):
            importlib.reload(trade_advisor.api)

    @pytest.mark.test_id("1.0-UNIT-018")
    @pytest.mark.p3
    def test_app_is_fastapi_instance(self):
        from fastapi import FastAPI

        from trade_advisor.main import app

        assert isinstance(app, FastAPI)
