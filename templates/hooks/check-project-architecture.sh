#!/bin/bash

# RadioHeader: Check if current project has the dynamic experience framework configured.
# If not, prompt the agent to ask the user.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
MARKER_FILE="$PROJECT_DIR/.claude/rules/memory-reflux.md"

if [ ! -f "$MARKER_FILE" ]; then
  echo ""
  echo "================================================================"
  echo "  This project has not configured RadioHeader (dynamic experience framework)."
  echo ""
  echo "  Before starting work, ask the user:"
  echo "  'Would you like to enable RadioHeader (dynamic experience framework)?'"
  echo ""
  echo "  See the RadioHeader section in ~/.claude/CLAUDE.md for details."
  echo "================================================================"
  echo ""
fi

exit 0
