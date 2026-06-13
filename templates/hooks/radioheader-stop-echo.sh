#!/bin/bash

# RadioHeader: Stop hook
# When Claude stops responding:
#   1. Remind about Echo duties (for configured projects)
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

# Opt-in gate for RadioMind-backed automation (deny-by-default).
# Part 3 below auto-invokes `radiomind refine-step` on every Stop. That is an
# automatic RadioMind call the user never asked for in the foreground, so it is
# OFF by default. Enable via "radiomind_auto": true in config.json, or
# export RADIOHEADER_RADIOMIND_AUTO=1. When disabled, Part 3 is a silent no-op.
radiomind_auto_enabled() {
  case "${RADIOHEADER_RADIOMIND_AUTO:-}" in
    1|true|yes|on) return 0 ;;
  esac
  [ -f "$CONFIG_FILE" ] && grep -Eq '"radiomind_auto"[[:space:]]*:[[:space:]]*true' "$CONFIG_FILE" 2>/dev/null
}

# Part 1: Echo reminder (for configured projects)
if [ -f "$PROJECT_DIR/.claude/rules/memory-echo.md" ]; then
  echo ""
  echo "📝 Session Echo checklist:"
  echo "   ① New experience → memory/ and radioheader/topics/"
  echo "   ② Project info changed → update project overview doc"
  echo "   ③ Major task completed → write to logs/"
  echo ""
fi

# Part 2: Community vote evaluation (if enabled and pool exists)
if community_enabled && [ -d "$COMMUNITY_POOL" ]; then
  echo "📡 Community vote: If you referenced community/pool/ entries, evaluate causal contribution and append votes to ~/.claude/radioheader/pending-votes.jsonl"
fi

# Part 3: RadioMind refine-step trigger (opt-in only)
# When RadioMind is installed AND auto-automation is opted in, prime a three-body
# debate by outputting the Guardian prompt. Claude will reason about it in the
# next turn, and the user can continue with `radiomind refine-step guardian -r`.
if radiomind_auto_enabled && command -v radiomind &>/dev/null; then
  # Pick the most recently touched domain from the session's memory writes
  RECENT_DOMAIN=""
  if [ -d "$RADIOHEADER_DIR/topics" ]; then
    RECENT_FILE=$(ls -t "$RADIOHEADER_DIR/topics/"*.md 2>/dev/null | head -1)
    if [ -n "$RECENT_FILE" ]; then
      RECENT_DOMAIN=$(basename "$RECENT_FILE" .md | sed 's/^[0-9]*-//')
    fi
  fi

  REFINE_OUTPUT=$(radiomind refine-step prepare ${RECENT_DOMAIN:+--domain "$RECENT_DOMAIN"} 2>/dev/null)
  if [ $? -eq 0 ] && [ -n "$REFINE_OUTPUT" ]; then
    echo ""
    echo "🧠 RadioMind debate prompt (Guardian perspective):"
    echo "$REFINE_OUTPUT"
    echo ""
    echo "To continue: respond to the prompt above, then run:"
    echo "  radiomind refine-step guardian -r \"<your response>\""
  fi
fi

exit 0
