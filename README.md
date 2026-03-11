# RadioHeader

**Cross-project memory for Claude Code.** Stop re-solving bugs you already fixed in another project.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

[中文文档](README_zh.md)

## The Problem

Coding agents like Claude Code are great at analysis, but they don't accumulate experience. Even with the built-in memory system, Claude remembers the general direction — not the key details. And project memories are completely isolated: what Project A learned, Project B has no idea about.

Existing tools (`.cursorrules`, `awesome-rules`, CLAUDE.md) work at the "rules" level. RadioHeader works at the **experience** level — the kind of know-how you only get by hitting a problem yourself, solving it, and writing it down.

The name — I'm a fan of the band Radiohead, and this system works like a signal tower that projects tune into when they need information. RadioHeader.

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

From the second time onward, the same class of problem goes from minutes to seconds. Not because the AI got smarter — because the answer was already there.

## Key Features

**Three-Layer Memory** — RadioHeader (global, shared by all projects) → Project memory (project-specific) → Session context (ephemeral). Experience flows up from projects to the global hub, then back down to wherever it's needed.

**Echo (Experience Flows Back)** — After each task, experience automatically flows back into the memory system. Four hooks drive the cycle: SessionStart shows status, PostToolUse detects memory writes and triggers Echo, Stop reminds Claude to check for new experience. No manual intervention needed.

**Shortwave (Knowledge Distillation)** — Topic entries contain project-specific details (`[source:MyApp]`). Shortwave strips out project names, file paths, and framework details into universal, project-agnostic knowledge units — searchable across any tech stack. This also protects privacy: raw entries might contain project paths, internal naming, or API keys. Shortwave removes all of that.

**Search → Apply → Trace** — Not a suggestion, a mandatory behavioral rule injected into CLAUDE.md. When Claude finds relevant experience, it **must** cite and apply it. Finding experience but ignoring it is explicitly prohibited.

**Community Sharing** — Opt-in community shortwave library. Your local experience stays local; when you choose to publish, entries pass three gates (quality score ≥6/8, privacy scan, dedup check) before reaching the shared pool. Quality follows a [Stigmergy](https://en.wikipedia.org/wiki/Stigmergy) model — like ant pheromone trails: good entries get reinforced through usage, bad entries decay naturally.

## Quick Start

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh
```

That's it. Start Claude Code in any project and RadioHeader is active — hooks fire, rules are loaded, experience is searchable.

Optionally, run `radioheader init` inside a project to add per-project scaffolding (Echo rules, log directory, doc templates). This is not required — RadioHeader works globally without it.

## How It Works

```
RadioHeader (~/.claude/radioheader/)
├── shortwave/   ← refined, project-agnostic knowledge (Shortwave)
├── topics/      ← detailed experience with [source:] tags
└── INDEX.md     ← master index

    ▲ Echo   ║ search
    ║        ▼

Project A memory/    Project B memory/    Project N memory/
```

When you solve a bug, Claude records it in the project's memory. A PostToolUse hook fires and prompts Claude to check: *is this useful cross-project?* If yes, it flows up to `topics/` with a `[source:ProjectName]` tag, then gets distilled into a `shortwave/` entry.

The three layers connect like this: experience flows back to **RadioHeader** via **Echo**, then **Shortwave** strips project noise and turns it into reusable knowledge that can be broadcast across all projects.

Later, in a different project, Claude hits a similar issue. The **Search → Apply → Trace** rule kicks in: search RadioHeader first, cite and apply what's found, trace back to the source project if more detail is needed.

### Community Sharing

When community is enabled (`radioheader community on`), search results include entries from the shared pool alongside your local ones:

```
📡 Shortwave (local)     — your own refined experience (highest priority)
🌐 Community (shared)    — entries from other users, with quality scores
📂 Topics (detailed)     — your raw topic entries
```

The quality lifecycle follows a [Stigmergy](https://en.wikipedia.org/wiki/Stigmergy) model — like ant pheromone trails:
- New entries get a 30-day exposure period
- Usage triggers automatic voting (LLM judges causal contribution)
- Votes aggregate weekly via GitHub Actions into scores
- High-score entries get `verified`; low-score entries decay and archive

Publishing goes through three gates: quality (≥6/8), privacy scan (no paths/keys/source tags), and dedup check.

## Tips

**Manually trigger Echo.** Hooks handle most of it automatically, but you can also tell Claude in plain language at any time:

- *"Sync project info"* — Claude updates the project overview doc and checks for global Echo
- *"Update memory"* — Claude reviews what was learned and writes to memory/topics
- *"Write a log for today's work"* — Claude creates a task log in the logs directory

This is useful after a long session, when you finish a feature, or whenever you feel recent work should be recorded before the session ends.

## CLI

| Command | Description |
|---------|-------------|
| `radioheader init` | Initialize the experience framework in your project |
| `radioheader search <query>` | Search across all topics, shortwave, and community |
| `radioheader status` | Show topic count, entry count, community status |
| `radioheader doctor` | Run health checks on hooks, rules, and registry |
| `radioheader align` | Analyze topics↔shortwave coverage |
| `radioheader align --execute` | Output batch refinement instructions for Claude |
| `radioheader align --refs` | Validate and fix shortwave reference links |
| `radioheader community on\|off\|status` | Toggle community sharing |
| `radioheader sync` | Pull latest community library + push votes/entries |
| `radioheader publish <file>` | Publish a shortwave to community (3-gate check) |
| `radioheader publish --auto-detect` | Scan all local shortwave for publishable entries |
| `radioheader device-sync init <url>` | Set up cross-device sync via git |
| `radioheader device-sync push\|pull` | Push/pull RadioHeader data between devices |

```bash
# Search by symptoms, not solutions
radioheader search "white screen|slow launch|startup"

# Initialize a new project with flags
radioheader init --name "MyAPI" --stack "Python/FastAPI" --doc-dir docs

# Enable community and sync
radioheader community on
radioheader sync
```

## Lessons Learned

Built through real usage across 13 projects. Three lessons that shaped everything:

**"Searched but didn't use" — the #1 failure mode.** Early versions told Claude to search RadioHeader. It would search, find results, and completely ignore them. The fix: make it three mandatory steps (Search → Apply → Trace) with an explicit prohibition on finding but not using. Behavioral instructions beat informational descriptions.

**Symptom keywords > solution keywords.** Developers search "white screen" and "slow launch", not "Task.detached". Stripping symptom keywords from entries makes them unfindable. Every entry must preserve the words someone would actually search for.

**Instructions beat knowledge.** Writing "experience is stored here" doesn't drive behavior. Writing "you MUST search here first" does. CLAUDE.md content must be imperative behavioral rules, not reference documentation.

See [docs/lessons-learned.md](docs/lessons-learned.md) for the full list.

## Docs

| Document | Content |
|----------|---------|
| [How It Works](docs/how-it-works.md) | Architecture and behavioral design |
| [Quality Standards](docs/quality-standards.md) | Scoring rubric and audit checklist |
| [Shortwave Spec](docs/shortwave-spec.md) | Shortwave format, refinement rules |
| [Writing Good Entries](docs/writing-good-entries.md) | Format, keywords, and examples |
| [Lessons Learned](docs/lessons-learned.md) | What we tried, what failed, what works |
| [Example Topics](examples/topics/) | Sample topic file |

## License

MIT
