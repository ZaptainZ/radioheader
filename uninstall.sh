#!/bin/bash
set -e

# RadioHeader — Uninstaller
# Removes RadioHeader components, optionally preserves topic files.

CLAUDE_DIR="$HOME/.claude"
RADIOHEADER_DIR="$CLAUDE_DIR/radioheader"
HOOKS_DIR="$CLAUDE_DIR/hooks"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
SETTINGS_JSON="$CLAUDE_DIR/settings.json"
KIMI_DIR="${KIMI_CODE_HOME:-$HOME/.kimi-code}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CODEX_DIR="$HOME/.codex"
CODEX_AGENTS="$CODEX_DIR/AGENTS.md"
CODEX_HOOKS_JSON="$CODEX_DIR/hooks.json"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
RUNTIME="both"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[RadioHeader]${NC} $1"; }
ok()    { echo -e "${GREEN}[RadioHeader]${NC} $1"; }
warn()  { echo -e "${YELLOW}[RadioHeader]${NC} $1"; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    --runtime)
      RUNTIME="$2"
      shift 2
      ;;
    --runtime=*)
      RUNTIME="${1#*=}"
      shift
      ;;
    *)
      echo "Usage: ./uninstall.sh [--runtime claude|codex|kimi|both|all]"
      exit 1
      ;;
  esac
done

case "$RUNTIME" in
  claude|codex|kimi|both|all) ;;
  *)
    echo "Invalid runtime: $RUNTIME"
    exit 1
    ;;
esac

claude_enabled() {
  [ "$RUNTIME" = "claude" ] || [ "$RUNTIME" = "both" ] || [ "$RUNTIME" = "all" ]
}

codex_enabled() {
  [ "$RUNTIME" = "codex" ] || [ "$RUNTIME" = "both" ] || [ "$RUNTIME" = "all" ]
}

kimi_enabled() {
  [ "$RUNTIME" = "kimi" ] || [ "$RUNTIME" = "all" ]
}

# "both" retains its original CC+Codex meaning. Never remove shared engines
# when an installed Kimi runtime still depends on them.
FULL_UNINSTALL=false
if [ "$RUNTIME" = "all" ] || { [ "$RUNTIME" = "both" ] &&
    ! grep -q 'RadioHeader START' "$KIMI_DIR/AGENTS.md" 2>/dev/null &&
    ! grep -q 'radioheader-kimi.py' "$KIMI_DIR/config.toml" 2>/dev/null; }; then
  FULL_UNINSTALL=true
fi

# Validate/remove the owned config first; failure leaves its scripts available.
if kimi_enabled; then
  KIMI_PY=""
  for candidate in python3 python3.14 python3.13 python3.12 python3.11 /opt/homebrew/bin/python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import tomllib' 2>/dev/null; then
      KIMI_PY="$candidate"; break
    fi
  done
  if [ -z "$KIMI_PY" ]; then echo "Kimi configuration needs Python 3.11+"; exit 1; fi
  "$KIMI_PY" "$SCRIPT_DIR/kimi-config.py" remove --config "$KIMI_DIR/config.toml"
fi

remove_managed_section() {
  local target="$1"
  local label="$2"
  if [ -f "$target" ] && grep -q "RadioHeader START" "$target" 2>/dev/null; then
    cp "$target" "$target.bak.$TIMESTAMP"
    sed '/^# --- RadioHeader START ---$/,/^# --- RadioHeader END ---$/d' "$target.bak.$TIMESTAMP" > "$target"
    ok "Removed RadioHeader rules from $label (backup: .bak.$TIMESTAMP)"
  fi
}

clean_codex_hooks() {
  python3 - <<PY
import json
import os

path = os.path.expanduser("$CODEX_HOOKS_JSON")
if not os.path.exists(path):
    raise SystemExit(0)
backup = f"{path}.bak.$TIMESTAMP"
try:
    with open(path) as f:
        data = json.load(f)
except Exception:
    # Corrupt JSON: preserve the broken file as backup and leave hooks.json
    # untouched so the user can inspect and repair.
    os.replace(path, backup)
    raise SystemExit(0)

hooks = data.get("hooks", {}) or {}
targets = {
    "check-project-architecture.sh",
    "radioheader-loader.sh",
    "radioheader-error-capture.sh",
    "radioheader-codex-userprompt.py",
    "radioheader-stop-codex.py",
    "radioheader-git-sync.sh",
}
for event, groups in list(hooks.items()):
    kept = []
    for group in groups:
        new_group = dict(group)
        new_hooks = []
        for hook in group.get("hooks", []):
            command = hook.get("command", "")
            if any(token in command for token in targets):
                continue
            new_hooks.append(hook)
        if new_hooks:
            new_group["hooks"] = new_hooks
            kept.append(new_group)
    if kept:
        hooks[event] = kept
    else:
        # No non-RadioHeader hooks remain for this event — drop the empty
        # array so Codex doesn't see a stub event.
        del hooks[event]

if hooks:
    data["hooks"] = hooks
else:
    # Nothing left under "hooks" — drop the key entirely.
    data.pop("hooks", None)

os.replace(path, backup)
if data:
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\\n")
else:
    # File only contained RadioHeader-managed hooks. Leave the filesystem
    # tidy: no empty "{}" left behind. Backup keeps the history.
    pass
PY
}

if [ ! -d "$RADIOHEADER_DIR" ] && ! grep -q "RadioHeader START" "$CLAUDE_MD" 2>/dev/null && ! grep -q "RadioHeader START" "$CODEX_AGENTS" 2>/dev/null; then
  info "RadioHeader does not appear to be installed. Nothing to do."
  exit 0
fi

echo -e "${YELLOW}This will remove RadioHeader from your $RUNTIME runtime setup.${NC}"
echo ""

# --- Step 1: Remove RadioHeader section from CLAUDE.md ---

if claude_enabled; then
  remove_managed_section "$CLAUDE_MD" "CLAUDE.md"
fi

if codex_enabled; then
  remove_managed_section "$CODEX_AGENTS" "~/.codex/AGENTS.md"
fi

if kimi_enabled; then
  remove_managed_section "$KIMI_DIR/AGENTS.md" "Kimi AGENTS.md"
  rm -f "$HOOKS_DIR/radioheader-kimi.py"
fi

# --- Step 2: Remove shared hook scripts only on full uninstall ---

if [ "$FULL_UNINSTALL" = "true" ]; then
  rm -f "$HOOKS_DIR/radioheader-kimi.py"
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

  if [ -f "$HOOKS_DIR/radioheader-stop-echo.sh" ]; then
    rm "$HOOKS_DIR/radioheader-stop-echo.sh"
    ok "Removed radioheader-stop-echo.sh"
  fi

  if [ -f "$HOOKS_DIR/radioheader-error-capture.sh" ]; then
    rm "$HOOKS_DIR/radioheader-error-capture.sh"
    ok "Removed radioheader-error-capture.sh"
  fi

  if [ -f "$HOOKS_DIR/radioheader-codex-userprompt.py" ]; then
    rm "$HOOKS_DIR/radioheader-codex-userprompt.py"
    ok "Removed radioheader-codex-userprompt.py"
  fi

  if [ -f "$HOOKS_DIR/radioheader-stop-codex.py" ]; then
    rm "$HOOKS_DIR/radioheader-stop-codex.py"
    ok "Removed radioheader-stop-codex.py"
  fi

  if [ -f "$HOOKS_DIR/radioheader-git-sync.sh" ]; then
    rm "$HOOKS_DIR/radioheader-git-sync.sh"
    ok "Removed radioheader-git-sync.sh (sync repo in ~/.claude/radioheader is kept)"
  fi
else
  info "Keeping shared hook scripts in $HOOKS_DIR for the other runtime."
fi

# --- Step 3: Clean hooks from settings.json ---

if claude_enabled && [ -f "$SETTINGS_JSON" ] && command -v jq &>/dev/null; then
  cp "$SETTINGS_JSON" "$SETTINGS_JSON.bak.$TIMESTAMP"
  TEMP_JSON=$(mktemp)

  jq '
    # Clean SessionStart hooks
    (if .hooks.SessionStart then
      .hooks.SessionStart |= map(
        select(
          .hooks | all(.command | (
            contains("check-project-architecture.sh") or
            contains("radioheader-loader.sh") or
            contains("radioheader-git-sync.sh")
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
          .hooks | all(.command | (
            contains("radioheader-stop-echo.sh") or
            contains("radioheader-git-sync.sh")
          ) | not)
        )
      )
    else . end)
  ' "$SETTINGS_JSON" > "$TEMP_JSON"

  mv "$TEMP_JSON" "$SETTINGS_JSON"
  ok "Removed hooks from settings.json (backup: .bak.$TIMESTAMP)"
else
  if claude_enabled; then
    warn "Please manually remove RadioHeader hooks from ~/.claude/settings.json"
  fi
fi

if codex_enabled; then
  if [ -f "$CODEX_HOOKS_JSON" ]; then
    clean_codex_hooks
    ok "Removed hooks from ~/.codex/hooks.json (backup: .bak.$TIMESTAMP)"
  else
    warn "Please manually remove RadioHeader hooks from ~/.codex/hooks.json"
  fi
fi

# --- Step 4: Handle radioheader directory ---

if [ "$FULL_UNINSTALL" = "true" ] && [ -d "$RADIOHEADER_DIR" ]; then
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

# --- Step 5: Remove CLI and companion scripts ---

COMPANION_SCRIPTS="fts-index.py fts-search.py attn-consolidate.py radioheader-mcp-server.py kimi-config.py"

remove_cli_dir() {
  local dir="$1"
  rm -f "$dir/radioheader"
  for pyfile in $COMPANION_SCRIPTS; do
    rm -f "$dir/$pyfile"
  done
}

if [ "$FULL_UNINSTALL" = "true" ] && [ -f "/usr/local/bin/radioheader" ]; then
  if [ -w "/usr/local/bin" ]; then
    remove_cli_dir "/usr/local/bin"
  else
    sudo rm -f /usr/local/bin/radioheader 2>/dev/null || warn "Could not remove /usr/local/bin/radioheader (try: sudo rm /usr/local/bin/radioheader)"
    for pyfile in $COMPANION_SCRIPTS; do
      sudo rm -f "/usr/local/bin/$pyfile" 2>/dev/null
    done
  fi
  ok "Removed CLI and companion scripts from /usr/local/bin/"
fi

if [ "$FULL_UNINSTALL" = "true" ] && [ -f "$HOME/bin/radioheader" ]; then
  remove_cli_dir "$HOME/bin"
  ok "Removed CLI and companion scripts from ~/bin/"
fi

# Remove the PATH line install.sh may have added (only the marked block; a
# user's own PATH lines are untouched because the marker guards the delete)
if [ "$FULL_UNINSTALL" = "true" ]; then
  for rc in "$HOME/.zshrc" "$HOME/.bash_profile" "$HOME/.bashrc" "$HOME/.profile"; do
    if [ -f "$rc" ] && grep -q "# Added by RadioHeader install.sh" "$rc"; then
      sed -i.radioheader-uninstall-bak \
        -e '/^# Added by RadioHeader install\.sh/d' \
        -e '/^export PATH="\$HOME\/bin:\$PATH"$/d' \
        "$rc" && rm -f "$rc.radioheader-uninstall-bak"
      ok "Removed RadioHeader PATH line from $rc"
    fi
  done
fi

echo ""
ok "RadioHeader uninstall completed for runtime: $RUNTIME."
echo ""
echo "Note: Per-project .claude/rules/ files are NOT removed."
echo "Remove them manually if desired."
echo ""
