# RadioHeader

**Cross-project memory for Claude Code.** Stop re-solving bugs you already fixed in another project.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[中文文档](README_zh.md)

## The Problem

Claude Code's memory is isolated per project. You fix a SwiftUI NavigationStack bug in one app, then hit the exact same issue three months later in another app — and Claude starts from scratch. Every solved problem stays locked inside the project where it happened.

RadioHeader creates a shared experience hub across all your projects. Claude searches it **before** analyzing any technical problem.

## What Changes

**Before** — Claude encounters a white screen bug in Project B:

```
You: App shows white screen for 10+ seconds on launch

Claude: Let me investigate... [reads files, runs debugger, checks logs]
        ... 30 minutes later ...
        Found it! Task {} in .onAppear inherits MainActor,
        blocking iCloud I/O on the main thread.
        Fix: use Task.detached(priority:)
```

**After** — Same bug, but RadioHeader is installed:

```
You: App shows white screen for 10+ seconds on launch

Claude: RadioHeader has experience from ProjectA:
        "Task {} in SwiftUI .onAppear inherits Main Actor —
        iCloud I/O blocks main thread, causing 10s+ white screen.
        Fix: use Task.detached(priority:)"

        Let me verify this applies here... ✓ Same pattern confirmed.
        Applying the fix now.
```

10 seconds instead of 30 minutes — because the experience already existed.

## Key Features

**Cross-Project Memory** — A three-layer model: RadioHeader (global, shared by all projects) → Project memory (project-specific) → Session context (ephemeral). Experience flows up from projects to the global hub, then back down to wherever it's needed.

**Search → Apply → Trace** — Not a suggestion, a mandatory behavioral rule injected into Claude's CLAUDE.md. When Claude finds relevant experience, it **must** cite and apply it. Finding experience but ignoring it is explicitly prohibited.

**Automatic Experience Reflux** — Four hooks drive the cycle automatically: SessionStart shows status, PostToolUse detects memory writes and triggers reflux checks, Stop reminds Claude to check for new experience. No manual intervention needed.

**Knowledge Distillation (Shortwave)** — Topic entries contain project-specific details (`[source:MyApp]`). Shortwave strips those details into universal, project-agnostic knowledge units — searchable across any tech stack.

## Quick Start

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh
```

That's it. Start Claude Code in any project and RadioHeader is active — hooks fire, rules are loaded, experience is searchable.

Optionally, run `radioheader init` inside a project to add per-project scaffolding (memory reflux rules, log directory, doc templates). This is not required — RadioHeader works globally without it.

## How It Works

```
RadioHeader (~/.claude/radioheader/)
├── shortwave/   ← refined, project-agnostic knowledge
├── topics/      ← detailed experience with [source:] tags
└── INDEX.md     ← master index

    ▲ reflux ║ search
    ║        ▼

Project A memory/    Project B memory/    Project N memory/
```

When you solve a bug, Claude records it in the project's memory. A PostToolUse hook fires and prompts Claude to check: *is this useful cross-project?* If yes, it flows up to `topics/` with a `[source:ProjectName]` tag, then gets distilled into a `shortwave/` entry.

Later, in a different project, Claude hits a similar issue. The **Search → Apply → Trace** rule kicks in: search RadioHeader first, cite and apply what's found, trace back to the source project if more detail is needed.

## Tips

**Manually trigger reflux.** Hooks handle most reflux automatically, but you can also tell Claude in plain language at any time:

- *"Sync project info"* — Claude updates the project overview doc and checks for global reflux
- *"Update memory"* — Claude reviews what was learned and writes to memory/topics
- *"Write a log for today's work"* — Claude creates a task log in the logs directory

This is useful after a long session, when you finish a feature, or whenever you feel recent work should be recorded before the session ends.

## CLI

| Command | Description |
|---------|-------------|
| `radioheader init` | Initialize the experience framework in your project |
| `radioheader search <query>` | Search across all topics and shortwave |
| `radioheader status` | Show topic count, entry count, registered projects |
| `radioheader doctor` | Run health checks on hooks, rules, and registry |
| `radioheader align` | Analyze topics↔shortwave coverage |
| `radioheader align --execute` | Output batch refinement instructions for Claude |
| `radioheader align --refs` | Validate and fix shortwave reference links |

```bash
# Search by symptoms, not solutions
radioheader search "white screen|slow launch|startup"

# Initialize a new project with flags
radioheader init --name "MyAPI" --stack "Python/FastAPI" --doc-dir docs
```

## Real-World Results

Built through real usage across 13 projects. Three lessons that shaped everything:

**"Searched but didn't use" — the #1 failure mode.** Early versions told Claude to search RadioHeader. It would search, find results, and completely ignore them. The fix: make it three mandatory steps (Search → Apply → Trace) with an explicit prohibition on finding but not using. Behavioral instructions beat informational descriptions.

**Symptom keywords > solution keywords.** Developers search "white screen" and "slow launch", not "Task.detached". Stripping symptom keywords from entries makes them unfindable. Every entry must preserve the words someone would actually search for.

**Instructions beat knowledge.** Writing "experience is stored here" doesn't drive behavior. Writing "you MUST search here first" does. CLAUDE.md content must be imperative behavioral rules, not reference documentation.

See [docs/lessons-learned.md](docs/lessons-learned.md) for the full list.

## Docs

| Document | Content |
|----------|---------|
| [How It Works](docs/how-it-works.md) | Architecture and behavioral design |
| [Shortwave Spec](docs/shortwave-spec.md) | Shortwave format, refinement rules |
| [Writing Good Entries](docs/writing-good-entries.md) | Format, keywords, and examples |
| [Lessons Learned](docs/lessons-learned.md) | What we tried, what failed, what works |
| [Example Topics](examples/topics/) | Sample topic file |

## License

MIT
