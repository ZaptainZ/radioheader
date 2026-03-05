#!/bin/bash

# RadioHeader: PostToolUse hook for Write|Edit
# When CC updates memory/ files, inject context to trigger RadioHeader + projectBasicInfo reflux.
# Requires jq.

command -v jq &>/dev/null || exit 0

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty' 2>/dev/null)

# Trigger 1: memory/ writes → full reflux check
if echo "$FILE_PATH" | grep -q "/memory/"; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: "📡 RadioHeader reflux triggered: You just updated a project memory file. Perform these checks (mandatory):\n\n1. **Global reflux**: Is this experience useful across projects? If yes → update ~/.claude/radioheader/topics/ with [source:ProjectName] tag. Create the topic file and update INDEX.md if needed.\n2. **Project docs sync**: Did this work change project architecture, key paths, or tech stack? If yes → update project overview doc (typically projectBasicInfo/01_PROJECT_OVERVIEW.md).\n3. **Task log**: Did you complete a significant task (bug fix, feature, architecture change)? If yes → write to logs directory (typically projectBasicInfo/logs/YYYY-MM-DD-topic-cc.md).\n\nCheck all three items. Briefly state which reflux actions you performed."
    }
  }'

# Trigger 2: topics/ writes → shortwave refinement
elif echo "$FILE_PATH" | grep -q "radioheader/topics/"; then
  FILENAME=$(basename "$FILE_PATH")
  jq -n --arg fn "$FILENAME" '{
    hookSpecificOutput: {
      hookEventName: "PostToolUse",
      additionalContext: ("📡 短波精炼触发：你刚更新了 RadioHeader topics 文件 " + $fn + "。\n\n请为本次新增/修改的条目生成对应的知识短波条目：\n\n1. 检查 ~/.claude/radioheader/shortwave/ 中是否已有对应条目（按 domain 和内容判断）\n2. 如果没有，创建新文件 sw-{domain缩写}-{序号}.md\n3. 如果已有，更新现有条目\n\n精炼规则：\n- 剥离项目名和文件路径，抽象为通用技术规律\n- domain 用逗号分隔（如 iOS, SwiftUI, Concurrency）\n- tags 包含中英文症状词、技术名词、同义表述，与正文冗余\n- 保留症状关键词和量化数据\n- 判断是否需要 case：正文已足够具体可操作则不加，偏抽象或症状不直观时加假名化案例\n- 假名化：项目名→用途描述，专有类名→删除或替换，量化数据原样保留\n\n格式参考 ~/.claude/radioheader/shortwave/ 中已有条目，或参考 radioheader/docs/shortwave-spec.md 中的规范。")
    }
  }'
fi

exit 0
