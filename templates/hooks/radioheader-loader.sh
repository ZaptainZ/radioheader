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

exit 0
