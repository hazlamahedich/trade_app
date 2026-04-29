"""Cross-module import boundary enforcement tests (AC-6)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC = REPO_ROOT / "src" / "trade_advisor"


def _scan_imports(pattern: str, root: Path) -> list[str]:
    import ast

    results: list[str] = []
    regex = re.compile(pattern)
    for py_file in root.rglob("*.py"):
        text = py_file.read_text(errors="replace")
        try:
            tree = ast.parse(text, filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Import, ast.ImportFrom)):
                continue
            line = ast.get_source_segment(text, node)
            if line is None:
                line = text.splitlines()[node.lineno - 1]
            if regex.search(line):
                rel = py_file.relative_to(root)
                results.append(f"{rel}:{node.lineno}: {line.strip()}")
    return results


class TestImportContracts:
    def test_backtest_imports_from_interface_not_base(self):
        engine = SRC / "backtest" / "engine.py"
        content = engine.read_text()
        assert "from trade_advisor.strategies.base" not in content

    def test_container_imports_protocols(self):
        container = SRC / "core" / "container.py"
        content = container.read_text()
        assert "from trade_advisor.data.providers.base import DataProvider" in content

    def test_no_concrete_strategy_imports_outside_module(self):
        matches = _scan_imports(r"from trade_advisor\.strategies\.base", SRC)
        violations = [m for m in matches if "strategies/" not in m.split(":")[0]]
        assert not violations, (
            "Modules outside strategies/ import from strategies.base:\n" + "\n".join(violations)
        )

    def test_no_concrete_strategy_class_imports_outside_container(self):
        matches = _scan_imports(r"from trade_advisor\.strategies\.sma_cross import", SRC)
        violations = [
            m
            for m in matches
            if "strategies/" not in m.split(":")[0]
            and "container.py" not in m
            and "web/routes/strategies.py" not in m
        ]
        assert not violations, (
            "Modules outside strategies/ and container.py import SmaCross:\n"
            + "\n".join(violations)
        )
