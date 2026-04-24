#!/usr/bin/env python3
"""Bridge: BMAD artifacts → Serena memories.

Reads BMAD planning/implementation artifacts and writes structured
summaries to Serena memories.

Usage:
    python scripts/bmad-to-serena.py [--bmad-output BMAD_OUTPUT_DIR]
"""
import json
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime


BMAD_OUTPUT = Path("_bmad-output")
PLANNING = BMAD_OUTPUT / "planning-artifacts"


def read_file_safe(path: Path) -> str:
    if path.exists():
        return path.read_text()
    return ""


def extract_phase_from_csv() -> str:
    csv_path = Path("_bmad/_config/bmad-help.csv")
    if not csv_path.exists():
        return "unknown"
    content = csv_path.read_text()
    lines = content.strip().splitlines()
    if len(lines) < 2:
        return "unknown"
    header = lines[0].split(",")
    phase_idx = None
    for i, h in enumerate(header):
        if "phase" in h.strip().lower():
            phase_idx = i
            break
    if phase_idx is None:
        return "unknown"
    phases = set()
    for line in lines[1:]:
        parts = line.split(",")
        if len(parts) > phase_idx:
            phases.add(parts[phase_idx].strip())
    required_phases = [p for p in phases if "implementation" in p or "solutioning" in p or "planning" in p]
    if required_phases:
        return f"phases detected: {', '.join(sorted(required_phases))}"
    return f"phases detected: {', '.join(sorted(phases))}"


def extract_prd_summary() -> str:
    prd_file = PLANNING / "Quant_Trade_Advisor_PRD.md"
    content = read_file_safe(prd_file)
    if not content:
        return "PRD not found"
    lines = content.splitlines()
    summary_lines = []
    in_summary = False
    for line in lines[:100]:
        if any(kw in line.lower() for kw in ["## overview", "## summary", "## problem", "# quant trade"]):
            in_summary = True
        if in_summary:
            summary_lines.append(line)
            if len(summary_lines) > 30:
                break
    return "\n".join(summary_lines) if summary_lines else content[:2000]


def extract_architecture_summary() -> str:
    arch_file = PLANNING / "architecture.md"
    content = read_file_safe(arch_file)
    if not content:
        return "Architecture not found"
    lines = content.splitlines()
    decisions = []
    for line in lines:
        if line.startswith("## ") or line.startswith("### "):
            decisions.append(line)
        if len(decisions) > 30:
            break
    return "\n".join(decisions) if decisions else content[:2000]


def extract_epics_summary() -> str:
    epics_file = PLANNING / "epics.md"
    content = read_file_safe(epics_file)
    if not content:
        return "Epics not found"
    epics = re.findall(r'^##+\s+(.+)$', content, re.MULTILINE)
    if epics:
        return "# Epics\n\n" + "\n".join(f"- {e}" for e in epics[:20])
    return content[:2000]


def extract_sprint_state() -> str:
    for name in ["sprint-status.yaml", "sprint-status.yml"]:
        for d in [BMAD_OUTPUT, BMAD_OUTPUT / "implementation-artifacts", Path(".")]:
            f = d / name
            if f.exists():
                return f.read_text()
    return "No sprint-status file found. Sprint planning has not been run yet."


def extract_agent_insights() -> str:
    insights = []
    for agent_dir in Path("_bmad/memory").glob("agent-*"):
        memory_file = agent_dir / "MEMORY.md"
        if memory_file.exists():
            agent_name = agent_dir.name.replace("agent-", "").replace("-", " ").title()
            content = memory_file.read_text()[:1000]
            insights.append(f"## {agent_name}\n\n{content}")
    if insights:
        return "\n\n---\n\n".join(insights)
    return "No agent memories found."


def extract_project_context() -> str:
    ctx_file = BMAD_OUTPUT / "project-context.md"
    content = read_file_safe(ctx_file)
    if not content:
        return "Project context not found"
    return content[:3000]


def format_phase(current_phase: str) -> str:
    return f"# BMAD Current Phase\n\n{current_phase}\n\nLast updated: {datetime.now().isoformat()}"


def format_sprint_summary(sprint_content: str) -> str:
    return f"# BMAD Sprint Summary\n\n```\n{sprint_content}\n```\n\nLast updated: {datetime.now().isoformat()}"


def format_decisions(prd: str, arch: str) -> str:
    return f"# BMAD Key Decisions\n\n## PRD Summary\n{prd}\n\n## Architecture Decisions\n{arch}\n\nLast updated: {datetime.now().isoformat()}"


def format_agent_insights(insights: str) -> str:
    return f"# BMAD Agent Insights\n\n{insights}\n\nLast updated: {datetime.now().isoformat()}"


def write_serena_memory(memory_name: str, content: str):
    memory_dir = Path(".serena/memories")
    memory_dir.mkdir(parents=True, exist_ok=True)
    safe_name = memory_name.replace("/", "_")
    mem_file = memory_dir / f"{safe_name}.md"
    mem_file.write_text(content)
    print(f"  Written: {mem_file}")


def main():
    parser = argparse.ArgumentParser(description="BMAD → Serena memory bridge")
    parser.add_argument("--bmad-output", type=str, default="_bmad-output", help="BMAD output directory")
    args = parser.parse_args()

    print("BMAD → Serena Bridge")
    print()

    phase = extract_phase_from_csv()
    prd_summary = extract_prd_summary()
    arch_summary = extract_architecture_summary()
    epics_summary = extract_epics_summary()
    sprint_state = extract_sprint_state()
    agent_insights = extract_agent_insights()

    write_serena_memory("bmad_current-phase", format_phase(phase))
    write_serena_memory("bmad_sprint-summary", format_sprint_summary(sprint_state))
    write_serena_memory("bmad_decisions", format_decisions(prd_summary, arch_summary))
    write_serena_memory("bmad_agent-insights", format_agent_insights(agent_insights))
    write_serena_memory("bmad_epics", epics_summary)

    stats = {
        "last_sync": datetime.now().isoformat(),
        "prd_exists": (PLANNING / "Quant_Trade_Advisor_PRD.md").exists(),
        "architecture_exists": (PLANNING / "architecture.md").exists(),
        "epics_exists": (PLANNING / "epics.md").exists(),
        "sprint_status_exists": "sprint" in sprint_state[:50].lower() if sprint_state else False,
    }
    write_serena_memory("integration_sync-log", f"# Sync Log\n\n```json\n{json.dumps(stats, indent=2)}\n```\n\nAppended from bmad-to-serena at {datetime.now().isoformat()}")

    print("\nDone. All BMAD insights written to Serena memories.")


if __name__ == "__main__":
    main()
