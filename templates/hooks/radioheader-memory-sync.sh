#!/bin/bash

# RadioHeader: PostToolUse hook for Write|Edit
# When CC updates memory/ files, inject context to trigger RadioHeader + projectBasicInfo reflux.
# Requires jq.

command -v jq &>/dev/null || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Only trigger when the edited file is in a memory/ directory
if echo "$FILE_PATH" | grep -q "/memory/"; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: "📡 RadioHeader reflux triggered: You just updated a project memory file. Perform these checks (mandatory):\n\n1. **Global reflux**: Is this experience useful across projects? If yes → update ~/.claude/radioheader/topics/ with [source:ProjectName] tag. Create the topic file and update INDEX.md if needed.\n2. **Project docs sync**: Did this work change project architecture, key paths, or tech stack? If yes → update project overview doc (typically projectBasicInfo/01_PROJECT_OVERVIEW.md).\n3. **Task log**: Did you complete a significant task (bug fix, feature, architecture change)? If yes → write to logs directory (typically projectBasicInfo/logs/YYYY-MM-DD-topic-cc.md).\n\nCheck all three items. Briefly state which reflux actions you performed."
    }
  }'
fi

exit 0
