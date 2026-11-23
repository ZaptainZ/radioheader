# Antigravity CLI integration

RadioHeader 2.7 adds an Antigravity CLI (`agy`) adapter. It shares `~/.claude/radioheader/` and canonical project memory with the other runtimes. The compatibility baseline is Antigravity CLI **1.5.14** (Homebrew cask `antigravity-cli`). Hooks run in the CLI. Per Google's forum, public IDE builds do not execute them yet, so the IDE is not covered.

## Install and initialize

Requires Bash, Python 3 and the existing RadioHeader prerequisites. Install `agy` and sign in through its own flow first. RadioHeader does not configure auth, models or providers.

```bash
./install.sh --runtime antigravity --yes --bin-dir "$HOME/bin"
# Or install every adapter:
./install.sh --runtime all --yes --bin-dir "$HOME/bin"

cd /path/to/project
radioheader init --runtime antigravity --name MyProject --stack Python
radioheader doctor
```

Antigravity CLI reads global rules from `~/.gemini/GEMINI.md`, the same file Gemini CLI uses. RadioHeader therefore writes one shared managed section, never two. Uninstalling either runtime keeps that section while the other one is still installed. Project rules come from `GEMINI.md` or `AGENTS.md` in the start folder and its parents up to the repository root; `init --runtime antigravity` creates `GEMINI.md`. Antigravity has no config-home override, so everything lives under `~/.gemini`.

Hooks go in `~/.gemini/config/hooks.json`, an object of named hooks. RadioHeader owns exactly the `radioheader` entry:

- Every other named hook is preserved.
- An existing `radioheader` entry that RadioHeader did not write is refused.
- Turning the hook off in `/hooks` (`"enabled": false`) survives a reinstall.
- Writes use a mode-0600 backup, keep the original file mode and replace the file atomically.
- Strict JSON is required.

## Lifecycle

| Event | Behavior |
|---|---|
| `SessionStart` | Start opt-in device-sync pull. Inject the digest, architecture reminder and project `MEMORY.md` quick reference (first 200 lines, at most 8,000 characters) as an `injectSteps` system message. |
| `PreInvocation` | On `invocationNum == 0` (the first model call for a user message), snapshot memory/topics/shortwave and project changes. Later calls in the same message are ignored. |
| `Stop` | Log queued shell failures. If an Echo step is missing, return `decision: "continue"` with the reason; agy re-enters the loop and shows the reason as a system message. Otherwise run opt-in sync push and return `decision: "stop"`. |
| `PostToolUse` (`run_command`) | Queue the step for failure capture |

Behavior verified against agy 1.5.14 (several parts are undocumented):

- **Input:** camelCase stdin JSON that also carries an undocumented `cwd` (the project folder). The hook process itself runs with the `hooks.json` directory as its working directory, so the adapter takes the project path from `cwd`/`workspacePaths`.
- **Counters:** `invocationNum` and `executionNum` reset for every user message. `SessionStart` does not fire again when a conversation is resumed with `-c`.
- **No loop guard from agy:** the continuation pass has `executionNum: 1`, while `continuationActive` stays `false`. The adapter keeps its own per-conversation marker and also treats `executionNum > 0` as the continuation pass, so the Echo continuation is requested at most once.
- **Failed hooks never block:** a failing hook, including exit 2, is only logged by agy (fail open). The adapter always prints exactly one JSON object.
- **Shell failures:** `PostToolUse.error` is empty for a command that exits non-zero. The exit code and output only appear in the transcript, and that step is written after `PostToolUse`. So failures are queued at `PostToolUse` and read from the transcript at `Stop`, once per step.
- **No session-end event:** sync push happens at every successful `Stop`.

Antigravity state uses its own files: `.antigravity-turn-snapshots/` (including continuation markers and queued shell steps), `.antigravity-consolidate-counter` and `.antigravity-consolidate.log`. All are excluded from device sync. Consolidation defaults to `radioheader consolidate --native` every five changed turns. `doctor` checks the hook entry, the shared rules and that the recorded Python interpreter still exists. The interpreter may differ from the current `python3`.

## Remove only this adapter

```bash
./uninstall.sh --runtime antigravity
```

This removes the `radioheader` hook entry and the adapter script, and removes the shared `GEMINI.md` section unless Gemini CLI is still installed. `--runtime all` is the full uninstall. Project `GEMINI.md` files are kept.

## Validation

`tests/test_antigravity.py` runs without network or credentials. Its payloads mirror what agy 1.5.14 actually sent. It covers:

- `hooks.json` preservation and idempotency, user disable surviving a reinstall, and refusal of a foreign entry or invalid JSON
- detection of a missing interpreter
- install, init, doctor and uninstall, including the shared rules section with Gemini CLI
- `SessionStart` injection and the per-message snapshot
- `Stop` continue-once (with and without `executionNum` advancing), fresh baselines per message, and conversation isolation
- independent consolidation, transcript-based shell-failure capture, and Antigravity-only device sync

An end-to-end run of the real agy 1.5.14 binary also passed. It used an isolated home, `modelProvider: "gemini"` with a fake key and `GOOGLE_GEMINI_BASE_URL` pointed at a local scripted model server, so no data left the machine. It confirmed that:

- the shared rules, digest and project memory reach every model request
- a memory edit during the turn produces exactly one Echo continuation
- a failed `run_command` is logged
- the run ends without hook errors

A signed-in session with a real model has not been tested.

Protocol references: [Antigravity hooks](https://antigravity.google/docs/hooks), [settings](https://antigravity.google/docs/settings), [rules](https://antigravity.google/docs/rules), plus the local runs above.
