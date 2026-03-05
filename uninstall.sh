#!/bin/bash
set -e

# RadioHeader — Uninstaller
# Removes RadioHeader components, optionally preserves topic files.

CLAUDE_DIR="$HOME/.claude"
RADIOHEADER_DIR="$CLAUDE_DIR/radioheader"
HOOKS_DIR="$CLAUDE_DIR/hooks"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
SETTINGS_JSON="$CLAUDE_DIR/settings.json"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[RadioHeader]${NC} $1"; }
ok()    { echo -e "${GREEN}[RadioHeader]${NC} $1"; }
warn()  { echo -e "${YELLOW}[RadioHeader]${NC} $1"; }

if [ ! -d "$RADIOHEADER_DIR" ] && ! grep -q "RadioHeader START" "$CLAUDE_MD" 2>/dev/null; then
  info "RadioHeader does not appear to be installed. Nothing to do."
  exit 0
fi

echo -e "${YELLOW}This will remove RadioHeader from your Claude Code setup.${NC}"
echo ""

# --- Step 1: Remove RadioHeader section from CLAUDE.md ---

if [ -f "$CLAUDE_MD" ] && grep -q "RadioHeader START" "$CLAUDE_MD" 2>/dev/null; then
  cp "$CLAUDE_MD" "$CLAUDE_MD.bak.$TIMESTAMP"
  sed '/^# --- RadioHeader START ---$/,/^# --- RadioHeader END ---$/d' "$CLAUDE_MD.bak.$TIMESTAMP" > "$CLAUDE_MD"
  ok "Removed RadioHeader rules from CLAUDE.md (backup: .bak.$TIMESTAMP)"
fi

# --- Step 2: Remove hook scripts ---

if [ -f "$HOOKS_DIR/check-project-architecture.sh" ]; then
  rm "$HOOKS_DIR/check-project-architecture.sh"
  ok "Removed check-project-architecture.sh"
fi

if [ -f "$HOOKS_DIR/radioheader-loader.sh" ]; then
  rm "$HOOKS_DIR/radioheader-loader.sh"
  ok "Removed radioheader-loader.sh"
fi

if [ -f "$HOOKS_DIR/radioheader-memory-sync.sh" ]; then
  rm "$HOOKS_DIR/radioheader-memory-sync.sh"
  ok "Removed radioheader-memory-sync.sh"
fi

if [ -f "$HOOKS_DIR/radioheader-stop-reflux.sh" ]; then
  rm "$HOOKS_DIR/radioheader-stop-reflux.sh"
  ok "Removed radioheader-stop-reflux.sh"
fi

# --- Step 3: Clean hooks from settings.json ---

if [ -f "$SETTINGS_JSON" ] && command -v jq &>/dev/null; then
  cp "$SETTINGS_JSON" "$SETTINGS_JSON.bak.$TIMESTAMP"
  TEMP_JSON=$(mktemp)

  jq '
    # Clean SessionStart hooks
    (if .hooks.SessionStart then
      .hooks.SessionStart |= map(
        select(
          .hooks | all(.command | (
            contains("check-project-architecture.sh") or
            contains("radioheader-loader.sh")
          ) | not)
        )
      )
    else . end) |
    # Clean PostToolUse hooks
    (if .hooks.PostToolUse then
      .hooks.PostToolUse |= map(
        select(
          .hooks | all(.command | contains("radioheader-memory-sync.sh") | not)
        )
      )
    else . end) |
    # Clean Stop hooks
    (if .hooks.Stop then
      .hooks.Stop |= map(
        select(
          .hooks | all(.command | contains("radioheader-stop-reflux.sh") | not)
        )
      )
    else . end)
  ' "$SETTINGS_JSON" > "$TEMP_JSON"

  mv "$TEMP_JSON" "$SETTINGS_JSON"
  ok "Removed hooks from settings.json (backup: .bak.$TIMESTAMP)"
else
  warn "Please manually remove RadioHeader hooks from ~/.claude/settings.json"
fi

# --- Step 4: Handle radioheader directory ---

if [ -d "$RADIOHEADER_DIR" ]; then
  TOPIC_COUNT=$(ls "$RADIOHEADER_DIR/topics/"*.md 2>/dev/null | wc -l | tr -d ' ')

  if [ "$TOPIC_COUNT" -gt 0 ]; then
    echo ""
    warn "You have $TOPIC_COUNT topic files in $RADIOHEADER_DIR/topics/"
    read -p "Delete the radioheader directory and all topics? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
      rm -rf "$RADIOHEADER_DIR"
      ok "Deleted $RADIOHEADER_DIR"
    else
      info "Kept $RADIOHEADER_DIR (you can delete it manually later)"
    fi
  else
    rm -rf "$RADIOHEADER_DIR"
    ok "Deleted $RADIOHEADER_DIR (no topics to preserve)"
  fi
fi

echo ""
ok "RadioHeader uninstalled."
echo ""
echo "Note: Per-project .claude/rules/ files are NOT removed."
echo "Remove them manually if desired."
echo ""
