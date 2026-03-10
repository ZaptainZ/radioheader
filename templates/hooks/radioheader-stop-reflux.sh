#!/bin/bash

# RadioHeader: Stop hook
# When Claude stops responding:
#   1. Remind about reflux duties (for configured projects)
#   2. Trigger community vote evaluation (if community enabled)

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
RADIOHEADER_DIR="$HOME/.claude/radioheader"
CONFIG_FILE="$RADIOHEADER_DIR/config.json"
PENDING_VOTES="$RADIOHEADER_DIR/pending-votes.jsonl"
COMMUNITY_POOL="$RADIOHEADER_DIR/community/pool"

# Check if community is enabled
community_enabled() {
  [ -f "$CONFIG_FILE" ] && grep -q '"community".*true' "$CONFIG_FILE" 2>/dev/null
}

# Part 1: Reflux reminder (for configured projects)
if [ -f "$PROJECT_DIR/.claude/rules/memory-reflux.md" ]; then
  echo ""
  echo "📝 Session reflux checklist:"
  echo "   ① New experience → memory/ and radioheader/topics/"
  echo "   ② Project info changed → update project overview doc"
  echo "   ③ Major task completed → write to logs/"
  echo ""
fi

# Part 2: Community vote evaluation (if enabled and pool exists)
if community_enabled && [ -d "$COMMUNITY_POOL" ]; then
  echo "📡 Community vote: If you referenced community/pool/ entries, evaluate causal contribution and append votes to ~/.claude/radioheader/pending-votes.jsonl"
fi

exit 0
