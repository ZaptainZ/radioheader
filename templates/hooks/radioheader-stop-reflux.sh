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

# Check if jq is available (needed for JSON output)
HAS_JQ=false
command -v jq &>/dev/null && HAS_JQ=true

# Build context message
CONTEXT=""

# Part 1: Reflux reminder (for configured projects)
if [ -f "$PROJECT_DIR/.claude/rules/memory-reflux.md" ]; then
  CONTEXT+="📝 Session reflux checklist:\n"
  CONTEXT+="   ① New experience → memory/ and radioheader/topics/\n"
  CONTEXT+="   ② Project info changed → update project overview doc\n"
  CONTEXT+="   ③ Major task completed → write to logs/\n\n"
fi

# Part 2: Community vote evaluation (if enabled and pool exists)
if community_enabled && [ -d "$COMMUNITY_POOL" ]; then
  CONTEXT+="📡 Community shortwave vote evaluation:\n\n"
  CONTEXT+="If you referenced any community shortwave entries (from community/pool/) in this session, evaluate each for causal contribution:\n\n"
  CONTEXT+="Criteria (strict causation, not correlation):\n"
  CONTEXT+="- Did this entry directly help identify the root cause or choose the correct solution?\n"
  CONTEXT+="- Without this experience, would you have taken a wrong path or given incorrect advice?\n\n"
  CONTEXT+="For each community shortwave used, append one JSON line to ~/.claude/radioheader/pending-votes.jsonl:\n"
  CONTEXT+="{\"id\":\"sw-xxx-yyy\",\"vote\":1,\"ts\":\"$(date +%Y-%m-%d)\",\"reason\":\"directly pointed to root cause\"}\n"
  CONTEXT+="or {\"id\":\"sw-xxx-yyy\",\"vote\":-1,\"ts\":\"$(date +%Y-%m-%d)\",\"reason\":\"scenario mismatch\"}\n\n"
  CONTEXT+="Rules:\n"
  CONTEXT+="- Only vote on entries from community/pool/, not local shortwave/\n"
  CONTEXT+="- If you cannot judge causation, skip (do not vote)\n"
  CONTEXT+="- One vote per entry (+1 or -1)\n"
  CONTEXT+="- If no community shortwave was used in this session, skip voting entirely\n"
fi

# Output
if [ -n "$CONTEXT" ] && [ "$HAS_JQ" = true ]; then
  jq -n --arg ctx "$CONTEXT" '{
    hookSpecificOutput: {
      hookEventName: "Stop",
      additionalContext: $ctx
    }
  }'
elif [ -n "$CONTEXT" ]; then
  # Fallback: plain text (no jq)
  echo -e "$CONTEXT"
fi

exit 0
