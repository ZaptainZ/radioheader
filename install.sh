#!/bin/bash
set -e

# RadioHeader — Cross-project memory framework for Claude Code and Codex
# https://github.com/anthropics/radioheader

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
RADIOHEADER_DIR="$CLAUDE_DIR/radioheader"
HOOKS_DIR="$CLAUDE_DIR/hooks"
CLAUDE_MD="$CLAUDE_DIR/CLAUDE.md"
SETTINGS_JSON="$CLAUDE_DIR/settings.json"
CODEX_DIR="$HOME/.codex"
CODEX_AGENTS="$CODEX_DIR/AGENTS.md"
CODEX_HOOKS_JSON="$CODEX_DIR/hooks.json"
TIMESTAMP=$(date +%Y%m%d%H%M%S)
RUNTIME="both"

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

# The rc file the user's interactive shell actually reads (for PATH persistence)
detect_shell_rc() {
  case "${SHELL:-}" in
    */zsh)  echo "$HOME/.zshrc" ;;
    */bash)
      if [ "$(uname)" = "Darwin" ]; then echo "$HOME/.bash_profile"; else echo "$HOME/.bashrc"; fi ;;
    *)      echo "$HOME/.profile" ;;
  esac
}

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
    --help|-h)
      cat <<EOF
Usage: ./install.sh [--runtime claude|codex|both]
EOF
      exit 0
      ;;
    *)
      err "Unknown flag: $1"
      exit 1
      ;;
  esac
done

case "$RUNTIME" in
  claude|codex|both) ;;
  *)
    err "Invalid runtime: $RUNTIME (expected claude, codex, or both)"
    exit 1
    ;;
esac

claude_enabled() {
  [ "$RUNTIME" = "claude" ] || [ "$RUNTIME" = "both" ]
}

codex_enabled() {
  [ "$RUNTIME" = "codex" ] || [ "$RUNTIME" = "both" ]
}

append_managed_section() {
  local target="$1"
  local template="$2"
  local label="$3"
  if [ -f "$target" ]; then
    if grep -q "RadioHeader START" "$target" 2>/dev/null; then
      warn "Updating existing RadioHeader section in $label"
      cp "$target" "$target.bak.$TIMESTAMP"
      sed '/^# --- RadioHeader START ---$/,/^# --- RadioHeader END ---$/d' "$target.bak.$TIMESTAMP" > "$target"
    else
      cp "$target" "$target.bak.$TIMESTAMP"
      ok "Backed up $label → $(basename "$target").bak.$TIMESTAMP"
    fi
  else
    mkdir -p "$(dirname "$target")"
    touch "$target"
    info "Created new $label"
  fi

  echo "" >> "$target"
  sed "s|__HOME__|$HOME|g" "$template" >> "$target"
}

merge_codex_hooks() {
  python3 - <<PY
import copy
import json
import os

path = os.path.expanduser("$CODEX_HOOKS_JSON")
backup = f"{path}.bak.$TIMESTAMP"
data = {}
if os.path.exists(path):
    with open(path) as f:
        raw = f.read()
    try:
        data = json.loads(raw)
    except Exception:
        # Corrupt JSON: save aside and start fresh.
        with open(backup, "w") as bf:
            bf.write(raw)
        data = {}
    else:
        # Back up valid JSON before we touch it so the user can roll back.
        with open(backup, "w") as bf:
            bf.write(raw)

hooks = data.setdefault("hooks", {})

# All commands RadioHeader manages. Anything matching any of these tokens is
# considered a stale RadioHeader hook and will be stripped before re-adding.
MANAGED_TOKENS = (
    "check-project-architecture.sh",
    "radioheader-loader.sh",
    "radioheader-error-capture.sh",
    "radioheader-codex-userprompt.py",
    "radioheader-stop-codex.py",
)

def strip_managed(event):
    groups = hooks.get(event, [])
    new_groups = []
    for group in groups:
        new_hooks = [
            h for h in group.get("hooks", [])
            if not any(tok in h.get("command", "") for tok in MANAGED_TOKENS)
        ]
        if new_hooks:
            new_group = copy.deepcopy(group)
            new_group["hooks"] = new_hooks
            new_groups.append(new_group)
    hooks[event] = new_groups

def add(event, entry):
    hooks.setdefault(event, []).append(entry)

before = json.dumps(data, sort_keys=True)

for ev in ("SessionStart", "PostToolUse", "UserPromptSubmit", "Stop"):
    strip_managed(ev)

add("SessionStart", {
    "matcher": "startup|resume",
    "hooks": [
        {"type": "command", "command": "~/.claude/hooks/check-project-architecture.sh"},
        {"type": "command", "command": "~/.claude/hooks/radioheader-loader.sh"},
    ],
})
add("PostToolUse", {
    "matcher": "Bash",
    "hooks": [
        {"type": "command", "command": "~/.claude/hooks/radioheader-error-capture.sh"}
    ],
})
add("UserPromptSubmit", {
    "hooks": [
        {"type": "command", "command": "~/.claude/hooks/radioheader-codex-userprompt.py"}
    ],
})
add("Stop", {
    "hooks": [
        {"type": "command", "command": "~/.claude/hooks/radioheader-stop-codex.py"}
    ],
})

# Drop empty event arrays so the resulting file stays clean.
for ev in list(hooks):
    if not hooks[ev]:
        del hooks[ev]

after = json.dumps(data, sort_keys=True)

os.makedirs(os.path.dirname(path), exist_ok=True)
with open(path, "w") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write("\\n")
print("changed" if before != after else "unchanged")
PY
}

# --- Pre-checks ---

mkdir -p "$CLAUDE_DIR"
mkdir -p "$CODEX_DIR"

if [ -d "$RADIOHEADER_DIR" ]; then
  warn "RadioHeader is already installed at $RADIOHEADER_DIR"
  read -p "Reinstall? This will NOT delete your existing topics. [y/N] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    info "Aborted."
    exit 0
  fi
fi

info "Installing RadioHeader (runtime: $RUNTIME)..."

# --- Step 1: Create radioheader directory ---

mkdir -p "$RADIOHEADER_DIR/topics"
mkdir -p "$RADIOHEADER_DIR/shortwave"

if [ ! -f "$RADIOHEADER_DIR/INDEX.md" ]; then
  sed "s|__HOME__|$HOME|g" "$SCRIPT_DIR/templates/radioheader/INDEX.md" > "$RADIOHEADER_DIR/INDEX.md"
  ok "Created INDEX.md"
fi

if [ ! -f "$RADIOHEADER_DIR/project-registry.md" ]; then
  cp "$SCRIPT_DIR/templates/radioheader/project-registry.md" "$RADIOHEADER_DIR/project-registry.md"
  ok "Created project-registry.md"
fi

if [ ! -f "$RADIOHEADER_DIR/project-registry.json" ]; then
  if [ -f "$SCRIPT_DIR/templates/radioheader/project-registry.json" ]; then
    cp "$SCRIPT_DIR/templates/radioheader/project-registry.json" "$RADIOHEADER_DIR/project-registry.json"
  else
    python3 -c "
import json
data = {'version': 1, 'projects': [], 'domain_index': {}}
with open('$RADIOHEADER_DIR/project-registry.json', 'w') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)
    f.write('\n')
"
  fi
  ok "Created project-registry.json"
fi

if [ ! -f "$RADIOHEADER_DIR/user-profile.md" ]; then
  cat > "$RADIOHEADER_DIR/user-profile.md" <<'PROFILE'
# 用户画像

> RadioHeader 注意力记忆架构的查询向量组成部分。
> 维度 1（用户做过什么）由 project-registry.json 承载。

## 工作方式（维度 2）

- problem_solving:
- interaction_style:
- strengths:
- weaknesses:

## 资源（维度 3）

- devices:
- network:
- accounts:
PROFILE
  ok "Created user-profile.md (fill in your details)"
fi

# --- Step 1.5: Copy project templates ---

TEMPLATE_DEST="$RADIOHEADER_DIR/templates/project"
mkdir -p "$TEMPLATE_DEST"
cp -R "$SCRIPT_DIR/templates/project/" "$TEMPLATE_DEST/"
ok "Installed project templates → $TEMPLATE_DEST"

# --- Step 2: Install hook scripts ---

mkdir -p "$HOOKS_DIR"

cp "$SCRIPT_DIR/templates/hooks/check-project-architecture.sh" "$HOOKS_DIR/check-project-architecture.sh"
chmod +x "$HOOKS_DIR/check-project-architecture.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-loader.sh" "$HOOKS_DIR/radioheader-loader.sh"
chmod +x "$HOOKS_DIR/radioheader-loader.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-memory-sync.sh" "$HOOKS_DIR/radioheader-memory-sync.sh"
chmod +x "$HOOKS_DIR/radioheader-memory-sync.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-stop-echo.sh" "$HOOKS_DIR/radioheader-stop-echo.sh"
chmod +x "$HOOKS_DIR/radioheader-stop-echo.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-error-capture.sh" "$HOOKS_DIR/radioheader-error-capture.sh"
chmod +x "$HOOKS_DIR/radioheader-error-capture.sh"

cp "$SCRIPT_DIR/templates/hooks/radioheader-codex-userprompt.py" "$HOOKS_DIR/radioheader-codex-userprompt.py"
chmod +x "$HOOKS_DIR/radioheader-codex-userprompt.py"

cp "$SCRIPT_DIR/templates/hooks/radioheader-stop-codex.py" "$HOOKS_DIR/radioheader-stop-codex.py"
chmod +x "$HOOKS_DIR/radioheader-stop-codex.py"

ok "Installed hook scripts (7 hooks)"

# --- Step 3: Append rules to CLAUDE.md ---

if claude_enabled; then
  append_managed_section "$CLAUDE_MD" "$SCRIPT_DIR/templates/global-claude-md.md" "CLAUDE.md"
  ok "Added RadioHeader rules to CLAUDE.md"
fi

if codex_enabled; then
  append_managed_section "$CODEX_AGENTS" "$SCRIPT_DIR/templates/global-agents-md.md" "AGENTS.md"
  ok "Added RadioHeader rules to ~/.codex/AGENTS.md"
fi

# --- Step 4: Merge hooks into settings.json ---

if claude_enabled && [ -f "$SETTINGS_JSON" ]; then
  cp "$SETTINGS_JSON" "$SETTINGS_JSON.bak.$TIMESTAMP"
  ok "Backed up settings.json → settings.json.bak.$TIMESTAMP"

  # Validate existing JSON — if corrupt, rebuild from scratch (inspired by
  # Claude Code config.rs: legacy files are silently skipped on parse error)
  SETTINGS_VALID=true
  if command -v jq &>/dev/null; then
    if ! jq empty "$SETTINGS_JSON" 2>/dev/null; then
      warn "settings.json is not valid JSON — rebuilding (backup preserved at settings.json.bak.$TIMESTAMP)"
      SETTINGS_VALID=false
    fi
  elif command -v python3 &>/dev/null; then
    if ! python3 -c "import json; json.load(open('$SETTINGS_JSON'))" 2>/dev/null; then
      warn "settings.json is not valid JSON — rebuilding (backup preserved at settings.json.bak.$TIMESTAMP)"
      SETTINGS_VALID=false
    fi
  fi

  if [ "$SETTINGS_VALID" = false ]; then
    # Remove corrupt file — will be recreated in the else branch below
    rm "$SETTINGS_JSON"
  fi
fi

if claude_enabled && [ -f "$SETTINGS_JSON" ]; then
  # Check if hooks already exist
  HAS_CHECK_HOOK=$(grep -c "check-project-architecture.sh" "$SETTINGS_JSON" 2>/dev/null || true)
  HAS_LOADER_HOOK=$(grep -c "radioheader-loader.sh" "$SETTINGS_JSON" 2>/dev/null || true)
  HAS_SYNC_HOOK=$(grep -c "radioheader-memory-sync.sh" "$SETTINGS_JSON" 2>/dev/null || true)
  HAS_STOP_HOOK=$(grep -c "radioheader-stop-echo.sh" "$SETTINGS_JSON" 2>/dev/null || true)

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

      # --- PostToolUse hooks (error capture) ---
      ERROR_HOOK='[{"matcher": "Bash", "hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-error-capture.sh"}]}]'
      if ! grep -q "radioheader-error-capture" "$TEMP_JSON" 2>/dev/null; then
        jq --argjson h "$ERROR_HOOK" '.hooks.PostToolUse += $h' "$TEMP_JSON" > "$TEMP_JSON.tmp" && mv "$TEMP_JSON.tmp" "$TEMP_JSON"
      fi

      # --- Stop hooks (Echo reminder) ---
      if [ "$HAS_STOP_HOOK" -eq 0 ]; then
        STOP_HOOK='[{"hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-stop-echo.sh"}]}]'
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
      {"matcher": "Write|Edit", "hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-memory-sync.sh"}]},
      {"matcher": "Bash", "hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-error-capture.sh"}]}
    ],
    "Stop": [
      {"hooks": [{"type": "command", "command": "~/.claude/hooks/radioheader-stop-echo.sh"}]}
    ]
  }
HOOKS_HELP
      echo ""
      warn "Or install jq (brew install jq / apt install jq) and re-run this script."
    fi
  fi
elif claude_enabled
then
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
      },
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/radioheader-error-capture.sh"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/hooks/radioheader-stop-echo.sh"
          }
        ]
      }
    ]
  }
}
SETTINGS_EOF
  ok "Created settings.json with hooks"
fi

if codex_enabled; then
  CODEX_HOOK_STATUS=$(merge_codex_hooks)
  if [ "$CODEX_HOOK_STATUS" = "changed" ]; then
    ok "Merged hooks into ~/.codex/hooks.json"
  else
    ok "Hooks already configured in ~/.codex/hooks.json"
  fi
fi

# --- Step 5: Install CLI ---

CLI_INSTALLED=""
if [ -w "/usr/local/bin" ]; then
  cp "$SCRIPT_DIR/radioheader" "/usr/local/bin/radioheader"
  chmod +x "/usr/local/bin/radioheader"
  CLI_INSTALLED="/usr/local/bin/radioheader"
  ok "Installed CLI → /usr/local/bin/radioheader"
elif command -v sudo &>/dev/null; then
  info "Installing CLI to /usr/local/bin (may require sudo)..."
  if sudo cp "$SCRIPT_DIR/radioheader" "/usr/local/bin/radioheader" 2>/dev/null && sudo chmod +x "/usr/local/bin/radioheader" 2>/dev/null; then
    CLI_INSTALLED="/usr/local/bin/radioheader"
    ok "Installed CLI → /usr/local/bin/radioheader"
  else
    warn "Could not install to /usr/local/bin, trying ~/bin/ ..."
  fi
fi

if [ -z "$CLI_INSTALLED" ]; then
  mkdir -p "$HOME/bin"
  cp "$SCRIPT_DIR/radioheader" "$HOME/bin/radioheader"
  chmod +x "$HOME/bin/radioheader"
  CLI_INSTALLED="$HOME/bin/radioheader"
  ok "Installed CLI → ~/bin/radioheader"

  # ~/bin is NOT in the default PATH on macOS zsh (and on many Linux setups only
  # after re-login). Without fixing this, the CLI is installed but unreachable —
  # a warn alone gets ignored once and the breakage becomes permanent.
  if ! echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/bin"; then
    SHELL_RC="$(detect_shell_rc)"
    if [ -f "$SHELL_RC" ] && grep -E 'PATH=' "$SHELL_RC" 2>/dev/null | grep -qE '(\$HOME|~|'"$HOME"')/bin([":]|$)'; then
      warn "~/bin is configured in $SHELL_RC but not active in this shell."
      echo "  Restart your shell or run: source $SHELL_RC"
    elif [ -t 0 ]; then
      echo ""
      read -p "  ~/bin is not in your PATH. Add it to $SHELL_RC? (recommended) [Y/n] " -n 1 -r
      echo
      if [[ $REPLY =~ ^[Nn]$ ]]; then
        warn "Skipped. The CLI won't be reachable as 'radioheader' until you add:"
        echo "  export PATH=\"\$HOME/bin:\$PATH\""
      else
        {
          echo ""
          echo "# Added by RadioHeader install.sh — ~/bin holds the radioheader CLI"
          echo "export PATH=\"\$HOME/bin:\$PATH\""
        } >> "$SHELL_RC"
        ok "Added ~/bin to PATH in $SHELL_RC (takes effect in new shells)"
      fi
    else
      warn "~/bin is not in your PATH. Add it with:"
      echo "  echo 'export PATH=\"\$HOME/bin:\$PATH\"' >> $SHELL_RC"
      echo "  ('radioheader doctor' will keep flagging this until fixed)"
    fi
    # Make the CLI reachable for the remainder of this install run
    export PATH="$HOME/bin:$PATH"
  fi
fi

# --- Step 5.5: Auto-initialize (index + consolidate) ---

echo ""
info "Running post-install initialization..."

# Copy Python scripts alongside CLI
for pyfile in fts-index.py fts-search.py attn-consolidate.py radioheader-mcp-server.py; do
  if [ -f "$SCRIPT_DIR/$pyfile" ]; then
    cp "$SCRIPT_DIR/$pyfile" "$(dirname "$CLI_INSTALLED")/$pyfile"
    if [[ "$pyfile" == "radioheader-mcp-server.py" ]]; then
      chmod +x "$(dirname "$CLI_INSTALLED")/$pyfile"
    fi
  fi
done

# Build FTS5 search index (if shortwave/topics exist)
if command -v radioheader &>/dev/null || [ -n "$CLI_INSTALLED" ]; then
  SW_COUNT=$(ls "$RADIOHEADER_DIR/shortwave/"*.md 2>/dev/null | wc -l | tr -d ' ')
  TOPIC_COUNT=$(ls "$RADIOHEADER_DIR/topics/"*.md 2>/dev/null | wc -l | tr -d ' ')
  if [ "$((SW_COUNT + TOPIC_COUNT))" -gt 0 ]; then
    info "Building search index..."
    if "$CLI_INSTALLED" index --rebuild >/dev/null 2>&1; then
      ok "Search index built ($((SW_COUNT + TOPIC_COUNT)) source files)"
    else
      warn "Search index build skipped (run 'radioheader index' manually)"
    fi
  fi

  # Run consolidate to generate context-digest
  info "Generating context digest..."
  if "$CLI_INSTALLED" consolidate >/dev/null 2>&1; then
    ok "Context digest generated"
  else
    warn "Context digest skipped (run 'radioheader consolidate' manually)"
  fi
fi

# --- Step 6: Community toggle ---

CONFIG_FILE="$RADIOHEADER_DIR/config.json"

echo ""
info "Community Shortwave Sharing"
echo "  RadioHeader can search a shared community library of shortwave entries."
echo "  When enabled, search results include community entries with quality scores."
echo "  You can toggle this anytime with: radioheader community on|off"
echo ""
read -p "  Enable community sharing? (recommended) [Y/n] " -n 1 -r
echo

COMMUNITY_ENABLED="true"
if [[ $REPLY =~ ^[Nn]$ ]]; then
  COMMUNITY_ENABLED="false"
fi

python3 -c "
import json, os
path = '$CONFIG_FILE'
d = {}
if os.path.exists(path):
    with open(path) as f:
        try: d = json.load(f)
        except: d = {}
d['community'] = '$COMMUNITY_ENABLED' == 'true'
with open(path,'w') as f:
    json.dump(d, f, indent=2, ensure_ascii=False)
    f.write('\n')
" 2>/dev/null || true

if [ "$COMMUNITY_ENABLED" = "true" ]; then
  ok "Community sharing enabled. Run 'radioheader sync' to download the library."
else
  ok "Community sharing disabled. Enable later with: radioheader community on"
fi

# --- Done ---

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  RadioHeader installed successfully!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "What's next:"
if [ "$RUNTIME" = "both" ]; then
  echo "  1. Open any project with Claude Code or Codex — RadioHeader is already active"
elif [ "$RUNTIME" = "claude" ]; then
  echo "  1. Open any project with Claude Code — RadioHeader is already active"
else
  echo "  1. Open any project with Codex — RadioHeader is already active"
fi
echo "  2. Optionally run 'radioheader init' inside a project for per-project scaffolding"
if [ "$COMMUNITY_ENABLED" = "true" ]; then
echo "  3. Run 'radioheader sync' to download the community library"
fi
echo ""
echo "Everything else is automatic:"
echo "  - Search index is built and kept up to date"
echo "  - Context digest updates every few memory syncs"
echo "  - Experience flows back via Echo hooks"
echo ""
echo "CLI commands:"
echo "  radioheader search      # Search all experience (BM25 + synonyms)"
echo "  radioheader init        # Initialize a project"
echo "  radioheader learn <url> # Extract article into shortwave"
echo "  radioheader consolidate # Update context digest"
echo "  radioheader status      # Show status"
echo "  radioheader doctor      # Health check"
echo ""
echo "Paths:"
echo "  RadioHeader:  $RADIOHEADER_DIR/"
echo "  Hooks:        $HOOKS_DIR/"
if claude_enabled; then
echo "  Claude rules: $CLAUDE_MD"
fi
if codex_enabled; then
echo "  Codex rules:  $CODEX_AGENTS"
echo "  Codex hooks:  $CODEX_HOOKS_JSON"
fi
echo "  CLI:          $CLI_INSTALLED"
echo ""
echo "Backups (if any) have a .bak.$TIMESTAMP suffix."
echo ""
