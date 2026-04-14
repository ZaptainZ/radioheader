# RadioHeader

**Cross-project memory for coding agents — stop re-solving bugs you already fixed in another project.**

```
You: App shows white screen for 10+ seconds on launch

Claude: RadioHeader has experience from ProjectA:
        "Task {} in SwiftUI .onAppear inherits Main Actor —
        iCloud I/O blocks main thread, causing 10s+ white screen.
        Fix: use Task.detached(priority:)"

        Verifying this applies here... ✓ Same pattern. Applying fix.
```

One install. Works on Claude Code, Codex CLI, and any MCP-compatible agent. Zero config.

[中文文档](README_zh.md) · [How It Works](docs/how-it-works.md) · [MCP Server](docs/mcp-server.md) · [Lessons Learned](docs/lessons-learned.md)

---

## What it does

Coding agents are great at analysis but don't accumulate experience. Even with built-in memory, project memories are completely isolated: what Project A learned, Project B has no idea about.

RadioHeader solves this with three mechanisms:

| Mechanism | What it does |
|-----------|-------------|
| **Echo** | After each task, experience flows back from the project into the global memory hub — automatically, via hooks |
| **Search → Apply → Trace** | A mandatory behavioral rule injected into `CLAUDE.md` / `AGENTS.md`. The agent **must** search before starting independent analysis, **must** cite what it finds, and is **prohibited** from ignoring matching experience |
| **Shortwave** | Strips project names, file paths, and framework details from experience entries, producing universal knowledge units searchable across any tech stack |

The result: the second time any agent in any project hits a similar problem, the answer is already there. Minutes to seconds.

## What RadioHeader adds to coding agents

| Capability | Without RadioHeader | With RadioHeader |
|-----------|---------------------|------------------|
| **Cross-project experience** | Each project is an island | Experience from 12+ projects flows to wherever it's needed |
| **Enforce memory usage** | Agent searches, finds results, ignores them | Search → Apply → Trace: finding but not using is explicitly prohibited |
| **Learn from articles** | Copy-paste into prompts | `radioheader learn <url>` extracts and distills into searchable entries |
| **Agent calibration** | Agent treats every user the same | Context digest: knows your project landscape, strengths, known weaknesses |
| **Community knowledge** | Start from zero | Opt-in shared library with Stigmergy quality governance |

---

## How memory flows

```
Conversation (bug fix, feature, debugging session)
     │
     ▼
 ┌─ Echo (automatic, via hooks) ─────────────────────┐
 │  Claude: PostToolUse Write|Edit → immediate        │
 │  Codex:  UserPromptSubmit snapshot + Stop diff      │
 │  Result: experience written to project memory/      │
 └───────────────────────────┬───────────────────────┘
                             ▼
 ┌─ Three-Layer Memory ──────────────────────────────┐
 │                                                    │
 │  Project memory/ ─── is this cross-project? ──→    │
 │                          yes ↓                     │
 │  RadioHeader topics/ ──── [source:ProjectName] ──→ │
 │                          distill ↓                 │
 │  RadioHeader shortwave/ ── project-agnostic ──→    │
 │                          searchable everywhere     │
 └───────────────────────────┬───────────────────────┘
                             ▼
 ┌─ Search → Apply → Trace ──────────────────────────┐
 │  Next time any agent hits a similar problem:       │
 │  1. Search: Grep with symptom keywords             │
 │  2. Apply:  Cite the matching entry in the answer  │
 │  3. Trace:  Follow [source:] to the origin project │
 └──────────────────────────────────────────────────┘
```

```
RadioHeader (~/.claude/radioheader/)
├── shortwave/            ← refined, project-agnostic knowledge
├── topics/               ← detailed experience with [source:] tags
├── project-registry.json ← project cards (domains, problems, pain points)
├── context-digest.md     ← attention-compressed awareness (auto-generated)
└── INDEX.md              ← master index
```

<details>
<summary><b>Consolidate — memory during sleep</b></summary>

Human memory compresses during sleep: episodes fade, but patterns solidify. RadioHeader's `consolidate` does the same:

```
Memory syncs accumulate → every 5 syncs, consolidate runs automatically
                                    ↓
                  Analyzes search logs + project activity + user profile
                                    ↓
                  Generates context-digest.md (compressed awareness)
                                    ↓
                  Next session: Agent starts knowing who it's helping
```

The digest tells the Agent, before any code is read: problem-solving style, project landscape, recent focus areas, technology overlaps, known weaknesses. Not search optimization — **Agent calibration**.

When [RadioMind](https://github.com/ZaptainZ/radiomind) is installed, consolidation auto-upgrades to dream refinement (SHY pruning + DMN wandering).

</details>

<details>
<summary><b>Community sharing — Stigmergy quality model</b></summary>

Opt-in community library ([radioheader-community](https://github.com/ZaptainZ/radioheader-community)). Quality follows a [Stigmergy](https://en.wikipedia.org/wiki/Stigmergy) model — like ant pheromone trails:

- New entries get a 30-day exposure period
- Usage triggers automatic voting (LLM judges causal contribution)
- Votes aggregate weekly via GitHub Actions into scores
- High-score entries get `verified`; low-score entries decay and archive

Publishing goes through three gates: quality (≥6/8), privacy scan, dedup check.

```
📡 Shortwave (local)     — your own experience (highest priority)
🌐 Community (shared)    — entries from other users, with quality scores
📂 Topics (detailed)     — raw topic entries with [source:] tags
```

</details>

<details>
<summary><b>MCP server — for Cursor, Claude Desktop, and other agents</b></summary>

RadioHeader ships an optional MCP server (8 read-only tools) so any [MCP](https://modelcontextprotocol.io/)-compatible agent can query the same experience layer:

```bash
pip install "mcp[cli]"
radioheader mcp-server          # starts stdio server
```

Tools: `radioheader_search`, `radioheader_list_projects`, `radioheader_trace_project`, `radioheader_read_shortwave`, `radioheader_read_topic`, `radioheader_list_topics`, `radioheader_context_digest`, `radioheader_stats`.

See [docs/mcp-server.md](docs/mcp-server.md) for client-specific setup and a recommended system prompt.

> If you use [RadioMind](https://github.com/ZaptainZ/radiomind), its MCP server already includes RadioHeader search — you don't need both.

</details>

---

## Runtime support

RadioHeader ships a single data layer with **runtime adapters** that plug into whichever coding agent you're using:

| | Claude Code | Codex CLI | MCP agents |
|---|---|---|---|
| Entry file | `~/.claude/CLAUDE.md` | `~/.codex/AGENTS.md` | System prompt |
| Echo trigger | `PostToolUse Write\|Edit` | `UserPromptSubmit` snapshot + `Stop` diff | — |
| Per-project scaffold | `.claude/settings.json` | `.codex/hooks.json` | — |

The Codex adapter uses a **snapshot + diff** loop: `UserPromptSubmit` fingerprints memory/topics/shortwave before each turn; `Stop` diffs against that fingerprint and uses `decision: block` with a continuation prompt if any step in the Echo chain was skipped.

Python hooks target **Python 3.7+** (`from __future__ import annotations`). Snapshot walker caps at 10k files with 24h TTL cleanup.

---

## Setup

```bash
git clone https://github.com/ZaptainZ/radioheader.git
cd radioheader
./install.sh --runtime both
```

That's it. Start Claude Code or Codex in any project — hooks fire, rules are loaded, experience is searchable.

```bash
./install.sh --runtime claude   # only Claude Code
./install.sh --runtime codex    # only Codex CLI
./install.sh --runtime both     # default
```

Optionally, run `radioheader init` inside a project for per-project scaffolding (Echo rules, log directory, doc templates).

## Use

```bash
# Search by symptoms, not solutions
radioheader search "white screen|slow launch|startup"

# Initialize a project
radioheader init --name "MyAPI" --stack "Python/FastAPI"

# Learn from an article
radioheader learn https://example.com/article

# Check health
radioheader doctor
```

**Full CLI:**

| Command | What it does |
|---------|-------------|
| `search <query>` | BM25 + synonym search across topics, shortwave, community |
| `init` | Project scaffolding (`--runtime claude\|codex\|both`) |
| `index [--rebuild]` | Build/update FTS5 search index |
| `learn <url>` | Extract article into shortwave entry |
| `consolidate` | Update attention weights and context digest |
| `upgrade` | Upgrade registered projects to latest templates |
| `status` | Topic count, shortwave count, community status |
| `doctor` | Health check: hooks, rules, registry, RadioMind |
| `align` | Topics↔shortwave coverage analysis |
| `community on\|off` | Toggle community library |
| `sync` | Pull community library + push votes |
| `publish <file>` | Publish shortwave to community (3-gate check) |
| `vote <id> [+1\|-1]` | Vote on a shortwave entry |
| `device-sync` | Cross-device sync via git |
| `mcp-server` | Run MCP server (stdio) for Cursor, Claude Desktop |

---

## RadioMind integration

[RadioMind](https://github.com/ZaptainZ/radiomind) is a bionic memory core for AI agents — it distills scattered conversations into deep habits through three-body debate and dream refinement, then serves them back when they matter. RadioHeader captures and enforces; RadioMind refines and deepens.

When RadioMind is installed, RadioHeader **automatically upgrades itself** — no config needed:

| Command | Without RadioMind | With RadioMind |
|---------|-------------------|----------------|
| `radioheader search` | FTS5 + synonym expansion | Pyramid retrieval + knowledge graph + habit matching |
| `radioheader consolidate` | Attention weights + context digest | Dream refinement (SHY pruning + DMN wandering) + richer digest |

RadioMind reads RadioHeader's `topics/` and `shortwave/` files directly. RadioHeader doesn't need to know RadioMind exists — it just detects `radiomind` on PATH and delegates `search` and `consolidate`. If RadioMind fails or is absent, the native path runs seamlessly.

```
RadioHeader (capture + rules)              RadioMind (refine + enhance)
─────────────────────────                  ─────────────────────────
Echo hooks → write topics/shortwave/ ────→ adapter reads, indexes, refines
radioheader search ─── radiomind? yes ──→ radiomind rh-search
                   └── no ──→ fts-search.py (native)
radioheader consolidate ── radiomind? ──→ radiomind rh-consolidate
                        └── no ──→ attn-consolidate.py (native)
```

## Community library

[radioheader-community](https://github.com/ZaptainZ/radioheader-community) is an opt-in shared library of shortwave entries contributed by the RadioHeader community. Your local experience stays local; entries you choose to publish pass three gates before reaching the shared pool.

```bash
radioheader community on          # enable
radioheader sync                  # pull shared library + push your votes
radioheader publish <file>        # publish (quality ≥6/8 + privacy + dedup)
```

Quality governance follows a [Stigmergy](https://en.wikipedia.org/wiki/Stigmergy) model — like ant pheromone trails: good entries get reinforced through usage, bad entries decay naturally, no human curation needed.

| Step | What happens |
|------|-------------|
| **Exposure** | New entries get a 30-day exposure window |
| **Voting** | Usage triggers automatic LLM-judged causal contribution votes |
| **Aggregation** | GitHub Actions aggregates votes weekly into quality scores |
| **Lifecycle** | High-score entries get `verified`; low-score entries decay and archive |

When enabled, search results blend three sources with clear priority:

```
📡 Shortwave (local)     — your own experience (highest priority)
🌐 Community (shared)    — entries from other users, with quality scores
📂 Topics (detailed)     — raw topic entries with [source:] tags
```

---

## Lessons learned

Built through real usage across 13 projects. Four lessons that shaped everything:

**"Searched but didn't use" — the #1 failure mode.** Claude would search, find results, and ignore them. The fix: three mandatory steps (Search → Apply → Trace) with an explicit prohibition on finding but not using.

**Symptom keywords > solution keywords.** Developers search "white screen" and "slow launch", not "Task.detached". Every entry must preserve the words someone would actually search for.

**Instructions beat knowledge.** Writing "experience is stored here" doesn't drive behavior. Writing "you MUST search here first" does. `CLAUDE.md` / `AGENTS.md` content must be imperative behavioral rules, not reference documentation.

**Attention belongs in compression, not retrieval.** Attention-weighted search ranking added zero value — BM25 already gets the right results. The real value is in memory consolidation: compressing the user's project landscape into a digest that shapes how the Agent thinks.

See [docs/lessons-learned.md](docs/lessons-learned.md) for the full list.

---

## Radio ecosystem

| Project | What it does | Relationship | Status |
|---------|-------------|--------------|--------|
| **RadioHeader** | Cross-project experience framework for coding agents. Captures debugging experience and enforces its reuse. | This repo. The "rules and capture" layer. | Released, 240+ shortwave entries |
| **[RadioMind](https://github.com/ZaptainZ/radiomind)** | Bionic memory core. Distills conversations into habits through three-body debate and dream refinement. | Uses RadioHeader's data. RadioHeader auto-upgrades search/consolidate when RadioMind is installed. | Released |
| **RadioHand** | Personal agent framework. Multi-channel, task planning, tool orchestration. | Will use RadioMind as memory, RadioHeader as experience rules. | Planned |

```
RadioHeader (rules & experience) → RadioMind (memory & habits) → RadioHand (actions & channels)
         head                              brain                          hands
```

## Docs

| Document | Content |
|----------|---------|
| [How It Works](docs/how-it-works.md) | Architecture and behavioral design |
| [MCP Server](docs/mcp-server.md) | Setup for Cursor, Claude Desktop, etc. |
| [Shortwave Spec](docs/shortwave-spec.md) | Shortwave format and refinement rules |
| [Quality Standards](docs/quality-standards.md) | Scoring rubric and audit checklist |
| [Writing Good Entries](docs/writing-good-entries.md) | Format, keywords, and examples |
| [Lessons Learned](docs/lessons-learned.md) | What we tried, what failed, what works |

## License

MIT
