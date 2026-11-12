# How RadioHeader Works

## Overview

RadioHeader is a behavioral framework, not a database. It works by:

1. Injecting mandatory behavioral rules into the runtime entry file (`CLAUDE.md` for Claude, `AGENTS.md` for Codex)
2. Using runtime hooks to provide context and reinforcement during the session lifecycle
3. Relying on the agent's existing search tools (`Grep`, `Glob`, etc.) against plain files

There is no daemon, no API, no external service. Everything runs through the agent runtime's native hook system and file-based configuration.

## Architecture

### Three-Layer Memory Model

```
Layer 1: RadioHeader (global)
  ~/.claude/radioheader/topics/*.md
  Cross-project experience, shared by all projects
  Entries tagged with [source:ProjectName]

Layer 2: Project Memory (per-project)
  ~/.claude/projects/{project-hash}/memory/
  Project-specific context and decisions
  Auto-loaded MEMORY.md (first 200 lines)

Layer 3: Session Context (ephemeral)
  Current conversation only
  Lost when the session ends
```

Each layer has a different scope and lifetime. RadioHeader occupies the top layer — it persists across all projects and all sessions.

### Components

**Global runtime rules**

- Claude: `~/.claude/CLAUDE.md`
- Codex: `~/.codex/AGENTS.md`

The core of RadioHeader. Appended between `# --- RadioHeader START ---` and `# --- RadioHeader END ---` markers. Contains:

- Echo rules (when and how to write experience back)
- Three-step behavioral mandate (Search → Apply → Trace)
- New project onboarding flow
- Prohibition on finding but not using results

**Shared hook scripts** (`~/.claude/hooks/`)

Claude and Codex both point to the same shared hook script directory, but they trigger different events:

- `check-project-architecture.sh` — checks if the current project has the dynamic experience framework configured
- `radioheader-loader.sh` — prints topic counts and context-digest info
- `radioheader-memory-sync.sh` — Claude-only `PostToolUse Write|Edit` Echo trigger
- `radioheader-error-capture.sh` — Bash error capture
- `radioheader-codex-userprompt.py` — Codex `UserPromptSubmit` snapshot
- `radioheader-stop-echo.sh` — Claude Stop reminder
- `radioheader-stop-codex.py` — Codex Stop compensation and reminders

**Topic files** (`~/.claude/radioheader/topics/*.md`)

Plain Markdown files organized by technology or domain. Each entry is one line:

```
- [source:ProjectName] symptom description — root cause. Fix: solution
```

**Index and registry**

- `INDEX.md` — Lists all topic files with entry counts
- `project-registry.json` — Machine-local source of truth for project paths and metadata; `.project-registry.backup.json` is a validated recovery copy, never synced. Missing source without a valid backup is an error, not an empty registry.
- `project-registry.md` — Human-readable projection generated from the JSON registry

### Per-Project Structure

When the dynamic experience framework is enabled for a project:

```
project/
├── .claude/
│   ├── settings.json              # Claude project hooks
│   ├── hooks/
│   │   └── load-project-rules.sh  # Startup message
│   └── rules/
│       ├── memory-echo.md         # Echo rules (project + global)
│       ├── logs-writing.md        # Log writing rules
│       └── information-lookup.md  # Five-step search strategy
├── .codex/
│   ├── hooks.json                 # Codex project hooks
│   └── hooks/
│       ├── load-project-rules.sh  # Startup reminder
│       └── stop-reminder.py       # Project-level Stop reminder
├── CLAUDE.md                      # Claude project entry point
├── AGENTS.md                      # Codex project entry point
└── {doc-dir}/
    ├── 00_AGENT_RULES.md
    ├── 01_PROJECT_OVERVIEW.md
    └── logs/
```

The `information-lookup.md` rule enforces a search hierarchy:

1. Check already-loaded context (MEMORY.md, rules/)
2. Consult the project document index (`CLAUDE.md` / `AGENTS.md`)
3. Use Grep/Glob for targeted search
4. Read matched files
5. Use Explore agent (last resort only)

## Behavioral Design

### Why "MUST" Rules Work

The runtime instruction file is loaded as high-priority guidance. Content phrased as behavioral mandates ("you MUST search") is treated as imperative by the model. Content phrased as information ("experience is stored here") is treated as optional background.

RadioHeader uses imperative phrasing throughout:

- "MUST search RadioHeader first"
- "MUST explicitly cite it in your response"
- "PROHIBITED: Finding relevant experience but not citing or applying it"

### The Search → Apply → Trace Pattern

This three-step pattern was developed after discovering that Claude would search RadioHeader, find results, and then ignore them entirely:

**Step 1 — Search**: Use `Grep` with multiple synonymous keywords against `~/.claude/radioheader/topics/` and `shortwave/`. Multiple keywords increase hit rate (e.g., "white screen|slow launch|loading|startup").

**Step 2 — Apply**: If relevant entries are found, cite them explicitly ("RadioHeader has experience from {source}: {summary}"). Check each match for applicability. If an entry points to a solution, verify it before doing independent analysis.

**Step 3 — Trace**: If more detail is needed, look up the source project in `project-registry.json` / `project-registry.md` and read its `memory/` directory for full context.

### Echo (Experience Flows Back)

After completing a task series (bug fix, feature, deployment), the agent checks:

1. Did this produce new experience?
2. Project-level: Write to `memory/` topic files
3. Global-level: Is this useful across projects? If yes → write to RadioHeader topics with `[source:ProjectName]` tag
4. Replace outdated entries, don't append endlessly

The Stop hook provides a reminder: "Check if new experience should echo back to memory/".

In Claude, this reminder is a plain Stop message. In Codex, the Stop hook can also inspect the current turn and continue the loop if `memory -> topics -> shortwave` is incomplete.

## What RadioHeader Does NOT Do

- **No automatic extraction**: Experience is written by Claude during sessions, not batch-processed
- **No separate Codex datastore**: Claude and Codex share the same `~/.claude/radioheader/` data layer
- **No deduplication**: You manage topic files manually or let Claude maintain them
- **No version control**: Topic files are plain text; use git if you want history
- **No mandatory cloud sync**: Everything works locally under `~/.claude/` and runtime config files
- **No model fine-tuning**: RadioHeader works through prompting and behavioral rules, not training

### Codex digest refresh and runtime verification

Codex counts turns with actual changes to project memory, global topics, or shortwave entries. Every five changed turns the Stop adapter starts consolidation; Claude counts five matching Write/Edit events instead. The counters are deliberately separate because their events have different granularity. Codex protects its counter with a file lock, consumes each snapshot once, and refreshes before an Echo continuation. The default command is `consolidate --native`; only explicit `radiomind_auto` opt-in permits delegation. `auto_digest: false` or `RADIOHEADER_AUTO_DIGEST=0` disables the native automation. Failures from the background process are recorded in `.codex-consolidate.log`.

Reinstalling refreshes generated device-sync adapters and local ignore metadata via `device-sync refresh`. This operation does not contact the remote or enable disabled sync. The next normal sync handles updated metadata.

Codex requires review of new or changed hook definitions through `/hooks`; installing hook files alone does not establish trust. Current Codex also supports `apply_patch` PostToolUse events, but the snapshot adapter continues to cover file edits regardless of tool choice. See [official Codex hooks documentation](https://learn.chatgpt.com/docs/hooks). Regression tests exercise protocol fixtures; real-client acceptance must separately verify that hooks actually run and that model authentication is available.

### Kimi Code adapter (2.5)

Kimi reuses the snapshot engine with its own state directory and consolidation counter. Its prompt hook returns a `message`; its Stop hook requests continuation through exit code 2 and stderr. Global TOML hooks are managed without replacing user model/provider settings. `SessionEnd` flushes compensation writes because Kimi 2.3.3 does not repeat Stop after continuation. See [Kimi Code integration](kimi-code.md) for setup, lifecycle and compatibility boundaries.
