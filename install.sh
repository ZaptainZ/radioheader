#!/bin/bash
set -e

# RadioHeader — Cross-project memory framework for Claude Code
# https://github.com/anthropics/radioheader

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
RADIOHEADER_DIR="$CLAUDE_DIR/radioheader"
HOOKS_DIR="$CLAUDE_DIR/hooks"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
SETTINGS_JSON="$CLAUDE_DIR/settings.json"
TIMESTAMP=$(date +%Y%m%d%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info()  { echo -e "${BLUE}[RadioHeader]${NC} $1"; }
ok()    { echo -e "${GREEN}[RadioHeader]${NC} $1"; }
warn()  { echo -e "${YELLOW}[RadioHeader]${NC} $1"; }
err()   { echo -e "${RED}[RadioHeader]${NC} $1"; }

# --- Pre-checks ---

if [ ! -d "$CLAUDE_DIR" ]; then
  err "~/.claude/ directory not found. Is Claude Code installed?"
  err "Install Claude Code first: https://docs.anthropic.com/en/docs/claude-code"
  exit 1
fi

if [ -d "$RADIOHEADER_DIR" ]; then
  warn "RadioHeader is already installed at $RADIOHEADER_DIR"
  read -p "Reinstall? This will NOT delete your existing topics. [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    info "Aborted."
    exit 0
  fi
fi

info "Installing RadioHeader..."

# --- Step 1: Create radioheader directory ---

mkdir -p "$RADIOHEADER_DIR/topics"

if [ ! -f "$RADIOHEADER_DIR/INDEX.md" ]; then
  sed "s|__HOME__|$HOME|g" "$SCRIPT_DIR/templates/radioheader/INDEX.md" > "$RADIOHEADER_DIR/INDEX.md"
  ok "Created INDEX.md"
fi

if [ ! -f "$RADIOHEADER_DIR/project-registry.md" ]; then
  cp "$SCRIPT_DIR/templates/radioheader/project-registry.md" "$RADIOHEADER_DIR/project-registry.md"
  ok "Created project-registry.md"
fi

# --- Step 2: Install hook scripts ---

mkdir -p "$HOOKS_DIR"

cp "$SCRIPT_DIR/templates/hooks/check-project-architecture.sh" "$HOOKS_DIR/check-project-architecture.sh"
chmod +x "$HOOKS_DIR/check-project-architecture.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-loader.sh" "$HOOKS_DIR/radioheader-loader.sh"
chmod +x "$HOOKS_DIR/radioheader-loader.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-memory-sync.sh" "$HOOKS_DIR/radioheader-memory-sync.sh"
chmod +x "$HOOKS_DIR/radioheader-memory-sync.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-stop-reflux.sh" "$HOOKS_DIR/radioheader-stop-reflux.sh"
chmod +x "$HOOKS_DIR/radioheader-stop-reflux.sh"

ok "Installed hook scripts (4 hooks)"

# --- Step 3: Append rules to CLAUDE.md ---

if [ -f "$CLAUDE_MD" ]; then
  if grep -q "RadioHeader START" "$CLAUDE_MD" 2>/dev/null; then
    # Remove existing RadioHeader section and re-add
    warn "Updating existing RadioHeader section in CLAUDE.md"
    cp "$CLAUDE_MD" "$CLAUDE_MD.bak.$TIMESTAMP"
    # Use sed to remove the section between markers
    sed '/^# --- RadioHeader START ---$/,/^# --- RadioHeader END ---$/d' "$CLAUDE_MD.bak.$TIMESTAMP" > "$CLAUDE_MD"
  else
    cp "$CLAUDE_MD" "$CLAUDE_MD.bak.$TIMESTAMP"
    ok "Backed up CLAUDE.md → CLAUDE.md.bak.$TIMESTAMP"
  fi
else
  touch "$CLAUDE_MD"
  info "Created new CLAUDE.md"
fi

# Append RadioHeader rules with __HOME__ replaced
echo "" >> "$CLAUDE_MD"
sed "s|__HOME__|$HOME|g" "$SCRIPT_DIR/templates/global-claude-md.md" >> "$CLAUDE_MD"

ok "Added RadioHeader rules to CLAUDE.md"

# --- Step 4: Merge hooks into settings.json ---

if [ -f "$SETTINGS_JSON" ]; then
  cp "$SETTINGS_JSON" "$SETTINGS_JSON.bak.$TIMESTAMP"
  ok "Backed up settings.json → settings.json.bak.$TIMESTAMP"

  # Check if hooks already exist
  HAS_CHECK_HOOK=$(grep -c "check-project-architecture.sh" "$SETTINGS_JSON" 2>/dev/null || true)
  HAS_LOADER_HOOK=$(grep -c "radioheader-loader.sh" "$SETTINGS_JSON" 2>/dev/null || true)
  HAS_SYNC_HOOK=$(grep -c "radioheader-memory-sync.sh" "$SETTINGS_JSON" 2>/dev/null || true)
  HAS_STOP_HOOK=$(grep -c "radioheader-stop-reflux.sh" "$SETTINGS_JSON" 2>/dev/null || true)

  if [ "$HAS_CHECK_HOOK" -gt 0 ] && [ "$HAS_LOADER_HOOK" -gt 0 ] && [ "$HAS_SYNC_HOOK" -gt 0 ] && [ "$HAS_STOP_HOOK" -gt 0 ]; then
    ok "Hooks already configured in settings.json"
  else
    # Try jq first, fall back to manual instructions
    if command -v jq &>/dev/null; then
      TEMP_JSON=$(mktemp)

      # Start from current settings
      cp "$SETTINGS_JSON" "$TEMP_JSON"

      # Ensure .hooks object exists
      if ! jq -e '.hooks' "$TEMP_JSON" &>/dev/null; then
        jq '. + {hooks: {}}' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
      fi

      # --- SessionStart hooks ---
      NEW_SESSION_HOOKS='[]'
      if [ "$HAS_CHECK_HOOK" -eq 0 ]; then
        NEW_SESSION_HOOKS=$(echo "$NEW_SESSION_HOOKS" | jq '. + [{"hooks": [{"type": "command", "command": "~/.claude/hooks/check-project-architecture.sh"}]}]')
      fi
      if [ "$HAS_LOADER_HOOK" -eq 0 ]; then
        NEW_SESSION_HOOKS=$(echo "$NEW_SESSION_HOOKS" | jq '. + [{"hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-loader.sh"}]}]')
      fi
      if [ "$(echo "$NEW_SESSION_HOOKS" | jq 'length')" -gt 0 ]; then
        if jq -e '.hooks.SessionStart' "$TEMP_JSON" &>/dev/null; then
          jq --argjson h "$NEW_SESSION_HOOKS" '.hooks.SessionStart += $h' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
        else
          jq --argjson h "$NEW_SESSION_HOOKS" '.hooks.SessionStart = $h' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
        fi
      fi

      # --- PostToolUse hooks (memory sync) ---
      if [ "$HAS_SYNC_HOOK" -eq 0 ]; then
        SYNC_HOOK='[{"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-memory-sync.sh"}]}]'
        if jq -e '.hooks.PostToolUse' "$TEMP_JSON" &>/dev/null; then
          jq --argjson h "$SYNC_HOOK" '.hooks.PostToolUse += $h' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
        else
          jq --argjson h "$SYNC_HOOK" '.hooks.PostToolUse = $h' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
        fi
      fi

      # --- Stop hooks (reflux reminder) ---
      if [ "$HAS_STOP_HOOK" -eq 0 ]; then
        STOP_HOOK='[{"hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-stop-reflux.sh"}]}]'
        if jq -e '.hooks.Stop' "$TEMP_JSON" &>/dev/null; then
          jq --argjson h "$STOP_HOOK" '.hooks.Stop += $h' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
        else
          jq --argjson h "$STOP_HOOK" '.hooks.Stop = $h' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
        fi
      fi

      mv "$TEMP_JSON" "$SETTINGS_JSON"
      ok "Merged hooks into settings.json (SessionStart + PostToolUse + Stop)"
    else
      warn "jq not found. Please manually add the following to ~/.claude/settings.json:"
      echo ""
      cat << 'HOOKS_HELP'
  "hooks": {
    "SessionStart": [
      {"hooks": [{"type": "command", "command": "~/.claude/hooks/check-project-architecture.sh"}]},
      {"hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-loader.sh"}]}
    ],
    "PostToolUse": [
      {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-memory-sync.sh"}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-stop-reflux.sh"}]}
    ]
  }
HOOKS_HELP
      echo ""
      warn "Or install jq (brew install jq / apt install jq) and re-run this script."
    fi
  fi
else
  # Create settings.json from scratch
  cat > "$SETTINGS_JSON" << 'SETTINGS_EOF'
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/check-project-architecture.sh"
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/radioheader-loader.sh"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/radioheader-memory-sync.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/radioheader-stop-reflux.sh"
          }
        ]
      }
    ]
  }
}
SETTINGS_EOF
  ok "Created settings.json with hooks"
fi

# --- Done ---

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  RadioHeader installed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "What's next:"
echo "  1. Open any project with Claude Code"
echo "  2. You'll be asked to enable the dynamic experience framework"
echo "  3. As you work, experience flows into ~/.claude/radioheader/topics/"
echo "  4. All projects can search and use shared experience"
echo ""
echo "Paths:"
echo "  RadioHeader:  $RADIOHEADER_DIR/"
echo "  Hooks:        $HOOKS_DIR/"
echo "  Rules:        $CLAUDE_MD"
echo ""
echo "Backups (if any) have a .bak.$TIMESTAMP suffix."
echo ""
