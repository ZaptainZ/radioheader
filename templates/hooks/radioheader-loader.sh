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

exit 0
