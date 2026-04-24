#!/usr/bin/env bash
# sync-all.sh — Master synchronization script for BMAD + Serena + Graphify integration
# Runs all three bridges in sequence to keep systems in sync.
#
# Usage:
#   ./scripts/sync-all.sh [--graphify-update] [--skip-graphify] [--skip-serena]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

TIMESTAMP=$(date -u +%Y-%m-%dT%H:%M:%SZ)
LOG_FILE=".serena/sync-log.txt"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() { echo -e "${GREEN}[$TIMESTAMP]${NC} $1"; }
warn() { echo -e "${YELLOW}[$TIMESTAMP] WARN:${NC} $1"; }
err() { echo -e "${RED}[$TIMESTAMP] ERROR:${NC} $1"; }

DO_GRAPHIFY_UPDATE=false
SKIP_GRAPHIFY=false
SKIP_SERENA=false

for arg in "$@"; do
    case "$arg" in
        --graphify-update) DO_GRAPHIFY_UPDATE=true ;;
        --skip-graphify) SKIP_GRAPHIFY=true ;;
        --skip-serena) SKIP_SERENA=true ;;
    esac
done

mkdir -p .serena/memories

log "Starting unified sync..."

# ── Step 1: Graphify update (optional) ──
if [ "$DO_GRAPHIFY_UPDATE" = true ] && [ "$SKIP_GRAPHIFY" = false ]; then
    log "Step 1: Running Graphify incremental update..."
    if command -v graphify &> /dev/null; then
        graphify --update . --no-viz 2>&1 || warn "Graphify update failed"
        log "Graphify update complete"
    else
        warn "Graphify not found. Skipping graph update."
    fi
else
    log "Step 1: Skipping Graphify update (use --graphify-update to enable)"
fi

# ── Step 2: Graphify → Serena ──
if [ "$SKIP_GRAPHIFY" = false ]; then
    log "Step 2: Syncing Graphify → Serena memories..."
    if [ -f "graphify-out/graph.json" ]; then
        python3 "$SCRIPT_DIR/graphify-to-serena.py" --graph-dir graphify-out 2>&1 || warn "Graphify→Serena bridge failed"
    else
        warn "graphify-out/graph.json not found. Run graphify first."
    fi
else
    log "Step 2: Skipping Graphify bridge"
fi

# ── Step 3: BMAD → Serena ──
log "Step 3: Syncing BMAD → Serena memories..."
if [ -d "_bmad-output" ]; then
    python3 "$SCRIPT_DIR/bmad-to-serena.py" 2>&1 || warn "BMAD→Serena bridge failed"
else
    warn "_bmad-output/ not found. Skipping BMAD bridge."
fi

# ── Step 4: Serena → BMAD context ──
log "Step 4: Generating BMAD context from Serena memories..."
python3 "$SCRIPT_DIR/serena-context-for-bmad.py" 2>&1 || warn "Serena→BMAD context bridge failed"

# ── Step 5: Serena re-index (optional) ──
if [ "$SKIP_SERENA" = false ]; then
    log "Step 5: Serena re-index check..."
    if [ -f ".serena/project.yml" ]; then
        LAST_INDEX=0
        [ -f ".serena/.last_index" ] && LAST_INDEX=$(cat .serena/.last_index 2>/dev/null || echo "0")
        CURRENT_TIME=$(date +%s)
        TIME_SINCE=$(( (CURRENT_TIME - LAST_INDEX) / 3600 ))
        if [ "$TIME_SINCE" -gt 1 ]; then
            log "Triggering Serena re-index (${TIME_SINCE}h since last)..."
            date +%s > .serena/.last_index
            log "Serena index timestamp updated"
        else
            log "Serena index fresh (${TIME_SINCE}h old)"
        fi
    else
        warn ".serena/project.yml not found. Serena not activated for this project."
    fi
else
    log "Step 5: Skipping Serena re-index"
fi

# ── Summary ──
echo ""
log "=== Sync Complete ==="
echo "  Timestamp: $TIMESTAMP"
echo "  Memories dir: .serena/memories/"
echo "  Context files: _bmad-output/unified-context.md, _bmad-output/compact-context.md"
echo "  Log: $LOG_FILE"

echo "[$TIMESTAMP] sync-all completed" >> "$LOG_FILE"
