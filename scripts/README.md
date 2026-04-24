# BMAD-Serena-Graphify Integration

Automated integration layer connecting three powerful systems:

- **BMAD Method** — Full product development lifecycle (65+ skills)
- **Serena** — Code intelligence with persistent memories
- **Graphify** — Knowledge graph with community detection

## Quick Start

```bash
# Bootstrap the integration (run once)
./scripts/sync-all.sh

# Or with a Graphify incremental update
./scripts/sync-all.sh --graphify-update
```

## Architecture

```
Serena Memories (.serena/memories/)     ← Single source of truth
    │
    ├── bmad/*          ← BMAD artifact summaries
    ├── graphify/*      ← Knowledge graph insights
    └── integration/*   ← Sync state and logs
         │
         ├── scripts/sync-all.sh          ← Master sync orchestrator
         ├── scripts/graphify-to-serena.py ← Graph → Serena bridge
         ├── scripts/bmad-to-serena.py     ← BMAD → Serena bridge
         └── scripts/serena-context-for-bmad.py ← Serena → BMAD context
```

## Files

| File | Purpose |
|------|---------|
| `scripts/sync-all.sh` | Master sync — runs all bridges in sequence |
| `scripts/graphify-to-serena.py` | Extracts graph communities, god nodes, dependencies → Serena memories |
| `scripts/bmad-to-serena.py` | Extracts PRD, architecture, sprint state → Serena memories |
| `scripts/serena-context-for-bmad.py` | Generates unified context files from Serena memories |
| `_bmad-output/unified-context.md` | Full context for BMAD skills |
| `_bmad-output/compact-context.md` | Compact context for injection |
| `.serena/memories/*.md` | Individual memory files (the shared brain) |

## Memory Schema

| Memory | Source | Content |
|--------|--------|---------|
| `bmad/current-phase` | BMAD help CSV | Current workflow phase |
| `bmad/sprint-summary` | sprint-status.yaml | Sprint state digest |
| `bmad/decisions` | PRD + Architecture | Key design decisions |
| `bmad/agent-insights` | Agent MEMORY.md | Fei-Fei + Fisher insights |
| `bmad/epics` | epics.md | Epic titles and structure |
| `graphify/communities` | graph.json | Community structure |
| `graphify/god-nodes` | graph.json | High-connectivity nodes |
| `graphify/dependencies` | graph.json | Cross-community edges |
| `graphify/surprising` | GRAPH_REPORT.md | Unexpected connections |
| `graphify/hyperedges` | graph.json | Group relationships |
| `integration/sync-log` | Bridge scripts | Last sync timestamp + stats |

## Usage

### Via BMAD Unified Skill

```
bmad unified status          — Show unified dashboard
bmad unified sync            — Full sync
bmad unified context         — Show enriched context
bmad unified communities     — Show graph communities
bmad unified deps            — Show cross-community dependencies
bmad unified gaps            — Show knowledge gaps
```

### Via Scripts

```bash
# Full sync
./scripts/sync-all.sh

# Sync + update graph
./scripts/sync-all.sh --graphify-update

# Individual bridges
python3 scripts/graphify-to-serena.py --graph-dir graphify-out
python3 scripts/bmad-to-serena.py
python3 scripts/serena-context-for-bmad.py
```

## Automation

Hooks in `~/.claude/hooks.json` automatically:

1. **Before BMAD skills** — Check and inject unified context
2. **After file changes** — Coordinate Serena re-index + Graphify update + memory sync

## Design Principles

- **Non-invasive** — No BMAD skill files are modified
- **Serena memories as SSoT** — All shared state flows through memories
- **Event-driven** — Hooks trigger syncs automatically
- **Debounced** — Expensive operations are throttled (30s debounce)
- **Graceful degradation** — Systems work independently if one is unavailable
