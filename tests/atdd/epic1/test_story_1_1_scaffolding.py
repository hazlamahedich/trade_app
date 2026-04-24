"""ATDD red-phase: Story 1.1 — Project Scaffolding & Quality Infrastructure.

Tests assert the expected end-state AFTER full Epic 1 implementation
as defined in the architecture spec. All tests are SKIPPED (TDD red phase).

Remove @pytest.mark.skip when implementing Story 1.1.
"""
from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[4]


class TestStory11ProjectScaffolding:
    """Story 1.1: Project initialized with all tooling configured."""

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_pyproject_toml_exists_and_valid(self):
        pyproject = PROJECT_ROOT / "pyproject.toml"
        assert pyproject.exists()
        content = pyproject.read_text()
        assert 'requires-python' in content
        assert '3.11' in content
        assert 'ruff' in content
        assert 'mypy' in content
        assert 'pytest' in content

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_pinned_deps_no_upper_unbounded(self):
        import tomllib

        pyproject = PROJECT_ROOT / "pyproject.toml"
        with open(pyproject, "rb") as f:
            data = tomllib.load(f)
        deps = data.get("project", {}).get("dependencies", [])
        for dep in deps:
            if ">=" in dep and "," not in dep:
                pytest.fail(f"Unbounded upper version: {dep}")
            if dep.startswith(">=") and "<" not in dep:
                pytest.fail(f"Unbounded upper version: {dep}")

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_python_version_file(self):
        pv = PROJECT_ROOT / ".python-version"
        assert pv.exists()
        assert "3.11" in pv.read_text().strip()

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_pre_commit_config_exists(self):
        pc = PROJECT_ROOT / ".pre-commit-config.yaml"
        assert pc.exists()
        content = pc.read_text()
        assert "ruff" in content
        assert "mypy" in content

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_github_ci_workflow_exists(self):
        ci = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"
        assert ci.exists()
        content = ci.read_text()
        assert "ruff" in content
        assert "mypy" in content
        assert "pytest" in content

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_justfile_exists_with_required_commands(self):
        jf = PROJECT_ROOT / "justfile"
        assert jf.exists()
        content = jf.read_text()
        for cmd in ("dev", "test", "lint", "migrate"):
            assert cmd in content, f"justfile missing '{cmd}' command"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_lint_passes_zero_violations(self):
        import subprocess

        result = subprocess.run(
            ["ruff", "check", "src/", "tests/"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"ruff violations:\n{result.stdout}"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_mypy_strict_passes(self):
        import subprocess

        result = subprocess.run(
            ["mypy", "--strict", "src/"],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"mypy errors:\n{result.stdout}"

    @pytest.mark.skip(reason="ATDD red phase — Story 1.1 not implemented")
    def test_uv_lock_exists(self):
        assert (PROJECT_ROOT / "uv.lock").exists()
