# Kimi Code integration

RadioHeader 2.5 adds a Kimi Code 2.x adapter. It shares `~/.claude/radioheader/` and canonical project memory with Claude Code and Codex. The compatibility baseline is Kimi Code **2.3.3**; the legacy Python `kimi-cli` / `~/.kimi` configuration is not supported by this adapter.

## Install and initialize

Requires Bash, Python **3.11+** (standard-library TOML parsing), and the existing RadioHeader prerequisites. Install Kimi Code and authenticate through its own CLI first; RadioHeader does not configure providers or change your model.

```bash
./install.sh --runtime kimi --yes --bin-dir "$HOME/bin"
# Or install all three adapters:
./install.sh --runtime all --yes --bin-dir "$HOME/bin"

cd /path/to/project
radioheader init --runtime kimi --name MyProject --stack Python
radioheader doctor
kimi doctor
```

`both` still means Claude Code + Codex and remains the default. `all` adds Kimi. Re-initializing an existing project asks once and preserves existing files. Use `init --runtime kimi` to add the dedicated project entry `.kimi-code/AGENTS.md`; hooks stay user-level. `upgrade` reads that entry for project metadata and restores it if missing while retaining existing custom guidance.

Global instructions live in `$KIMI_CODE_HOME/AGENTS.md` (default `~/.kimi-code/AGENTS.md`). Five owned `[[hooks]]` entries are added to `config.toml`. Existing model/provider/service settings and unrelated hooks are retained. The configuration helper validates TOML before writing, checks that unrelated parsed values remain unchanged, makes a mode-0600 backup, and atomically replaces the file. Reinstall is idempotent, including when Kimi has reserialized the config without ownership comments. Unsupported inline `hooks = [...]` or ambiguous ownership fails with the original config preserved. Backups contain the same private settings as the original config; keep them private.

## Lifecycle

| Event | Behavior |
|---|---|
| `SessionStart` | Start opt-in device-sync pull; no context injection through this observation-only event |
| `UserPromptSubmit` | Snapshot memory/topics/shortwave and project changes; inject the digest, project `MEMORY.md` quick reference (first 200 lines, at most 8,000 characters), and architecture reminder through Kimi's `message` JSON field |
| `Stop` | Compare the snapshot; request one Echo continuation using exit code **2** and a reason on stderr; otherwise run opt-in sync push |
| `SessionEnd` | Flush opt-in sync, including changes made during an Echo continuation |
| `PostToolUseFailure` (`Bash`) | Record recognized error symptoms as JSON for local consolidation |

The shared snapshot engine also catches shell edits. Kimi 2.3.3 does not send `turn_id` with prompt/Stop hooks, so the adapter uses one baseline per session and project. Steer messages do not replace a running turn's baseline. Snapshot names hash the session ID. Kimi state and its five-changed-turn consolidation counter are separate from Codex state and excluded from device sync.

Consolidation defaults to `radioheader consolidate --native`; existing `auto_digest` and explicit `radiomind_auto` settings apply. Shared memory means search, consolidation, community commands, and encrypted device sync use the same CLI and data as the other adapters.

Kimi 2.3.3 runs Stop only once after requesting a continuation. It does not run a second verification of the compensation turn. Those later edits flush on session close or the next successful sync; a killed client may require `radioheader device-sync now`. Kimi controls lifecycle delivery, approvals and model execution. RadioHeader does not bypass permissions, execute project-provided hook scripts, install `SYSTEM.md`, or promise hooks on a remote worker: memory belongs to the machine running the Kimi hook process.

Kimi's managed `AGENTS.md` supplies memory/Echo guidance. Project `.claude/rules/*.md` remain readable shared instructions; Kimi does not automatically load Claude's rule directory. The project entry points to these rules as needed.

## Remove only this adapter

```bash
./uninstall.sh --runtime kimi
```

This removes owned Kimi hooks, its managed global instruction section and adapter script, retaining custom Kimi settings and shared memory/CLI/other runtime engines. `--runtime both` retains shared files when Kimi is still installed. `--runtime all` is the full uninstall. Project instruction files are retained.

## Validation

`tests/test_kimi.py` runs without network or credentials and covers config preservation, idempotency, reserialized config, invalid config refusal, install/init/doctor/uninstall, digest injection, steer behavior, native Stop continuation, sync ordering, independent consolidation, and safe error logging. It runs alongside the existing CC/Codex regression suites on macOS and Ubuntu.

A real Kimi Code 2.3.3 session in default permission mode also confirmed the injected digest heading, shared memory path and `kimi` log suffix, with zero tool calls. Model-written Echo continuation is covered by the isolated protocol tests, not by that read-only smoke test.

Protocol references: [Kimi hooks](https://www.kimi.com/code/docs/en/kimi-code-cli/customization/hooks.html), [configuration files](https://www.kimi.com/code/docs/en/kimi-code-cli/configuration/config-files), plus the installed 2.3.3 hook schema and lifecycle implementation. Newer documented events are deliberately not registered until supported by the compatibility baseline.
