# RadioHeader

**Cross-project memory for Claude Code and Codex.** Stop re-solving bugs you already fixed in another project.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Runtime: Claude Code](https://img.shields.io/badge/Claude%20Code-supported-6b4bff)](https://claude.com/claude-code)
[![Runtime: Codex CLI](https://img.shields.io/badge/Codex%20CLI-supported-10a37f)](https://developers.openai.com/codex/cli)

[中文文档](README_zh.md)

> **v2.0 — Codex CLI support.** RadioHeader now works on both Claude Code **and** OpenAI Codex CLI from a single install. The same `topics/`, `shortwave/`, and project memory are shared between the two runtimes; an experience captured on one agent is immediately searchable from the other. See [Runtime Support](#runtime-support) below.

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

**Echo (Experience Flows Back)** — After each task, experience automatically flows back into the memory system. The feedback loop is runtime-native: Claude Code uses `PostToolUse Write|Edit` to trigger Echo the moment memory is written; Codex CLI uses a `UserPromptSubmit` snapshot + `Stop` diff so the same "memory → topics → shortwave" chain is enforced with a `decision: block` continuation if any step is skipped. The rules fire regardless of which agent you're driving, and both runtimes share one data layer.

**Shortwave (Knowledge Distillation)** — Topic entries contain project-specific details (`[source:MyApp]`). Shortwave strips out project names, file paths, and framework details into universal, project-agnostic knowledge units — searchable across any tech stack. This also protects privacy: raw entries might contain project paths, internal naming, or API keys. Shortwave removes all of that.

**Search → Apply → Trace** — Not a suggestion, a mandatory behavioral rule injected into `CLAUDE.md` and `AGENTS.md`. When the agent finds relevant experience, it **must** cite and apply it. Finding experience but ignoring it is explicitly prohibited.

**Learn (External Knowledge)** — RadioHeader isn't limited to lessons learned the hard way. The `learn` command extracts articles from any URL — including walled gardens like WeChat Official Accounts, Medium, and Substack — and distills them into shortwave entries. This turns RadioHeader from a passive experience manager into an active **information gateway** for Claude Code: not just remembering mistakes, but actively absorbing knowledge from the outside world.

**Context Digest (Attention-Compressed Awareness)** — Inspired by [Kimi's Attention Residuals](https://github.com/MoonshotAI/Attention-Residuals) research, RadioHeader builds a compressed environmental awareness profile that gets injected at session start. Instead of weighting search results (which adds little value when content matching already works), the attention mechanism operates at the **memory consolidation** level — like sleep consolidation in human memory. Every few memory syncs, `consolidate` automatically runs and produces a `context-digest.md` containing: user traits (problem-solving style, strengths, known weaknesses), a full project landscape with **scope annotations** (each project's path, so the Agent can navigate directly), recent search patterns, and cross-project technology overlaps. The digest enforces a **3,500-character budget** (inspired by Claude Code's internal 4K-per-file instruction limit) — when projects grow, lower-priority sections are automatically dropped to stay within budget, with a secondary guard in the loader hook. The Agent starts every session already knowing who it's helping — not just what code it's looking at.

**User Profile (Three Dimensions)** — RadioHeader maintains a user model across three dimensions: (1) **What you've done** — project portfolio with domains, problems, and pain points tracked in `project-registry.json`; (2) **How you work** — problem-solving style, interaction preferences, known strengths and weaknesses; (3) **What you have** — devices, network access, infrastructure. This profile serves as the "query vector" for memory consolidation — it determines what gets emphasized, what gets connected, and what the Agent should proactively watch for.

**Community Sharing** — Opt-in community shortwave library. Your local experience stays local; when you choose to publish, entries pass three gates (quality score ≥6/8, privacy scan, dedup check) before reaching the shared pool. Quality follows a [Stigmergy](https://en.wikipedia.org/wiki/Stigmergy) model — like ant pheromone trails: good entries get reinforced through usage, bad entries decay naturally.

## Runtime Support

RadioHeader ships a single data layer (`~/.claude/radioheader/`) with **runtime adapters** that plug into whichever coding agent you're using — Claude Code, OpenAI Codex CLI, or both at once.

| | Claude Code | Codex CLI |
|---|---|---|
| Entry file | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` |
| Global hooks | `~/.claude/settings.json` | `~/.codex/hooks.json` |
| SessionStart context | `radioheader-loader.sh` (plain stdout) | `radioheader-loader.sh` (plain stdout) |
| Echo-back trigger | `PostToolUse Write\|Edit` (immediate) | `UserPromptSubmit` snapshot + `Stop` diff |
| Search → Apply → Trace rules | Injected into `CLAUDE.md` | Injected into `AGENTS.md` |
| Per-project scaffold | `.claude/rules/`, `.claude/settings.json`, `CLAUDE.md` | `.codex/hooks.json`, `.codex/hooks/`, `AGENTS.md` |

The Codex adapter uses a **snapshot + diff** loop: the `UserPromptSubmit` hook takes a lightweight fingerprint of `memory/`, `topics/`, `shortwave/`, project docs, and up to 10k files of the repo before each turn; the `Stop` hook diffs against that fingerprint and decides what to do:

- Memory changed but no global topic updated → `decision: block` with a continuation prompt asking the agent to echo the experience.
- Topic changed but no shortwave entry distilled → `decision: block` asking for the shortwave follow-up.
- Both sides updated → `{"continue": true}` with a `systemMessage` checklist (log writing, overview sync).

This reproduces the Claude Code `PostToolUse`/`Stop` loop using the hook events Codex actually exposes, so the behavior is the same from the user's perspective: experience flows back automatically, and both runtimes see each other's knowledge.

### Compatibility notes

- Requires `codex-cli 0.118.0+` for the `Stop` hook and `UserPromptSubmit` hook support.
- Python hooks target **Python 3.7+** (use `from __future__ import annotations`) — compatible with the `/usr/bin/python3` that ships with macOS.
- The snapshot walker caps at 10k files per repo to stay under ~300ms even on 100k+ file monorepos, with a 24-hour TTL on stale snapshots.
- `upgrade` never overwrites user-customized `CLAUDE.md`, `AGENTS.md`, `settings.json`, `hooks.json`, or drifted `.claude/rules/*.md` files — it reports drift and leaves them alone.

## Quick Start

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh --runtime both
```

That's it. Start Claude Code or Codex in any project and RadioHeader is active — hooks fire, rules are loaded, experience is searchable. The installer is fault-tolerant: if your existing `settings.json` or `~/.codex/hooks.json` is corrupted, it backs up and rebuilds automatically instead of failing.

Install flags:

```bash
./install.sh --runtime claude   # only Claude Code
./install.sh --runtime codex    # only Codex CLI
./install.sh --runtime both     # default — both runtimes
```

Uninstalling a single runtime (`./uninstall.sh --runtime codex`) is also supported and leaves the shared data and the other runtime untouched.

Optionally, run `radioheader init` inside a project to add per-project scaffolding (Echo rules, log directory, doc templates). This is not required — RadioHeader works globally without it.

## How It Works

```
RadioHeader (~/.claude/radioheader/)
├── shortwave/            ← refined, project-agnostic knowledge
├── topics/               ← detailed experience with [source:] tags
├── project-registry.json ← project cards (domains, problems, pain points)
├── user-profile.md       ← user traits (work style, resources)
├── context-digest.md     ← attention-compressed awareness (auto-generated)
└── INDEX.md              ← master index

    ▲ Echo        ║ search      consolidate ──→ context-digest.md
    ║             ▼                                    ║
                                                       ▼
Project A memory/    Project B memory/    SessionStart (injected)
```

When you solve a bug, the runtime records it in the project's memory. Claude uses PostToolUse to prompt the Echo step immediately; Codex snapshots the turn and uses Stop-hook continuation to ask for any missing Echo or shortwave follow-up. If the experience is useful cross-project, it flows up to `topics/` with a `[source:ProjectName]` tag, then gets distilled into a `shortwave/` entry.

The three layers connect like this: experience flows back to **RadioHeader** via **Echo**, then **Shortwave** strips project noise and turns it into reusable knowledge that can be broadcast across all projects.

Later, in a different project, Claude hits a similar issue. The **Search → Apply → Trace** rule kicks in: search RadioHeader first, cite and apply what's found, trace back to the source project if more detail is needed.

### Learn — The Second Channel

Echo captures experience from mistakes. `learn` captures knowledge from articles:

```
Sources                     RadioHeader               Consumers
─────────────────           ─────────────────         ─────────────────
Bug fixes (Echo) ────────→                        ──→ search command
Web articles (learn) ────→  topics/ + shortwave/  ──→ Agent Search→Apply→Trace
Community (sync) ────────→                        ──→ publish to community
User behavior ───────────→  consolidate           ──→ context-digest (SessionStart)
```

This makes RadioHeader an **information gateway** — the single entry point through which external knowledge flows into Claude Code's working memory. Not a browser, not a bookmark manager — a system that absorbs, distills, and serves knowledge exactly when it's needed.

### Consolidate — Memory During Sleep

Human memory compresses during sleep: episodes fade, but patterns and skills solidify. RadioHeader's `consolidate` command does the same:

```
Memory syncs accumulate → every 5 syncs, consolidate runs automatically
                                    ↓
                  Analyzes search logs + project activity + user profile
                                    ↓
                  Generates context-digest.md (compressed awareness)
                                    ↓
                  Next session: Agent starts with full environmental context
```

The context digest tells the Agent, before any code is read:
- **Who it's helping** — problem-solving style, strengths, known weaknesses
- **What they're working on** — 12 projects with their domains, pain points, activity levels
- **What they've been searching** — recent focus areas and hot topics
- **Where technologies overlap** — which skills transfer across projects

This is not search optimization — it's **Agent calibration**. The difference: without the digest, the Agent treats every user the same. With it, the Agent knows this user tends toward greedy initialization on startup paths, has weak schema migration testing habits, and is currently focused on search quality improvements. That context shapes every recommendation.

### Community Sharing

The default community repository is [radioheader-community](https://github.com/ZaptainZ/radioheader-community) (you can point to your own via `config.json`).

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

### MCP Server

RadioHeader ships an optional MCP server so any [Model Context Protocol](https://modelcontextprotocol.io/)-compatible agent — Cursor, Claude Desktop, Windsurf, Continue.dev — can query the same experience layer:

```bash
pip install "mcp[cli]"                    # one-time dependency
radioheader mcp-server                    # starts stdio server
```

The server exposes 8 read-only tools (`radioheader_search`, `radioheader_list_projects`, `radioheader_trace_project`, `radioheader_read_shortwave`, `radioheader_read_topic`, `radioheader_list_topics`, `radioheader_context_digest`, `radioheader_stats`) backed by the same FTS5 + synonym search the CLI uses.

See [docs/mcp-server.md](docs/mcp-server.md) for client-specific setup (Claude Desktop, Cursor, etc.) and a recommended system prompt.

> **Note:** If you use [RadioMind](https://github.com/ZaptainZ/radiomind), its MCP server already includes RadioHeader search — you don't need both.

## Tips

**Manually trigger Echo.** Hooks handle most of it automatically, but you can also tell Claude in plain language at any time:

- *"Sync project info"* — Claude updates the project overview doc and checks for global Echo
- *"Update memory"* — Claude reviews what was learned and writes to memory/topics
- *"Write a log for today's work"* — Claude creates a task log in the logs directory

This is useful after a long session, when you finish a feature, or whenever you feel recent work should be recorded before the session ends.

## CLI

| Command | Description |
|---------|-------------|
| `radioheader init` | Initialize the experience framework in your project (`--runtime claude|codex|both`) |
| `radioheader search <query>` | Search across all topics, shortwave, and community |
| `radioheader index [--rebuild]` | Build/update FTS5 search index (BM25 + synonyms) |
| `radioheader learn <url>` | Extract web article and generate shortwave entry |
| `radioheader consolidate` | Update project weights and generate context digest |
| `radioheader upgrade` | Upgrade all registered projects to latest templates |
| `radioheader status` | Show topic count, entry count, community status |
| `radioheader doctor` | Run health checks on hooks, rules, and registry |
| `radioheader align` | Analyze topics↔shortwave coverage |
| `radioheader align --execute` | Output batch refinement instructions for Claude |
| `radioheader align --refs` | Validate and fix shortwave reference links |
| `radioheader community on\|off\|status` | Toggle community sharing |
| `radioheader sync` | Pull latest community library + push votes/entries |
| `radioheader publish <file>` | Publish a shortwave to community (3-gate check) |
| `radioheader publish --auto-detect` | Scan all local shortwave for publishable entries |
| `radioheader vote <id> [+1\|-1]` | Vote on a shortwave entry |
| `radioheader device-sync init <url>` | Set up cross-device sync via git |
| `radioheader device-sync push\|pull` | Push/pull RadioHeader data between devices |
| `radioheader mcp-server` | Run the MCP server (stdio) for Cursor, Claude Desktop, etc. |

```bash
# Search by symptoms, not solutions
radioheader search "white screen|slow launch|startup"

# Initialize a new project with flags
radioheader init --runtime both --name "MyAPI" --stack "Python/FastAPI" --doc-dir docs

# Enable community and sync
radioheader community on
radioheader sync
```

## Lessons Learned

Built through real usage across 13 projects. Three lessons that shaped everything:

**"Searched but didn't use" — the #1 failure mode.** Early versions told Claude to search RadioHeader. It would search, find results, and completely ignore them. The fix: make it three mandatory steps (Search → Apply → Trace) with an explicit prohibition on finding but not using. Behavioral instructions beat informational descriptions.

**Symptom keywords > solution keywords.** Developers search "white screen" and "slow launch", not "Task.detached". Stripping symptom keywords from entries makes them unfindable. Every entry must preserve the words someone would actually search for.

**Instructions beat knowledge.** Writing "experience is stored here" doesn't drive behavior. Writing "you MUST search here first" does. `CLAUDE.md` / `AGENTS.md` content must be imperative behavioral rules, not reference documentation.

**Attention belongs in compression, not retrieval.** We initially applied attention weights to search results (boosting entries from active projects). Testing showed zero meaningful ranking changes — BM25 content matching already gets the right results. The real value of attention is in memory consolidation: compressing the user's project landscape, behavioral patterns, and known weaknesses into a digest that shapes how the Agent thinks, not what it finds.

See [docs/lessons-learned.md](docs/lessons-learned.md) for the full list.

## Docs

| Document | Content |
|----------|---------|
| [How It Works](docs/how-it-works.md) | Architecture and behavioral design |
| [Quality Standards](docs/quality-standards.md) | Scoring rubric and audit checklist |
| [Shortwave Spec](docs/shortwave-spec.md) | Shortwave format, refinement rules |
| [Writing Good Entries](docs/writing-good-entries.md) | Format, keywords, and examples |
| [Lessons Learned](docs/lessons-learned.md) | What we tried, what failed, what works |
| [MCP Server](docs/mcp-server.md) | Setup guide for Cursor, Claude Desktop, etc. |
| [Example Topics](examples/topics/) | Sample topic file |

## License

MIT
