# RadioHeader

**Cross-project experience sharing for Claude Code.**

RadioHeader gives Claude Code a persistent memory layer that works across all your projects. When you solve a tricky bug in Project A, that experience automatically becomes available in Project B, C, and every future project.

## The Problem

Claude Code's memory is isolated per project. You fix a SwiftUI NavigationStack bug in one app, then hit the exact same issue three months later in another app — and Claude starts from scratch.

RadioHeader solves this by creating a shared experience hub that Claude searches before analyzing any technical problem.

## How It Works

```
┌─────────────────────────────────────────────────┐
│                  RadioHeader                     │
│          ~/.claude/radioheader/topics/            │
│                                                  │
│  ios-swiftui.md  ·  rust-systems.md  ·  ...     │
│  [source:AppA] NavigationStack nested bug...     │
│  [source:AppB] Swift concurrency pitfall...      │
└────────────────────┬────────────────────────────┘
                     │
        ┌────────────┼────────────────┐
        ▼            ▼                ▼
   ┌─────────┐ ┌─────────┐     ┌─────────┐
   │Project A│ │Project B│     │Project N│
   │ memory/ │ │ memory/ │     │ memory/ │
   └─────────┘ └─────────┘     └─────────┘
```

**Three-layer memory model:**

1. **RadioHeader** (global) — cross-project experience, shared by all projects
2. **Project memory** (`~/.claude/projects/*/memory/`) — project-specific context
3. **Session context** — ephemeral, within one conversation

**Behavioral rules — Search, Apply, Trace:**

1. **Search**: When facing a technical problem, Claude searches RadioHeader first
2. **Apply**: If relevant experience is found, Claude cites and applies it
3. **Trace**: If more detail is needed, Claude traces back to the source project's memory

This isn't optional — RadioHeader injects mandatory behavioral rules into Claude's CLAUDE.md, so the agent **must** search, apply, and trace. Finding experience but not using it is explicitly prohibited.

## Installation

### Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed (`~/.claude/` directory exists)
- `jq` recommended for automatic settings.json merging (install: `brew install jq` / `apt install jq`)

### Install

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh
```

The installer:
- Creates `~/.claude/radioheader/` with index and registry files
- Installs two session hooks into `~/.claude/hooks/`
- Appends RadioHeader behavioral rules to `~/.claude/CLAUDE.md`
- Merges hooks into `~/.claude/settings.json`
- Creates timestamped backups of all modified files

### Uninstall

```bash
cd radioheader
./uninstall.sh
```

The uninstaller removes all RadioHeader components. If you have topic files, it will ask before deleting them.

## Usage

### Automatic (just work normally)

After installation, RadioHeader works automatically:

1. **Session start**: A hook fires showing "RadioHeader ready (N topic files)"
2. **New project detection**: If a project hasn't been configured, Claude asks if you want to enable the dynamic experience framework
3. **Problem solving**: When you hit a technical issue, Claude searches RadioHeader before investigating
4. **Experience reflux**: After completing a task series, Claude checks if new experience should flow back to RadioHeader

### Writing Experience Entries

Experience accumulates naturally as you work. Entries are written to topic files under `~/.claude/radioheader/topics/` in this format:

```markdown
- [source:MyApp] `Task {}` in SwiftUI `.onAppear` inherits Main Actor —
  iCloud I/O blocks main thread, causing 10s+ white screen (slow launch /
  startup delay). Fix: use `Task.detached(priority:)`
```

**Key principles:**

- Keep **symptom keywords** ("white screen", "slow launch", "10s+") — users search by symptoms
- Include **quantified data** ("20-40s" not just "slow")
- Add **synonyms** in parentheses for search discoverability
- Tag **source project** `[source:Name]` for traceability
- One experience per line — concise but complete

See [`examples/topics/`](examples/topics/) for a full example.

### Per-Project Setup

When you open a project for the first time after installing RadioHeader, Claude will offer to set up the dynamic experience framework. This creates:

```
your-project/
├── .claude/
│   ├── settings.json         # Project-level hooks
│   ├── hooks/
│   │   └── load-project-rules.sh
│   └── rules/
│       ├── memory-reflux.md  # Experience reflux rules
│       ├── logs-writing.md   # Log writing rules
│       └── information-lookup.md  # Search strategy
├── CLAUDE.md                 # Project entry point
└── {doc-dir}/
    ├── 00_AGENT_RULES.md
    ├── 01_PROJECT_OVERVIEW.md
    └── logs/
```

## Architecture

### Files Installed

| Path | Purpose |
|------|---------|
| `~/.claude/radioheader/INDEX.md` | Master index of all topic files |
| `~/.claude/radioheader/project-registry.md` | Registry of all projects (name, stack, path) |
| `~/.claude/radioheader/topics/*.md` | Experience files organized by technology/domain |
| `~/.claude/hooks/radioheader-loader.sh` | Session hook: shows RadioHeader status |
| `~/.claude/hooks/check-project-architecture.sh` | Session hook: detects unconfigured projects |
| `~/.claude/CLAUDE.md` | RadioHeader rules appended between markers |

### How Experience Flows

```
You solve a bug in Project A
        │
        ▼
Claude records it in Project A's memory/
        │
        ▼
Claude checks: Is this useful cross-project?
        │  Yes
        ▼
Writes to ~/.claude/radioheader/topics/{topic}.md
  with [source:ProjectA] tag
        │
        ▼
Later, in Project B, you hit a similar issue
        │
        ▼
Claude searches RadioHeader → finds the entry
        │
        ▼
Cites it: "RadioHeader has experience from ProjectA: ..."
        │
        ▼
Applies the solution (or verifies applicability first)
```

## Lessons Learned

RadioHeader was built through real-world usage across 13 projects. Key insights:

1. **"Searched but didn't use" is the #1 failure mode.** Early versions told Claude to search RadioHeader, but the agent would search, find results, and then completely ignore them. The fix: make the behavioral rule three mandatory steps (Search → Apply → Trace) with an explicit prohibition on finding but not using.

2. **Symptom keywords matter more than solution keywords.** Developers search by symptoms ("white screen", "slow launch") not by solutions ("Task.detached"). Strip the symptoms and the entry becomes unfindable.

3. **Instructions beat knowledge.** Writing "experience is stored in RadioHeader" (informational) doesn't drive behavior. Writing "you MUST search RadioHeader first" (imperative) does. CLAUDE.md content must be behavioral instructions, not reference documentation.

4. **Bidirectional flow is essential.** One-way aggregation (project → global) creates a stale knowledge base. The reflux cycle (project → global → project) keeps experience alive and verified.

## Docs

- [How It Works](docs/how-it-works.md) — Architecture and behavioral design
- [Writing Good Entries](docs/writing-good-entries.md) — Format, keywords, and examples
- [Lessons Learned](docs/lessons-learned.md) — What we tried, what failed, what works

## License

MIT
