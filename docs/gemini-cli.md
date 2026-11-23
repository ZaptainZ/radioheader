# Gemini CLI integration

RadioHeader 2.6 adds a Gemini CLI adapter. It shares `~/.claude/radioheader/` and canonical project memory with Claude Code, Codex and Kimi Code. The compatibility baseline is Gemini CLI **0.70.0** (`@google/gemini-cli`), whose hook system is enabled by default (`hooksConfig.enabled`).

## Install and initialize

Requires Bash, Python 3 and the existing RadioHeader prerequisites. Install Gemini CLI and authenticate through its own flow first. RadioHeader does not configure auth, models or providers.

```bash
./install.sh --runtime gemini --yes --bin-dir "$HOME/bin"
# Or install all four adapters:
./install.sh --runtime all --yes --bin-dir "$HOME/bin"

cd /path/to/project
radioheader init --runtime gemini --name MyProject --stack Python
radioheader doctor
```

`both` still means Claude Code + Codex and remains the default. `all` adds Kimi Code and Gemini CLI. `init --runtime gemini` creates the project entry `GEMINI.md` (Gemini's default context file); an existing `GEMINI.md` is never overwritten. Hooks stay user-level: RadioHeader never writes a project `.gemini/settings.json`. `upgrade` reads `GEMINI.md` for project metadata and restores it if missing in a project that has a `.gemini/` directory.

Global instructions live in a managed section of `~/.gemini/GEMINI.md`. Gemini's own `save_memory` entries in the same file are kept. `GEMINI_CLI_HOME` is honoured: it replaces the home directory and Gemini appends `.gemini`. Five owned hook groups are added to `~/.gemini/settings.json`:

- Ownership is recognized by the exact adapter command, because JSON has no comments to hold markers.
- Every other key, hook group and hook entry is preserved, including user hooks that share a group.
- The helper checks that unrelated settings are semantically unchanged before writing.
- It makes a mode-0600 backup, keeps the original file mode and replaces the file atomically.
- Reinstall is idempotent.
- `settings.json` must be strict JSON. If it has comments, trailing commas or an unexpected `hooks` shape, the install fails before any runtime file changes, and the original is preserved.

Backups contain the same private settings as the original file; keep them private.

## Lifecycle

| Event | Behavior |
|---|---|
| `SessionStart` | Start opt-in device-sync pull (`startup`/`resume` only). Inject the digest, architecture reminder and project `MEMORY.md` quick reference (first 200 lines, at most 8,000 characters) through `hookSpecificOutput.additionalContext`. Interactive sessions get it as the first history turn; headless runs get it prepended to the prompt. |
| `BeforeAgent` | Snapshot memory/topics/shortwave and project changes; no output |
| `AfterAgent` | Compare the snapshot. If an Echo step is missing, return `decision: "deny"` with the reason; Gemini sends that reason back as a retry prompt. Otherwise run opt-in sync push and show the checklist as `systemMessage`. |
| `SessionEnd` | Detached, best-effort sync push (Gemini does not wait for this hook) |
| `AfterTool` (`run_shell_command`) | Record recognized error symptoms from failed commands (`Exit Code: N`) as JSON for local consolidation |

Gemini fires `BeforeAgent`/`AfterAgent` once per user prompt, not per model call, and supplies no turn id. The adapter therefore keeps one baseline per hashed session ID and project. After a deny, Gemini fires `BeforeAgent` again for the retry prompt and then `AfterAgent` with `stop_hook_active: true`. The adapter discards that second baseline and pushes sync instead of checking again, so an Echo retry never loops.

Every hook prints exactly one JSON object to stdout. Gemini treats any other stdout text as a parse failure. Diagnostics go to stderr. Unexpected errors exit 1, which Gemini treats as a non-fatal warning (fail open). Timeouts are in milliseconds.

Gemini state uses its own files: `.gemini-turn-snapshots/`, `.gemini-consolidate-counter`, `.gemini-consolidate.log` and `.gemini-sync.log`. All are excluded from device sync. Consolidation defaults to `radioheader consolidate --native` every five changed turns. The existing `auto_digest` and explicit `radiomind_auto` settings apply.

Gemini controls lifecycle delivery, approvals, folder trust and model execution. RadioHeader does not bypass permissions or change `hooksConfig`. `doctor` reports a repair if hooks are globally disabled, or if `hooksConfig.disabled` lists a RadioHeader hook. Project `.claude/rules/*.md` stay readable shared instructions; Gemini does not load Claude's rule directory automatically.

## Remove only this adapter

```bash
./uninstall.sh --runtime gemini
```

This removes the owned Gemini hooks, the managed `GEMINI.md` section and the adapter script. Other Gemini settings, shared memory, the CLI and other runtimes' engines stay. `--runtime both` and `--runtime kimi` keep shared files while Gemini is still installed. `--runtime all` is the full uninstall. Project `GEMINI.md` files are kept.

## Validation

`tests/test_gemini.py` runs without network or credentials. It covers:

- settings preservation and idempotency, user hooks in shared groups, and refusal of invalid JSON
- install, init, doctor, upgrade and partial/full uninstall
- disabled-hooks detection
- `SessionStart` injection, silent `BeforeAgent` and the `AfterAgent` deny/retry protocol
- independent consolidation, background `SessionEnd` sync, shell-failure logging and Gemini-only device sync

An end-to-end run of the real Gemini CLI 0.70.0 binary also passed. It used an isolated home and `GOOGLE_GEMINI_BASE_URL` pointed at a local fake model server, so no data left the machine. It confirmed that:

- the injected digest and project memory reach the model request
- a memory edit during the turn produces exactly one Echo retry prompt
- the retry pass ends without looping

Interactive-mode injection and real-model Echo writes were not part of that run.

Protocol references: the bundled `docs/hooks/reference.md` of Gemini CLI 0.70.0 and its hook runner implementation.
