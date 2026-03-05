# How RadioHeader Works

## Overview

RadioHeader is a behavioral framework, not a database. It works by:

1. Injecting mandatory behavioral rules into Claude Code's global `CLAUDE.md`
2. Using session hooks to provide context at startup
3. Relying on Claude Code's existing `Grep` tool for search

There is no daemon, no API, no external service. Everything runs through Claude Code's native hook system and file-based configuration.

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

**Global CLAUDE.md rules** (`~/.claude/CLAUDE.md`)

The core of RadioHeader. Appended between `# --- RadioHeader START ---` and `# --- RadioHeader END ---` markers. Contains:

- Memory reflux rules (when and how to write experience back)
- Three-step behavioral mandate (Search → Apply → Trace)
- New project onboarding flow
- Prohibition on finding but not using results

**Session hooks** (`~/.claude/hooks/`)

Two hooks fire at every session start:

1. `radioheader-loader.sh` — Prints topic file count and search instructions
2. `check-project-architecture.sh` — Checks if the current project has the dynamic experience framework configured; if not, prompts the agent to ask the user

**Topic files** (`~/.claude/radioheader/topics/*.md`)

Plain Markdown files organized by technology or domain. Each entry is one line:

```
- [source:ProjectName] symptom description — root cause. Fix: solution
```

**Index and registry**

- `INDEX.md` — Lists all topic files with entry counts
- `project-registry.md` — Maps project names to paths and tech stacks

### Per-Project Structure

When the dynamic experience framework is enabled for a project:

```
project/
├── .claude/
│   ├── settings.json              # Project-level SessionStart + Stop hooks
│   ├── hooks/
│   │   └── load-project-rules.sh  # Startup message
│   └── rules/
│       ├── memory-reflux.md       # Dual reflux rules (project + global)
│       ├── logs-writing.md        # Log writing rules
│       └── information-lookup.md  # Five-step search strategy
├── CLAUDE.md                      # Project entry point
└── {doc-dir}/
    ├── 00_AGENT_RULES.md
    ├── 01_PROJECT_OVERVIEW.md
    └── logs/
```

The `information-lookup.md` rule enforces a search hierarchy:

1. Check already-loaded context (MEMORY.md, rules/)
2. Consult CLAUDE.md document index
3. Use Grep/Glob for targeted search
4. Read matched files
5. Use Explore agent (last resort only)

## Behavioral Design

### Why "MUST" Rules Work

Claude Code's CLAUDE.md is loaded as system-level instructions. Content phrased as behavioral mandates ("you MUST search") is treated as imperative by the model. Content phrased as information ("experience is stored here") is treated as optional background.

RadioHeader uses imperative phrasing throughout:

- "MUST search RadioHeader first"
- "MUST explicitly cite it in your response"
- "PROHIBITED: Finding relevant experience but not citing or applying it"

### The Search → Apply → Trace Pattern

This three-step pattern was developed after discovering that Claude would search RadioHeader, find results, and then ignore them entirely:

**Step 1 — Search**: Use `Grep` with multiple synonymous keywords against `~/.claude/radioheader/topics/`. Multiple keywords increase hit rate (e.g., "white screen|slow launch|loading|startup").

**Step 2 — Apply**: If relevant entries are found, cite them explicitly ("RadioHeader has experience from {source}: {summary}"). Check each match for applicability. If an entry points to a solution, verify it before doing independent analysis.

**Step 3 — Trace**: If more detail is needed, look up the source project in `project-registry.md` and read its `memory/` directory for full context.

### Experience Reflux

After completing a task series (bug fix, feature, deployment), the agent checks:

1. Did this produce new experience?
2. Project-level: Write to `memory/` topic files
3. Global-level: Is this useful across projects? If yes → write to RadioHeader topics with `[source:ProjectName]` tag
4. Replace outdated entries, don't append endlessly

The Stop hook provides a reminder: "Check if new experience should flow to memory/".

## What RadioHeader Does NOT Do

- **No automatic extraction**: Experience is written by Claude during sessions, not batch-processed
- **No deduplication**: You manage topic files manually or let Claude maintain them
- **No version control**: Topic files are plain text; use git if you want history
- **No cloud sync**: Everything is local to `~/.claude/`
- **No model fine-tuning**: RadioHeader works through prompting and behavioral rules, not training
