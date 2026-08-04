#!/bin/bash

# e2e tests for the auto_digest scope: loader self-heal of missing derived
# files + memory-sync native refresh, and their gating (env / config.json).
# Pure-local by design: stubs `radioheader` to record invocations.
# bash 3 compatible (macOS /bin/bash).

set -u

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOADER="$REPO_DIR/templates/hooks/radioheader-loader.sh"
MEMSYNC="$REPO_DIR/templates/hooks/radioheader-memory-sync.sh"

PASS=0
FAIL=0

ok()   { PASS=$((PASS + 1)); echo "  ✓ $1"; }
bad()  { FAIL=$((FAIL + 1)); echo "  ✗ $1"; }

check() {  # check <desc> <condition...>
  local desc="$1"; shift
  if "$@"; then ok "$desc"; else bad "$desc"; fi
}

# --- Sandbox: fake HOME with a recording radioheader stub in $HOME/bin ---
make_sandbox() {
  SANDBOX=$(mktemp -d)
  export HOME="$SANDBOX"
  mkdir -p "$SANDBOX/.claude/radioheader" "$SANDBOX/bin"
  CALL_LOG="$SANDBOX/calls.log"
  : > "$CALL_LOG"
  cat > "$SANDBOX/bin/radioheader" <<STUB
#!/bin/bash
echo "\$@" >> "$CALL_LOG"
STUB
  chmod +x "$SANDBOX/bin/radioheader"
}

drain_bg() {  # background consolidate is fire-and-forget; give it a beat
  sleep 0.5
}

wait_for_call() {  # poll up to 2s for the stub call to land in the log
  local i=0
  while [ $i -lt 20 ]; do
    [ -s "$CALL_LOG" ] && return 0
    sleep 0.1
    i=$((i + 1))
  done
  return 1
}

REAL_HOME="$HOME"

echo ""
echo "auto_digest gating + self-heal tests"
echo ""

# ============================================================
echo "[1] loader self-heal: missing derived files trigger native rebuild"
make_sandbox
unset RADIOHEADER_AUTO_DIGEST 2>/dev/null || true
OUT=$(bash "$LOADER" 2>/dev/null)
wait_for_call
check "invokes consolidate --native" grep -q "consolidate --native" "$CALL_LOG"
check "prints rebuild notice" bash -c "echo \"$OUT\" | grep -q 'rebuilding natively'"
check "writes throttle marker" test -f "$SANDBOX/.claude/radioheader/.digest-rebuilding"

# Second run inside throttle window must NOT re-trigger
: > "$CALL_LOG"
bash "$LOADER" >/dev/null 2>&1
drain_bg
check "throttled within 5 min (no second rebuild)" test ! -s "$CALL_LOG"

# ============================================================
echo "[2] loader self-heal: no trigger when derived files exist"
make_sandbox
echo '{}' > "$SANDBOX/.claude/radioheader/project-registry.json"
echo 'digest' > "$SANDBOX/.claude/radioheader/context-digest.md"
bash "$LOADER" >/dev/null 2>&1
drain_bg
check "no consolidate call" test ! -s "$CALL_LOG"

# ============================================================
echo "[3] gating: env RADIOHEADER_AUTO_DIGEST=0 disables self-heal"
make_sandbox
export RADIOHEADER_AUTO_DIGEST=0
bash "$LOADER" >/dev/null 2>&1
drain_bg
check "env off → no consolidate call" test ! -s "$CALL_LOG"
unset RADIOHEADER_AUTO_DIGEST

# ============================================================
echo "[4] gating: config.json auto_digest:false disables self-heal"
make_sandbox
echo '{"auto_digest": false}' > "$SANDBOX/.claude/radioheader/config.json"
bash "$LOADER" >/dev/null 2>&1
drain_bg
check "config false → no consolidate call" test ! -s "$CALL_LOG"

# ============================================================
echo "[5] memory-sync: 5th memory write runs consolidate --native (radiomind_auto off)"
make_sandbox
echo "4" > "$SANDBOX/.claude/radioheader/.consolidate-counter"
echo '{"tool_input":{"file_path":"/proj/memory/note.md"}}' \
  | bash "$MEMSYNC" >/dev/null 2>&1
wait_for_call
check "invokes consolidate --native" grep -q "consolidate --native" "$CALL_LOG"
check "does not use RadioMind-delegating path" bash -c "! grep -qx 'consolidate' '$CALL_LOG'"
check "counter reset to 0" bash -c "[ \"\$(cat '$SANDBOX/.claude/radioheader/.consolidate-counter')\" = 0 ]"

# ============================================================
echo "[6] memory-sync: below threshold only increments counter"
make_sandbox
echo "2" > "$SANDBOX/.claude/radioheader/.consolidate-counter"
echo '{"tool_input":{"file_path":"/proj/memory/note.md"}}' \
  | bash "$MEMSYNC" >/dev/null 2>&1
drain_bg
check "no consolidate call" test ! -s "$CALL_LOG"
check "counter incremented to 3" bash -c "[ \"\$(cat '$SANDBOX/.claude/radioheader/.consolidate-counter')\" = 3 ]"

# ============================================================
echo "[7] memory-sync: auto_digest off + radiomind_auto off → fully inert"
make_sandbox
export RADIOHEADER_AUTO_DIGEST=0
echo "4" > "$SANDBOX/.claude/radioheader/.consolidate-counter"
echo '{"tool_input":{"file_path":"/proj/memory/note.md"}}' \
  | bash "$MEMSYNC" >/dev/null 2>&1
drain_bg
check "no consolidate call" test ! -s "$CALL_LOG"
check "counter untouched" bash -c "[ \"\$(cat '$SANDBOX/.claude/radioheader/.consolidate-counter')\" = 4 ]"
unset RADIOHEADER_AUTO_DIGEST

# ============================================================
export HOME="$REAL_HOME"
echo ""
echo "Result: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
