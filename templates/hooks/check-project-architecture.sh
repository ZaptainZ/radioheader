#!/bin/bash

# RadioHeader: Check if current project has the dynamic experience framework configured.
# If not, prompt the agent to ask the user.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
MARKER_FILE="$PROJECT_DIR/.claude/rules/memory-echo.md"

if [ ! -f "$MARKER_FILE" ]; then
  echo ""
  echo "================================================================"
  echo "  This project has not configured RadioHeader."
  echo ""
  echo "  Before starting work, ask the user:"
  echo "  'Would you like to enable RadioHeader?'"
  echo ""
  echo "  See the RadioHeader global instructions for details."
  echo "================================================================"
  echo ""
fi

exit 0
