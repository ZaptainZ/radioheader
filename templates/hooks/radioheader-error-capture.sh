#!/bin/bash

# RadioHeader: PostToolUse hook for Bash
# Silently captures recurring error patterns to error-log.jsonl.
# When consolidate runs, it analyzes these patterns and surfaces
# recurring issues in context-digest.md for the Agent to record
# as project-level memory.

command -v jq &>/dev/null || exit 0

INPUT=$(cat)
TOOL_RESULT=$(echo "$INPUT" | jq -r '.tool_result // empty' 2>/dev/null)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)

# Only process if there's an error signal in the result
# Check for known error patterns that indicate structural/navigational issues
ERROR_PATTERN=""

if echo "$TOOL_RESULT" | grep -q "fatal: not a git repository"; then
  ERROR_PATTERN="not-a-git-repo"
elif echo "$TOOL_RESULT" | grep -q "No such file or directory"; then
  ERROR_PATTERN="file-not-found"
elif echo "$TOOL_RESULT" | grep -q "command not found"; then
  ERROR_PATTERN="command-not-found"
elif echo "$TOOL_RESULT" | grep -q "Permission denied"; then
  ERROR_PATTERN="permission-denied"
elif echo "$TOOL_RESULT" | grep -q "Connection refused\|Could not resolve"; then
  ERROR_PATTERN="network-error"
fi

# If no known pattern matched, exit silently
if [ -z "$ERROR_PATTERN" ]; then
  exit 0
fi

# Extract a short error snippet (first line of error, truncated)
ERROR_SNIPPET=$(echo "$TOOL_RESULT" | grep -i "fatal\|error\|not found\|denied\|refused" | head -1 | cut -c1-120)

# Log to error-log.jsonl (project-scoped via cwd)
ERROR_LOG="$HOME/.claude/radioheader/error-log.jsonl"

python3 -c "
import json, datetime
entry = {
    'ts': datetime.datetime.now().isoformat(),
    'pattern': '$ERROR_PATTERN',
    'snippet': '''$ERROR_SNIPPET''',
    'cwd': '$CWD'
}
with open('$ERROR_LOG', 'a') as f:
    f.write(json.dumps(entry, ensure_ascii=False) + '\n')
" 2>/dev/null

exit 0
