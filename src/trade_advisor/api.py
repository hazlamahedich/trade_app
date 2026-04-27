from __future__ import annotations

import warnings

from trade_advisor.main import app  # noqa: F401

warnings.warn("Use trade_advisor.main instead", DeprecationWarning, stacklevel=2)
