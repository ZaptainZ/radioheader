#!/bin/bash
# e2e for `radioheader device-sync` v2 (multi-machine reconcile engine).
# Simulates two machines with two fake HOMEs and a file:// bare vault:
# init / join / union convergence / exclusions / v1 upgrade / locks / off.
# No network, no real ~/.claude touched. Run: bash tests/test_device_sync.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$SCRIPT_DIR/radioheader"

PASS=0
FAIL=0
t_ok()   { PASS=$((PASS + 1)); echo "  ok  - $1"; }
t_fail() { FAIL=$((FAIL + 1)); echo "  FAIL- $1"; }
check()  { if eval "$2"; then t_ok "$1"; else t_fail "$1"; fi; }

WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
VAULT="$WORK/vault.git"
HOME_A="$WORK/home-a"
HOME_B="$WORK/home-b"

git init --bare --quiet "$VAULT"

mk_home() {
  local h="$1"
  mkdir -p "$h/.claude/radioheader/topics" "$h/.claude/radioheader/shortwave" "$h/.claude/hooks"
}

# Run the CLI / hook as if on a given machine. UI language pinned to English
# so output assertions are deterministic regardless of the host locale.
rh()   { local h="$1"; shift; HOME="$h" RADIOHEADER_LANG=en "$CLI" "$@" < /dev/null; }
hook() { local h="$1"; shift; HOME="$h" "$h/.claude/hooks/radioheader-git-sync.sh" "$@"; }

echo "== machine A: init =="
mk_home "$HOME_A"
printf '# t\n- base line\n' > "$HOME_A/.claude/radioheader/topics/t.md"
printf 'sqlite-junk' > "$HOME_A/.claude/radioheader/search.db"
printf '{"projects": []}\n' > "$HOME_A/.claude/radioheader/project-registry.json"

rh "$HOME_A" device-sync init --remote "file://$VAULT" > "$WORK/init-a.log" 2>&1
check "init exits 0"                        "[ $? -eq 0 ]"
check "repo created"                        "[ -d '$HOME_A/.claude/radioheader/.git' ]"
check "hook script installed + executable"  "[ -x '$HOME_A/.claude/hooks/radioheader-git-sync.sh' ]"
check "hook script parses (bash -n)"        "bash -n '$HOME_A/.claude/hooks/radioheader-git-sync.sh'"
check "SessionStart pull registered"        "grep -q 'radioheader-git-sync.sh pull' '$HOME_A/.claude/settings.json'"
check "Stop push registered"                "grep -q 'radioheader-git-sync.sh push' '$HOME_A/.claude/settings.json'"
check "settings.json is valid JSON"         "python3 -c 'import json;json.load(open(\"$HOME_A/.claude/settings.json\"))'"
check "device_sync_enabled=true"            "grep -q '\"device_sync_enabled\": true' '$HOME_A/.claude/radioheader/config.json'"
check "pull.rebase=false"                   "[ \"\$(git -C '$HOME_A/.claude/radioheader' config pull.rebase)\" = false ]"
check "vault received initial push"         "git -C '$VAULT' rev-parse HEAD >/dev/null 2>&1"
check "search.db not tracked"               "! git -C '$HOME_A/.claude/radioheader' ls-files | grep -q search.db"
check "project-registry.json not tracked"   "! git -C '$HOME_A/.claude/radioheader' ls-files | grep -q project-registry.json"
check "identity fallback lets commits work" "git -C '$HOME_A/.claude/radioheader' log -1 >/dev/null 2>&1"

echo "== machine B: join (with pre-existing local data) =="
mk_home "$HOME_B"
printf '# local B knowledge\n' > "$HOME_B/.claude/radioheader/topics/local-b.md"

rh "$HOME_B" device-sync join "file://$VAULT" > "$WORK/join-b.log" 2>&1
check "join exits 0"                     "[ $? -eq 0 ]"
check "vault file arrived on B"          "grep -q 'base line' '$HOME_B/.claude/radioheader/topics/t.md'"
check "B-local file survived join"       "[ -f '$HOME_B/.claude/radioheader/topics/local-b.md' ]"
check "B-local file reached the vault"   "git -C '$VAULT' ls-tree -r --name-only HEAD | grep -q topics/local-b.md"
check "hooks registered on B"            "grep -q 'radioheader-git-sync.sh' '$HOME_B/.claude/settings.json'"

echo "== divergent edits converge via union merge =="
printf -- '- line from A\n' >> "$HOME_A/.claude/radioheader/topics/t.md"
hook "$HOME_A" push
printf -- '- line from B\n' >> "$HOME_B/.claude/radioheader/topics/t.md"
hook "$HOME_B" push
hook "$HOME_A" push
check "A has its own line"   "grep -q 'line from A' '$HOME_A/.claude/radioheader/topics/t.md'"
check "A got B's line"       "grep -q 'line from B' '$HOME_A/.claude/radioheader/topics/t.md'"
check "B has its own line"   "grep -q 'line from B' '$HOME_B/.claude/radioheader/topics/t.md'"
check "B got A's line"       "grep -q 'line from A' '$HOME_B/.claude/radioheader/topics/t.md'"
check "no diverged marker"   "[ ! -f '$HOME_A/.claude/radioheader/.sync-diverged' ]"

echo "== fresh lock skips, stale lock self-clears =="
printf -- '- lock test line\n' >> "$HOME_A/.claude/radioheader/topics/t.md"
mkdir "$HOME_A/.claude/radioheader/.sync.lock"
hook "$HOME_A" push
check "fresh lock: sync skipped"  "git -C '$HOME_A/.claude/radioheader' status --porcelain | grep -q t.md"
touch -t 202601010000 "$HOME_A/.claude/radioheader/.sync.lock"
hook "$HOME_A" push
check "stale lock: sync ran"      "! git -C '$HOME_A/.claude/radioheader' status --porcelain | grep -q t.md"
check "stale lock: lock released" "[ ! -d '$HOME_A/.claude/radioheader/.sync.lock' ]"

echo "== v1 repo upgrade untracks now-ignored files =="
HOME_C="$WORK/home-c"
VAULT2="$WORK/vault2.git"
git init --bare --quiet "$VAULT2"
mk_home "$HOME_C"
printf 'old knowledge\n' > "$HOME_C/.claude/radioheader/topics/old.md"
printf 'sqlite-junk' > "$HOME_C/.claude/radioheader/search.db"
(
  cd "$HOME_C/.claude/radioheader"
  git init --quiet
  git config user.email v1@test && git config user.name v1
  git add -A && git commit -qm "v1 state"
)
check "precondition: v1 tracked search.db" "git -C '$HOME_C/.claude/radioheader' ls-files | grep -q search.db"
rh "$HOME_C" device-sync init --remote "file://$VAULT2" > "$WORK/init-c.log" 2>&1
check "upgrade untracked search.db"        "! git -C '$HOME_C/.claude/radioheader' ls-files | grep -q search.db"
check "search.db still on disk"            "[ -f '$HOME_C/.claude/radioheader/search.db' ]"
check "knowledge stayed tracked"           "git -C '$HOME_C/.claude/radioheader' ls-files | grep -q topics/old.md"

echo "== off: hooks unregistered, repo kept, hook inert =="
rh "$HOME_A" device-sync off > /dev/null 2>&1
check "off exits 0"                  "[ $? -eq 0 ]"
check "hooks removed from settings"  "! grep -q 'radioheader-git-sync.sh' '$HOME_A/.claude/settings.json'"
check "settings still valid JSON"    "python3 -c 'import json;json.load(open(\"$HOME_A/.claude/settings.json\"))'"
check "repo kept"                    "[ -d '$HOME_A/.claude/radioheader/.git' ]"
BEFORE_OFF=$(git -C "$VAULT" rev-parse HEAD)
printf -- '- after off\n' >> "$HOME_A/.claude/radioheader/topics/t.md"
hook "$HOME_A" push
check "disabled hook is a no-op"     "[ \"\$(git -C '$VAULT' rev-parse HEAD)\" = '$BEFORE_OFF' ]"

echo "== Phase B: encrypted project memories (git-crypt) =="
if ! command -v git-crypt >/dev/null 2>&1; then
  echo "  (git-crypt not installed — skipping encrypted-memory tests)"
else
  HOME_D="$WORK/home-d"
  HOME_E="$WORK/home-e"
  HOME_F="$WORK/home-f"
  VAULT3="$WORK/vault3.git"
  git init --bare --quiet "$VAULT3"

  # machine E simulates a different login via the test-only RH_SYNC_USER override
  rhE()   { HOME="$HOME_E" RH_SYNC_USER=eve RADIOHEADER_LANG=en "$CLI" "$@" < /dev/null; }
  hookE() { HOME="$HOME_E" RH_SYNC_USER=eve "$HOME_E/.claude/hooks/radioheader-git-sync.sh" "$@"; }

  mk_home "$HOME_D"
  MEM_D="$HOME_D/.claude/projects/-Users-$(whoami)-ProjX/memory"
  mkdir -p "$MEM_D"
  printf 'TOPSECRET-CANARY-9137\n' > "$MEM_D/creds.md"
  printf '# knowledge\n' > "$HOME_D/.claude/radioheader/topics/k.md"

  rh "$HOME_D" device-sync init --remote "file://$VAULT3" > "$WORK/init-d.log" 2>&1
  rh "$HOME_D" device-sync encrypt > "$WORK/encrypt-d.log" 2>&1
  check "encrypt exits 0"                "[ $? -eq 0 ]"
  rh "$HOME_D" device-sync key export "$WORK/vault3.key" > /dev/null 2>&1
  check "key export produced a key"      "[ -s '$WORK/vault3.key' ]"

  hook "$HOME_D" push
  PM_D="$HOME_D/.claude/radioheader/project-memories/-HOME-ProjX"
  check "memory collected into staging"  "grep -q CANARY '$PM_D/creds.md'"
  check "vault blob is GITCRYPT cipher"  "git -C '$VAULT3' cat-file blob HEAD:project-memories/-HOME-ProjX/creds.md | head -c 16 | LC_ALL=C grep -aq GITCRYPT"
  check "no plaintext canary in vault"   "! git -C '$VAULT3' cat-file blob HEAD:project-memories/-HOME-ProjX/creds.md | LC_ALL=C grep -aq CANARY"
  check ".sync-pm-seen stays untracked"  "! git -C '$HOME_D/.claude/radioheader' ls-files | grep -q .sync-pm-seen"
  check "doctor verifies ciphertext"     "HOME='$HOME_D' '$CLI' doctor 2>/dev/null | grep -q 'ciphertext verified'"

  echo "-- machine E joins with the key (different username) --"
  mk_home "$HOME_E"
  rhE device-sync join "file://$VAULT3" --key "$WORK/vault3.key" > "$WORK/join-e.log" 2>&1
  check "join --key exits 0"             "[ $? -eq 0 ]"
  check "memory decrypted to eve's dir"  "grep -q CANARY '$HOME_E/.claude/projects/-Users-eve-ProjX/memory/creds.md'"

  echo "-- deletion propagates via tombstone --"
  rm "$MEM_D/creds.md"
  hook "$HOME_D" push
  check "tombstone written on D"         "[ -f '$PM_D/creds.md.tombstone' ]"
  check "staging copy gone on D"         "[ ! -f '$PM_D/creds.md' ]"
  hookE push
  check "deletion reached E's memory"    "[ ! -f '$HOME_E/.claude/projects/-Users-eve-ProjX/memory/creds.md' ]"

  echo "-- recreation after deletion wins --"
  sleep 1
  printf 'RECREATED-CONTENT-5561\n' > "$HOME_E/.claude/projects/-Users-eve-ProjX/memory/creds.md"
  hookE push
  check "tombstone consumed on E"        "[ ! -f '$HOME_E/.claude/radioheader/project-memories/-HOME-ProjX/creds.md.tombstone' ]"
  hook "$HOME_D" push
  check "D got the recreated file back"  "grep -q RECREATED '$MEM_D/creds.md'"
  check "recreated file cipher in vault" "! git -C '$VAULT3' cat-file blob HEAD:project-memories/-HOME-ProjX/creds.md | LC_ALL=C grep -aq RECREATED"

  echo "-- keyless machine can never leak plaintext --"
  mk_home "$HOME_F"
  MEM_F="$HOME_F/.claude/projects/-Users-$(whoami)-ProjF/memory"
  mkdir -p "$MEM_F"
  printf 'F-SECRET-CANARY\n' > "$MEM_F/fsecret.md"
  rh "$HOME_F" device-sync join "file://$VAULT3" > "$WORK/join-f.log" 2>&1
  hook "$HOME_F" push
  check "keyless machine staged nothing" "! git -C '$VAULT3' ls-tree -r --name-only HEAD | grep -q ProjF"
  check "keyless knowledge still syncs"  "grep -q knowledge '$HOME_F/.claude/radioheader/topics/k.md'"
  check "keyless join kept vault memories" "git -C '$VAULT3' ls-tree -r --name-only HEAD | grep -q 'ProjX/creds.md'"

  echo "== Phase C: pairing (pair export / join --pair) =="

  echo "-- plain pair file (AirDrop channel) --"
  rh "$HOME_D" device-sync pair export --file "$WORK/pair.rhpair" > /dev/null 2>&1
  check "pair export exits 0"            "[ $? -eq 0 ]"
  check "pair file has vault URL"        "grep -q '^remote=file://' '$WORK/pair.rhpair'"
  check "pair file carries the key"      "grep -q '^key_b64=' '$WORK/pair.rhpair'"

  HOME_G="$WORK/home-g"
  mk_home "$HOME_G"
  rh "$HOME_G" device-sync join --pair "$WORK/pair.rhpair" > "$WORK/join-g.log" 2>&1
  check "join --pair exits 0"            "[ $? -eq 0 ]"
  check "G got knowledge base"           "grep -q knowledge '$HOME_G/.claude/radioheader/topics/k.md'"
  check "G got decrypted memory"         "grep -q RECREATED '$HOME_G/.claude/projects/-Users-$(whoami)-ProjX/memory/creds.md'"
  check "G is fully enabled"             "grep -q '\"device_sync_project_memories\": true' '$HOME_G/.claude/radioheader/config.json'"

  echo "-- iCloud channel (passphrase-encrypted bundle) --"
  RH_PAIR_PASSPHRASE=test-pass-123 rh "$HOME_D" device-sync pair export --icloud > /dev/null 2>&1
  check "icloud export exits 0"          "[ $? -eq 0 ]"
  ICF_D="$HOME_D/Library/Mobile Documents/com~apple~CloudDocs/RadioHeader/pairing.rhpair"
  check "icloud bundle written"          "[ -s '$ICF_D' ]"
  check "bundle has encrypted header"    "head -1 '$ICF_D' | grep -q 'PAIR-V1-ENC'"
  check "no plaintext key in bundle"     "! grep -q 'key_b64=' '$ICF_D'"
  check "no plaintext URL in bundle"     "! grep -q '^remote=' '$ICF_D'"

  HOME_H="$WORK/home-h"
  mk_home "$HOME_H"
  ICH="$HOME_H/Library/Mobile Documents/com~apple~CloudDocs/RadioHeader"
  mkdir -p "$ICH"
  cp "$ICF_D" "$ICH/pairing.rhpair"      # simulate iCloud syncing the bundle over
  RH_PAIR_PASSPHRASE=test-pass-123 rh "$HOME_H" device-sync join --pair "$ICH/pairing.rhpair" > "$WORK/join-h.log" 2>&1
  check "join via icloud bundle"         "[ $? -eq 0 ]"
  check "H got decrypted memory"         "grep -q RECREATED '$HOME_H/.claude/projects/-Users-$(whoami)-ProjX/memory/creds.md'"
  check "icloud bundle single-use"       "[ ! -f '$ICH/pairing.rhpair' ]"

  echo "-- wrong passphrase fails safely --"
  HOME_I="$WORK/home-i"
  mk_home "$HOME_I"
  cp "$ICF_D" "$WORK/stale.rhpair"
  RH_PAIR_PASSPHRASE=WRONG-PASS rh "$HOME_I" device-sync join --pair "$WORK/stale.rhpair" > /dev/null 2>&1
  check "wrong passphrase rejected"      "[ $? -ne 0 ]"
  check "no repo created on failure"     "[ ! -d '$HOME_I/.claude/radioheader/.git' ]"

  echo "-- setup wizard guards --"
  rh "$HOME_I" device-sync setup > "$WORK/setup.log" 2>&1
  check "setup without tty exits 1"      "[ $? -ne 0 ]"
  check "setup points to manual cmds"    "grep -q 'join <url>' '$WORK/setup.log'"
fi

echo "== bilingual UI (RADIOHEADER_LANG / locale detection) =="
check "zh status has Chinese labels" "HOME='$HOME_A' RADIOHEADER_LANG=zh '$CLI' device-sync status | grep -q '多机同步状态'"
check "zh help screen"               "HOME='$HOME_A' RADIOHEADER_LANG=zh '$CLI' device-sync --help | grep -q '工作原理'"
check "locale zh_CN auto-detected"   "HOME='$HOME_A' RADIOHEADER_LANG= LC_ALL= LC_MESSAGES= LANG=zh_CN.UTF-8 '$CLI' device-sync status | grep -q '启用'"
check "en output stays English"      "HOME='$HOME_A' RADIOHEADER_LANG=en '$CLI' device-sync status | grep -q 'Device Sync Status'"
check "en output has no Chinese"     "! HOME='$HOME_A' RADIOHEADER_LANG=en '$CLI' device-sync status | grep -q '启用'"

echo ""
echo "== $PASS passed, $FAIL failed =="
[ "$FAIL" -eq 0 ]
