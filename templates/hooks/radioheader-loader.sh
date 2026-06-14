#!/bin/bash

# RadioHeader: Inject cross-project experience hub context at session start.

# Prepend standard user-bin dirs so `command -v radiomind` detects an install
# even under a minimal hook PATH (e.g. Codex non-interactive shells lack ~/bin),
# otherwise the install suggestion shows even when radiomind is present.
export PATH="$HOME/bin:$HOME/.local/bin:$PATH"

RADIOHEADER_DIR="$HOME/.claude/radioheader"

if [ -d "$RADIOHEADER_DIR/topics" ]; then
  TOPIC_COUNT=$(ls "$RADIOHEADER_DIR/topics/"*.md 2>/dev/null | wc -l | tr -d ' ')
  SHORTWAVE_COUNT=$(ls "$RADIOHEADER_DIR/shortwave/"*.md 2>/dev/null | wc -l | tr -d ' ')
  PROJECT_COUNT=$(python3 -c "import json;print(len(json.load(open('$RADIOHEADER_DIR/project-registry.json')).get('projects',[])))" 2>/dev/null || echo "?")
  if [ "$TOPIC_COUNT" -gt 0 ]; then
    echo ""
    echo "RadioHeader: your cross-project memory CLI (~/.claude/radioheader/)"
    echo "  Holds:  ${SHORTWAVE_COUNT} shortwave entries + ${TOPIC_COUNT} topic files from ${PROJECT_COUNT} projects you've worked on"
    echo "  Query:  radioheader search \"<symptom>\"   — FTS5 + 中英同义词扩展 (白屏 ↔ blank screen)"
    echo "  Tip:    symptom words (白屏/闪退/错位/丢失/慢), not action words; for multi-symptom use OR: \"白屏|闪退\""
    echo "          spaces = AND-strict (usually miss); Chinese hits more than English; no stemming"
    echo "  Index:  $RADIOHEADER_DIR/INDEX.md"
    echo ""
  fi
fi

# Inject context digest (attention-compressed environmental awareness)
# Budget guard: Claude Code truncates instruction files at ~4K chars.
# If digest exceeds 3500 chars, inject truncated version with warning.
MAX_DIGEST_CHARS=3500
DIGEST="$RADIOHEADER_DIR/context-digest.md"
if [ -f "$DIGEST" ]; then
  DIGEST_SIZE=$(wc -c < "$DIGEST" | tr -d ' ')
  echo "--- context-digest ---"
  if [ "$DIGEST_SIZE" -le "$MAX_DIGEST_CHARS" ]; then
    cat "$DIGEST"
  else
    head -c "$MAX_DIGEST_CHARS" "$DIGEST"
    echo ""
    echo "> [loader truncated: ${DIGEST_SIZE}/${MAX_DIGEST_CHARS} chars — run \`radioheader consolidate\` to regenerate]"
  fi
  echo "--- end digest ---"
fi

# Periodic RadioMind suggestion (once per cooldown window)
if ! command -v radiomind &>/dev/null; then
  SUGGEST_FILE="$RADIOHEADER_DIR/.radiomind-suggested"
  COOLDOWN_DAYS=14
  show_suggest=false
  if [ ! -f "$SUGGEST_FILE" ]; then
    show_suggest=true
  else
    last_ts=$(cat "$SUGGEST_FILE" 2>/dev/null || echo "0")
    now_ts=$(date +%s)
    diff=$(( now_ts - last_ts ))
    cooldown=$(( COOLDOWN_DAYS * 86400 ))
    [ "$diff" -ge "$cooldown" ] && show_suggest=true
  fi
  if [ "$show_suggest" = true ]; then
    echo ""
    echo "Tip: RadioMind can enhance RadioHeader with pyramid search, three-body"
    echo "debate refinement, and dream pruning — reading your existing data."
    echo "Install: pip install radiomind  |  Docs: https://github.com/ZaptainZ/radiomind"
    date +%s > "$SUGGEST_FILE" 2>/dev/null || true
  fi
fi

exit 0
