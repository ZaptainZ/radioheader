#!/bin/bash

# RadioHeader: Check if current project has the dynamic experience framework configured.
# If not, inject a high-priority instruction via SessionStart additionalContext to
# force the agent to ask the user BEFORE doing any task.
#
# Design note:普通 stdout 会被当成背景提示被 Agent 忽略。必须用 JSON additionalContext
# + 强指令措辞（MUST FOLLOW / PROHIBITED）驱动行为。
# 询问只问一个问题：项目名（默认目录名）。技术栈/术语映射/文档目录都用默认值，
# 避免在 onboarding 时一次问 4 个问题骚扰用户。

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-.}"
MARKER_FILE="$PROJECT_DIR/.claude/rules/memory-echo.md"

if [ ! -f "$MARKER_FILE" ]; then
  PROJECT_NAME=$(basename "$PROJECT_DIR" 2>/dev/null || echo "current")
  PROJECT_NAME_ESC=$(printf '%s' "$PROJECT_NAME" | sed 's/\\/\\\\/g; s/"/\\"/g')

  cat <<JSON
{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"⚠️ MUST FOLLOW — RadioHeader onboarding check\n\nProject \"${PROJECT_NAME_ESC}\" has NOT configured RadioHeader (no \`.claude/rules/memory-echo.md\` found).\n\nBEFORE responding to the user's first task request, you MUST ask ONE question only:\n\n  '这是新项目，要启用 RadioHeader 动态经验框架吗？项目名默认用「${PROJECT_NAME_ESC}」（来自目录名），如果有正式名请告诉我。'\n\nDO NOT ask about tech stack, terminology mapping, or doc directory — those use defaults and evolve naturally:\n  - tech stack: inferred from code as work progresses\n  - terminology mapping: skipped by default (rarely needed)\n  - doc directory: always \`projectBasicInfo\`\n\nIf the user agrees → use \`${PROJECT_NAME_ESC}\` (or the corrected name they provide) as the project name, then create the project structure from RadioHeader templates AND register in \`~/.claude/radioheader/project-registry.json\`.\nIf the user declines → continue normally without creating extra files.\n\nPROHIBITED: (1) silently starting the user's task without asking; (2) asking the 4-question version. This check exists because missing the onboarding moment means the project never gets integrated into the three-layer memory system.\n\nIf the user has already answered this question in an earlier turn this session, skip the prompt and proceed."}}
JSON
fi

exit 0
