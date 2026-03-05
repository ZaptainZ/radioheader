#!/bin/bash

# RadioHeader: Stop hook
# When Claude stops responding, remind about reflux duties.
# Only triggers for projects with the dynamic experience framework configured.

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"

if [ -f "$PROJECT_DIR/.claude/rules/memory-reflux.md" ]; then
  echo ""
  echo "📝 Session reflux checklist:"
  echo "   ① New experience → memory/ and radioheader/topics/"
  echo "   ② Project info changed → projectBasicInfo/01_PROJECT_OVERVIEW.md"
  echo "   ③ Major task completed → projectBasicInfo/logs/"
  echo ""
fi

exit 0
