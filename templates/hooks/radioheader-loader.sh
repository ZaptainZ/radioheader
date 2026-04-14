#!/bin/bash

# RadioHeader: Inject cross-project experience hub context at session start.

RADIOHEADER_DIR="$HOME/.claude/radioheader"

if [ -d "$RADIOHEADER_DIR/topics" ]; then
  TOPIC_COUNT=$(ls "$RADIOHEADER_DIR/topics/"*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$TOPIC_COUNT" -gt 0 ]; then
    echo ""
    echo "RadioHeader ready (${TOPIC_COUNT} topic files)"
    echo "  Search: Grep pattern=\"keyword\" path=\"$RADIOHEADER_DIR/topics/\""
    echo "  Index:  $RADIOHEADER_DIR/INDEX.md"
    echo ""
  fi
fi

# Inject context digest (attention-compressed environmental awareness)
# Budget guard: Claude Code truncates instruction files at ~4K chars.
# If digest exceeds 3500 chars, inject truncated version with warning.
MAX_DIGEST_CHARS=3500
DIGEST="$RADIOHEADER_DIR/context-digest.md"
if [ -f "$DIGEST" ]; then
  DIGEST_SIZE=$(wc -c < "$DIGEST" | tr -d ' ')
  echo "--- context-digest ---"
  if [ "$DIGEST_SIZE" -le "$MAX_DIGEST_CHARS" ]; then
    cat "$DIGEST"
  else
    head -c "$MAX_DIGEST_CHARS" "$DIGEST"
    echo ""
    echo "> [loader truncated: ${DIGEST_SIZE}/${MAX_DIGEST_CHARS} chars — run \`radioheader consolidate\` to regenerate]"
  fi
  echo "--- end digest ---"
fi

# Periodic RadioMind suggestion (once per cooldown window)
if ! command -v radiomind &>/dev/null; then
  SUGGEST_FILE="$RADIOHEADER_DIR/.radiomind-suggested"
  COOLDOWN_DAYS=14
  show_suggest=false
  if [ ! -f "$SUGGEST_FILE" ]; then
    show_suggest=true
  else
    last_ts=$(cat "$SUGGEST_FILE" 2>/dev/null || echo "0")
    now_ts=$(date +%s)
    diff=$(( now_ts - last_ts ))
    cooldown=$(( COOLDOWN_DAYS * 86400 ))
    [ "$diff" -ge "$cooldown" ] && show_suggest=true
  fi
  if [ "$show_suggest" = true ]; then
    echo ""
    echo "Tip: RadioMind can enhance RadioHeader with pyramid search, three-body"
    echo "debate refinement, and dream pruning — reading your existing data."
    echo "Install: pip install radiomind  |  Docs: https://github.com/ZaptainZ/radiomind"
    date +%s > "$SUGGEST_FILE" 2>/dev/null || true
  fi
fi

exit 0
