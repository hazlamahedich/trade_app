"""Financial oracle fixtures — hand-computed truth tables for ROUND_HALF_EVEN."""

from __future__ import annotations

ROUND_HALF_EVEN_ORACLE: list[tuple[str, str]] = [
    ("1.23456789015", "1.2345678902"),
    ("1.23456789025", "1.2345678902"),
    ("-1.23456789015", "-1.2345678902"),
    ("0.00000000005", "0.0000000000"),
]

ASSET_CLASS_QUANTIZATION_ORACLE: list[tuple[str, str, str, str]] = [
    ("99.999", "0.01", "EQUITY", "100.00"),
    ("1.23456", "0.0001", "FX", "1.2346"),
    ("0.123456789", "0.00000001", "CRYPTO", "0.12345679"),
    ("0.001", "0.01", "EQUITY", "0.00"),
    ("1.23454", "0.0001", "FX", "1.2345"),
]
