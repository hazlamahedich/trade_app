from __future__ import annotations

import re
from pathlib import Path


def _find_repo_root() -> Path:
    p = Path(__file__).resolve()
    for parent in p.parents:
        if (parent / "pyproject.toml").exists():
            return parent
    raise FileNotFoundError("Cannot locate repo root (no pyproject.toml found)")


_REPO_ROOT = _find_repo_root()
_TS_EVENTS = _REPO_ROOT / "frontend" / "events.ts"
_PY_EVENTS = _REPO_ROOT / "src" / "trade_advisor" / "web" / "events.py"


def _parse_ts_event_names() -> set[str]:
    source = _TS_EVENTS.read_text()
    names = set()
    for line in source.splitlines():
        m = re.match(r'\s+"(ta:[^"]+)"\s*:', line)
        if m:
            names.add(m.group(1))
    return names


def _parse_ts_payload_keys() -> dict[str, set[str]]:
    source = _TS_EVENTS.read_text()
    result: dict[str, set[str]] = {}
    current_event: str | None = None
    brace_depth = 0
    in_event = False
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if not in_event:
            m = re.match(r'\s+"(ta:[^"]+)"\s*:\s*\{', line)
            if m:
                current_event = m.group(1)
                result[current_event] = set()
                brace_depth = line.count("{") - line.count("}")
                if brace_depth <= 0:
                    for km in re.findall(r"(\w+)\s*:", stripped.split("{", 1)[1]):
                        result[current_event].add(km)
                    current_event = None
                else:
                    in_event = True
                    km = re.match(r"\s+(\w+)\s*:", line)
                    if km:
                        result[current_event].add(km.group(1))
            continue
        brace_depth += line.count("{") - line.count("}")
        km = re.match(r"\s+(\w+)\s*:", line)
        if km:
            result[current_event].add(km.group(1))
        if brace_depth <= 0:
            in_event = False
            current_event = None
    return result


def _parse_py_event_names() -> set[str]:
    source = _PY_EVENTS.read_text()
    names = set()
    for line in source.splitlines():
        m = re.match(r'\s+"(ta:[^"]+)"\s*:', line)
        if m:
            names.add(m.group(1))
    return names


class TestEventContract:
    def test_event_names_match_bidirectionally(self):
        ts_names = _parse_ts_event_names()
        py_names = _parse_py_event_names()
        assert ts_names, "No TS event names parsed — check events.ts format"
        assert py_names, "No Python event names parsed — check events.py format"
        only_ts = ts_names - py_names
        only_py = py_names - ts_names
        assert not only_ts, f"Events only in TypeScript: {only_ts}"
        assert not only_py, f"Events only in Python: {only_py}"

    def test_payload_keys_non_empty(self):
        ts_payloads = _parse_ts_payload_keys()
        assert ts_payloads, "No TS payload keys parsed — check events.ts format"
        for event_name, ts_keys in ts_payloads.items():
            assert ts_keys, f"Event {event_name} has no parsed payload keys in TS"
