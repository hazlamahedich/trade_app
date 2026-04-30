# CI Pipeline

## Overview

The CI pipeline runs on GitHub Actions at `.github/workflows/ci.yml`.

**Triggers:** push to any branch, PR to main, weekly schedule (Sunday 3 AM UTC).

## Pipeline Stages

| Stage | Trigger | Timeout | Description |
|-------|---------|---------|-------------|
| **Lint & Typecheck** | All pushes | 5 min | ruff check, ruff format, mypy |
| **Unit Tests** (4 shards) | After lint | 15 min | Parallel sharded pytest (non-integration) |
| **Integration Tests** | PRs only | 20 min | Network-dependent tests (yfinance) |
| **Coverage Report** | After test+integration | 20 min | Coverage with 70% quality gate |
| **Pre-commit** | PRs only | 15 min | Full pre-commit hook suite |
| **Pipeline Report** | Always | 5 min | Summary table in GitHub Step Summary |

## Parallel Sharding

Unit tests split into 4 shards using file-level distribution. Each shard runs independently with `fail-fast: false` so one shard failure doesn't cancel others.

## Caching

- **uv cache** keyed on `pyproject.toml` + `uv.lock` hash
- Shared across all jobs via `actions/cache@v4`

## Quality Gates

- **Coverage threshold**: 70% minimum (configurable in ci.yml)
- **All lint checks must pass** before tests run
- **Pre-commit** must pass on PRs

## Helper Scripts

### `scripts/ci-local.sh`

Mirror the CI pipeline locally:

```bash
./scripts/ci-local.sh
```

Runs lint + mypy + unit tests (same as the fast-gate).

### `scripts/test-changed.sh`

Run tests only for changed files:

```bash
./scripts/test-changed.sh main
./scripts/test-changed.sh HEAD~3 --verbose
```

## Secrets

No secrets required. The pipeline uses only public dependencies via uv.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| Tests fail in CI but pass locally | Run `./scripts/ci-local.sh` to mirror CI |
| Coverage below threshold | Run `pytest --cov=trade_advisor` locally |
| Shard shows 0 tests | Collection issue — check test markers |
| Cache miss | Expected on first run or after lockfile changes |
